"""
Utilitaires pour interagir avec l'API Geo du gouvernement français.

Ce module gère les appels à l'API geo.api.gouv.fr pour obtenir des informations
sur les communes, codes postaux et départements français.
"""

import json
import logging
import random
import urllib.request
from typing import Any
from urllib.parse import urlencode

from core.constants import FALLBACK_COMMUNES, GEO_API_URL

logger = logging.getLogger(__name__)


class GeoAPIClient:
    """
    Client pour interagir avec l'API Geo du gouvernement français.

    Fournit des méthodes pour récupérer des informations sur les communes,
    codes postaux et départements avec gestion des erreurs et fallback.
    Utilise un cache local pour éviter les appels API répétés.
    """

    def __init__(self, storage_manager=None):
        """
        Initialise le client API.

        Args:
            storage_manager: Instance de StorageManager pour gérer le cache
        """
        self.base_url = GEO_API_URL
        self.timeout = 5  # Timeout en secondes
        self.storage_manager = storage_manager
        self.communes_cache: list[dict[str, Any]] | None = None

        # Charger le cache si disponible
        if self.storage_manager:
            self.communes_cache = self.storage_manager.load_communes_cache()
            if self.communes_cache:
                logger.info("Cache des communes chargé : %s communes", len(self.communes_cache))

    def _ensure_cache_loaded(self) -> None:
        """
        Tente un rechargement paresseux du cache depuis le disque si celui-ci
        est absent en mémoire mais a été créé après l'initialisation de l'instance
        (ex : fetch effectué dans un autre contexte, relance partielle de l'app).
        """
        if self.communes_cache is None and self.storage_manager:
            loaded = self.storage_manager.load_communes_cache()
            if loaded:
                self.communes_cache = loaded
                logger.info(
                    "Cache des communes rechargé à la demande : %s communes",
                    len(self.communes_cache),
                )

    def fetch_all_communes(self, progress_callback=None):
        """
        Récupère toutes les communes depuis l'API et les met en cache.

        Args:
            progress_callback: Fonction de callback pour indiquer la progression

        Returns:
            List[Dict]: Liste de toutes les communes
        """
        try:
            if progress_callback:
                progress_callback("Récupération des communes depuis l'API...")

            params = {
                "fields": "nom,code,codeDepartement,siren,codeEpci,"
                "codeRegion,codesPostaux,population",
                "format": "json",
            }
            url = f"{self.base_url}/communes?{urlencode(params)}"

            logger.info("Récupération de toutes les communes depuis l'API...")

            with urllib.request.urlopen(url, timeout=30) as response:
                communes = json.loads(response.read().decode("utf-8"))

            logger.info("%s communes récupérées", len(communes))

            # Mettre à jour le cache en mémoire immédiatement
            self.communes_cache = communes

            # Sauvegarder sur disque si un storage_manager est disponible
            if self.storage_manager:
                if progress_callback:
                    progress_callback(f"Sauvegarde de {len(communes)} communes...")
                self.storage_manager.save_communes_cache(communes)

            return communes

        except Exception as e:
            logger.error("Erreur lors de la récupération des communes : %s", e)
            return FALLBACK_COMMUNES

    def get_communes_cache(self):
        """
        Retourne le cache des communes.

        Returns:
            List[Dict] or None: Liste des communes en cache
        """
        self._ensure_cache_loaded()
        return self.communes_cache

    def get_commune_aleatoire(self, faker) -> dict[str, Any]:
        """
        Récupère une commune aléatoire via le cache ou Faker.

        Args:
            faker: Instance de Faker pour générer des données de secours

        Returns:
            Dict contenant nom, code, codesPostaux et codeDepartement

        Example:
            >>> client = GeoAPIClient()
            >>> commune = client.get_commune_aleatoire(faker)
            >>> print(commune['nom'])
            'Paris'
        """
        # Utiliser le cache si disponible
        self._ensure_cache_loaded()
        if self.communes_cache and len(self.communes_cache) > 0:
            commune = random.choice(self.communes_cache)
            return {
                "nom": commune["nom"],
                "code": commune.get("code", ""),
                "codesPostaux": commune.get("codesPostaux", []),
                "codeDepartement": commune.get("codeDepartement", "99"),
            }

        # Fallback sur données générées
        logger.debug("Utilisation de données générées par Faker")
        return {
            "nom": faker.city(),
            "code": str(faker.random_int(min=1001, max=95999)).zfill(5),
            "codesPostaux": [faker.postcode()],
            "codeDepartement": str(faker.random_int(min=1, max=95)).zfill(2),
        }

    def get_commune_par_code_postal(self, code_postal: str) -> dict[str, Any] | None:
        """
        Récupère une commune par son code postal depuis le cache.

        Args:
            code_postal: Code postal à rechercher (ex: "75001")

        Returns:
            Dict contenant les informations de la commune ou None

        Example:
            >>> client = GeoAPIClient()
            >>> commune = client.get_commune_par_code_postal("75001")
            >>> print(commune['nom'])
            'Paris'
        """
        # Rechercher dans le cache
        self._ensure_cache_loaded()
        if self.communes_cache:
            for commune in self.communes_cache:
                if code_postal in commune.get("codesPostaux", []):
                    logger.info(
                        "Commune trouvée dans le cache: %s pour CP %s",
                        commune["nom"],
                        {code_postal},
                    )
                    return commune

        # Recherche dans les communes de fallback
        logger.debug("Recherche dans les communes de fallback pour %s", code_postal)
        for commune in FALLBACK_COMMUNES:
            if code_postal in commune.get("codesPostaux", []):
                return commune

        return None

    def get_commune_par_code_insee(self, code_insee: str) -> dict[str, Any] | None:
        """
        Récupère une commune par son code INSEE depuis le cache.

        Args:
            code_insee: Code INSEE à rechercher (ex: "75056")

        Returns:
            Dict contenant les informations de la commune ou None
        """
        # Rechercher dans le cache
        self._ensure_cache_loaded()
        if self.communes_cache:
            for commune in self.communes_cache:
                if commune.get("code") == code_insee:
                    logger.info(
                        "Commune trouvée dans le cache: %s pour code INSEE %s",
                        commune["nom"],
                        code_insee,
                    )
                    return commune

        # Recherche dans les communes de fallback
        logger.debug("Recherche dans les communes de fallback pour code INSEE %s", code_insee)
        for commune in FALLBACK_COMMUNES:
            if commune.get("code") == code_insee:
                return commune

        return None

    def get_codes_postaux_par_filtre(self, filtre: str) -> list[str]:
        """
        Récupère les codes postaux correspondant à un filtre avec support des wildcards.
        Utilise le cache local des communes.
        Exemples :
            - "33*" : codes postaux commençant par 33
            - "*10*" : codes postaux contenant 10
            - "*25" : codes postaux finissant par 25
            - "*" : aucun filtre (tous les codes postaux)

        Args:
            filtre: Pattern de filtrage (ex: "33*", "*10*", "*25", "*")

        Returns:
            Liste des codes postaux correspondants
        """
        codes = []

        # Utiliser le cache si disponible
        self._ensure_cache_loaded()
        if self.communes_cache:
            # Extraire tous les codes postaux du cache
            all_codes = []
            for commune in self.communes_cache:
                all_codes.extend(commune.get("codesPostaux", []))

            # Supprimer les doublons
            all_codes = list(set(all_codes))

            # Filtrer selon le pattern
            codes = self._filter_codes_postaux(all_codes, filtre)

            if codes:
                return codes

        # Fallback : générer des codes postaux selon le filtre
        logger.warning("Cache non disponible, génération de codes selon le filtre '%s'", filtre)

        if filtre == "*":
            # Retourner quelques codes aléatoires
            return [f"{random.randint(1000, 95999):05d}" for _ in range(10)]
        elif filtre.endswith("*"):
            # Codes commençant par le préfixe
            prefix = filtre[:-1]
            return [prefix + f"{i:0{5 - len(prefix)}d}" for i in range(10)]
        else:
            return [filtre] if filtre.isdigit() and len(filtre) == 5 else []

    def _filter_codes_postaux(self, codes: list[str], filtre: str) -> list[str]:
        """
        Filtre une liste de codes postaux selon un pattern.

        Args:
            codes: Liste de codes postaux à filtrer
            filtre: Pattern de filtrage (ex: "33*", "*10*", "*25")

        Returns:
            Liste filtrée de codes postaux
        """
        if filtre == "*":
            return codes

        filtered = []

        if filtre.startswith("*") and filtre.endswith("*"):
            # Contient: *10*
            pattern = filtre.strip("*")
            filtered = [code for code in codes if pattern in code]

        elif filtre.startswith("*"):
            # Finit par: *25
            pattern = filtre[1:]
            filtered = [code for code in codes if code.endswith(pattern)]

        elif filtre.endswith("*"):
            # Commence par: 33*
            pattern = filtre[:-1]
            filtered = [code for code in codes if code.startswith(pattern)]

        else:
            # Exact match
            filtered = [code for code in codes if code == filtre]

        return filtered

    def get_code_postal_aleatoire(self, filtre: str = "*") -> str:
        """
        Génère un code postal aléatoire selon un filtre.

        Args:
            filtre: Pattern de filtrage (défaut: "*" pour tous les codes)

        Returns:
            Code postal aléatoire correspondant au filtre

        Example:
            >>> client = GeoAPIClient()
            >>> code = client.get_code_postal_aleatoire("75*")
            >>> print(code)
            '75008'
        """
        codes = self.get_codes_postaux_par_filtre(filtre)

        if codes:
            code = random.choice(codes)
            logger.debug("Code postal aléatoire généré: %s (filtre: %s)", code, filtre)
            return code

        # Si aucun code trouvé, générer un code générique
        logger.warning("Aucun code postal trouvé pour le filtre '%s', génération aléatoire", filtre)
        return f"{random.randint(1000, 99999):05d}"
