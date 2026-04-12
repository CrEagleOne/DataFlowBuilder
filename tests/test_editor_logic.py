"""
Tests unitaires — views/editor.py (fonctions logiques pures)
=============================================================
Couvre les fonctions module-level et méthodes pures de ``EditorView``
sans instanciation Flet :

* ``_nest_by_category``          – imbrication JSON par catégorie de champ
* ``EditorView._prepare_export_content`` – transformation données brutes → JSON
* ``_card_section`` / ``_info_badge``    – helpers de construction UI (fumée)
"""

import json
from unittest.mock import MagicMock

from views.editor import _card_section, _info_badge, _nest_by_category

# ── Helpers ───────────────────────────────────────────────────────────────────


def _f(name: str, category: str = "", include: bool = True) -> dict:
    """Fabrique un champ minimal pour les tests.

    Args:
        name: Nom du champ.
        category: Catégorie au format ``xxx.yyy.zzz`` (vide = aucune).
        include: Valeur de ``includeInOutput``.

    Returns:
        dict: Champ minimal.
    """
    return {
        "id": name,
        "name": name,
        "category": category,
        "includeInOutput": include,
    }


def _flat_from_fields(fields: list, values: list | None = None) -> dict:
    """Construit un dict plat ``{nom: valeur}`` depuis une liste de champs.

    Args:
        fields: Champs dont on utilise la clé ``name``.
        values: Valeurs associées dans le même ordre. Si ``None``, utilise
            l'index sous forme de chaîne.

    Returns:
        dict: Dictionnaire plat.
    """
    vals = values or [str(i) for i in range(len(fields))]
    return {f["name"]: v for f, v in zip(fields, vals, strict=False)}


# ══════════════════════════════════════════════════════════════════════════════
# _nest_by_category
# ══════════════════════════════════════════════════════════════════════════════


class TestNestByCategory:
    """Tests de la fonction ``_nest_by_category``."""

    # ── Cas de base ───────────────────────────────────────────────────────────

    def test_empty_inputs_return_empty_dict(self):
        assert _nest_by_category({}, []) == {}

    def test_no_category_returns_flat(self):
        fields = [_f("id"), _f("nom")]
        flat = _flat_from_fields(fields, ["1", "Dupont"])
        result = _nest_by_category(flat, fields)
        assert result == {"id": "1", "nom": "Dupont"}

    def test_empty_category_stays_at_root(self):
        fields = [_f("x", category="")]
        flat = {"x": "val"}
        result = _nest_by_category(flat, fields)
        assert result["x"] == "val"
        assert len(result) == 1

    def test_none_category_treated_as_root(self):
        fields = [{"id": "a", "name": "a", "category": None, "includeInOutput": True}]
        flat = {"a": "hello"}
        result = _nest_by_category(flat, fields)
        assert result["a"] == "hello"

    # ── Niveau 1 ──────────────────────────────────────────────────────────────

    def test_single_level_creates_nested_dict(self):
        fields = [_f("prenom", "personne")]
        flat = {"prenom": "Jean"}
        result = _nest_by_category(flat, fields)
        assert "personne" in result
        assert result["personne"]["prenom"] == "Jean"
        assert "prenom" not in result  # ne doit pas rester à la racine

    def test_two_fields_same_category_in_same_object(self):
        fields = [_f("nom", "personne"), _f("prenom", "personne")]
        flat = {"nom": "Dupont", "prenom": "Jean"}
        result = _nest_by_category(flat, fields)
        assert result["personne"]["nom"] == "Dupont"
        assert result["personne"]["prenom"] == "Jean"

    def test_two_fields_different_level1_categories(self):
        fields = [_f("cp", "adresse"), _f("nom", "personne")]
        flat = {"cp": "75001", "nom": "Dupont"}
        result = _nest_by_category(flat, fields)
        assert "adresse" in result
        assert "personne" in result
        assert result["adresse"]["cp"] == "75001"
        assert result["personne"]["nom"] == "Dupont"

    # ── Niveaux profonds ──────────────────────────────────────────────────────

    def test_two_level_nesting(self):
        fields = [_f("cp", "adresse.contact")]
        flat = {"cp": "75001"}
        result = _nest_by_category(flat, fields)
        assert result["adresse"]["contact"]["cp"] == "75001"

    def test_three_level_nesting(self):
        fields = [_f("val", "a.b.c")]
        flat = {"val": "x"}
        result = _nest_by_category(flat, fields)
        assert result["a"]["b"]["c"]["val"] == "x"

    def test_four_level_nesting(self):
        fields = [_f("deep", "w.x.y.z")]
        flat = {"deep": "42"}
        result = _nest_by_category(flat, fields)
        assert result["w"]["x"]["y"]["z"]["deep"] == "42"

    # ── Mélange racine + catégorisés ──────────────────────────────────────────

    def test_mixed_root_and_nested(self):
        fields = [_f("id", ""), _f("prenom", "personne")]
        flat = {"id": "1", "prenom": "Jean"}
        result = _nest_by_category(flat, fields)
        assert result["id"] == "1"
        assert result["personne"]["prenom"] == "Jean"

    def test_multiple_root_fields_preserved(self):
        fields = [_f("a"), _f("b"), _f("c")]
        flat = {"a": "1", "b": "2", "c": "3"}
        result = _nest_by_category(flat, fields)
        assert result == {"a": "1", "b": "2", "c": "3"}

    # ── Cas limites ───────────────────────────────────────────────────────────

    def test_value_overwrite_when_same_name_same_category(self):
        """Deux champs de même nom dans la même catégorie : le dernier l'emporte."""
        fields = [_f("x", "cat"), _f("x", "cat")]
        flat = {"x": "second"}
        result = _nest_by_category(flat, fields)
        assert result["cat"]["x"] == "second"

    def test_shared_intermediate_node(self):
        """``parent.A`` et ``parent.B`` partagent le nœud ``parent``."""
        fields = [_f("fa", "parent.A"), _f("fb", "parent.B")]
        flat = {"fa": "alpha", "fb": "beta"}
        result = _nest_by_category(flat, fields)
        assert result["parent"]["A"]["fa"] == "alpha"
        assert result["parent"]["B"]["fb"] == "beta"

    def test_empty_string_value_preserved(self):
        fields = [_f("x", "cat")]
        flat = {"x": ""}
        result = _nest_by_category(flat, fields)
        assert result["cat"]["x"] == ""

    def test_numeric_string_value_preserved(self):
        fields = [_f("age", "personne")]
        flat = {"age": "30"}
        result = _nest_by_category(flat, fields)
        assert result["personne"]["age"] == "30"

    def test_field_missing_in_flat_yields_empty_string(self):
        """Si la clé n'est pas dans le dict plat, la valeur doit être ``''``."""
        fields = [_f("ghost", "cat")]
        flat = {}
        result = _nest_by_category(flat, fields)
        assert result["cat"]["ghost"] == ""


# ══════════════════════════════════════════════════════════════════════════════
# EditorView._prepare_export_content
# ══════════════════════════════════════════════════════════════════════════════


def _make_editor(
    fmt: str = "csv",
    cat_keys: bool = False,
    header_fields: list | None = None,
    footer_fields: list | None = None,
    field_lines: list | None = None,
    num_rows: int = 2,
    delimiter: str = ",",
):
    """Construit un ``EditorView`` avec un ``FlowManager`` mocké.

    Args:
        fmt: Format de sortie (``'csv'``, ``'json'``…).
        cat_keys: Valeur de ``categoriesAsJsonKeys``.
        header_fields: Champs d'en-tête (list de dicts).
        footer_fields: Champs de pied de page (list de dicts).
        field_lines: Lignes de données (list de ``{id, fields}``).
        num_rows: Nombre de lignes de données.
        delimiter: Délimiteur de colonnes.

    Returns:
        EditorView: Instance partiellement mockée, prête pour ``_prepare_export_content``.
    """
    from views.editor import EditorView

    mock_app = MagicMock()
    editor = EditorView(mock_app)

    fm = MagicMock()
    fm.current_flow = {
        "format": fmt,
        "categoriesAsJsonKeys": cat_keys,
        "numRows": num_rows,
        "delimiter": delimiter,
        "encoding": "UTF-8",
    }
    fm.header_fields = header_fields or []
    fm.footer_fields = footer_fields or []
    fm.field_lines = field_lines or []

    editor.fm = fm
    return editor


class TestPrepareExportContentNonJson:
    """Format non-JSON : texte retourné tel quel."""

    def test_csv_passthrough(self):
        editor = _make_editor(fmt="csv")
        raw = "col1,col2\nval1,val2"
        assert editor._prepare_export_content(raw, "csv") == raw

    def test_fixed_passthrough(self):
        editor = _make_editor(fmt="fixed")
        raw = "ABCDE12345"
        assert editor._prepare_export_content(raw, "fixed") == raw

    def test_xml_passthrough(self):
        editor = _make_editor(fmt="xml")
        raw = "<root><item>1</item></root>"
        assert editor._prepare_export_content(raw, "xml") == raw


class TestPrepareExportContentJson:
    """Format JSON sans option catégories (sortie tableau plat)."""

    def _run(self, raw: str, fields: list, **kw) -> list:
        """Exécute ``_prepare_export_content`` et retourne le JSON parsé.

        Args:
            raw: Données CSV brutes.
            fields: Champs inclus dans la sortie (section données).
            **kw: Paramètres supplémentaires pour ``_make_editor``.

        Returns:
            list: Liste d'objets JSON parsés.
        """
        line = {"id": "line1", "fields": fields}
        num_rows = kw.pop("num_rows", len(raw.splitlines()))
        editor = _make_editor(fmt="json", field_lines=[line], num_rows=num_rows, **kw)
        result = editor._prepare_export_content(raw, "json")
        return list(json.loads(result))

    def test_returns_valid_json(self):
        fields = [_f("col1"), _f("col2")]
        raw = "a,b\nc,d"
        editor = _make_editor(fmt="json", field_lines=[{"id": "l", "fields": fields}], num_rows=2)
        result = editor._prepare_export_content(raw, "json")
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    def test_field_names_as_keys(self):
        fields = [_f("nom"), _f("prenom")]
        raw = "Dupont,Jean"
        parsed = self._run(raw, fields, num_rows=1)
        assert len(parsed) == 1
        assert parsed[0]["nom"] == "Dupont"
        assert parsed[0]["prenom"] == "Jean"

    def test_multiple_rows(self):
        fields = [_f("x"), _f("y")]
        raw = "1,2\n3,4"
        parsed = self._run(raw, fields, num_rows=2)
        assert len(parsed) == 2

    def test_missing_value_becomes_empty_string(self):
        """Si la ligne CSV est plus courte que les champs, la valeur vaut ``''``."""
        fields = [_f("a"), _f("b"), _f("c")]
        raw = "1,2"  # 3 champs, seulement 2 valeurs
        parsed = self._run(raw, fields, num_rows=1)
        assert parsed[0]["c"] == ""

    def test_header_row_included(self):
        header = [_f("entete1")]
        editor = _make_editor(
            fmt="json",
            header_fields=header,
            field_lines=[],
            num_rows=0,
        )
        raw = "valeur_entete"
        parsed = json.loads(editor._prepare_export_content(raw, "json"))
        assert len(parsed) == 1
        assert parsed[0]["entete1"] == "valeur_entete"

    def test_footer_row_included(self):
        footer = [_f("total")]
        editor = _make_editor(
            fmt="json",
            footer_fields=footer,
            field_lines=[],
            num_rows=0,
        )
        raw = "999"
        parsed = json.loads(editor._prepare_export_content(raw, "json"))
        assert any("total" in row for row in parsed)

    def test_non_included_fields_excluded(self):
        """Les champs avec ``includeInOutput=False`` ne doivent pas apparaître."""
        fields = [_f("visible", include=True), _f("cache", include=False)]
        # Seul le champ visible contribue à la ligne CSV
        raw = "hello"
        line = {"id": "l", "fields": fields}
        editor = _make_editor(fmt="json", field_lines=[line], num_rows=1)
        parsed = json.loads(editor._prepare_export_content(raw, "json"))
        if parsed:
            assert "visible" in parsed[0]
            assert "cache" not in parsed[0]


class TestPrepareExportContentJsonWithCatKeys:
    """Format JSON avec option ``categoriesAsJsonKeys=True``."""

    def _run_cat(self, raw: str, fields: list, num_rows: int = 1) -> list:
        """Exécute ``_prepare_export_content`` avec catégories imbriquées.

        Args:
            raw: Données CSV brutes.
            fields: Champs avec leurs catégories.
            num_rows: Nombre de lignes de données.

        Returns:
            list: JSON parsé.
        """
        line = {"id": "l", "fields": fields}
        editor = _make_editor(fmt="json", cat_keys=True, field_lines=[line], num_rows=num_rows)
        return list(json.loads(editor._prepare_export_content(raw, "json")))

    def test_flat_field_stays_at_root(self):
        fields = [_f("id", "")]
        raw = "123"
        parsed = self._run_cat(raw, fields)
        assert parsed[0]["id"] == "123"

    def test_categorized_field_nested(self):
        fields = [_f("prenom", "personne")]
        raw = "Jean"
        parsed = self._run_cat(raw, fields)
        assert parsed[0]["personne"]["prenom"] == "Jean"

    def test_deep_nesting(self):
        fields = [_f("cp", "adresse.geo")]
        raw = "75001"
        parsed = self._run_cat(raw, fields)
        assert parsed[0]["adresse"]["geo"]["cp"] == "75001"

    def test_multiple_fields_same_category(self):
        fields = [_f("nom", "personne"), _f("age", "personne")]
        raw = "Dupont,30"
        parsed = self._run_cat(raw, fields)
        assert parsed[0]["personne"]["nom"] == "Dupont"
        assert parsed[0]["personne"]["age"] == "30"

    def test_mixed_root_and_nested(self):
        fields = [_f("id", ""), _f("nom", "personne")]
        raw = "1,Dupont"
        parsed = self._run_cat(raw, fields)
        assert parsed[0]["id"] == "1"
        assert parsed[0]["personne"]["nom"] == "Dupont"

    def test_cat_keys_false_stays_flat(self):
        """Quand l'option est désactivée, les catégories n'imbriquent pas le JSON."""
        fields = [_f("prenom", "personne")]
        raw = "Jean"
        line = {"id": "l", "fields": fields}
        editor = _make_editor(fmt="json", cat_keys=False, field_lines=[line], num_rows=1)
        parsed = json.loads(editor._prepare_export_content(raw, "json"))
        assert parsed[0]["prenom"] == "Jean"
        assert "personne" not in parsed[0]


# ══════════════════════════════════════════════════════════════════════════════
# Helpers UI (_card_section, _info_badge) — tests de fumée
# ══════════════════════════════════════════════════════════════════════════════


class TestCardSection:
    """Vérifie que ``_card_section`` retourne un objet Flet sans lever d'exception."""

    def test_returns_card_object(self):
        import flet as ft

        card = _card_section("Mon titre", [ft.Text("contenu")])
        assert card is not None

    def test_title_in_content(self):

        card = _card_section("Titre test", [])
        # On vérifie que l'objet possède une propriété content (ft.Card)
        assert hasattr(card, "content")

    def test_empty_controls_no_error(self):
        card = _card_section("Vide", [])
        assert card is not None


class TestInfoBadge:
    """Vérifie que ``_info_badge`` retourne un objet Flet sans lever d'exception."""

    def test_returns_container(self):
        import flet as ft

        badge = _info_badge("JSON", ft.Colors.BLUE_400)
        assert badge is not None

    def test_content_has_text(self):
        import flet as ft

        badge = _info_badge("CSV", ft.Colors.GREEN_400)
        assert hasattr(badge, "content")
