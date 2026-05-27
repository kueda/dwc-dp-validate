"""Tests for DwC semantic row-level checks (Layer 3)."""
import csv
import tempfile
from pathlib import Path

import pytest

from dwcdp_validate.checks.semantic import check, _parse_iso8601
from dwcdp_validate.report import Report, Severity


def _run_on_rows(rows: list[dict], resource_name: str = "occurrence") -> Report:
    """Write rows to a temp CSV and run semantic checks against them."""
    if not rows:
        return Report()
    fieldnames = list(rows[0].keys())
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        csv_path = tmp_path / "occurrence.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        dp = {
            "resources": [
                {
                    "name": resource_name,
                    "path": "occurrence.csv",
                    "format": "csv",
                    "schema": {"fields": [{"name": f} for f in fieldnames]},
                }
            ]
        }
        report = Report()
        check(dp, tmp_path, report)
    return report


def _errors(report: Report) -> list[str]:
    return [i.message for i in report.issues if i.severity == Severity.ERROR]


def _warnings(report: Report) -> list[str]:
    return [i.message for i in report.issues if i.severity == Severity.WARNING]


class TestBasisOfRecord:
    def test_valid_basis_no_error(self):
        report = _run_on_rows([{"basisOfRecord": "HumanObservation"}])
        assert not _errors(report)

    def test_invalid_basis_is_error(self):
        report = _run_on_rows([{"basisOfRecord": "NotValid"}])
        assert any("basisOfRecord" in e for e in _errors(report))

    def test_empty_basis_no_error(self):
        report = _run_on_rows([{"basisOfRecord": ""}])
        assert not _errors(report)

    def test_all_valid_basis_values(self):
        from dwcdp_validate.checks.semantic import BASIS_OF_RECORD_VALUES
        for val in BASIS_OF_RECORD_VALUES:
            report = _run_on_rows([{"basisOfRecord": val}])
            assert not _errors(report), f"Unexpected error for basisOfRecord={val!r}"


class TestOccurrenceStatus:
    def test_present_is_valid(self):
        report = _run_on_rows([{"occurrenceStatus": "present"}])
        assert not _errors(report)

    def test_absent_is_valid(self):
        report = _run_on_rows([{"occurrenceStatus": "absent"}])
        assert not _errors(report)

    def test_invalid_status_is_error(self):
        report = _run_on_rows([{"occurrenceStatus": "detected"}])
        assert any("occurrenceStatus" in e for e in _errors(report))

    def test_empty_status_no_error(self):
        report = _run_on_rows([{"occurrenceStatus": ""}])
        assert not _errors(report)


class TestCoordinates:
    def test_valid_lat_lon_no_error(self):
        report = _run_on_rows([{
            "decimalLatitude": "48.5",
            "decimalLongitude": "2.3",
            "geodeticDatum": "WGS84",
        }])
        assert not _errors(report)

    def test_lat_out_of_range_is_error(self):
        report = _run_on_rows([{"decimalLatitude": "91.0", "decimalLongitude": "0.0", "geodeticDatum": "WGS84"}])
        assert any("decimalLatitude" in e for e in _errors(report))

    def test_lat_negative_boundary_valid(self):
        report = _run_on_rows([{"decimalLatitude": "-90.0", "decimalLongitude": "0.0", "geodeticDatum": "WGS84"}])
        assert not _errors(report)

    def test_lon_out_of_range_is_error(self):
        report = _run_on_rows([{"decimalLatitude": "0.0", "decimalLongitude": "181.0", "geodeticDatum": "WGS84"}])
        assert any("decimalLongitude" in e for e in _errors(report))

    def test_missing_datum_with_coords_is_warning(self):
        report = _run_on_rows([{
            "decimalLatitude": "48.5",
            "decimalLongitude": "2.3",
            "geodeticDatum": "",
        }])
        assert any("geodeticDatum" in w for w in _warnings(report))

    def test_datum_present_no_warning(self):
        report = _run_on_rows([{
            "decimalLatitude": "48.5",
            "decimalLongitude": "2.3",
            "geodeticDatum": "EPSG:4326",
        }])
        assert not any("geodeticDatum" in w for w in _warnings(report))

    def test_non_numeric_lat_is_error(self):
        report = _run_on_rows([{"decimalLatitude": "forty-eight"}])
        assert any("decimalLatitude" in e for e in _errors(report))


class TestCoordinateUncertainty:
    def test_positive_value_no_error(self):
        report = _run_on_rows([{"coordinateUncertaintyInMeters": "30"}])
        assert not _errors(report)

    def test_zero_is_error(self):
        report = _run_on_rows([{"coordinateUncertaintyInMeters": "0"}])
        assert any("coordinateUncertaintyInMeters" in e for e in _errors(report))

    def test_negative_is_error(self):
        report = _run_on_rows([{"coordinateUncertaintyInMeters": "-5"}])
        assert any("coordinateUncertaintyInMeters" in e for e in _errors(report))

    def test_empty_no_error(self):
        report = _run_on_rows([{"coordinateUncertaintyInMeters": ""}])
        assert not _errors(report)


class TestCountryCode:
    def test_valid_code_no_warning(self):
        report = _run_on_rows([{"countryCode": "US"}])
        assert not _warnings(report)

    def test_invalid_code_is_warning(self):
        report = _run_on_rows([{"countryCode": "XX"}])
        assert any("countryCode" in w for w in _warnings(report))

    def test_lowercase_is_warning(self):
        report = _run_on_rows([{"countryCode": "us"}])
        assert any("countryCode" in w for w in _warnings(report))

    def test_empty_no_warning(self):
        report = _run_on_rows([{"countryCode": ""}])
        assert not _warnings(report)


class TestTaxonRank:
    def test_species_is_valid(self):
        report = _run_on_rows([{"taxonRank": "species"}])
        assert not _warnings(report)

    def test_unknown_rank_is_warning(self):
        report = _run_on_rows([{"taxonRank": "magnorder"}])
        assert any("taxonRank" in w for w in _warnings(report))

    def test_empty_no_warning(self):
        report = _run_on_rows([{"taxonRank": ""}])
        assert not _warnings(report)


class TestEventDate:
    @pytest.mark.parametrize("date_str", [
        "2024-01-15",
        "2024",
        "2024-06",
        "2024-01-15T10:30:00",
        "2024-01-15T10:30:00Z",
        "2007-03-01T13:00:00Z/2008-05-11T15:30:00Z",
        "1900/1909",
        "2007-11-13/15",
    ])
    def test_valid_dates(self, date_str: str):
        assert _parse_iso8601(date_str), f"Expected {date_str!r} to be valid ISO 8601"

    @pytest.mark.parametrize("date_str", [
        "not-a-date",
        "15/01/2024",
        "Jan 15, 2024",
    ])
    def test_invalid_dates(self, date_str: str):
        assert not _parse_iso8601(date_str), f"Expected {date_str!r} to be invalid"

    def test_invalid_date_in_row_is_error(self):
        report = _run_on_rows([{"eventDate": "not-a-date"}])
        assert any("eventDate" in e for e in _errors(report))

    def test_valid_date_in_row_no_error(self):
        report = _run_on_rows([{"eventDate": "2024-01-15"}])
        assert not _errors(report)

    def test_empty_no_error(self):
        report = _run_on_rows([{"eventDate": ""}])
        assert not _errors(report)
