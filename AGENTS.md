# AGENTS.md
## Project
Summer Movie Wager — Python ≥3.11 static-site generator (batch pipeline, static HTML output). This repo also serves as a learning ground for a fully agentic coding workflow (see CONTRIBUTING.md).

## Deterministic checks (must pass before any review round)
> STACK NOT YET CONFIRMED — replace this section once it is.
> Planned (superpowers/plans/2026-08-15-standalone-rebuild.md, Task 1): pyproject.toml + pytest; `uv` is available locally; ruff/mypy not yet decided.
- Install: TODO (e.g. `uv sync` / `npm ci`)
- Test: TODO (e.g. `uv run pytest` / `npm test`)
- Lint: TODO (e.g. `uv run ruff check .` / `npm run lint`)
- Types/Build: TODO (e.g. `uv run mypy .` / `npm run build`)
> While these are TODO, agents must report "deterministic checks not
> yet configured" in every review summary — never skip silently and
> never invent commands.

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
