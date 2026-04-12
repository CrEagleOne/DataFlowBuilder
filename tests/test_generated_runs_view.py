"""
Tests unitaires — views/generated_runs_view.py
===============================================
Couvre les fonctions pures et la logique métier de la vue :

* ``_fmt_size``                           – formatage de taille
* ``GeneratedRunsView._load_groups``      – chargement, filtrage, tri
* ``GeneratedRunsView._sort_runs``        – critères de tri
* ``GeneratedRunsView._confirm_delete_file``  – suppression fichier
* ``GeneratedRunsView._confirm_delete_group`` – suppression groupe
* ``GeneratedRunsView._copy_path``        – copie chemin
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock

from views.generated_runs_view import GeneratedRunsView, _fmt_size

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_run(name: str, size: int = 100, modified: str = "2026-01-01 12:00:00") -> dict:
    """Fabrique un dict de run minimal.

    Args:
        name: Nom de fichier (avec extension).
        size: Taille en octets.
        modified: Horodatage de modification au format ``YYYY-MM-DD HH:MM:SS``.

    Returns:
        dict: Run minimal ``{name, path, size, modified}``.
    """
    return {"name": name, "path": f"/fake/{name}", "size": size, "modified": modified}


def _make_view(tmp_path, flows: dict[str, list[dict]] | None = None) -> GeneratedRunsView:
    """Construit une instance de ``GeneratedRunsView`` avec un storage mocké.

    Args:
        tmp_path: Répertoire temporaire pytest fourni comme ``generated_dir``.
        flows: Mapping ``{flow_name: [runs]}`` pré-chargé dans
            ``storage.list_generated_runs``.

    Returns:
        GeneratedRunsView: Instance avec ``app`` et ``storage`` mockés.
    """
    mock_app = MagicMock()
    mock_app.page.set_clipboard = MagicMock()

    storage = MagicMock()
    storage.generated_dir = str(tmp_path)

    flows = flows or {}

    def _list_runs(folder_name):
        return flows.get(folder_name, [])

    def _get_folder(flow_name):
        return os.path.join(str(tmp_path), flow_name)

    storage.list_generated_runs.side_effect = _list_runs
    storage.get_generated_folder.side_effect = _get_folder

    # Créer les sous-dossiers pour que os.listdir fonctionne
    for folder_name in flows:
        os.makedirs(os.path.join(str(tmp_path), folder_name), exist_ok=True)

    mock_fm = MagicMock()
    mock_fm.storage = storage
    mock_app.flow_manager = mock_fm

    view = GeneratedRunsView(mock_app)
    return view


# ══════════════════════════════════════════════════════════════════════════════
# _fmt_size
# ══════════════════════════════════════════════════════════════════════════════


class TestFmtSize:
    """Tests de la fonction ``_fmt_size``."""

    def test_zero_bytes(self):
        assert _fmt_size(0) == "0 o"

    def test_small_bytes(self):
        assert _fmt_size(500) == "500 o"

    def test_exactly_1024_is_ko(self):
        result = _fmt_size(1024)
        assert "Ko" in result

    def test_kilobytes(self):
        result = _fmt_size(2048)
        assert "Ko" in result
        assert "2.0" in result

    def test_megabytes(self):
        result = _fmt_size(1024 * 1024)
        assert "Mo" in result
        assert "1.00" in result

    def test_large_file(self):
        result = _fmt_size(5 * 1024 * 1024)
        assert "Mo" in result

    def test_returns_string(self):
        assert isinstance(_fmt_size(100), str)

    def test_just_under_1024(self):
        result = _fmt_size(1023)
        assert "o" in result
        assert "Ko" not in result


# ══════════════════════════════════════════════════════════════════════════════
# _sort_runs
# ══════════════════════════════════════════════════════════════════════════════


class TestSortRuns:
    """Tests de ``GeneratedRunsView._sort_runs``."""

    RUNS = [
        _make_run("c.csv", size=300, modified="2026-03-01 10:00:00"),
        _make_run("a.csv", size=100, modified="2026-01-01 10:00:00"),
        _make_run("b.csv", size=200, modified="2026-02-01 10:00:00"),
    ]

    def _view_with_sort(self, sort_key: str, tmp_path) -> GeneratedRunsView:
        v = _make_view(tmp_path)
        v._sort_key = sort_key
        return v

    def test_sort_recent_most_recent_first(self, tmp_path):
        v = self._view_with_sort("recent", tmp_path)
        sorted_runs = v._sort_runs(list(self.RUNS))
        assert sorted_runs[0]["modified"] == "2026-03-01 10:00:00"

    def test_sort_oldest_oldest_first(self, tmp_path):
        v = self._view_with_sort("oldest", tmp_path)
        sorted_runs = v._sort_runs(list(self.RUNS))
        assert sorted_runs[0]["modified"] == "2026-01-01 10:00:00"

    def test_sort_name_alphabetical(self, tmp_path):
        v = self._view_with_sort("name", tmp_path)
        sorted_runs = v._sort_runs(list(self.RUNS))
        names = [r["name"] for r in sorted_runs]
        assert names == sorted(names, key=str.lower)

    def test_sort_size_largest_first(self, tmp_path):
        v = self._view_with_sort("size", tmp_path)
        sorted_runs = v._sort_runs(list(self.RUNS))
        assert sorted_runs[0]["size"] == 300

    def test_unknown_sort_key_returns_unchanged(self, tmp_path):
        v = self._view_with_sort("unknown_key", tmp_path)
        original = list(self.RUNS)
        result = v._sort_runs(original)
        assert result == original

    def test_sort_empty_list(self, tmp_path):
        v = self._view_with_sort("recent", tmp_path)
        assert v._sort_runs([]) == []

    def test_sort_single_element(self, tmp_path):
        v = self._view_with_sort("size", tmp_path)
        run = _make_run("x.csv")
        assert v._sort_runs([run]) == [run]


# ══════════════════════════════════════════════════════════════════════════════
# _load_groups
# ══════════════════════════════════════════════════════════════════════════════


class TestLoadGroups:
    """Tests de ``GeneratedRunsView._load_groups``."""

    def test_empty_generated_dir_returns_empty(self, tmp_path):
        v = _make_view(tmp_path, flows={})
        assert v._load_groups() == []

    def test_single_flow_single_file(self, tmp_path):
        flows = {"FluxA": [_make_run("run1.csv")]}
        v = _make_view(tmp_path, flows=flows)
        groups = v._load_groups()
        assert len(groups) == 1
        assert groups[0][0] == "FluxA"
        assert len(groups[0][1]) == 1

    def test_multiple_flows(self, tmp_path):
        flows = {
            "FluxA": [_make_run("a.csv")],
            "FluxB": [_make_run("b.json")],
        }
        v = _make_view(tmp_path, flows=flows)
        groups = v._load_groups()
        assert len(groups) == 2

    def test_groups_sorted_alphabetically(self, tmp_path):
        flows = {
            "Zeta": [_make_run("z.csv")],
            "Alpha": [_make_run("a.csv")],
            "Mu": [_make_run("m.csv")],
        }
        v = _make_view(tmp_path, flows=flows)
        names = [g[0] for g in v._load_groups()]
        assert names == sorted(names)

    def test_search_filters_by_flow_name(self, tmp_path):
        flows = {
            "ClientFlux": [_make_run("c.csv")],
            "CommandeFlux": [_make_run("cmd.csv")],
            "Autre": [_make_run("a.csv")],
        }
        v = _make_view(tmp_path, flows=flows)
        v._search_query = "flux"
        groups = v._load_groups()
        names = [g[0] for g in groups]
        assert "Autre" not in names
        assert "ClientFlux" in names
        assert "CommandeFlux" in names

    def test_search_filters_by_file_name(self, tmp_path):
        flows = {
            "Flux": [
                _make_run("export_prod.csv"),
                _make_run("export_test.csv"),
                _make_run("rapport.csv"),
            ]
        }
        v = _make_view(tmp_path, flows=flows)
        v._search_query = "prod"
        groups = v._load_groups()
        assert len(groups) == 1
        assert len(groups[0][1]) == 1
        assert groups[0][1][0]["name"] == "export_prod.csv"

    def test_search_case_insensitive(self, tmp_path):
        flows = {"MonFlux": [_make_run("fichier.CSV")]}
        v = _make_view(tmp_path, flows=flows)
        v._search_query = "MONFLUX"
        groups = v._load_groups()
        assert len(groups) == 1

    def test_empty_search_returns_all(self, tmp_path):
        flows = {"A": [_make_run("a.csv")], "B": [_make_run("b.csv")]}
        v = _make_view(tmp_path, flows=flows)
        v._search_query = ""
        groups = v._load_groups()
        assert len(groups) == 2

    def test_flow_with_no_files_excluded(self, tmp_path):
        """Un dossier vide (aucun run) ne doit pas apparaître dans les groupes."""
        flows = {"FluxVide": [], "FluxPlein": [_make_run("x.csv")]}
        v = _make_view(tmp_path, flows=flows)
        groups = v._load_groups()
        names = [g[0] for g in groups]
        assert "FluxVide" not in names
        assert "FluxPlein" in names

    def test_nondir_entries_ignored(self, tmp_path):
        """Un fichier à la racine de generated/ ne doit pas lever d'erreur."""
        fake_file = tmp_path / "not_a_folder.txt"
        fake_file.write_text("data")
        v = _make_view(tmp_path, flows={})
        assert v._load_groups() == []

    def test_search_no_match_returns_empty(self, tmp_path):
        flows = {"FluxA": [_make_run("a.csv")]}
        v = _make_view(tmp_path, flows=flows)
        v._search_query = "zzznomatch"
        assert v._load_groups() == []

    def test_runs_in_group_are_sorted(self, tmp_path):
        """Les fichiers dans chaque groupe sont triés selon ``_sort_key``."""
        runs = [
            _make_run("z.csv", modified="2026-03-01 00:00:00"),
            _make_run("a.csv", modified="2026-01-01 00:00:00"),
        ]
        flows = {"Flux": runs}
        v = _make_view(tmp_path, flows=flows)
        v._sort_key = "recent"
        groups = v._load_groups()
        sorted_names = [r["name"] for r in groups[0][1]]
        assert sorted_names[0] == "z.csv"


# ══════════════════════════════════════════════════════════════════════════════
# _copy_path
# ══════════════════════════════════════════════════════════════════════════════


class TestCopyPath:
    """Tests de ``GeneratedRunsView._copy_path``."""

    def test_calls_set_clipboard(self, tmp_path):
        v = _make_view(tmp_path)
        v._copy_path("/some/path/file.csv")
        v.app.page.set_clipboard.assert_called_once_with("/some/path/file.csv")

    def test_shows_snack_on_success(self, tmp_path):
        v = _make_view(tmp_path)
        v._copy_path("/some/path/file.csv")
        v.app.show_snack.assert_called_once()
        args = v.app.show_snack.call_args[0]
        assert "/some/path/file.csv" in args[0]

    def test_clipboard_error_shows_failure_snack(self, tmp_path):
        v = _make_view(tmp_path)
        v.app.page.set_clipboard.side_effect = Exception("clipboard error")
        v._copy_path("/bad/path")
        v.app.show_snack.assert_called_once()
        # success=False doit être passé
        kwargs = v.app.show_snack.call_args[1]
        assert kwargs.get("success") is False


# ══════════════════════════════════════════════════════════════════════════════
# _confirm_delete_file
# ══════════════════════════════════════════════════════════════════════════════


class TestConfirmDeleteFile:
    """Tests de ``GeneratedRunsView._confirm_delete_file``."""

    def test_calls_app_confirm(self, tmp_path):
        v = _make_view(tmp_path)
        run = _make_run("file.csv")
        v._confirm_delete_file(run, "Flux")
        v.app.confirm.assert_called_once()

    def test_confirm_title_and_body_mention_filename(self, tmp_path):
        v = _make_view(tmp_path)
        run = _make_run("important.csv")
        v._confirm_delete_file(run, "Flux")
        call_kwargs = v.app.confirm.call_args[1]
        body_or_args = (
            v.app.confirm.call_args[0][1]
            if len(v.app.confirm.call_args[0]) > 1
            else call_kwargs.get("body", "")
        )
        assert "important.csv" in body_or_args

    def test_on_confirm_removes_file(self, tmp_path):
        """Le callback ``on_confirm`` doit appeler ``os.remove`` sur le chemin."""
        real_file = tmp_path / "to_delete.csv"
        real_file.write_text("data")
        run = {"name": "to_delete.csv", "path": str(real_file), "size": 4, "modified": ""}

        v = _make_view(tmp_path)
        v._confirm_delete_file(run, "Flux")

        # Récupère le callable on_confirm passé à app.confirm
        on_confirm = v.app.confirm.call_args[1].get("on_confirm") or v.app.confirm.call_args[0][2]
        on_confirm()

        assert not real_file.exists()

    def test_on_confirm_shows_snack(self, tmp_path):
        real_file = tmp_path / "file.csv"
        real_file.write_text("x")
        run = {"name": "file.csv", "path": str(real_file), "size": 1, "modified": ""}

        v = _make_view(tmp_path)
        v._confirm_delete_file(run, "Flux")

        on_confirm = v.app.confirm.call_args[1].get("on_confirm") or v.app.confirm.call_args[0][2]
        on_confirm()

        v.app.show_snack.assert_called()

    def test_on_confirm_handles_missing_file_gracefully(self, tmp_path):
        """Si le fichier a déjà été supprimé, le callback ne doit pas planter."""
        run = _make_run("ghost.csv")
        run["path"] = str(tmp_path / "ghost.csv")  # n'existe pas

        v = _make_view(tmp_path)
        v._confirm_delete_file(run, "Flux")
        on_confirm = v.app.confirm.call_args[1].get("on_confirm") or v.app.confirm.call_args[0][2]
        # Ne doit pas lever d'exception
        on_confirm()
        v.app.show_snack.assert_called()


# ══════════════════════════════════════════════════════════════════════════════
# _confirm_delete_group
# ══════════════════════════════════════════════════════════════════════════════


class TestConfirmDeleteGroup:
    """Tests de ``GeneratedRunsView._confirm_delete_group``."""

    def test_calls_app_confirm(self, tmp_path):
        flows = {"Flux": [_make_run("a.csv"), _make_run("b.csv")]}
        v = _make_view(tmp_path, flows=flows)
        v._confirm_delete_group("Flux")
        v.app.confirm.assert_called_once()

    def test_body_mentions_count(self, tmp_path):
        flows = {"Flux": [_make_run("a.csv"), _make_run("b.csv"), _make_run("c.csv")]}
        v = _make_view(tmp_path, flows=flows)
        v._confirm_delete_group("Flux")
        call_args = v.app.confirm.call_args[0]
        body = call_args[1] if len(call_args) > 1 else v.app.confirm.call_args[1].get("body", "")
        assert "3" in body

    def test_on_confirm_deletes_all_files(self, tmp_path):
        """Le callback doit supprimer tous les fichiers du groupe."""
        file_a = tmp_path / "a.csv"
        file_b = tmp_path / "b.csv"
        file_a.write_text("x")
        file_b.write_text("y")

        runs = [
            {"name": "a.csv", "path": str(file_a), "size": 1, "modified": ""},
            {"name": "b.csv", "path": str(file_b), "size": 1, "modified": ""},
        ]
        flows = {"Flux": runs}
        v = _make_view(tmp_path, flows=flows)
        v._confirm_delete_group("Flux")

        on_confirm = v.app.confirm.call_args[1].get("on_confirm") or v.app.confirm.call_args[0][2]
        on_confirm()

        assert not file_a.exists()
        assert not file_b.exists()

    def test_on_confirm_partial_errors_show_failure_snack(self, tmp_path):
        """Si certains fichiers échouent à être supprimés, un snack d'erreur
        doit être affiché."""
        real_file = tmp_path / "real.csv"
        real_file.write_text("x")

        runs = [
            {"name": "real.csv", "path": str(real_file), "size": 1, "modified": ""},
            {"name": "ghost.csv", "path": str(tmp_path / "ghost.csv"), "size": 1, "modified": ""},
        ]
        flows = {"Flux": runs}
        v = _make_view(tmp_path, flows=flows)
        v._confirm_delete_group("Flux")

        on_confirm = v.app.confirm.call_args[1].get("on_confirm") or v.app.confirm.call_args[0][2]
        on_confirm()

        v.app.show_snack.assert_called()
        kwargs = v.app.show_snack.call_args[1]
        assert kwargs.get("success") is False

    def test_on_confirm_all_success_shows_success_snack(self, tmp_path):
        real_file = tmp_path / "ok.csv"
        real_file.write_text("x")
        runs = [{"name": "ok.csv", "path": str(real_file), "size": 1, "modified": ""}]
        flows = {"Flux": runs}
        v = _make_view(tmp_path, flows=flows)
        v._confirm_delete_group("Flux")

        on_confirm = v.app.confirm.call_args[1].get("on_confirm") or v.app.confirm.call_args[0][2]
        on_confirm()

        # Doit avoir success=True (valeur par défaut, kwargs vide ou success=True)
        call_kwargs = v.app.show_snack.call_args[1]
        assert call_kwargs.get("success", True) is True
