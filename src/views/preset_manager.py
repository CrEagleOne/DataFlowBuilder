"""
ui/preset_manager.py – Gestionnaire de presets d'un champ
==========================================================
Permet de définir une liste de valeurs prédéfinies pour un champ.
En mode « utiliser des valeurs aléatoires » ces presets sont ignorés.
En mode « valeurs prédéfinies », le générateur pioche aléatoirement
dans la liste.

Fonctionnalités :
  • Switch aléatoire / prédéfini
  • Ajout, modification, suppression de valeurs
  • Support de la valeur par défaut du champ (badge [Défaut])
  • Gestion spéciale de la date du jour pour les champs de type ``date``
"""

import logging
from datetime import datetime

import flet as ft

from core.field_types import DATE_FORMATS

logger = logging.getLogger(__name__)


class PresetManagerDialog:
    """
    Dialogue de gestion des presets d'un champ.

    Args:
        app:      Instance de :class:`ui.app.DataFlowApp`.
        field:    Champ concerné.
        on_close: Callback optionnel appelé à la fermeture.
    """

    def __init__(self, app, field: dict, on_close=None) -> None:
        self.app = app
        self.fm = app.flow_manager
        self.field = field
        self.field_id = field["id"]
        self.ftype = field.get("type", "")
        self.on_close = on_close

        self._selected: set[int] = set()
        self._values_col: ft.Column | None = None
        self._rand_switch: ft.Switch | None = None
        self._dialog: ft.AlertDialog | None = None

        # Initialisation des presets dans le FlowManager si absents
        if self.field_id not in self.fm.field_presets:
            self.fm.field_presets[self.field_id] = {"useRandom": True, "values": []}
            dv = field.get("defaultValue")
            if dv:
                self.fm.field_presets[self.field_id]["values"].append(
                    {
                        "value": self._display(str(dv)),
                        "comment": "Valeur par défaut",
                        "isDefault": True,
                    }
                )

        self._pdata = self.fm.field_presets[self.field_id]

    # ═══════════════════════════════════════════════════════════════════════════
    # API publique
    # ═══════════════════════════════════════════════════════════════════════════

    def open(self) -> None:
        """Construit et affiche le dialogue."""
        self._dialog = self._build_dialog()
        self.app.open_dialog(self._dialog)

    # ═══════════════════════════════════════════════════════════════════════════
    # Construction
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_dialog(self) -> ft.AlertDialog:
        self._rand_switch = ft.Switch(
            label="Générer des valeurs aléatoires",
            value=self._pdata.get("useRandom", True),
            active_color=ft.Colors.BLUE_400,
        )
        self._values_col = ft.Column(
            spacing=4,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        self._fill_table()

        return ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.TUNE, color=ft.Colors.ORANGE_400),
                    ft.Column(
                        [
                            ft.Text("Données du champ", size=16, weight=ft.FontWeight.BOLD),
                            ft.Text(
                                f"{self.field.get('name', '')}  ·  {self.ftype}",
                                size=12,
                                color=ft.Colors.GREY_400,
                            ),
                        ],
                        spacing=2,
                    ),
                ],
                spacing=10,
            ),
            content=ft.Container(
                content=ft.Column(
                    [
                        # ── Switch aléatoire ─────────────────────────────────
                        ft.Container(
                            content=self._rand_switch,
                            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
                            border_radius=10,
                            padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                        ),
                        ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.WHITE)),
                        # ── En-tête + boutons CRUD ────────────────────────────
                        ft.Row(
                            [
                                ft.Column(
                                    [
                                        ft.Text(
                                            "Valeurs prédéfinies :",
                                            weight=ft.FontWeight.W_500,
                                            size=13,
                                        ),
                                        ft.Text(
                                            "(utilisées quand le mode aléatoire est désactivé)",
                                            size=11,
                                            color=ft.Colors.GREY_500,
                                        ),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                                ft.Row(
                                    [
                                        ft.ElevatedButton(
                                            "Ajouter",
                                            icon=ft.Icons.ADD,
                                            on_click=self._add_dialog,
                                            style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_800),
                                        ),
                                        ft.OutlinedButton(
                                            "Supprimer sélectionnés",
                                            icon=ft.Icons.DELETE_OUTLINE,
                                            on_click=self._delete_selected,
                                        ),
                                    ],
                                    spacing=8,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        # ── Zone scrollable des valeurs ───────────────────────
                        ft.Container(
                            content=self._values_col,
                            border=ft.border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
                            border_radius=8,
                            padding=8,
                            expand=True,
                        ),
                    ],
                    spacing=12,
                    expand=True,
                ),
                width=680,
                height=460,
                padding=8,
                expand=True,
            ),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._close()),
                ft.ElevatedButton(
                    "Sauvegarder",
                    icon=ft.Icons.SAVE_OUTLINED,
                    on_click=self._save,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_800),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    # ─── Tableau ───────────────────────────────────────────────────────────────

    def _fill_table(self) -> None:
        if self._values_col is None:
            return

        self._values_col.controls.clear()
        self._selected.clear()
        values = self._pdata.get("values", [])

        if not values:
            self._values_col.controls.append(
                ft.Text("(aucune valeur définie)", color=ft.Colors.GREY_600, italic=True, size=12)
            )
        else:
            # En-têtes
            self._values_col.controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Container(width=32),
                            ft.Text("Valeur", size=11, weight=ft.FontWeight.BOLD, width=200),
                            ft.Text("Commentaire", size=11, weight=ft.FontWeight.BOLD, expand=True),
                        ],
                        spacing=8,
                    ),
                    bgcolor=ft.Colors.with_opacity(0.07, ft.Colors.WHITE),
                    border_radius=6,
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                )
            )

            for i, item in enumerate(values):
                is_default = item.get("isDefault", False)
                disp_val = self._display(item.get("value", ""))

                chk = ft.Checkbox(
                    value=False,
                    disabled=is_default,
                    on_change=lambda e, idx=i: self._toggle(idx, e.control.value),
                )

                row = ft.Container(
                    content=ft.Row(
                        [
                            chk,
                            ft.Text(
                                disp_val, size=12, width=200, overflow=ft.TextOverflow.ELLIPSIS
                            ),
                            ft.Text(
                                item.get("comment", ""),
                                size=11,
                                color=ft.Colors.GREY_400,
                                expand=True,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            ft.Container(
                                content=ft.Text(
                                    "[Défaut]",
                                    size=10,
                                    color=ft.Colors.ORANGE_400,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                visible=is_default,
                                padding=ft.padding.only(right=4),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.EDIT_OUTLINED,
                                icon_size=14,
                                icon_color=ft.Colors.BLUE_300,
                                tooltip="Modifier",
                                disabled=is_default,
                                on_click=lambda e, idx=i: self._edit_dialog(idx),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                    bgcolor=(
                        ft.Colors.with_opacity(0.06, ft.Colors.ORANGE)
                        if is_default
                        else ft.Colors.with_opacity(0.03, ft.Colors.WHITE)
                    ),
                    border_radius=6,
                    padding=ft.Padding.symmetric(horizontal=4, vertical=4),
                )
                self._values_col.controls.append(row)

        try:
            self._values_col.update()
        except Exception:
            logger.debug("Widget update skipped", exc_info=True)

    # ─── Actions ──────────────────────────────────────────────────────────────

    def _toggle(self, idx: int, selected: bool) -> None:
        if selected:
            self._selected.add(idx)
        else:
            self._selected.discard(idx)

    def _add_dialog(self, e) -> None:
        """Mini-dialogue pour ajouter une valeur."""
        val_tf = ft.TextField(label="Valeur *", autofocus=True, width=300)
        comment_tf = ft.TextField(label="Commentaire", width=300)

        def do_add(ev):
            if val_tf.value:
                self._pdata["values"].append(
                    {"value": val_tf.value, "comment": comment_tf.value or "", "isDefault": False}
                )
                # Retour au dialog principal avec table rafraîchie
                self.app.open_dialog(self._dialog)
                self._fill_table()

        sub_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Ajouter une valeur"),
            content=ft.Column([val_tf, comment_tf], spacing=12, tight=True),
            actions=[
                ft.TextButton(
                    "Annuler",
                    on_click=lambda e: self.app.open_dialog(self._dialog),
                ),
                ft.ElevatedButton("Ajouter", on_click=do_add),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.app.open_dialog(sub_dlg)

    def _edit_dialog(self, idx: int) -> None:
        """Mini-dialogue pour modifier une valeur existante."""
        item = self._pdata["values"][idx]
        val_tf = ft.TextField(label="Valeur *", value=item["value"], autofocus=True, width=300)
        comment_tf = ft.TextField(label="Commentaire", value=item.get("comment", ""), width=300)

        def do_edit(ev):
            if val_tf.value:
                item["value"] = val_tf.value
                item["comment"] = comment_tf.value or ""
                # Retour au dialog principal avec table rafraîchie
                self.app.open_dialog(self._dialog)
                self._fill_table()

        sub_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Modifier la valeur"),
            content=ft.Column([val_tf, comment_tf], spacing=12, tight=True),
            actions=[
                ft.TextButton(
                    "Annuler",
                    on_click=lambda e: self.app.open_dialog(self._dialog),
                ),
                ft.ElevatedButton("Sauvegarder", on_click=do_edit),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.app.open_dialog(sub_dlg)

    def _delete_selected(self, e) -> None:
        """Supprime les valeurs cochées (sauf [Défaut])."""
        if not self._selected:
            return
        for idx in sorted(self._selected, reverse=True):
            item = self._pdata["values"][idx]
            if not item.get("isDefault"):
                self._pdata["values"].pop(idx)
        self._selected.clear()
        self._fill_table()

    def _save(self, e) -> None:
        assert self._rand_switch is not None
        self._pdata["useRandom"] = self._rand_switch.value
        self._close()
        self.app.show_snack("✅ Presets sauvegardés.")
        if self.on_close:
            self.on_close()

    def _close(self) -> None:
        self.app.close_dialog()

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _display(self, value: str) -> str:
        """Retourne la valeur à afficher (gère la date du jour)."""
        if self.ftype == "date" and self.field.get("useTodayDate", False):
            fmt_key = self.field.get("format", "DD/MM/YYYY")
            today = datetime.today()
            if fmt_key == "timestamp":
                return str(int(datetime.combine(today, datetime.min.time()).timestamp()))
            fmt = DATE_FORMATS.get(fmt_key, "%d/%m/%Y")
            return today.strftime(fmt)
        return value
