"""
ui/generated_runs_view.py – Vue des fichiers de données générés
===============================================================
Affiche tous les fichiers produits par « Sauvegarder sous… »,
groupés par flux source dans des panneaux pliables/dépliables.

Fonctionnalités :
  • Liste complète groupée par flux avec badge de comptage
  • Barre de recherche en temps réel (filtre sur le nom du flux ou du fichier)
  • Tri : plus récent / plus ancien / nom de fichier / taille
  • Actions par fichier : ouvrir dans l'explorateur, copier le chemin,
    supprimer (avec confirmation)
  • Action par groupe : tout supprimer pour un flux donné
  • Bouton « Ouvrir le dossier racine generated/ »
  • Rafraîchissement à la demande
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess

import flet as ft

logger = logging.getLogger(__name__)

# ── Constantes visuelles ───────────────────────────────────────────────────────
_NAV_BG = "#1a1a2e"
_EXT_COLORS: dict[str, str] = {
    ".csv": "#2e7d32",
    ".json": "#1565c0",
    ".xml": "#6a1b9a",
    ".txt": "#455a64",
}
_SORT_OPTIONS = [
    ("recent", "Plus récent"),
    ("oldest", "Plus ancien"),
    ("name", "Nom"),
    ("size", "Taille"),
]


def _fmt_size(size_bytes: int) -> str:
    """Formate un nombre d'octets en chaîne lisible (o / Ko / Mo).

    Args:
        size_bytes: Taille en octets.

    Returns:
        str: Chaîne formatée, ex. ``"12 Ko"``.
    """
    if size_bytes < 1024:
        return f"{size_bytes} o"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} Ko"
    return f"{size_bytes / (1024 * 1024):.2f} Mo"


def _open_in_explorer(path: str) -> None:
    """Ouvre le chemin donné dans l'explorateur de fichiers natif.

    Sélectionne le fichier si ``path`` pointe vers un fichier,
    ouvre le dossier sinon.

    Args:
        path: Chemin absolu vers un fichier ou un dossier.
    """
    system = platform.system()
    try:
        folder = os.path.dirname(path) if os.path.isfile(path) else path

        if system == "Windows":
            subprocess.Popen(
                [
                    "explorer",
                    "/select," if os.path.isfile(path) else "",
                    path if os.path.isfile(path) else folder,
                ]
            )
        elif system == "Darwin":
            subprocess.Popen(
                [
                    "open",
                    "-R" if os.path.isfile(path) else "",
                    path if os.path.isfile(path) else folder,
                ]
            )
        else:
            subprocess.Popen(["xdg-open", folder])
    except Exception as exc:
        logger.warning("Impossible d'ouvrir l'explorateur : %s", exc)


class GeneratedRunsView:
    """Vue listant tous les fichiers de données générés.

    Les fichiers sont groupés par flux source (nom du dossier dans
    ``generated/``), dans des panneaux ``ExpansionTile`` pliables.
    Une barre de recherche et un menu de tri permettent de filtrer
    et réordonner les résultats en temps réel.

    Args:
        app: Instance de :class:`ui.app.DataFlowApp`.
    """

    def __init__(self, app) -> None:
        self.app = app
        self.storage = app.flow_manager.storage

        self._search_query: str = ""
        self._sort_key: str = "recent"  # recent | oldest | name | size

        # Widgets internes mis à jour lors des rafraîchissements
        self._content_col: ft.Column | None = None
        self._stats_text: ft.Text | None = None

    # ─── API publique ─────────────────────────────────────────────────────────

    def build(self) -> ft.Control:
        """Construit et retourne le contrôle racine de la vue.

        Returns:
            ft.Control: Conteneur principal scrollable.
        """
        self._stats_text = ft.Text("", size=12, color=ft.Colors.GREY_500)
        self._content_col = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)

        self._fill()

        return ft.Container(
            content=ft.Column(
                [
                    self._build_toolbar(),
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
                    ft.Container(
                        content=self._stats_text,
                        padding=ft.padding.only(left=4, bottom=4),
                    ),
                    self._content_col,
                ],
                spacing=0,
                expand=True,
            ),
            padding=ft.Padding.symmetric(horizontal=32, vertical=20),
            expand=True,
        )

    def refresh(self) -> None:
        """Rafraîchit la liste depuis le disque et met à jour l'affichage."""
        self._fill()

    # ─── Barre d'outils ───────────────────────────────────────────────────────

    def _build_toolbar(self) -> ft.Row:
        """Construit la barre d'outils : titre, recherche, tri, actions globales.

        Returns:
            ft.Row: Barre d'outils prête à l'affichage.
        """
        search_tf = ft.TextField(
            hint_text="Rechercher un flux ou un fichier…",
            prefix_icon=ft.Icons.SEARCH,
            border_radius=20,
            height=38,
            text_size=12,
            content_padding=ft.Padding.symmetric(horizontal=14, vertical=0),
            expand=True,
            on_change=self._on_search,
        )

        sort_dd = ft.Dropdown(
            hint_text="Trier par…",
            width=150,
            height=38,
            text_size=12,
            content_padding=ft.Padding.symmetric(horizontal=10, vertical=0),
            options=[ft.dropdown.Option(k, lbl) for k, lbl in _SORT_OPTIONS],
            value=self._sort_key,
            on_select=self._on_sort,
        )

        open_root_btn = ft.OutlinedButton(
            "Dossier generated/",
            icon=ft.Icons.FOLDER_OPEN_OUTLINED,
            tooltip="Ouvrir le dossier racine des données générées",
            on_click=lambda e: _open_in_explorer(self.storage.generated_dir),
            style=ft.ButtonStyle(
                side=ft.BorderSide(1, ft.Colors.GREY_700),
                color=ft.Colors.GREY_400,
            ),
        )

        refresh_btn = ft.IconButton(
            icon=ft.Icons.REFRESH,
            tooltip="Rafraîchir",
            icon_color=ft.Colors.GREY_400,
            on_click=lambda e: self.refresh(),
        )

        return ft.Row(
            [
                ft.Column(
                    [
                        ft.Text(
                            "Données générées",
                            size=26,
                            weight=ft.FontWeight.W_700,
                        ),
                    ],
                    spacing=2,
                ),
                ft.Container(expand=True),
                search_tf,
                ft.Container(width=10),
                sort_dd,
                ft.Container(width=6),
                open_root_btn,
                refresh_btn,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
        )

    # ─── Remplissage ──────────────────────────────────────────────────────────

    def _fill(self) -> None:
        """Recharge les données depuis le disque, applique recherche + tri,
        et reconstruit les contrôles Flet."""
        if self._content_col is None:
            return

        groups = self._load_groups()
        total_files = sum(len(runs) for _, runs in groups)
        total_flows = len(groups)

        self._content_col.controls.clear()

        # Statistiques globales
        if self._stats_text is not None:
            self._stats_text.value = (
                f"{total_files} fichier{'s' if total_files != 1 else ''} dans {total_flows} flux"
                if total_flows
                else "Aucun fichier généré."
            )

        if not groups:
            self._content_col.controls.append(self._build_empty_state())
        else:
            for flow_name, runs in groups:
                self._content_col.controls.append(self._build_flow_group(flow_name, runs))

        try:
            self._content_col.update()
            if self._stats_text:
                self._stats_text.update()
        except Exception:
            logger.debug("Widget update skipped", exc_info=True)

    def _load_groups(self) -> list[tuple[str, list[dict]]]:
        """Charge et filtre les groupes de fichiers depuis le disque.

        Parcourt ``generated_dir``, collecte les sous-dossiers comme noms
        de flux, filtre selon la recherche courante, trie les fichiers
        de chaque groupe, puis trie les groupes par ordre alphabétique.

        Returns:
            list[tuple[str, list[dict]]]: Liste de ``(nom_flux, [runs])``
            filtrée et triée.
        """
        base = self.storage.generated_dir
        if not os.path.isdir(base):
            return []

        query = self._search_query.lower().strip()
        groups: list[tuple[str, list[dict]]] = []

        for folder_name in sorted(os.listdir(base)):
            folder_path = os.path.join(base, folder_name)
            if not os.path.isdir(folder_path):
                continue

            # Chargement brut de tous les fichiers du dossier
            all_runs = self.storage.list_generated_runs(folder_name)

            # Filtrage : correspond à la recherche sur le nom du flux ou du fichier
            if query:
                filtered = [
                    r
                    for r in all_runs
                    if query in folder_name.lower() or query in r["name"].lower()
                ]
            else:
                filtered = all_runs

            if not filtered:
                continue

            # Tri des fichiers du groupe
            filtered = self._sort_runs(filtered)
            groups.append((folder_name, filtered))

        return groups

    def _sort_runs(self, runs: list[dict]) -> list[dict]:
        """Trie une liste de runs selon le critère courant.

        Args:
            runs: Liste de dicts ``{name, path, size, modified}``.

        Returns:
            list[dict]: Liste triée.
        """
        if self._sort_key == "recent":
            return sorted(runs, key=lambda r: r["modified"], reverse=True)
        if self._sort_key == "oldest":
            return sorted(runs, key=lambda r: r["modified"])
        if self._sort_key == "name":
            return sorted(runs, key=lambda r: r["name"].lower())
        if self._sort_key == "size":
            return sorted(runs, key=lambda r: r["size"], reverse=True)
        return runs

    # ─── Composants ───────────────────────────────────────────────────────────

    def _build_empty_state(self) -> ft.Container:
        """Construit le panneau vide affiché quand aucun fichier n'existe.

        Returns:
            ft.Container: Panneau centré avec icône et message.
        """
        if self._search_query:
            msg = f"Aucun résultat pour « {self._search_query} »"
            sub = "Essayez un autre terme de recherche."
            icon = ft.Icons.SEARCH_OFF_OUTLINED
        else:
            msg = "Aucune donnée générée"
            sub = (
                "Ouvrez un flux, cliquez sur « Aperçu » puis "
                "« Sauvegarder sous… » pour créer un fichier."
            )
            icon = ft.Icons.FOLDER_OFF_OUTLINED

        return ft.Container(
            content=ft.Column(
                [
                    ft.Icon(icon, size=64, color=ft.Colors.GREY_700),
                    ft.Text(msg, size=18, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_500),
                    ft.Text(sub, color=ft.Colors.GREY_600, size=12, text_align=ft.TextAlign.CENTER),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=10,
            ),
            alignment=ft.Alignment.CENTER,
            expand=True,
            padding=ft.Padding.symmetric(vertical=80),
        )

    def _build_flow_group(self, flow_name: str, runs: list[dict]) -> ft.Container:
        """Construit le panneau pliable pour un flux donné.

        Args:
            flow_name: Nom du dossier / flux source (sanitisé sur disque).
            runs: Liste triée de dicts ``{name, path, size, modified}``.

        Returns:
            ft.Container: Panneau ``ExpansionTile`` avec ses fichiers.
        """
        nb = len(runs)
        total_size = sum(r["size"] for r in runs)

        file_controls: list[ft.Control] = [self._build_file_row(r, flow_name) for r in runs]

        # En-tête du groupe
        title_row = ft.Row(
            [
                ft.Text(
                    flow_name,
                    size=13,
                    weight=ft.FontWeight.W_600,
                    color=ft.Colors.AMBER_200,
                ),
                ft.Container(
                    content=ft.Text(
                        f"{nb} fichier{'s' if nb != 1 else ''}",
                        size=10,
                        color=ft.Colors.GREY_400,
                    ),
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.WHITE),
                    border_radius=8,
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                ),
                ft.Container(
                    content=ft.Text(
                        _fmt_size(total_size),
                        size=10,
                        color=ft.Colors.GREY_500,
                    ),
                    padding=ft.padding.only(left=4),
                ),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        tile = ft.ExpansionTile(
            title=title_row,
            leading=ft.Icon(
                ft.Icons.FOLDER_OUTLINED,
                size=16,
                color=ft.Colors.AMBER_400,
            ),
            trailing=ft.Row(
                [
                    ft.IconButton(
                        icon=ft.Icons.FOLDER_OPEN_OUTLINED,
                        icon_size=16,
                        tooltip="Ouvrir le dossier dans l'explorateur",
                        icon_color=ft.Colors.GREY_500,
                        on_click=lambda e, fn=flow_name: _open_in_explorer(
                            self.storage.get_generated_folder(fn)
                        ),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_SWEEP_OUTLINED,
                        icon_size=16,
                        tooltip="Supprimer tous les fichiers de ce flux",
                        icon_color=ft.Colors.RED_400,
                        on_click=lambda e, fn=flow_name: self._confirm_delete_group(fn),
                    ),
                ],
                spacing=0,
                tight=True,
            ),
            bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.WHITE),
            collapsed_bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.WHITE),
            tile_padding=ft.Padding.symmetric(horizontal=12, vertical=4),
            controls=file_controls,
        )

        return ft.Container(
            content=tile,
            border=ft.border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.AMBER)),
            border_radius=10,
            margin=ft.margin.only(bottom=8),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )

    def _build_file_row(self, run: dict, flow_name: str) -> ft.Container:
        """Construit la ligne d'un fichier généré.

        Args:
            run: Dict ``{name, path, size, modified}`` du fichier.
            flow_name: Nom du flux parent (pour les actions de suppression).

        Returns:
            ft.Container: Ligne avec badge format, nom, taille, date et actions.
        """
        ext = os.path.splitext(run["name"])[1].lower()
        ext_color = _EXT_COLORS.get(ext, "#546e7a")

        ext_badge = ft.Container(
            content=ft.Text(
                ext.lstrip(".").upper() or "?",
                size=9,
                color=ft.Colors.WHITE,
                weight=ft.FontWeight.BOLD,
            ),
            bgcolor=ext_color,
            border_radius=4,
            padding=ft.Padding.symmetric(horizontal=5, vertical=2),
            width=38,
        )

        return ft.Container(
            content=ft.Row(
                [
                    ext_badge,
                    ft.Container(width=6),
                    ft.Text(
                        run["name"],
                        size=12,
                        expand=True,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        no_wrap=True,
                        color=ft.Colors.GREY_300,
                    ),
                    ft.Text(
                        _fmt_size(run["size"]),
                        size=11,
                        color=ft.Colors.GREY_600,
                        width=60,
                        text_align=ft.TextAlign.RIGHT,
                    ),
                    ft.Container(width=8),
                    ft.Text(
                        run["modified"],
                        size=10,
                        color=ft.Colors.GREY_700,
                        width=140,
                    ),
                    ft.Container(width=4),
                    # ── Actions ──────────────────────────────────────────────
                    ft.IconButton(
                        icon=ft.Icons.FOLDER_OPEN_OUTLINED,
                        icon_size=15,
                        tooltip="Localiser dans l'explorateur",
                        icon_color=ft.Colors.GREY_500,
                        on_click=lambda e, p=run["path"]: _open_in_explorer(p),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CONTENT_COPY_OUTLINED,
                        icon_size=15,
                        tooltip="Copier le chemin",
                        icon_color=ft.Colors.GREY_500,
                        on_click=lambda e, p=run["path"]: self._copy_path(p),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_size=15,
                        tooltip="Supprimer ce fichier",
                        icon_color=ft.Colors.RED_400,
                        on_click=lambda e, r=run, fn=flow_name: self._confirm_delete_file(r, fn),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
            ),
            bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.WHITE),
            border_radius=6,
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            margin=ft.margin.only(bottom=2),
        )

    # ─── Actions ──────────────────────────────────────────────────────────────

    def _on_search(self, e) -> None:
        """Met à jour la requête de recherche et rafraîchit l'affichage.

        Args:
            e: Événement de changement du champ de recherche.
        """
        self._search_query = e.control.value or ""
        self._fill()

    def _on_sort(self, e) -> None:
        """Met à jour le critère de tri et rafraîchit l'affichage.

        Args:
            e: Événement de changement du menu déroulant de tri.
        """
        self._sort_key = e.control.value or "recent"
        self._fill()

    def _copy_path(self, path: str) -> None:
        """Copie le chemin d'un fichier dans le presse-papier.

        Args:
            path: Chemin absolu à copier.
        """
        try:
            self.app.page.set_clipboard(path)
            self.app.show_snack(f"Chemin copié : {path}")
        except Exception as exc:
            logger.warning("Impossible de copier dans le presse-papier : %s", exc)
            self.app.show_snack("Impossible de copier le chemin.", success=False)

    def _confirm_delete_file(self, run: dict, flow_name: str) -> None:
        """Demande confirmation avant de supprimer un fichier.

        Args:
            run: Dict ``{name, path, …}`` du fichier à supprimer.
            flow_name: Nom du flux parent (pour le rafraîchissement).
        """

        def do_delete():
            try:
                os.remove(run["path"])
                self.app.show_snack(f"Fichier « {run['name']} » supprimé.")
            except Exception as exc:
                logger.error("Erreur suppression fichier : %s", exc)
                self.app.show_snack("Erreur lors de la suppression.", success=False)
            self.refresh()

        self.app.confirm(
            title="Supprimer le fichier",
            body=f"Supprimer « {run['name']} » ? Cette action est irréversible.",
            on_confirm=do_delete,
        )

    def _confirm_delete_group(self, flow_name: str) -> None:
        """Demande confirmation avant de supprimer tous les fichiers d'un flux.

        Args:
            flow_name: Nom du flux (= nom du dossier dans ``generated/``).
        """
        runs = self.storage.list_generated_runs(flow_name)
        nb = len(runs)

        def do_delete():
            errors = 0
            for r in runs:
                try:
                    os.remove(r["path"])
                except Exception as exc:
                    logger.error("Erreur suppression %s : %s", r["path"], exc)
                    errors += 1
            if errors:
                self.app.show_snack(
                    f"{nb - errors} fichier(s) supprimé(s), {errors} erreur(s).",
                    success=False,
                )
            else:
                self.app.show_snack(f"{nb} fichier(s) supprimé(s) pour « {flow_name} ».")
            self.refresh()

        self.app.confirm(
            title="Supprimer tous les fichiers",
            body=(
                f"Supprimer les {nb} fichier(s) du flux « {flow_name} » ?\n"
                "Cette action est irréversible."
            ),
            on_confirm=do_delete,
        )
