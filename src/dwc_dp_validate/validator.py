"""Orchestrates all validation layers and returns a unified Report."""
from __future__ import annotations

import json
import tarfile
import tempfile
from pathlib import Path
from typing import Optional

import frictionless

from .checks import profile as profile_check
from .checks import schema as schema_check
from .checks import semantic as semantic_check
from .report import Issue, Report, Severity


def _resolve_package_dir(path: Path) -> tuple[Path, Optional[Path]]:
    """Return (datapackage.json path, temp_dir_to_cleanup)."""
    tmp = None

    if path.is_dir():
        dp = path / "datapackage.json"
        if not dp.exists():
            raise FileNotFoundError(f"No datapackage.json in directory {path}")
        return dp, tmp

    if path.is_file() and path.name.endswith(".gz"):
        tmp_dir = tempfile.mkdtemp()
        tmp = Path(tmp_dir)
        with tarfile.open(path) as tf:
            tf.extractall(tmp_dir)
        dp = tmp / "datapackage.json"
        if not dp.exists():
            subdirs = [p for p in tmp.iterdir() if p.is_dir()]
            for sd in subdirs:
                candidate = sd / "datapackage.json"
                if candidate.exists():
                    return candidate, tmp
        if not dp.exists():
            raise FileNotFoundError(f"No datapackage.json found inside {path}")
        return dp, tmp

    if path.is_file() and path.name.endswith(".json"):
        return path, tmp

    raise FileNotFoundError(f"Cannot resolve datapackage from {path}")


def _frictionless_errors_to_issues(fr_report: frictionless.Report) -> list[Issue]:
    issues = []
    try:
        resource_reports = fr_report.resource_reports
    except AttributeError:
        return issues

    for rr in resource_reports:
        resource_name = None
        try:
            resource_name = rr.resource.name
        except AttributeError:
            pass

        for error in rr.errors:
            row = getattr(error, "row_number", None)
            field = getattr(error, "field_name", None)
            issues.append(Issue(
                severity=Severity.ERROR,
                message=error.message,
                resource=resource_name,
                row=row,
                field_name=field,
            ))
    return issues


def validate(
    path: Path,
    fetch: bool = True,
) -> Report:
    report = Report()
    tmp_dir: Optional[Path] = None

    try:
        try:
            dp_path, tmp_dir = _resolve_package_dir(path)
        except FileNotFoundError as exc:
            report.add(Issue(severity=Severity.ERROR, message=str(exc)))
            return report

        base_dir = dp_path.parent

        try:
            dp = json.loads(dp_path.read_text(encoding="utf-8"))
        except Exception as exc:
            report.add(Issue(
                severity=Severity.ERROR,
                message=f"Could not parse datapackage.json: {exc}",
            ))
            return report

        # Layer 1: Frictionless structural validation
        try:
            fr_report = frictionless.validate(str(dp_path))
            for issue in _frictionless_errors_to_issues(fr_report):
                report.add(issue)
        except Exception as exc:
            report.add(Issue(
                severity=Severity.ERROR,
                message=f"Frictionless validation failed: {exc}",
            ))

        # Layer 2a: DwC-DP profile conformance
        profile_check.check(dp, report)

        # Layer 2b: Field conformance against official schemas
        schema_check.check(dp, report, fetch=fetch)

        # Layer 3: DwC semantic checks
        semantic_check.check(dp, base_dir, report)

    finally:
        if tmp_dir is not None:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    return report
