"""Integration tests for the full validation pipeline."""
# pylint: disable=missing-function-docstring,missing-class-docstring
import json
import tarfile
import tempfile
from pathlib import Path

from dwc_dp_validate.validator import validate
from dwc_dp_validate.report import Severity

FIXTURES = Path(__file__).parent / "fixtures"
BIRD_TRACKING = FIXTURES / "dwc-dp-examples" / "observation" / "bird-tracking" / "output_data"
CONABIO_BEES = FIXTURES / "dwc-dp-examples" / "organism_interaction" / "conabio-bees" / "output_data"
INVALID_MISSING_PROFILE = FIXTURES / "invalid_missing_profile"
INVALID_BAD_VALUES = FIXTURES / "invalid_bad_values"


class TestBirdTrackingFixture:
    def test_no_frictionless_errors(self):
        report = validate(BIRD_TRACKING, fetch=False)
        errors = [i for i in report.issues if i.severity == Severity.ERROR]
        assert not errors, (
            "Unexpected errors in bird-tracking fixture:\n"
            + "\n".join(i.message for i in errors)
        )

    def test_returns_report(self):
        report = validate(BIRD_TRACKING, fetch=False)
        assert report is not None
        assert isinstance(report.issues, list)

    def test_profile_warning_for_metadata(self):
        report = validate(BIRD_TRACKING, fetch=False)
        # bird-tracking is missing id/created/version → expect warnings
        messages = [i.message for i in report.issues if i.severity == Severity.WARNING]
        assert any("'id'" in m or "'created'" in m or "'version'" in m for m in messages)


class TestInvalidMissingProfile:
    def test_profile_error_detected(self):
        report = validate(INVALID_MISSING_PROFILE, fetch=False)
        errors = [i for i in report.issues if i.severity == Severity.ERROR]
        assert any("profile" in e.message.lower() for e in errors)

    def test_report_is_invalid(self):
        report = validate(INVALID_MISSING_PROFILE, fetch=False)
        assert not report.valid

    def test_exit_code_would_be_1(self):
        report = validate(INVALID_MISSING_PROFILE, fetch=False)
        assert not report.valid


class TestInvalidBadValues:
    def test_bad_basis_of_record_error(self):
        report = validate(INVALID_BAD_VALUES, fetch=False)
        errors = [i.message for i in report.issues if i.severity == Severity.ERROR]
        assert any("basisOfRecord" in e for e in errors)

    def test_nonrecommended_occurrence_status_info(self):
        report = validate(INVALID_BAD_VALUES, fetch=False)
        infos = [i.message for i in report.issues if i.severity == Severity.INFO]
        assert any("occurrenceStatus" in m for m in infos)

    def test_lat_out_of_range_error(self):
        report = validate(INVALID_BAD_VALUES, fetch=False)
        errors = [i.message for i in report.issues if i.severity == Severity.ERROR]
        assert any("decimalLatitude" in e for e in errors)

    def test_lon_out_of_range_error(self):
        report = validate(INVALID_BAD_VALUES, fetch=False)
        errors = [i.message for i in report.issues if i.severity == Severity.ERROR]
        assert any("decimalLongitude" in e for e in errors)

    def test_invalid_event_date_error(self):
        report = validate(INVALID_BAD_VALUES, fetch=False)
        errors = [i.message for i in report.issues if i.severity == Severity.ERROR]
        assert any("eventDate" in e for e in errors)

    def test_invalid_country_code_warning(self):
        report = validate(INVALID_BAD_VALUES, fetch=False)
        warnings = [i.message for i in report.issues if i.severity == Severity.WARNING]
        assert any("countryCode" in w for w in warnings)

    def test_report_is_invalid(self):
        report = validate(INVALID_BAD_VALUES, fetch=False)
        assert not report.valid


class TestPathResolution:
    def test_directory_path(self):
        report = validate(BIRD_TRACKING, fetch=False)
        assert report is not None

    def test_nonexistent_path_returns_error(self):
        report = validate(Path("/nonexistent/path"), fetch=False)
        errors = [i for i in report.issues if i.severity == Severity.ERROR]
        assert errors

    def test_explicit_datapackage_json_path(self):
        dp_path = BIRD_TRACKING / "datapackage.json"
        report = validate(dp_path, fetch=False)
        assert report is not None


class TestGzipArchive:
    def _make_archive(self, source_dir: Path, dest: Path) -> None:
        with tarfile.open(dest, "w:gz") as tf:
            for f in source_dir.iterdir():
                tf.add(f, arcname=f.name)

    def test_valid_package_in_gz_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "package.tar.gz"
            self._make_archive(BIRD_TRACKING, archive)
            report = validate(archive, fetch=False)
            errors = [i for i in report.issues if i.severity == Severity.ERROR]
            assert not errors

    def test_invalid_package_in_gz_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "package.tar.gz"
            self._make_archive(INVALID_MISSING_PROFILE, archive)
            report = validate(archive, fetch=False)
            assert not report.valid
            errors = [i.message for i in report.issues if i.severity == Severity.ERROR]
            assert any("profile" in e for e in errors)


class TestReportFormatting:
    def test_as_text_contains_status(self):
        report = validate(INVALID_MISSING_PROFILE, fetch=False)
        text = report.as_text()
        assert "INVALID" in text

    def test_as_json_is_valid_json(self):
        report = validate(INVALID_MISSING_PROFILE, fetch=False)
        parsed = json.loads(report.as_json())
        assert "valid" in parsed
        assert "issues" in parsed
        assert parsed["valid"] is False

    def test_as_text_summary_groups_row_issues(self):
        report = validate(CONABIO_BEES, fetch=False)
        summary = report.as_text_summary()
        lines = summary.splitlines()
        # geodeticDatum warning appears on many rows but should collapse to one line
        geod_lines = [l for l in lines if "geodeticDatum" in l]
        assert len(geod_lines) == 1
        assert "rows" in geod_lines[0]

    def test_as_text_summary_non_row_issues_shown_as_is(self):
        report = validate(INVALID_MISSING_PROFILE, fetch=False)
        summary = report.as_text_summary()
        assert "profile" in summary.lower()

    def test_as_text_summary_contains_status(self):
        report = validate(INVALID_MISSING_PROFILE, fetch=False)
        assert "INVALID" in report.as_text_summary()
