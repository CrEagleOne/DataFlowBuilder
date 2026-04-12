"""
ui/compliance_ui.py – Interface de vérification de conformité
=============================================================
Dialogue permettant de sélectionner un fichier de données et de le
vérifier par rapport au mapping du flux courant.

Fonctionnalités :
  • Sélection du fichier via l'explorateur de fichiers
  • Indicateur de progression pendant l'analyse
  • Affichage des résultats groupés par sévérité avec filtres
  • Export du compte-rendu au format texte (.txt)
  • Badges récapitulatifs (erreurs / avertissements / infos)
"""

from __future__ import annotations

import asyncio
import logging

import flet as ft

from core.compliance_checker import (
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    CheckResult,
    ComplianceChecker,
    ComplianceReport,
)

logger = logging.getLogger(__name__)

# ── Palette ───────────────────────────────────────────────────────────────────
_COLOR = {
    SEVERITY_ERROR: ft.Colors.RED_400,
    SEVERITY_WARNING: ft.Colors.ORANGE_300,
    SEVERITY_INFO: ft.Colors.BLUE_300,
}
_BG_COLOR = {
    SEVERITY_ERROR: ft.Colors.with_opacity(0.08, ft.Colors.RED),
    SEVERITY_WARNING: ft.Colors.with_opacity(0.08, ft.Colors.ORANGE),
    SEVERITY_INFO: ft.Colors.with_opacity(0.05, ft.Colors.BLUE),
}
_ICON = {
    SEVERITY_ERROR: ft.Icons.ERROR_OUTLINE,
    SEVERITY_WARNING: ft.Icons.WARNING_AMBER_OUTLINED,
    SEVERITY_INFO: ft.Icons.INFO_OUTLINED,
}
_LABEL = {
    SEVERITY_ERROR: "Erreur",
    SEVERITY_WARNING: "Avertissement",
    SEVERITY_INFO: "Information",
}


class ComplianceDialog:
    """Dialogue principal de vérification de conformité.

    Ce dialogue s'ouvre par-dessus la vue éditeur et permet de :
    - choisir un fichier de données à analyser,
    - lancer la vérification en arrière-plan,
    - consulter les résultats filtrables,
    - exporter le compte-rendu en texte.

    Args:
        app: Instance de :class:`ui.app.DataFlowApp`.

    Example:
        >>> dialog = ComplianceDialog(app)
        >>> dialog.open()
    """

    def __init__(self, app) -> None:
        self.app = app
        self.fm = app.flow_manager

        self._file_path: str = ""
        self._report: ComplianceReport | None = None
        self._active_filter: str | None = None  # None = tout afficher

        # Contrôles UI principaux (créés dans _build_dialog)
        self._dialog: ft.AlertDialog | None = None
        self._file_label: ft.Text | None = None
        self._progress_ring: ft.ProgressRing | None = None
        self._progress_label: ft.Text | None = None
        self._progress_row: ft.Row | None = None
        self._results_col: ft.Column | None = None
        self._summary_row: ft.Row | None = None
        self._filter_row: ft.Row | None = None
        self._export_btn: ft.Control | None = None
        self._check_btn: ft.ElevatedButton | None = None
        self._status_text: ft.Text | None = None
        self._elapsed_text: ft.Text | None = None

        # Pickers Flet (ajoutés à page.overlay lors de l'ouverture)
        self._open_picker: ft.FilePicker | None = None
        self._save_picker: ft.FilePicker | None = None

    # ═══════════════════════════════════════════════════════════════════════════
    # API publique
    # ═══════════════════════════════════════════════════════════════════════════

    def open(self) -> None:
        """Construit les pickers Flet, affiche le dialogue de conformité.

        Les deux :class:`ft.FilePicker` (ouverture et sauvegarde) sont créés
        ici et injectés dans ``page.overlay`` pour être disponibles.
        """
        self._open_picker = ft.FilePicker()
        self._save_picker = ft.FilePicker()

        self._dialog = self._build_dialog()
        self.app.open_dialog(self._dialog)

    # ═══════════════════════════════════════════════════════════════════════════
    # Construction du dialogue
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_dialog(self) -> ft.AlertDialog:
        """Construit le :class:`ft.AlertDialog` complet.

        Returns:
            Le dialogue Flet prêt à être ouvert.
        """
        flow_name = (self.fm.current_flow or {}).get("name", "—")

        # ── Sélection du fichier ──────────────────────────────────────────────
        self._file_label = ft.Text(
            "Aucun fichier sélectionné",
            color=ft.Colors.GREY_500,
            size=12,
            italic=True,
            expand=True,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        file_row = ft.Row(
            [
                ft.OutlinedButton(
                    "Parcourir…",
                    icon=ft.Icons.FOLDER_OPEN_OUTLINED,
                    on_click=self._pick_file,
                    style=ft.ButtonStyle(
                        side=ft.BorderSide(1, ft.Colors.GREY_600),
                        color=ft.Colors.GREY_300,
                    ),
                ),
                self._file_label,
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # ── Barre de progression ──────────────────────────────────────────────
        self._progress_ring = ft.ProgressRing(
            width=18,
            height=18,
            stroke_width=2,
            color=ft.Colors.BLUE_400,
            visible=False,
        )
        self._progress_label = ft.Text("", size=12, color=ft.Colors.GREY_400)
        self._elapsed_text = ft.Text("", size=11, color=ft.Colors.GREY_600, italic=True)
        self._progress_row = ft.Row(
            [self._progress_ring, self._progress_label],
            spacing=10,
            visible=False,
        )

        # ── Badges récapitulatifs ─────────────────────────────────────────────
        self._summary_row = ft.Row(spacing=10, visible=False)

        # ── Filtres ───────────────────────────────────────────────────────────
        self._filter_row = ft.Row(spacing=8, visible=False)

        # ── Résultats ─────────────────────────────────────────────────────────
        self._results_col = ft.Column(
            spacing=6,
            scroll=ft.ScrollMode.AUTO,
            height=360,
        )
        self._status_text = ft.Text(
            "Sélectionnez un fichier pour lancer l'analyse.",
            color=ft.Colors.GREY_600,
            italic=True,
            size=13,
        )
        self._results_col.controls.append(self._status_text)

        # ── Bouton Exporter ───────────────────────────────────────────────────
        self._export_btn = ft.OutlinedButton(
            "Exporter le rapport",
            icon=ft.Icons.DOWNLOAD_OUTLINED,
            on_click=self._export_report,
            visible=False,
            style=ft.ButtonStyle(
                side=ft.BorderSide(1, ft.Colors.GREY_600),
                color=ft.Colors.GREY_300,
            ),
        )

        # ── Bouton Analyser ───────────────────────────────────────────────────
        self._check_btn = ft.ElevatedButton(
            "Lancer l'analyse",
            icon=ft.Icons.PLAY_CIRCLE_OUTLINED,
            on_click=self._start_check,
            disabled=True,
            style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700),
        )

        return ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.FACT_CHECK_OUTLINED, color=ft.Colors.BLUE_300),
                    ft.Column(
                        [
                            ft.Text(
                                "Vérification de conformité",
                                size=16,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Text(
                                f"Flux : {flow_name}",
                                size=12,
                                color=ft.Colors.GREY_500,
                            ),
                        ],
                        spacing=2,
                    ),
                ],
                spacing=12,
            ),
            content=ft.Container(
                content=ft.Column(
                    [
                        # ── Fichier ────────────────────────────────────────
                        _section_label("Fichier à analyser"),
                        file_row,
                        ft.Divider(
                            height=1,
                            color=ft.Colors.with_opacity(0.08, ft.Colors.WHITE),
                        ),
                        # ── Progression ────────────────────────────────────
                        self._progress_row,
                        # ── Récap + filtres ────────────────────────────────
                        self._summary_row,
                        self._filter_row,
                        # ── Résultats ──────────────────────────────────────
                        _section_label("Résultats"),
                        ft.Container(
                            content=self._results_col,
                            border=ft.border.all(
                                1,
                                ft.Colors.with_opacity(0.1, ft.Colors.WHITE),
                            ),
                            border_radius=8,
                            padding=8,
                            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.WHITE),
                        ),
                    ],
                    spacing=10,
                ),
                width=780,
                padding=ft.padding.only(bottom=4),
            ),
            actions=[
                c
                for c in [
                    self._export_btn,
                    ft.TextButton("Fermer", on_click=lambda e: self.app.close_dialog()),
                    self._check_btn,
                ]
                if c is not None
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # Actions
    # ═══════════════════════════════════════════════════════════════════════════

    # ── Table de correspondance format → extensions ───────────────────────────
    _FORMAT_ALLOWED: dict[str, list[str]] = {
        "csv": ["csv", "txt"],
        "fixed": ["txt", "dat"],
        "xml": ["xml"],
        "json": ["json"],
    }

    async def _pick_file(self, e) -> None:
        """Ouvre le sélecteur de fichiers natif Flet pour choisir le fichier à analyser.

        Les extensions proposées par défaut correspondent au format déclaré
        dans le flux courant. La fenêtre est native au système (topmost garanti
        par Flet) — aucune dépendance tkinter.

        Args:
            e: Événement Flet (non utilisé).
        """
        assert self._open_picker is not None
        assert self._file_label is not None
        assert self._check_btn is not None
        assert self._status_text is not None
        flow_fmt = (self.fm.current_flow or {}).get("format", "csv")
        allowed = self._FORMAT_ALLOWED.get(flow_fmt, ["txt"])
        path = await self._open_picker.pick_files(
            dialog_title="Sélectionner le fichier à analyser",
            allowed_extensions=allowed,
            allow_multiple=False,
        )
        if path[0]:
            self._file_path = path[0].path or ""
            self._file_label.value = path[0].path or ""
            self._file_label.color = ft.Colors.GREY_200
            self._file_label.italic = False
            self._check_btn.disabled = False
            self._report = None
            self._clear_results()
            self._status_text.value = "Prêt. Cliquez sur « Lancer l'analyse »."
            self._status_text.color = ft.Colors.GREY_400
            self._update_dialog()

    async def _start_check(self, e) -> None:
        """Lance l'analyse de conformité de manière asynchrone.

        Le travail bloquant (I/O + calcul) est délégué à un thread via
        ``asyncio.to_thread`` afin de ne pas bloquer la boucle événementielle
        Flet. Les mises à jour UI depuis ce thread sont schedulées via
        ``run_coroutine_threadsafe`` pour garantir le repaint immédiat.

        Args:
            e: Événement Flet (non utilisé).
        """
        if not self._file_path:
            return

        assert self._check_btn is not None
        assert self._export_btn is not None
        assert self._summary_row is not None
        assert self._filter_row is not None
        assert self._progress_row is not None
        assert self._progress_ring is not None
        assert self._status_text is not None
        self._check_btn.disabled = True
        self._export_btn.visible = False
        self._summary_row.visible = False
        self._filter_row.visible = False
        self._progress_row.visible = True
        self._progress_ring.visible = True
        self._clear_results()
        self._status_text.value = "Analyse en cours…"
        self._status_text.color = ft.Colors.GREY_400
        self._update_dialog()

        loop = asyncio.get_event_loop()

        def _progress_cb(message: str) -> None:
            """Callback appelé depuis le thread — schedule la MAJ sur la boucle."""

            async def _ui():
                if self._progress_label:
                    self._progress_label.value = message
                self._update_dialog()

            asyncio.run_coroutine_threadsafe(_ui(), loop)

        def _run_sync() -> ComplianceReport:
            checker = ComplianceChecker(self.fm, progress_cb=_progress_cb)
            return checker.check_file(self._file_path)

        try:
            report = await asyncio.to_thread(_run_sync)
            self._report = report
            self._display_results(report)
        except Exception as exc:
            logger.error("Erreur lors de l'analyse : %s", exc)
            self._on_check_error(str(exc))

    def _on_check_error(self, error: str) -> None:
        """Gère une erreur fatale pendant l'analyse.

        Args:
            error: Message d'erreur.
        """
        assert self._progress_row is not None
        assert self._check_btn is not None
        assert self._status_text is not None
        self._progress_row.visible = False
        self._check_btn.disabled = False
        self._status_text.value = f"❌ Erreur : {error}"
        self._status_text.color = ft.Colors.RED_400
        self._update_dialog()

    # ═══════════════════════════════════════════════════════════════════════════
    # Affichage des résultats
    # ═══════════════════════════════════════════════════════════════════════════

    def _display_results(self, report: ComplianceReport) -> None:
        """Construit et affiche les résultats dans l'UI.

        Args:
            report: Rapport de conformité à afficher.
        """
        assert self._progress_row is not None
        assert self._check_btn is not None
        assert self._export_btn is not None
        assert self._summary_row is not None
        assert self._filter_row is not None
        # ── Masquer la progression ─────────────────────────────────────────
        self._progress_row.visible = False
        self._check_btn.disabled = False
        self._export_btn.visible = True

        # ── Badges récapitulatifs ──────────────────────────────────────────
        self._summary_row.controls.clear()
        conformity_color = ft.Colors.GREEN_400 if report.is_compliant else ft.Colors.RED_400
        self._summary_row.controls.append(
            _badge(
                "✅ Conforme" if report.is_compliant else "❌ Non conforme",
                conformity_color,
                bold=True,
            )
        )
        self._summary_row.controls.append(
            _badge(f"🔴 {report.error_count} erreur(s)", ft.Colors.RED_700)
        )
        self._summary_row.controls.append(
            _badge(f"🟠 {report.warning_count} avert.", ft.Colors.ORANGE_700)
        )
        self._summary_row.controls.append(
            _badge(f"🔵 {report.info_count} info(s)", ft.Colors.BLUE_700)
        )
        self._summary_row.controls.append(
            _badge(f"📄 {report.total_rows} ligne(s)", ft.Colors.GREY_700)
        )
        self._summary_row.controls.append(
            _badge(f"⏱ {report.elapsed_seconds:.2f} s", ft.Colors.TEAL_700)
        )
        self._summary_row.visible = True

        # ── Filtres ────────────────────────────────────────────────────────
        self._filter_row.controls.clear()
        self._filter_row.controls.append(ft.Text("Filtrer :", size=12, color=ft.Colors.GREY_500))
        for sev, label, color in [
            (None, "Tout", ft.Colors.GREY_600),
            (SEVERITY_ERROR, "Erreurs", ft.Colors.RED_700),
            (SEVERITY_WARNING, "Avert.", ft.Colors.ORANGE_700),
            (SEVERITY_INFO, "Infos", ft.Colors.BLUE_700),
        ]:
            self._filter_row.controls.append(
                ft.TextButton(
                    label,
                    on_click=lambda e, s=sev: self._apply_filter(s),
                    style=ft.ButtonStyle(
                        bgcolor=color if self._active_filter == sev else None,
                        color=ft.Colors.WHITE,
                    ),
                )
            )
        self._filter_row.visible = True

        # ── Résultats ──────────────────────────────────────────────────────
        self._active_filter = None
        self._render_results(report.results)
        self._update_dialog()

    def _apply_filter(self, severity: str | None) -> None:
        """Filtre les résultats affichés par sévérité.

        Args:
            severity: Sévérité à filtrer, ou ``None`` pour tout afficher.
        """
        self._active_filter = severity
        if self._report:
            filtered = (
                self._report.results
                if severity is None
                else [r for r in self._report.results if r.severity == severity]
            )
            self._render_results(filtered)
            # Mettre à jour le style des boutons de filtre
            assert self._filter_row is not None
            for btn in self._filter_row.controls[1:]:
                if isinstance(btn, ft.TextButton):
                    btn_sev = {
                        "Tout": None,
                        "Erreurs": SEVERITY_ERROR,
                        "Avert.": SEVERITY_WARNING,
                        "Infos": SEVERITY_INFO,
                    }.get(btn.content if isinstance(btn.content, str) else "")
                    is_active = btn_sev == severity
                    colors = {
                        None: ft.Colors.GREY_600,
                        SEVERITY_ERROR: ft.Colors.RED_700,
                        SEVERITY_WARNING: ft.Colors.ORANGE_700,
                        SEVERITY_INFO: ft.Colors.BLUE_700,
                    }
                    btn.style = ft.ButtonStyle(
                        bgcolor=colors.get(btn_sev) if is_active else None,
                        color=ft.Colors.WHITE,
                    )
            self._update_dialog()

    def _render_results(self, results: list[CheckResult]) -> None:
        """Remplit la colonne des résultats avec des sections repliables par sévérité.

        Chaque groupe (Erreurs / Avertissements / Informations) est affiché
        dans un :class:`ft.ExpansionTile` que l'utilisateur peut déplier ou
        replier. Les groupes vides sont omis.

        Args:
            results: Liste de :class:`~compliance_checker.CheckResult` à afficher.
        """
        assert self._results_col is not None
        self._results_col.controls.clear()

        if not results:
            self._results_col.controls.append(
                ft.Text(
                    "✅ Aucun écart détecté pour ce filtre.",
                    color=ft.Colors.GREEN_400,
                    size=13,
                    italic=True,
                )
            )
            return

        order = [SEVERITY_ERROR, SEVERITY_WARNING, SEVERITY_INFO]
        groups: dict[str, list[CheckResult]] = {s: [] for s in order}
        for r in results:
            if r.severity in groups:
                groups[r.severity].append(r)

        _labels = {
            SEVERITY_ERROR: "Erreurs",
            SEVERITY_WARNING: "Avertissements",
            SEVERITY_INFO: "Informations",
        }
        _icons = {
            SEVERITY_ERROR: ft.Icons.ERROR_OUTLINE,
            SEVERITY_WARNING: ft.Icons.WARNING_AMBER_OUTLINED,
            SEVERITY_INFO: ft.Icons.INFO_OUTLINED,
        }

        for sev in order:
            group = groups[sev]
            if not group:
                continue

            color = _COLOR[sev]

            # Tuiles enfants
            tiles: list[ft.Control] = [
                ft.ListTile(
                    leading=ft.Container(width=3, height=40, bgcolor=color, border_radius=2),
                    title=ft.Text(r.message, size=12, color=ft.Colors.GREY_200),
                    subtitle=self._build_subtitle(r),
                    content_padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                )
                for r in group
            ]

            self._results_col.controls.append(
                ft.ExpansionTile(
                    leading=ft.Icon(_icons[sev], size=16, color=color),
                    title=ft.Text(
                        f"{_labels[sev]} ({len(group)})",
                        size=13,
                        weight=ft.FontWeight.W_600,
                        color=color,
                    ),
                    tile_padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                    controls=tiles,
                    bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.WHITE),
                    collapsed_bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.WHITE),
                )
            )

    def _build_subtitle(self, res: CheckResult) -> ft.Control | None:
        """Construit le sous-titre d'une tuile de résultat.

        Regroupe la localisation (ligne / champ), la catégorie et les
        valeurs attendue / observée sur une ou deux lignes compactes.

        Args:
            res: Le :class:`~compliance_checker.CheckResult` à décrire.

        Returns:
            Un :class:`ft.Control` ou ``None`` si aucune information utile.
        """
        parts: list[ft.Control] = []

        # Localisation + catégorie
        loc_parts = []
        if res.row:
            loc_parts.append(f"Ligne {res.row}")
        if res.col_name:
            loc_parts.append(res.col_name)
        loc_str = " · ".join(loc_parts)

        tag = ft.Container(
            content=ft.Text(
                res.category,
                size=10,
                color=_COLOR[res.severity],
                weight=ft.FontWeight.BOLD,
            ),
            bgcolor=ft.Colors.with_opacity(0.15, _COLOR[res.severity]),
            border_radius=4,
            padding=ft.Padding.symmetric(horizontal=5, vertical=1),
        )
        row1_controls: list[ft.Control] = [tag]
        if loc_str:
            row1_controls.append(ft.Text(loc_str, size=10, color=ft.Colors.GREY_500, italic=True))
        parts.append(ft.Row(row1_controls, spacing=6))

        # Attendu → Observé
        if res.expected and res.actual and res.expected != res.actual:
            parts.append(
                ft.Row(
                    [
                        ft.Text(res.expected, size=10, color=ft.Colors.GREY_500),
                        ft.Text("→", size=10, color=ft.Colors.GREY_700),
                        ft.Text(res.actual, size=10, color=ft.Colors.ORANGE_300),
                    ],
                    spacing=4,
                )
            )

        return ft.Column(parts, spacing=2, tight=True) if parts else None

    # ═══════════════════════════════════════════════════════════════════════════
    # Export
    # ═══════════════════════════════════════════════════════════════════════════

    async def _export_report(self, e) -> None:
        """Ouvre le sélecteur de sauvegarde Flet pour exporter le compte-rendu.

        Args:
            e: Événement Flet (non utilisé).
        """
        if not self._report:
            return
        assert self._save_picker is not None
        flow_name = (self.fm.current_flow or {}).get("name", "flux")
        safe_name = "".join(c for c in flow_name if c.isalnum() or c in "-_ ")
        path = await self._save_picker.save_file(
            dialog_title="Exporter le rapport de conformité",
            allowed_extensions=["txt"],
            file_name=f"conformite_{safe_name}.txt",
        )

        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self._report.to_text())
            self.app.show_snack(f"✅ Rapport exporté → {path}")
        except Exception as exc:
            logger.error("Erreur export rapport : %s", exc)
            self.app.show_snack("❌ Erreur lors de l'export du rapport.", success=False)

    # ═══════════════════════════════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════════════════════════════

    def _clear_results(self) -> None:
        """Vide la colonne des résultats et réinitialise les contrôles annexes."""
        if self._results_col:
            self._results_col.controls.clear()
            if self._status_text:
                self._results_col.controls.append(self._status_text)
        if self._summary_row:
            self._summary_row.controls.clear()
            self._summary_row.visible = False
        if self._filter_row:
            self._filter_row.controls.clear()
            self._filter_row.visible = False

    def _update_dialog(self) -> None:
        """Met à jour le dialogue Flet en gérant les exceptions de cycle de vie."""
        try:
            self.app.page.update()
        except Exception:
            logger.debug("Mise à jour UI ignorée.", exc_info=True)


# ── Helpers locaux ────────────────────────────────────────────────────────────


def _section_label(text: str) -> ft.Text:
    """Crée un libellé de section stylisé.

    Args:
        text: Texte du libellé.

    Returns:
        Un :class:`ft.Text` formaté.
    """
    return ft.Text(text, size=12, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_500)


def _badge(label: str, color: str, bold: bool = False) -> ft.Container:
    """Crée un badge coloré pour le récapitulatif.

    Args:
        label: Texte du badge.
        color: Couleur de fond.
        bold:  Si ``True``, le texte est en gras.

    Returns:
        Un :class:`ft.Container` formaté en badge.
    """
    return ft.Container(
        content=ft.Text(
            label,
            size=11,
            color=ft.Colors.WHITE,
            weight=ft.FontWeight.BOLD if bold else ft.FontWeight.NORMAL,
        ),
        bgcolor=color,
        border_radius=20,
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
    )
