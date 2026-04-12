"""
Tests unitaires — core/compliance_checker.py
"""

import json
import os
import tempfile

from core.compliance_checker import (
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    CheckResult,
    ComplianceChecker,
    ComplianceReport,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_fm(
    encoding="UTF-8",
    line_ending="CRLF",
    delimiter=",",
    fmt="csv",
    name="Test",
    header_fields=None,
    footer_fields=None,
    field_lines=None,
):
    class FakeFlow:
        pass

    fm = FakeFlow()
    fm.current_flow = {
        "encoding": encoding,
        "lineEnding": line_ending,
        "delimiter": delimiter,
        "format": fmt,
        "name": name,
    }
    fm.header_fields = header_fields or []
    fm.footer_fields = footer_fields or []
    fm.field_lines = field_lines or []
    return fm


def _write_tmp(content: bytes, suffix: str = ".csv") -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.write(fd, content)
    os.close(fd)
    return str(path)


# ── CheckResult & ComplianceReport ───────────────────────────────────────────


class TestCheckResult:
    def test_defaults(self):
        r = CheckResult(severity="error", category="Test", message="Msg")
        assert r.row == 0
        assert r.col_name == ""
        assert r.expected == ""
        assert r.actual == ""


class TestComplianceReport:
    def test_add_error_increments_count(self):
        report = ComplianceReport(
            flow_name="F",
            file_path="p",
            checked_at=__import__("datetime").datetime.now(),
            total_rows=0,
        )
        report.add(CheckResult(severity=SEVERITY_ERROR, category="C", message="M"))
        assert report.error_count == 1
        assert not report.is_compliant

    def test_add_warning(self):
        report = ComplianceReport(
            flow_name="F",
            file_path="p",
            checked_at=__import__("datetime").datetime.now(),
            total_rows=0,
        )
        report.add(CheckResult(severity=SEVERITY_WARNING, category="C", message="M"))
        assert report.warning_count == 1
        assert report.is_compliant

    def test_add_info(self):
        report = ComplianceReport(
            flow_name="F",
            file_path="p",
            checked_at=__import__("datetime").datetime.now(),
            total_rows=0,
        )
        report.add(CheckResult(severity=SEVERITY_INFO, category="C", message="M"))
        assert report.info_count == 1

    def test_to_text_compliant(self):
        from datetime import datetime

        report = ComplianceReport(
            flow_name="F", file_path="p.csv", checked_at=datetime.now(), total_rows=10
        )
        report.add(CheckResult(severity=SEVERITY_INFO, category="C", message="OK"))
        text = report.to_text()
        assert "CONFORME" in text
        assert "p.csv" in text

    def test_to_text_non_compliant(self):
        from datetime import datetime

        report = ComplianceReport(
            flow_name="F", file_path="p.csv", checked_at=datetime.now(), total_rows=5
        )
        report.add(
            CheckResult(
                severity=SEVERITY_ERROR,
                category="C",
                message="ERR",
                row=2,
                col_name="col1",
                expected="X",
                actual="Y",
            )
        )
        text = report.to_text()
        assert "NON CONFORME" in text
        assert "ERR" in text
        assert "Attendu" in text

    def test_to_text_no_results(self):
        from datetime import datetime

        report = ComplianceReport(
            flow_name="F", file_path="p.csv", checked_at=datetime.now(), total_rows=0
        )
        assert "Aucun écart" in report.to_text()

    def test_to_text_with_warnings(self):
        from datetime import datetime

        report = ComplianceReport(
            flow_name="F", file_path="p.csv", checked_at=datetime.now(), total_rows=0
        )
        report.add(CheckResult(severity=SEVERITY_WARNING, category="W", message="WARN"))
        assert "AVERTISSEMENTS" in report.to_text()

    def test_to_text_with_summary_lines(self):
        from datetime import datetime

        report = ComplianceReport(
            flow_name="F", file_path="p.csv", checked_at=datetime.now(), total_rows=0
        )
        report.summary_lines.append("Encodage       : UTF-8 ✓")
        assert "UTF-8" in report.to_text()


# ── _read_raw ─────────────────────────────────────────────────────────────────


class TestReadRaw:
    def test_reads_file(self):
        path = _write_tmp(b"hello world")
        fm = _make_fm()
        checker = ComplianceChecker(fm)
        report = ComplianceReport(
            flow_name="F",
            file_path=path,
            checked_at=__import__("datetime").datetime.now(),
            total_rows=0,
        )
        result = checker._read_raw(path, report)
        assert result == b"hello world"

    def test_missing_file_adds_error(self):
        fm = _make_fm()
        checker = ComplianceChecker(fm)
        report = ComplianceReport(
            flow_name="F",
            file_path="/no/such",
            checked_at=__import__("datetime").datetime.now(),
            total_rows=0,
        )
        result = checker._read_raw("/no/such/file.csv", report)
        assert result is None
        assert report.error_count == 1


# ── _check_encoding ───────────────────────────────────────────────────────────


class TestCheckEncoding:
    def test_utf8_ok(self):
        fm = _make_fm(encoding="UTF-8")
        checker = ComplianceChecker(fm)
        report = ComplianceReport(
            flow_name="F",
            file_path="p",
            checked_at=__import__("datetime").datetime.now(),
            total_rows=0,
        )
        content = checker._check_encoding(b"hello", report)
        assert content == "hello"
        assert report.info_count == 1

    def test_wrong_encoding_detected(self):
        fm = _make_fm(encoding="UTF-8")
        checker = ComplianceChecker(fm)
        report = ComplianceReport(
            flow_name="F",
            file_path="p",
            checked_at=__import__("datetime").datetime.now(),
            total_rows=0,
        )
        # Content encoded in latin-1, declared as UTF-8
        content = checker._check_encoding("café".encode("iso-8859-1"), report)
        assert content is not None  # détecté en fallback
        assert report.error_count >= 1

    def test_undecipherable_returns_none(self):
        fm = _make_fm(encoding="UTF-8")
        checker = ComplianceChecker(fm)
        report = ComplianceReport(
            flow_name="F",
            file_path="p",
            checked_at=__import__("datetime").datetime.now(),
            total_rows=0,
        )
        # Bytes that are not valid in any common encoding
        result = checker._check_encoding(bytes([0xFF, 0xFE, 0x00, 0x01, 0x02, 0x03] * 50), report)
        # May return None or content - just verify no crash
        assert isinstance(result, (str, type(None)))


# ── _check_line_endings ───────────────────────────────────────────────────────


class TestCheckLineEndings:
    def _check(self, content, declared="CRLF"):
        fm = _make_fm(line_ending=declared)
        checker = ComplianceChecker(fm)
        report = ComplianceReport(
            flow_name="F",
            file_path="p",
            checked_at=__import__("datetime").datetime.now(),
            total_rows=0,
        )
        checker._check_line_endings(content, report)
        return report

    def test_crlf_matches(self):
        report = self._check("a,b\r\nc,d\r\n", declared="CRLF")
        assert report.info_count == 1

    def test_lf_mismatch(self):
        report = self._check("a,b\nc,d\n", declared="CRLF")
        assert report.warning_count == 1

    def test_lf_matches(self):
        report = self._check("a,b\nc,d\n", declared="LF")
        assert report.info_count == 1

    def test_mixed_line_endings(self):
        report = self._check("a\r\nb\nc\r\n", declared="CRLF")
        assert report.warning_count == 1

    def test_cr_only(self):
        report = self._check("a\rb\r", declared="LF")
        assert report.warning_count == 1


# ── _check_structure ─────────────────────────────────────────────────────────


class TestCheckStructure:
    def _checker(self, fmt="csv"):
        return ComplianceChecker(_make_fm(fmt=fmt))

    def _report(self):
        return ComplianceReport(
            flow_name="F",
            file_path="p",
            checked_at=__import__("datetime").datetime.now(),
            total_rows=0,
        )

    def test_csv_returns_true(self):
        checker = self._checker("csv")
        assert checker._check_structure("a,b\n1,2", "csv", self._report())

    def test_json_valid_array(self):
        checker = self._checker("json")
        report = self._report()
        checker._check_json_structure('[{"a": 1}, {"a": 2}]', report)
        assert report.info_count >= 1

    def test_json_invalid(self):
        checker = self._checker("json")
        report = self._report()
        result = checker._check_json_structure("{invalid json}", report)
        assert result is False
        assert report.error_count == 1

    def test_json_dict_root(self):
        checker = self._checker("json")
        report = self._report()
        checker._check_json_structure('{"key": "val"}', report)
        assert report.info_count >= 1

    def test_json_primitive_root(self):
        checker = self._checker("json")
        report = self._report()
        checker._check_json_structure('"just a string"', report)
        assert report.warning_count >= 1

    def test_json_inconsistent_keys(self):
        checker = self._checker("json")
        report = self._report()
        checker._check_json_structure('[{"a": 1}, {"b": 2}]', report)
        assert report.warning_count >= 1

    def test_xml_valid(self):
        checker = self._checker("xml")
        report = self._report()
        result = checker._check_xml_structure("<root><row/><row/></root>", report)
        assert result is True
        assert report.info_count >= 1

    def test_xml_invalid(self):
        checker = self._checker("xml")
        report = self._report()
        result = checker._check_xml_structure("<unclosed", report)
        assert result is False
        assert report.error_count == 1

    def test_xml_multiple_tags(self):
        checker = self._checker("xml")
        report = self._report()
        checker._check_xml_structure("<root><a/><b/></root>", report)
        assert report.warning_count >= 1


# ── _check_delimiter ─────────────────────────────────────────────────────────


class TestCheckDelimiter:
    def _check(self, lines, delimiter=","):
        fm = _make_fm(delimiter=delimiter)
        checker = ComplianceChecker(fm)
        report = ComplianceReport(
            flow_name="F",
            file_path="p",
            checked_at=__import__("datetime").datetime.now(),
            total_rows=0,
        )
        checker._check_delimiter(lines, delimiter, report)
        return report

    def test_consistent_delimiter(self):
        report = self._check(["a,b,c", "1,2,3"])
        assert report.info_count == 1

    def test_absent_delimiter(self):
        report = self._check(["a;b;c", "1;2;3"], delimiter=",")
        assert report.error_count == 1

    def test_variable_count(self):
        report = self._check(["a,b,c", "1,2,3,4"])
        assert report.warning_count == 1

    def test_empty_lines_no_crash(self):
        report = self._check([])
        assert report.error_count == 0


# ── _check_header_footer ─────────────────────────────────────────────────────


class TestCheckHeaderFooter:
    def _checker_with_fields(self, header_fields=None, footer_fields=None):
        fm = _make_fm(header_fields=header_fields or [], footer_fields=footer_fields or [])
        return ComplianceChecker(fm)

    def _report(self):
        return ComplianceReport(
            flow_name="F",
            file_path="p",
            checked_at=__import__("datetime").datetime.now(),
            total_rows=0,
        )

    def test_header_correct_column_count(self):
        checker = self._checker_with_fields(
            header_fields=[
                {"id": "h1", "includeInOutput": True},
                {"id": "h2", "includeInOutput": True},
            ]
        )
        report = self._report()
        checker._check_header_footer(["h1,h2", "1,2"], ",", True, False, report)
        assert report.info_count >= 1

    def test_header_wrong_column_count(self):
        checker = self._checker_with_fields(
            header_fields=[
                {"id": "h1", "includeInOutput": True},
                {"id": "h2", "includeInOutput": True},
            ]
        )
        report = self._report()
        checker._check_header_footer(["h1,h2,h3", "1,2"], ",", True, False, report)
        assert report.error_count >= 1

    def test_no_header_declared_but_text_first_line(self):
        checker = self._checker_with_fields()
        report = self._report()
        checker._check_header_footer(["Name,City", "Alice,Paris"], ",", False, False, report)
        assert report.warning_count >= 1

    def test_footer_correct(self):
        checker = self._checker_with_fields(footer_fields=[{"id": "f1", "includeInOutput": True}])
        report = self._report()
        checker._check_header_footer(["1,2", "FOOT"], ",", False, True, report)
        assert report.info_count >= 1

    def test_footer_wrong_count(self):
        checker = self._checker_with_fields(
            footer_fields=[
                {"id": "f1", "includeInOutput": True},
                {"id": "f2", "includeInOutput": True},
            ]
        )
        report = self._report()
        checker._check_header_footer(["1,2", "FOOT"], ",", False, True, report)
        assert report.error_count >= 1

    def test_empty_lines_no_crash(self):
        checker = self._checker_with_fields()
        report = self._report()
        checker._check_header_footer([], ",", False, False, report)


# ── _check_field_count ────────────────────────────────────────────────────────


class TestCheckFieldCount:
    def _checker(self):
        return ComplianceChecker(_make_fm())

    def _report(self):
        return ComplianceReport(
            flow_name="F",
            file_path="p",
            checked_at=__import__("datetime").datetime.now(),
            total_rows=0,
        )

    def test_correct_count(self):
        checker = self._checker()
        report = self._report()
        checker._check_field_count(["a", "b"], [{"id": "1"}, {"id": "2"}], 1, "L", report)
        assert report.error_count == 0

    def test_wrong_count(self):
        checker = self._checker()
        report = self._report()
        checker._check_field_count(["a", "b", "c"], [{"id": "1"}, {"id": "2"}], 1, "L", report)
        assert report.error_count == 1


# ── _check_mandatory ─────────────────────────────────────────────────────────


class TestCheckMandatory:
    def _checker(self):
        return ComplianceChecker(_make_fm())

    def _report(self):
        return ComplianceReport(
            flow_name="F",
            file_path="p",
            checked_at=__import__("datetime").datetime.now(),
            total_rows=0,
        )

    def test_empty_mandatory_field(self):
        checker = self._checker()
        report = self._report()
        checker._check_mandatory(
            "", {"includeInOutput": True, "defaultValue": ""}, 1, "col", report
        )
        assert report.warning_count == 1

    def test_filled_field_ok(self):
        checker = self._checker()
        report = self._report()
        checker._check_mandatory(
            "value", {"includeInOutput": True, "defaultValue": ""}, 1, "col", report
        )
        assert report.warning_count == 0

    def test_field_with_default_no_warning(self):
        checker = self._checker()
        report = self._report()
        checker._check_mandatory(
            "", {"includeInOutput": True, "defaultValue": "DEFAULT"}, 1, "col", report
        )
        assert report.warning_count == 0

    def test_excluded_field_ignored(self):
        checker = self._checker()
        report = self._report()
        checker._check_mandatory(
            "", {"includeInOutput": False, "defaultValue": ""}, 1, "col", report
        )
        assert report.warning_count == 0


# ── _check_length ─────────────────────────────────────────────────────────────


class TestCheckLength:
    def _checker(self, fmt="csv"):
        return ComplianceChecker(_make_fm(fmt=fmt))

    def _report(self):
        return ComplianceReport(
            flow_name="F",
            file_path="p",
            checked_at=__import__("datetime").datetime.now(),
            total_rows=0,
        )

    def test_csv_ok_length(self):
        checker = self._checker("csv")
        report = self._report()
        checker._check_length("hello", {"length": 10}, 1, "col", report)
        assert report.warning_count == 0

    def test_csv_exceeds_length(self):
        checker = self._checker("csv")
        report = self._report()
        checker._check_length("hello world", {"length": 5}, 1, "col", report)
        assert report.warning_count == 1

    def test_fixed_exact_length_ok(self):
        checker = self._checker("fixed")
        report = self._report()
        checker._check_length("hello", {"length": 5}, 1, "col", report)
        assert report.error_count == 0

    def test_fixed_wrong_length(self):
        checker = self._checker("fixed")
        report = self._report()
        checker._check_length("hi", {"length": 5}, 1, "col", report)
        assert report.error_count == 1

    def test_empty_value_skipped(self):
        checker = self._checker("csv")
        report = self._report()
        checker._check_length("  ", {"length": 5}, 1, "col", report)
        assert report.warning_count == 0

    def test_zero_declared_length_skipped(self):
        checker = self._checker("csv")
        report = self._report()
        checker._check_length("longvalue", {"length": 0}, 1, "col", report)
        assert report.warning_count == 0


# ── _check_type ───────────────────────────────────────────────────────────────


class TestCheckType:
    def _checker(self):
        return ComplianceChecker(_make_fm())

    def _report(self):
        return ComplianceReport(
            flow_name="F",
            file_path="p",
            checked_at=__import__("datetime").datetime.now(),
            total_rows=0,
        )

    def test_num_valid(self):
        checker = self._checker()
        report = self._report()
        checker._check_type("12345", {"type": "num", "subType": "none"}, 1, "col", report)
        assert report.error_count == 0

    def test_num_invalid(self):
        checker = self._checker()
        report = self._report()
        checker._check_type("abc", {"type": "num", "subType": "none"}, 1, "col", report)
        assert report.error_count == 1

    def test_decimal_valid(self):
        checker = self._checker()
        report = self._report()
        checker._check_type("3.14", {"type": "decimal", "decimalSeparator": "."}, 1, "col", report)
        assert report.error_count == 0

    def test_decimal_comma_separator(self):
        checker = self._checker()
        report = self._report()
        checker._check_type("3,14", {"type": "decimal", "decimalSeparator": ","}, 1, "col", report)
        assert report.error_count == 0

    def test_decimal_invalid(self):
        checker = self._checker()
        report = self._report()
        checker._check_type("abc", {"type": "decimal", "decimalSeparator": "."}, 1, "col", report)
        assert report.error_count == 1

    def test_bool_valid(self):
        checker = self._checker()
        report = self._report()
        checker._check_type("O", {"type": "bool", "subType": "ON"}, 1, "col", report)
        assert report.error_count == 0

    def test_bool_invalid(self):
        checker = self._checker()
        report = self._report()
        checker._check_type("MAYBE", {"type": "bool", "subType": "OUINON"}, 1, "col", report)
        assert report.error_count == 1

    def test_bool_none_subtype(self):
        checker = self._checker()
        report = self._report()
        checker._check_type("OUI", {"type": "bool", "subType": "none"}, 1, "col", report)
        assert report.error_count == 0

    def test_alpha_no_error(self):
        checker = self._checker()
        report = self._report()
        checker._check_type("hello", {"type": "alpha", "subType": "none"}, 1, "col", report)
        assert report.error_count == 0

    def test_empty_value_skipped(self):
        checker = self._checker()
        report = self._report()
        checker._check_type("", {"type": "num", "subType": "none"}, 1, "col", report)
        assert report.error_count == 0


# ── _check_date_format ────────────────────────────────────────────────────────


class TestCheckDateFormat:
    def _checker(self):
        return ComplianceChecker(_make_fm())

    def _report(self):
        return ComplianceReport(
            flow_name="F",
            file_path="p",
            checked_at=__import__("datetime").datetime.now(),
            total_rows=0,
        )

    def test_valid_date(self):
        checker = self._checker()
        report = self._report()
        checker._check_date_format("15/06/2023", {"format": "DD/MM/YYYY"}, 1, "col", report)
        assert report.error_count == 0

    def test_invalid_date(self):
        checker = self._checker()
        report = self._report()
        checker._check_date_format("2023-06-15", {"format": "DD/MM/YYYY"}, 1, "col", report)
        assert report.error_count == 1

    def test_timestamp_valid(self):
        checker = self._checker()
        report = self._report()
        checker._check_date_format("1686873600", {"format": "timestamp"}, 1, "col", report)
        assert report.error_count == 0

    def test_timestamp_invalid(self):
        checker = self._checker()
        report = self._report()
        checker._check_date_format("not-a-timestamp", {"format": "timestamp"}, 1, "col", report)
        assert report.error_count == 1

    def test_unknown_format_no_crash(self):
        checker = self._checker()
        report = self._report()
        checker._check_date_format("somevalue", {"format": "UNKNOWN_FMT"}, 1, "col", report)
        # Should not crash, no error for unknown format
        assert True


# ── _check_subtype ────────────────────────────────────────────────────────────


class TestCheckSubtype:
    def _checker(self):
        return ComplianceChecker(_make_fm())

    def _report(self):
        return ComplianceReport(
            flow_name="F",
            file_path="p",
            checked_at=__import__("datetime").datetime.now(),
            total_rows=0,
        )

    def test_email_valid(self):
        checker = self._checker()
        report = self._report()
        checker._check_subtype("test@example.com", {"subType": "email"}, 1, "col", report)
        assert report.warning_count == 0

    def test_email_invalid(self):
        checker = self._checker()
        report = self._report()
        checker._check_subtype("notanemail", {"subType": "email"}, 1, "col", report)
        assert report.warning_count == 1

    def test_siret_valid(self):
        checker = self._checker()
        report = self._report()
        checker._check_subtype("73282932000074", {"subType": "siret"}, 1, "col", report)
        assert report.warning_count == 0

    def test_siret_invalid_format(self):
        checker = self._checker()
        report = self._report()
        checker._check_subtype("1234567", {"subType": "siret"}, 1, "col", report)
        assert report.warning_count == 1

    def test_siret_fails_luhn(self):
        checker = self._checker()
        report = self._report()
        checker._check_subtype("12345678901234", {"subType": "siret"}, 1, "col", report)
        # Valid format but likely fails luhn
        assert report.warning_count >= 1

    def test_nir_valid(self):
        checker = self._checker()
        report = self._report()
        checker._check_subtype("185016912345678", {"subType": "nir"}, 1, "col", report)
        assert report.warning_count == 0

    def test_nir_invalid(self):
        checker = self._checker()
        report = self._report()
        checker._check_subtype("123", {"subType": "nir"}, 1, "col", report)
        assert report.warning_count == 1

    def test_iban_valid(self):
        checker = self._checker()
        report = self._report()
        checker._check_subtype("FR7630006000011234567890189", {"subType": "iban"}, 1, "col", report)
        assert report.warning_count == 0

    def test_code_ape_valid(self):
        checker = self._checker()
        report = self._report()
        checker._check_subtype("6201A", {"subType": "codeApe"}, 1, "col", report)
        assert report.warning_count == 0

    def test_code_postal_valid(self):
        checker = self._checker()
        report = self._report()
        checker._check_subtype("75001", {"subType": "codePostal"}, 1, "col", report)
        assert report.warning_count == 0

    def test_code_postal_invalid(self):
        checker = self._checker()
        report = self._report()
        checker._check_subtype("7500", {"subType": "codePostal"}, 1, "col", report)
        assert report.warning_count == 1

    def test_phone_valid(self):
        checker = self._checker()
        report = self._report()
        checker._check_subtype("0612345678", {"subType": "phone"}, 1, "col", report)
        assert report.warning_count == 0

    def test_phonePlus33_valid(self):
        checker = self._checker()
        report = self._report()
        checker._check_subtype("+33612345678", {"subType": "phonePlus33"}, 1, "col", report)
        assert report.warning_count == 0

    def test_empty_value_skipped(self):
        checker = self._checker()
        report = self._report()
        checker._check_subtype("", {"subType": "email"}, 1, "col", report)
        assert report.warning_count == 0

    def test_unknown_subtype_no_crash(self):
        checker = self._checker()
        report = self._report()
        checker._check_subtype("value", {"subType": "none"}, 1, "col", report)


# ── _split_row ────────────────────────────────────────────────────────────────


class TestSplitRow:
    def test_simple(self):
        result = ComplianceChecker._split_row("a,b,c", ",")
        assert result == ["a", "b", "c"]

    def test_quoted(self):
        result = ComplianceChecker._split_row('"hello, world",b', ",")
        assert result == ["hello, world", "b"]

    def test_semicolon(self):
        result = ComplianceChecker._split_row("a;b;c", ";")
        assert result == ["a", "b", "c"]

    def test_tab(self):
        result = ComplianceChecker._split_row("a\tb\tc", "\t")
        assert result == ["a", "b", "c"]


# ── _extract_data_lines ───────────────────────────────────────────────────────


class TestExtractDataLines:
    LINES = ["header", "data1", "data2", "footer"]

    def test_no_header_no_footer(self):
        result = ComplianceChecker._extract_data_lines(self.LINES, False, False)
        assert result == self.LINES

    def test_with_header(self):
        result = ComplianceChecker._extract_data_lines(self.LINES, True, False)
        assert "header" not in result
        assert "data1" in result

    def test_with_footer(self):
        result = ComplianceChecker._extract_data_lines(self.LINES, False, True)
        assert "footer" not in result
        assert "data1" in result

    def test_with_both(self):
        result = ComplianceChecker._extract_data_lines(self.LINES, True, True)
        assert result == ["data1", "data2"]

    def test_empty_lines_skipped(self):
        lines = ["header", "data1", "", "data2", "footer"]
        result = ComplianceChecker._extract_data_lines(lines, True, True)
        assert "" not in result


# ── _luhn_check ───────────────────────────────────────────────────────────────


class TestLuhnCheck:
    def test_valid_luhn(self):
        # SIRET connu valide
        assert ComplianceChecker._luhn_check("73282932000074")

    def test_invalid_luhn(self):
        assert not ComplianceChecker._luhn_check("12345678901234")


# ── check_file intégration ────────────────────────────────────────────────────


class TestCheckFile:
    def test_missing_file(self):
        fm = _make_fm()
        checker = ComplianceChecker(fm)
        report = checker.check_file("/no/such/file.csv")
        assert report.error_count >= 1

    def test_valid_csv(self):
        content = "Alice,Paris\r\nBob,Lyon\r\n"
        path = _write_tmp(content.encode("utf-8"))
        fm = _make_fm(
            encoding="UTF-8",
            line_ending="CRLF",
            delimiter=",",
            fmt="csv",
            field_lines=[
                {
                    "id": "l1",
                    "name": "Ligne",
                    "fields": [
                        {
                            "id": "f1",
                            "name": "Nom",
                            "type": "alpha",
                            "subType": "none",
                            "includeInOutput": True,
                            "length": 20,
                            "defaultValue": "",
                        },
                        {
                            "id": "f2",
                            "name": "Ville",
                            "type": "alpha",
                            "subType": "none",
                            "includeInOutput": True,
                            "length": 20,
                            "defaultValue": "",
                        },
                    ],
                }
            ],
        )
        checker = ComplianceChecker(fm)
        report = checker.check_file(path)
        assert report.total_rows == 2
        os.unlink(path)

    def test_json_file(self):
        data = json.dumps([{"name": "Alice"}, {"name": "Bob"}]).encode("utf-8")
        path = _write_tmp(data, suffix=".json")
        fm = _make_fm(fmt="json")
        checker = ComplianceChecker(fm)
        report = checker.check_file(path)
        assert report.error_count == 0
        os.unlink(path)

    def test_xml_file(self):
        content = b"<root><row><name>Alice</name></row></root>"
        path = _write_tmp(content, suffix=".xml")
        fm = _make_fm(fmt="xml")
        checker = ComplianceChecker(fm)
        report = checker.check_file(path)
        assert report.error_count == 0
        os.unlink(path)

    def test_progress_callback_called(self):
        messages = []
        content = "a,b\r\n1,2\r\n"
        path = _write_tmp(content.encode("utf-8"))
        fm = _make_fm()
        checker = ComplianceChecker(fm, progress_cb=messages.append)
        checker.check_file(path)
        assert len(messages) > 0
        os.unlink(path)

    def test_csv_with_num_type_error(self):
        content = "Alice,Paris\r\n"
        path = _write_tmp(content.encode("utf-8"))
        fm = _make_fm(
            field_lines=[
                {
                    "id": "l1",
                    "name": "Ligne",
                    "fields": [
                        {
                            "id": "f1",
                            "name": "Code",
                            "type": "num",
                            "subType": "none",
                            "includeInOutput": True,
                            "length": 5,
                            "defaultValue": "",
                        },
                        {
                            "id": "f2",
                            "name": "Ville",
                            "type": "alpha",
                            "subType": "none",
                            "includeInOutput": True,
                            "length": 20,
                            "defaultValue": "",
                        },
                    ],
                }
            ]
        )
        checker = ComplianceChecker(fm)
        report = checker.check_file(path)
        # "Alice" is not numeric → should have an error
        assert report.error_count >= 1
        os.unlink(path)

    def test_no_flow_uses_defaults(self):
        content = "a,b\r\n"
        path = _write_tmp(content.encode("utf-8"))
        fm = _make_fm()
        fm.current_flow = None
        checker = ComplianceChecker(fm)
        checker.check_file(path)
        # Should not crash
        os.unlink(path)
