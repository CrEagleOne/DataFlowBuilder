"""
Tests unitaires — core/field_types.py
"""

import pytest

from core.field_types import (
    DATE_FORMAT_LENGTHS,
    DATE_FORMAT_PLACEHOLDERS,
    DATE_FORMATS,
    DEFAULT_FIELD_CONFIG,
    FIELD_BASE_TYPES,
    FIELD_SUBTYPES,
    SUBTYPE_CONFIG,
    clean_field_for_export,
    get_field_defaults,
    get_relevant_keys,
    get_visible_fields,
)

# ── Constantes de base ────────────────────────────────────────────────────────


class TestFieldBaseTypes:
    def test_expected_types_present(self):
        assert set(FIELD_BASE_TYPES) == {"alpha", "num", "date", "bool", "decimal"}

    def test_all_types_have_subtypes_entry(self):
        for t in FIELD_BASE_TYPES:
            assert t in FIELD_SUBTYPES, f"Type '{t}' absent de FIELD_SUBTYPES"

    def test_all_types_have_subtype_config(self):
        for t in FIELD_BASE_TYPES:
            assert t in SUBTYPE_CONFIG, f"Type '{t}' absent de SUBTYPE_CONFIG"


class TestBoolSubtypes:
    def test_binaire_present(self):
        values = [v for v, _ in FIELD_SUBTYPES["bool"]]
        assert "BINAIRE" in values

    def test_all_bool_subtypes(self):
        expected = {"none", "ON", "OUINON", "OKKO", "BINAIRE"}
        values = {v for v, _ in FIELD_SUBTYPES["bool"]}
        assert expected == values

    def test_binaire_default_length(self):
        defaults = get_field_defaults("bool", "BINAIRE")
        assert defaults["length"] == 1


# ── DATE_FORMATS et longueurs ─────────────────────────────────────────────────


class TestDateFormats:
    def test_all_formats_have_length(self):
        for fmt in DATE_FORMATS:
            assert fmt in DATE_FORMAT_LENGTHS, f"Format '{fmt}' absent de DATE_FORMAT_LENGTHS"

    def test_all_formats_have_placeholder(self):
        for fmt in DATE_FORMATS:
            assert fmt in DATE_FORMAT_PLACEHOLDERS, (
                f"Format '{fmt}' absent de DATE_FORMAT_PLACEHOLDERS"
            )

    @pytest.mark.parametrize(
        "fmt_key, expected_len",
        [
            ("DD/MM/YYYY", 10),
            ("YYYY-MM-DD", 10),
            ("YYYYMMDD", 8),
            ("DDMMYYYY", 8),
            ("YYYYMMDDHHmmss", 14),
            ("DD/MM/YYYY HH:mm:ss", 19),
            ("timestamp", 10),
        ],
    )
    def test_date_length_values(self, fmt_key, expected_len):
        assert DATE_FORMAT_LENGTHS[fmt_key] == expected_len


# ── DEFAULT_FIELD_CONFIG ──────────────────────────────────────────────────────


class TestDefaultFieldConfig:
    def test_required_keys_present(self):
        required = {
            "id",
            "name",
            "type",
            "subType",
            "length",
            "includeInOutput",
            "format",
            "todayDate",
            "dateMin",
            "dateMax",
            "dateMinEnabled",
            "dateMinToday",
            "dateMinExclusive",
            "dateMaxEnabled",
            "dateMaxToday",
            "dateMaxExclusive",
        }
        for key in required:
            assert key in DEFAULT_FIELD_CONFIG, f"Clé '{key}' manquante dans DEFAULT_FIELD_CONFIG"

    def test_today_date_defaults_false(self):
        assert DEFAULT_FIELD_CONFIG["todayDate"] is False

    def test_date_bounds_disabled_by_default(self):
        assert DEFAULT_FIELD_CONFIG["dateMinEnabled"] is False
        assert DEFAULT_FIELD_CONFIG["dateMaxEnabled"] is False
        assert DEFAULT_FIELD_CONFIG["dateMinExclusive"] is False
        assert DEFAULT_FIELD_CONFIG["dateMaxExclusive"] is False
        assert DEFAULT_FIELD_CONFIG["dateMinToday"] is False
        assert DEFAULT_FIELD_CONFIG["dateMaxToday"] is False


# ── get_visible_fields ────────────────────────────────────────────────────────


class TestGetVisibleFields:
    def test_date_none_includes_today_and_range(self):
        fields = get_visible_fields("date", "none")
        assert "todayDate" in fields
        assert "dateRange" in fields
        assert "format" in fields

    def test_date_naissance_no_today(self):
        fields = get_visible_fields("date", "dateNaissance")
        assert "todayDate" not in fields
        assert "dateRange" in fields

    def test_alpha_concat_includes_concat(self):
        fields = get_visible_fields("alpha", "concat")
        assert "concat" in fields

    def test_num_code_postal_includes_filter(self):
        fields = get_visible_fields("num", "codePostal")
        assert "codePostalFilter" in fields

    def test_decimal_includes_decimal_config(self):
        fields = get_visible_fields("decimal", "none")
        assert "decimal" in fields


# ── get_field_defaults ────────────────────────────────────────────────────────


class TestGetFieldDefaults:
    def test_date_none_defaults(self):
        d = get_field_defaults("date", "none")
        assert d["format"] == "DD/MM/YYYY"
        assert d["length"] == 10
        assert d["todayDate"] is False
        assert d["dateMinEnabled"] is False

    def test_alpha_email_length(self):
        d = get_field_defaults("alpha", "email")
        assert d["length"] == 50

    def test_num_iban_length(self):
        d = get_field_defaults("alpha", "iban")
        assert d["length"] == 27

    def test_num_nir_length(self):
        d = get_field_defaults("num", "nir")
        assert d["length"] == 15


# ── get_relevant_keys ─────────────────────────────────────────────────────────


class TestGetRelevantKeys:
    def test_always_keys_present(self):
        always = {
            "id",
            "name",
            "category",
            "type",
            "subType",
            "length",
            "includeInOutput",
            "comment",
        }
        keys = get_relevant_keys("alpha", "none")
        assert always.issubset(keys)

    def test_date_none_includes_bound_keys(self):
        keys = get_relevant_keys("date", "none")
        for k in (
            "dateMin",
            "dateMax",
            "dateMinEnabled",
            "dateMaxEnabled",
            "dateMinExclusive",
            "dateMaxExclusive",
            "todayDate",
        ):
            assert k in keys, f"Clé '{k}' manquante pour date/none"

    def test_alpha_email_excludes_concat(self):
        keys = get_relevant_keys("alpha", "email")
        assert "concatItems" not in keys

    def test_num_none_includes_increment(self):
        keys = get_relevant_keys("num", "none")
        assert "increment" in keys
        assert "incrementStart" in keys


# ── clean_field_for_export ────────────────────────────────────────────────────


class TestCleanFieldForExport:
    def test_irrelevant_keys_stripped(self):
        field = {
            "id": "1",
            "name": "Test",
            "type": "alpha",
            "subType": "email",
            "length": 50,
            "includeInOutput": True,
            "comment": "",
            "category": "",
            "decimalSeparator": ".",  # non pertinent pour email
            "concatItems": [],  # non pertinent pour email
        }
        cleaned = clean_field_for_export(field)
        assert "decimalSeparator" not in cleaned
        assert "concatItems" not in cleaned
        assert cleaned["name"] == "Test"

    def test_date_field_keeps_bound_keys(self):
        field = {
            "id": "3",
            "name": "Date",
            "type": "date",
            "subType": "none",
            "length": 10,
            "includeInOutput": True,
            "comment": "",
            "category": "",
            "format": "DD/MM/YYYY",
            "todayDate": False,
            "dateMinEnabled": True,
            "dateMin": "01/01/2000",
            "dateMinToday": False,
            "dateMinExclusive": False,
            "dateMaxEnabled": True,
            "dateMax": "31/12/2024",
            "dateMaxToday": False,
            "dateMaxExclusive": True,
        }
        cleaned = clean_field_for_export(field)
        assert cleaned["dateMinEnabled"] is True
        assert cleaned["dateMaxExclusive"] is True
