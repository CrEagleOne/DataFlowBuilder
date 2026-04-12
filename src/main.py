#!/usr/bin/env python3
"""
Data Flow Builder – Point d'entrée principal (Flet)
====================================================
Génère des fichiers de données de test avec des champs personnalisables.

Author : Data Flow Builder Team
"""

import logging
import sys

import flet as ft

from core.storage import StorageManager
from views.app import DataFlowApp

# ── Configuration du logging ─────────────────────────────────────────────────
_storage = StorageManager()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.FileHandler(_storage.get_logfile_path(), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def main(page: ft.Page) -> None:
    """
    Point d'entrée Flet.  Appelé par ``ft.app()`` avec la page initialisée.

    Args:
        page: Instance de la page Flet fournie par le runtime.
    """

    logger.info("Démarrage de Data Flow Builder")
    app = DataFlowApp(page)
    app.initialize()


if __name__ == "__main__":
    ft.run(main)
