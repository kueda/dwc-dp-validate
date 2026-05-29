"""Shared helpers for check modules."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator


def get_delimiter(resource: dict) -> str:
    """Return the CSV delimiter for a resource descriptor dict."""
    fmt = resource.get("format", "csv").lower()
    dialect = resource.get("dialect", {})
    if isinstance(dialect, dict):
        return dialect.get("delimiter", "\t" if fmt in ("tsv", "tab") else ",")
    return "\t" if fmt in ("tsv", "tab") else ","


def iter_csv_resources(
    dp: dict, base_dir: Path
) -> Iterator[tuple[dict, str, Path, str]]:
    """Yield (resource, name, csv_path, path_str) for resources with an existing file."""
    for resource in dp.get("resources", []):
        path_str = resource.get("path", "")
        if not path_str:
            continue
        csv_path = base_dir / path_str
        if not csv_path.exists():
            continue
        yield resource, resource.get("name", "<unnamed>"), csv_path, path_str
