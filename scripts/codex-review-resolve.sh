#!/usr/bin/env bash
# Usage: scripts/codex-review-resolve.sh retry|accept
#
# Recovery tool for after the gate's 10-round cap has been hit. The cap
# deliberately leaves both the round counter and the `.unresolved`
# marker in place (see codex-review-gate.sh), so clearing them back out
# has to be an explicit, intentional action rather than something that
# happens by accident.
#
# `set -euo pipefail`: -e exits immediately if any command fails (unlike
# the other two scripts, this one is a short, linear set of file
# operations with no expected-failure branches, so failing fast is
# safe); -u errors on unset variables; pipefail makes a pipeline fail if
# any stage of it does.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
STATE_DIR="$(git rev-parse --git-dir)/codex-review"
BRANCH_KEY="$(git symbolic-ref --quiet --short HEAD | tr '/' '_')"
case "${1:-}" in
  retry)   # findings fixed — intentionally restart the review loop at round zero
    rm -f "$STATE_DIR/$BRANCH_KEY-"*.rounds "$STATE_DIR/$BRANCH_KEY-"*.unresolved ;;
  accept)  # human arbitration stands in for approval — release the gate entirely
    # `accept` substitutes a human decision for an approval, so the decision
    # has to actually exist, be committed, and name the revision it covers —
    # otherwise this is just a way to silence the gate.
    ARB=".codex/arbitration/$BRANCH_KEY.json"
    HEAD_SHA="$(git rev-parse HEAD)"
    jq -e '(.decision | type == "string") and (.decision | length > 0)' "$ARB" >/dev/null 2>&1 \
      || { echo "No decision recorded: add a non-empty \"decision\" field to $ARB" >&2; exit 1; }
    REVIEWED="$(jq -r '.reviewed_head // ""' "$ARB")"
    git merge-base --is-ancestor "$REVIEWED" HEAD 2>/dev/null \
      || { echo "$ARB names reviewed_head '$REVIEWED', which is not an ancestor of HEAD" >&2; exit 1; }
    # Everything between the arbitrated commit and HEAD must be the decision
    # itself — otherwise this would release the gate over unreviewed code.
    UNREVIEWED="$(git diff --name-only "$REVIEWED" HEAD -- . ':(exclude).codex/arbitration')"
    [ -z "$UNREVIEWED" ] \
      || { echo "Code changed since $REVIEWED: $(echo "$UNREVIEWED" | tr '\n' ' ')— re-review instead (codex-review-resolve.sh retry)" >&2; exit 1; }
    git ls-files --error-unmatch "$ARB" >/dev/null 2>&1 \
      || { echo "$ARB is not committed — commit your decision first" >&2; exit 1; }
    git diff --quiet HEAD -- "$ARB" \
      || { echo "$ARB has uncommitted edits — commit your decision first" >&2; exit 1; }
    rm -f "$STATE_DIR/$BRANCH_KEY-"*.rounds "$STATE_DIR/$BRANCH_KEY-"*.unresolved \
          "$STATE_DIR/$BRANCH_KEY.active-spec"
    printf '%s\n' "$HEAD_SHA" > "$STATE_DIR/$BRANCH_KEY.approved-sha"
    echo "Gate released for $HEAD_SHA on the strength of $ARB." ;;
  *) echo "usage: codex-review-resolve.sh retry|accept" >&2; exit 1 ;;
esac
