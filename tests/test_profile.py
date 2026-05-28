"""Tests for the profile conformance checks (Layer 2a)."""
# pylint: disable=missing-function-docstring,missing-class-docstring
from dwc_dp_validate.checks.profile import check, KNOWN_DWC_DP_PROFILES
from dwc_dp_validate.report import Report, Severity


def _run(dp: dict) -> Report:
    report = Report()
    check(dp, report)
    return report


def _errors(report: Report) -> list[str]:
    return [i.message for i in report.issues if i.severity == Severity.ERROR]


def _warnings(report: Report) -> list[str]:
    return [i.message for i in report.issues if i.severity == Severity.WARNING]


VALID_PROFILE = "https://raw.githubusercontent.com/gbif/dwc-dp/0.1/dwc-dp/dwc-dp-profile.json"


def _minimal_dp(**overrides) -> dict:
    base = {
        "profile": VALID_PROFILE,
        "name": "test",
        "id": "test-id",
        "created": "2026-01-01",
        "version": "1.0",
        "resources": [],
    }
    base.update(overrides)
    return base


def _minimal_resource(name: str = "occurrence", **overrides) -> dict:
    base = {
        "name": name,
        "path": f"{name}.csv",
        "profile": "tabular-data-resource",
        "mediatype": "text/csv",
        "schema": {"fields": []},
    }
    base.update(overrides)
    return base


class TestProfileField:
    def test_valid_profile_no_error(self):
        report = _run(_minimal_dp())
        assert not _errors(report)

    def test_all_known_profiles_accepted(self):
        for url in KNOWN_DWC_DP_PROFILES:
            report = _run(_minimal_dp(profile=url))
            assert not _errors(report), f"Unexpected error for profile {url!r}"

    def test_missing_profile_is_error(self):
        dp = _minimal_dp()
        del dp["profile"]
        errors = _errors(_run(dp))
        assert any("profile" in e for e in errors)

    def test_generic_frictionless_profile_is_error(self):
        errors = _errors(_run(_minimal_dp(profile="tabular-data-package")))
        assert any("profile" in e for e in errors)

    def test_wrong_url_is_error(self):
        errors = _errors(_run(_minimal_dp(profile="http://example.com/other")))
        assert any("profile" in e for e in errors)


class TestTopLevelMetadata:
    def test_missing_id_is_warning(self):
        dp = _minimal_dp()
        del dp["id"]
        warnings = _warnings(_run(dp))
        assert any("'id'" in w for w in warnings)

    def test_missing_created_is_warning(self):
        dp = _minimal_dp()
        del dp["created"]
        warnings = _warnings(_run(dp))
        assert any("'created'" in w for w in warnings)

    def test_missing_version_is_warning(self):
        dp = _minimal_dp()
        del dp["version"]
        warnings = _warnings(_run(dp))
        assert any("'version'" in w for w in warnings)

    def test_all_present_no_warning(self):
        report = _run(_minimal_dp())
        meta_warnings = [
            w for w in _warnings(report)
            if any(f in w for f in ("'id'", "'created'", "'version'"))
        ]
        assert not meta_warnings


class TestResourceChecks:
    def test_missing_tabular_profile_is_error(self):
        dp = _minimal_dp(resources=[_minimal_resource(profile="data-resource")])
        errors = _errors(_run(dp))
        assert any("tabular-data-resource" in e for e in errors)

    def test_correct_resource_profile_no_error(self):
        dp = _minimal_dp(resources=[_minimal_resource()])
        report = _run(dp)
        assert not any("tabular-data-resource" in e for e in _errors(report))

    def test_wrong_mediatype_is_warning(self):
        dp = _minimal_dp(resources=[_minimal_resource(mediatype="application/json")])
        warnings = _warnings(_run(dp))
        assert any("mediatype" in w for w in warnings)

    def test_tsv_mediatype_accepted(self):
        dp = _minimal_dp(resources=[
            _minimal_resource(mediatype="text/tab-separated-values")
        ])
        report = _run(dp)
        assert not any("mediatype" in w for w in _warnings(report))

    def test_unknown_resource_name_is_warning(self):
        dp = _minimal_dp(resources=[_minimal_resource(name="my-custom-table")])
        warnings = _warnings(_run(dp))
        assert any("my-custom-table" in w for w in warnings)

    def test_reserved_resource_name_no_warning(self):
        dp = _minimal_dp(resources=[_minimal_resource(name="occurrence")])
        report = _run(dp)
        name_warnings = [w for w in _warnings(report) if "occurrence" in w and "reserved" in w]
        assert not name_warnings
