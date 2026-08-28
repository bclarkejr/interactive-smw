# AGENTS.md
## Project
Summer Movie Wager — Python ≥3.11 static-site generator (batch pipeline, static HTML output). This repo also serves as a learning ground for a fully agentic coding workflow (see CONTRIBUTING.md).

## Deterministic checks (must pass before any review round)
- Install: `uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python --config-settings editable_mode=compat -e '.[dev]'`
- Test: `.venv/bin/pytest`
- Worker test: `cd worker && npm ci && npm test` (Node ≥20; `npm run deploy`/`wrangler` itself needs Node ≥22. The players API in `worker/` has its own suite)
- Lint: not configured
- Types/Build: not configured

## Conventions
- Reproducible output: identical inputs (including the run date) must produce byte-identical HTML across builds. The run date is the only wall-clock input: the CLI takes it via `--date` and, by design, defaults it to today's calendar date when the flag is omitted — that default is not a defect.
- Self-contained pages: zero network requests from published friends-group pages — all CSS/JS inlined, no remote fonts (system font stack), no runtime fetch, no external links in output. Exception (play-along spec §5.1): `play.html` and `join.html` make exactly one `fetch()` each to the `api_base_url` configured in `play.yaml` and reference no other origin.
- No module-level date or threshold constants in projection, simulation, or render layers. Game/model constants (point values, day-of-week weights, sigma tables) are allowed as module constants; dates and tunables are not.
- No type may carry film data and roster data together. `score`, `simulate`, `render` take `(Season, Group, MovieCatalog)` and never read global state; `render()` takes an output directory parameter.
- `smw/score/rules.py` depends on nothing but the roster type.
- No network in tests. The chart HTML is a committed fixture.
- Persisted data is exactly the files in spec §5 laid out per season as `data/seasons/<year>/` (`season.yaml`, `play.yaml` [optional, play-along spec §6.1], `groups/*.yaml`, `preopening_projections.yaml`, `movies_overrides.yaml`, `box_office_history.jsonl`, `forecast_history/<group_id>.jsonl`). There is deliberately **no persisted refresh/run-date record**: a degraded production refresh appends nothing (§5.6), and a refresh date that is consequently absent from the odds-over-time axis is accepted behaviour, not a defect. Reviewers must not request refresh-date persistence.
- Autoescaping is forced on unconditionally in Jinja2; embedded JSON escapes `<` as `\u003c`.

## Review protocol
- The review workflow applies to implementation changes for the Summer Movie
  Wager application.
- Non-trivial application changes require a spec in `superpowers/specs/` and a
  passing cross-review (see CONTRIBUTING.md) before merge.
- Changes that only establish or maintain the agent workflow, review harness,
  repository instructions, or workflow documentation are outside this
  cross-review requirement and should be validated directly.
