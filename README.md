# dwcdp-validate

A CLI validator for [DarwinCore Data Packages](https://github.com/gbif/dwc-dp) (dwc-dp),
an emerging biodiversity data exchange standard built on top of
[Frictionless Data Packages](https://specs.frictionlessdata.io/).

## Installation

Requires Python 3.11+ and [uv](https://github.com/astral-sh/uv).

```bash
uv sync
uv tool install .
```

## Usage

```
dwcdp-validate PATH [OPTIONS]

Arguments:
  PATH    Path to a datapackage.json file, a directory containing one,
          or a gzip archive (.gz) as specified by the DwC-DP standard.

Options:
  --format [text|json]          Output format (default: text)
  --level [error|warning|info]  Minimum severity to show (default: warning)
  --no-fetch                    Skip remote schema fetching (offline mode)
  --help
```

**Exit codes:** `0` = valid, `1` = validation errors found, `2` = tool/usage error.

### Examples

```bash
# Validate a directory
uv run dwcdp-validate path/to/my-package/

# JSON output, show all issues including info
uv run dwcdp-validate path/to/my-package/ --format json --level info

# Offline mode (no network requests to fetch official schemas)
uv run dwcdp-validate path/to/my-package/ --no-fetch

# Validate a gzip archive (the only archive format the DwC-DP spec permits)
uv run dwcdp-validate my-package.tar.gz
```

## Validation layers

### Layer 1 — Frictionless structural validation

Delegates to `frictionless.validate()` for free structural checks:

- JSON validity and required `datapackage.json` fields
- UTF-8 CSV encoding, RFC 4180 compliance
- Field type/format/constraint violations (required, unique, enum, pattern, min/max)
- Primary key uniqueness and foreign key referential integrity

### Layer 2a — DwC-DP profile conformance

- Top-level `profile` is a recognised DwC-DP profile URL (error if absent/wrong)
- Each resource has `profile: "tabular-data-resource"` (error)
- Each resource `mediatype` is `text/csv` or `text/tab-separated-values` (warning)
- Resource `name` is from the DwC-DP reserved list (warning)
- Top-level `id`, `created`, `version` fields are present (warning)

### Layer 2b — Field conformance

For each resource, field names in the local schema are compared against the
official table schema fetched from the
[gbif/dwc-dp](https://github.com/gbif/dwc-dp) repository. Unknown fields
produce a warning. Skipped with `--no-fetch`.

### Layer 3 — DwC semantic checks

Row-level checks across all CSV/TSV files:

| Field | Severity | Rule |
|---|---|---|
| `basisOfRecord` | error | must be in the DwC controlled vocabulary |
| `occurrenceStatus` | error | must be `present` or `absent` |
| `decimalLatitude` | error | must be in [-90, 90] |
| `decimalLongitude` | error | must be in [-180, 180] |
| `geodeticDatum` | warning | should be present when lat/lon are given |
| `coordinateUncertaintyInMeters` | error | must be > 0 |
| `countryCode` | warning | must be a valid ISO 3166-1 alpha-2 code |
| `taxonRank` | warning | must be in the DwC controlled vocabulary |
| `eventDate` | error | must be a valid ISO 8601 date, datetime, or interval |

## Development

```bash
# Install with dev dependencies
uv sync

# Run tests
uv run pytest tests/ -v

# Run against the bundled example fixtures
uv run dwcdp-validate tests/fixtures/dwc-dp-examples/observation/bird-tracking/output_data/ --no-fetch
```
