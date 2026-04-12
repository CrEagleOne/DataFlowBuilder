"""
Gestionnaire de flux - Logique métier principale
"""

from datetime import datetime
from threading import Lock
from time import time_ns

from .data_generator import DataGenerator
from .field_types import (
    clean_field_for_export,
)
from .storage import StorageManager

# ── Générateur d'IDs unique ───────────────────────────────────────────────────
# Sur Windows, la résolution de l'horloge peut être insuffisante pour garantir
# des IDs uniques lors de créations rapides en test.
# Un compteur atomique complète le timestamp : unicité absolue, format
# float-string conservé pour la compatibilité avec storage.py.

_id_lock = Lock()
_id_counter = 0


def _new_id() -> str:
    global _id_counter
    with _id_lock:
        _id_counter += 1
        seq = _id_counter
    return f"{time_ns() // 1_000_000_000}.{seq:09d}"


def _ensure_subtype(field: dict) -> dict:
    """Garantit la présence de la clé subType (sans migration d'anciens types)."""
    if "subType" not in field:
        return {**field, "subType": "none"}
    return field


class FlowManager:
    """Classe responsable de la gestion des flux de données et des dossiers"""

    def __init__(self):
        self.storage = StorageManager()
        self.generator = DataGenerator(self.storage)
        self.current_flow = None
        self.field_lines = []
        self.header_fields = []
        self.footer_fields = []
        self.field_presets = {}

        # Dossiers : liste plate de dicts {id, name, parentId, created}
        self._folders: list[dict] = self.storage.load_folders()

    # ─── Propriété lecture seule des dossiers ──────────────────────────────────

    @property
    def folders(self) -> list[dict]:
        return self._folders

    # ═══════════════════════════════════════════════════════════════════════════
    # CRUD Dossiers
    # ═══════════════════════════════════════════════════════════════════════════

    def create_folder(self, name: str, parent_id: str | None = None) -> dict:
        """
        Crée un nouveau dossier.

        Args:
            name:      Nom du dossier.
            parent_id: ID du dossier parent (None = racine).

        Returns:
            Le dict du dossier créé.
        """
        folder = {
            "id": _new_id(),
            "name": name.strip() or "Nouveau dossier",
            "parentId": parent_id,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._folders.append(folder)
        self._save_folders()
        return folder

    def rename_folder(self, folder_id: str, new_name: str) -> bool:
        """Renomme un dossier existant."""
        for f in self._folders:
            if f["id"] == folder_id:
                f["name"] = new_name.strip() or f["name"]
                self._save_folders()
                return True
        return False

    def delete_folder(self, folder_id: str, move_flows_to: str | None = None) -> bool:
        """
        Supprime un dossier et tous ses sous-dossiers récursivement.
        Les flux contenus sont déplacés vers *move_flows_to* (None = racine).

        Args:
            folder_id:     ID du dossier à supprimer.
            move_flows_to: ID du dossier de destination pour les flux orphelins.
        """
        # Collecter tous les IDs à supprimer (dossier + descendants)
        to_delete = self._collect_subtree_ids(folder_id)

        # Réaffecter les flux orphelins
        for flow in self.storage.load_all_flows():
            if flow.get("folderId") in to_delete:
                flow["folderId"] = move_flows_to
                self.storage.save_flow(flow)

        # Supprimer les dossiers
        self._folders = [f for f in self._folders if f["id"] not in to_delete]
        self._save_folders()
        return True

    def move_folder(self, folder_id: str, new_parent_id: str | None) -> bool:
        """
        Déplace un dossier sous un nouveau parent.
        Refuse si new_parent_id est dans le sous-arbre de folder_id (cycle).
        """
        # Vérification anti-cycle
        subtree = self._collect_subtree_ids(folder_id)
        if new_parent_id in subtree:
            return False

        for f in self._folders:
            if f["id"] == folder_id:
                f["parentId"] = new_parent_id
                self._save_folders()
                return True
        return False

    def get_folder(self, folder_id: str) -> dict | None:
        """Retourne un dossier par son ID."""
        return next((f for f in self._folders if f["id"] == folder_id), None)

    def get_children_folders(self, parent_id: str | None) -> list[dict]:
        """Retourne les dossiers enfants directs d'un parent donné."""
        return [f for f in self._folders if f.get("parentId") == parent_id]

    # ═══════════════════════════════════════════════════════════════════════════
    # Affectation flux ↔ dossier
    # ═══════════════════════════════════════════════════════════════════════════

    def move_flow_to_folder(self, flow_id: str, folder_id: str | None) -> bool:
        """
        Affecte un flux à un dossier (ou à la racine si folder_id est None).

        Args:
            flow_id:   ID du flux à déplacer.
            folder_id: ID du dossier cible, ou None pour la racine.
        """
        flows = self.storage.load_all_flows()
        for flow in flows:
            if flow.get("id") == flow_id:
                flow["folderId"] = folder_id
                return bool(self.storage.save_flow(flow))
        return False

    def get_flows_in_folder(self, folder_id: str | None) -> list[dict]:
        """
        Retourne les flux appartenant directement à un dossier donné.
        folder_id == None → flux à la racine (sans dossier).
        """
        all_flows = self.storage.load_all_flows()
        return [f for f in all_flows if f.get("folderId") == folder_id]

    # ═══════════════════════════════════════════════════════════════════════════
    # Helpers privés
    # ═══════════════════════════════════════════════════════════════════════════

    def _collect_subtree_ids(self, root_id: str) -> set[str]:
        """Retourne l'ensemble des IDs du dossier root et de tous ses descendants."""
        result = {root_id}
        queue = [root_id]
        while queue:
            current = queue.pop()
            children = [
                f["id"]
                for f in self._folders
                if f.get("parentId") == current and f["id"] not in result
            ]
            result.update(children)
            queue.extend(children)
        return result

    def _save_folders(self) -> None:
        self.storage.save_folders(self._folders)

    # ═══════════════════════════════════════════════════════════════════════════
    # Gestion des flux (inchangée)
    # ═══════════════════════════════════════════════════════════════════════════

    def create_new_flow(self):
        self.current_flow = {
            "id": _new_id(),
            "name": "Nouveau flux",
            "description": "",
            "format": "csv",
            "delimiter": ",",
            "lineEnding": "CRLF",
            "encoding": "UTF-8",
            "hasHeader": True,
            "numRows": 10,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "folderId": None,
        }
        self.field_lines = []
        self.header_fields = []
        self.footer_fields = []
        self.field_presets = {}

    def load_flow(self, flow: dict):
        """Charge un flux."""
        self.current_flow = {
            k: v
            for k, v in flow.items()
            if k not in ("fields", "headerFields", "footerFields", "presets")
        }
        self.field_lines = [
            {**line, "fields": [_ensure_subtype(f) for f in line.get("fields", [])]}
            for line in flow.get("fields", [])
        ]
        self.header_fields = [_ensure_subtype(f) for f in flow.get("headerFields", [])]
        self.footer_fields = [_ensure_subtype(f) for f in flow.get("footerFields", [])]
        self.field_presets = flow.get("presets", {})

    def save_current_flow(self) -> bool:
        if not self.current_flow:
            return False
        flow_to_save = {
            **self.current_flow,
            "fields": self.field_lines,
            "headerFields": self.header_fields,
            "footerFields": self.footer_fields,
            "presets": self.field_presets,
        }
        return bool(self.storage.save_flow(flow_to_save))

    def load_all_flows(self) -> list:
        return list(self.storage.load_all_flows())

    def delete_flow(self, flow_id) -> bool:
        return bool(self.storage.delete_flow(flow_id))

    def export_flow(self, filepath: str) -> bool:
        if not self.current_flow:
            return False

        def clean_line(line: dict) -> dict:
            return {
                **{k: v for k, v in line.items() if k != "fields"},
                "fields": [clean_field_for_export(f) for f in line.get("fields", [])],
            }

        flow_to_export = {
            **self.current_flow,
            "fields": [clean_line(line) for line in self.field_lines],
            "headerFields": [clean_field_for_export(f) for f in self.header_fields],
            "footerFields": [clean_field_for_export(f) for f in self.footer_fields],
            "presets": self.field_presets,
        }
        return bool(self.storage.export_flow(flow_to_export, filepath))

    def import_flow(self, filepath: str) -> bool:
        imported = self.storage.import_flow(filepath)
        if imported:
            self.load_flow(imported)
            return True
        return False

    def update_flow_field(self, key: str, value) -> None:
        if self.current_flow:
            self.current_flow[key] = value

    def add_field_line(self) -> None:
        new_line = {
            "id": _new_id(),
            "name": f"Ligne {len(self.field_lines) + 1}",
            "fields": [],
        }
        self.field_lines.append(new_line)

    def delete_field_line(self, line_id: str) -> None:
        self.field_lines = [line for line in self.field_lines if line["id"] != line_id]

    def update_line_name(self, line_id: str, name: str) -> None:
        for line in self.field_lines:
            if line["id"] == line_id:
                line["name"] = name
                break

    def _calculate_line_count(self) -> int:
        total = 0
        if self.header_fields and any(f.get("includeInOutput", False) for f in self.header_fields):
            total += 1
        for line in self.field_lines:
            if any(f.get("includeInOutput", False) for f in line.get("fields", [])):
                total += self.current_flow.get("numRows", 10)
        if self.footer_fields and any(f.get("includeInOutput", False) for f in self.footer_fields):
            total += 1
        return total

    def generate_sample_data(self) -> str:
        if not self.current_flow:
            return ""

        num_rows = int(self.current_flow.get("numRows", 10))
        delimiter = str(self.current_flow.get("delimiter", ","))
        trailing_delim = self.current_flow.get("trailingDelimiter", False)
        output = []

        self.generator.reset_counters()
        total_lines = self._calculate_line_count()

        def join_row(row: list) -> str:
            line = delimiter.join(row)
            if trailing_delim:
                line += delimiter
            return line

        if self.header_fields:
            row = self._generate_row(self.header_fields, 0, total_lines)
            if row:
                output.append(join_row(row))

        for i in range(num_rows):
            for line in self.field_lines:
                row = self._generate_row(line.get("fields", []), i, total_lines)
                if row:
                    output.append(join_row(row))

        if self.footer_fields:
            row = self._generate_row(self.footer_fields, 0, total_lines)
            if row:
                output.append(join_row(row))

        return "\n".join(output)

    def _generate_row(
        self,
        fields: list,
        row_index: int,
        total_lines: int | None = None,
    ) -> list:
        fields_data: dict[str, str] = {}
        sorted_fields = self.generator.sort_fields_by_dependencies(fields)

        self.generator.inject_linked_field_ids(fields, fields_data)

        for field in sorted_fields:
            value = self.generator.generate_field_value(
                field, row_index, fields_data, self.field_presets, total_lines
            )
            fields_data[field["id"]] = value

        return [fields_data[f["id"]] for f in fields if f.get("includeInOutput")]
