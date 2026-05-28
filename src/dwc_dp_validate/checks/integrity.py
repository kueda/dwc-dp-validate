"""Layer 2c: Referential integrity checks across tables."""
from __future__ import annotations

import csv
from pathlib import Path

from ..report import Issue, Report, Severity
from . import schema as schema_check


def _get_delimiter(resource: dict) -> str:
    fmt = resource.get("format", "csv").lower()
    dialect = resource.get("dialect", {})
    if isinstance(dialect, dict):
        return dialect.get("delimiter", "\t" if fmt in ("tsv", "tab") else ",")
    return "\t" if fmt in ("tsv", "tab") else ","


def _load_column_values(csv_path: Path, field_name: str, delimiter: str) -> set[str]:
    values: set[str] = set()
    try:
        with open(csv_path, newline="", encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh, delimiter=delimiter):
                val = row.get(field_name, "").strip()
                if val:
                    values.add(val)
    except Exception:
        pass
    return values


def check(dp: dict, base_dir: Path, report: Report, fetch: bool = True) -> None:
    """Error when a foreign key value has no matching row in the referenced table."""
    if not fetch:
        return

    resources_by_name = {r.get("name", ""): r for r in dp.get("resources", [])}
    key_cache: dict[tuple[str, str], set[str]] = {}

    for resource in dp.get("resources", []):
        name = resource.get("name", "")
        path_str = resource.get("path", "")
        if not path_str:
            continue
        csv_path = base_dir / path_str
        if not csv_path.exists():
            continue

        fk_defs = schema_check.get_foreign_keys(name)
        if not fk_defs:
            continue

        delimiter = _get_delimiter(resource)

        for fk in fk_defs:
            local_field = fk.get("fields", "")
            ref = fk.get("reference", {})
            ref_resource_name = ref.get("resource", "")
            ref_field = ref.get("fields", "")

            if not local_field or not ref_resource_name or not ref_field:
                continue  # skip self-references and malformed definitions

            if ref_resource_name not in resources_by_name:
                continue  # referenced table not present in this package

            ref_resource = resources_by_name[ref_resource_name]
            ref_path_str = ref_resource.get("path", "")
            if not ref_path_str:
                continue
            ref_csv_path = base_dir / ref_path_str
            if not ref_csv_path.exists():
                continue

            cache_key = (ref_resource_name, ref_field)
            if cache_key not in key_cache:
                ref_delimiter = _get_delimiter(ref_resource)
                key_cache[cache_key] = _load_column_values(
                    ref_csv_path, ref_field, ref_delimiter
                )
            valid_keys = key_cache[cache_key]

            try:
                with open(csv_path, newline="", encoding="utf-8-sig") as fh:
                    reader = csv.DictReader(fh, delimiter=delimiter)
                    for row_num, row in enumerate(reader, start=2):
                        val = row.get(local_field, "").strip()
                        if val and val not in valid_keys:
                            report.add(Issue(
                                severity=Severity.ERROR,
                                resource=name,
                                row=row_num,
                                field_name=local_field,
                                message=(
                                    f"{local_field} {val!r} in '{name}' does not "
                                    f"reference a row in '{ref_resource_name}'."
                                ),
                            ))
            except Exception as exc:
                report.add(Issue(
                    severity=Severity.ERROR,
                    resource=name,
                    message=f"Could not read '{name}' for integrity check: {exc}",
                ))
