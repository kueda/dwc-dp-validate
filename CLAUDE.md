# CLAUDE.md

See [AGENTS.md](AGENTS.md) for full project context, layout, and development
workflow.

## Claude-specific notes

- Run `uv run pytest tests/ -v` to verify changes. All tests must pass before
  reporting a task complete.
- Run `uv run pylint src/ tests/` after every change. Score must stay at 10.00/10.
- Every `# pylint: disable=<rule>` must include a brief justification for why suppression
  is appropriate. Do not suppress to make the score pass — fix the underlying issue unless
  suppression is genuinely right.
- Always pass `--no-fetch` / `fetch=False` in tests; do not make live network
  calls during testing.
- The `docs/plan.md` file describes the original design intent and is useful
  context when the spec is ambiguous, but the code is the source of truth.
