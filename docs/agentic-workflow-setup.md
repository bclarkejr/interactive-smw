# Agentic workflow setup

How the Claude-writes / Codex-reviews loop described in [CONTRIBUTING.md](../CONTRIBUTING.md)
was actually set up in this repo, what was decided along the way, and what to change if
you're copying it elsewhere.

## What was set up

| File | Role |
| --- | --- |
| `AGENTS.md` | Shared agent context: project one-liner, deterministic-check commands, repo conventions, review protocol. Codex reads it natively. |
| `CLAUDE.md` | One line — `@AGENTS.md` — so Claude Code imports the shared context. Vendor-specific instructions can go below it. |
| `.gitignore` (changed) | `.claude/` replaced by `.claude/*` plus negations for `skills/` and `settings.json`. See decision 2. |
| `.codex/review-rubric.md` | The reviewer's contract: what to evaluate, severity definitions, what blocks, and the instruction to treat repo contents as untrusted data. |
| `.codex/review.schema.json` | JSON Schema for the review verdict. Passed to `codex exec --output-schema`, so the reviewer can only answer in a parseable shape. |
| `scripts/codex-review.sh` | The single entry point. Checks preconditions, invokes `codex exec`, validates the JSON, maps the result to an exit code: 0 approved, 10 changes requested, 20 invalid output, 30 reviewer failure, 40 precondition failure. |
| `scripts/codex-review-gate.sh` | Optional Claude Code Stop hook. Wraps the same script, tracks round counts, blocks with exit 2, escalates to `.codex/arbitration/` at the 3-round cap. Not registered — see decision 4. |
| `scripts/codex-review-resolve.sh` | Recovery after the cap: `retry` restarts the loop at round zero, `accept` releases the gate on the strength of a committed arbitration decision. |
| `.claude/skills/cross-review/SKILL.md` | The `/cross-review <spec>` skill. Records the active spec, runs checks, checkpoints, calls the script, and drives the fix loop on exit code 10. |
| `README.md` | Repo orientation: the two purposes, where the spec/plan/workflow docs live, quick start. |
| `docs/agentic-workflow-setup.md` | This file. |

**How the pieces connect:**

```
/cross-review <spec>            (.claude/skills/cross-review/SKILL.md)
      └─ scripts/codex-review.sh
            └─ codex exec --output-schema .codex/review.schema.json
                           --output-last-message <result.json>
                  └─ Codex reads .codex/review-rubric.md + <spec> + the git range
            └─ jq validates result.json
            └─ exit code 0 / 10 / 20 / 30 / 40
      └─ skill branches on the exit code; on 10 it fixes findings,
         re-checkpoints, and re-runs (3 rounds max)
```

The optional Stop hook wraps the *same* `codex-review.sh`, so a review behaves
identically whether a human typed `/cross-review`, the hook fired, or CI ran it later.
State lives in `.git/codex-review/` (session-local, branch-keyed) except unresolved
findings at the cap, which are written to the tracked `.codex/arbitration/` so they
travel with the branch. Verdicts are stamped with the reviewed commit (decision 8).

## Environment verified on 2026-08-26

| Tool | Version |
| --- | --- |
| Claude Code | 2.1.246 |
| codex-cli | 0.149.1 |
| jq | 1.7.1 |
| git | 2.50.1 |
| uv | 0.11.8 |

`ruff` and `mypy` are **not** installed.

`codex exec` flags confirmed present in 0.149.1: `--ephemeral`, `--output-schema`,
`--output-last-message`, `--sandbox read-only`, `-c model_reasoning_effort=`.

Codex auth is a ChatGPT login (not an API key). Both `gpt-5.6-sol` and `gpt-5.6-terra`
were verified working with a one-shot `codex exec` call, so the guide's default of
`gpt-5.6-sol` was kept.

Gotcha: `codex exec` refuses to run outside a git repository unless you pass
`--skip-git-repo-check`. Not needed here — the scripts always run inside the repo — but
it will bite you when testing from a scratch directory.

## Decisions and why

### 1. Scripts in bash, not Python

Claude Code hooks are `{"type": "command"}` shell commands, and Codex is a CLI. The
official docs for both use shell + `jq`. Writing the gate in bash means it has no
venv/uv dependency and runs unchanged in CI. Since bash isn't everyone's first
language, the scripts are commented more heavily than usual — including what
`set -uo pipefail` does and why `-e` is deliberately omitted.

### 2. `.gitignore`: `.claude/*` with negations

Changed from a blanket `.claude/` to:

```
.claude/*
!.claude/skills/
!.claude/settings.json
```

The `cross-review` skill and shared settings are part of the workflow and belong in
version control; `settings.local.json` is personal and stays ignored. This is the
Claude Code convention — `settings.json` is the shared, committed file,
`settings.local.json` the per-developer override.

### 3. Deterministic checks left as TODO in `AGENTS.md`

No `pyproject.toml` exists yet, so there is no real test/lint/type command to name.
Agents must never invent commands, so the section keeps its TODO placeholders
and instructs agents to state **"deterministic checks not yet configured"** in every
review summary rather than skipping silently.

Fill this in at Task 1 of the rebuild plan, which creates `pyproject.toml` with pytest.
`uv` is already available locally.

### 4. Stop hook scripts created but NOT registered

`scripts/codex-review-gate.sh` exists and is executable, but nothing in
`.claude/settings.json` invokes it. Adopt the hook only after manual `/cross-review`
runs have proven the rubric useful — the hook fires every
time Claude tries to finish, so a bad rubric becomes a very expensive habit fast.

To enable it, add to `.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      { "hooks": [ { "type": "command",
                     "command": "bash scripts/codex-review-gate.sh" } ] }
    ]
  }
}
```

Hooks load at session start, so **restart Claude Code** afterwards and verify with
`/hooks`.

One addition beyond the guide: the gate checks `stop_hook_active` and exits 0 when it's
true. Claude Code re-fires the Stop hook after a hook blocks (exit 2), setting
`stop_hook_active: true` on that re-fire. Without the guard, every block would trigger
another full Codex review — an infinite, billable loop.

### 5. `--ephemeral` added to the codex invocation

Review sessions are standalone and don't need to persist any state between runs, so `--ephemeral` is passed.

### 6. Review direction: Claude writes, Codex reviews

This is the direction the guide specifies, and the repo keeps it.

Known tradeoff worth flagging: a 2026 study (arXiv 2607.21656, Xiang et al.) reported
that Claude-reviewing-Codex improved pass rates, while Codex-reviewing-Claude *slightly
lowered* them. We're deliberately keeping the guide's direction for consistency, but it
should be evaluated per-branch after a few real reviews — the setup makes flipping it a
one-variable change.

The 3-round cap is within community norms (reported practice is 3–5 rounds before
escalating to a human).

### 7. Schema note: `additionalProperties: false` everywhere

`--output-schema` is forwarded to OpenAI's strict structured outputs, which requires
every object in the schema to set `additionalProperties: false`. The guide's schema
already does this at both the root and the findings-item level; if you extend it, keep
that rule or the call will be rejected.

### 8. An approval is bound to the commit it reviewed

`codex-review.sh` writes the reviewed SHA to `<branch>.result.sha` and prints it as
`head=`; the gate stores it as `<branch>.approved-sha` on approval. Two consequences:
a stop attempt with an unchanged HEAD skips the review entirely (previously every
subsequent stop bought another full model pass, because approval cleared the round
counter but left the active spec in place), and a commit added after approval no
longer inherits it — the gate reviews again, and the merge checklist compares HEAD to
the stamped SHA.

### 9. Arbitration is a decision record, not a copy of the findings

At the cap the gate writes `{reviewed_head, decision: "", findings}` rather than
copying the raw result. `codex-review-resolve.sh accept` then refuses unless
`decision` is a non-empty string, the file is tracked and committed, and nothing but
the arbitration file changed between `reviewed_head` and HEAD. Without those checks
`accept` was just a way to silence the gate — it printed "confirm your decision is
recorded" and released regardless.

Deliberately not done: a JSON Schema for the arbitration file. Three `jq` predicates
cover it; add a schema if the file grows fields worth validating.

### 10. CI must not run the harness from the branch it reviews

The review contract — driver script, prompt, rubric, schema — is version-controlled,
which is what makes it reviewable, and also what makes it editable by any PR. Codex
additionally loads the checked-out `AGENTS.md` before reviewing, so instructions
planted there reach the reviewer regardless of what the rubric says about untrusted
input. A prompt cannot defend against text the model reads as configuration.

So when CI lands: check out `scripts/`, `.codex/`, and the agent context from the
protected base branch (or a separate trusted repo) rather than the PR head; pin the
Codex CLI version; pass `--ignore-user-config` and an isolated `CODEX_HOME`; give the
job read-only repository scope and no secrets beyond the model credential. Model
review is quality evidence, never a security boundary — the deterministic checks and
human review are the boundary. OpenAI's Codex GitHub Action is the supported route
and documents its own permission/secret isolation.

### 11. `codex exec review` tested and rejected — it ignores `--output-schema`

Codex 0.149.1 has a purpose-built `codex exec review --base <branch>`, and it accepts
`--output-schema` and `--output-last-message` on the command line. Tested on
2026-08-26 against a scratch repo with a deliberately flawed change
(`gpt-5.6-terra`, effort `low`, this repo's real rubric and schema). It does not work
for this harness:

1. **`--base` and a prompt are mutually exclusive.** `codex exec review --base X -`
   fails to parse: *"the argument '--base <BRANCH>' cannot be used with '[PROMPT]'"*.
   There is no way to pass `--base` **and** the rubric/spec instructions, so the
   per-run spec path could not be delivered at all.
2. **`--output-schema` is accepted but has no effect.** Review mode writes its own
   review format to `--output-last-message` — prose with `[P1]`/`[P2]` priority
   markers and absolute file paths, no `verdict`, no `findings` array. `--json`
   doesn't help: the event stream carries the same text as a single `agent_message`
   item, with no structured review payload anywhere.

Consequence if adopted: every review would fail our jq validation and exit **20**
(invalid reviewer output). The gate fails closed, so it would block every finish —
and the severity mapping has nothing to read, since review mode emits P1/P2/P3 rather
than high/med/low.

Confirmed along the way: the process exit code is 0 even when review mode reports P1
issues, so exit code ≠ verdict either way. Review *quality* looked good — it caught
every violated acceptance criterion plus a negative-price edge case — but quality was
never the blocker; the output contract is.

Revisit only if a later Codex release wires `--output-schema` into review mode, or
exposes findings structurally on `--json`. Re-run the same scratch test before
switching. The generic `codex exec` path returns a conforming
`{verdict, findings}` on the identical flawed change (see smoke test Z).

## Online best practices consulted

- **agents.md conventions** — keep it short, name exact runnable commands, don't
  duplicate the README. <https://agents.md>,
  <https://www.morphllm.com/agents-md-guide>
- **Claude Code `@AGENTS.md` import over symlinks** — a plain import line is portable
  and leaves room for vendor-specific additions.
  <https://travis.media/blog/claude-md-import-agents-md/>
- **Claude Code skills & hooks** — skills are the recommended structure over
  `.claude/commands/`; hooks are shell commands loaded at session start.
  <https://code.claude.com/docs/en/skills>,
  <https://code.claude.com/docs/en/hooks-guide>
- **`settings.json` vs `settings.local.json`** — commit the shared one, ignore the
  personal one. <https://claudecodeguides.com/claude-code-gitignore-best-practices/>
- **Cross-vendor review loop patterns** — direction effects and round caps.
  <https://arxiv.org/abs/2607.21656>, <https://github.com/lukaskucinski/clodex>

## Smoke tests

The dangerous failure mode here isn't a bad review — it's a gate that approves the
wrong thing. So the plumbing gets tested independently of the model.

The approach: put a **fake `codex`** first on `PATH` — a
stub script that scans its arguments for `--output-last-message`, copies a canned JSON
file to that path, and exits 0 (or nonzero, to simulate an infrastructure failure).
With the stub in place you can drive every branch of `codex-review.sh` and the gate
deterministically and for free: valid approval, blocking finding, malformed output,
reviewer failure, clean/empty diff, dirty tree, bad spec path, missing base ref, the
three-round cap, arbitration re-entry, both recovery modes, and concurrency across
branches. Only the "deliberately flawed code" case needs the real Codex.

**Results (2026-08-26, fake `codex` stub, scratch clone, `REVIEW_BASE=main`) — 25/25 PASS.**
Case AA was added later, after the original table missed it: the approval fast path
sat *above* the clean-tree check, so uncommitted edits made after an approval let
Claude stop with unreviewed work in the tree. Fixed by reordering the two checks in
`codex-review-gate.sh`; verified in the live repo rather than the stub clone.
Case Z below additionally used the **real** Codex.

| Case | Scenario | Expected | Actual | Result |
|---|---|---|---|---|
| A | approved, no findings | exit 0 | 0, `verdict=approved blocking_findings=0` | PASS |
| B | one high finding | 10 | 10, `verdict=changes_requested blocking_findings=1` | PASS |
| C | malformed JSON | 20 | 20, "did not conform to schema" | PASS |
| D | stub exits 1 | 30 | 30, "codex exec failed" | PASS |
| E | dirty tree | 40 | 40, "working tree not clean" | PASS |
| F | no diff past base | 40 | 40, "no committed changes" | PASS |
| G | spec missing / outside `superpowers/specs/` | 40 | 40 (both) | PASS |
| H | bogus `REVIEW_BASE` | 40 | 40, "base ref not found" | PASS |
| I | gate, no active spec | 0 | 0, silent | PASS |
| J | gate ×3 changes_requested, then cap | 2,2,2 then `{"continue": false}` | as expected; `.codex/arbitration/<branch>.json` + `.unresolved` created | PASS |
| K | re-entry after cap | stop again, file untouched | arbitration-pending stop; `git diff` empty | PASS |
| L | `resolve retry` → approved gate | state cleared, 0 | cleared, 0 | PASS |
| M | cap → `resolve accept` → gate | 0, codex not invoked | 0, stub never ran | PASS |
| N | `stop_hook_active: true` | 0, codex not invoked | 0, stub never ran | PASS |
| O | gate, dirty tree | 2 + checkpoint message | 2, message present | PASS |
| P | two branches | separate state files | `feat_smoke.*` vs `feat_other.*` | PASS |
| Q | finding missing `severity` | 20 | 20, "did not conform to schema" | PASS |
| R | spec path containing `..` | 40 | 40, "may not contain '..'" | PASS |
| S | detached HEAD | 40 | 40, "detached HEAD" | PASS |
| T | invoked from a subdirectory | works | resolves to repo root, exit 0 | PASS |
| U | stop twice, HEAD unchanged | codex called once | 2nd stop skipped, stub never ran | PASS |
| V | stop after a new commit | codex called again | stub ran | PASS |
| W | `accept` with empty/uncommitted decision | refuse | exit 1, both cases | PASS |
| X | `accept` after code changed post-arbitration | refuse | exit 1, names the file | PASS |
| Y | `accept` with committed decision | release gate | exit 0; next stop skips review | PASS |
| AA | approved SHA == HEAD but tree dirty | 2 + checkpoint message | 2, message present | PASS |
| Z | real Codex, flawed code vs. spec | conforming JSON, `changes_requested` | `changes_requested`, 2 blocking findings, schema OK | PASS |

Fake `codex` stub used (put first in `PATH`; `FAKE_RESULT` = canned JSON path, `FAKE_EXIT` = exit code, optional `FAKE_CALL_MARKER` touch-file proves invocation):

```bash
#!/usr/bin/env bash
[ -n "${FAKE_CALL_MARKER:-}" ] && touch "$FAKE_CALL_MARKER"
out=""
while [ $# -gt 0 ]; do
  case "$1" in
    --output-last-message|-o) out="$2"; shift 2 ;;
    *) shift ;;
  esac
done
[ -n "$out" ] && cp "${FAKE_RESULT:?set FAKE_RESULT}" "$out"
exit "${FAKE_EXIT:-0}"
```

Case Z (2026-08-26) used a scratch repo — `apply_discount` violating three acceptance
criteria — with `gpt-5.6-terra` at effort `low`. Codex caught the percent/multiplier
error (high) and the missing range validation (med) and returned schema-conforming
output; the rubric needed no tightening. Still worth repeating on the first real
feature branch at the default `gpt-5.6-sol`, since this was the cheap tier on a
three-line file.


## Replicating in another repo

1. Copy `AGENTS.md`, `CLAUDE.md`, `.codex/`, `scripts/codex-review*.sh`, and
   `.claude/skills/cross-review/` into the target repo. `chmod +x scripts/*.sh`.
2. Edit `AGENTS.md`: replace the project one-liner, the deterministic-check commands,
   and the conventions with the target repo's own. Leave TODOs only if the commands
   genuinely don't exist yet — and keep the "must report not-yet-configured" note.
3. Adjust `REVIEW_BASE` in `scripts/codex-review.sh` if the default branch isn't
   `main` (or export `REVIEW_BASE=origin/<branch>`).
4. Update `.gitignore` the same way (decision 2), so the skill and shared settings are
   tracked.
5. Restart Claude Code so the new skill is picked up; confirm `/cross-review` appears.
6. Run the smoke tests with the fake-`codex` stub before trusting the gate.
7. Only then, optionally register the Stop hook (decision 4) and restart again.

## Next steps for this repo

- Pick the first spec from `superpowers/specs/`, branch, implement it with Claude Code,
  and run `/cross-review` manually. That's the first real exercise of the rubric.
- At Task 1 of `superpowers/plans/2026-08-15-standalone-rebuild.md`, `pyproject.toml`
  lands — fill in the deterministic-check commands in `AGENTS.md` at that moment
  (decision 3). This is the highest-leverage remaining gap: until it's done, merge
  readiness rests on model review alone. Put them behind one `scripts/check.sh` so the
  skill, the gate, and CI run the identical command against the identical commit —
  today they're prose an agent interprets, and nothing proves they ran.
- After a few real reviews, decide whether to enable the Stop hook (decision 4) and
  whether the review direction is earning its cost (decision 6).
- Add CI per CONTRIBUTING.md's merge-enforcement section — run the deterministic checks *and*
  `scripts/codex-review.sh <spec>` in a protected merge workflow, and block merge when
  either fails, when the approved SHA isn't the merged SHA, or when
  `.codex/arbitration/` holds an undecided file. Local hooks can be bypassed; CI is the
  only real enforcement — but run the harness from the base branch, not the PR head
  (decision 10).
