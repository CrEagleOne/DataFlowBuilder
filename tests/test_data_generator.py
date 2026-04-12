"""
Tests unitaires — core/data_generator.py
"""

import re
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from core.data_generator import DataGenerator

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def gen():
    return DataGenerator(storage_manager=None)


@pytest.fixture
def gen_with_geo():
    """Générateur avec geo_client mocké."""
    g = DataGenerator(storage_manager=None)
    mock_geo = MagicMock()
    mock_geo.get_code_postal_aleatoire.return_value = "75001"
    mock_geo.get_commune_par_code_postal.return_value = {
        "nom": "Paris",
        "code": "75056",
        "codesPostaux": ["75001"],
        "codeDepartement": "75",
    }
    mock_geo.get_commune_aleatoire.return_value = {
        "nom": "Lyon",
        "code": "69123",
        "codesPostaux": ["69001"],
        "codeDepartement": "69",
    }
    mock_geo.get_codes_postaux_par_filtre.return_value = ["75001", "75008"]
    g.geo_client = mock_geo
    return g


def _field(base, sub="none", **kwargs):
    return {
        "id": "test_field",
        "type": base,
        "subType": sub,
        "length": kwargs.pop("length", 20),
        **kwargs,
    }


# ── Résolution de type ────────────────────────────────────────────────────────


class TestResolveType:
    def test_known_base_type(self, gen):
        assert gen._resolve_type({"type": "alpha", "subType": "email"}) == ("alpha", "email")

    def test_missing_subtype_defaults_to_none(self, gen):
        _, sub = gen._resolve_type({"type": "alpha"})
        assert sub == "none"

    def test_unknown_type_returned_as_is(self, gen):
        base, sub = gen._resolve_type({"type": "inexistant"})
        assert base == "inexistant"
        assert sub == "none"


# ── Booléens ─────────────────────────────────────────────────────────────────


class TestGenBool:
    @pytest.mark.parametrize(
        "sub, expected",
        [
            ("ON", {"O", "N"}),
            ("OUINON", {"OUI", "NON"}),
            ("OKKO", {"OK", "KO"}),
            ("BINAIRE", {"0", "1"}),
            ("none", {"OUI", "NON"}),
        ],
    )
    def test_values_in_expected_set(self, gen, sub, expected):
        results = {gen._gen_bool(sub) for _ in range(40)}
        assert results == expected


# ── Dates ─────────────────────────────────────────────────────────────────────


class TestGenDate:
    def test_format_ddmmyyyy(self, gen):
        val = gen._gen_date("none", _field("date", format="DD/MM/YYYY"))
        assert re.match(r"^\d{2}/\d{2}/\d{4}$", val)

    def test_format_yyyymmdd(self, gen):
        val = gen._gen_date("none", _field("date", format="YYYYMMDD"))
        assert re.match(r"^\d{8}$", val)

    def test_format_timestamp(self, gen):
        val = gen._gen_date("none", _field("date", format="timestamp"))
        assert int(val) != 0

    def test_format_long(self, gen):
        val = gen._gen_date("none", _field("date", format="YYYYMMDDHHmmss"))
        assert re.match(r"^\d{14}$", val)

    def test_today_date(self, gen):
        expected = datetime.now().strftime("%d/%m/%Y")
        assert (
            gen._gen_date("none", _field("date", format="DD/MM/YYYY", todayDate=True)) == expected
        )

    def test_date_naissance_from_nir(self, gen):
        nir_data = gen._build_nir()
        fields_data = {"_nir_data": nir_data}
        val = gen._gen_date("dateNaissance", _field("date", format="DD/MM/YYYY"), fields_data)
        assert re.match(r"^\d{2}/\d{2}/\d{4}$", val)

    def test_format_ddmmyyyy_hhmmss(self, gen):
        val = gen._gen_date("none", _field("date", format="DD/MM/YYYY HH:mm:ss"))
        assert re.match(r"^\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}$", val)

    def test_format_yyyymmdd_hyphen(self, gen):
        val = gen._gen_date("none", _field("date", format="YYYY-MM-DD"))
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", val)


class TestRandomDateInRange:
    def _parse(self, s, fmt="%d/%m/%Y"):
        return datetime.strptime(s, fmt)

    def test_no_bounds_returns_valid_date(self, gen):
        val = gen._random_date_in_range(
            _field("date", format="DD/MM/YYYY", dateMinEnabled=False, dateMaxEnabled=False)
        )
        assert isinstance(val, datetime)

    def test_min_bound_inclusive(self, gen):
        d_min = datetime(2020, 1, 1)
        field = _field(
            "date",
            format="DD/MM/YYYY",
            dateMinEnabled=True,
            dateMinToday=False,
            dateMinExclusive=False,
            dateMin="01/01/2020",
            dateMaxEnabled=True,
            dateMaxToday=False,
            dateMaxExclusive=False,
            dateMax="31/12/2020",
        )
        for _ in range(50):
            assert gen._random_date_in_range(field) >= d_min

    def test_max_bound_inclusive(self, gen):
        d_max = datetime(2020, 12, 31)
        field = _field(
            "date",
            format="DD/MM/YYYY",
            dateMinEnabled=True,
            dateMinToday=False,
            dateMinExclusive=False,
            dateMin="01/01/2020",
            dateMaxEnabled=True,
            dateMaxToday=False,
            dateMaxExclusive=False,
            dateMax="31/12/2020",
        )
        for _ in range(50):
            assert gen._random_date_in_range(field) <= d_max

    def test_min_exclusive(self, gen):
        d_min = datetime(2020, 6, 15)
        field = _field(
            "date",
            format="DD/MM/YYYY",
            dateMinEnabled=True,
            dateMinToday=False,
            dateMinExclusive=True,
            dateMin="15/06/2020",
            dateMaxEnabled=True,
            dateMaxToday=False,
            dateMaxExclusive=False,
            dateMax="20/06/2020",
        )
        for _ in range(50):
            assert gen._random_date_in_range(field) > d_min

    def test_max_exclusive(self, gen):
        d_max = datetime(2020, 6, 20)
        field = _field(
            "date",
            format="DD/MM/YYYY",
            dateMinEnabled=True,
            dateMinToday=False,
            dateMinExclusive=False,
            dateMin="15/06/2020",
            dateMaxEnabled=True,
            dateMaxToday=False,
            dateMaxExclusive=True,
            dateMax="20/06/2020",
        )
        for _ in range(50):
            assert gen._random_date_in_range(field) < d_max

    def test_min_today(self, gen):
        field = _field(
            "date",
            format="DD/MM/YYYY",
            dateMinEnabled=True,
            dateMinToday=True,
            dateMinExclusive=False,
            dateMin="",
            dateMaxEnabled=True,
            dateMaxToday=False,
            dateMaxExclusive=False,
            dateMax="31/12/2099",
        )
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        for _ in range(20):
            assert gen._random_date_in_range(field) >= today

    def test_max_today(self, gen):
        field = _field(
            "date",
            format="DD/MM/YYYY",
            dateMinEnabled=True,
            dateMinToday=False,
            dateMinExclusive=False,
            dateMin="01/01/1900",
            dateMaxEnabled=True,
            dateMaxToday=True,
            dateMaxExclusive=False,
            dateMax="",
        )
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        for _ in range(20):
            assert gen._random_date_in_range(field) <= today

    @pytest.mark.parametrize(
        "fmt_key, raw_min, raw_max",
        [
            ("DD/MM/YYYY", "01/01/2010", "31/12/2020"),
            ("YYYY-MM-DD", "2010-01-01", "2020-12-31"),
            ("YYYYMMDD", "20100101", "20201231"),
        ],
    )
    def test_various_input_formats(self, gen, fmt_key, raw_min, raw_max):
        field = _field(
            "date",
            format=fmt_key,
            dateMinEnabled=True,
            dateMinToday=False,
            dateMinExclusive=False,
            dateMin=raw_min,
            dateMaxEnabled=True,
            dateMaxToday=False,
            dateMaxExclusive=False,
            dateMax=raw_max,
        )
        result = gen._random_date_in_range(field)
        assert datetime(2010, 1, 1) <= result <= datetime(2020, 12, 31)

    def test_inverted_bounds_swap(self, gen):
        """Bornes min > max → échange silencieux."""
        field = _field(
            "date",
            format="DD/MM/YYYY",
            dateMinEnabled=True,
            dateMinToday=False,
            dateMinExclusive=False,
            dateMin="31/12/2020",
            dateMaxEnabled=True,
            dateMaxToday=False,
            dateMaxExclusive=False,
            dateMax="01/01/2010",
        )
        result = gen._random_date_in_range(field)
        assert isinstance(result, datetime)


# ── NIR ───────────────────────────────────────────────────────────────────────


class TestNir:
    def test_nir_length(self, gen):
        assert len(gen._build_nir()["nir"]) == 15

    def test_nir_all_digits(self, gen):
        assert gen._build_nir()["nir"].isdigit()

    def test_nir_sexe_valid(self, gen):
        for _ in range(20):
            assert gen._build_nir()["sexe"] in ("1", "2")

    def test_nir_mois_valid(self, gen):
        for _ in range(20):
            assert 1 <= int(gen._build_nir()["mois"]) <= 12

    def test_parse_nir_roundtrip(self, gen):
        nir = gen._build_nir()
        parsed = gen._parse_nir(nir["nir"])
        assert parsed is not None
        assert parsed["sexe"] == nir["sexe"]

    def test_parse_nir_invalid_returns_none(self, gen):
        assert gen._parse_nir("1234") is None
        assert gen._parse_nir("AZERTYUIOPQSDFF") is None

    def test_parse_nir_bad_sexe_returns_none(self, gen):
        # Sexe non 1 ou 2
        assert gen._parse_nir("3" + "85" + "01" + "75" + "001" + "001" + "00") is None


# ── _get_or_create_nir_data ───────────────────────────────────────────────────


class TestGetOrCreateNirData:
    def test_independent_mode(self, gen):
        field = {"linkedFieldId": "__none__"}
        data = gen._get_or_create_nir_data(field, {})
        assert "nir" in data

    def test_linked_to_existing_nir(self, gen):
        nir = gen._build_nir()
        fields_data = {"f_nir": nir["nir"]}
        field = {"linkedFieldId": "f_nir"}
        data = gen._get_or_create_nir_data(field, fields_data)
        assert data["sexe"] == nir["sexe"]

    def test_linked_to_missing_field_builds_new(self, gen):
        field = {"linkedFieldId": "missing"}
        data = gen._get_or_create_nir_data(field, {})
        assert "sexe" in data

    def test_cache_reused_for_same_linked_id(self, gen):
        nir = gen._build_nir()
        fields_data = {"f_nir": nir["nir"]}
        field = {"linkedFieldId": "f_nir"}
        d1 = gen._get_or_create_nir_data(field, fields_data)
        d2 = gen._get_or_create_nir_data(field, fields_data)
        assert d1 is d2

    def test_auto_detect_from_existing_nir_in_fields(self, gen):
        nir = gen._build_nir()
        fields_data = {"f1": nir["nir"], "_nir_field_id": "f1"}
        field = {"linkedFieldId": ""}
        data = gen._get_or_create_nir_data(field, fields_data)
        assert data["sexe"] == nir["sexe"]

    def test_auto_detect_builds_new_if_no_nir(self, gen):
        field = {"linkedFieldId": ""}
        data = gen._get_or_create_nir_data(field, {})
        assert "sexe" in data


# ── _get_or_create_cp_data ────────────────────────────────────────────────────


class TestGetOrCreateCpData:
    def test_independent_returns_none(self, gen):
        assert gen._get_or_create_cp_data({"linkedFieldId": "__none__"}, {}) is None

    def test_no_cp_value_returns_none(self, gen):
        result = gen._get_or_create_cp_data({"linkedFieldId": "cp_field"}, {})
        assert result is None

    def test_linked_to_cp_field_with_geo(self, gen_with_geo):
        fields_data = {"cp1": "75001"}
        field = {"linkedFieldId": "cp1"}
        result = gen_with_geo._get_or_create_cp_data(field, fields_data)
        assert result is not None
        assert result["codePostal"] == "75001"

    def test_auto_detect_no_cp_field(self, gen):
        result = gen._get_or_create_cp_data({"linkedFieldId": ""}, {})
        assert result is None

    def test_auto_detect_with_cp_field_id(self, gen_with_geo):
        fields_data = {"cp1": "75001", "_cp_field_id": "cp1"}
        result = gen_with_geo._get_or_create_cp_data({"linkedFieldId": ""}, fields_data)
        assert result is not None


# ── Alpha sous-types ──────────────────────────────────────────────────────────


class TestGenAlpha:
    def test_none_with_default_value(self, gen):
        assert gen._gen_alpha("none", _field("alpha", defaultValue="FOO")) == "FOO"

    def test_none_random(self, gen):
        val = gen._gen_alpha("none", _field("alpha"))
        assert isinstance(val, str) and len(val) > 0

    def test_email(self, gen):
        val = gen._gen_alpha("email", _field("alpha"))
        assert "@" in val

    def test_phone(self, gen):
        val = gen._gen_alpha("phone", _field("alpha"))
        assert isinstance(val, str) and len(val) > 0

    def test_phone_plus33(self, gen):
        val = gen._gen_alpha("phonePlus33", _field("alpha"))
        assert "+33" in val

    def test_nom(self, gen):
        val = gen._gen_alpha("nom", _field("alpha"))
        assert isinstance(val, str) and len(val) > 0

    def test_prenom(self, gen):
        val = gen._gen_alpha("prenom", _field("alpha"))
        assert isinstance(val, str) and len(val) > 0

    def test_pays(self, gen):
        assert gen._gen_alpha("pays", _field("alpha")) == "France"

    def test_adresse(self, gen):
        val = gen._gen_alpha("adresse", _field("alpha"))
        assert isinstance(val, str) and len(val) > 0

    def test_iban(self, gen):
        val = gen._gen_alpha("iban", _field("alpha"))
        assert isinstance(val, str) and len(val) > 0

    def test_code_ape(self, gen):
        val = gen._gen_alpha("codeApe", _field("alpha"))
        assert re.match(r"^\d{4}[A-Z]$", val)

    def test_civilite_code(self, gen):
        val = gen._gen_alpha(
            "civilite", _field("alpha", civiliteCategorie="classiques", civiliteOutput="code")
        )
        assert val in ("M", "Mme", "Mlle")

    def test_civilite_nir(self, gen):
        nir = gen._build_nir()
        nir["sexe"] = "1"
        fields_data = {"_nir_data": nir}
        val = gen._gen_alpha(
            "civiliteNir",
            _field(
                "alpha", civiliteCategorie="classiques", civiliteOutput="code", linkedFieldId=""
            ),
            fields_data,
        )
        assert val == "M"

    def test_prenom_nir(self, gen):
        nir = gen._build_nir()
        nir["sexe"] = "2"
        fields_data = {"_nir_data": nir}
        val = gen._gen_alpha("prenomNir", _field("alpha", linkedFieldId=""), fields_data)
        assert isinstance(val, str) and len(val) > 0

    def test_lieu_naissance(self, gen):
        nir = gen._build_nir()
        nir["departement"] = "75"
        fields_data = {"_nir_data": nir}
        val = gen._gen_alpha("lieuNaissance", _field("alpha", linkedFieldId=""), fields_data)
        assert isinstance(val, str) and len(val) > 0

    def test_adresse_complete_no_cp(self, gen):
        val = gen._gen_alpha("adresseComplete", _field("alpha", linkedFieldId="__none__"))
        assert isinstance(val, str) and len(val) > 0

    def test_adresse_complete_with_cp(self, gen_with_geo):
        fields_data = {"cp1": "75001"}
        val = gen_with_geo._gen_alpha(
            "adresseComplete", _field("alpha", linkedFieldId="cp1"), fields_data
        )
        assert "75001" in val or "Paris" in val

    def test_ville_with_geo(self, gen_with_geo):
        val = gen_with_geo._gen_alpha(
            "ville", _field("alpha", codePostalFilter="75*", linkedFieldId="")
        )
        assert isinstance(val, str) and len(val) > 0

    def test_ville_no_geo(self, gen):
        val = gen._gen_alpha("ville", _field("alpha", codePostalFilter="*", linkedFieldId=""))
        assert isinstance(val, str) and len(val) > 0

    def test_unknown_subtype_fallback(self, gen):
        val = gen._gen_alpha("unknown_sub", _field("alpha"))
        assert isinstance(val, str)


# ── Num sous-types ────────────────────────────────────────────────────────────


class TestGenNum:
    def test_none_default_value(self, gen):
        assert gen._gen_num("none", _field("num", defaultValue="42")) == "42"

    def test_none_random(self, gen):
        val = gen._gen_num("none", _field("num"))
        assert val.isdigit()

    def test_siret(self, gen):
        val = gen._gen_num("siret", _field("num", length=14))
        assert len(val) == 14 and val.isdigit()

    def test_departement(self, gen):
        val = gen._gen_num("departement", _field("num", length=2))
        assert 1 <= int(val) <= 95

    def test_nir_generates_and_caches(self, gen):
        fields_data = {}
        val = gen._gen_num("nir", _field("num", length=15), fields_data)
        assert len(val) == 15
        assert "_nir_data" in fields_data

    def test_compteur_lignes_fallback(self, gen):
        val = gen._gen_num("compteurLignes", _field("num"))
        assert val == "0"

    def test_code_postal_with_geo(self, gen_with_geo):
        val = gen_with_geo._gen_num("codePostal", _field("num", length=5, codePostalFilter="75*"))
        assert val == "75001"

    def test_code_postal_no_geo(self, gen):
        val = gen._gen_num("codePostal", _field("num", length=5, codePostalFilter="*"))
        assert len(val) == 5

    def test_code_insee_with_geo(self, gen_with_geo):
        val = gen_with_geo._gen_num("codeInsee", _field("num", length=5, codePostalFilter="75*"))
        assert isinstance(val, str) and len(val) > 0

    def test_code_insee_no_geo(self, gen):
        val = gen._gen_num("codeInsee", _field("num", length=5, codePostalFilter="*"))
        assert len(val) == 5

    def test_departement_naissance(self, gen):
        fields_data = {"_nir_data": {**gen._build_nir(), "departement": "69"}}
        val = gen._gen_num(
            "departementNaissance", _field("num", length=2, linkedFieldId=""), fields_data
        )
        assert val == "69"


# ── NIR Dependencies ──────────────────────────────────────────────────────────


class TestNirDependencies:
    def test_civilite_nir_matches_sexe(self, gen):
        nir_m = {**gen._build_nir(), "sexe": "1"}
        civ = gen._gen_civilite_nir(
            {"civiliteCategorie": "classiques", "civiliteOutput": "code"}, {"_nir_data": nir_m}
        )
        assert civ == "M"

    def test_prenom_nir_male(self, gen):
        fields_data = {"_nir_data": {**gen._build_nir(), "sexe": "1"}}
        assert len(gen._gen_prenom_nir(_field("alpha", "prenomNir"), fields_data)) > 0

    def test_departement_naissance_from_nir(self, gen):
        fields_data = {"_nir_data": {**gen._build_nir(), "departement": "75"}}
        assert gen._gen_num("departementNaissance", _field("num", length=2), fields_data) == "75"


# ── _gen_civilite ─────────────────────────────────────────────────────────────


class TestGenCivilite:
    def test_professional_category(self, gen):
        val = gen._gen_civilite({"civiliteCategorie": "professionnelles", "civiliteOutput": "code"})
        assert val in ("Dr", "Pr", "Me", "Ing", "Dir", "Pres", "Chef")

    def test_output_label(self, gen):
        val = gen._gen_civilite({"civiliteCategorie": "classiques", "civiliteOutput": "label"})
        assert val in ("Monsieur", "Madame", "Mademoiselle")

    def test_female_filter(self, gen):
        val = gen._gen_civilite(
            {"civiliteCategorie": "classiques", "civiliteOutput": "code"}, sexe="2"
        )
        assert val in ("Mme", "Mlle")

    def test_administrative_no_gender_match(self, gen):
        # Catégorie sans gender pour certains → prend tous
        val = gen._gen_civilite(
            {"civiliteCategorie": "administratives", "civiliteOutput": "code"}, sexe="1"
        )
        assert isinstance(val, str) and len(val) > 0


# ── Incrément ─────────────────────────────────────────────────────────────────


class TestIncrement:
    def test_starts_at_default(self, gen):
        field = {**_field("num"), "increment": True, "incrementStart": 1, "defaultValue": ""}
        gen.reset_counters()
        vals = [gen._generate_increment_value(field, "f1") for _ in range(5)]
        assert vals == ["1", "2", "3", "4", "5"]

    def test_starts_at_custom(self, gen):
        field = {**_field("num"), "increment": True, "incrementStart": 100, "defaultValue": ""}
        gen.reset_counters()
        assert gen._generate_increment_value(field, "f2") == "100"

    def test_start_from_default_value(self, gen):
        field = {**_field("num"), "increment": True, "incrementStart": 1, "defaultValue": "50"}
        gen.reset_counters()
        assert gen._generate_increment_value(field, "f3") == "50"

    def test_reset_clears_counters(self, gen):
        field = {**_field("num"), "increment": True, "incrementStart": 1, "defaultValue": ""}
        gen._generate_increment_value(field, "f3")
        gen._generate_increment_value(field, "f3")
        gen.reset_counters()
        assert gen._generate_increment_value(field, "f3") == "1"


# ── Padding ───────────────────────────────────────────────────────────────────


class TestPadding:
    def _gen(self, gen, value, padding, char, length):
        return gen.generate_field_value(
            {
                "id": "p",
                "type": "alpha",
                "subType": "none",
                "length": length,
                "padding": padding,
                "paddingChar": char,
                "defaultValue": value,
            },
            0,
        )

    def test_pad_before(self, gen):
        assert self._gen(gen, "ABC", "before", "0", 6) == "000ABC"

    def test_pad_after(self, gen):
        assert self._gen(gen, "ABC", "after", " ", 6) == "ABC   "

    def test_pad_both(self, gen):
        assert self._gen(gen, "AB", "both", "0", 6) == "00AB00"

    def test_truncate(self, gen):
        result = self._gen(gen, "ABCDEFGH", "none", " ", 5)
        assert result == "ABCDE"

    def test_no_padding(self, gen):
        result = self._gen(gen, "ABC", "none", " ", 10)
        assert result.startswith("ABC")


# ── Concaténation ─────────────────────────────────────────────────────────────


class TestConcat:
    def test_concat_text(self, gen):
        field = {
            "id": "c",
            "type": "alpha",
            "subType": "concat",
            "length": 50,
            "concatItems": [
                {"type": "text", "value": "Hello"},
                {"type": "text", "value": " World"},
            ],
        }
        assert gen._generate_concat_value(field, {}) == "Hello World"

    def test_concat_field_ref(self, gen):
        fields_data = {"f_nom": "Dupont", "f_prenom": "Jean"}
        field = {
            "id": "c",
            "type": "alpha",
            "subType": "concat",
            "length": 50,
            "concatItems": [
                {"type": "field", "fieldId": "f_prenom"},
                {"type": "text", "value": " "},
                {"type": "field", "fieldId": "f_nom"},
            ],
        }
        assert gen._generate_concat_value(field, fields_data) == "Jean Dupont"

    def test_concat_missing_field_skipped(self, gen):
        field = {
            "id": "c",
            "type": "alpha",
            "subType": "concat",
            "length": 50,
            "concatItems": [
                {"type": "field", "fieldId": "inexistant"},
                {"type": "text", "value": "OK"},
            ],
        }
        assert gen._generate_concat_value(field, {}) == "OK"


# ── Tri dépendances ───────────────────────────────────────────────────────────


class TestSortFieldsByDependencies:
    def test_nir_before_nir_dependents(self):
        fields = [
            {"id": "a", "type": "alpha", "subType": "prenomNir"},
            {"id": "b", "type": "num", "subType": "nir"},
            {"id": "c", "type": "date", "subType": "dateNaissance"},
        ]
        ids = [f["id"] for f in DataGenerator.sort_fields_by_dependencies(fields)]
        assert ids.index("b") < ids.index("a")
        assert ids.index("b") < ids.index("c")

    def test_concat_always_last(self):
        fields = [
            {"id": "a", "type": "alpha", "subType": "concat"},
            {"id": "b", "type": "alpha", "subType": "nom"},
            {"id": "c", "type": "num", "subType": "none"},
        ]
        assert DataGenerator.sort_fields_by_dependencies(fields)[-1]["id"] == "a"

    def test_cp_before_ville(self):
        fields = [
            {"id": "a", "type": "alpha", "subType": "ville"},
            {"id": "b", "type": "num", "subType": "codePostal"},
        ]
        ids = [f["id"] for f in DataGenerator.sort_fields_by_dependencies(fields)]
        assert ids.index("b") < ids.index("a")


# ── inject_linked_field_ids ───────────────────────────────────────────────────


class TestInjectLinkedFieldIds:
    def test_injects_nir_field_id(self):
        fields = [{"id": "n1", "subType": "nir"}, {"id": "f1", "subType": "nom"}]
        data = {}
        DataGenerator.inject_linked_field_ids(fields, data)
        assert data["_nir_field_id"] == "n1"

    def test_injects_cp_field_id(self):
        fields = [{"id": "cp1", "subType": "codePostal"}, {"id": "v1", "subType": "ville"}]
        data = {}
        DataGenerator.inject_linked_field_ids(fields, data)
        assert data["_cp_field_id"] == "cp1"


# ── Decimal ───────────────────────────────────────────────────────────────────


class TestDecimal:
    def test_point_separator(self, gen):
        val = gen._gen_decimal(_field("decimal", decimalSeparator=".", decimalPlaces=2))
        assert "." in val
        assert len(val.split(".")[1]) == 2

    def test_comma_separator(self, gen):
        val = gen._gen_decimal(_field("decimal", decimalSeparator=",", decimalPlaces=3))
        assert "," in val
        assert len(val.split(",")[1]) == 3


# ── Compteur de lignes ────────────────────────────────────────────────────────


class TestCompteurLignes:
    def test_total_lines_injected(self, gen):
        field = {
            "id": "cl",
            "type": "num",
            "subType": "compteurLignes",
            "length": 5,
            "includeInOutput": True,
        }
        assert gen.generate_field_value(field, 0, {}, {}, total_lines=42) == "42"

    def test_no_total_lines_returns_zero(self, gen):
        field = {
            "id": "cl",
            "type": "num",
            "subType": "compteurLignes",
            "length": 5,
            "includeInOutput": True,
        }
        assert gen.generate_field_value(field, 0, {}, {}, total_lines=None) == "0"


# ── Presets ───────────────────────────────────────────────────────────────────


class TestPresets:
    def test_preset_fixed_value(self, gen):
        field = {
            "id": "f1",
            "type": "alpha",
            "subType": "none",
            "length": 10,
            "padding": "none",
            "defaultValue": "",
        }
        presets = {"f1": {"useRandom": False, "values": [{"value": "PRESET"}]}}
        val = gen.generate_field_value(field, 0, {}, presets)
        assert val == "PRESET"

    def test_preset_empty_values_uses_default(self, gen):
        field = {
            "id": "f1",
            "type": "alpha",
            "subType": "none",
            "length": 10,
            "padding": "none",
            "defaultValue": "DEFAULT",
        }
        presets = {"f1": {"useRandom": False, "values": []}}
        val = gen.generate_field_value(field, 0, {}, presets)
        assert val == "DEFAULT"

    def test_preset_use_random_skipped(self, gen):
        field = {"id": "f1", "type": "alpha", "subType": "nom", "length": 30, "padding": "none"}
        presets = {"f1": {"useRandom": True, "values": [{"value": "NEVER"}]}}
        val = gen.generate_field_value(field, 0, {}, presets)
        assert val != "NEVER"


# ── _gen_ville geo fallback ───────────────────────────────────────────────────


class TestGenVilleGeo:
    def test_ville_with_geo_filter(self, gen_with_geo):
        field = _field("alpha", "ville", codePostalFilter="75*", linkedFieldId="")
        val = gen_with_geo._gen_ville(field, {})
        assert isinstance(val, str) and len(val) > 0

    def test_ville_geo_exception_fallback(self, gen):
        # geo_client absent → faker
        val = gen._gen_ville(_field("alpha", codePostalFilter="*", linkedFieldId=""))
        assert isinstance(val, str) and len(val) > 0

    def test_code_postal_with_prefix_filter_no_geo(self, gen):
        val = gen._gen_code_postal(_field("num", codePostalFilter="33*"))
        assert val.startswith("33")

    def test_code_insee_no_commune_found(self, gen_with_geo):
        gen_with_geo.geo_client.get_commune_par_code_postal.return_value = None
        val = gen_with_geo._gen_code_insee(_field("num", codePostalFilter="*"))
        assert isinstance(val, str) and len(val) > 0
