---
name: cross-review
description: Run the spec-driven Codex review loop on committed changes.
  Use when the user invokes /cross-review with a spec path, or asks to
  cross-review a feature before finishing it.
---

Input: an explicit spec path, e.g. `/cross-review superpowers/specs/<feature>.md`.
If no path was provided, ask which spec applies — never guess.

1. Validate the path: it must exist and be under `superpowers/specs/`.
2. Record it for the hook (branch-keyed so concurrent sessions on
   other branches can't overwrite it):
   `S="$(git rev-parse --git-dir)/codex-review"; mkdir -p "$S" && echo "<spec>" > "$S/$(git rev-parse --abbrev-ref HEAD | tr '/' '_').active-spec"`
3. Run the deterministic checks listed in AGENTS.md (tests, lint,
   types). Fix failures before requesting review. If that section still
   contains TODO placeholders, do not invent commands — proceed, but
   state "deterministic checks not yet configured" in your summary so
   the user knows merge readiness rests on review alone.
4. Ensure a clean working tree by creating a checkpoint commit —
   but stage ONLY the files you created or modified for this task,
   listed explicitly (`git add <paths>`), never `git add -A`. Run
   `git status` first: if unrelated modified or untracked files
   remain, ask the user whether to stash them or commit them
   separately — do not sweep another person's or session's work into
   your checkpoint. Every review round reviews committed state only.
5. Run `scripts/codex-review.sh <spec>` and branch on the exit code:
   - 0  — approved. Report the verdict, the reviewed commit (the `head=`
          value the script prints — the approval covers that commit and
          nothing later), and the deterministic-check results, then stop.
   - 10 — read the findings JSON. Fix every high/med finding (if you
          believe a finding is factually wrong, say so with reasoning
          instead of "fixing" it). Re-run checks, create another
          checkpoint commit, and repeat from step 5.
   - 20/30/40 — a precondition or infrastructure problem, not a review
          outcome. Report the script's message to the user verbatim.
          Do not retry blindly and never treat it as approval.
6. Hard cap: 3 review rounds. If not approved by then, stop the loop,
   summarize the unresolved findings and both sides' reasoning, and
   hand the decision to the user.
