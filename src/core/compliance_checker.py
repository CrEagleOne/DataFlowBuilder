"""
src/core/compliance_checker.py – Vérificateur de conformité des flux
=====================================================================
Vérifie la conformité d'un fichier de données réel par rapport au
mapping d'un flux DataFlow Builder.

Contrôles effectués :
  • Encodage du fichier
  • Délimiteur de colonnes
  • Présence / absence d'en-tête et de pied de page
  • Nombre de champs par ligne vs mapping
  • Longueur de chaque champ vs longueur déclarée
  • Cohérence de type (alpha / num / date / bool / decimal)
  • Champs obligatoires vides (includeInOutput = True)
  • Format de date
  • Valeurs booléennes attendues
  • Cohérence du sous-type (email, SIRET, NIR, IBAN, code postal…)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

import csv
import io
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime

# Import au niveau module pour éviter un rechargement à chaque appel de méthode
from .field_types import DATE_FORMATS

logger = logging.getLogger(__name__)

# ── Sévérités ─────────────────────────────────────────────────────────────────
SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

# ── Correspondance bool attendu ────────────────────────────────────────────────
BOOL_EXPECTED: dict[str, list[str]] = {
    "ON": ["O", "N"],
    "OUINON": ["OUI", "NON"],
    "OKKO": ["OK", "KO"],
    "BINAIRE": ["0", "1"],
}

# ── Patterns de validation de sous-types ──────────────────────────────────────
_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_RE_SIRET = re.compile(r"^\d{14}$")
_RE_NIR = re.compile(r"^\d{15}$")
_RE_IBAN = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{1,30}$")
_RE_CODE_APE = re.compile(r"^\d{4}[A-Z]$")
_RE_CODE_POSTAL = re.compile(r"^\d{5}$")
_RE_CODE_INSEE = re.compile(r"^\d{5}$")
_RE_PHONE = re.compile(r"^(\+33|0)\d[\s.\-]?\d{2}[\s.\-]?\d{2}[\s.\-]?\d{2}[\s.\-]?\d{2}$")
_RE_PHONE_PLUS = re.compile(r"^\+33\d[\s.\-]?\d{2}[\s.\-]?\d{2}[\s.\-]?\d{2}[\s.\-]?\d{2}$")

# Table de contrôle des sous-types – construite une seule fois au chargement du module
# Format : sous_type -> (pattern, valeur_attendue, libellé_erreur, appliquer_upper)
_SUBTYPE_CHECKS: dict[str, tuple[re.Pattern, str, str, bool]] = {
    "email": (_RE_EMAIL, "adresse e-mail valide", "format email invalide", False),
    "siret": (_RE_SIRET, "14 chiffres", "format SIRET invalide", False),
    "nir": (_RE_NIR, "15 chiffres", "format NIR invalide", False),
    "iban": (_RE_IBAN, "IBAN (CC99...)", "format IBAN invalide", True),
    "codeApe": (_RE_CODE_APE, "4 chiffres + 1 lettre maj", "format code APE invalide", True),
    "codePostal": (_RE_CODE_POSTAL, "5 chiffres", "format code postal invalide", False),
    "codeInsee": (_RE_CODE_INSEE, "5 chiffres", "format code INSEE invalide", False),
    "phone": (_RE_PHONE, "numéro de téléphone FR", "format téléphone invalide", False),
    "phonePlus33": (_RE_PHONE_PLUS, "numéro +33...", "format téléphone +33 invalide", False),
}


# ═══════════════════════════════════════════════════════════════════════════════
# Structures de données
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class CheckResult:
    """Résultat d'un contrôle unitaire.

    Attributes:
        severity: Niveau de sévérité : ``'error'``, ``'warning'`` ou ``'info'``.
        category: Catégorie du contrôle (ex. ``'Longueur'``, ``'Type'``…).
        message:  Description lisible de l'écart.
        row:      Numéro de ligne du fichier concerné (0 = global).
        col_name: Nom du champ concerné (vide = contrôle global).
        expected: Valeur ou contrainte attendue.
        actual:   Valeur ou contrainte observée.
    """

    severity: str
    category: str
    message: str
    row: int = 0
    col_name: str = ""
    expected: str = ""
    actual: str = ""


@dataclass
class ComplianceReport:
    """Rapport complet de vérification de conformité.

    Attributes:
        flow_name:       Nom du flux vérifié.
        file_path:       Chemin du fichier analysé.
        checked_at:      Horodatage de l'analyse.
        total_rows:      Nombre de lignes de données analysées.
        results:         Liste de tous les :class:`CheckResult`.
        error_count:     Nombre d'erreurs.
        warning_count:   Nombre d'avertissements.
        info_count:      Nombre d'informations.
        is_compliant:    ``True`` si aucune erreur détectée.
        metadata:        Métadonnées diverses (encodage détecté, etc.).
    """

    flow_name: str
    file_path: str
    checked_at: datetime
    total_rows: int
    results: list[CheckResult] = field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    is_compliant: bool = True
    metadata: dict = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    # Lignes de résumé technique (une par contrôle global) pour le rapport exporté
    summary_lines: list[str] = field(default_factory=list)

    def add(self, result: CheckResult) -> None:
        """Ajoute un résultat et met à jour les compteurs.

        Args:
            result: Instance de :class:`CheckResult` à enregistrer.
        """
        self.results.append(result)
        if result.severity == SEVERITY_ERROR:
            self.error_count += 1
            self.is_compliant = False
        elif result.severity == SEVERITY_WARNING:
            self.warning_count += 1
        else:
            self.info_count += 1

    def to_text(self) -> str:
        """Génère un compte-rendu textuel simplifié et lisible.

        Chaque contrôle global (encodage, fins de ligne, délimiteur…) est
        résumé sur une seule ligne. Les écarts sont listés ensuite par sévérité.

        Returns:
            Chaîne multi-lignes contenant le rapport complet.
        """
        lines: list[str] = []
        sep = "═" * 72
        sep2 = "─" * 72

        conformity = "✅ CONFORME" if self.is_compliant else "❌ NON CONFORME"

        lines.append(sep)
        lines.append("  RAPPORT DE CONFORMITÉ – DATA FLOW BUILDER")
        lines.append(sep)
        lines.append(f"  Flux      : {self.flow_name}")
        lines.append(f"  Fichier   : {self.file_path}")
        lines.append(f"  Date      : {self.checked_at.strftime('%d/%m/%Y à %H:%M:%S')}")
        lines.append(sep2)

        # ── Résumé technique (une ligne par contrôle) ─────────────────────────
        for item in self.summary_lines:
            lines.append(f"  {item}")
        lines.append(sep2)

        # ── Bilan ─────────────────────────────────────────────────────────────
        lines.append(
            f"  {conformity}   "
            f"❌ {self.error_count} erreur(s)   "
            f"⚠️  {self.warning_count} avert.   "
            f"ℹ️  {self.info_count} info(s)   "
            f"⏱ {self.elapsed_seconds:.2f} s   "
            f"📄 {self.total_rows} ligne(s)"
        )
        lines.append(sep)

        # ── Détail des écarts ──────────────────────────────────────────────────
        if not self.results:
            lines.append("  Aucun écart détecté.")
        else:
            for sev, icon in [
                (SEVERITY_ERROR, "❌"),
                (SEVERITY_WARNING, "⚠️ "),
                (SEVERITY_INFO, "ℹ️ "),
            ]:
                group = [r for r in self.results if r.severity == sev]
                if not group:
                    continue
                label = {
                    "error": "ERREURS",
                    "warning": "AVERTISSEMENTS",
                    "info": "INFORMATIONS",
                }[sev]
                lines.append(f"\n  {icon} {label} ({len(group)})")
                lines.append("  " + sep2)
                for r in group:
                    loc = f"Ligne {r.row}" if r.row else "Global"
                    col = f" | {r.col_name}" if r.col_name else ""
                    tag = f"[{r.category}]"
                    lines.append(f"  {loc}{col}  {tag}  {r.message}")
                    if r.expected and r.actual and r.expected != r.actual:
                        lines.append(f"      Attendu : {r.expected}  →  Observé : {r.actual}")

        lines.append("\n" + sep)
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# Vérificateur principal
# ═══════════════════════════════════════════════════════════════════════════════


class ComplianceChecker:
    """Vérifie la conformité d'un fichier de données par rapport à un flux.

    Args:
        flow_manager: Instance de :class:`core.flow_manager.FlowManager`
                      contenant le flux chargé à vérifier.
        progress_cb:  Callback optionnel ``(message: str) -> None`` pour
                      signaler la progression à l'interface.

    Example:
        >>> checker = ComplianceChecker(app.flow_manager)
        >>> report = checker.check_file("/chemin/vers/fichier.csv")
        >>> print(report.to_text())
    """

    # Nombre maximal de lignes analysées en détail (performance)
    _MAX_DETAIL_ROWS = 1000

    def __init__(
        self,
        flow_manager,
        progress_cb: Callable[[str], None] | None = None,
    ) -> None:
        self.fm = flow_manager
        self._progress = progress_cb or (lambda msg: None)

    # ─── Point d'entrée ───────────────────────────────────────────────────────

    def check_file(self, file_path: str) -> ComplianceReport:
        """Lance l'analyse complète d'un fichier.

        Pour les formats JSON et XML, seules les vérifications de structure
        et d'encodage sont effectuées (pas de contrôle de délimiteur ni de
        champs). Pour CSV et longueur fixe, tous les contrôles s'appliquent.

        Args:
            file_path: Chemin absolu vers le fichier à analyser.

        Returns:
            Un :class:`ComplianceReport` rempli avec tous les écarts détectés.
        """
        flow = self.fm.current_flow or {}
        fmt = flow.get("format", "csv")
        report = ComplianceReport(
            flow_name=flow.get("name", "—"),
            file_path=file_path,
            checked_at=datetime.now(),
            total_rows=0,
        )
        _t0 = time.perf_counter()

        self._progress("Lecture du fichier…")
        raw_bytes = self._read_raw(file_path, report)
        if raw_bytes is None:
            report.elapsed_seconds = time.perf_counter() - _t0
            return report

        # ── 1. Encodage ───────────────────────────────────────────────────────
        content = self._check_encoding(raw_bytes, report)
        if content is None:
            report.elapsed_seconds = time.perf_counter() - _t0
            return report

        # ── 2. Structure (JSON / XML) ─────────────────────────────────────────
        self._progress("Vérification de la structure du fichier…")
        self._check_structure(content, fmt, report)

        # Pour JSON / XML, les contrôles délimiteur/champ ne s'appliquent pas
        if fmt in ("json", "xml"):
            report.elapsed_seconds = time.perf_counter() - _t0
            report.metadata["Durée"] = f"{report.elapsed_seconds:.2f} s"
            return report

        # ── 3. Fin de ligne ───────────────────────────────────────────────────
        self._check_line_endings(content, report)

        lines_raw = content.splitlines()
        report.total_rows = len(lines_raw)

        # ── 4. Délimiteur ─────────────────────────────────────────────────────
        self._progress("Vérification du délimiteur…")
        delimiter = flow.get("delimiter", ",")
        self._check_delimiter(lines_raw, delimiter, report)

        # ── 5. Présence en-tête / pied de page ────────────────────────────────
        self._progress("Vérification de la structure…")
        has_header_in_flow = bool(
            self.fm.header_fields and any(f.get("includeInOutput") for f in self.fm.header_fields)
        )
        has_footer_in_flow = bool(
            self.fm.footer_fields and any(f.get("includeInOutput") for f in self.fm.footer_fields)
        )
        self._check_header_footer(
            lines_raw, delimiter, has_header_in_flow, has_footer_in_flow, report
        )

        # ── 6. Découpage des lignes selon structure ────────────────────────────
        self._progress("Analyse des lignes de données…")
        data_lines = self._extract_data_lines(lines_raw, has_header_in_flow, has_footer_in_flow)

        for line_def in self.fm.field_lines:
            expected_fields = [f for f in line_def.get("fields", []) if f.get("includeInOutput")]
            if not expected_fields:
                continue

            self._progress(f"Contrôle de la ligne « {line_def.get('name', '?')} »…")

            for row_idx, raw_line in enumerate(data_lines[: self._MAX_DETAIL_ROWS], start=1):
                row_num = row_idx + (1 if has_header_in_flow else 0)
                parsed = self._split_row(raw_line, delimiter)

                self._check_field_count(parsed, expected_fields, row_num, line_def["name"], report)

                for col_idx, field_def in enumerate(expected_fields):
                    value = parsed[col_idx] if col_idx < len(parsed) else ""
                    fname = field_def.get("name", f"Champ {col_idx + 1}")

                    self._check_mandatory(value, field_def, row_num, fname, report)
                    self._check_length(value, field_def, row_num, fname, report)
                    self._check_type(value, field_def, row_num, fname, report)
                    self._check_subtype(value, field_def, row_num, fname, report)

        # ── 7. Finalisation ───────────────────────────────────────────────────
        report.elapsed_seconds = time.perf_counter() - _t0
        report.metadata["Durée"] = f"{report.elapsed_seconds:.2f} s"
        self._progress("Analyse terminée.")
        return report

    # ─── Lecture & encodage ───────────────────────────────────────────────────

    def _read_raw(self, file_path: str, report: ComplianceReport) -> bytes | None:
        """Lit le fichier en mode binaire.

        Args:
            file_path: Chemin vers le fichier.
            report:    Rapport en cours d'alimentation.

        Returns:
            Contenu brut ou ``None`` si lecture impossible.
        """
        try:
            with open(file_path, "rb") as fh:
                return fh.read()
        except OSError as exc:
            report.add(
                CheckResult(
                    severity=SEVERITY_ERROR,
                    category="Lecture",
                    message=f"Impossible de lire le fichier : {exc}",
                )
            )
            return None

    def _check_encoding(self, raw: bytes, report: ComplianceReport) -> str | None:
        """Vérifie et décode le fichier selon l'encodage déclaré dans le flux.

        Args:
            raw:    Octets bruts du fichier.
            report: Rapport en cours d'alimentation.

        Returns:
            Contenu décodé ou ``None`` si décodage impossible.
        """
        declared = (self.fm.current_flow or {}).get("encoding", "UTF-8")
        try:
            content = raw.decode(declared)
            report.summary_lines.append(f"Encodage       : {declared} ✓")
            report.add(
                CheckResult(
                    severity=SEVERITY_INFO,
                    category="Encodage",
                    message=f"Encodage cohérent : {declared} ✓",
                )
            )
            return content
        except (UnicodeDecodeError, LookupError):
            pass

        for enc in ("utf-8-sig", "iso-8859-1", "windows-1252", "utf-16"):
            try:
                content = raw.decode(enc)
                report.summary_lines.append(
                    f"Encodage       : déclaré {declared} ✗ — détecté {enc}"
                )
                report.add(
                    CheckResult(
                        severity=SEVERITY_ERROR,
                        category="Encodage",
                        message=(f"Encodage incohérent : déclaré {declared}, détecté {enc}."),
                        expected=declared,
                        actual=enc,
                    )
                )
                return content
            except (UnicodeDecodeError, LookupError):
                continue

        report.summary_lines.append(f"Encodage       : déclaré {declared} ✗ — indéchiffrable")
        report.add(
            CheckResult(
                severity=SEVERITY_ERROR,
                category="Encodage",
                message="Impossible de décoder le fichier avec les encodages courants.",
                expected=declared,
                actual="inconnu",
            )
        )
        return None

    def _check_line_endings(self, content: str, report: ComplianceReport) -> None:
        """Vérifie les fins de ligne par rapport à la configuration du flux.

        Args:
            content: Contenu textuel du fichier.
            report:  Rapport en cours d'alimentation.
        """
        declared = (self.fm.current_flow or {}).get("lineEnding", "CRLF")
        crlf_count = content.count("\r\n")
        lf_count = content.count("\n") - crlf_count
        cr_count = content.count("\r") - crlf_count

        detected = "LF"
        if crlf_count > 0 and lf_count == 0 and cr_count == 0:
            detected = "CRLF"
        elif cr_count > 0 and lf_count == 0 and crlf_count == 0:
            detected = "CR"
        elif crlf_count > 0 and lf_count > 0:
            detected = "mixte (CRLF + LF)"

        declared_key = declared.split()[0] if declared else "CRLF"
        if detected not in (declared_key, declared):
            report.summary_lines.append(
                f"Fins de ligne  : déclaré {declared} ✗ — détecté {detected}"
            )
            report.add(
                CheckResult(
                    severity=SEVERITY_WARNING,
                    category="Fins de ligne",
                    message=f"Fins de ligne incohérentes : déclaré {declared}, détecté {detected}.",
                    expected=declared,
                    actual=detected,
                )
            )
        else:
            report.summary_lines.append(f"Fins de ligne  : {detected} ✓")
            report.add(
                CheckResult(
                    severity=SEVERITY_INFO,
                    category="Fins de ligne",
                    message=f"Fins de ligne cohérentes : {detected} ✓",
                )
            )

    # ─── Structure JSON / XML ─────────────────────────────────────────────────

    def _check_structure(self, content: str, fmt: str, report: ComplianceReport) -> bool:
        """Vérifie la validité structurelle du fichier selon son format déclaré.

        Pour les formats ``json`` et ``xml``, le contenu est parsé et les
        erreurs de syntaxe sont reportées. Pour les autres formats, aucun
        contrôle structurel global n'est effectué (les contrôles de champ
        gèrent la conformité au niveau ligne).

        Args:
            content: Contenu textuel du fichier déjà décodé.
            fmt:     Format déclaré dans le flux (``'csv'``, ``'json'``…).
            report:  Rapport en cours d'alimentation.

        Returns:
            ``True`` si la structure est valide (ou non vérifiable), ``False``
            en cas d'erreur structurelle bloquante.
        """
        if fmt == "json":
            return self._check_json_structure(content, report)
        if fmt == "xml":
            return self._check_xml_structure(content, report)
        return True

    def _check_json_structure(self, content: str, report: ComplianceReport) -> bool:
        """Valide la syntaxe JSON du fichier.

        Vérifie également que la racine est un tableau (liste d'objets), ce
        qui est la convention attendue pour les flux tabulaires.

        Args:
            content: Contenu textuel du fichier.
            report:  Rapport en cours d'alimentation.

        Returns:
            ``True`` si le JSON est valide, ``False`` sinon.
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            report.summary_lines.append(
                f"Structure JSON : ✗ syntaxe invalide (ligne {exc.lineno}, col {exc.colno})"
            )
            report.add(
                CheckResult(
                    severity=SEVERITY_ERROR,
                    category="Structure JSON",
                    message=f"JSON invalide : {exc.msg} (ligne {exc.lineno}, col. {exc.colno}).",
                    expected="JSON syntaxiquement valide",
                    actual=str(exc),
                )
            )
            return False

        # Type de la racine
        root_type = type(data).__name__
        if isinstance(data, list):
            report.summary_lines.append(f"Structure JSON : ✓ tableau de {len(data)} objet(s)")
            report.add(
                CheckResult(
                    severity=SEVERITY_INFO,
                    category="Structure JSON",
                    message=f"JSON valide : tableau de {len(data)} enregistrement(s) ✓",
                )
            )
            report.total_rows = len(data)
            # Cohérence des clés : tous les objets doivent avoir les mêmes clés
            if data and isinstance(data[0], dict):
                ref_keys = set(data[0].keys())
                bad_rows = [
                    i + 1
                    for i, obj in enumerate(data)
                    if isinstance(obj, dict) and set(obj.keys()) != ref_keys
                ]
                if bad_rows:
                    report.summary_lines.append(
                        f"Clés JSON      : ✗ incohérentes sur {len(bad_rows)} ligne(s)"
                    )
                    report.add(
                        CheckResult(
                            severity=SEVERITY_WARNING,
                            category="Structure JSON",
                            message=(
                                f"Clés incohérentes sur {len(bad_rows)} objet(s) "
                                f"(ex. lignes : {bad_rows[:5]})."
                            ),
                            expected=str(sorted(ref_keys)),
                            actual=f"divergences sur {len(bad_rows)} ligne(s)",
                        )
                    )
                else:
                    nb_keys = len(ref_keys)
                    report.summary_lines.append(
                        f"Clés JSON      : ✓ cohérentes ({nb_keys} clé(s) / objet)"
                    )
        elif isinstance(data, dict):
            report.summary_lines.append("Structure JSON : ✓ objet racine unique")
            report.add(
                CheckResult(
                    severity=SEVERITY_INFO,
                    category="Structure JSON",
                    message="JSON valide : objet racine unique ✓",
                )
            )
        else:
            report.summary_lines.append(f"Structure JSON : ⚠ racine de type {root_type}")
            report.add(
                CheckResult(
                    severity=SEVERITY_WARNING,
                    category="Structure JSON",
                    message=(
                        f"La racine JSON est de type '{root_type}'. "
                        "Un tableau d'objets est attendu pour un flux tabulaire."
                    ),
                    expected="list",
                    actual=root_type,
                )
            )
        return True

    def _check_xml_structure(self, content: str, report: ComplianceReport) -> bool:
        """Valide la syntaxe XML du fichier.

        Args:
            content: Contenu textuel du fichier.
            report:  Rapport en cours d'alimentation.

        Returns:
            ``True`` si le XML est valide, ``False`` sinon.
        """
        try:
            root = ET.fromstring(content)
        except ET.ParseError as exc:
            report.summary_lines.append(f"Structure XML  : ✗ syntaxe invalide ({exc})")
            report.add(
                CheckResult(
                    severity=SEVERITY_ERROR,
                    category="Structure XML",
                    message=f"XML invalide : {exc}.",
                    expected="XML syntaxiquement valide",
                    actual=str(exc),
                )
            )
            return False

        children = list(root)
        report.total_rows = len(children)
        report.summary_lines.append(
            f"Structure XML  : ✓ balise racine <{root.tag}>, {len(children)} enfant(s)"
        )
        report.add(
            CheckResult(
                severity=SEVERITY_INFO,
                category="Structure XML",
                message=(
                    f"XML valide : racine <{root.tag}>, {len(children)} élément(s) enfant(s) ✓"
                ),
            )
        )

        # Cohérence des balises enfants
        if children:
            tags = [c.tag for c in children]
            unique_tags = set(tags)
            if len(unique_tags) > 1:
                report.summary_lines.append(
                    f"Balises XML    : ⚠ {len(unique_tags)} balises différentes détectées"
                )
                report.add(
                    CheckResult(
                        severity=SEVERITY_WARNING,
                        category="Structure XML",
                        message=(
                            f"Les éléments enfants ont {len(unique_tags)} noms de balise différents : "
                            f"{sorted(unique_tags)}. Un flux tabulaire attend des balises homogènes."
                        ),
                        expected="balises homogènes",
                        actual=str(sorted(unique_tags)),
                    )
                )
            else:
                tag = tags[0]
                report.summary_lines.append(f"Balises XML    : ✓ homogènes <{tag}>")
        return True

    # ─── Délimiteur ───────────────────────────────────────────────────────────

    def _check_delimiter(self, lines: list[str], delimiter: str, report: ComplianceReport) -> None:
        """Vérifie la présence et la cohérence du délimiteur sur les premières lignes.

        Args:
            lines:     Lignes brutes du fichier.
            delimiter: Délimiteur déclaré dans le flux.
            report:    Rapport en cours d'alimentation.
        """
        if not lines:
            return

        sample = lines[:20]
        count_per_line = [line.count(delimiter) for line in sample if line.strip()]
        if not count_per_line:
            return

        max_count = max(count_per_line)
        min_count = min(count_per_line)

        if max_count == 0:
            candidates = {";": "point-virgule", ",": "virgule", "|": "pipe", "\t": "tabulation"}
            found = [
                name
                for char, name in candidates.items()
                if char != delimiter and sample[0].count(char) > 0
            ]
            msg = f"Délimiteur '{delimiter}' absent des 20 premières lignes."
            if found:
                msg += f" Séparateurs potentiels : {', '.join(found)}."
            report.summary_lines.append(f"Délimiteur     : '{delimiter}' ✗ absent")
            report.add(
                CheckResult(
                    severity=SEVERITY_ERROR,
                    category="Délimiteur",
                    message=msg,
                    expected=f"'{delimiter}'",
                    actual="absent",
                )
            )
            return

        delim_repr = repr(delimiter)
        if min_count != max_count:
            report.summary_lines.append(
                f"Délimiteur     : {delim_repr} ✗ variable ({min_count}–{max_count} / ligne)"
            )
            report.add(
                CheckResult(
                    severity=SEVERITY_WARNING,
                    category="Délimiteur",
                    message=(
                        f"Occurrences du délimiteur {delim_repr} variables : "
                        f"{min_count}–{max_count} / ligne."
                    ),
                    expected=str(count_per_line[0]),
                    actual=f"variable ({min_count}–{max_count})",
                )
            )
        else:
            report.summary_lines.append(
                f"Délimiteur     : {delim_repr} ✓  ({count_per_line[0]} col. / ligne)"
            )
            report.add(
                CheckResult(
                    severity=SEVERITY_INFO,
                    category="Délimiteur",
                    message=f"Délimiteur {delim_repr} cohérent ({count_per_line[0]} col. / ligne) ✓",
                )
            )

    # ─── En-tête / Pied de page ───────────────────────────────────────────────

    def _check_header_footer(
        self,
        lines: list[str],
        delimiter: str,
        has_header: bool,
        has_footer: bool,
        report: ComplianceReport,
    ) -> None:
        """Vérifie la présence ou l'absence d'en-tête et de pied de page.

        Compare les champs déclarés dans le mapping aux valeurs observées
        sur la première et la dernière ligne.

        Args:
            lines:      Lignes brutes du fichier.
            delimiter:  Délimiteur de colonnes.
            has_header: ``True`` si le flux déclare un en-tête.
            has_footer: ``True`` si le flux déclare un pied de page.
            report:     Rapport en cours d'alimentation.
        """
        if not lines:
            return

        # ── En-tête ────────────────────────────────────────────────────────
        if has_header:
            header_fields = [f for f in self.fm.header_fields if f.get("includeInOutput")]
            first_cols = self._split_row(lines[0], delimiter)
            exp_count = len(header_fields)
            obs_count = len(first_cols)
            if obs_count != exp_count:
                report.summary_lines.append(
                    f"En-tête        : déclaré {exp_count} col. ✗ — observé {obs_count} col."
                )
                report.add(
                    CheckResult(
                        severity=SEVERITY_ERROR,
                        category="En-tête",
                        message=f"En-tête : {obs_count} colonne(s) observée(s), {exp_count} attendue(s).",
                        expected=str(exp_count),
                        actual=str(obs_count),
                        row=1,
                    )
                )
            else:
                report.summary_lines.append(f"En-tête        : présent ({obs_count} col.) ✓")
                report.add(
                    CheckResult(
                        severity=SEVERITY_INFO,
                        category="En-tête",
                        message=f"En-tête présent ({obs_count} colonnes) ✓",
                        row=1,
                    )
                )
        else:
            report.summary_lines.append("En-tête        : non déclaré")
            if lines:
                first = self._split_row(lines[0], delimiter)
                if all(not v.strip().isdigit() for v in first) and len(first) > 1:
                    report.add(
                        CheckResult(
                            severity=SEVERITY_WARNING,
                            category="En-tête",
                            message=(
                                "Première ligne textuelle alors qu'aucun en-tête n'est déclaré."
                            ),
                            row=1,
                        )
                    )

        # ── Pied de page ───────────────────────────────────────────────────
        if has_footer:
            footer_fields = [f for f in self.fm.footer_fields if f.get("includeInOutput")]
            last_cols = self._split_row(lines[-1], delimiter)
            exp_count = len(footer_fields)
            obs_count = len(last_cols)
            if obs_count != exp_count:
                report.summary_lines.append(
                    f"Pied de page   : déclaré {exp_count} col. ✗ — observé {obs_count} col."
                )
                report.add(
                    CheckResult(
                        severity=SEVERITY_ERROR,
                        category="Pied de page",
                        message=f"Pied de page : {obs_count} colonne(s) observée(s), {exp_count} attendue(s).",
                        expected=str(exp_count),
                        actual=str(obs_count),
                        row=len(lines),
                    )
                )
            else:
                report.summary_lines.append(f"Pied de page   : présent ({obs_count} col.) ✓")
                report.add(
                    CheckResult(
                        severity=SEVERITY_INFO,
                        category="Pied de page",
                        message=f"Pied de page présent ({obs_count} colonnes) ✓",
                        row=len(lines),
                    )
                )
        else:
            report.summary_lines.append("Pied de page   : non déclaré")

    # ─── Nombre de champs ─────────────────────────────────────────────────────

    def _check_field_count(
        self,
        parsed: list[str],
        expected_fields: list[dict],
        row_num: int,
        line_name: str,
        report: ComplianceReport,
    ) -> None:
        """Vérifie que le nombre de colonnes correspond au mapping.

        Args:
            parsed:          Valeurs parsées de la ligne.
            expected_fields: Champs attendus (includeInOutput = True).
            row_num:         Numéro de ligne pour le rapport.
            line_name:       Nom de la ligne de données (pour le rapport).
            report:          Rapport en cours d'alimentation.
        """
        exp = len(expected_fields)
        obs = len(parsed)
        if obs != exp:
            report.add(
                CheckResult(
                    severity=SEVERITY_ERROR,
                    category="Nombre de champs",
                    message=(
                        f"Ligne '{line_name}' : {obs} colonne(s) observée(s) "
                        f"pour {exp} attendue(s)."
                    ),
                    row=row_num,
                    col_name=line_name,
                    expected=str(exp),
                    actual=str(obs),
                )
            )

    # ─── Champs obligatoires ──────────────────────────────────────────────────

    def _check_mandatory(
        self,
        value: str,
        field_def: dict,
        row_num: int,
        fname: str,
        report: ComplianceReport,
    ) -> None:
        """Vérifie qu'un champ obligatoire n'est pas vide.

        Un champ est considéré obligatoire s'il est marqué ``includeInOutput``
        et que sa ``defaultValue`` est vide.

        Args:
            value:     Valeur observée.
            field_def: Définition du champ issue du mapping.
            row_num:   Numéro de ligne pour le rapport.
            fname:     Nom du champ.
            report:    Rapport en cours d'alimentation.
        """
        if not field_def.get("includeInOutput", True):
            return
        default = field_def.get("defaultValue", "")
        if value.strip() == "" and default == "":
            report.add(
                CheckResult(
                    severity=SEVERITY_WARNING,
                    category="Champ obligatoire",
                    message=f"Le champ '{fname}' est vide alors qu'il est inclus dans la sortie.",
                    row=row_num,
                    col_name=fname,
                    expected="valeur non vide",
                    actual="(vide)",
                )
            )

    # ─── Longueur ─────────────────────────────────────────────────────────────

    def _check_length(
        self,
        value: str,
        field_def: dict,
        row_num: int,
        fname: str,
        report: ComplianceReport,
    ) -> None:
        """Vérifie que la longueur de la valeur respecte la longueur déclarée.

        Pour les champs à longueur fixe (format ``fixed``), un écart de longueur
        est une **erreur**. Pour les champs CSV, c'est un **avertissement** si
        la valeur dépasse la longueur déclarée.

        Args:
            value:     Valeur observée.
            field_def: Définition du champ issue du mapping.
            row_num:   Numéro de ligne pour le rapport.
            fname:     Nom du champ.
            report:    Rapport en cours d'alimentation.
        """
        declared_len = field_def.get("length", 0)
        if not declared_len or value.strip() == "":
            return

        actual_len = len(value)
        flow_format = (self.fm.current_flow or {}).get("format", "csv")

        if flow_format == "fixed":
            # Longueur fixe : l'écart est toujours une erreur
            if actual_len != declared_len:
                report.add(
                    CheckResult(
                        severity=SEVERITY_ERROR,
                        category="Longueur",
                        message=(
                            f"'{fname}' : longueur {actual_len} ≠ {declared_len} "
                            f"(format longueur fixe)."
                        ),
                        row=row_num,
                        col_name=fname,
                        expected=str(declared_len),
                        actual=str(actual_len),
                    )
                )
        else:
            # CSV / autre : seulement si dépassement
            if actual_len > declared_len:
                report.add(
                    CheckResult(
                        severity=SEVERITY_WARNING,
                        category="Longueur",
                        message=(
                            f"'{fname}' : longueur {actual_len} dépasse "
                            f"la longueur maximale déclarée ({declared_len})."
                        ),
                        row=row_num,
                        col_name=fname,
                        expected=f"≤ {declared_len}",
                        actual=str(actual_len),
                    )
                )

    # ─── Type de base ─────────────────────────────────────────────────────────

    def _check_type(
        self,
        value: str,
        field_def: dict,
        row_num: int,
        fname: str,
        report: ComplianceReport,
    ) -> None:
        """Vérifie la cohérence du type de base (alpha / num / date / bool / decimal).

        Args:
            value:     Valeur observée.
            field_def: Définition du champ issue du mapping.
            row_num:   Numéro de ligne pour le rapport.
            fname:     Nom du champ.
            report:    Rapport en cours d'alimentation.
        """
        stripped = value.strip()
        if not stripped:
            return

        base_type = field_def.get("type", "alpha")

        if base_type == "num":
            if not stripped.isdigit():
                report.add(
                    CheckResult(
                        severity=SEVERITY_ERROR,
                        category="Type",
                        message=f"'{fname}' déclaré numérique mais contient '{stripped}'.",
                        row=row_num,
                        col_name=fname,
                        expected="chiffres uniquement",
                        actual=stripped[:30],
                    )
                )

        elif base_type == "decimal":
            sep = field_def.get("decimalSeparator", ".")
            normalized = stripped.replace(sep, ".", 1)
            try:
                float(normalized)
            except ValueError:
                report.add(
                    CheckResult(
                        severity=SEVERITY_ERROR,
                        category="Type",
                        message=f"'{fname}' déclaré décimal mais '{stripped}' n'est pas un nombre.",
                        row=row_num,
                        col_name=fname,
                        expected=f"nombre décimal (séparateur '{sep}')",
                        actual=stripped[:30],
                    )
                )

        elif base_type == "bool":
            sub = field_def.get("subType", "none")
            expected_vals = BOOL_EXPECTED.get(sub)
            if expected_vals and stripped.upper() not in expected_vals:
                report.add(
                    CheckResult(
                        severity=SEVERITY_ERROR,
                        category="Type",
                        message=(
                            f"'{fname}' déclaré booléen ({sub}) "
                            f"mais '{stripped}' n'est pas dans {expected_vals}."
                        ),
                        row=row_num,
                        col_name=fname,
                        expected=" ou ".join(expected_vals),
                        actual=stripped[:30],
                    )
                )

        elif base_type == "date":
            self._check_date_format(stripped, field_def, row_num, fname, report)

        elif base_type == "alpha":
            # Vérification légère : pas entièrement numérique (hors sous-type num)
            pass  # Contrôles fins gérés dans _check_subtype

    def _check_date_format(
        self,
        value: str,
        field_def: dict,
        row_num: int,
        fname: str,
        report: ComplianceReport,
    ) -> None:
        """Vérifie qu'une valeur de date correspond au format déclaré.

        Args:
            value:     Valeur de date brute.
            field_def: Définition du champ issue du mapping.
            row_num:   Numéro de ligne pour le rapport.
            fname:     Nom du champ.
            report:    Rapport en cours d'alimentation.
        """
        fmt_key = field_def.get("format", "DD/MM/YYYY")
        fmt_str = DATE_FORMATS.get(fmt_key)
        if not fmt_str or fmt_str == "timestamp":
            if fmt_str == "timestamp" and not value.isdigit():
                report.add(
                    CheckResult(
                        severity=SEVERITY_ERROR,
                        category="Format date",
                        message=f"'{fname}' déclaré timestamp mais '{value}' n'est pas numérique.",
                        row=row_num,
                        col_name=fname,
                        expected="timestamp (chiffres)",
                        actual=value[:20],
                    )
                )
            return

        try:
            datetime.strptime(value, fmt_str)
        except ValueError:
            report.add(
                CheckResult(
                    severity=SEVERITY_ERROR,
                    category="Format date",
                    message=(
                        f"'{fname}' : '{value}' ne correspond pas au format déclaré '{fmt_key}'."
                    ),
                    row=row_num,
                    col_name=fname,
                    expected=fmt_key,
                    actual=value[:20],
                )
            )

    # ─── Sous-types ───────────────────────────────────────────────────────────

    def _check_subtype(
        self,
        value: str,
        field_def: dict,
        row_num: int,
        fname: str,
        report: ComplianceReport,
    ) -> None:
        """Vérifie la cohérence du sous-type du champ (email, SIRET, NIR…).

        Args:
            value:     Valeur observée.
            field_def: Définition du champ issue du mapping.
            row_num:   Numéro de ligne pour le rapport.
            fname:     Nom du champ.
            report:    Rapport en cours d'alimentation.
        """
        stripped = value.strip()
        if not stripped:
            return

        sub = field_def.get("subType", "none")

        if sub in _SUBTYPE_CHECKS:
            pattern, expected_desc, error_label, use_upper = _SUBTYPE_CHECKS[sub]
            test_val = stripped.upper() if use_upper else stripped
            if not pattern.match(test_val):
                report.add(
                    CheckResult(
                        severity=SEVERITY_WARNING,
                        category=f"Sous-type ({sub})",
                        message=f"'{fname}' ({sub}) : {error_label} pour '{stripped[:30]}'.",
                        row=row_num,
                        col_name=fname,
                        expected=expected_desc,
                        actual=stripped[:30],
                    )
                )

        # Luhn check SIRET (longueur + chiffres déjà vérifiés par le pattern)
        if sub == "siret" and _RE_SIRET.match(stripped) and not self._luhn_check(stripped):
            report.add(
                CheckResult(
                    severity=SEVERITY_WARNING,
                    category="Sous-type (siret)",
                    message=f"'{fname}' : le SIRET '{stripped}' échoue à la clé de contrôle Luhn.",
                    row=row_num,
                    col_name=fname,
                    expected="clé Luhn valide",
                    actual=stripped,
                )
            )

    # ─── Utilitaires ──────────────────────────────────────────────────────────

    @staticmethod
    def _split_row(line: str, delimiter: str) -> list[str]:
        """Découpe une ligne en colonnes en tenant compte des guillemets CSV.

        Args:
            line:      Ligne brute.
            delimiter: Caractère délimiteur.

        Returns:
            Liste de valeurs (sans guillemets extérieurs).
        """
        try:
            reader = csv.reader(io.StringIO(line), delimiter=delimiter)
            return next(reader, [])
        except Exception:
            return line.split(delimiter)

    @staticmethod
    def _extract_data_lines(
        lines: list[str],
        has_header: bool,
        has_footer: bool,
    ) -> list[str]:
        """Retourne uniquement les lignes de données (sans en-tête ni pied).

        Args:
            lines:      Toutes les lignes brutes du fichier.
            has_header: Si ``True``, la première ligne est l'en-tête.
            has_footer: Si ``True``, la dernière ligne est le pied de page.

        Returns:
            Sous-liste des lignes de données.
        """
        start = 1 if has_header else 0
        end = len(lines) - 1 if has_footer else len(lines)
        return [line for line in lines[start:end] if line.strip()]

    @staticmethod
    def _luhn_check(number: str) -> bool:
        """Algorithme de Luhn pour validation SIRET / numérique.

        Args:
            number: Chaîne de chiffres.

        Returns:
            ``True`` si la clé est valide.
        """
        digits = [int(d) for d in number]
        digits.reverse()
        total = 0
        for i, d in enumerate(digits):
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        return total % 10 == 0
