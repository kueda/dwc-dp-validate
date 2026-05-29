"""Click entry point for dwc-dp-validate."""
from __future__ import annotations

import sys
from pathlib import Path

import click

from .validator import validate


@click.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--level",
    type=click.Choice(["error", "warning", "info"]),
    default="warning",
    show_default=True,
    help="Minimum severity to show.",
)
@click.option(
    "--no-fetch",
    is_flag=True,
    default=False,
    help="Skip remote schema fetching (offline mode).",
)
@click.option(
    "--detail",
    is_flag=True,
    default=False,
    help="Show every row-level issue instead of a grouped summary.",
)
def cli(path: Path, output_format: str, level: str, no_fetch: bool, detail: bool) -> None:
    """Validate a DarwinCore Data Package.

    PATH may be a datapackage.json file, a directory containing one,
    or a gzip archive (.gz) as specified by the DwC-DP standard.
    """
    report = validate(path, fetch=not no_fetch)
    color = sys.stdout.isatty()

    if output_format == "json":
        click.echo(report.as_json(min_level=level))
    elif detail:
        click.echo(report.as_text(min_level=level, color=color))
    else:
        click.echo(report.as_text_summary(min_level=level, color=color))

    sys.exit(0 if report.valid else 1)
