# Interactive SMW

This repo has two purposes.

**1. Build the Summer Movie Wager website.** A Python static-site generator for a
season-long box-office prediction game: ingest the yearly chart, project each film's
final in-window gross, Monte-Carlo-simulate the season, and render a small
self-contained static site with win probabilities, projected scores, and per-player
breakdowns. The full specification lives in
[`superpowers/specs/`](superpowers/specs/); the task-by-task implementation plan lives
in [`superpowers/plans/`](superpowers/plans/).

**2. Learn a fully agentic coding workflow.** Claude Code writes the code; GPT Codex
reviews the committed changes against the spec and a version-controlled review
contract; blocking findings go back to Claude for fixes. The workflow is documented in
[CONTRIBUTING.md](CONTRIBUTING.md); how it was set up in this repo, and why each
decision went the way it did, is in
[docs/agentic-workflow-setup.md](docs/agentic-workflow-setup.md).

**The application code isn't written yet.** What exists today is the spec, the plan,
and the review harness.

## Quick start

Prerequisites: `claude` (Claude Code CLI), `codex` (Codex CLI) — both installed and
authenticated — and `jq`.

Work on a feature branch, implement against a spec, checkpoint-commit, then:

```
/cross-review superpowers/specs/<feature>.md
```

That runs the deterministic checks, hands the committed diff to Codex, and loops on
blocking findings (3 rounds max). See [CONTRIBUTING.md](CONTRIBUTING.md) for the full
day-to-day workflow and merge criteria.
