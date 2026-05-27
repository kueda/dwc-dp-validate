"""Layer 2: Field conformance against official DwC-DP table schemas."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import requests

from ..report import Issue, Report, Severity

SCHEMA_BASE_URL = (
    "https://raw.githubusercontent.com/gbif/dwc-dp/master/dwc-dp/table-schemas/"
)
BUNDLED_SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"

_cache: dict[str, Optional[set[str]]] = {}


def _fetch_official_field_names(name: str) -> Optional[set[str]]:
    if name in _cache:
        return _cache[name]

    bundled = BUNDLED_SCHEMAS_DIR / f"{name}.json"
    if bundled.exists():
        try:
            data = json.loads(bundled.read_text())
            result = {f["name"] for f in data.get("fields", [])}
            _cache[name] = result
            return result
        except Exception:
            pass

    try:
        resp = requests.get(f"{SCHEMA_BASE_URL}{name}.json", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            result = {f["name"] for f in data.get("fields", [])}
            _cache[name] = result
            return result
    except Exception:
        pass

    _cache[name] = None
    return None


def check(dp: dict, report: Report, fetch: bool = True) -> None:
    """Warn when local field names are not present in the official schema."""
    if not fetch:
        return

    for resource in dp.get("resources", []):
        name = resource.get("name", "")
        schema = resource.get("schema", {})
        if isinstance(schema, str):
            continue
        local_fields = {f["name"] for f in schema.get("fields", []) if "name" in f}
        if not local_fields:
            continue

        official = _fetch_official_field_names(name)
        if official is None:
            continue

        for field_name in sorted(local_fields - official):
            report.add(Issue(
                severity=Severity.WARNING,
                resource=name,
                field_name=field_name,
                message=(
                    f"Field '{field_name}' is not in the official DwC-DP schema "
                    f"for '{name}'."
                ),
            ))
