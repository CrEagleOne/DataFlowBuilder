"""
Tests unitaires — views/components.py (fonctions logiques pures)
=================================================================
Couvre les fonctions module-level sans dépendance à Flet :

* ``_build_fields_tree``    – construction de l'arbre de catégories
* ``_count_fields_in_node`` – comptage récursif des champs d'un nœud
* ``_badge_label``          – libellé du badge type/sous-type
"""

from collections import OrderedDict

from views.components import (
    _badge_label,
    _build_fields_tree,
    _count_fields_in_node,
)

# ── Helpers de fabrication de champs ─────────────────────────────────────────


def _field(
    fid: str, name: str, category: str = "", ftype: str = "alpha", sub: str = "none"
) -> dict:
    """Fabrique un champ minimal pour les tests.

    Args:
        fid: Identifiant unique du champ.
        name: Nom du champ.
        category: Catégorie au format ``xxx.yyy.zzz`` (vide = aucune).
        ftype: Type de base (``'alpha'``, ``'num'``…).
        sub: Sous-type (``'none'``, ``'email'``…).

    Returns:
        dict: Dictionnaire de champ minimal.
    """
    return {"id": fid, "name": name, "category": category, "type": ftype, "subType": sub}


# ══════════════════════════════════════════════════════════════════════════════
# _build_fields_tree
# ══════════════════════════════════════════════════════════════════════════════


class TestBuildFieldsTree:
    """Tests de ``_build_fields_tree``."""

    # ── Structure de base ─────────────────────────────────────────────────────

    def test_empty_list_returns_empty_root(self):
        tree = _build_fields_tree([])
        assert tree["_fields"] == []
        assert tree["_children"] == {} or tree["_children"] == OrderedDict()

    def test_root_keys_always_present(self):
        tree = _build_fields_tree([])
        assert "_fields" in tree
        assert "_children" in tree

    # ── Champs sans catégorie ─────────────────────────────────────────────────

    def test_no_category_goes_to_root_fields(self):
        fields = [_field("1", "a", category="")]
        tree = _build_fields_tree(fields)
        assert len(tree["_fields"]) == 1
        assert tree["_fields"][0]["id"] == "1"

    def test_none_category_treated_as_root(self):
        fields = [{"id": "1", "name": "x", "category": None}]
        tree = _build_fields_tree(fields)
        assert len(tree["_fields"]) == 1

    def test_whitespace_category_treated_as_root(self):
        fields = [_field("1", "a", category="   ")]
        tree = _build_fields_tree(fields)
        assert len(tree["_fields"]) == 1
        assert not tree["_children"]

    def test_multiple_root_fields(self):
        fields = [_field(str(i), f"f{i}") for i in range(5)]
        tree = _build_fields_tree(fields)
        assert len(tree["_fields"]) == 5
        assert not tree["_children"]

    # ── Catégorie niveau 1 ────────────────────────────────────────────────────

    def test_single_level_category_creates_child(self):
        fields = [_field("1", "a", "section")]
        tree = _build_fields_tree(fields)
        assert "section" in tree["_children"]

    def test_single_level_field_placed_correctly(self):
        fields = [_field("1", "a", "section")]
        tree = _build_fields_tree(fields)
        node = tree["_children"]["section"]
        assert len(node["_fields"]) == 1
        assert node["_fields"][0]["id"] == "1"

    def test_single_level_has_no_children(self):
        fields = [_field("1", "a", "section")]
        tree = _build_fields_tree(fields)
        assert not tree["_children"]["section"]["_children"]

    # ── Catégorie niveau 2 ────────────────────────────────────────────────────

    def test_two_level_category(self):
        fields = [_field("1", "a", "parent.child")]
        tree = _build_fields_tree(fields)
        assert "parent" in tree["_children"]
        parent_node = tree["_children"]["parent"]
        assert "child" in parent_node["_children"]

    def test_two_level_field_in_leaf(self):
        fields = [_field("1", "a", "parent.child")]
        tree = _build_fields_tree(fields)
        leaf = tree["_children"]["parent"]["_children"]["child"]
        assert len(leaf["_fields"]) == 1

    # ── Catégorie profonde ────────────────────────────────────────────────────

    def test_three_level_category(self):
        fields = [_field("1", "a", "a.b.c")]
        tree = _build_fields_tree(fields)
        assert "a" in tree["_children"]
        assert "b" in tree["_children"]["a"]["_children"]
        assert "c" in tree["_children"]["a"]["_children"]["b"]["_children"]

    def test_four_level_category(self):
        fields = [_field("1", "a", "w.x.y.z")]
        tree = _build_fields_tree(fields)
        node = tree["_children"]["w"]["_children"]["x"]["_children"]["y"]["_children"]["z"]
        assert len(node["_fields"]) == 1

    def test_deep_field_placed_at_leaf(self):
        fields = [_field("42", "deep", "a.b.c")]
        tree = _build_fields_tree(fields)
        leaf = tree["_children"]["a"]["_children"]["b"]["_children"]["c"]
        assert leaf["_fields"][0]["id"] == "42"

    # ── Regroupement de champs ────────────────────────────────────────────────

    def test_two_fields_same_category_grouped(self):
        fields = [_field("1", "x", "cat"), _field("2", "y", "cat")]
        tree = _build_fields_tree(fields)
        assert len(tree["_children"]["cat"]["_fields"]) == 2

    def test_two_fields_different_categories_separated(self):
        fields = [_field("1", "x", "catA"), _field("2", "y", "catB")]
        tree = _build_fields_tree(fields)
        assert "catA" in tree["_children"]
        assert "catB" in tree["_children"]
        assert len(tree["_children"]["catA"]["_fields"]) == 1
        assert len(tree["_children"]["catB"]["_fields"]) == 1

    # ── Mélange racine + catégorisés ──────────────────────────────────────────

    def test_mixed_root_and_categorized(self):
        fields = [_field("1", "root"), _field("2", "cat", "section")]
        tree = _build_fields_tree(fields)
        assert len(tree["_fields"]) == 1
        assert "section" in tree["_children"]

    def test_mixed_preserves_order_in_root(self):
        fields = [_field("1", "first"), _field("2", "second"), _field("3", "third")]
        tree = _build_fields_tree(fields)
        ids = [f["id"] for f in tree["_fields"]]
        assert ids == ["1", "2", "3"]

    # ── Cas limites ───────────────────────────────────────────────────────────

    def test_category_with_empty_parts_handled(self):
        """Un point seul ou des points doubles ne doivent pas lever d'exception."""
        fields = [_field("1", "a", "a..b")]
        # Le parser filtre les parties vides via ``if p.strip()``
        tree = _build_fields_tree(fields)
        # "a" et "b" existent, la partie vide est ignorée
        assert "a" in tree["_children"]

    def test_many_fields_many_categories(self):
        fields = [_field(str(i), f"f{i}", f"cat{i}") for i in range(20)]
        tree = _build_fields_tree(fields)
        assert len(tree["_children"]) == 20

    def test_shared_intermediate_nodes(self):
        """Deux catégories ``parent.A`` et ``parent.B`` partagent ``parent``."""
        fields = [_field("1", "a", "parent.A"), _field("2", "b", "parent.B")]
        tree = _build_fields_tree(fields)
        parent = tree["_children"]["parent"]
        assert "A" in parent["_children"]
        assert "B" in parent["_children"]
        assert not parent["_fields"]  # rien directement sous parent


# ══════════════════════════════════════════════════════════════════════════════
# _count_fields_in_node
# ══════════════════════════════════════════════════════════════════════════════


class TestCountFieldsInNode:
    """Tests de ``_count_fields_in_node``."""

    def _node(self, direct: int, *children_counts) -> dict:
        """Construit un nœud artificiel avec ``direct`` champs directs
        et des nœuds enfants ayant chacun un nombre fixe de champs directs.

        Args:
            direct: Nombre de champs directement dans le nœud.
            *children_counts: Nombre de champs pour chaque enfant.

        Returns:
            dict: Nœud prêt à passer à ``_count_fields_in_node``.
        """
        children = {}
        for i, cnt in enumerate(children_counts):
            children[f"child_{i}"] = {"_fields": [None] * cnt, "_children": {}}
        return {"_fields": [None] * direct, "_children": children}

    def test_empty_node_returns_zero(self):
        assert _count_fields_in_node(self._node(0)) == 0

    def test_only_direct_fields(self):
        assert _count_fields_in_node(self._node(5)) == 5

    def test_only_children(self):
        node = self._node(0, 3, 2)
        assert _count_fields_in_node(node) == 5

    def test_direct_plus_children(self):
        node = self._node(2, 3)
        assert _count_fields_in_node(node) == 5

    def test_deeply_nested(self):
        inner = {"_fields": [None, None], "_children": {}}
        mid = {"_fields": [None], "_children": {"inner": inner}}
        root = {"_fields": [], "_children": {"mid": mid}}
        assert _count_fields_in_node(root) == 3

    def test_multiple_children_at_same_level(self):
        node = self._node(1, 2, 3, 4)
        assert _count_fields_in_node(node) == 10

    def test_consistency_with_build_tree(self):
        """Le comptage doit être cohérent avec un arbre issu de ``_build_fields_tree``."""
        fields = [_field(str(i), f"f{i}", "a" if i < 3 else "b") for i in range(6)]
        tree = _build_fields_tree(fields)
        # 3 dans "a", 3 dans "b"
        assert _count_fields_in_node(tree["_children"]["a"]) == 3
        assert _count_fields_in_node(tree["_children"]["b"]) == 3
        assert _count_fields_in_node(tree) == 6


# ══════════════════════════════════════════════════════════════════════════════
# _badge_label
# ══════════════════════════════════════════════════════════════════════════════


class TestBadgeLabel:
    """Tests de ``_badge_label``."""

    def test_alpha_none_returns_base_only(self):
        field = {"type": "alpha", "subType": "none"}
        assert _badge_label(field) == "alpha"

    def test_alpha_email_returns_combined(self):
        field = {"type": "alpha", "subType": "email"}
        assert _badge_label(field) == "alpha:email"

    def test_num_nir(self):
        field = {"type": "num", "subType": "nir"}
        assert _badge_label(field) == "num:NIR"

    def test_num_iban(self):
        field = {"type": "alpha", "subType": "iban"}
        assert _badge_label(field) == "alpha:IBAN"

    def test_date_none_returns_date_only(self):
        field = {"type": "date", "subType": "none"}
        assert _badge_label(field) == "date"

    def test_bool_on_returns_on_label(self):
        field = {"type": "bool", "subType": "ON"}
        assert _badge_label(field) == "bool:O/N"

    def test_missing_subtype_key_defaults_to_none(self):
        field = {"type": "num"}
        # subType absent → sub = None → "none"
        assert _badge_label(field) == "num"

    def test_unknown_subtype_uses_raw_value(self):
        """Un sous-type inconnu doit afficher sa valeur brute."""
        field = {"type": "alpha", "subType": "unknown_sub"}
        label = _badge_label(field)
        assert "unknown_sub" in label

    def test_concat_subtype(self):
        field = {"type": "alpha", "subType": "concat"}
        assert _badge_label(field) == "alpha:concat"

    def test_decimal_none(self):
        field = {"type": "decimal", "subType": "none"}
        assert _badge_label(field) == "decimal"
