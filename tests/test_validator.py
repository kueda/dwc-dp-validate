"""Integration tests for the full validation pipeline."""
import tarfile
import tempfile
from pathlib import Path

import pytest

from dwc_dp_validate.validator import validate
from dwc_dp_validate.report import Severity

FIXTURES = Path(__file__).parent / "fixtures"
BIRD_TRACKING = FIXTURES / "dwc-dp-examples" / "observation" / "bird-tracking" / "output_data"
INVALID_MISSING_PROFILE = FIXTURES / "invalid_missing_profile"
INVALID_BAD_VALUES = FIXTURES / "invalid_bad_values"


class TestBirdTrackingFixture:
    def test_no_frictionless_errors(self):
        report = validate(BIRD_TRACKING, fetch=False)
        frictionless_errors = [
            i for i in report.issues
            if i.severity == Severity.ERROR
            and "frictionless" not in i.message.lower()
            and i.resource in ("event", "occurrence", "occurrence-assertion", None)
        ]
        # The bird-tracking package should have no structural errors
        structural_errors = [
            i for i in report.issues
            if i.severity == Severity.ERROR
        ]
        assert not structural_errors, (
            f"Unexpected errors in bird-tracking fixture:\n"
            + "\n".join(i.message for i in structural_errors)
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

    def test_bad_occurrence_status_error(self):
        report = validate(INVALID_BAD_VALUES, fetch=False)
        errors = [i.message for i in report.issues if i.severity == Severity.ERROR]
        assert any("occurrenceStatus" in e for e in errors)

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
        from pathlib import Path
        import pytest
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
            assert not any(i.severity == Severity.ERROR for i in report.issues)

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
        import json
        report = validate(INVALID_MISSING_PROFILE, fetch=False)
        parsed = json.loads(report.as_json())
        assert "valid" in parsed
        assert "issues" in parsed
        assert parsed["valid"] is False
