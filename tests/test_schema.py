"""Tests for the schema conformance check (Layer 2b)."""
# pylint: disable=missing-function-docstring,missing-class-docstring
import responses as resp_lib

from dwc_dp_validate.checks import schema as schema_check
from dwc_dp_validate.report import Report, Severity
from .helpers import MOCK_SURVEY_SCHEMA

SCHEMA_BASE_URL = schema_check.SCHEMA_BASE_URL
SURVEY_URL = f"{SCHEMA_BASE_URL}survey.json"


def _make_survey_dp(csv_filename: str = "survey.csv") -> dict:
    return {
        "resources": [{
            "name": "survey",
            "path": csv_filename,
            "format": "csv",
            "schema": {"fields": []},
        }]
    }


class TestFetchFalse:
    def test_skips_all_checks(self, tmp_path):
        (tmp_path / "survey.csv").write_text("eventID\nE1\n")
        report = Report()
        schema_check.check(_make_survey_dp(), report, fetch=False, base_dir=tmp_path)
        assert not report.issues


class TestRequiredColumnPresence:
    @resp_lib.activate
    def test_missing_required_column_is_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(schema_check, "_cache", {})
        resp_lib.add(resp_lib.GET, SURVEY_URL, json=MOCK_SURVEY_SCHEMA, status=200)

        (tmp_path / "survey.csv").write_text("eventID,siteCount\nE1,5\n")

        report = Report()
        schema_check.check(_make_survey_dp(), report, fetch=True, base_dir=tmp_path)

        errors = [i for i in report.issues if i.severity == Severity.ERROR]
        assert any(i.field_name == "surveyID" for i in errors)

    @resp_lib.activate
    def test_all_required_columns_present_no_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(schema_check, "_cache", {})
        resp_lib.add(resp_lib.GET, SURVEY_URL, json=MOCK_SURVEY_SCHEMA, status=200)

        (tmp_path / "survey.csv").write_text("surveyID,eventID,siteCount\nS1,E1,5\n")

        report = Report()
        schema_check.check(_make_survey_dp(), report, fetch=True, base_dir=tmp_path)

        errors = [i for i in report.issues if i.severity == Severity.ERROR]
        assert not errors

    @resp_lib.activate
    def test_missing_multiple_required_columns(self, tmp_path, monkeypatch):
        monkeypatch.setattr(schema_check, "_cache", {})
        resp_lib.add(resp_lib.GET, SURVEY_URL, json=MOCK_SURVEY_SCHEMA, status=200)

        (tmp_path / "survey.csv").write_text("siteCount\n5\n")

        report = Report()
        schema_check.check(_make_survey_dp(), report, fetch=True, base_dir=tmp_path)

        error_fields = {i.field_name for i in report.issues if i.severity == Severity.ERROR}
        assert "surveyID" in error_fields
        assert "eventID" in error_fields

    def test_no_base_dir_skips_column_check(self, monkeypatch):
        monkeypatch.setattr(schema_check, "_cache", {"survey": MOCK_SURVEY_SCHEMA})

        report = Report()
        schema_check.check(_make_survey_dp(), report, fetch=True, base_dir=None)

        errors = [i for i in report.issues if i.severity == Severity.ERROR]
        assert not errors
