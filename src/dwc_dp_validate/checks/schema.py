"""Layer 2: Field conformance against official DwC-DP table schemas."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Optional

import requests

from ..report import Issue, Report, Severity

SCHEMA_BASE_URL = (
    "https://raw.githubusercontent.com/gbif/dwc-dp/master/dwc-dp/table-schemas/"
)
BUNDLED_SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"

_cache: dict[str, Optional[list[dict]]] = {}


def _fetch_fields(name: str) -> Optional[list[dict]]:
    if name in _cache:
        return _cache[name]

    bundled = BUNDLED_SCHEMAS_DIR / f"{name}.json"
    if bundled.exists():
        try:
            data = json.loads(bundled.read_text())
            result = data.get("fields", [])
            _cache[name] = result
            return result
        except Exception:
            pass

    try:
        resp = requests.get(f"{SCHEMA_BASE_URL}{name}.json", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            result = data.get("fields", [])
            _cache[name] = result
            return result
    except Exception:
        pass

    _cache[name] = None
    return None


def get_required_field_names(name: str) -> Optional[set[str]]:
    """Return the set of required field names for the named table, or None if unknown."""
    fields = _fetch_fields(name)
    if fields is None:
        return None
    return {f["name"] for f in fields if f.get("constraints", {}).get("required")}


def _get_delimiter(resource: dict) -> str:
    fmt = resource.get("format", "csv").lower()
    dialect = resource.get("dialect", {})
    if isinstance(dialect, dict):
        return dialect.get("delimiter", "\t" if fmt in ("tsv", "tab") else ",")
    return "\t" if fmt in ("tsv", "tab") else ","


def check(
    dp: dict,
    report: Report,
    fetch: bool = True,
    base_dir: Optional[Path] = None,
) -> None:
    """Warn on unknown fields; error on missing required columns."""
    if not fetch:
        return

    for resource in dp.get("resources", []):
        name = resource.get("name", "")
        schema = resource.get("schema", {})
        if isinstance(schema, str):
            continue

        fields = _fetch_fields(name)
        if fields is None:
            continue

        official_names = {f["name"] for f in fields}
        local_declared = {f["name"] for f in schema.get("fields", []) if "name" in f}

        for field_name in sorted(local_declared - official_names):
            report.add(Issue(
                severity=Severity.WARNING,
                resource=name,
                field_name=field_name,
                message=(
                    f"Field '{field_name}' is not in the official DwC-DP schema "
                    f"for '{name}'."
                ),
            ))

        if base_dir is None:
            continue

        required = {f["name"] for f in fields if f.get("constraints", {}).get("required")}
        path_str = resource.get("path", "")
        if not required or not path_str:
            continue

        csv_path = base_dir / path_str
        if not csv_path.exists():
            continue

        delimiter = _get_delimiter(resource)
        try:
            with open(csv_path, newline="", encoding="utf-8-sig") as fh:
                headers = set(next(csv.reader(fh, delimiter=delimiter), []))
            for field_name in sorted(required - headers):
                report.add(Issue(
                    severity=Severity.ERROR,
                    resource=name,
                    field_name=field_name,
                    message=f"Required field '{field_name}' is missing from '{name}'.",
                ))
        except Exception:
            pass
