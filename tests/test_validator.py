"""Integration tests for the full validation pipeline."""
# pylint: disable=missing-function-docstring,missing-class-docstring
import json
import tarfile
import tempfile
from pathlib import Path

from dwc_dp_validate.validator import validate
from dwc_dp_validate.report import Issue, Report, Severity

FIXTURES = Path(__file__).parent / "fixtures"
BIRD_TRACKING = FIXTURES / "dwc-dp-examples" / "observation" / "bird-tracking" / "output_data"
CONABIO_BEES = (
    FIXTURES / "dwc-dp-examples" / "organism_interaction" / "conabio-bees" / "output_data"
)
INVALID_MISSING_PROFILE = FIXTURES / "invalid_missing_profile"
INVALID_BAD_VALUES = FIXTURES / "invalid_bad_values"
OVERLAP_VIOLATIONS = FIXTURES / "overlap_violations"


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

    def test_as_text_summary_groups_by_file(self):
        report = validate(CONABIO_BEES, fetch=False)
        summary = report.as_text_summary()
        # event.tsv has geodeticDatum warnings; it should appear as a section header
        assert "event.tsv" in summary
        # the geodeticDatum warning should be indented under the file header
        lines = summary.splitlines()
        file_idx = next(i for i, l in enumerate(lines) if l == "event.tsv")
        assert any("geodeticDatum" in lines[j] for j in range(file_idx + 1, len(lines)))

    def test_as_text_summary_groups_by_file_multi_path(self):
        r = Report()
        r.add(Issue(Severity.WARNING, "msg a", resource="foo", row=2,
                    field_name="f", path="foo.csv"))
        r.add(Issue(Severity.WARNING, "msg a", resource="foo", row=3,
                    field_name="f", path="foo.csv"))
        r.add(Issue(Severity.ERROR, "msg b", resource="bar", row=2,
                    field_name="g", path="bar.csv"))
        summary = r.as_text_summary()
        assert "foo.csv" in summary
        assert "bar.csv" in summary
        # foo.csv rows collapse to one line
        foo_section = summary[summary.index("foo.csv"):]
        assert "(2 rows)" in foo_section

    def test_as_text_detail_includes_path(self):
        report = validate(CONABIO_BEES, fetch=False)
        detail = report.as_text()
        row_lines = [l for l in detail.splitlines() if "geodeticDatum" in l]
        assert row_lines
        assert all("event.tsv" in l for l in row_lines)


class TestOverlapViolations:
    # This fixture exposes overlapping checks between frictionless (Layer 1)
    # and our own semantic checks (Layer 3). The same violation can produce
    # two errors: one from frictionless and one from us.

    def test_type_error_double_reported(self):
        # "forty-eight" in a number-typed decimalLatitude field fires both a
        # frictionless type-error and our own "not a number" semantic check.
        report = validate(OVERLAP_VIOLATIONS, fetch=False)
        errors = [i for i in report.issues if i.severity == Severity.ERROR
                  and i.row == 2 and (i.path or "").endswith("occurrence.csv")]
        messages = [i.message for i in errors]
        assert any("type" in m.lower() or "number/default" in m for m in messages)
        assert any("not a number" in m for m in messages)

    def test_required_constraint_reported_by_frictionless(self):
        # Empty occurrenceID (required+unique in schema) fires a frictionless
        # constraint-error; our required-field check only fires when fetch=True.
        report = validate(OVERLAP_VIOLATIONS, fetch=False)
        errors = [i.message for i in report.issues if i.severity == Severity.ERROR]
        assert any("constraint" in m and "required" in m for m in errors)

    def test_fk_violation_reported_by_frictionless(self):
        # "missing-event" in eventID has no match in event.csv; frictionless
        # catches this from the foreignKeys declared in the datapackage schema.
        # Our integrity check would also catch it, but only with fetch=True.
        report = validate(OVERLAP_VIOLATIONS, fetch=False)
        errors = [i.message for i in report.issues if i.severity == Severity.ERROR]
        assert any("foreign" in m.lower() for m in errors)
