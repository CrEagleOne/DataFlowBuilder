"""
Gestion du stockage des flux sur le système de fichiers
"""

import base64
import json
import os
import re
import tempfile
from datetime import datetime

from utils import FAVICON_ICO_B64

_icon_tmp_path: str | None = None

# Extensions de fichier par format de sortie
_FORMAT_EXT: dict[str, str] = {
    "csv": "csv",
    "fixed": "txt",
    "xml": "xml",
    "json": "json",
}


class StorageManager:
    """Classe responsable de la persistance des flux, des dossiers et des données générées."""

    def __init__(self):
        self.app_dir = self._get_app_directory()
        self.logs_dir = os.path.join(self.app_dir, "logs")
        self.data_dir = os.path.join(self.app_dir, "data")
        self.flow_dir = os.path.join(self.app_dir, "flows")
        self.assets_dir = os.path.join(self.app_dir, "assets")
        self.generated_dir = os.path.join(self.app_dir, "generated")
        os.makedirs(self.app_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.flow_dir, exist_ok=True)
        os.makedirs(self.assets_dir, exist_ok=True)
        os.makedirs(self.generated_dir, exist_ok=True)
        self.communes_cache_file = os.path.join(self.data_dir, "communes_cache.json")
        self.folders_file = os.path.join(self.data_dir, "folders.json")
        self.log_file = os.path.join(self.logs_dir, "dataflow_builder.log")

    @staticmethod
    def _get_app_directory():
        """Retourne le chemin du dossier de l'application selon l'OS.

        Returns:
            str: Chemin absolu vers le répertoire applicatif dans le dossier
            temporaire du système.
        """
        temp_base = tempfile.gettempdir()
        app_folder = os.path.join(temp_base, "DataFlowBuilder")
        return app_folder

    # ─── Icone ───────────────────────────────────────────────────────────────
    def get_icon_path(self) -> str:
        """Retourne le chemin vers favicon.ico sur le disque.

        Crée le fichier dans le dossier applicatif au premier appel, réutilise
        le fichier existant ensuite. Compatible avec un lancement normal et avec
        un exécutable PyInstaller.

        Returns:
            str: Chemin absolu vers le fichier favicon.ico applicatif.
        """
        global _icon_tmp_path
        if _icon_tmp_path is None:
            icon_path = os.path.join(self.assets_dir, "favicon.ico")
            if not os.path.exists(icon_path):
                data = base64.b64decode(FAVICON_ICO_B64)
                with open(icon_path, "wb") as f:
                    f.write(data)
            _icon_tmp_path = icon_path
        return _icon_tmp_path

    # ─── Flux ────────────────────────────────────────────────────────────────

    def save_flow(self, flow_data):
        """Sauvegarde un flux dans un fichier JSON.

        Args:
            flow_data: Dictionnaire contenant toutes les données du flux.

        Returns:
            bool: True si la sauvegarde a réussi.
        """
        try:
            flow_data["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            filename = os.path.join(self.flow_dir, f"flow_{flow_data['id']}.json")

            with open(filename, "w", encoding="utf-8") as f:
                json.dump(flow_data, f, indent=2, ensure_ascii=False)

            return True
        except Exception as e:
            print(f"Erreur lors de la sauvegarde : {e}")
            return False

    def load_all_flows(self):
        """Charge tous les flux sauvegardés.

        Returns:
            list: Liste des flux chargés depuis le répertoire de flux.
        """
        flows = []

        if not os.path.exists(self.flow_dir):
            return flows

        flow_pattern = re.compile(r"^flow_\d+\.\d+\.json$")

        for filename in os.listdir(self.flow_dir):
            if flow_pattern.match(filename):
                filepath = os.path.join(self.flow_dir, filename)
                try:
                    with open(filepath, encoding="utf-8") as f:
                        flow = json.load(f)
                        flows.append(flow)
                except Exception as e:
                    print(f"Erreur lors du chargement de {filename} : {e}")
                    continue

        return flows

    def delete_flow(self, flow_id):
        """Supprime un flux.

        Args:
            flow_id: ID du flux à supprimer.

        Returns:
            bool: True si la suppression a réussi.
        """
        try:
            filename = os.path.join(self.flow_dir, f"flow_{flow_id}.json")
            if os.path.exists(filename):
                os.remove(filename)
            return True
        except Exception as e:
            print(f"Erreur lors de la suppression : {e}")
            return False

    @staticmethod
    def export_flow(flow_data, filepath):
        """Exporte un flux vers un fichier spécifié par l'utilisateur.

        Args:
            flow_data: Données du flux à exporter.
            filepath: Chemin du fichier de destination.

        Returns:
            bool: True si l'export a réussi.
        """
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(flow_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Erreur lors de l'export : {e}")
            return False

    @staticmethod
    def import_flow(filepath):
        """Importe un flux depuis un fichier.

        Args:
            filepath: Chemin du fichier à importer.

        Returns:
            dict | None: Données du flux importé ou None en cas d'erreur.
        """
        try:
            with open(filepath, encoding="utf-8") as f:
                flow_data = json.load(f)

            flow_data["id"] = str(datetime.now().timestamp())
            return flow_data
        except Exception as e:
            print(f"Erreur lors de l'import : {e}")
            return None

    # ─── Données générées ────────────────────────────────────────────────────

    @staticmethod
    def _sanitize_path_component(name: str) -> str:
        """Nettoie un nom pour qu'il soit utilisable comme composant de chemin.

        Remplace tous les caractères non alphanumériques (sauf tirets, espaces,
        underscores) par un underscore, et supprime les espaces en début/fin.

        Args:
            name: Chaîne brute à nettoyer.

        Returns:
            str: Chaîne utilisable comme nom de dossier ou de fichier.
        """
        return re.sub(r"[^\w\- ]", "_", name).strip() or "sans_nom"

    def save_generated_data(
        self,
        flow_name: str,
        file_name: str,
        content: str,
        fmt: str = "csv",
        encoding: str = "UTF-8",
    ) -> str | None:
        """Sauvegarde des données générées dans un sous-dossier nommé d'après le flux.

        La structure créée est ``generated/{flux_name}/{file_name}.{ext}``.
        Le dossier ``generated/{flux_name}`` est créé s'il n'existe pas.

        Args:
            flow_name: Nom du flux source, utilisé comme nom de dossier.
            file_name: Nom de base du fichier (sans extension).
            content: Contenu textuel à écrire dans le fichier.
            fmt: Identifiant de format (``'csv'``, ``'fixed'``, ``'xml'``,
                ``'json'``). Détermine l'extension du fichier.
            encoding: Encodage du fichier de sortie (défaut ``'UTF-8'``).

        Returns:
            str | None: Chemin absolu du fichier créé, ou ``None`` en cas
            d'erreur.
        """
        safe_folder = self._sanitize_path_component(flow_name)
        folder_path = os.path.join(self.generated_dir, safe_folder)
        os.makedirs(folder_path, exist_ok=True)

        ext = _FORMAT_EXT.get(fmt, "txt")
        safe_file = self._sanitize_path_component(file_name)
        file_path = os.path.join(folder_path, f"{safe_file}.{ext}")

        try:
            with open(file_path, "w", encoding=encoding) as fh:
                fh.write(content)
            return file_path
        except Exception as exc:
            print(f"Erreur lors de la sauvegarde des données générées : {exc}")
            return None

    def list_generated_runs(self, flow_name: str) -> list[dict]:
        """Liste les fichiers de données générées pour un flux donné.

        Parcourt le dossier ``generated/{flux_name}`` et retourne la liste
        des fichiers triée par date de modification décroissante.

        Args:
            flow_name: Nom du flux source.

        Returns:
            list[dict]: Liste de dicts ``{name, path, size, modified}``
            triée du plus récent au plus ancien. Retourne une liste vide si
            le dossier n'existe pas.
        """
        safe_folder = self._sanitize_path_component(flow_name)
        folder_path = os.path.join(self.generated_dir, safe_folder)

        if not os.path.isdir(folder_path):
            return []

        runs = []
        for fname in os.listdir(folder_path):
            fpath = os.path.join(folder_path, fname)
            if not os.path.isfile(fpath):
                continue
            stat = os.stat(fpath)
            runs.append(
                {
                    "name": fname,
                    "path": fpath,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
        return sorted(runs, key=lambda r: r["modified"], reverse=True)

    def get_generated_folder(self, flow_name: str) -> str:
        """Retourne le chemin du dossier de données générées pour un flux.

        Args:
            flow_name: Nom du flux source.

        Returns:
            str: Chemin absolu vers le dossier ``generated/{flux_name}``.
        """
        safe_folder = self._sanitize_path_component(flow_name)
        return os.path.join(self.generated_dir, safe_folder)

    # ─── Dossiers ────────────────────────────────────────────────────────────

    def save_folders(self, folders: list) -> bool:
        """Sauvegarde la liste complète des dossiers.

        Args:
            folders: Liste de dicts ``{id, name, parentId, created}``.

        Returns:
            bool: True si la sauvegarde a réussi.
        """
        try:
            data = {
                "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "folders": folders,
            }
            with open(self.folders_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Erreur lors de la sauvegarde des dossiers : {e}")
            return False

    def load_folders(self) -> list:
        """Charge la liste des dossiers persistés.

        Returns:
            list: Liste de dicts ``{id, name, parentId, created}``.
        """
        try:
            if not os.path.exists(self.folders_file):
                return []
            with open(self.folders_file, encoding="utf-8") as f:
                data = json.load(f)
            return list(data.get("folders", []))
        except Exception as e:
            print(f"Erreur lors du chargement des dossiers : {e}")
            return []

    # ─── Cache communes ──────────────────────────────────────────────────────

    def save_communes_cache(self, communes_data):
        """Sauvegarde les données de communes dans le fichier cache JSON.

        Args:
            communes_data: Données des communes à mettre en cache.

        Returns:
            bool: ``True`` si la sauvegarde a réussi, ``False`` sinon.
        """
        try:
            cache_data = {
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "communes": communes_data,
            }
            with open(self.communes_cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Erreur lors de la sauvegarde du cache : {e}")
            return False

    def load_communes_cache(self):
        """Charge les données de communes depuis le fichier cache JSON.

        Returns:
            list | dict | None: Données des communes si le cache existe et est
            lisible, ``None`` sinon.
        """
        try:
            if not os.path.exists(self.communes_cache_file):
                return None
            with open(self.communes_cache_file, encoding="utf-8") as f:
                cache_data = json.load(f)
            return cache_data.get("communes", None)
        except Exception as e:
            print(f"Erreur lors du chargement du cache : {e}")
            return None

    def has_communes_cache(self):
        """Vérifie si le fichier cache des communes existe sur le disque.

        Returns:
            bool: ``True`` si le fichier cache existe, ``False`` sinon.
        """
        return os.path.exists(self.communes_cache_file)

    def clear_communes_cache(self):
        """Supprime le fichier cache des communes s'il existe.

        Returns:
            bool: ``True`` si la suppression a réussi ou si le fichier
            n'existait pas, ``False`` en cas d'erreur.
        """
        try:
            if os.path.exists(self.communes_cache_file):
                os.remove(self.communes_cache_file)
            return True
        except Exception as e:
            print(f"Erreur lors de la suppression du cache : {e}")
            return False

    def get_logfile_path(self):
        """Retourne le chemin absolu vers le fichier de log applicatif.

        Returns:
            str: Chemin vers le fichier de log.
        """
        return self.log_file
