#!/usr/bin/env bash
# Usage: scripts/codex-review.sh superpowers/specs/<feature>.md
# Exit codes: 0 approved | 10 changes requested | 20 invalid reviewer output
#             30 reviewer infra failure         | 40 precondition failure
#
# In plain English, those exit codes mean:
#   0  = Codex looked at the diff and has no blocking complaints.
#   10 = Codex looked at the diff and wants something fixed first.
#   20 = Codex answered, but not in the JSON shape we asked for — don't
#        trust it as either an approval or a rejection.
#   30 = we couldn't even get an answer out of Codex (auth/network/etc).
#   40 = we never got as far as asking Codex — something about the repo
#        state (dirty tree, missing spec, bad base ref, no changes) means
#        there's nothing valid to review yet.
#
# `set -uo pipefail`: -u makes referencing an unset variable an error
# instead of silently expanding to an empty string (catches typos in
# variable names); pipefail makes a pipeline (e.g. `a | b`) fail if any
# stage fails, not just the last one. (We skip `-e` deliberately: several
# commands below are expected to "fail" as normal control flow — e.g. the
# jq schema check — and we want to handle that ourselves via `fail`
# rather than have the script die immediately.)
set -uo pipefail

SPEC_PATH="${1:-}"
REVIEW_BASE="${REVIEW_BASE:-origin/main}"      # this repo's default branch is main
MODEL="${CODEX_REVIEW_MODEL:-gpt-5.6-sol}"
EFFORT="${CODEX_REVIEW_EFFORT:-medium}"

# Small helper so every failure path prints a consistent message to
# stderr and exits with the documented code, instead of repeating
# `echo ... >&2; exit N` everywhere.
fail() { echo "codex-review: $2" >&2; exit "$1"; }

# Hooks and CI may invoke this from anywhere in the worktree; every path
# below (spec, schema, rubric) is repo-relative.
cd "$(git rev-parse --show-toplevel)" 2>/dev/null || fail 40 "not inside a git repository"

# --- Preconditions -----------------------------------------------------
# Everything in this block is a sanity check that must hold BEFORE we
# spend a model call on a review. If any of them fail, exit 40 — a
# precondition problem, not a verdict.
case "$SPEC_PATH" in
  *..*)    fail 40 "spec path may not contain '..': $SPEC_PATH" ;;
  superpowers/specs/*) [ -f "$SPEC_PATH" ] || fail 40 "spec not found: $SPEC_PATH" ;;
  *)       fail 40 "usage: codex-review.sh superpowers/specs/<feature>.md" ;;
esac
# Detached HEAD has no branch name, so every detached checkout would share
# one state key. Refuse rather than mix state across unrelated commits.
BRANCH="$(git symbolic-ref --quiet --short HEAD)" \
  || fail 40 "detached HEAD — check out a branch before reviewing"
git rev-parse --verify --quiet "${REVIEW_BASE}^{commit}" >/dev/null \
  || fail 40 "base ref '$REVIEW_BASE' not found — run 'git fetch' or set REVIEW_BASE"
# The tree must be clean because the review only ever looks at COMMITTED
# history ($REVIEW_BASE...HEAD). If uncommitted edits exist, Codex can't
# see them (it only inspects the git range) but they'd land in whatever
# gets merged — so an "approved" verdict would be reviewing different
# code than what actually ships. Committing first (a checkpoint commit)
# keeps what's reviewed and what's merged identical.
[ -z "$(git status --porcelain)" ] \
  || fail 40 "working tree not clean — create a checkpoint commit first"
# Resolve the merge base explicitly: `git diff --quiet A...B` returns 1 for
# "there are differences" but 128 for errors (unrelated histories, bad ref),
# and a bare `&& fail` would let that error fall through as a real diff.
MERGE_BASE="$(git merge-base "$REVIEW_BASE" HEAD)" \
  || fail 40 "no common ancestor between $REVIEW_BASE and HEAD"
git diff --quiet "$MERGE_BASE" HEAD; DIFF_RC=$?
[ "$DIFF_RC" -eq 0 ] && fail 40 "no committed changes between $REVIEW_BASE and HEAD"
[ "$DIFF_RC" -eq 1 ] || fail 40 "git diff failed (exit $DIFF_RC)"

STATE_DIR="$(git rev-parse --git-dir)/codex-review"
mkdir -p "$STATE_DIR"
BRANCH_KEY="$(echo "$BRANCH" | tr '/' '_')"
RESULT_FILE="$STATE_DIR/$BRANCH_KEY.result.json"   # branch-keyed: concurrent sessions can't clobber
HEAD_SHA="$(git rev-parse HEAD)"

# --- Invoke the reviewer (read-only; prompt via stdin, no diff inlining) ---
# The diff itself is never passed as a shell argument or inlined into the
# prompt. Two reasons: (1) diffs can be arbitrarily large and blow past
# shell/argument length limits; (2) handing Codex the git range instead
# of a text blob lets it actually run `git` itself to explore call
# sites, tests, and surrounding code — a static diff snippet can't do
# that. So we only tell it *which range* to look at, via the heredoc
# prompt on stdin, and let it inspect the repository directly
# (`--sandbox read-only` means it can look but not modify anything).
# `--ephemeral` tells Codex this session's state doesn't need to persist
# after this run — each review is a fresh, standalone pass.
codex exec \
  --sandbox read-only \
  --ephemeral \
  --model "$MODEL" \
  -c model_reasoning_effort="$EFFORT" \
  --output-schema .codex/review.schema.json \
  --output-last-message "$RESULT_FILE" \
  - <<EOF
Review the committed changes in the range $REVIEW_BASE...HEAD of this
repository. Follow the rubric in .codex/review-rubric.md exactly. The
spec under review is $SPEC_PATH. Read both files yourself, and inspect
the repository as the rubric permits.
EOF
[ $? -eq 0 ] || fail 30 "codex exec failed (auth/model/network/timeout) — review was NOT performed"

# --- Validate and interpret the result --------------------------------
# Don't trust the reviewer's output just because the process exited 0.
# `--output-schema` already constrains the real Codex, but the consumer must
# not depend on that: a missing `severity` would silently count as zero
# blocking findings and approve. Check every field the script reads.
jq -e '
  (.verdict == "approved" or .verdict == "changes_requested")
  and (.findings | type == "array")
  and ([.findings[] | select(
        (.file    | type == "string")
    and (.line    | type == "number")
    and (.severity | IN("high","med","low"))
    and (.issue   | type == "string")
    and (.suggestion | type == "string")
  )] | length) == (.findings | length)' \
  "$RESULT_FILE" >/dev/null 2>&1 \
  || fail 20 "reviewer output did not conform to schema — see $RESULT_FILE"

BLOCKING=$(jq '[.findings[] | select(.severity == "high" or .severity == "med")] | length' "$RESULT_FILE")
VERDICT=$(jq -r '.verdict' "$RESULT_FILE")
# Bind the verdict to the exact revision reviewed, so a later commit can't
# inherit this approval. Merge checks (and CI) compare this against HEAD.
printf '%s\n' "$HEAD_SHA" > "$STATE_DIR/$BRANCH_KEY.result.sha"
echo "verdict=$VERDICT blocking_findings=$BLOCKING head=$HEAD_SHA model=$MODEL/$EFFORT result=$RESULT_FILE"
[ "$VERDICT" = "approved" ] && [ "$BLOCKING" -eq 0 ] && exit 0
exit 10
