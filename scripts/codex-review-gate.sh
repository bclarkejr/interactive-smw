#!/usr/bin/env bash
# Claude Code "Stop" hook: runs every time Claude tries to finish, and can
# block that by exiting 2 (Claude then keeps going instead of stopping).
# This is a LOCAL convenience, not the merge-enforcement mechanism — see
# CONTRIBUTING.md for the real (manual, for now) enforcement story.
#
# `set -uo pipefail`: -u turns a reference to an unset variable into an
# error instead of a silent empty string (catches typos); pipefail makes
# a pipeline fail if any stage of it fails, not just the last command.
# We don't use `-e` because several commands here are expected to return
# non-zero as part of normal control flow (e.g. checking for a missing
# state file), and we want to handle those cases explicitly.
set -uo pipefail

HOOK_INPUT=$(cat)                                # consume hook stdin first —
#                                                — so Codex never inherits it

# Claude Code re-fires the Stop hook after a hook blocks (exit 2), passing
# stop_hook_active=true on that re-fire. Without this check we'd run a
# fresh Codex review every time Claude stops, including immediately after
# we just blocked it — an infinite review loop. Bailing out here means we
# only ever gate the *first* stop attempt in a cycle, not our own re-fire.
if [ "$(echo "$HOOK_INPUT" | jq -r '.stop_hook_active // false')" = "true" ]; then
  exit 0
fi

SESSION_ID=$(echo "$HOOK_INPUT" | jq -r '.session_id // "local"')

[ "${CODEX_REVIEW_BYPASS:-0}" = "1" ] && exit 0  # documented human bypass (local only)

cd "$(git rev-parse --show-toplevel)" 2>/dev/null || exit 0   # nothing to gate outside a repo
STATE_DIR="$(git rev-parse --git-dir)/codex-review"
BRANCH_KEY="$(git symbolic-ref --quiet --short HEAD | tr '/' '_')"
[ -n "$BRANCH_KEY" ] || exit 0                   # detached HEAD → no branch state to gate
RESULT_FILE="$STATE_DIR/$BRANCH_KEY.result.json"   # must match codex-review.sh
SPEC_PATH=$(cat "$STATE_DIR/$BRANCH_KEY.active-spec" 2>/dev/null || true)
[ -n "$SPEC_PATH" ] || exit 0                    # no active spec → nothing to gate

KEY="$BRANCH_KEY-$SESSION_ID"
ROUNDS=$(cat "$STATE_DIR/$KEY.rounds" 2>/dev/null || echo 0)

if [ -f "$STATE_DIR/$KEY.unresolved" ]; then     # cap already hit: don't restart at round zero
  cat <<JSON
{"continue": false, "stopReason": "Cross-review on this branch is awaiting human arbitration (see .codex/arbitration/). Record a decision there before continuing the loop."}
JSON
  exit 0
fi

# The tree must be clean before we can review anything — the reviewer
# only looks at committed history, so uncommitted work would be invisible
# to it (see codex-review.sh for the fuller explanation). Block here and
# ask for a checkpoint commit rather than silently reviewing stale state.
if [ -n "$(git status --porcelain)" ]; then
  echo "Working tree not clean. Commit this task's changes as a checkpoint — stage only files you changed, never 'git add -A'; ask the user about any unrelated files — then finish again." >&2
  exit 2                                          # block until state is reviewable
fi

# An approval belongs to the exact commit that was reviewed. If HEAD hasn't
# moved since, there is nothing new to review — don't spend another model
# call on every subsequent stop. If HEAD has moved, the approval is stale
# and the loop runs again. This check comes AFTER the clean-tree check:
# an approval covers the reviewed commit only, so uncommitted edits made
# after it must still be checkpointed and re-reviewed, not waved through.
HEAD_SHA="$(git rev-parse HEAD)"
[ "$(cat "$STATE_DIR/$BRANCH_KEY.approved-sha" 2>/dev/null)" = "$HEAD_SHA" ] && exit 0

if [ "$ROUNDS" -ge 3 ]; then
  mkdir -p .codex/arbitration
  # Stamp the commit the findings belong to, and leave `decision` empty for
  # the human — codex-review-resolve.sh accept requires both to be filled in
  # and committed. no-clobber: never overwrite a recorded decision.
  if [ ! -f ".codex/arbitration/$BRANCH_KEY.json" ]; then
    jq --arg h "$HEAD_SHA" '{reviewed_head: $h, decision: "", findings: .findings}' \
       "$RESULT_FILE" > "$STATE_DIR/arb.tmp" 2>/dev/null \
      && mv "$STATE_DIR/arb.tmp" ".codex/arbitration/$BRANCH_KEY.json"
    rm -f "$STATE_DIR/arb.tmp"
  fi
  touch "$STATE_DIR/$KEY.unresolved"
  cat <<JSON
{"continue": false, "stopReason": "Cross-review cap (3 rounds) reached WITHOUT approval. Unresolved findings saved to .codex/arbitration/$BRANCH_KEY.json — fill in its \"decision\" field, commit it, then run scripts/codex-review-resolve.sh accept (or retry after fixing the findings)."}
JSON
  exit 0                                          # structured stop: control returns to the human, visibly
fi

scripts/codex-review.sh "$SPEC_PATH"
RC=$?
case $RC in
  0)
    rm -f "$STATE_DIR/$KEY.rounds" "$STATE_DIR/$KEY.unresolved"
    printf '%s\n' "$HEAD_SHA" > "$STATE_DIR/$BRANCH_KEY.approved-sha"
    exit 0 ;;
  10)
    echo $((ROUNDS + 1)) > "$STATE_DIR/$KEY.rounds"
    SUMMARY=$(jq -r '[.findings[] | select(.severity != "low")][:5]
      | map("\(.file):\(.line) [\(.severity)] \(.issue)") | join("; ")' \
      "$RESULT_FILE")
    echo "Codex requested changes: $SUMMARY. Full result: $RESULT_FILE" >&2
    exit 2 ;;                                     # block: fix, checkpoint, finish again
  *)
    echo "Review gate could not run (exit $RC): see message above. Fix the issue, or set CODEX_REVIEW_BYPASS=1 to skip this local gate — merge enforcement remains in CI." >&2
    exit 2 ;;                                     # fail CLOSED: an error is never an approval
esac
