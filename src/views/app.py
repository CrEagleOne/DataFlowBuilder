"""
ui/app.py – Contrôleur principal de Data Flow Builder (Flet)
"""

import logging
import threading

import flet as ft

from core.flow_manager import FlowManager
from core.geo_api import GeoAPIClient
from core.storage import StorageManager
from utils import FAVICON_ICO_B64
from views.editor import EditorView
from views.folder_tree import FolderTreeView
from views.generated_runs_view import GeneratedRunsView
from views.home import HomeView

logger = logging.getLogger(__name__)

ACCENT = ft.Colors.BLUE_400
NAV_BG = "#1a1a2e"
CONTENT_BG = "#16213e"
_storage = StorageManager()


class DataFlowApp:
    """Orchestrateur principal de l'application."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.flow_manager = FlowManager()
        self._current_sections: dict = {}
        self.selected_folder_id: str = FolderTreeView.ALL

        self._content_area: ft.Container | None = None
        self._loading_overlay: ft.Container | None = None
        self._loading_label: ft.Text | None = None
        self._current_dialog: ft.AlertDialog | None = None
        self._dialog_stack: list[ft.AlertDialog] = []
        self._folder_tree: FolderTreeView | None = None
        self._home_view: HomeView | None = None
        # Pastille de comptage dans l'AppBar pour les fichiers générés
        self._runs_badge: ft.Stack | None = None
        self._runs_badge_pip: ft.Container | None = None
        self._runs_badge_text: ft.Text | None = None

    # ═══════════════════════════════════════════════════════════════════════════
    # Initialisation
    # ═══════════════════════════════════════════════════════════════════════════

    def initialize(self) -> None:
        """Initialise la page, construit le layout, affiche l'accueil et
        lance les tâches de fond."""
        self._configure_page()
        self._build_layout()
        self.show_home()
        threading.Thread(target=self._init_background, daemon=True).start()

    def _configure_page(self) -> None:
        """Configure les propriétés de base de la page Flet."""
        p = self.page
        p.title = "Data Flow Builder"
        p.theme_mode = ft.ThemeMode.DARK
        p.bgcolor = CONTENT_BG
        p.padding = 0
        p.spacing = 0
        p.theme = ft.Theme(color_scheme_seed=ft.Colors.BLUE, use_material3=True)
        p.window.min_width = 900
        p.window.min_height = 640
        p.window.width = 1280
        p.window.height = 800
        p.window.icon = _storage.get_icon_path()

    # ═══════════════════════════════════════════════════════════════════════════
    # Construction du layout
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_layout(self) -> None:
        """Construit le layout global : AppBar, sidebar et zone de contenu."""
        nav_logo = ft.Image(
            src=f"data:image/x-icon;base64,{FAVICON_ICO_B64}",
            width=36,
            height=36,
            fit=ft.BoxFit(value="contain"),
            tooltip="Data Flow Builder",
        )

        # ── Badge de comptage des fichiers générés ────────────────────────────
        # Badge de comptage : Stack icône + pastille numérique en surimpression
        self._runs_badge_text = ft.Text(
            "", size=8, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD
        )
        self._runs_badge_pip = ft.Container(
            content=self._runs_badge_text,
            bgcolor=ft.Colors.GREEN_700,
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=3, vertical=1),
            visible=False,
            right=0,
            top=0,
        )
        self._runs_badge = ft.Stack(
            [
                ft.Icon(ft.Icons.DATASET_OUTLINED, color=ft.Colors.GREY_300, size=20),
                self._runs_badge_pip,
            ],
            width=24,
            height=24,
        )

        # ── AppBar ────────────────────────────────────────────────────────────
        self.page.appbar = ft.AppBar(
            leading=ft.Container(
                content=nav_logo,
                padding=ft.padding.only(left=14),
            ),
            leading_width=46,
            title=ft.Text(
                "Data Flow Builder", size=18, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE
            ),
            center_title=False,
            bgcolor="#0f0f23",
            elevation=0,
            actions=[
                # Bouton Accueil
                ft.TextButton(
                    "Accueil",
                    icon=ft.Icons.HOME_ROUNDED,
                    on_click=lambda e: self.show_home(),
                    style=ft.ButtonStyle(color=ft.Colors.GREY_300),
                ),
                # Bouton Données générées avec badge compteur
                ft.Container(
                    content=ft.TextButton(
                        content=ft.Row(
                            [
                                self._runs_badge,
                                ft.Text(
                                    "Données générées",
                                    size=13,
                                    color=ft.Colors.GREY_300,
                                ),
                            ],
                            spacing=6,
                            tight=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        on_click=lambda e: self.show_generated_runs(),
                        tooltip="Voir tous les fichiers de données générés",
                    ),
                    padding=ft.Padding.symmetric(horizontal=4),
                ),
                # Bouton Nouveau flux
                ft.Container(
                    content=ft.ElevatedButton(
                        "Nouveau flux",
                        icon=ft.Icons.ADD,
                        on_click=lambda e: self.show_editor(None),
                        style=ft.ButtonStyle(
                            bgcolor=ft.Colors.BLUE_700,
                            color=ft.Colors.WHITE,
                        ),
                    ),
                    padding=ft.padding.only(right=8),
                ),
                ft.IconButton(
                    icon=ft.Icons.INFO_OUTLINE,
                    icon_color=ft.Colors.GREY_500,
                    tooltip="À propos",
                    on_click=self._show_about,
                ),
                ft.Container(width=4),
            ],
        )

        # ── Sidebar : arbre seul ──────────────────────────────────────────────
        self._folder_tree = FolderTreeView(self, on_select=self._on_folder_select)
        tree_widget = self._folder_tree.build()

        sidebar_header = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.FOLDER_COPY_OUTLINED, size=13, color=ft.Colors.GREY_600),
                    ft.Text(
                        "DOSSIERS", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_600
                    ),
                ],
                spacing=6,
            ),
            padding=ft.padding.only(left=12, top=14, bottom=6),
        )

        sidebar = ft.Container(
            content=ft.Column(
                [
                    sidebar_header,
                    tree_widget,
                    ft.Container(
                        content=ft.Text("v1.0", size=10, color=ft.Colors.GREY_800),
                        padding=ft.padding.only(left=12, bottom=10),
                    ),
                ],
                spacing=0,
                expand=True,
            ),
            width=170,
            bgcolor=NAV_BG,
        )

        # ── Zone de contenu ───────────────────────────────────────────────────
        self._content_area = ft.Container(expand=True, bgcolor=CONTENT_BG)

        # ── Overlay de chargement ─────────────────────────────────────────────
        self._loading_label = ft.Text("Chargement…", size=15, color=ft.Colors.WHITE)
        self._loading_overlay = ft.Container(
            visible=False,
            bgcolor=ft.Colors.with_opacity(0.75, ft.Colors.BLACK),
            expand=True,
            content=ft.Column(
                [ft.ProgressRing(color=ACCENT, stroke_width=3), self._loading_label],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=18,
            ),
        )

        main_row = ft.Row(
            [
                sidebar,
                ft.VerticalDivider(width=1, color=ft.Colors.with_opacity(0.10, ft.Colors.WHITE)),
                self._content_area,
            ],
            expand=True,
            spacing=0,
        )
        self.page.add(ft.Stack([main_row, self._loading_overlay], expand=True))

        # Premier calcul du badge après construction du layout
        self._refresh_runs_badge()

    # ═══════════════════════════════════════════════════════════════════════════
    # Badge « Données générées »
    # ═══════════════════════════════════════════════════════════════════════════

    def _refresh_runs_badge(self) -> None:
        """Recalcule le compteur de fichiers générés et met à jour la pastille
        dans l'AppBar.

        Compte tous les fichiers présents dans les sous-dossiers de
        ``generated/`` et affiche le total dans la pastille. Celle-ci est
        masquée quand aucun fichier n'existe.
        """
        if self._runs_badge_pip is None:
            return
        assert self._runs_badge_text is not None
        base = self.flow_manager.storage.generated_dir
        total = 0
        try:
            if os.path.isdir(base):
                for folder_name in os.listdir(base):
                    folder_path = os.path.join(base, folder_name)
                    if os.path.isdir(folder_path):
                        total += sum(
                            1
                            for f in os.listdir(folder_path)
                            if os.path.isfile(os.path.join(folder_path, f))
                        )
        except Exception as exc:
            logger.debug("Badge runs : erreur lecture disque : %s", exc)

        self._runs_badge_text.value = str(total) if total else ""
        self._runs_badge_pip.visible = total > 0
        try:
            self._runs_badge_pip.update()
        except Exception:
            logger.debug("runs badge update skipped")

    # ═══════════════════════════════════════════════════════════════════════════
    # Callbacks dossier
    # ═══════════════════════════════════════════════════════════════════════════

    def _on_folder_select(self, folder_id: str) -> None:
        """Transmet la sélection de dossier à la vue d'accueil.

        Args:
            folder_id: Identifiant du dossier sélectionné.
        """
        self.selected_folder_id = folder_id
        if self._home_view is not None:
            self._home_view.set_folder_filter(folder_id)

    def refresh_folder_tree(self) -> None:
        """Demande à l'arbre de dossiers de se rafraîchir."""
        if self._folder_tree:
            self._folder_tree.refresh()

    def refresh_home_view(self) -> None:
        """Demande à la vue d'accueil de se rafraîchir."""
        if self._home_view is not None:
            self._home_view._refresh()

    # ═══════════════════════════════════════════════════════════════════════════
    # Navigation
    # ═══════════════════════════════════════════════════════════════════════════

    def show_home(self) -> None:
        """Navigue vers la vue d'accueil (liste des flux)."""
        self._current_sections.clear()
        self._home_view = HomeView(self)
        assert self._content_area is not None
        self._content_area.content = self._home_view.build()
        self.page.update()

    def show_editor(self, flow: dict | None) -> None:
        """Navigue vers l'éditeur de flux.

        Args:
            flow: Flux existant à charger, ou ``None`` pour créer un nouveau flux.
        """
        self._current_sections.clear()
        self._home_view = None

        if flow:
            self.flow_manager.load_flow(flow)
        else:
            self.flow_manager.create_new_flow()
            fid = self.selected_folder_id
            if fid not in (FolderTreeView.ALL, FolderTreeView.NONE):
                self.flow_manager.update_flow_field("folderId", fid)

        view = EditorView(self)
        assert self._content_area is not None
        self._content_area.content = view.build()
        self.page.update()

    def show_generated_runs(self) -> None:
        """Navigue vers la vue des fichiers de données générés.

        Efface les sections courantes, instancie :class:`GeneratedRunsView`
        et met à jour le badge de l'AppBar.
        """
        self._current_sections.clear()
        self._home_view = None
        view = GeneratedRunsView(self)
        assert self._content_area is not None
        self._content_area.content = view.build()
        self._refresh_runs_badge()
        self.page.update()

    # ═══════════════════════════════════════════════════════════════════════════
    # Helpers UI
    # ═══════════════════════════════════════════════════════════════════════════

    def show_loading(self, message: str = "Chargement…") -> None:
        """Affiche l'overlay de chargement avec un message personnalisé.

        Args:
            message: Texte affiché sous l'indicateur de progression.
        """
        if self._loading_overlay:
            assert self._loading_label is not None
            self._loading_label.value = message
            self._loading_overlay.visible = True
            self.page.update()

    def hide_loading(self) -> None:
        """Masque l'overlay de chargement."""
        if self._loading_overlay:
            self._loading_overlay.visible = False
            self.page.update()

    def show_snack(self, message: str, success: bool = True) -> None:
        """Affiche une notification temporaire (SnackBar) en bas de l'écran.

        Args:
            message: Texte de la notification.
            success: ``True`` → fond vert, ``False`` → fond rouge.
        """
        snack = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.Colors.GREEN_800 if success else ft.Colors.RED_800,
            duration=3000,
        )
        self.page.overlay.append(snack)
        snack.open = True
        self.page.update()

    def open_dialog(self, dialog: ft.AlertDialog) -> None:
        """Affiche un dialogue modal en le remplaçant si nécessaire.

        Args:
            dialog: Dialogue Flet à afficher.
        """
        if self._current_dialog is not None and self._current_dialog is not dialog:
            self._current_dialog.open = False
        self._current_dialog = dialog
        if dialog not in self.page.overlay:
            self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()

    def open_sub_dialog(self, dialog: ft.AlertDialog) -> None:
        """Empile le dialogue courant et affiche un nouveau dialogue par-dessus.

        Args:
            dialog: Dialogue secondaire à afficher.
        """
        if self._current_dialog is not None:
            self._dialog_stack.append(self._current_dialog)
        self._current_dialog = dialog
        if dialog not in self.page.overlay:
            self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()

    def close_sub_dialog(self) -> None:
        """Ferme le dialogue courant et restaure le dialogue parent si présent."""
        if self._current_dialog is not None:
            self._current_dialog.open = False
        if self._dialog_stack:
            parent = self._dialog_stack.pop()
            self._current_dialog = parent
            parent.open = True
            self.page.update()
        else:
            self._current_dialog = None
            self.page.update()

    def close_dialog(self) -> None:
        """Ferme le dialogue modal courant."""
        if self._current_dialog is None:
            return
        dlg = self._current_dialog
        if self._dialog_stack:
            self._current_dialog = None
            dlg.open = False
            parent = self._dialog_stack.pop()
            self._current_dialog = parent
            parent.open = True
            self.page.update()
        else:
            self._current_dialog = None
            dlg.open = False
            dlg.update()

    def confirm(self, title: str, body: str, on_confirm) -> None:
        """Affiche un dialogue de confirmation standardisé.

        Args:
            title: Titre du dialogue.
            body: Message de confirmation.
            on_confirm: Callable appelé si l'utilisateur confirme.
        """

        def _do_confirm(e) -> None:
            self.close_dialog()
            on_confirm()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(title, weight=ft.FontWeight.BOLD),
            content=ft.Text(body),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self.close_dialog()),
                ft.ElevatedButton(
                    "Confirmer",
                    on_click=_do_confirm,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.RED_700),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.open_dialog(dlg)

    def refresh_current_tab(self) -> None:
        """Rafraîchit toutes les sections de l'onglet actif (éditeur)."""
        for section_obj in self._current_sections.values():
            if hasattr(section_obj, "refresh"):
                section_obj.refresh()

    # ═══════════════════════════════════════════════════════════════════════════
    # Tâche de fond
    # ═══════════════════════════════════════════════════════════════════════════

    def _init_background(self) -> None:
        """Charge le cache des communes françaises en arrière-plan si absent."""
        try:
            if not self.flow_manager.storage.has_communes_cache():
                logger.info("Chargement du cache communes depuis l'API…")
                client = GeoAPIClient(self.flow_manager.storage)
                communes = client.fetch_all_communes()
                logger.info("%d communes mises en cache.", len(communes))
        except Exception as exc:
            logger.error("Erreur init background : %s", exc)

    # ═══════════════════════════════════════════════════════════════════════════
    # À propos
    # ═══════════════════════════════════════════════════════════════════════════

    def _show_about(self, e) -> None:
        """Affiche le dialogue « À propos ».

        Args:
            e: Événement de clic (non utilisé).
        """
        self.open_dialog(
            ft.AlertDialog(
                title=ft.Text("À propos de Data Flow Builder", weight=ft.FontWeight.BOLD),
                content=ft.Column(
                    [
                        ft.Text("Version 1.0  •  Interface Flet", color=ft.Colors.GREY_400),
                        ft.Divider(),
                        ft.Text("Génère des fichiers de données de test structurés."),
                        ft.Text("Fonctionnalités :", weight=ft.FontWeight.W_500),
                        *[
                            ft.Text(f"  • {feature}", size=13)
                            for feature in [
                                "Formats : CSV, Longueur fixe, XML, JSON",
                                "En-tête, données (multi-lignes) et pied de page",
                                "22 types de champs (noms, adresses, IBAN, NIR…)",
                                "Presets et valeurs prédéfinies par champ",
                                "API communes françaises avec cache local",
                                "Organisation des flux en dossiers (drag & drop)",
                                "Données générées sauvegardées et consultables",
                            ]
                        ],
                    ],
                    spacing=8,
                    tight=True,
                    width=400,
                ),
                actions=[ft.TextButton("Fermer", on_click=lambda e: self.close_dialog())],
            )
        )


# ── import os requis pour _refresh_runs_badge ──────────────────────────────────
import os  # noqa: E402  (en bas pour respecter la logique du module)
