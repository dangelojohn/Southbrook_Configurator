#!/usr/bin/env bash
# Trigger a QNAP-side pull deploy with one short SSH command.
#
# This is the sandbox-friendly deploy path. It does not use local rsync, scp,
# tar-over-SSH, or stdin streaming. The QNAP downloads committed code from
# Forgejo and performs the addon replacement + Odoo upgrade locally.

set -euo pipefail

MODULES_ARG="${1:-}"
[[ -n "$MODULES_ARG" ]] || {
  echo "Usage: $0 module[,module...]"
  echo "Example: $0 southbrook_floor_traveler,southbrook_premium_orchestration"
  exit 2
}

QNAP_HOST="${QNAP_HOST:-admin@192.168.68.108}"
REF="${REF:-$(git rev-parse HEAD)}"
SCRIPT_REF="${SCRIPT_REF:-$REF}"
RAW_SCRIPT_URL="${RAW_SCRIPT_URL:-http://192.168.68.108:9080/git/qnap/southbrook-v19cr/raw/commit/$SCRIPT_REF/scripts/qnap_pull_deploy.sh}"
TEST_TAGS="${TEST_TAGS:-}"

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "[qnap-pull-trigger] ERROR: worktree has uncommitted changes; commit and push first." >&2
  exit 2
fi

echo "[qnap-pull-trigger] host: $QNAP_HOST" >&2
echo "[qnap-pull-trigger] ref: $REF" >&2
echo "[qnap-pull-trigger] modules: $MODULES_ARG" >&2

remote_cmd="/sbin/curl -fsSL '$RAW_SCRIPT_URL' | /bin/bash -s -- --ref '$REF' --modules '$MODULES_ARG'"
if [[ -n "$TEST_TAGS" ]]; then
  remote_cmd="$remote_cmd --test-tags '$TEST_TAGS'"
  echo "[qnap-pull-trigger] test-tags: $TEST_TAGS" >&2
fi

ssh -o BatchMode=yes -o ConnectTimeout=15 "$QNAP_HOST" "$remote_cmd"
