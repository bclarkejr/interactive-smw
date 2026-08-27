# AGENTS.md
## Project
Summer Movie Wager — Python ≥3.11 static-site generator (batch pipeline, static HTML output). This repo also serves as a learning ground for a fully agentic coding workflow (see CONTRIBUTING.md).

## Deterministic checks (must pass before any review round)
- Install: `uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e '.[dev]'`
- Test: `.venv/bin/pytest`
- Lint: not configured
- Types/Build: not configured

## Conventions
- Reproducible output: identical inputs must produce byte-identical HTML across builds; nothing reads wall-clock time except an explicitly passed `--date`.
- Self-contained pages: zero network requests from published pages — all CSS/JS inlined, no remote fonts (system font stack), no runtime fetch, no external links in output.
- No module-level date or threshold constants in projection, simulation, or render layers. Game/model constants (point values, day-of-week weights, sigma tables) are allowed as module constants; dates and tunables are not.
- No type may carry film data and roster data together. `score`, `simulate`, `render` take `(Season, Group, MovieCatalog)` and never read global state; `render()` takes an output directory parameter.
- `smw/score/rules.py` depends on nothing but the roster type.
- No network in tests. The chart HTML is a committed fixture.
- Autoescaping is forced on unconditionally in Jinja2; embedded JSON escapes `<` as `\u003c`.

## Review protocol
- The review workflow applies to implementation changes for the Summer Movie
  Wager application.
- Non-trivial application changes require a spec in `superpowers/specs/` and a
  passing cross-review (see CONTRIBUTING.md) before merge.
- Changes that only establish or maintain the agent workflow, review harness,
  repository instructions, or workflow documentation are outside this
  cross-review requirement and should be validated directly.
