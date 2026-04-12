"""
Tests unitaires — core/geo_api.py

Les tests marqués @pytest.mark.network appellent l'API réelle.
Ils sont désactivés par défaut en CI ; lancez-les avec :
    pytest -m network
"""

from unittest.mock import MagicMock

import pytest
from faker import Faker

from core.constants import FALLBACK_COMMUNES
from core.geo_api import GeoAPIClient

# ── Fixture ───────────────────────────────────────────────────────────────────


@pytest.fixture
def client_no_cache():
    """Client sans storage (pas de cache)."""
    return GeoAPIClient(storage_manager=None)


@pytest.fixture
def client_with_cache():
    """Client avec cache préchargé depuis les communes de fallback."""
    mock_storage = MagicMock()
    mock_storage.load_communes_cache.return_value = FALLBACK_COMMUNES
    client = GeoAPIClient(storage_manager=mock_storage)
    return client


# ── Initialisation ────────────────────────────────────────────────────────────


class TestInit:
    def test_no_cache_without_storage(self, client_no_cache):
        assert client_no_cache.communes_cache is None

    def test_cache_loaded_from_storage(self, client_with_cache):
        assert client_with_cache.communes_cache is not None
        assert len(client_with_cache.communes_cache) > 0


# ── get_commune_aleatoire ─────────────────────────────────────────────────────


class TestGetCommuneAleatoire:
    def test_returns_dict_with_required_keys(self, client_with_cache):
        faker = Faker("fr_FR")
        commune = client_with_cache.get_commune_aleatoire(faker)
        for key in ("nom", "code", "codesPostaux", "codeDepartement"):
            assert key in commune

    def test_uses_faker_when_no_cache(self, client_no_cache):
        faker = Faker("fr_FR")
        commune = client_no_cache.get_commune_aleatoire(faker)
        assert isinstance(commune["nom"], str)
        assert len(commune["nom"]) > 0


# ── get_commune_par_code_postal ───────────────────────────────────────────────


class TestGetCommuneParCodePostal:
    def test_found_in_cache(self, client_with_cache):
        commune = client_with_cache.get_commune_par_code_postal("75001")
        assert commune is not None
        assert commune["nom"] == "Paris"

    def test_found_in_fallback(self, client_no_cache):
        commune = client_no_cache.get_commune_par_code_postal("75001")
        assert commune is not None
        assert commune["nom"] == "Paris"

    def test_not_found_returns_none(self, client_no_cache):
        result = client_no_cache.get_commune_par_code_postal("00000")
        assert result is None

    def test_bordeaux_found(self, client_no_cache):
        commune = client_no_cache.get_commune_par_code_postal("33000")
        assert commune is not None
        assert commune["nom"] == "Bordeaux"


# ── get_commune_par_code_insee ────────────────────────────────────────────────


class TestGetCommuneParCodeInsee:
    def test_found_paris(self, client_with_cache):
        commune = client_with_cache.get_commune_par_code_insee("75056")
        assert commune is not None
        assert commune["nom"] == "Paris"

    def test_not_found_returns_none(self, client_with_cache):
        assert client_with_cache.get_commune_par_code_insee("99999") is None


# ── _filter_codes_postaux ─────────────────────────────────────────────────────


class TestFilterCodesPostaux:
    CODES = ["75001", "75008", "33000", "33100", "13001", "69003"]

    def test_wildcard_all(self, client_no_cache):
        result = client_no_cache._filter_codes_postaux(self.CODES, "*")
        assert set(result) == set(self.CODES)

    def test_prefix_filter(self, client_no_cache):
        result = client_no_cache._filter_codes_postaux(self.CODES, "75*")
        assert set(result) == {"75001", "75008"}

    def test_suffix_filter(self, client_no_cache):
        result = client_no_cache._filter_codes_postaux(self.CODES, "*001")
        assert set(result) == {"75001", "13001"}

    def test_contains_filter(self, client_no_cache):
        result = client_no_cache._filter_codes_postaux(self.CODES, "*300*")
        assert set(result) == {"33000", "13001"}

    def test_exact_match(self, client_no_cache):
        result = client_no_cache._filter_codes_postaux(self.CODES, "69003")
        assert result == ["69003"]

    def test_no_match_returns_empty(self, client_no_cache):
        result = client_no_cache._filter_codes_postaux(self.CODES, "99*")
        assert result == []


# ── get_code_postal_aleatoire ─────────────────────────────────────────────────


class TestGetCodePostalAleatoire:
    def test_returns_string(self, client_with_cache):
        code = client_with_cache.get_code_postal_aleatoire("75*")
        assert isinstance(code, str)
        assert code.startswith("75")

    def test_wildcard_returns_some_code(self, client_with_cache):
        code = client_with_cache.get_code_postal_aleatoire("*")
        assert isinstance(code, str)
        assert len(code) == 5

    def test_fallback_when_no_cache(self, client_no_cache):
        code = client_no_cache.get_code_postal_aleatoire("*")
        assert isinstance(code, str)
        assert len(code) == 5


# ── Tests réseau réels (désactivés par défaut) ────────────────────────────────


@pytest.mark.network
class TestNetworkFetchCommunes:
    def test_fetch_returns_list(self):
        client = GeoAPIClient(storage_manager=None)
        communes = client.fetch_all_communes()
        assert isinstance(communes, list)
        assert len(communes) > 1000

    def test_fetch_commune_has_required_fields(self):
        client = GeoAPIClient(storage_manager=None)
        communes = client.fetch_all_communes()
        first = communes[0]
        assert "nom" in first
        assert "code" in first
