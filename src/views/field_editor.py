"""
ui/field_editor.py – Dialogue d'édition / création d'un champ
==============================================================
Formulaire adaptatif avec :
  • Type de base  (alpha / num / date / bool / decimal)
  • Sous-type     (selon le type de base)
  • Options dynamiques selon le sous-type sélectionné
  • Remplissage : caractère masqué si « Aucun »
  • Inclure dans la sortie (seule case — remplace Requis + ancienne case)
"""

import logging
from datetime import datetime

import flet as ft

from core.field_types import (
    CIVILITES,
    DATE_FORMAT_LENGTHS,
    DATE_FORMAT_PLACEHOLDERS,
    DATE_FORMATS,
    DEFAULT_FIELD_CONFIG,
    FIELD_BASE_TYPES,
    FIELD_SUBTYPES,
    get_field_defaults,
    get_visible_fields,
)

logger = logging.getLogger(__name__)


class FieldEditorDialog:
    """
    Dialogue d'édition de champ.

    Args:
        app:      Instance de :class:`ui.app.DataFlowApp`.
        field:    Champ existant à éditer, ou ``None`` pour la création.
        section:  ``'header'``, ``'footer'``, ou ``'data'``.
        line_id:  ID de la ligne parente (uniquement pour ``'data'``).
        on_save:  Callback optionnel appelé après la sauvegarde réussie.
    """

    def __init__(
        self,
        app,
        field: dict | None,
        section: str,
        line_id: str | None,
        on_save=None,
    ) -> None:
        self.app = app
        self.fm = app.flow_manager
        self.section = section
        self.line_id = line_id
        self.on_save = on_save
        self.is_new = field is None

        if self.is_new:
            self.data = DEFAULT_FIELD_CONFIG.copy()
            self.data["id"] = str(datetime.now().timestamp())
        else:
            assert field is not None
            self.data = field.copy()

        self._dialog: ft.AlertDialog | None = None
        self._opt_col: ft.Column | None = None

        # Références pour mise à jour réactive
        self._subtype_dd: ft.Dropdown | None = None
        self._padding_dd: ft.Dropdown | None = None
        self._paddingchar_dd: ft.Dropdown | None = None
        self._paddingchar_row: ft.Row | None = None
        self._concat_count_txt: ft.Text | None = None  # compteur d'éléments concat
        # longueur max (réactive)
        self._length_tf: ft.TextField | None = None
        self._date_range_row: ft.Row | None = None  # ligne min/max date
        self._date_min_tf: ft.TextField | None = None
        self._date_max_tf: ft.TextField | None = None
        # conteneurs de borne (pour afficher/masquer le détail selon "Activer")
        self._date_min_detail: ft.Column | None = None
        self._date_max_detail: ft.Column | None = None

    # ──────────────────────────────────────────────────────────────────────────
    # API publique
    # ──────────────────────────────────────────────────────────────────────────

    def open(self) -> None:
        self._dialog = self._build_dialog()
        self.app.open_dialog(self._dialog)

    # ──────────────────────────────────────────────────────────────────────────
    # Construction
    # ──────────────────────────────────────────────────────────────────────────

    def _build_dialog(self) -> ft.AlertDialog:
        title_txt = "Nouveau champ" if self.is_new else f"Éditer : {self.data.get('name', '')}"
        self._opt_col = ft.Column(spacing=12)

        form = ft.Column(
            [
                *self._common_fields(),
                ft.Divider(height=1, color=ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
                self._opt_col,
                self._comment_field(),
            ],
            spacing=16,
            scroll=ft.ScrollMode.AUTO,
            height=540,
            width=600,
        )

        base_type = str(self.data.get("type", "alpha"))
        sub_type = str(self.data.get("subType", "none"))
        self._rebuild_opt_section(base_type, sub_type)

        return ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.EDIT_NOTE, color=ft.Colors.BLUE_400),
                    ft.Text(title_txt, size=17, weight=ft.FontWeight.BOLD),
                ],
                spacing=10,
            ),
            content=ft.Container(content=form, width=700, padding=8),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self.app.close_dialog()),
                ft.ElevatedButton(
                    "Sauvegarder",
                    icon=ft.Icons.SAVE_OUTLINED,
                    on_click=self._save,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    # ─── Champs communs ────────────────────────────────────────────────────────

    def _common_fields(self) -> list[ft.Control]:
        """Contrôles toujours présents : nom, catégorie, type de base, sous-type, longueur."""
        current_base = str(self.data.get("type", "alpha"))
        current_sub = str(self.data.get("subType", "none"))
        controls: list[ft.Control] = []

        # ── Nom ──
        controls.append(
            ft.TextField(
                label="Nom du champ *",
                value=str(self.data.get("name", "")),
                autofocus=True,
                on_change=lambda e: self._upd("name", e.control.value),
            )
        )

        # ── Catégorie ──
        controls.append(
            ft.TextField(
                label="Catégorie",
                value=str(self.data.get("category", "")),
                hint_text="Ex : Client, Adresse, Finance…",
                on_change=lambda e: self._upd("category", e.control.value),
            )
        )

        # ── Type de base + Sous-type (côte à côte) ──
        self._subtype_dd = self._build_subtype_dd(current_base, current_sub)

        type_row = ft.Row(
            [
                ft.Dropdown(
                    label="Type de champ *",
                    value=current_base,
                    options=[ft.dropdown.Option(t) for t in FIELD_BASE_TYPES],
                    on_select=self._on_base_type_change,
                    expand=True,
                ),
                ft.Container(
                    content=self._subtype_dd,
                    expand=True,
                    visible=(current_base != "decimal"),
                    ref=ft.Ref(),
                ),
            ],
            spacing=16,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        # Garde la référence au conteneur du sous-type pour le masquer si decimal
        self._subtype_container: ft.Container = type_row.controls[1]  # type: ignore[assignment]
        controls.append(type_row)

        # ── Longueur + Inclure dans la sortie (case unique) ──
        self._length_tf = ft.TextField(
            label="Longueur max",
            value=str(self.data.get("length", 10)),
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=lambda e: self._upd(
                "length",
                int(e.control.value) if e.control.value.isdigit() else 10,
            ),
            width=160,
        )
        controls.append(
            ft.Row(
                [
                    self._length_tf,
                    ft.Checkbox(
                        label="Inclure dans la sortie",
                        value=bool(self.data.get("includeInOutput", True)),
                        on_change=lambda e: self._upd("includeInOutput", e.control.value),
                    ),
                ],
                spacing=20,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )

        return controls

    def _build_subtype_dd(self, base_type: str, current_sub: str) -> ft.Dropdown:
        """Crée le dropdown de sous-type pour le type de base donné."""
        subtypes = FIELD_SUBTYPES.get(base_type, [])
        options = [ft.dropdown.Option(val, lbl) for val, lbl in subtypes]
        # Si la valeur actuelle n'est pas dans la liste, remettre à 'none'
        valid_values = [val for val, _ in subtypes]
        actual_value = current_sub if current_sub in valid_values else "none"

        return ft.Dropdown(
            label="Sous-type",
            value=str(actual_value),
            options=options,
            on_select=self._on_subtype_change,
            expand=True,
        )

    def _comment_field(self) -> ft.TextField:
        return ft.TextField(
            label="Commentaire / note",
            value=str(self.data.get("comment", "")),
            multiline=True,
            min_lines=2,
            max_lines=3,
            on_change=lambda e: self._upd("comment", e.control.value),
        )

    # ─── Section conditionnelle ────────────────────────────────────────────────

    def _rebuild_opt_section(self, base_type: str, sub_type: str) -> None:
        """Reconstruit les options propres au type/sous-type sélectionné."""
        if self._opt_col is None:
            return

        self._opt_col.controls.clear()
        extra = get_visible_fields(base_type, sub_type)

        # ── Configuration civilité ──
        if "civiliteConfig" in extra:
            self._opt_col.controls.append(self._build_civilite_config())

        # ── Valeur par défaut ──
        if "defaultValue" in extra:
            self._opt_col.controls.append(
                ft.TextField(
                    label="Valeur par défaut",
                    value=str(self.data.get("defaultValue", "")),
                    on_change=lambda e: self._upd("defaultValue", e.control.value),
                )
            )

        # ── Format de date ──
        if "format" in extra:

            def _on_format_change(e):
                old_fmt_key = self.data.get("format", "DD/MM/YYYY")
                new_fmt_key = e.control.value
                self._upd("format", new_fmt_key)

                # Mettre à jour la longueur automatiquement
                new_len = DATE_FORMAT_LENGTHS.get(new_fmt_key, 10)
                self._upd("length", new_len)
                if self._length_tf is not None:
                    self._length_tf.value = str(new_len)
                    try:
                        self._length_tf.update()
                    except Exception:
                        logger.debug("Widget update skipped", exc_info=True)

                # Reformater dateMin/dateMax si renseignées
                old_py = DATE_FORMATS.get(old_fmt_key, "%d/%m/%Y")
                new_py = DATE_FORMATS.get(new_fmt_key, "%d/%m/%Y")
                if old_py == "timestamp":
                    old_py = "%d/%m/%Y"
                if new_py == "timestamp":
                    new_py = "%d/%m/%Y"

                _all_fmts = [f for f in DATE_FORMATS.values() if f != "timestamp"]

                def _reformat(raw: str) -> str:
                    """Parse avec tous les formats connus, reformate dans le nouveau."""
                    for f in [old_py] + _all_fmts:
                        try:
                            return datetime.strptime(raw, f).strftime(new_py)
                        except ValueError:
                            pass
                    return raw  # impossible à parser → on garde tel quel

                for key, tf_attr in (("dateMin", "_date_min_tf"), ("dateMax", "_date_max_tf")):
                    val = self.data.get(key, "")
                    if val:
                        new_val = _reformat(val)
                        self._upd(key, new_val)
                        tf = getattr(self, tf_attr, None)
                        if tf is not None:
                            tf.value = new_val
                            ph = DATE_FORMAT_PLACEHOLDERS.get(new_fmt_key, "")
                            tf.hint_text = ph
                            try:
                                tf.update()
                            except Exception:
                                logger.debug("Widget update skipped", exc_info=True)

                # Mettre à jour les placeholders même si les champs sont vides
                ph = DATE_FORMAT_PLACEHOLDERS.get(new_fmt_key, "")
                for tf in (self._date_min_tf, self._date_max_tf):
                    if tf is not None:
                        tf.hint_text = ph
                        try:
                            tf.update()
                        except Exception:
                            logger.debug("Widget update skipped", exc_info=True)

            self._opt_col.controls.append(
                ft.Dropdown(
                    label="Format de date",
                    value=str(self.data.get("format", "DD/MM/YYYY")),
                    options=[ft.dropdown.Option(k) for k in DATE_FORMATS],
                    on_select=_on_format_change,
                )
            )

        # ── Case « Générer à la date du jour » ──
        if "todayDate" in extra:

            def _on_today_change(e):
                checked = e.control.value
                self._upd("todayDate", checked)
                if self._date_range_row is not None:
                    self._date_range_row.visible = not checked
                    try:
                        self._date_range_row.update()
                    except Exception:
                        logger.debug("Widget update skipped", exc_info=True)

            self._opt_col.controls.append(
                ft.Checkbox(
                    label="Générer à la date du jour",
                    value=bool(self.data.get("todayDate", False)),
                    on_change=_on_today_change,
                )
            )

        # ── Bornes de date min/max ──
        if "dateRange" in extra:
            fmt_key = str(self.data.get("format", "DD/MM/YYYY"))
            ph = DATE_FORMAT_PLACEHOLDERS.get(fmt_key, "")
            today_checked = self.data.get("todayDate", False)

            def _open_datepicker(target_key: str, tf: ft.TextField):
                """Ouvre un DatePicker et reporte la date sélectionnée dans tf."""
                fmt_py = DATE_FORMATS.get(str(self.data.get("format", "DD/MM/YYYY")), "%d/%m/%Y")
                if fmt_py == "timestamp":
                    fmt_py = "%d/%m/%Y"

                dp = ft.DatePicker()

                def _on_picked(e):
                    if dp.value:
                        try:
                            val = dp.value.strftime(fmt_py)
                        except Exception:
                            val = dp.value.strftime("%d/%m/%Y")
                        self._upd(target_key, val)
                        tf.value = val
                        try:
                            tf.update()
                        except Exception:
                            logger.debug("Widget update skipped", exc_info=True)
                    if dp in self.app.page.overlay:
                        self.app.page.overlay.remove(dp)
                    try:
                        self.app.page.update()
                    except Exception:
                        logger.debug("Widget update skipped", exc_info=True)

                dp.on_change = _on_picked
                dp.on_dismiss = lambda e: (
                    (self.app.page.overlay.remove(dp) if dp in self.app.page.overlay else None)
                    or self.app.page.update()
                )

                self.app.page.overlay.append(dp)
                self.app.page.update()
                dp.open = True
                self.app.page.update()

            def _build_bound(
                label: str,
                key_enabled: str,
                key_today: str,
                key_excl: str,
                key_val: str,
                tf_attr: str,
                detail_attr: str,
            ) -> ft.Container:
                """Construit le bloc UI complet pour une borne (min ou max)."""
                enabled = bool(self.data.get(key_enabled, False))
                is_today: bool = bool(self.data.get(key_today, False))
                exclusive = self.data.get(key_excl, False)
                val = self.data.get(key_val, "")

                # TextField + bouton calendrier
                tf = ft.TextField(
                    label="Valeur fixe",
                    value=str(val),
                    hint_text=ph,
                    expand=True,
                    disabled=is_today,
                    on_change=lambda e, k=key_val: self._upd(k, e.control.value),
                )
                setattr(self, tf_attr, tf)

                cal_btn = ft.IconButton(
                    icon=ft.Icons.CALENDAR_MONTH_OUTLINED,
                    tooltip="Choisir une date",
                    icon_color=ft.Colors.BLUE_300,
                    disabled=is_today,
                    on_click=lambda e, k=key_val, _tf=tf: _open_datepicker(k, _tf),
                )

                def _on_today_bound(e, _tf=tf, _btn=cal_btn):
                    checked = e.control.value
                    self._upd(key_today, checked)
                    _tf.disabled = checked
                    _btn.disabled = checked
                    try:
                        _tf.update()
                        _btn.update()
                    except Exception:
                        logger.debug("Widget update skipped", exc_info=True)

                detail = ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Checkbox(
                                    label="Date du jour",
                                    value=bool(is_today),
                                    on_change=_on_today_bound,
                                ),
                                ft.Checkbox(
                                    label="Exclure la borne",
                                    tooltip="Coché: strict (> <) | Décoché: inclus (≥ ≤)",
                                    value=bool(exclusive),
                                    on_change=lambda e, k=key_excl: self._upd(k, e.control.value),
                                ),
                            ],
                            spacing=20,
                        ),
                        ft.Row(
                            [tf, cal_btn],
                            spacing=4,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ],
                    spacing=6,
                    visible=enabled,
                )
                setattr(self, detail_attr, detail)

                def _on_enabled(e, _detail=detail):
                    checked = e.control.value
                    self._upd(key_enabled, checked)
                    _detail.visible = checked
                    try:
                        _detail.update()
                    except Exception:
                        logger.debug("Widget update skipped", exc_info=True)

                return ft.Container(
                    content=ft.Column(
                        [
                            ft.Checkbox(
                                label=label,
                                value=bool(enabled),
                                on_change=_on_enabled,
                            ),
                            detail,
                        ],
                        spacing=4,
                    ),
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.WHITE),
                    border_radius=8,
                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                    expand=True,
                )

            bound_min = _build_bound(
                label="Activer une borne min",
                key_enabled="dateMinEnabled",
                key_today="dateMinToday",
                key_excl="dateMinExclusive",
                key_val="dateMin",
                tf_attr="_date_min_tf",
                detail_attr="_date_min_detail",
            )
            bound_max = _build_bound(
                label="Activer une borne max",
                key_enabled="dateMaxEnabled",
                key_today="dateMaxToday",
                key_excl="dateMaxExclusive",
                key_val="dateMax",
                tf_attr="_date_max_tf",
                detail_attr="_date_max_detail",
            )

            self._date_range_row = ft.Row(
                [bound_min, bound_max],
                spacing=12,
                visible=not today_checked,
                vertical_alignment=ft.CrossAxisAlignment.START,
            )
            self._opt_col.controls.append(self._date_range_row)

        # ── Numérique : incrément ──
        if "increment" in extra:
            self._opt_col.controls.append(
                ft.Row(
                    [
                        ft.Checkbox(
                            label="Valeur incrémentée",
                            value=bool(self.data.get("increment", False)),
                            on_change=lambda e: self._upd("increment", e.control.value),
                        ),
                        ft.TextField(
                            label="Départ",
                            value=str(self.data.get("incrementStart", 1)),
                            keyboard_type=ft.KeyboardType.NUMBER,
                            on_change=lambda e: self._upd(
                                "incrementStart",
                                int(e.control.value) if e.control.value.isdigit() else 1,
                            ),
                            width=120,
                        ),
                    ],
                    spacing=20,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )

        # ── Remplissage (padding) ──
        if "padding" in extra:
            self._opt_col.controls.append(self._build_padding_section())

        # ── Filtre code postal ──
        if "codePostalFilter" in extra:
            self._opt_col.controls.append(
                ft.TextField(
                    label="Filtre code postal",
                    value=str(self.data.get("codePostalFilter", "*")),
                    hint_text="Ex : 75* (Paris) | 33* (Gironde) | * (tous)",
                    on_change=lambda e: self._upd("codePostalFilter", e.control.value),
                )
            )

        # ── Décimal : séparateur + nombre de décimales ──
        if "decimal" in extra:
            self._opt_col.controls.append(
                ft.Row(
                    [
                        ft.Dropdown(
                            label="Séparateur décimal",
                            value=str(self.data.get("decimalSeparator", ".")),
                            options=[
                                ft.dropdown.Option(".", "Point  ( 3.14 )"),
                                ft.dropdown.Option(",", "Virgule ( 3,14 )"),
                            ],
                            on_select=lambda e: self._upd("decimalSeparator", e.control.value),
                            expand=True,
                        ),
                        ft.TextField(
                            label="Chiffres après virgule",
                            value=str(self.data.get("decimalPlaces", 2)),
                            keyboard_type=ft.KeyboardType.NUMBER,
                            on_change=lambda e: self._upd(
                                "decimalPlaces",
                                int(e.control.value) if e.control.value.isdigit() else 2,
                            ),
                            width=180,
                        ),
                    ],
                    spacing=16,
                )
            )

        # ── Lien vers un champ source ──
        if "linkedField" in extra:
            self._opt_col.controls.append(self._build_linked_field_section(base_type, sub_type))

        # ── Concaténation ──
        if "concat" in extra:
            _concat_raw = self.data.get("concatItems", [])
            items = list(_concat_raw) if isinstance(_concat_raw, list) else []
            nb_items = len(items)
            self._concat_count_txt = ft.Text(
                f"{nb_items} élément(s) configuré(s)",
                size=12,
                color=ft.Colors.GREY_400,
            )
            self._opt_col.controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            self._concat_count_txt,
                            ft.ElevatedButton(
                                "⚙️  Configurer la concaténation",
                                on_click=lambda e: self._open_concat_editor(),
                                style=ft.ButtonStyle(bgcolor=ft.Colors.PURPLE_900),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
                    border_radius=8,
                    padding=12,
                )
            )

        # Mettre à jour le champ longueur max si une valeur par défaut a changé
        if self._length_tf is not None:
            new_len = self.data.get("length", 10)
            self._length_tf.value = str(new_len)
            try:
                self._length_tf.update()
            except Exception:
                logger.debug("Widget update skipped", exc_info=True)

        try:
            self._opt_col.update()
        except Exception:
            logger.debug("Widget update skipped", exc_info=True)

    # ─── Civilité config ──────────────────────────────────────────────────────

    def _build_civilite_config(self) -> ft.Column:
        """Construit les contrôles de configuration du type civilité."""
        cat_options = [
            ft.dropdown.Option("classiques", "Classiques  (M. / Mme / Mlle)"),
            ft.dropdown.Option("administratives", "Administratives  (M., Dr, Pr, Me…)"),
            ft.dropdown.Option("professionnelles", "Professionnelles  (Dr, Pr, Ing…)"),
        ]
        output_options = [
            ft.dropdown.Option("code", "Code  (M, Mme, Dr…)"),
            ft.dropdown.Option("label", "Libellé  (Monsieur, Madame, Docteur…)"),
        ]

        # Aperçu des valeurs disponibles
        def _preview(cat: str, output_key: str) -> str:
            items = CIVILITES.get(cat, [])
            vals = [it[output_key] for it in items if output_key in it]
            return "  ·  ".join(vals[:6]) + ("  …" if len(vals) > 6 else "")

        preview_txt = ft.Text(
            _preview(
                str(self.data.get("civiliteCategorie", "classiques")),
                str(self.data.get("civiliteOutput", "code")),
            ),
            size=11,
            color=ft.Colors.GREY_500,
            italic=True,
        )

        def on_cat_change(e):
            self._upd("civiliteCategorie", e.control.value)
            preview_txt.value = _preview(e.control.value, self.data.get("civiliteOutput", "code"))
            try:
                preview_txt.update()
            except Exception:
                logger.debug("Widget update skipped", exc_info=True)

        def on_output_change(e):
            self._upd("civiliteOutput", e.control.value)
            preview_txt.value = _preview(
                self.data.get("civiliteCategorie", "classiques"), e.control.value
            )
            try:
                preview_txt.update()
            except Exception:
                logger.debug("Widget update skipped", exc_info=True)

        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Dropdown(
                            label="Catégorie de civilités",
                            value=str(self.data.get("civiliteCategorie", "classiques")),
                            options=cat_options,
                            on_select=on_cat_change,
                            expand=True,
                        ),
                        ft.Dropdown(
                            label="Valeur générée",
                            value=str(self.data.get("civiliteOutput", "code")),
                            options=output_options,
                            on_select=on_output_change,
                            width=220,
                        ),
                    ],
                    spacing=16,
                ),
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.PREVIEW_OUTLINED, size=13, color=ft.Colors.GREY_600),
                            preview_txt,
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.padding.only(top=4, left=2),
                ),
            ],
            spacing=8,
        )

    # ─── Callback rafraîchissement compteur concat ────────────────────────────

    def _refresh_concat_count(self) -> None:
        """Appelé par ConcatEditorDialog après sauvegarde pour
        mettre à jour le compteur.
        """
        if self._concat_count_txt is not None:
            _concat_raw = self.data.get("concatItems", [])
            nb = len(list(_concat_raw) if isinstance(_concat_raw, list) else [])
            self._concat_count_txt.value = f"{nb} élément(s) configuré(s)"
            try:
                self._concat_count_txt.update()
            except Exception:
                logger.debug("Widget update skipped", exc_info=True)

    # ─── Lien vers champ source ───────────────────────────────────────────────

    # Sous-types dépendants → (sous-type source attendu, groupe)
    _LINK_SOURCE_MAP: dict[str, tuple[str, str]] = {
        "civiliteNir": ("nir", "NIR"),
        "prenomNir": ("nir", "NIR"),
        "lieuNaissance": ("nir", "NIR"),
        "dateNaissance": ("nir", "NIR"),
        "departementNaissance": ("nir", "NIR"),
        "ville": ("codePostal", "Code postal"),
        "adresseComplete": ("codePostal", "Code postal"),
    }

    def _get_link_candidates(self, source_sub: str) -> list[dict]:
        """Retourne les champs de la section courante dont le sous-type == source_sub."""
        fm = self.fm
        current_id = self.data.get("id")
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
        return [f for f in src if f.get("subType") == source_sub and f["id"] != current_id]

    def _build_linked_field_section(self, base_type: str, sub_type: str) -> ft.Container:
        """Construit le sélecteur de lien pour un sous-type dépendant."""
        source_sub, group_label = self._LINK_SOURCE_MAP.get(sub_type, ("", ""))
        candidates = self._get_link_candidates(source_sub) if source_sub else []

        current_linked = self.data.get("linkedFieldId", "")

        options = [
            ft.dropdown.Option("", f"Auto (lier au {group_label} de la ligne)"),
            ft.dropdown.Option("__none__", "Indépendant (générer sans lien)"),
        ]
        for c in candidates:
            options.append(ft.dropdown.Option(c["id"], f"→ {c['name']}"))

        # Si la valeur stockée pointe un champ qui n'existe plus, on repasse en auto
        valid_ids = {c["id"] for c in candidates} | {"", "__none__"}
        actual_value = current_linked if current_linked in valid_ids else ""

        icon_color = ft.Colors.ORANGE_300 if source_sub == "nir" else ft.Colors.CYAN_300

        def _on_change(e):
            self._upd("linkedFieldId", e.control.value)

        hint = (
            f"Aucun champ {group_label} disponible dans cette section" if not candidates else None
        )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.LINK, size=14, color=icon_color),
                            ft.Text(
                                f"Lien de cohérence ({group_label})",
                                size=13,
                                weight=ft.FontWeight.W_500,
                            ),
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Dropdown(
                        value=str(actual_value),
                        options=options,
                        hint_text=hint,
                        on_select=_on_change,
                        disabled=not candidates and actual_value == "",
                    ),
                    ft.Text(
                        "« Indépendant » génère ce champ sans tenir compte des autres champs "
                        f"{group_label} de la ligne.",
                        size=11,
                        color=ft.Colors.GREY_600,
                        italic=True,
                    ),
                ],
                spacing=6,
            ),
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.WHITE),
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        )

    # ─── Padding ──────────────────────────────────────────────────────────────

    def _build_padding_section(self) -> ft.Column:
        """Construit le bloc remplissage :
        dropdown position + dropdown caractère (masqué si Aucun).
        """
        current_padding = self.data.get("padding", "none")

        self._paddingchar_dd = ft.Dropdown(
            label="Caractère de remplissage",
            value=str(self.data.get("paddingChar", " ")),
            options=[
                ft.dropdown.Option(" ", "Espace"),
                ft.dropdown.Option("0", "Zéro  (0)"),
            ],
            on_select=lambda e: self._upd("paddingChar", e.control.value),
            expand=True,
        )

        self._paddingchar_row = ft.Row(
            [self._paddingchar_dd],
            visible=(current_padding != "none"),
        )

        def on_padding_change(e):
            val = e.control.value
            self._upd("padding", val)
            if self._paddingchar_row:
                self._paddingchar_row.visible = val != "none"
                try:
                    self._paddingchar_row.update()
                except Exception:
                    logger.debug("Widget update skipped", exc_info=True)

        self._padding_dd = ft.Dropdown(
            label="Remplissage (padding)",
            value=str(current_padding),
            options=[
                ft.dropdown.Option("none", "Aucun"),
                ft.dropdown.Option("before", "Avant"),
                ft.dropdown.Option("after", "Après"),
                ft.dropdown.Option("both", "Des deux côtés"),
            ],
            on_select=on_padding_change,
            expand=True,
        )

        return ft.Column(
            [
                self._padding_dd,
                self._paddingchar_row,
            ],
            spacing=10,
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # Événements
    # ═══════════════════════════════════════════════════════════════════════════

    def _on_base_type_change(self, e) -> None:
        """Change le type de base → réinitialise le sous-type et recharge les options."""
        new_base = e.control.value
        self.data["type"] = new_base
        self.data["subType"] = "none"

        # Appliquer les défauts du nouveau type de base
        for key, val in get_field_defaults(new_base, "none").items():
            self.data[key] = val

        # Reconstruire le dropdown de sous-type et le placer dans le Container
        new_dd = self._build_subtype_dd(new_base, "none")
        self._subtype_dd = new_dd

        if self._subtype_container is not None:
            # Mettre à jour le content du Container qui enveloppe le dropdown
            self._subtype_container.content = new_dd
            # Masquer le conteneur entier pour 'decimal' (pas de sous-types)
            self._subtype_container.visible = new_base != "decimal"
            try:
                self._subtype_container.update()
            except Exception:
                logger.debug("Widget update skipped", exc_info=True)

        self._rebuild_opt_section(new_base, "none")

    def _on_subtype_change(self, e) -> None:
        """Change le sous-type → applique les défauts et recharge les options."""
        new_sub = e.control.value
        base_type = str(self.data.get("type", "alpha"))
        self.data["subType"] = new_sub

        for key, val in get_field_defaults(base_type, new_sub).items():
            self.data[key] = val

        self._rebuild_opt_section(base_type, new_sub)

    def _upd(self, key: str, value) -> None:
        self.data[key] = value

    def _open_concat_editor(self) -> None:
        from views.concat_editor import ConcatEditorDialog

        ConcatEditorDialog(
            self.app,
            self.data,
            self.section,
            self.line_id,
            on_save=self._refresh_concat_count,
        ).open()

    # ═══════════════════════════════════════════════════════════════════════════
    # Sauvegarde
    # ═══════════════════════════════════════════════════════════════════════════

    def _save(self, e) -> None:
        if not str(self.data.get("name", "")).strip():
            self.app.show_snack("⚠️  Le nom du champ est obligatoire.", success=False)
            return

        fm = self.fm

        if self.is_new:
            if self.section == "header":
                fm.header_fields.append(self.data)
            elif self.section == "footer":
                fm.footer_fields.append(self.data)
            elif self.section == "data":
                for line in fm.field_lines:
                    if line["id"] == self.line_id:
                        line["fields"].append(self.data)
                        break
        else:
            self._update_existing()

        self.app.close_dialog()

        if self.on_save:
            self.on_save()
        else:
            self.app.refresh_current_tab()

        self.app.show_snack("✅ Champ créé." if self.is_new else "✅ Champ mis à jour.")

    def _update_existing(self) -> None:
        fm = self.fm
        field_id = self.data["id"]

        def _swap(lst: list) -> bool:
            for i, f in enumerate(lst):
                if f["id"] == field_id:
                    lst[i] = self.data
                    return True
            return False

        if not _swap(fm.header_fields) and not _swap(fm.footer_fields):
            for line in fm.field_lines:
                if _swap(line.get("fields", [])):
                    break
