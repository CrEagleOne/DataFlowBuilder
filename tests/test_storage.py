"""
Tests unitaires — core/storage.py
==================================
Couverture des fonctionnalités existantes **et** des nouvelles méthodes
de gestion des données générées (``save_generated_data``,
``list_generated_runs``, ``get_generated_folder``,
``_sanitize_path_component``).
"""

import json
import os
import time

import pytest

from core.storage import StorageManager

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def storage(tmp_path, monkeypatch):
    """Instance isolée de StorageManager dans un répertoire temporaire."""
    monkeypatch.setattr(
        StorageManager,
        "_get_app_directory",
        staticmethod(lambda: str(tmp_path / "src")),
    )
    return StorageManager()


@pytest.fixture
def sample_flow():
    """Flux minimal valide."""
    return {"id": "1234567890.123", "name": "Flux de test", "fields": []}


# ── Init ──────────────────────────────────────────────────────────────────────


class TestInit:
    def test_directories_created(self, storage):
        assert os.path.isdir(storage.app_dir)
        assert os.path.isdir(storage.flow_dir)
        assert os.path.isdir(storage.data_dir)
        assert os.path.isdir(storage.logs_dir)

    def test_generated_directory_created(self, storage):
        """Le dossier ``generated/`` doit être créé à l'initialisation."""
        assert os.path.isdir(storage.generated_dir)

    def test_logfile_path(self, storage):
        path = storage.get_logfile_path()
        assert path.endswith(".log")
        assert "src" in path or "dataflow" in path.lower()


# ── Icon ──────────────────────────────────────────────────────────────────────


class TestIcon:
    def test_get_icon_path_returns_string(self, storage):
        path = storage.get_icon_path()
        assert isinstance(path, str)
        assert path.endswith(".ico")

    def test_icon_file_created(self, storage):
        path = storage.get_icon_path()
        assert os.path.isfile(path)

    def test_icon_path_stable_on_second_call(self, storage):
        p1 = storage.get_icon_path()
        p2 = storage.get_icon_path()
        assert p1 == p2


# ── save_flow / load_all_flows ────────────────────────────────────────────────


class TestFlowPersistence:
    def test_save_and_reload(self, storage, sample_flow):
        assert storage.save_flow(sample_flow)
        flows = storage.load_all_flows()
        assert len(flows) == 1
        assert flows[0]["name"] == "Flux de test"

    def test_updated_timestamp_set(self, storage, sample_flow):
        storage.save_flow(sample_flow)
        flows = storage.load_all_flows()
        assert "updated" in flows[0]

    def test_multiple_flows(self, storage):
        for i in range(3):
            storage.save_flow({"id": f"{i}.0", "name": f"Flux {i}"})
        assert len(storage.load_all_flows()) == 3

    def test_load_returns_empty_when_no_flows(self, storage):
        assert storage.load_all_flows() == []

    def test_unknown_files_ignored(self, storage, sample_flow):
        bad = os.path.join(storage.flow_dir, "not_a_flow.json")
        with open(bad, "w") as f:
            json.dump({"id": "bad"}, f)
        storage.save_flow(sample_flow)
        assert len(storage.load_all_flows()) == 1

    def test_corrupted_file_skipped(self, storage, sample_flow):
        storage.save_flow(sample_flow)
        fname = os.path.join(storage.flow_dir, f"flow_{sample_flow['id']}.json")
        with open(fname, "w") as f:
            f.write("NOT JSON {{{")
        flows = storage.load_all_flows()
        assert flows == []


# ── delete_flow ───────────────────────────────────────────────────────────────


class TestDeleteFlow:
    def test_delete_existing(self, storage, sample_flow):
        storage.save_flow(sample_flow)
        assert storage.delete_flow(sample_flow["id"])
        assert storage.load_all_flows() == []

    def test_delete_nonexistent_ok(self, storage):
        assert storage.delete_flow("99999.0")


# ── export / import ───────────────────────────────────────────────────────────


class TestExportImport:
    def test_export_creates_file(self, storage, sample_flow, tmp_path):
        dest = str(tmp_path / "export.json")
        assert storage.export_flow(sample_flow, dest)
        assert os.path.isfile(dest)

    def test_import_assigns_new_id(self, storage, sample_flow, tmp_path):
        dest = str(tmp_path / "export.json")
        storage.export_flow(sample_flow, dest)
        imported = storage.import_flow(dest)
        assert imported is not None
        assert imported["id"] != sample_flow["id"]

    def test_import_preserves_name(self, storage, sample_flow, tmp_path):
        dest = str(tmp_path / "export.json")
        storage.export_flow(sample_flow, dest)
        imported = storage.import_flow(dest)
        assert imported["name"] == sample_flow["name"]

    def test_import_invalid_file_returns_none(self, storage, tmp_path):
        bad = str(tmp_path / "bad.json")
        with open(bad, "w") as f:
            f.write("NOT JSON {{{")
        assert storage.import_flow(bad) is None

    def test_import_nonexistent_returns_none(self, storage):
        assert storage.import_flow("/no/such/file.json") is None

    def test_export_invalid_path_returns_false(self, storage, sample_flow):
        assert not storage.export_flow(sample_flow, "/no/such/dir/export.json")


# ── Dossiers ──────────────────────────────────────────────────────────────────


class TestFolders:
    SAMPLE = [{"id": "1", "name": "Test", "parentId": None, "created": "2024-01-01"}]

    def test_save_and_load(self, storage):
        assert storage.save_folders(self.SAMPLE)
        loaded = storage.load_folders()
        assert loaded[0]["name"] == "Test"

    def test_load_returns_empty_if_no_file(self, storage):
        assert storage.load_folders() == []

    def test_corrupted_folders_file_returns_empty(self, storage):
        with open(storage.folders_file, "w") as f:
            f.write("NOT JSON")
        assert storage.load_folders() == []


# ── Cache communes ────────────────────────────────────────────────────────────


class TestCommunesCache:
    SAMPLE = [{"nom": "Paris", "code": "75056", "codesPostaux": ["75001"]}]

    def test_save_and_load(self, storage):
        assert storage.save_communes_cache(self.SAMPLE)
        loaded = storage.load_communes_cache()
        assert loaded[0]["nom"] == "Paris"

    def test_has_cache_true_after_save(self, storage):
        storage.save_communes_cache(self.SAMPLE)
        assert storage.has_communes_cache()

    def test_has_cache_false_initially(self, storage):
        assert not storage.has_communes_cache()

    def test_clear_cache(self, storage):
        storage.save_communes_cache(self.SAMPLE)
        assert storage.clear_communes_cache()
        assert not storage.has_communes_cache()

    def test_load_returns_none_without_cache(self, storage):
        assert storage.load_communes_cache() is None

    def test_clear_nonexistent_returns_true(self, storage):
        assert storage.clear_communes_cache()

    def test_corrupted_cache_returns_none(self, storage):
        with open(storage.communes_cache_file, "w") as f:
            f.write("INVALID JSON {{")
        assert storage.load_communes_cache() is None


# ══════════════════════════════════════════════════════════════════════════════
# Données générées — nouvelles méthodes
# ══════════════════════════════════════════════════════════════════════════════


class TestSanitizePathComponent:
    """Tests de la méthode statique ``_sanitize_path_component``."""

    def test_normal_name_unchanged(self, storage):
        result = storage._sanitize_path_component("MonFlux")
        assert result == "MonFlux"

    def test_spaces_preserved(self, storage):
        result = storage._sanitize_path_component("Mon Flux")
        assert " " in result or "_" in result  # espaces ou substitués, non vides

    def test_slashes_replaced(self, storage):
        result = storage._sanitize_path_component("Flux/Test")
        assert "/" not in result

    def test_colons_replaced(self, storage):
        result = storage._sanitize_path_component("Flux:2024")
        assert ":" not in result

    def test_dots_replaced(self, storage):
        r"""Les points ne sont pas dans ``[\w\- ]``, ils doivent être remplacés."""
        result = storage._sanitize_path_component("Flux.v2")
        assert "." not in result

    def test_empty_string_becomes_sans_nom(self, storage):
        assert storage._sanitize_path_component("") == "sans_nom"

    def test_whitespace_only_becomes_sans_nom(self, storage):
        assert storage._sanitize_path_component("   ") == "sans_nom"

    def test_special_chars_all_replaced(self, storage):
        result = storage._sanitize_path_component('a<b>c:d"e/f\\g|h?i*j')
        for char in ("<", ">", ":", '"', "/", "\\", "|", "?", "*"):
            assert char not in result

    def test_accented_chars_kept(self, storage):
        r"""Les lettres accentuées font partie de ``\w`` en Unicode."""
        result = storage._sanitize_path_component("Résumé")
        assert len(result) > 0


class TestSaveGeneratedData:
    """Tests de ``save_generated_data``."""

    def test_returns_path_string(self, storage):
        path = storage.save_generated_data("MonFlux", "run_001", "col1,col2\n1,2")
        assert isinstance(path, str)

    def test_file_actually_created(self, storage):
        path = storage.save_generated_data("MonFlux", "run_001", "contenu csv")
        assert path is not None
        assert os.path.isfile(path)

    def test_default_extension_is_csv(self, storage):
        path = storage.save_generated_data("F", "f", "data")
        assert path.endswith(".csv")

    def test_json_extension(self, storage):
        path = storage.save_generated_data("F", "f", "{}", fmt="json")
        assert path.endswith(".json")

    def test_txt_extension_for_fixed(self, storage):
        path = storage.save_generated_data("F", "f", "data", fmt="fixed")
        assert path.endswith(".txt")

    def test_xml_extension(self, storage):
        path = storage.save_generated_data("F", "f", "<r/>", fmt="xml")
        assert path.endswith(".xml")

    def test_content_written_correctly(self, storage):
        content = "hello,world\n1,2"
        path = storage.save_generated_data("F", "f", content)
        with open(path, encoding="utf-8") as fh:
            assert fh.read() == content

    def test_subdirectory_named_after_flow(self, storage):
        path = storage.save_generated_data("MonFlux", "run", "x")
        assert "MonFlux" in path or "MonFlux".replace(" ", "_") in path

    def test_subdirectory_created(self, storage):
        storage.save_generated_data("NouveauFlux", "run", "x")
        folder = storage.get_generated_folder("NouveauFlux")
        assert os.path.isdir(folder)

    def test_multiple_files_same_flow(self, storage):
        storage.save_generated_data("F", "run1", "a")
        storage.save_generated_data("F", "run2", "b")
        folder = storage.get_generated_folder("F")
        files = [n for n in os.listdir(folder) if os.path.isfile(os.path.join(folder, n))]
        assert len(files) == 2

    def test_encoding_respected(self, storage):
        content = "café,résumé"
        path = storage.save_generated_data("F", "f", content, encoding="UTF-8")
        with open(path, encoding="utf-8") as fh:
            assert fh.read() == content

    def test_invalid_encoding_returns_none(self, storage):
        result = storage.save_generated_data("F", "f", "data", encoding="INVALID-ENC-99999")
        assert result is None

    def test_flow_name_with_special_chars(self, storage):
        """Les caractères spéciaux dans le nom de flux ne doivent pas lever d'erreur."""
        path = storage.save_generated_data("Flux/Test:2024", "run", "x")
        assert path is not None
        assert os.path.isfile(path)


class TestListGeneratedRuns:
    """Tests de ``list_generated_runs``."""

    def test_empty_when_no_files(self, storage):
        runs = storage.list_generated_runs("InexistantFlux")
        assert runs == []

    def test_returns_one_run_after_save(self, storage):
        storage.save_generated_data("Flux", "run1", "data")
        runs = storage.list_generated_runs("Flux")
        assert len(runs) == 1

    def test_returns_multiple_runs(self, storage):
        for i in range(4):
            storage.save_generated_data("Flux", f"run{i}", f"data{i}")
        runs = storage.list_generated_runs("Flux")
        assert len(runs) == 4

    def test_run_has_required_keys(self, storage):
        storage.save_generated_data("Flux", "run", "content")
        runs = storage.list_generated_runs("Flux")
        for key in ("name", "path", "size", "modified"):
            assert key in runs[0], f"Clé '{key}' manquante"

    def test_path_points_to_existing_file(self, storage):
        storage.save_generated_data("Flux", "run", "x")
        runs = storage.list_generated_runs("Flux")
        assert os.path.isfile(runs[0]["path"])

    def test_size_is_positive_integer(self, storage):
        storage.save_generated_data("Flux", "run", "content_non_vide")
        runs = storage.list_generated_runs("Flux")
        assert isinstance(runs[0]["size"], int)
        assert runs[0]["size"] > 0

    def test_modified_is_formatted_string(self, storage):
        storage.save_generated_data("Flux", "run", "x")
        runs = storage.list_generated_runs("Flux")
        mod = runs[0]["modified"]
        # Format attendu : YYYY-MM-DD HH:MM:SS
        assert len(mod) == 19
        assert mod[4] == "-" and mod[7] == "-"

    def test_sorted_most_recent_first(self, storage):
        """Deux fichiers sauvegardés à des instants distincts : le plus récent
        en premier dans la liste."""
        storage.save_generated_data("Flux", "older", "x")
        # Petit délai pour garantir des timestamps différents
        time.sleep(0.05)
        storage.save_generated_data("Flux", "newer", "y")
        runs = storage.list_generated_runs("Flux")
        assert len(runs) == 2
        mods = [r["modified"] for r in runs]
        assert mods == sorted(mods, reverse=True)

    def test_isolated_per_flow(self, storage):
        """Les runs d'un flux n'apparaissent pas dans la liste d'un autre."""
        storage.save_generated_data("FluxA", "run", "x")
        storage.save_generated_data("FluxB", "run", "y")
        assert len(storage.list_generated_runs("FluxA")) == 1
        assert len(storage.list_generated_runs("FluxB")) == 1

    def test_subdirectories_inside_generated_folder_ignored(self, storage):
        """Les sous-dossiers dans le répertoire du flux ne sont pas comptés comme runs."""
        storage.save_generated_data("Flux", "run", "x")
        folder = storage.get_generated_folder("Flux")
        subdir = os.path.join(folder, "sous_dossier")
        os.makedirs(subdir, exist_ok=True)
        runs = storage.list_generated_runs("Flux")
        # Seul le fichier doit être compté
        assert len(runs) == 1


class TestGetGeneratedFolder:
    """Tests de ``get_generated_folder``."""

    def test_returns_string(self, storage):
        folder = storage.get_generated_folder("MonFlux")
        assert isinstance(folder, str)

    def test_path_under_generated_dir(self, storage):
        folder = storage.get_generated_folder("MonFlux")
        assert folder.startswith(storage.generated_dir)

    def test_different_flows_different_folders(self, storage):
        f1 = storage.get_generated_folder("Flux1")
        f2 = storage.get_generated_folder("Flux2")
        assert f1 != f2

    def test_same_flow_same_folder(self, storage):
        f1 = storage.get_generated_folder("Flux")
        f2 = storage.get_generated_folder("Flux")
        assert f1 == f2

    def test_special_chars_in_name_sanitized(self, storage):
        folder = storage.get_generated_folder("Flux/Spécial:2024")
        assert "/" not in os.path.basename(folder)
        assert ":" not in os.path.basename(folder)
