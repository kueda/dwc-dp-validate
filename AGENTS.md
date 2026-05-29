# Agent Guide — dwcdp-validate

## What this project is

A Python CLI that validates DarwinCore Data Packages (dwc-dp), an emerging
biodiversity data exchange standard from GBIF built on Frictionless Data
Packages. The tool combines three validation layers: Frictionless structural
checks, DwC-DP profile conformance, and DwC semantic row-level rules.

The standard is new (released 2026-04-17) and still evolving. Real-world
examples live in `gbif/dwc-dp-examples`; the authoritative schema definitions
live in `gbif/dwc-dp`. Both repos are useful references when the spec is
ambiguous.

## Layout

```
src/dwcdp_validate/
├── cli.py          # Click entry point — thin, delegates to validator.py
├── validator.py    # Orchestrates all layers; resolves paths (dir/.gz/file)
├── report.py       # Issue dataclass + Report (valid, add, filtered, as_text, as_json)
└── checks/
    ├── profile.py  # Layer 2a: profile URL, metadata fields, resource names/mediatype
    ├── schema.py   # Layer 2b: field names vs official GitHub schemas (network, cached)
    └── semantic.py # Layer 3: basisOfRecord, occurrenceStatus, coords, dates, etc.
tests/
├── fixtures/
│   ├── dwc-dp-examples/          # git submodule → gbif/dwc-dp-examples (real data)
│   ├── invalid_missing_profile/  # hand-crafted: wrong top-level profile
│   └── invalid_bad_values/       # hand-crafted: bad lat/lon/dates/codes
├── test_profile.py
├── test_semantic.py
└── test_validator.py
```

## Development workflow

```bash
git submodule update --init   # populate tests/fixtures/dwc-dp-examples if not already present
uv sync                       # install deps (creates .venv automatically)
uv run pytest tests/ -v             # run all tests
uv run pylint src/ tests/           # lint — must stay at 10.00/10
uv run dwc-dp-validate tests/fixtures/dwc-dp-examples/observation/bird-tracking/output_data/ --no-fetch
```

Run **both** pytest and pylint after every change. Pylint must remain at 10.00/10.

Every `# pylint: disable=<rule>` comment must include a brief justification
explaining *why* the suppression is appropriate, e.g.:

```python
def _check_row(  # pylint: disable=too-many-arguments  # row context + report + required_fields are all distinct
```

Do not suppress a warning just to make the score pass — fix the underlying
issue unless suppression is genuinely the right call, and say why.

`tests/fixtures/dwc-dp-examples` is a git submodule pointing at
`gbif/dwc-dp-examples`. When cloning this repo, use
`git clone --recurse-submodules` to get it automatically, or run
`git submodule update --init` after a plain clone.

Always pass `--no-fetch` in tests and local development to avoid network
requests. The `fetch=False` parameter on `validate()` achieves the same thing
programmatically.

## Testing approach

- **TDD**: write a failing test before changing behaviour under test.
- Unit tests hit `checks/profile.py` and `checks/semantic.py` directly.
- Integration tests in `test_validator.py` call `validate()` end-to-end.
- Use `--no-fetch` / `fetch=False` everywhere; do not mock the network unless
  specifically testing the schema fetch path.
- Hand-crafted fixtures in `tests/fixtures/` are the source of truth for
  invalid-package tests; add new ones there rather than constructing large
  dicts inline.

## Severity model

`Severity.ERROR` → package is invalid, CLI exits 1.
`Severity.WARNING` → informational, package is still valid.
`Severity.INFO` → reserved for future use.

The `--level` flag filters display; `report.valid` is always based on
whether any ERROR-level issues exist.

## Important design notes

- **Profile URLs**: real examples use the GitHub raw URL, not the future
  `rs.tdwg.org` URL. Both are in `KNOWN_DWC_DP_PROFILES`; add new ones there
  as the spec stabilises rather than hardcoding elsewhere.

- **Reserved resource names**: the full list comes from the official
  `gbif/dwc-dp/dwc-dp/table-schemas/` directory (70+ names). Maintain this
  list in `checks/profile.py:RESERVED_RESOURCE_NAMES`.

- **Schema fetch cache**: `checks/schema.py` caches fetched schemas in a
  module-level `_cache` dict (per process). Tests that exercise schema
  fetching should clear or mock this cache.

- **Semantic checks are field-presence-conditional**: if a field is not in
  the row dict or is empty, the check is skipped silently. Do not error on
  absent optional fields.

- **TSV support**: some real examples (NEON-fish) use TSV. The delimiter is
  inferred from `resource.format` or `resource.dialect.delimiter`; always
  test new row-level checks with both CSV and TSV data.

## Adding a new semantic check

1. Write a failing test in `tests/test_semantic.py`.
2. Add the rule to `_check_row()` in `checks/semantic.py`.
3. Add a row to the `| Field | Severity | Rule |` table in `README.md`.

## Adding a new profile check

1. Write a failing test in `tests/test_profile.py`.
2. Add the rule to `check()` in `checks/profile.py`.
3. Update `README.md` if the check is user-visible.
