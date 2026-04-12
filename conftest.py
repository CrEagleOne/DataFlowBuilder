"""
Configuration pytest globale.

Informations
-------------------
Sur Windows, Python utilise la méthode ``spawn`` pour les processus et
``ProactorEventLoop`` pour asyncio. Cela provoque un blocage indéfini quand
``DataGenerator(storage)`` tente un appel réseau réel à l'API geo-communes
dès que le cache est absent (premier lancement sur un ``tmp_path`` vide).

Le fixture ``_mock_geo_fetch`` intercepte ce chemin pour tous les tests
qui ne portent pas le marqueur ``@pytest.mark.network``.
"""

from unittest.mock import patch

import pytest

# ── Marqueur réseau ──────────────────────────────────────────────────────────


def pytest_configure(config):
    """Enregistre le marqueur ``network`` pour éviter les avertissements."""
    config.addinivalue_line(
        "markers",
        "network: marque les tests qui appellent l'API réelle (désactivés par défaut).",
    )


# ── Mock global de l'API géo ─────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _mock_geo_fetch(request):
    """
    Empêche tout appel réseau vers l'API communes pendant les tests unitaires.

    Raison du blocage Windows
    ~~~~~~~~~~~~~~~~~~~~~~~~~
    ``FlowManager.__init__`` instancie ``DataGenerator(self.storage)``.
    Si ``DataGenerator`` crée un ``GeoAPIClient`` avec un vrai storage
    (cache absent dans ``tmp_path``), il appelle ``fetch_all_communes()``
    — une requête HTTP sans timeout — qui se fige indéfiniment sur Windows
    (pas de ``SIGALRM``, comportement ``socket`` différent avec Proactor).

    Ce fixture remplace ``fetch_all_communes`` par un retour immédiat des
    communes de fallback intégrées, pour tous les tests non-réseau.
    """
    if request.node.get_closest_marker("network"):
        # Laisser passer les vrais appels pour les tests marqués @network
        yield
        return

    try:
        from core.constants import FALLBACK_COMMUNES

        fallback = FALLBACK_COMMUNES
    except ImportError:
        fallback = []

    with patch(
        "core.geo_api.GeoAPIClient.fetch_all_communes",
        return_value=fallback,
    ):
        yield
