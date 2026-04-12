"""
Tests unitaires — core/flow_manager.py
"""

import json
import os
from unittest.mock import patch

import pytest

from core.constants import FALLBACK_COMMUNES
from core.flow_manager import FlowManager
from core.storage import StorageManager


@pytest.fixture
def fm(tmp_path, monkeypatch):
    monkeypatch.setattr(
        StorageManager,
        "_get_app_directory",
        staticmethod(lambda: str(tmp_path / "src")),
    )
    # Sur Windows, GeoAPIClient.fetch_all_communes() effectue une requête HTTP
    # sans timeout qui bloque indéfiniment quand le cache communes est absent
    # (tmp_path vide). On retourne immédiatement les communes de fallback.
    with patch(
        "core.geo_api.GeoAPIClient.fetch_all_communes",
        return_value=FALLBACK_COMMUNES,
    ):
        yield FlowManager()


# ── Flux de base ───────────────────────────────────────────────────────────────


class TestCreateNewFlow:
    def test_creates_flow_with_defaults(self, fm):
        fm.create_new_flow()
        assert fm.current_flow["name"] == "Nouveau flux"
        assert "id" in fm.current_flow

    def test_clears_fields(self, fm):
        fm.field_lines = [{"id": "x"}]
        fm.create_new_flow()
        assert fm.field_lines == []
        assert fm.header_fields == []
        assert fm.footer_fields == []

    def test_flow_has_format_delimiter_numrows(self, fm):
        fm.create_new_flow()
        assert "format" in fm.current_flow
        assert "delimiter" in fm.current_flow
        assert "numRows" in fm.current_flow


class TestLoadFlow:
    def test_loads_fields(self, fm):
        flow = {
            "id": "1.0",
            "name": "Test",
            "fields": [
                {
                    "id": "l1",
                    "name": "L",
                    "fields": [{"id": "f1", "type": "alpha", "subType": "nom"}],
                }
            ],
            "headerFields": [],
            "footerFields": [],
        }
        fm.load_flow(flow)
        assert fm.current_flow["name"] == "Test"
        assert fm.field_lines[0]["fields"][0]["subType"] == "nom"

    def test_ensures_subtype_on_load(self, fm):
        flow = {
            "id": "2.0",
            "name": "Ancien",
            "fields": [{"id": "l1", "name": "L", "fields": [{"id": "f1", "type": "email"}]}],
            "headerFields": [{"id": "h1", "type": "civilite"}],
            "footerFields": [],
        }
        fm.load_flow(flow)
        assert fm.field_lines[0]["fields"][0]["subType"] == "none"
        assert fm.header_fields[0]["subType"] == "none"

    def test_loads_presets(self, fm):
        flow = {
            "id": "3.0",
            "name": "P",
            "fields": [],
            "headerFields": [],
            "footerFields": [],
            "presets": {"f1": {"useRandom": False, "values": [{"value": "X"}]}},
        }
        fm.load_flow(flow)
        assert "f1" in fm.field_presets

    def test_loads_footer_fields(self, fm):
        flow = {
            "id": "4.0",
            "name": "Footer",
            "fields": [],
            "headerFields": [],
            "footerFields": [{"id": "foot1", "type": "alpha", "subType": "none"}],
        }
        fm.load_flow(flow)
        assert len(fm.footer_fields) == 1


class TestFieldLines:
    def test_add_field_line(self, fm):
        fm.create_new_flow()
        fm.add_field_line()
        assert len(fm.field_lines) == 1

    def test_delete_field_line(self, fm):
        fm.create_new_flow()
        fm.add_field_line()
        line_id = fm.field_lines[0]["id"]
        fm.delete_field_line(line_id)
        assert fm.field_lines == []

    def test_update_line_name(self, fm):
        fm.create_new_flow()
        fm.add_field_line()
        line_id = fm.field_lines[0]["id"]
        fm.update_line_name(line_id, "Ma Ligne")
        assert fm.field_lines[0]["name"] == "Ma Ligne"

    def test_update_unknown_line_noop(self, fm):
        fm.create_new_flow()
        fm.update_line_name("unknown_id", "Noop")


class TestSaveAndLoad:
    def test_save_and_reload(self, fm):
        fm.create_new_flow()
        fm.current_flow["name"] = "Flux persisté"
        assert fm.save_current_flow()
        flows = fm.load_all_flows()
        assert any(f["name"] == "Flux persisté" for f in flows)

    def test_save_without_flow_returns_false(self, fm):
        fm.current_flow = None
        assert not fm.save_current_flow()

    def test_delete_flow(self, fm):
        fm.create_new_flow()
        flow_id = fm.current_flow["id"]
        fm.save_current_flow()
        assert fm.delete_flow(flow_id)
        assert not any(f["id"] == flow_id for f in fm.load_all_flows())


class TestUpdateFlowField:
    def test_updates_field(self, fm):
        fm.create_new_flow()
        fm.update_flow_field("name", "Nouveau nom")
        assert fm.current_flow["name"] == "Nouveau nom"

    def test_no_op_without_flow(self, fm):
        fm.current_flow = None
        fm.update_flow_field("name", "X")


class TestGenerateSampleData:
    def _simple_field(self, fid="f1"):
        return {
            "id": fid,
            "type": "alpha",
            "subType": "nom",
            "length": 20,
            "includeInOutput": True,
            "padding": "none",
        }

    def test_generates_csv(self, fm):
        fm.create_new_flow()
        fm.current_flow.update({"format": "csv", "delimiter": ",", "numRows": 3})
        fm.add_field_line()
        fm.field_lines[0]["fields"].append(self._simple_field())
        lines = [line for line in fm.generate_sample_data().splitlines() if line.strip()]
        assert len(lines) == 3

    def test_empty_flow_returns_empty_string(self, fm):
        fm.create_new_flow()
        assert fm.generate_sample_data() == ""

    def test_no_flow_returns_empty(self, fm):
        fm.current_flow = None
        assert fm.generate_sample_data() == ""

    def test_header_adds_one_line(self, fm):
        fm.create_new_flow()
        fm.current_flow["numRows"] = 2
        fm.header_fields = [
            {
                "id": "h1",
                "type": "alpha",
                "subType": "none",
                "length": 5,
                "includeInOutput": True,
                "defaultValue": "HDR",
                "padding": "none",
            }
        ]
        fm.add_field_line()
        fm.field_lines[0]["fields"].append(self._simple_field())
        lines = [line for line in fm.generate_sample_data().splitlines() if line.strip()]
        assert len(lines) == 3
        assert lines[0] == "HDR"

    def test_footer_adds_one_line(self, fm):
        fm.create_new_flow()
        fm.current_flow["numRows"] = 2
        fm.footer_fields = [
            {
                "id": "foot1",
                "type": "alpha",
                "subType": "none",
                "length": 5,
                "includeInOutput": True,
                "defaultValue": "FOOT",
                "padding": "none",
            }
        ]
        fm.add_field_line()
        fm.field_lines[0]["fields"].append(self._simple_field())
        lines = [line for line in fm.generate_sample_data().splitlines() if line.strip()]
        assert len(lines) == 3
        assert lines[-1] == "FOOT"

    def test_trailing_delimiter(self, fm):
        fm.create_new_flow()
        fm.current_flow.update({"numRows": 1, "delimiter": ",", "trailingDelimiter": True})
        fm.add_field_line()
        fm.field_lines[0]["fields"].append(
            {
                "id": "f1",
                "type": "alpha",
                "subType": "none",
                "length": 5,
                "includeInOutput": True,
                "defaultValue": "ABC",
                "padding": "none",
            }
        )
        assert fm.generate_sample_data().endswith(",")

    def test_excluded_fields_produce_no_output(self, fm):
        fm.create_new_flow()
        fm.current_flow["numRows"] = 2
        fm.add_field_line()
        fm.field_lines[0]["fields"].append(
            {
                "id": "f1",
                "type": "alpha",
                "subType": "nom",
                "length": 20,
                "includeInOutput": False,
                "padding": "none",
            }
        )
        assert fm.generate_sample_data() == ""


class TestExportImport:
    def test_export_creates_file(self, fm, tmp_path):
        fm.create_new_flow()
        dest = str(tmp_path / "export.json")
        assert fm.export_flow(dest)
        assert os.path.isfile(dest)

    def test_export_without_flow_returns_false(self, fm, tmp_path):
        fm.current_flow = None
        assert not fm.export_flow(str(tmp_path / "nope.json"))

    def test_export_cleans_irrelevant_keys(self, fm, tmp_path):
        fm.create_new_flow()
        fm.add_field_line()
        fm.field_lines[0]["fields"].append(
            {
                "id": "f1",
                "type": "alpha",
                "subType": "email",
                "length": 50,
                "includeInOutput": True,
                "comment": "",
                "category": "",
                "decimalSeparator": ".",
                "concatItems": [],
                "name": "Email",
            }
        )
        dest = str(tmp_path / "clean.json")
        fm.export_flow(dest)
        with open(dest) as f:
            data = json.load(f)
        assert "decimalSeparator" not in data["fields"][0]["fields"][0]

    def test_import_loads_flow(self, fm, tmp_path):
        fm.create_new_flow()
        fm.current_flow["name"] = "Importé"
        dest = str(tmp_path / "import.json")
        fm.export_flow(dest)
        fm.current_flow = None
        result = fm.import_flow(dest)
        assert result is True
        assert fm.current_flow["name"] == "Importé"

    def test_import_nonexistent_returns_false(self, fm):
        assert not fm.import_flow("/no/such/file.json")


# ── Dossiers ───────────────────────────────────────────────────────────────────


class TestCreateFolder:
    def test_creates_folder(self, fm):
        f = fm.create_folder("Mon Dossier")
        assert f["name"] == "Mon Dossier"
        assert f["parentId"] is None

    def test_with_parent(self, fm):
        parent = fm.create_folder("P")
        child = fm.create_folder("C", parent["id"])
        assert child["parentId"] == parent["id"]

    def test_empty_name_defaults(self, fm):
        f = fm.create_folder("   ")
        assert f["name"] == "Nouveau dossier"

    def test_persisted_in_folders(self, fm):
        fm.create_folder("Persisté")
        assert any(f["name"] == "Persisté" for f in fm.folders)


class TestRenameFolder:
    def test_renames(self, fm):
        f = fm.create_folder("Avant")
        assert fm.rename_folder(f["id"], "Après")
        assert fm.get_folder(f["id"])["name"] == "Après"

    def test_unknown_id_returns_false(self, fm):
        assert not fm.rename_folder("unknown", "X")

    def test_empty_name_keeps_old(self, fm):
        f = fm.create_folder("Original")
        fm.rename_folder(f["id"], "   ")
        assert fm.get_folder(f["id"])["name"] == "Original"


class TestDeleteFolder:
    def test_deletes_folder(self, fm):
        f = fm.create_folder("À supprimer")
        fm.delete_folder(f["id"])
        assert fm.get_folder(f["id"]) is None

    def test_deletes_subtree(self, fm):
        p = fm.create_folder("P")
        c = fm.create_folder("C", p["id"])
        gc = fm.create_folder("GC", c["id"])
        fm.delete_folder(p["id"])
        for fid in (p["id"], c["id"], gc["id"]):
            assert fm.get_folder(fid) is None

    def test_orphan_flows_moved_to_root(self, fm):
        folder = fm.create_folder("D")
        fm.create_new_flow()
        fm.current_flow["folderId"] = folder["id"]
        fm.save_current_flow()
        flow_id = fm.current_flow["id"]
        fm.delete_folder(folder["id"], move_flows_to=None)
        moved = next((f for f in fm.storage.load_all_flows() if f["id"] == flow_id), None)
        assert moved["folderId"] is None


class TestMoveFolder:
    def test_moves_to_new_parent(self, fm):
        a = fm.create_folder("A")
        b = fm.create_folder("B")
        assert fm.move_folder(a["id"], b["id"])
        assert fm.get_folder(a["id"])["parentId"] == b["id"]

    def test_rejects_cycle(self, fm):
        parent = fm.create_folder("Parent")
        child = fm.create_folder("Enfant", parent["id"])
        assert not fm.move_folder(parent["id"], child["id"])

    def test_unknown_folder_returns_false(self, fm):
        assert not fm.move_folder("unknown", None)

    def test_move_to_root(self, fm):
        p = fm.create_folder("P")
        c = fm.create_folder("C", p["id"])
        fm.move_folder(c["id"], None)
        assert fm.get_folder(c["id"])["parentId"] is None


class TestGetFolder:
    def test_returns_folder(self, fm):
        f = fm.create_folder("T")
        assert fm.get_folder(f["id"]) is not None

    def test_returns_none_for_unknown(self, fm):
        assert fm.get_folder("nonexistent") is None


class TestGetChildrenFolders:
    def test_direct_children(self, fm):
        p = fm.create_folder("P")
        c1 = fm.create_folder("C1", p["id"])
        c2 = fm.create_folder("C2", p["id"])
        other = fm.create_folder("Other")
        children_ids = [f["id"] for f in fm.get_children_folders(p["id"])]
        assert c1["id"] in children_ids
        assert c2["id"] in children_ids
        assert other["id"] not in children_ids

    def test_root_children(self, fm):
        r1 = fm.create_folder("R1")
        sub = fm.create_folder("Sub", r1["id"])
        root_ids = [f["id"] for f in fm.get_children_folders(None)]
        assert r1["id"] in root_ids
        assert sub["id"] not in root_ids


class TestMoveFlowToFolder:
    def test_moves_flow(self, fm):
        folder = fm.create_folder("Dest")
        fm.create_new_flow()
        flow_id = fm.current_flow["id"]
        fm.save_current_flow()
        assert fm.move_flow_to_folder(flow_id, folder["id"])
        flows = fm.storage.load_all_flows()
        assert next(f for f in flows if f["id"] == flow_id)["folderId"] == folder["id"]

    def test_unknown_flow_returns_false(self, fm):
        assert not fm.move_flow_to_folder("unknown", None)


class TestGetFlowsInFolder:
    def test_flows_in_folder(self, fm):
        folder = fm.create_folder("F")
        fm.create_new_flow()
        fm.current_flow["folderId"] = folder["id"]
        fm.save_current_flow()
        assert len(fm.get_flows_in_folder(folder["id"])) == 1

    def test_empty_folder(self, fm):
        folder = fm.create_folder("Vide")
        assert fm.get_flows_in_folder(folder["id"]) == []


class TestCalculateLineCount:
    def test_data_rows_only(self, fm):
        fm.create_new_flow()
        fm.current_flow["numRows"] = 5
        fm.add_field_line()
        fm.field_lines[0]["fields"].append(
            {
                "id": "f1",
                "type": "alpha",
                "subType": "nom",
                "length": 10,
                "includeInOutput": True,
                "padding": "none",
            }
        )
        assert fm._calculate_line_count() == 5

    def test_includes_header_footer(self, fm):
        fm.create_new_flow()
        fm.current_flow["numRows"] = 3
        fm.header_fields = [{"id": "h1", "includeInOutput": True}]
        fm.footer_fields = [{"id": "f1", "includeInOutput": True}]
        fm.add_field_line()
        fm.field_lines[0]["fields"].append(
            {
                "id": "d1",
                "type": "alpha",
                "subType": "nom",
                "length": 10,
                "includeInOutput": True,
                "padding": "none",
            }
        )
        assert fm._calculate_line_count() == 5  # 1 + 3 + 1
