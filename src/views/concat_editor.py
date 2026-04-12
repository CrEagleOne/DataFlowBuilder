"""
ui/concat_editor.py – Dialogue de configuration de la concaténation
=====================================================================
Permet de composer une valeur par concaténation de champs existants
et/ou de chaînes de texte libres.

Fonctionnalités :
  • Ajout de champs disponibles (dropdown)
  • Ajout de texte libre
  • Réordonnancement (↑ ↓)
  • Suppression d'un élément
"""

import logging

import flet as ft

logger = logging.getLogger(__name__)


class ConcatEditorDialog:
    """
    Dialogue d'édition de la concaténation d'un champ de type ``concat``.

    Args:
        app:        Instance de :class:`ui.app.DataFlowApp`.
        field_data: Dictionnaire du champ (modifié en place à la sauvegarde).
        section:    ``'header'``, ``'footer'``, ou ``'data'``.
        line_id:    ID de la ligne parente (si ``section == 'data'``).
    """

    def __init__(
        self,
        app,
        field_data: dict,
        section: str,
        line_id: str | None,
        on_save=None,
    ) -> None:
        self.app = app
        self.fm = app.flow_manager
        self.field_data = field_data
        self.section = section
        self.line_id = line_id
        self.on_save = on_save

        # Copie de travail
        self.items: list[dict] = field_data.get("concatItems", []).copy()

        self._items_col: ft.Column | None = None
        self._field_dd: ft.Dropdown | None = None
        self._text_tf: ft.TextField | None = None
        self._dialog: ft.AlertDialog | None = None

    # ═══════════════════════════════════════════════════════════════════════════
    # API publique
    # ═══════════════════════════════════════════════════════════════════════════

    def open(self) -> None:
        """Construit et affiche le dialogue PAR-DESSUS le dialogue parent."""
        self._dialog = self._build_dialog()
        self.app.open_sub_dialog(self._dialog)

    # ═══════════════════════════════════════════════════════════════════════════
    # Construction
    # ═══════════════════════════════════════════════════════════════════════════

    def _available_fields(self) -> list[dict]:
        """Retourne les champs disponibles (hors le champ courant)."""
        fm = self.fm
        current_id = self.field_data.get("id")

        if self.section == "header":
            src = fm.header_fields
        elif self.section == "footer":
            src = fm.footer_fields
        else:
            src = []
            for line in fm.field_lines:
                if line["id"] == self.line_id:
                    src = line["fields"]
                    break

        return [f for f in src if f["id"] != current_id]

    def _build_dialog(self) -> ft.AlertDialog:
        self._items_col = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, height=240)
        self._fill_items()

        available = self._available_fields()
        self._field_dd = ft.Dropdown(
            label="Champ à ajouter",
            options=[ft.dropdown.Option(f["id"], f["name"]) for f in available]
            or [ft.dropdown.Option("", "(aucun champ disponible)")],
            expand=True,
        )
        self._text_tf = ft.TextField(
            label="Texte libre",
            hint_text="Ex :  –  /  _  @  …",
            expand=True,
        )

        return ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.MERGE_TYPE, color=ft.Colors.PURPLE_400),
                    ft.Text(
                        "Configuration de la concaténation", size=16, weight=ft.FontWeight.BOLD
                    ),
                ],
                spacing=10,
            ),
            content=ft.Container(
                content=ft.Column(
                    [
                        # ── Liste des éléments ──────────────────────────────
                        ft.Text(
                            "Éléments (dans l'ordre d'assemblage) :",
                            weight=ft.FontWeight.W_500,
                            size=13,
                        ),
                        ft.Container(
                            content=self._items_col,
                            border=ft.border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
                            border_radius=8,
                            padding=8,
                        ),
                        ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.WHITE)),
                        # ── Ajout d'un champ ────────────────────────────────
                        ft.Text("Ajouter un élément :", weight=ft.FontWeight.W_500, size=13),
                        ft.Row(
                            [
                                self._field_dd,
                                ft.ElevatedButton(
                                    "＋ Champ",
                                    icon=ft.Icons.ADD_LINK,
                                    on_click=self._add_field,
                                    style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_800),
                                ),
                            ],
                            spacing=10,
                        ),
                        ft.Row(
                            [
                                self._text_tf,
                                ft.OutlinedButton(
                                    "＋ Texte",
                                    icon=ft.Icons.TEXT_FIELDS,
                                    on_click=self._add_text,
                                ),
                            ],
                            spacing=10,
                        ),
                    ],
                    spacing=12,
                ),
                width=580,
                padding=8,
            ),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self.app.close_sub_dialog()),
                ft.ElevatedButton(
                    "Sauvegarder",
                    icon=ft.Icons.SAVE_OUTLINED,
                    on_click=self._save,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_800),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    # ─── Rendu des items ──────────────────────────────────────────────────────

    def _fill_items(self) -> None:
        """Remplit la liste des éléments de concaténation."""
        if self._items_col is None:
            return

        self._items_col.controls.clear()
        available = self._available_fields()

        if not self.items:
            self._items_col.controls.append(
                ft.Text(
                    "(vide – ajoutez des champs ou du texte ci-dessous)",
                    color=ft.Colors.GREY_600,
                    italic=True,
                    size=12,
                )
            )
        else:
            for i, item in enumerate(self.items):
                is_field = item["type"] == "field"
                if is_field:
                    label = next(
                        (f["name"] for f in available if f["id"] == item.get("fieldId")),
                        "⚠️ Inconnu",
                    )
                    icon = ft.Icons.DATASET_LINKED
                    color = ft.Colors.BLUE_300
                    text = f"[Champ] {label}"
                else:
                    icon = ft.Icons.TEXT_SNIPPET
                    color = ft.Colors.GREEN_300
                    text = f'[Texte] "{item.get("value", "")}"'

                row = ft.Container(
                    content=ft.Row(
                        [
                            ft.Text(f"{i + 1}.", size=11, color=ft.Colors.GREY_600, width=22),
                            ft.Icon(icon, size=14, color=color),
                            ft.Text(text, size=12, expand=True),
                            ft.IconButton(
                                icon=ft.Icons.KEYBOARD_ARROW_UP,
                                icon_size=14,
                                disabled=(i == 0),
                                tooltip="Monter",
                                on_click=lambda e, idx=i: self._move(idx, -1),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.KEYBOARD_ARROW_DOWN,
                                icon_size=14,
                                disabled=(i >= len(self.items) - 1),
                                tooltip="Descendre",
                                on_click=lambda e, idx=i: self._move(idx, +1),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_size=14,
                                icon_color=ft.Colors.RED_400,
                                tooltip="Supprimer",
                                on_click=lambda e, idx=i: self._delete(idx),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=4,
                    ),
                    bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
                    border_radius=6,
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                )
                self._items_col.controls.append(row)

        try:
            self._items_col.update()
        except Exception:
            logger.debug("Widget update skipped", exc_info=True)

    # ─── Actions ──────────────────────────────────────────────────────────────

    def _add_field(self, e) -> None:
        if self._field_dd and self._field_dd.value:
            self.items.append({"type": "field", "fieldId": self._field_dd.value})
            self._fill_items()

    def _add_text(self, e) -> None:
        val = self._text_tf.value.strip() if self._text_tf else ""
        if val:
            self.items.append({"type": "text", "value": val})
            if self._text_tf is not None:
                self._text_tf.value = ""
                try:
                    self._text_tf.update()
                except Exception:
                    logger.debug("Widget update skipped", exc_info=True)
            self._fill_items()

    def _move(self, idx: int, direction: int) -> None:
        ni = idx + direction
        if 0 <= ni < len(self.items):
            self.items[idx], self.items[ni] = self.items[ni], self.items[idx]
        self._fill_items()

    def _delete(self, idx: int) -> None:
        self.items.pop(idx)
        self._fill_items()

    def _save(self, e) -> None:
        self.field_data["concatItems"] = self.items
        self.app.close_sub_dialog()
        self.app.show_snack("✅ Concaténation sauvegardée.")
        if self.on_save:
            self.on_save()
