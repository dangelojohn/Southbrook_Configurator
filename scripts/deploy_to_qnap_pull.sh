#!/usr/bin/env bash
# Trigger a QNAP-side pull deploy with one short SSH command.
#
# This is the sandbox-friendly deploy path. It does not use local rsync, scp,
# tar-over-SSH, or stdin streaming. The QNAP downloads committed code from
# GitHub (or another archive URL) and performs the addon replacement + Odoo
# upgrade locally.

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
RAW_SCRIPT_URL="${RAW_SCRIPT_URL:-https://raw.githubusercontent.com/dangelojohn/Southbrook_Configurator/$SCRIPT_REF/scripts/qnap_pull_deploy.sh}"
REPO_ARCHIVE_BASE="${REPO_ARCHIVE_BASE:-https://github.com/dangelojohn/Southbrook_Configurator/archive}"
TEST_TAGS="${TEST_TAGS:-}"

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "[qnap-pull-trigger] ERROR: worktree has uncommitted changes; commit and push first." >&2
  exit 2
fi

echo "[qnap-pull-trigger] host: $QNAP_HOST" >&2
echo "[qnap-pull-trigger] ref: $REF" >&2
echo "[qnap-pull-trigger] modules: $MODULES_ARG" >&2
echo "[qnap-pull-trigger] archive-base: $REPO_ARCHIVE_BASE" >&2

remote_cmd="/sbin/curl -fsSL '$RAW_SCRIPT_URL' | REPO_ARCHIVE_BASE='$REPO_ARCHIVE_BASE' /bin/bash -s -- --ref '$REF' --modules '$MODULES_ARG'"
if [[ -n "$TEST_TAGS" ]]; then
  remote_cmd="$remote_cmd --test-tags '$TEST_TAGS'"
  echo "[qnap-pull-trigger] test-tags: $TEST_TAGS" >&2
fi

ssh -o BatchMode=yes -o ConnectTimeout=15 "$QNAP_HOST" "$remote_cmd"
