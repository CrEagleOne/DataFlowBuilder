"""
ui/editor.py – Vue éditeur de flux
====================================
Quatre onglets :
  1. ⚙️ Configuration  – paramètres généraux du flux
  2. 📋 En-tête        – champs de la ligne d'en-tête
  3. 📊 Données        – structures de lignes de données (multi-lignes)
  4. 📄 Pied de page   – champs du pied de page

Actions de la barre supérieure :
  • ← Retour       → revient à l'accueil
  • Aperçu         → génère + affiche un extrait des données
  • Sauvegarder    → persiste le flux
  • Vérifier       → dialogue de conformité

Nouvelles fonctionnalités :
  • Option JSON « Catégories → clés imbriquées » (``xxx.yyy.zzz`` →
    objet JSON imbriqué) dans l'onglet Configuration.
  • Bouton « Sauvegarder sous… » dans l'aperçu : nomme le fichier et
    le range dans ``generated/{nom_du_flux}/``.
"""

import logging
from datetime import datetime

import flet as ft

from views.compliance_ui import ComplianceDialog

logger = logging.getLogger(__name__)


class EditorView:
    """Vue éditeur principal.

    Attributes:
        app: Instance de :class:`ui.app.DataFlowApp`.
        fm:  Alias sur ``app.flow_manager``.
    """

    def __init__(self, app) -> None:
        self.app = app
        self.fm = app.flow_manager
        self._tabs: ft.Tabs | None = None
        self._save_picker: ft.FilePicker | None = None
        self._preview_data: str = ""

    # ─── Construction principale ───────────────────────────────────────────────

    def build(self) -> ft.Control:
        """Retourne le contrôle racine de l'éditeur."""
        # Crée le picker de sauvegarde et l'injecte dans page.overlay
        self._save_picker = ft.FilePicker()

        return ft.Column(
            [
                self._build_action_bar(),
                ft.Divider(height=1, color=ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
                ft.Tabs(
                    selected_index=0,
                    animation_duration=250,
                    length=4,  # Nombre d'onglets
                    expand=True,
                    content=ft.Column(
                        expand=True,
                        controls=[
                            ft.TabBar(
                                tabs=[
                                    ft.Tab(label="⚙️  Configuration"),
                                    ft.Tab(label="📋  En-tête"),
                                    ft.Tab(label="📊  Données"),
                                    ft.Tab(label="📄 Pied de page"),
                                ],
                                tab_alignment=ft.TabAlignment.START,
                            ),
                            ft.TabBarView(
                                expand=True,
                                controls=[
                                    self._config_tab(),
                                    self._section_tab("header"),
                                    self._data_tab(),
                                    self._section_tab("footer"),
                                ],
                            ),
                        ],
                    ),
                ),
            ],
            spacing=0,
            expand=True,
        )

    # ─── Barre d'actions ──────────────────────────────────────────────────────

    def _build_action_bar(self) -> ft.Container:
        """Barre supérieure : retour, nom du flux, actions.

        Returns:
            ft.Container: Barre d'actions avec boutons Retour, Aperçu,
            Sauvegarder et Vérifier conformité.
        """
        flow_name_ctrl = ft.Text(
            self.fm.current_flow.get("name", "Nouveau flux"),
            size=17,
            weight=ft.FontWeight.W_700,
            expand=True,
        )
        return ft.Container(
            content=ft.Row(
                [
                    ft.TextButton(
                        "← Retour",
                        on_click=lambda e: self.app.show_home(),
                        style=ft.ButtonStyle(color=ft.Colors.GREY_400),
                    ),
                    ft.VerticalDivider(width=1, color=ft.Colors.GREY_800),
                    flow_name_ctrl,
                    ft.Row(
                        [
                            ft.OutlinedButton(
                                "Aperçu",
                                icon=ft.Icons.REMOVE_RED_EYE_OUTLINED,
                                on_click=self._show_preview,
                                style=ft.ButtonStyle(
                                    side=ft.BorderSide(1, ft.Colors.GREY_600),
                                    color=ft.Colors.GREY_300,
                                ),
                            ),
                            ft.ElevatedButton(
                                "Sauvegarder",
                                icon=ft.Icons.SAVE_OUTLINED,
                                on_click=self._save_flow,
                                style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700),
                            ),
                            ft.OutlinedButton(
                                "Vérifier conformité",
                                icon=ft.Icons.FACT_CHECK_OUTLINED,
                                on_click=lambda e: ComplianceDialog(self.app).open(),
                            ),
                        ],
                        spacing=10,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=16,
            ),
            padding=ft.Padding.symmetric(horizontal=24, vertical=10),
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.WHITE),
        )

    # ─── Onglet Configuration ─────────────────────────────────────────────────

    def _config_tab(self) -> ft.Container:
        """Formulaire des paramètres généraux du flux.

        Inclut une option JSON-only pour structurer la sortie selon les
        catégories de champs (``xxx.yyy.zzz`` → clés imbriquées).

        Returns:
            ft.Container: Onglet de configuration scrollable.
        """
        flow = self.fm.current_flow

        def upd(key, value):
            self.fm.update_flow_field(key, value)

        # ── Option « catégories → clés JSON » (visible seulement si format=json) ─
        cat_keys_checkbox = ft.Checkbox(
            label=(
                "Structurer le JSON par catégories de champs\n"
                '  Ex : catégorie « personne.identite » → {"personne": {"identite": {…}}}'
            ),
            value=flow.get("categoriesAsJsonKeys", False),
            on_change=lambda e: upd("categoriesAsJsonKeys", e.control.value),
        )
        cat_keys_container = ft.Container(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(
                                    ft.Icons.ACCOUNT_TREE_OUTLINED,
                                    size=14,
                                    color=ft.Colors.BLUE_300,
                                ),
                                ft.Text(
                                    "Options JSON avancées",
                                    size=12,
                                    weight=ft.FontWeight.W_600,
                                    color=ft.Colors.BLUE_300,
                                ),
                            ],
                            spacing=6,
                        ),
                        cat_keys_checkbox,
                    ],
                    spacing=8,
                ),
                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLUE),
                border_radius=8,
                padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                border=ft.border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.BLUE)),
            ),
            visible=flow.get("format", "csv") == "json",
        )

        def _on_format_change(e):
            """Met à jour le format et affiche/masque l'option JSON.

            Args:
                e: Événement de changement de sélection.
            """
            upd("format", e.control.value)
            cat_keys_container.visible = e.control.value == "json"
            try:
                cat_keys_container.update()
            except Exception:
                logger.debug("cat_keys_container update skipped")

        section = _card_section(
            "Paramètres généraux",
            [
                ft.TextField(
                    label="Nom du flux",
                    value=flow.get("name", ""),
                    on_change=lambda e: upd("name", e.control.value),
                ),
                ft.TextField(
                    label="Description",
                    value=flow.get("description", ""),
                    multiline=True,
                    min_lines=2,
                    max_lines=4,
                    on_change=lambda e: upd("description", e.control.value),
                ),
                ft.Row(
                    [
                        ft.Dropdown(
                            label="Format de sortie",
                            value=flow.get("format", "csv"),
                            options=[
                                ft.dropdown.Option("csv", "CSV"),
                                ft.dropdown.Option("fixed", "Longueur fixe"),
                                ft.dropdown.Option("xml", "XML"),
                                ft.dropdown.Option("json", "JSON"),
                            ],
                            on_select=_on_format_change,
                            expand=True,
                        ),
                        ft.Dropdown(
                            label="Encodage",
                            value=flow.get("encoding", "UTF-8"),
                            options=[
                                ft.dropdown.Option("UTF-8"),
                                ft.dropdown.Option("ISO-8859-1"),
                                ft.dropdown.Option("Windows-1252"),
                            ],
                            on_select=lambda e: upd("encoding", e.control.value),
                            expand=True,
                        ),
                    ],
                    spacing=16,
                ),
                cat_keys_container,
                ft.Row(
                    [
                        ft.TextField(
                            label="Délimiteur",
                            value=flow.get("delimiter", ","),
                            hint_text="Ex : ,  ;  |  \\t",
                            on_change=lambda e: upd("delimiter", e.control.value),
                            expand=True,
                        ),
                        ft.TextField(
                            label="Nombre de lignes de données",
                            value=str(flow.get("numRows", 10)),
                            keyboard_type=ft.KeyboardType.NUMBER,
                            on_change=lambda e: upd(
                                "numRows",
                                int(e.control.value) if e.control.value.isdigit() else 10,
                            ),
                            expand=True,
                        ),
                        ft.Dropdown(
                            label="Fin de ligne",
                            value=flow.get("lineEnding", "CRLF (Windows)"),
                            options=[
                                ft.dropdown.Option("CRLF (Windows)"),
                                ft.dropdown.Option("LF (Unix)"),
                                ft.dropdown.Option("CR (Mac)"),
                            ],
                            on_select=lambda e: upd("lineEnding", e.control.value),
                            expand=True,
                        ),
                    ],
                    spacing=16,
                ),
                ft.Checkbox(
                    label="Ajouter le délimiteur en fin de ligne",
                    value=flow.get("trailingDelimiter", False),
                    on_change=lambda e: upd("trailingDelimiter", e.control.value),
                ),
            ],
        )

        return ft.Container(
            content=ft.Column([section], scroll=ft.ScrollMode.AUTO, expand=True),
            padding=ft.Padding.symmetric(horizontal=32, vertical=24),
            expand=True,
        )

    # ─── Onglet En-tête / Pied de page ────────────────────────────────────────

    def _section_tab(self, section: str) -> ft.Container:
        """Délègue à :class:`ui.components.FieldsSection`.

        Args:
            section: ``'header'`` ou ``'footer'``.

        Returns:
            ft.Container: Conteneur de la section avec arbre de catégories.
        """
        from views.components import FieldsSection

        sec = FieldsSection(self.app, section)
        self.app._current_sections[section] = sec
        return sec.build_container()

    # ─── Onglet Données ───────────────────────────────────────────────────────

    def _data_tab(self) -> ft.Container:
        """Délègue à :class:`ui.components.DataSection`.

        Returns:
            ft.Container: Conteneur de la section données avec arbre de catégories.
        """
        from views.components import DataSection

        sec = DataSection(self.app)
        self.app._current_sections["data"] = sec
        return sec.build_container()

    # ─── Actions ──────────────────────────────────────────────────────────────

    def _save_flow(self, e) -> None:
        """Sauvegarde le flux courant sur disque.

        Args:
            e: Événement de clic (non utilisé).
        """
        ok = self.fm.save_current_flow()
        msg = "✅ Flux sauvegardé." if ok else "❌ Erreur lors de la sauvegarde."
        self.app.show_snack(msg, success=ok)

    def _show_preview(self, e) -> None:
        """Génère un aperçu des données et l'affiche formaté.

        Le contenu affiché (et exportable) est identique au fichier final.
        L'aperçu propose également le bouton « Sauvegarder sous… » pour
        nommer et ranger le fichier généré.

        Args:
            e: Événement de clic (non utilisé).
        """
        try:
            raw_data = self.fm.generate_sample_data()
        except Exception as exc:
            logger.error("Erreur génération aperçu : %s", exc)
            self.app.show_snack(f"Erreur : {exc}", success=False)
            return

        self._preview_data = raw_data

        fmt = self.fm.current_flow.get("format", "csv")
        display_data = self._prepare_export_content(raw_data, fmt) if raw_data else ""
        lines_count = len(display_data.splitlines()) if display_data else 0

        self.app.open_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Aperçu des données générées", weight=ft.FontWeight.BOLD),
                content=ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    _info_badge(fmt.upper(), ft.Colors.BLUE_400),
                                    _info_badge(
                                        self.fm.current_flow.get("encoding", "UTF-8"),
                                        ft.Colors.GREEN_400,
                                    ),
                                    _info_badge(f"{lines_count} lignes", ft.Colors.ORANGE_400),
                                ],
                                spacing=8,
                            ),
                            ft.Divider(),
                            ft.TextField(
                                value=display_data
                                or "(Aucune donnée — vérifiez que des champs sont marqués"
                                " « Inclure dans la sortie »)",
                                multiline=True,
                                read_only=True,
                                min_lines=16,
                                max_lines=24,
                                text_style=ft.TextStyle(font_family="monospace", size=12),
                                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
                                border_color=ft.Colors.with_opacity(0.15, ft.Colors.WHITE),
                            ),
                        ],
                        spacing=10,
                    ),
                    width=400,
                    height=520,
                    padding=8,
                ),
                actions=[
                    ft.TextButton("Fermer", on_click=lambda e: self.app.close_dialog()),
                    ft.OutlinedButton(
                        "Sauvegarder sous…",
                        icon=ft.Icons.SAVE_AS_OUTLINED,
                        on_click=self._save_named_data,
                        style=ft.ButtonStyle(
                            side=ft.BorderSide(1, ft.Colors.BLUE_600),
                            color=ft.Colors.BLUE_300,
                        ),
                    ),
                    ft.ElevatedButton(
                        "Exporter les données",
                        icon=ft.Icons.DOWNLOAD_OUTLINED,
                        on_click=self._export_data,
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
        )

    def _save_named_data(self, e) -> None:
        """Ouvre un sous-dialogue pour nommer et sauvegarder les données générées.

        Le fichier est enregistré dans ``generated/{nom_du_flux}/{nom_choisi}.{ext}``.
        Le dossier est automatiquement créé d'après le nom du flux courant.

        Args:
            e: Événement de clic (non utilisé).
        """
        if not self._preview_data:
            self.app.show_snack("Aucune donnée à sauvegarder.", success=False)
            return

        flow_name = self.fm.current_flow.get("name", "flux")
        fmt = self.fm.current_flow.get("format", "csv")
        ext = self._FORMAT_EXT.get(fmt, "txt")
        default_name = f"{flow_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        generated_folder = self.fm.storage.get_generated_folder(flow_name)

        name_tf = ft.TextField(
            label="Nom du fichier",
            value=default_name,
            autofocus=True,
            suffix=f".{ext}",
            hint_text="Ex : export_prod_2026…",
        )

        def do_save(ev):
            """Exécute la sauvegarde et ferme le sous-dialogue.

            Args:
                ev: Événement de clic (non utilisé).
            """
            file_name = name_tf.value.strip()
            if not file_name:
                self.app.show_snack("Le nom ne peut pas être vide.", success=False)
                return
            enc = self.fm.current_flow.get("encoding", "UTF-8")
            content = self._prepare_export_content(self._preview_data, fmt)
            path = self.fm.storage.save_generated_data(
                flow_name=flow_name,
                file_name=file_name,
                content=content,
                fmt=fmt,
                encoding=enc,
            )
            self.app.close_sub_dialog()
            if path:
                self.app.show_snack(f"✅ Sauvegardé → {path}")
            else:
                self.app.show_snack("❌ Erreur lors de la sauvegarde", success=False)

        sub_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.SAVE_AS_OUTLINED, color=ft.Colors.BLUE_400),
                    ft.Text("Sauvegarder sous…", size=15, weight=ft.FontWeight.BOLD),
                ],
                spacing=10,
            ),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Icon(
                                        ft.Icons.FOLDER_OUTLINED,
                                        size=13,
                                        color=ft.Colors.AMBER_400,
                                    ),
                                    ft.Text(
                                        f"Dossier : {generated_folder}",
                                        size=11,
                                        color=ft.Colors.GREY_400,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                        expand=True,
                                    ),
                                ],
                                spacing=6,
                            ),
                            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
                            border_radius=6,
                            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                        ),
                        ft.Container(height=4),
                        name_tf,
                    ],
                    spacing=8,
                    tight=True,
                ),
                width=440,
                padding=8,
            ),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self.app.close_sub_dialog()),
                ft.ElevatedButton(
                    "Sauvegarder",
                    icon=ft.Icons.SAVE,
                    on_click=do_save,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.app.open_sub_dialog(sub_dlg)

    # ── Table extension par format ─────────────────────────────────────────────
    _FORMAT_EXT: dict[str, str] = {
        "csv": "csv",
        "fixed": "txt",
        "xml": "xml",
        "json": "json",
    }

    async def _export_data(self, e) -> None:
        """Exporte les données générées via le sélecteur de fichier natif.

        Le format du fichier est cohérent avec le Format de sortie configuré.
        Si l'option « catégories → clés JSON » est activée, la sortie JSON
        sera imbriquée selon les catégories des champs.

        Args:
            e: Événement de clic (non utilisé).
        """
        if not self._preview_data:
            return

        assert self._save_picker is not None
        fmt = self.fm.current_flow.get("format", "csv")
        name = self.fm.current_flow.get("name", "export")
        ext = self._FORMAT_EXT.get(fmt, "txt")

        path = await self._save_picker.save_file(
            dialog_title="Exporter les données générées",
            allowed_extensions=[ext],
            file_name=f"{name}.{ext}",
        )

        if not path:
            return

        try:
            enc = self.fm.current_flow.get("encoding", "UTF-8")
            content = self._prepare_export_content(self._preview_data, fmt)
            with open(path, "w", encoding=enc) as fh:
                fh.write(content)
            self.app.close_dialog()
            self.app.show_snack(f"✅ Exporté → {path}")
        except Exception as exc:
            logger.error("Erreur export données : %s", exc)
            self.app.show_snack("❌ Erreur lors de l'export", success=False)

    def _prepare_export_content(self, raw_data: str, fmt: str) -> str:
        """Transforme les données brutes en contenu prêt à écrire selon le format.

        Pour CSV, longueur fixe et XML, le texte est retourné tel quel.
        Pour JSON, un tableau d'objets est reconstruit avec les noms de champs
        comme clés. Si l'option ``categoriesAsJsonKeys`` est activée dans le
        flux, les catégories au format ``xxx.yyy.zzz`` sont dépliées en
        objets imbriqués.

        Args:
            raw_data: Texte CSV produit par :meth:`generate_sample_data`.
            fmt: Format déclaré dans le flux (``'csv'``, ``'json'``…).

        Returns:
            str: Chaîne prête à écrire dans le fichier de sortie.
        """
        if fmt != "json":
            return raw_data

        import csv as _csv
        import io as _io
        import json as _json

        delimiter = self.fm.current_flow.get("delimiter", ",")
        use_cat_keys = self.fm.current_flow.get("categoriesAsJsonKeys", False)

        def _parse_row(line: str) -> list[str]:
            """Parse une ligne CSV en tenant compte du délimiteur configuré.

            Args:
                line: Ligne brute à parser.

            Returns:
                list[str]: Liste des valeurs de la ligne.
            """
            try:
                return next(_csv.reader(_io.StringIO(line), delimiter=delimiter), [])
            except Exception:
                return line.split(delimiter)

        def _make_row_dict(fields: list, csv_row: list) -> dict:
            """Construit un dict (plat ou imbriqué) depuis une ligne CSV.

            Args:
                fields: Champs de la section (inclus dans la sortie uniquement).
                csv_row: Valeurs parsées de la ligne CSV.

            Returns:
                dict: Dict plat ``{nom: valeur}`` ou imbriqué si
                ``categoriesAsJsonKeys`` est activé.
            """
            flat = {
                f.get("name", f"champ_{i}"): (csv_row[i] if i < len(csv_row) else "")
                for i, f in enumerate(fields)
            }
            return _nest_by_category(flat, fields) if use_cat_keys else flat

        lines = [ln for ln in raw_data.splitlines() if ln.strip()]
        idx = 0
        result: list[dict] = []

        # ── En-tête ──────────────────────────────────────────────────────────
        header_fields = [f for f in (self.fm.header_fields or []) if f.get("includeInOutput")]
        if header_fields and idx < len(lines):
            result.append(_make_row_dict(header_fields, _parse_row(lines[idx])))
            idx += 1

        # ── Lignes de données ─────────────────────────────────────────────────
        all_data_fields: list[dict] = []
        for line_def in self.fm.field_lines or []:
            all_data_fields.extend(
                f for f in line_def.get("fields", []) if f.get("includeInOutput")
            )

        num_rows = self.fm.current_flow.get("numRows", 10)
        footer_fields = [f for f in (self.fm.footer_fields or []) if f.get("includeInOutput")]

        available = len(lines) - idx - (1 if footer_fields else 0)
        for _ in range(max(available, num_rows)):
            if idx >= len(lines) - (1 if footer_fields else 0):
                break
            if all_data_fields:
                result.append(_make_row_dict(all_data_fields, _parse_row(lines[idx])))
            idx += 1

        # ── Pied de page ──────────────────────────────────────────────────────
        if footer_fields and idx < len(lines):
            result.append(_make_row_dict(footer_fields, _parse_row(lines[idx])))

        return _json.dumps(result, ensure_ascii=False, indent=2)


# ── Helpers locaux ────────────────────────────────────────────────────────────


def _nest_by_category(flat: dict, fields: list) -> dict:
    """Convertit un dict plat en dict imbriqué selon les catégories de champs.

    Exemple : un champ ``name="prenom"`` avec ``category="personne.identite"``
    sera placé à ``result["personne"]["identite"]["prenom"]``.

    Si deux champs différents partagent exactement la même catégorie et le
    même nom, la dernière valeur l'emporte.

    Args:
        flat: Dict ``{nom_champ: valeur}`` issu du parsing CSV.
        fields: Liste des champs avec leur clé ``category``.

    Returns:
        dict: Dict potentiellement imbriqué.
    """
    result: dict = {}
    for i, field in enumerate(fields):
        name = field.get("name", f"champ_{i}")
        value = flat.get(name, "")
        cat = (field.get("category") or "").strip()

        if cat:
            parts = [p.strip() for p in cat.split(".") if p.strip()]
            node = result
            for part in parts:
                if part not in node or not isinstance(node[part], dict):
                    node[part] = {}
                node = node[part]
            node[name] = value
        else:
            result[name] = value

    return result


def _card_section(title: str, controls: list) -> ft.Card:
    """Carte groupant un titre et une liste de contrôles de formulaire.

    Args:
        title: Titre de la section.
        controls: Liste de contrôles Flet à afficher dans la carte.

    Returns:
        ft.Card: Carte avec titre en bleu et contrôles en colonne.
    """
    return ft.Card(
        content=ft.Container(
            content=ft.Column(
                [
                    ft.Text(title, size=15, weight=ft.FontWeight.W_600, color=ft.Colors.BLUE_200),
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
                    *controls,
                ],
                spacing=16,
            ),
            padding=24,
        ),
        elevation=2,
        shadow_color=ft.Colors.BLUE_900,
    )


def _info_badge(label: str, color: str) -> ft.Container:
    """Petit badge coloré pour l'en-tête de la prévisualisation.

    Args:
        label: Texte à afficher dans le badge.
        color: Couleur de fond du badge.

    Returns:
        ft.Container: Badge arrondi avec texte blanc.
    """
    return ft.Container(
        content=ft.Text(label, size=11, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
        bgcolor=color,
        border_radius=20,
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
    )
