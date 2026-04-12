"""
ui/folder_tree.py – Arborescence de dossiers dans la sidebar
=============================================================
Sidebar épurée : chevron + icône + nom + badge uniquement.
Les actions (créer, renommer, supprimer) sont déléguées à HomeView.
"""

import logging

import flet as ft

logger = logging.getLogger(__name__)

_ACTIVE_BG = ft.Colors.with_opacity(0.14, ft.Colors.BLUE)
_DROP_BG = ft.Colors.with_opacity(0.20, ft.Colors.GREEN)
_FOLDER_COLOR = ft.Colors.AMBER_400
_ICON_SIZE = 14


class FolderTreeView:
    """Arborescence latérale légère — aucun bouton sur les lignes."""

    ALL = "__all__"
    NONE = "__none__"

    def __init__(self, app, on_select=None) -> None:
        self.app = app
        self.fm = app.flow_manager
        self.on_select = on_select

        self._selected_id: str = self.ALL
        self._expanded: set[str] = set()
        self._col: ft.Column | None = None

    # ─── API publique ──────────────────────────────────────────────────────────

    @property
    def selected_id(self) -> str:
        return self._selected_id

    def build(self) -> ft.Control:
        self._col = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)
        self._refresh()
        return ft.Container(content=self._col, expand=True)

    def refresh(self) -> None:
        self._refresh()

    def select(self, folder_id: str) -> None:
        self._selected_id = folder_id
        self._refresh()
        if self.on_select:
            self.on_select(folder_id)

    def expand_folder(self, folder_id: str) -> None:
        self._expanded.add(folder_id)
        self._refresh()

    # ─── Actions dossier (appelées depuis HomeView) ────────────────────────────

    def ask_create_folder(self, parent_id: str | None = None) -> None:
        """Dialogue de création d'un dossier (racine ou sous-dossier)."""
        tf = ft.TextField(label="Nom du dossier", autofocus=True, hint_text="Mon dossier…")
        parent = self.fm.get_folder(parent_id) if parent_id else None
        ctx = f" dans « {parent['name']} »" if parent else " à la racine"

        def _create(e):
            name = tf.value.strip()
            if not name:
                self.app.show_snack("Le nom ne peut pas être vide.", success=False)
                return
            folder = self.fm.create_folder(name, parent_id)
            if parent_id:
                self._expanded.add(parent_id)
            self.app.close_dialog()
            self.refresh()
            self.app.refresh_home_view()
            self.app.show_snack(f"Dossier « {folder['name']} » créé ✓")

        self.app.open_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Row(
                    [
                        ft.Icon(ft.Icons.CREATE_NEW_FOLDER_OUTLINED, color=_FOLDER_COLOR),
                        ft.Text(f"Nouveau dossier{ctx}", size=15, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=10,
                ),
                content=ft.Container(content=tf, width=360, padding=4),
                actions=[
                    ft.TextButton("Annuler", on_click=lambda e: self.app.close_dialog()),
                    ft.ElevatedButton(
                        "Créer",
                        icon=ft.Icons.ADD,
                        on_click=_create,
                        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_800),
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
        )

    def ask_rename_folder(self, folder_id: str) -> None:
        """Dialogue de renommage d'un dossier."""
        folder = self.fm.get_folder(folder_id)
        if not folder:
            return
        tf = ft.TextField(label="Nouveau nom", autofocus=True, value=folder.get("name", ""))

        def _rename(e):
            name = tf.value.strip()
            if not name:
                self.app.show_snack("Le nom ne peut pas être vide.", success=False)
                return
            self.fm.rename_folder(folder_id, name)
            self.app.close_dialog()
            self.refresh()
            self.app.refresh_home_view()
            self.app.show_snack(f"Dossier renommé en « {name} » ✓")

        self.app.open_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Row(
                    [
                        ft.Icon(ft.Icons.DRIVE_FILE_RENAME_OUTLINE, color=_FOLDER_COLOR),
                        ft.Text("Renommer le dossier", size=15, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=10,
                ),
                content=ft.Container(content=tf, width=360, padding=4),
                actions=[
                    ft.TextButton("Annuler", on_click=lambda e: self.app.close_dialog()),
                    ft.ElevatedButton(
                        "Renommer",
                        icon=ft.Icons.CHECK,
                        on_click=_rename,
                        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_800),
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
        )

    def confirm_delete_folder(self, folder_id: str) -> None:
        """Dialogue de confirmation avant suppression."""
        folder = self.fm.get_folder(folder_id)
        if not folder:
            return
        subtree_ids = self.fm._collect_subtree_ids(folder_id)
        all_flows = self.fm.load_all_flows()
        n_flows = len([f for f in all_flows if f.get("folderId") in subtree_ids])
        n_sub = len(subtree_ids) - 1

        lines = [f"Supprimer le dossier « {folder['name']} » ?"]
        if n_sub:
            lines.append(f"  • {n_sub} sous-dossier(s) supprimé(s)")
        if n_flows:
            lines.append(f"  • {n_flows} flux déplacé(s) vers « Sans dossier »")
        lines.append("Cette action est irréversible.")

        def _do():
            if self._selected_id in subtree_ids:
                self._selected_id = self.ALL
            self._expanded.difference_update(subtree_ids)
            self.fm.delete_folder(folder_id, move_flows_to=None)
            self.refresh()
            self.app.refresh_home_view()
            self.app.show_snack(f"Dossier « {folder['name']} » supprimé.")

        self.app.confirm(
            title="Supprimer le dossier",
            body="\n".join(lines),
            on_confirm=_do,
        )

    # ─── Construction interne ──────────────────────────────────────────────────

    def _refresh(self) -> None:
        if self._col is None:
            return
        self._col.controls.clear()

        # Entrée « Tous les flux »
        all_count = len(self.fm.load_all_flows())
        self._col.controls.append(
            self._build_virtual_entry(
                ft.Icons.LAYERS_OUTLINED,
                "Tous les flux",
                self.ALL,
                all_count,
            )
        )

        # Entrée « Sans dossier »
        none_count = len([f for f in self.fm.load_all_flows() if not f.get("folderId")])
        self._col.controls.append(
            self._virtual_drag_target(
                self._build_virtual_entry(
                    ft.Icons.INBOX_OUTLINED,
                    "Sans dossier",
                    self.NONE,
                    none_count,
                ),
                target_folder_id=None,
            )
        )

        # Séparateur léger
        self._col.controls.append(
            ft.Container(
                height=1,
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.WHITE),
                margin=ft.margin.symmetric(vertical=4, horizontal=8),
            )
        )

        # Dossiers racine
        for folder in sorted(
            self.fm.get_children_folders(None), key=lambda f: f.get("name", "").lower()
        ):
            self._col.controls.extend(self._build_folder_rows(folder, depth=0))

        try:
            self.app.page.update()
        except Exception:
            logger.debug("Widget update skipped", exc_info=True)

    def _build_folder_rows(self, folder: dict, depth: int) -> list:
        rows = []
        fid = folder["id"]
        is_open = fid in self._expanded
        children = sorted(
            self.fm.get_children_folders(fid), key=lambda f: f.get("name", "").lower()
        )

        rows.append(self._build_folder_row(folder, depth, is_open, bool(children)))

        if is_open:
            for child in children:
                rows.extend(self._build_folder_rows(child, depth + 1))
        return rows

    def _build_folder_row(
        self, folder: dict, depth: int, is_open: bool, has_children: bool
    ) -> ft.Control:
        fid = folder["id"]
        is_selected = self._selected_id == fid
        indent = depth * 12
        flow_count = len(self.fm.get_flows_in_folder(fid))

        # Chevron (tap uniquement sur l'icône, pas sur toute la ligne)
        if has_children:
            chevron: ft.Control = ft.GestureDetector(
                content=ft.Icon(
                    ft.Icons.EXPAND_MORE if is_open else ft.Icons.CHEVRON_RIGHT,
                    size=14,
                    color=ft.Colors.GREY_500,
                ),
                on_tap=lambda e, _id=fid: self._toggle(_id),
            )
        else:
            chevron = ft.Container(width=14)

        name_ctrl = ft.Text(
            folder.get("name", ""),
            size=12,
            expand=True,
            overflow=ft.TextOverflow.ELLIPSIS,
            no_wrap=True,
            color=ft.Colors.WHITE if is_selected else ft.Colors.GREY_300,
            weight=ft.FontWeight.W_600 if is_selected else ft.FontWeight.NORMAL,
        )

        badge = ft.Container(
            content=ft.Text(str(flow_count), size=9, color=ft.Colors.GREY_500),
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.WHITE),
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=4, vertical=1),
            visible=flow_count > 0,
        )

        inner_row = ft.Row(
            [
                ft.Container(width=indent),
                chevron,
                ft.Container(width=3),
                ft.Icon(
                    ft.Icons.FOLDER_OPEN if is_open else ft.Icons.FOLDER_OUTLINED,
                    size=_ICON_SIZE,
                    color=_FOLDER_COLOR,
                ),
                ft.Container(width=5),
                name_ctrl,
                badge,
            ],
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        row_container = ft.Container(
            content=inner_row,
            bgcolor=_ACTIVE_BG if is_selected else ft.Colors.TRANSPARENT,
            border_radius=4,
            padding=ft.Padding.symmetric(horizontal=8, vertical=5),
            ink=True,
            on_click=lambda e, _id=fid: self._select(_id),
        )

        # ── Drop handlers ─────────────────────────────────────────────────────
        def _on_flow_drop(e, _fid=fid):
            draggable = e.control.page.get_control(e.src_id)
            flow_id = draggable.data if draggable else None
            if not flow_id:
                return
            self.fm.move_flow_to_folder(flow_id, _fid)
            self.refresh()
            self.app.refresh_home_view()
            self.app.show_snack("Flux déplacé ✓")

        def _on_folder_drop(e, _fid=fid):
            draggable = e.control.page.get_control(e.src_id)
            dragged_id = draggable.data if draggable else None
            if not dragged_id or dragged_id == _fid:
                return
            if self.fm.move_folder(dragged_id, _fid):
                self._expanded.add(_fid)
                self.refresh()
                self.app.show_snack("Dossier déplacé ✓")

        def _on_will_accept(e):
            e.control.content.bgcolor = _DROP_BG
            try:
                e.control.content.update()
            except Exception:
                logger.debug("Widget update skipped", exc_info=True)

        def _on_leave(e):
            e.control.content.bgcolor = (
                _ACTIVE_BG if self._selected_id == fid else ft.Colors.TRANSPARENT
            )
            try:
                e.control.content.update()
            except Exception:
                logger.debug("Widget update skipped", exc_info=True)

        flow_target = ft.DragTarget(
            group="flow",
            content=row_container,
            on_accept=_on_flow_drop,
            on_will_accept=_on_will_accept,
            on_leave=_on_leave,
        )
        folder_target = ft.DragTarget(
            group="folder",
            content=flow_target,
            on_accept=_on_folder_drop,
        )
        return ft.Draggable(
            group="folder",
            data=fid,
            content=folder_target,
            content_when_dragging=ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.FOLDER, size=12, color=_FOLDER_COLOR),
                        ft.Text(
                            folder.get("name", ""),
                            size=11,
                            color=ft.Colors.GREY_400,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                    spacing=4,
                    tight=True,
                ),
                bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.WHITE),
                border_radius=4,
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                opacity=0.7,
                width=140,
            ),
        )

    def _build_virtual_entry(self, icon, label: str, entry_id: str, count: int) -> ft.Container:
        is_selected = self._selected_id == entry_id
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(
                        icon,
                        size=_ICON_SIZE,
                        color=ft.Colors.BLUE_300 if is_selected else ft.Colors.GREY_500,
                    ),
                    ft.Container(width=6),
                    ft.Text(
                        label,
                        size=12,
                        expand=True,
                        color=ft.Colors.WHITE if is_selected else ft.Colors.GREY_300,
                        weight=ft.FontWeight.W_600 if is_selected else ft.FontWeight.NORMAL,
                    ),
                    ft.Container(
                        content=ft.Text(str(count), size=9, color=ft.Colors.GREY_500),
                        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.WHITE),
                        border_radius=8,
                        padding=ft.Padding.symmetric(horizontal=4, vertical=1),
                        visible=count > 0,
                    ),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=_ACTIVE_BG if is_selected else ft.Colors.TRANSPARENT,
            border_radius=4,
            padding=ft.Padding.symmetric(horizontal=8, vertical=5),
            ink=True,
            on_click=lambda e, _id=entry_id: self._select(_id),
        )

    def _virtual_drag_target(self, content: ft.Control, target_folder_id) -> ft.DragTarget:
        def _on_accept(e):
            draggable = e.control.page.get_control(e.src_id)
            flow_id = draggable.data if draggable else None
            if not flow_id:
                return
            self.fm.move_flow_to_folder(flow_id, target_folder_id)
            self.refresh()
            self.app.refresh_home_view()
            self.app.show_snack("Flux déplacé ✓")

        return ft.DragTarget(group="flow", content=content, on_accept=_on_accept)

    # ─── Interactions ──────────────────────────────────────────────────────────

    def _select(self, entry_id: str) -> None:
        self._selected_id = entry_id
        self._refresh()
        if self.on_select:
            self.on_select(entry_id)

    def _toggle(self, folder_id: str) -> None:
        if folder_id in self._expanded:
            self._expanded.discard(folder_id)
        else:
            self._expanded.add(folder_id)
        self._refresh()
