"""
ui/components.py – Composants réutilisables pour l'affichage des champs
========================================================================
• :class:`FieldCard`    – carte d'un champ avec badge de type et actions
• :class:`FieldsSection`– section en-tête ou pied de page
• :class:`DataSection`  – section données avec gestion des lignes multiples

Les champs portant une catégorie au format ``xxx.yyy.zzz`` (profondeur
illimitée) sont regroupés dans des panneaux imbriqués pliables/dépliables.
"""

import logging
from collections import OrderedDict

import flet as ft

from core.field_types import FIELD_BASE_TYPES
from views.field_editor import FieldEditorDialog
from views.preset_manager import PresetManagerDialog

logger = logging.getLogger(__name__)

# ── Couleurs associées aux types de base ─────────────────────────────────────
_TYPE_COLORS: dict[str, str] = {
    "alpha": "#2E7D32",
    "num": "#1565C0",
    "date": "#6A1B9A",
    "bool": "#B71C1C",
    "decimal": "#006064",
}

# Libellés courts des sous-types pour le badge
_SUBTYPE_LABELS: dict[str, str] = {
    "none": "",
    "email": "email",
    "phone": "tél",
    "phonePlus33": "+33",
    "civilite": "civilité",
    "nom": "nom",
    "prenom": "prénom",
    "ville": "ville",
    "pays": "pays",
    "adresse": "adresse",
    "adresseComplete": "adr. complète",
    "concat": "concat",
    "lieuNaissance": "lieu naiss.",
    "codeApe": "APE",
    "codePostal": "CP",
    "codeInsee": "INSEE",
    "siret": "SIRET",
    "departement": "dept",
    "iban": "IBAN",
    "nir": "NIR",
    "compteurLignes": "cpt. lignes",
    "departementNaissance": "dept naiss.",
    "dateJour": "aujourd'hui",
    "dateNaissance": "naiss.",
    "ON": "O/N",
    "OUINON": "OUI/NON",
    "OKKO": "OK/KO",
}

# Palette de couleurs pour les niveaux de catégories
_CATEGORY_LEVEL_COLORS = [
    ft.Colors.BLUE_300,
    ft.Colors.CYAN_300,
    ft.Colors.TEAL_300,
    ft.Colors.GREEN_300,
    ft.Colors.LIME_300,
]


def _badge_label(field: dict) -> str:
    """Retourne le libellé à afficher dans le badge type.

    Args:
        field: Dictionnaire du champ.

    Returns:
        str: Libellé formaté ``base`` ou ``base:sous_type``.
    """
    base = str(field.get("type", "alpha"))
    sub = str(field.get("subType", "none") or "none")
    sub_lbl = _SUBTYPE_LABELS.get(sub, sub)
    if sub_lbl:
        return f"{base}:{sub_lbl}"
    return base


# ══════════════════════════════════════════════════════════════════════════════
# Arbre de catégories – fonctions module-level
# ══════════════════════════════════════════════════════════════════════════════


def _build_fields_tree(fields: list) -> dict:
    """Construit un arbre imbriqué depuis une liste de champs.

    Chaque champ possède une propriété ``category`` au format ``xxx.yyy.zzz``
    (profondeur illimitée, séparateur ``'.'``). Les champs sans catégorie
    sont placés à la racine sous la clé ``'_fields'``.

    Args:
        fields: Liste de dicts de champs.

    Returns:
        dict: Arbre dont chaque nœud a la forme
        ``{"_fields": list, "_children": OrderedDict}``.
    """
    root: dict = {"_fields": [], "_children": OrderedDict()}
    for field in fields:
        cat = (field.get("category") or "").strip()
        if not cat:
            root["_fields"].append(field)
        else:
            parts = [p.strip() for p in cat.split(".") if p.strip()]
            node = root
            for part in parts:
                if part not in node["_children"]:
                    node["_children"][part] = {"_fields": [], "_children": OrderedDict()}
                node = node["_children"][part]
            node["_fields"].append(field)
    return root


def _count_fields_in_node(node: dict) -> int:
    """Compte récursivement le nombre total de champs dans un nœud.

    Args:
        node: Nœud d'arbre au format ``{"_fields": list, "_children": dict}``.

    Returns:
        int: Nombre total de champs dans ce nœud et tous ses descendants.
    """
    count = len(node["_fields"])
    for child in node["_children"].values():
        count += _count_fields_in_node(child)
    return count


def _render_category_node(
    node: dict,
    section: str,
    line_id: str | None,
    all_fields: list,
    app,
    depth: int = 0,
) -> list:
    """Convertit récursivement un nœud d'arbre en liste de contrôles Flet.

    Les champs directs du nœud sont rendus en :class:`FieldCard`.
    Les nœuds enfants (sous-catégories) sont enveloppés dans des
    ``ft.ExpansionTile`` imbriqués, initialement déployés.

    Args:
        node: Nœud courant ``{"_fields": list, "_children": OrderedDict}``.
        section: Section parente (``'header'``, ``'footer'`` ou ``'data'``).
        line_id: ID de la ligne parente pour les champs de données.
        all_fields: Liste plate complète des champs (pour les indices).
        app: Instance de l'application.
        depth: Profondeur de récursion (0 = racine).

    Returns:
        list: Liste de ``ft.Control`` prêts à être insérés dans une ``Column``.
    """
    controls: list = []
    total = len(all_fields)
    level_color = _CATEGORY_LEVEL_COLORS[min(depth, len(_CATEGORY_LEVEL_COLORS) - 1)]

    # ── Champs directs de ce nœud ─────────────────────────────────────────────
    for field in node["_fields"]:
        try:
            idx = next(i for i, f in enumerate(all_fields) if f["id"] == field["id"])
        except StopIteration:
            idx = 0
        controls.append(FieldCard.build(field, section, line_id, idx, total, app))

    # ── Sous-catégories ───────────────────────────────────────────────────────
    for cat_name, child_node in node["_children"].items():
        child_controls = _render_category_node(
            child_node, section, line_id, all_fields, app, depth + 1
        )
        nb = _count_fields_in_node(child_node)

        tile = ft.ExpansionTile(
            title=ft.Row(
                [
                    ft.Text(
                        cat_name,
                        size=12,
                        weight=ft.FontWeight.W_600,
                        color=level_color,
                    ),
                    ft.Container(
                        content=ft.Text(
                            f"{nb} champ{'s' if nb != 1 else ''}",
                            size=10,
                            color=ft.Colors.GREY_500,
                        ),
                        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.WHITE),
                        border_radius=8,
                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            leading=ft.Icon(
                ft.Icons.LABEL_OUTLINE,
                size=14,
                color=level_color,
            ),
            bgcolor=ft.Colors.with_opacity(0.02 * (depth + 1), ft.Colors.WHITE),
            collapsed_bgcolor=ft.Colors.with_opacity(0.015 * (depth + 1), ft.Colors.WHITE),
            tile_padding=ft.padding.only(left=depth * 8 + 8, right=8, top=2, bottom=2),
            controls=child_controls,
        )

        controls.append(
            ft.Container(
                content=tile,
                border=ft.border.all(1, ft.Colors.with_opacity(0.12, level_color)),
                border_radius=8,
                margin=ft.margin.only(bottom=4),
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            )
        )

    return controls


# ══════════════════════════════════════════════════════════════════════════════
# FieldCard
# ══════════════════════════════════════════════════════════════════════════════


class FieldCard:
    """Composant statique qui construit la carte d'un champ.

    Affiche : numéro, badge type, nom, longueur, catégorie.
    Actions  : monter, descendre, éditer, gérer presets, supprimer.
    """

    @staticmethod
    def build(
        field: dict,
        section: str,
        line_id: str | None,
        index: int,
        total: int,
        app,
    ) -> ft.Container:
        """Construit le contrôle carte pour un champ.

        Args:
            field: Dictionnaire du champ à afficher.
            section: Section parente (``'header'``, ``'footer'``, ``'data'``).
            line_id: ID de la ligne parente (uniquement si ``section == 'data'``).
            index: Position du champ dans la liste plate (pour l'affichage ``#N``
                et les boutons monter/descendre).
            total: Nombre total de champs dans la liste plate.
            app: Instance de l'application.

        Returns:
            ft.Container: Contrôle carte prêt à l'affichage.
        """
        raw_type = field.get("type", "alpha")
        base = raw_type if raw_type in FIELD_BASE_TYPES else "alpha"
        color = _TYPE_COLORS.get(base, "#546E7A")
        label = _badge_label(field)

        type_badge = ft.Container(
            content=ft.Text(label, size=10, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
            bgcolor=color,
            border_radius=4,
            padding=ft.Padding.symmetric(horizontal=7, vertical=3),
        )

        # Badge catégorie complet (visible seulement si la catégorie est présente)
        cat = (field.get("category") or "").strip()
        cat_badge = (
            ft.Container(
                content=ft.Text(cat, size=9, color=ft.Colors.GREY_400),
                bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.BLUE),
                border_radius=4,
                padding=ft.Padding.symmetric(horizontal=5, vertical=2),
                tooltip=f"Catégorie : {cat}",
            )
            if cat
            else None
        )

        info_controls: list[ft.Control] = [
            ft.Text(f"#{index + 1}", size=11, color=ft.Colors.GREY_600, width=28),
            type_badge,
            ft.Text(field.get("name", ""), size=13, weight=ft.FontWeight.W_600),
            ft.Text(f"L={field.get('length', 10)}", size=11, color=ft.Colors.GREY_500),
        ]
        if cat_badge:
            info_controls.append(cat_badge)
        if field.get("category"):
            pass  # already added above
        if field.get("category") and field.get("category") != cat:
            # fallback – should not happen
            info_controls.append(
                ft.Text(
                    f"[{field['category']}]",
                    size=10,
                    color=ft.Colors.BLUE_300,
                    italic=True,
                )
            )

        info = ft.Row(
            info_controls,
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # Icône si non inclus dans la sortie
        if not field.get("includeInOutput", True):
            info.controls.append(
                ft.Icon(
                    ft.Icons.VISIBILITY_OFF_OUTLINED,
                    size=12,
                    color=ft.Colors.GREY_600,
                    tooltip="Non inclus dans la sortie",
                )
            )

        move_up = (
            ft.IconButton(
                icon=ft.Icons.KEYBOARD_ARROW_UP,
                icon_size=15,
                tooltip="Monter",
                on_click=lambda e: FieldCard._move(app, field["id"], section, line_id, -1),
            )
            if index > 0
            else ft.Container(width=32)
        )

        move_dn = (
            ft.IconButton(
                icon=ft.Icons.KEYBOARD_ARROW_DOWN,
                icon_size=15,
                tooltip="Descendre",
                on_click=lambda e: FieldCard._move(app, field["id"], section, line_id, +1),
            )
            if index < total - 1
            else ft.Container(width=32)
        )

        actions = ft.Row(
            [
                move_up,
                move_dn,
                ft.IconButton(
                    icon=ft.Icons.EDIT_OUTLINED,
                    icon_size=15,
                    icon_color=ft.Colors.BLUE_300,
                    tooltip="Éditer",
                    on_click=lambda e: FieldCard._edit(app, field, section, line_id),
                ),
                ft.IconButton(
                    icon=ft.Icons.TUNE,
                    icon_size=15,
                    icon_color=ft.Colors.ORANGE_300,
                    tooltip="Gérer les données / presets",
                    on_click=lambda e: FieldCard._presets(app, field),
                ),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    icon_size=15,
                    icon_color=ft.Colors.RED_400,
                    tooltip="Supprimer",
                    on_click=lambda e: FieldCard._delete(app, field["id"], section, line_id),
                ),
            ],
            spacing=0,
        )

        return ft.Container(
            content=ft.Row(
                [ft.Container(info, expand=True), actions],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
            border=ft.border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.WHITE)),
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            margin=ft.margin.only(bottom=4),
        )

    # ── Callbacks ─────────────────────────────────────────────────────────────

    @staticmethod
    def _edit(app, field, section, line_id) -> None:
        """Ouvre le dialogue d'édition du champ.

        Args:
            app: Instance de l'application.
            field: Champ à éditer.
            section: Section parente.
            line_id: ID de la ligne parente.
        """
        FieldEditorDialog(app, field, section, line_id).open()

    @staticmethod
    def _presets(app, field) -> None:
        """Ouvre le gestionnaire de presets du champ.

        Args:
            app: Instance de l'application.
            field: Champ dont on gère les presets.
        """
        PresetManagerDialog(app, field).open()

    @staticmethod
    def _delete(app, field_id: str, section: str, line_id: str | None) -> None:
        """Supprime un champ après confirmation.

        Args:
            app: Instance de l'application.
            field_id: ID du champ à supprimer.
            section: Section parente.
            line_id: ID de la ligne parente (si section ``'data'``).
        """

        def do_delete():
            fm = app.flow_manager
            if section == "header":
                fm.header_fields = [f for f in fm.header_fields if f["id"] != field_id]
            elif section == "footer":
                fm.footer_fields = [f for f in fm.footer_fields if f["id"] != field_id]
            elif section == "data":
                for line in fm.field_lines:
                    if line["id"] == line_id:
                        line["fields"] = [f for f in line["fields"] if f["id"] != field_id]
                        break
            app.refresh_current_tab()

        app.confirm("Supprimer le champ", "Cette action est irréversible.", do_delete)

    @staticmethod
    def _move(app, field_id: str, section: str, line_id: str | None, direction: int) -> None:
        """Déplace un champ vers le haut ou le bas dans sa liste.

        Args:
            app: Instance de l'application.
            field_id: ID du champ à déplacer.
            section: Section parente.
            line_id: ID de la ligne parente (si section ``'data'``).
            direction: ``-1`` pour monter, ``+1`` pour descendre.
        """
        fm = app.flow_manager
        if section == "header":
            fields = fm.header_fields
        elif section == "footer":
            fields = fm.footer_fields
        else:
            fields = []
            for line in fm.field_lines:
                if line["id"] == line_id:
                    fields = line["fields"]
                    break

        for i, f in enumerate(fields):
            if f["id"] == field_id:
                ni = i + direction
                if 0 <= ni < len(fields):
                    fields[i], fields[ni] = fields[ni], fields[i]
                break

        app.refresh_current_tab()


# ══════════════════════════════════════════════════════════════════════════════
# FieldsSection
# ══════════════════════════════════════════════════════════════════════════════


class FieldsSection:
    """Gère une section en-tête ou pied de page.

    Les champs sont regroupés par catégorie (format ``xxx.yyy.zzz``) dans
    des panneaux pliables imbriqués.

    Args:
        app: Instance de :class:`ui.app.DataFlowApp`.
        section: ``'header'`` ou ``'footer'``.
    """

    _TITLES = {"header": "En-tête", "footer": "Pied de page"}

    def __init__(self, app, section: str) -> None:
        self.app = app
        self.fm = app.flow_manager
        self.section = section
        self._col: ft.Column | None = None
        app._current_sections[section] = self

    def build_container(self) -> ft.Container:
        """Construit et retourne le conteneur principal de la section.

        Returns:
            ft.Container: Conteneur avec titre, bouton d'ajout et liste de champs.
        """
        self._col = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)
        self._fill_col()

        title = self._TITLES.get(self.section, self.section)
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(title, size=16, weight=ft.FontWeight.W_700),
                            ft.ElevatedButton(
                                "Ajouter un champ",
                                icon=ft.Icons.ADD,
                                on_click=lambda e: self._add_field(),
                                style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_800),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
                    self._col,
                ],
                spacing=16,
                expand=True,
            ),
            padding=ft.Padding.symmetric(horizontal=32, vertical=24),
            expand=True,
        )

    def _fill_col(self) -> None:
        """Remplit la colonne avec les cartes de champs regroupées par catégorie.

        Les champs sans catégorie sont affichés en premier, suivis des
        sous-catégories dans des panneaux ``ExpansionTile`` imbriqués.
        """
        if self._col is None:
            return
        self._col.controls.clear()
        fields = self.fm.header_fields if self.section == "header" else self.fm.footer_fields

        if not fields:
            self._col.controls.append(
                ft.Container(
                    content=ft.Text(
                        f"Aucun champ dans la section {self._TITLES.get(self.section, '')}."
                        "  Cliquez sur « Ajouter un champ ».",
                        color=ft.Colors.GREY_600,
                        italic=True,
                        size=13,
                    ),
                    padding=ft.Padding.symmetric(vertical=24),
                )
            )
        else:
            tree = _build_fields_tree(fields)
            controls = _render_category_node(tree, self.section, None, fields, self.app)
            self._col.controls.extend(controls)

    def refresh(self) -> None:
        """Rafraîchit l'affichage de la section.

        Reconstruit l'arbre de catégories et met à jour le widget Flet.
        """
        self._fill_col()
        if self._col is None:
            return
        try:
            self._col.update()
        except Exception:
            logger.debug("Widget update skipped", exc_info=True)

    def _add_field(self) -> None:
        """Ouvre le dialogue d'ajout d'un nouveau champ dans la section."""
        FieldEditorDialog(self.app, None, self.section, None, on_save=self.refresh).open()


# ══════════════════════════════════════════════════════════════════════════════
# DataSection
# ══════════════════════════════════════════════════════════════════════════════


class DataSection:
    """Gère la section données : liste de lignes, chacune contenant ses champs.

    Les champs de chaque ligne sont regroupés par catégorie (format
    ``xxx.yyy.zzz``) dans des panneaux pliables imbriqués.

    Args:
        app: Instance de :class:`ui.app.DataFlowApp`.
    """

    def __init__(self, app) -> None:
        self.app = app
        self.fm = app.flow_manager
        self._col: ft.Column | None = None
        app._current_sections["data"] = self

    def build_container(self) -> ft.Container:
        """Construit et retourne le conteneur principal de la section données.

        Returns:
            ft.Container: Conteneur avec titre, bouton d'ajout et liste de lignes.
        """
        self._col = ft.Column(spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)
        self._fill_col()

        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text("Structures de données", size=16, weight=ft.FontWeight.W_700),
                            ft.ElevatedButton(
                                "Ajouter une ligne",
                                icon=ft.Icons.ADD,
                                on_click=lambda e: self._add_line(),
                                style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_800),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
                    self._col,
                ],
                spacing=16,
                expand=True,
            ),
            padding=ft.Padding.symmetric(horizontal=32, vertical=24),
            expand=True,
        )

    def _fill_col(self) -> None:
        """Remplit la colonne avec les cartes de lignes."""
        if self._col is None:
            return
        self._col.controls.clear()
        lines = self.fm.field_lines

        if not lines:
            self._col.controls.append(
                ft.Container(
                    content=ft.Text(
                        "Aucune ligne définie.  Cliquez sur « Ajouter une ligne ».",
                        color=ft.Colors.GREY_600,
                        italic=True,
                        size=13,
                    ),
                    padding=ft.Padding.symmetric(vertical=24),
                )
            )
        else:
            for line in lines:
                self._col.controls.append(self._build_line_card(line))

    def refresh(self) -> None:
        """Rafraîchit l'affichage de la section données.

        Reconstruit les cartes de lignes et met à jour le widget Flet.
        """
        self._fill_col()
        if self._col is None:
            return
        try:
            self._col.update()
        except Exception:
            logger.debug("Widget update skipped", exc_info=True)

    def _build_line_card(self, line: dict) -> ft.Card:
        """Construit la carte d'une ligne de données.

        Les champs sont regroupés par catégorie dans des panneaux pliables.

        Args:
            line: Dictionnaire de la ligne ``{id, name, fields}``.

        Returns:
            ft.Card: Carte complète de la ligne avec en-tête et corps.
        """
        fields = line.get("fields", [])
        nb_fields = len(fields)

        name_field = ft.TextField(
            value=line.get("name", ""),
            border=ft.InputBorder.NONE,
            text_style=ft.TextStyle(size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
            on_change=lambda e, lid=line["id"]: self.fm.update_line_name(lid, e.control.value),
            expand=True,
            hint_text="Nom de la ligne…",
            hint_style=ft.TextStyle(color=ft.Colors.GREY_600),
        )

        header = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.TABLE_ROWS_OUTLINED, size=16, color=ft.Colors.BLUE_400),
                    name_field,
                    ft.Text(
                        f"{nb_fields} champ{'s' if nb_fields != 1 else ''}",
                        size=11,
                        color=ft.Colors.GREY_500,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                        icon_size=18,
                        icon_color=ft.Colors.BLUE_300,
                        tooltip="Ajouter un champ",
                        on_click=lambda e, lid=line["id"]: self._add_field(lid),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_size=18,
                        icon_color=ft.Colors.RED_400,
                        tooltip="Supprimer cette ligne",
                        on_click=lambda e, lid=line["id"]: self._confirm_delete_line(lid),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            bgcolor=ft.Colors.with_opacity(0.07, ft.Colors.WHITE),
            border_radius=ft.border_radius.only(top_left=8, top_right=8),
            padding=ft.Padding.symmetric(horizontal=14, vertical=8),
        )

        if not fields:
            body_content = ft.Container(
                content=ft.Text(
                    "Aucun champ — cliquez sur ＋ pour en ajouter.",
                    color=ft.Colors.GREY_600,
                    italic=True,
                    size=12,
                ),
                padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            )
        else:
            tree = _build_fields_tree(fields)
            field_controls = _render_category_node(tree, "data", line["id"], fields, self.app)
            body_content = ft.Container(
                content=ft.Column(field_controls, spacing=3),
                padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            )

        return ft.Card(
            content=ft.Container(
                content=ft.Column([header, body_content], spacing=0),
                padding=0,
            ),
            elevation=3,
            shadow_color=ft.Colors.BLUE_900,
        )

    def _add_line(self) -> None:
        """Ajoute une nouvelle ligne de données vide et rafraîchit l'affichage."""
        self.fm.add_field_line()
        self.refresh()

    def _add_field(self, line_id: str) -> None:
        """Ouvre le dialogue d'ajout d'un champ dans une ligne.

        Args:
            line_id: ID de la ligne cible.
        """
        FieldEditorDialog(self.app, None, "data", line_id, on_save=self.refresh).open()

    def _confirm_delete_line(self, line_id: str) -> None:
        """Demande confirmation avant de supprimer une ligne de données.

        Args:
            line_id: ID de la ligne à supprimer.
        """

        def do_delete():
            self.fm.delete_field_line(line_id)
            self.refresh()

        self.app.confirm(
            "Supprimer la ligne",
            "Supprimer cette ligne et tous ses champs ? Action irréversible.",
            do_delete,
        )
