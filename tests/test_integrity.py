"""Tests for referential integrity checks (Layer 2c)."""
# pylint: disable=missing-function-docstring,missing-class-docstring
import csv
from pathlib import Path

from dwc_dp_validate.checks import schema as schema_check
from dwc_dp_validate.checks import integrity as integrity_check
from dwc_dp_validate.report import Report, Severity

MOCK_SURVEY = {
    "fields": [
        {"name": "surveyID", "constraints": {"required": True}},
        {"name": "eventID", "constraints": {"required": True}},
    ],
    "foreignKeys": [],
}

MOCK_SURVEY_TARGET = {
    "fields": [
        {"name": "surveyTargetID", "constraints": {"required": True}},
        {"name": "surveyID", "constraints": {"required": True}},
    ],
    "foreignKeys": [
        {
            "fields": "surveyID",
            "predicate": "for",
            "reference": {"resource": "survey", "fields": "surveyID"},
        }
    ],
}


def _write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _make_dp(tmp_path: Path, survey_rows, target_rows) -> dict:
    _write_csv(tmp_path / "survey.csv", survey_rows)
    _write_csv(tmp_path / "survey-target.csv", target_rows)
    return {
        "resources": [
            {"name": "survey", "path": "survey.csv", "format": "csv",
             "schema": {"fields": []}},
            {"name": "survey-target", "path": "survey-target.csv", "format": "csv",
             "schema": {"fields": []}},
        ]
    }


def _inject(monkeypatch) -> None:
    monkeypatch.setattr(schema_check, "_cache", {
        "survey": MOCK_SURVEY,
        "survey-target": MOCK_SURVEY_TARGET,
    })


class TestReferentialIntegrity:
    def test_valid_fk_no_error(self, tmp_path, monkeypatch):
        _inject(monkeypatch)
        dp = _make_dp(tmp_path,
            survey_rows=[{"surveyID": "S1", "eventID": "E1"}],
            target_rows=[{"surveyTargetID": "T1", "surveyID": "S1"}],
        )
        report = Report()
        integrity_check.check(dp, tmp_path, report, fetch=True)
        assert not report.issues

    def test_invalid_fk_is_error(self, tmp_path, monkeypatch):
        _inject(monkeypatch)
        dp = _make_dp(tmp_path,
            survey_rows=[{"surveyID": "S1", "eventID": "E1"}],
            target_rows=[{"surveyTargetID": "T1", "surveyID": "MISSING"}],
        )
        report = Report()
        integrity_check.check(dp, tmp_path, report, fetch=True)
        errors = [i for i in report.issues if i.severity == Severity.ERROR]
        assert len(errors) == 1
        assert errors[0].field_name == "surveyID"
        assert "MISSING" in errors[0].message
        assert errors[0].row == 2

    def test_multiple_invalid_fk_rows_all_reported(self, tmp_path, monkeypatch):
        _inject(monkeypatch)
        dp = _make_dp(tmp_path,
            survey_rows=[{"surveyID": "S1", "eventID": "E1"}],
            target_rows=[
                {"surveyTargetID": "T1", "surveyID": "MISSING_A"},
                {"surveyTargetID": "T2", "surveyID": "S1"},
                {"surveyTargetID": "T3", "surveyID": "MISSING_B"},
            ],
        )
        report = Report()
        integrity_check.check(dp, tmp_path, report, fetch=True)
        errors = [i for i in report.issues if i.severity == Severity.ERROR]
        assert len(errors) == 2

    def test_empty_fk_value_no_error(self, tmp_path, monkeypatch):
        _inject(monkeypatch)
        dp = _make_dp(tmp_path,
            survey_rows=[{"surveyID": "S1", "eventID": "E1"}],
            target_rows=[{"surveyTargetID": "T1", "surveyID": ""}],
        )
        report = Report()
        integrity_check.check(dp, tmp_path, report, fetch=True)
        assert not report.issues

    def test_referenced_table_absent_skips(self, tmp_path, monkeypatch):
        _inject(monkeypatch)
        _write_csv(tmp_path / "survey-target.csv", [
            {"surveyTargetID": "T1", "surveyID": "MISSING"},
        ])
        dp = {
            "resources": [
                {"name": "survey-target", "path": "survey-target.csv",
                 "format": "csv", "schema": {"fields": []}},
            ]
        }
        report = Report()
        integrity_check.check(dp, tmp_path, report, fetch=True)
        assert not report.issues

    def test_fetch_false_skips(self, tmp_path, monkeypatch):
        _inject(monkeypatch)
        dp = _make_dp(tmp_path,
            survey_rows=[{"surveyID": "S1", "eventID": "E1"}],
            target_rows=[{"surveyTargetID": "T1", "surveyID": "MISSING"}],
        )
        report = Report()
        integrity_check.check(dp, tmp_path, report, fetch=False)
        assert not report.issues
