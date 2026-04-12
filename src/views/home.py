"""
ui/home.py – Vue d'accueil : liste des flux sauvegardés
"""

import logging

import flet as ft

from views.folder_tree import FolderTreeView

logger = logging.getLogger(__name__)

_FORMAT_COLORS: dict[str, str] = {
    "csv": "#2e7d32",
    "fixed": "#e65100",
    "xml": "#6a1b9a",
    "json": "#1565c0",
}
_FOLDER_COLOR = ft.Colors.AMBER_400


class HomeView:
    """Vue d'accueil avec bandeau d'actions dossier contextuel."""

    def __init__(self, app) -> None:
        self.app = app
        self.fm = app.flow_manager
        self._list_col: ft.Column | None = None
        self._folder_bar: ft.Container | None = None
        self._current_filter: str = app.selected_folder_id

    # ─── Construction ──────────────────────────────────────────────────────────

    def build(self) -> ft.Control:
        self._list_col = ft.Column(spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)
        self._folder_bar = ft.Container()  # rempli par _refresh_folder_bar()

        self._refresh_folder_bar()
        self._refresh()

        return ft.Container(
            content=ft.Column(
                [
                    self._build_main_toolbar(),
                    self._folder_bar,
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
                    self._list_col,
                ],
                spacing=0,
                expand=True,
            ),
            padding=ft.Padding.symmetric(horizontal=32, vertical=20),
            expand=True,
        )

    # ─── Barre d'outils principale ─────────────────────────────────────────────

    def _build_main_toolbar(self) -> ft.Row:
        return ft.Row(
            [
                ft.Column(
                    [
                        ft.Text("Mes flux", size=26, weight=ft.FontWeight.W_700),
                    ],
                    spacing=2,
                ),
                ft.Row(
                    [
                        ft.OutlinedButton(
                            "Importer",
                            icon=ft.Icons.UPLOAD_FILE_OUTLINED,
                            on_click=self._import_flow,
                            style=ft.ButtonStyle(
                                side=ft.BorderSide(1, ft.Colors.GREY_600),
                                color=ft.Colors.GREY_300,
                            ),
                        ),
                    ],
                    spacing=10,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    # ─── Bandeau contextuel dossier ────────────────────────────────────────────

    def _refresh_folder_bar(self) -> None:
        """Reconstruit le bandeau d'actions selon le filtre courant."""
        if self._folder_bar is None:
            return

        fid = self._current_filter
        tree: FolderTreeView = self.app._folder_tree

        if fid == FolderTreeView.ALL:
            # Vue globale : juste un bouton « Nouveau dossier »
            content = ft.Row(
                [
                    ft.Icon(ft.Icons.LAYERS_OUTLINED, size=14, color=ft.Colors.GREY_500),
                    ft.Text("Tous les flux", size=13, color=ft.Colors.GREY_400),
                    ft.Container(expand=True),
                    ft.OutlinedButton(
                        "Nouveau dossier",
                        icon=ft.Icons.CREATE_NEW_FOLDER_OUTLINED,
                        on_click=lambda e: tree.ask_create_folder(None),
                        style=ft.ButtonStyle(
                            side=ft.BorderSide(1, ft.Colors.GREY_700),
                            color=ft.Colors.GREY_400,
                        ),
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

        elif fid == FolderTreeView.NONE:
            content = ft.Row(
                [
                    ft.Icon(ft.Icons.INBOX_OUTLINED, size=14, color=ft.Colors.GREY_500),
                    ft.Text("Flux sans dossier", size=13, color=ft.Colors.GREY_400),
                    ft.Container(expand=True),
                    ft.OutlinedButton(
                        "Nouveau dossier",
                        icon=ft.Icons.CREATE_NEW_FOLDER_OUTLINED,
                        on_click=lambda e: tree.ask_create_folder(None),
                        style=ft.ButtonStyle(
                            side=ft.BorderSide(1, ft.Colors.GREY_700),
                            color=ft.Colors.GREY_400,
                        ),
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

        else:
            # Dossier réel sélectionné → actions complètes
            self.fm.get_folder(fid)
            # Chemin de navigation (breadcrumb simplifié)
            breadcrumb = self._build_breadcrumb(fid)

            content = ft.Row(
                [
                    ft.Icon(ft.Icons.FOLDER_OPEN, size=16, color=_FOLDER_COLOR),
                    breadcrumb,
                    ft.Container(expand=True),
                    # ── Actions dossier ──────────────────────────────────────
                    ft.FilledTonalButton(
                        "Sous-dossier",
                        icon=ft.Icons.CREATE_NEW_FOLDER_OUTLINED,
                        on_click=lambda e, _fid=fid: tree.ask_create_folder(_fid),
                        style=ft.ButtonStyle(
                            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.AMBER),
                            color=ft.Colors.AMBER_200,
                        ),
                    ),
                    ft.FilledTonalButton(
                        "Renommer",
                        icon=ft.Icons.DRIVE_FILE_RENAME_OUTLINE,
                        on_click=lambda e, _fid=fid: tree.ask_rename_folder(_fid),
                        style=ft.ButtonStyle(
                            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.WHITE),
                            color=ft.Colors.GREY_300,
                        ),
                    ),
                    ft.FilledTonalButton(
                        "Supprimer",
                        icon=ft.Icons.DELETE_OUTLINE,
                        on_click=lambda e, _fid=fid: tree.confirm_delete_folder(_fid),
                        style=ft.ButtonStyle(
                            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.RED),
                            color=ft.Colors.RED_300,
                        ),
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

        self._folder_bar.content = ft.Container(
            content=content,
            padding=ft.Padding.symmetric(vertical=8),
        )
        try:
            self._folder_bar.update()
        except Exception:
            logger.debug("Widget update skipped", exc_info=True)

    def _build_breadcrumb(self, folder_id: str) -> ft.Row:
        """Construit la navigation miettes de pain jusqu'au dossier courant."""
        crumbs: list[dict] = []
        fid = folder_id
        while fid:
            folder = self.fm.get_folder(fid)
            if not folder:
                break
            crumbs.insert(0, folder)
            fid = folder.get("parentId")

        controls: list[ft.Control] = []
        for i, folder in enumerate(crumbs):
            if i > 0:
                controls.append(ft.Icon(ft.Icons.CHEVRON_RIGHT, size=12, color=ft.Colors.GREY_600))
            is_last = i == len(crumbs) - 1
            controls.append(
                ft.Text(
                    folder["name"],
                    size=13,
                    color=ft.Colors.AMBER_200 if is_last else ft.Colors.GREY_500,
                    weight=ft.FontWeight.W_600 if is_last else ft.FontWeight.NORMAL,
                )
            )
        return ft.Row(controls, spacing=2, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    # ─── Filtrage dossier ──────────────────────────────────────────────────────

    def set_folder_filter(self, folder_id: str) -> None:
        self._current_filter = folder_id
        self._refresh_folder_bar()
        self._refresh()

    def _get_filtered_flows(self) -> list[dict]:
        fid = self._current_filter
        all_flows: list[dict] = list(self.fm.load_all_flows())
        if fid == FolderTreeView.ALL:
            return all_flows
        if fid == FolderTreeView.NONE:
            return [f for f in all_flows if not f.get("folderId")]
        return [f for f in all_flows if f.get("folderId") == fid]

    # ─── Liste des flux ────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        if self._list_col is None:
            return
        self._list_col.controls.clear()

        flows = sorted(
            self._get_filtered_flows(),
            key=lambda f: f.get("updated", f.get("created", "")),
            reverse=True,
        )

        if not flows:
            self._list_col.controls.append(self._build_empty_state())
        else:
            for flow in flows:
                draggable = ft.Draggable(
                    group="flow",
                    data=flow.get("id", ""),
                    content=self._build_flow_card(flow),
                    content_when_dragging=ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.DRAG_INDICATOR, color=ft.Colors.GREY_500),
                                ft.Text(
                                    flow.get("name", "Flux"), size=13, color=ft.Colors.GREY_400
                                ),
                            ],
                            spacing=6,
                        ),
                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.WHITE),
                        border_radius=8,
                        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                        opacity=0.7,
                    ),
                )
                self._list_col.controls.append(draggable)

        try:
            self.app.page.update()
        except Exception:
            logger.debug("Widget update skipped", exc_info=True)

    # ─── Composants ────────────────────────────────────────────────────────────

    def _build_empty_state(self) -> ft.Container:
        fid = self._current_filter
        if fid == FolderTreeView.ALL:
            msg = "Aucun flux créé"
            sub = "Importez un fichier JSON ou créez votre premier flux depuis l'AppBar."
        elif fid == FolderTreeView.NONE:
            msg = "Aucun flux sans dossier"
            sub = "Tous vos flux sont organisés dans des dossiers."
        else:
            folder = self.fm.get_folder(fid)
            name = folder["name"] if folder else "ce dossier"
            msg = f"Dossier « {name} » vide"
            sub = "Créez un flux (bouton AppBar) ou glissez-en un depuis la liste."

        return ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.INBOX_OUTLINED, size=64, color=ft.Colors.GREY_700),
                    ft.Text(msg, size=18, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_500),
                    ft.Text(sub, color=ft.Colors.GREY_600, size=12),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=10,
            ),
            alignment=ft.Alignment.CENTER,
            expand=True,
            padding=ft.Padding.symmetric(vertical=80),
        )

    def _build_flow_card(self, flow: dict) -> ft.Card:
        fmt = flow.get("format", "csv").lower()
        color = _FORMAT_COLORS.get(fmt, "#455a64")
        name = flow.get("name", "Sans nom")
        desc = flow.get("description", "") or "Aucune description"
        date = flow.get("updated", flow.get("created", "—"))

        nb_data = sum(len(line.get("fields", [])) for line in flow.get("fields", []))
        total = len(flow.get("headerFields", [])) + nb_data + len(flow.get("footerFields", []))

        format_badge = ft.Container(
            content=ft.Text(fmt.upper(), color=ft.Colors.WHITE, size=11, weight=ft.FontWeight.BOLD),
            bgcolor=color,
            border_radius=6,
            padding=ft.Padding.symmetric(horizontal=10, vertical=5),
        )

        folder_badge = self._build_folder_badge(flow.get("folderId"))

        stats = ft.Row(
            [
                self._stat_chip(ft.Icons.TITLE, f"{total} champ{'s' if total != 1 else ''}"),
                self._stat_chip(ft.Icons.TABLE_CHART, f"{flow.get('numRows', 10)} lignes"),
                self._stat_chip(ft.Icons.CODE, flow.get("encoding", "UTF-8")),
            ],
            spacing=8,
        )

        # Dropdown « Déplacer vers… »
        folders = self.fm.folders
        options = [ft.dropdown.Option("__none__", "📥 Sans dossier")] + [
            ft.dropdown.Option(f["id"], f"📁 {f['name']}")
            for f in sorted(folders, key=lambda x: x.get("name", "").lower())
        ]

        header_controls: list[ft.Control] = [format_badge]
        if folder_badge:
            header_controls.append(folder_badge)
        header_controls += [
            ft.Container(expand=True),
            ft.Icon(
                ft.Icons.DRAG_INDICATOR,
                size=14,
                color=ft.Colors.GREY_700,
                tooltip="Glisser vers un dossier",
            ),
            ft.Dropdown(
                options=options,
                hint_text="Déplacer…",
                width=160,
                height=36,
                text_size=11,
                content_padding=ft.Padding.symmetric(horizontal=8, vertical=0),
                on_select=lambda e, fid=flow.get("id"): self._move_flow(fid, e.control.value),
            ),
            ft.IconButton(
                icon=ft.Icons.EDIT_OUTLINED,
                tooltip="Éditer",
                icon_color=ft.Colors.BLUE_300,
                on_click=lambda e, f=flow: self.app.show_editor(f),
            ),
            ft.IconButton(
                icon=ft.Icons.DOWNLOAD_OUTLINED,
                tooltip="Exporter JSON",
                icon_color=ft.Colors.GREEN_300,
                on_click=lambda e, f=flow: self._export_flow(f),
            ),
            ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                tooltip="Supprimer",
                icon_color=ft.Colors.RED_400,
                on_click=lambda e, f=flow: self._confirm_delete(f),
            ),
        ]

        return ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Row(header_controls, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Text(name, size=16, weight=ft.FontWeight.W_700),
                        ft.Text(
                            desc,
                            size=12,
                            color=ft.Colors.GREY_400,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Container(height=2),
                        ft.Row(
                            [
                                stats,
                                ft.Container(expand=True),
                                ft.Text(f"Modifié : {date}", size=10, color=ft.Colors.GREY_600),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ],
                    spacing=7,
                ),
                padding=18,
            ),
            elevation=3,
            shadow_color=ft.Colors.BLUE_900,
        )

    def _build_folder_badge(self, folder_id: str | None) -> ft.Container | None:
        """Badge dossier visible uniquement dans la vue « Tous les flux »."""
        if self._current_filter != FolderTreeView.ALL:
            return None
        if not folder_id:
            return None
        folder = self.fm.get_folder(folder_id)
        if not folder:
            return None
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.FOLDER_OUTLINED, size=10, color=_FOLDER_COLOR),
                    ft.Text(folder["name"], size=10, color=ft.Colors.AMBER_300),
                ],
                spacing=3,
            ),
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.AMBER),
            border_radius=5,
            padding=ft.Padding.symmetric(horizontal=6, vertical=3),
        )

    @staticmethod
    def _stat_chip(icon, label: str) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icon, size=12, color=ft.Colors.GREY_500),
                    ft.Text(label, size=11, color=ft.Colors.GREY_400),
                ],
                spacing=4,
            ),
            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.WHITE),
            border_radius=20,
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
        )

    # ─── Actions ───────────────────────────────────────────────────────────────

    def _move_flow(self, flow_id: str, folder_id: str) -> None:
        target = None if folder_id == "__none__" else folder_id
        self.fm.move_flow_to_folder(flow_id, target)
        self._refresh()
        self.app.refresh_folder_tree()
        self.app.show_snack("Flux déplacé ✓")

    def _confirm_delete(self, flow: dict) -> None:
        def do_delete():
            self.fm.delete_flow(flow["id"])
            self._refresh()
            self.app.refresh_folder_tree()
            self.app.show_snack(f"Flux « {flow.get('name')} » supprimé.")

        self.app.confirm(
            title="Supprimer le flux",
            body=(f"Supprimer « {flow.get('name', '')} » ? Cette action est irréversible."),
            on_confirm=do_delete,
        )

    def _export_flow(self, flow: dict) -> None:
        self.fm.load_flow(flow)

        async def _do(_):
            path = await ft.FilePicker().save_file(
                file_name=f"{flow.get('name', 'flux')}.json",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["json"],
            )
            if not path:
                return
            try:
                ok = self.fm.export_flow(path)
                self.app.show_snack(f"Exporté → {path}" if ok else "Échec de l'export", success=ok)
            except Exception as exc:
                logger.error("Erreur export : %s", exc)
                self.app.show_snack("Erreur lors de l'export", success=False)

        self.app.page.run_task(_do, None)

    def _import_flow(self, e) -> None:
        async def _do(_):
            files = await ft.FilePicker().pick_files(
                dialog_title="Importer un flux",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["json"],
                allow_multiple=False,
            )
            if not files:
                return
            path = files[0].path
            try:
                if self.fm.import_flow(path):
                    fid = self._current_filter
                    if fid not in (FolderTreeView.ALL, FolderTreeView.NONE):
                        self.fm.update_flow_field("folderId", fid)
                    self.fm.save_current_flow()
                    self._refresh()
                    self.app.refresh_folder_tree()
                    self.app.show_snack("Flux importé avec succès ✓")
                else:
                    self.app.show_snack("Impossible d'importer ce fichier", success=False)
            except Exception as exc:
                logger.error("Erreur import : %s", exc)
                self.app.show_snack("Erreur lors de l'import", success=False)

        self.app.page.run_task(_do, None)
