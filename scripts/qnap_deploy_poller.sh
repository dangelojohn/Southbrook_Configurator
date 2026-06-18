#!/usr/bin/env bash
# Run this ON THE QNAP host, typically from cron.
#
# Poll a GitHub-hosted deploy request file and, when REQUEST_ID changes, run
# qnap_pull_deploy.sh locally on the QNAP. This is the no-SSH deploy path for
# restricted agent sandboxes: the agent only pushes to GitHub; the QNAP pulls.

set -euo pipefail

REQUEST_URL="${REQUEST_URL:-https://raw.githubusercontent.com/dangelojohn/Southbrook_Configurator/feature/configurator-loop-p1-p8/deploy/qnap/request.env}"
PULL_SCRIPT_URL="${PULL_SCRIPT_URL:-https://raw.githubusercontent.com/dangelojohn/Southbrook_Configurator/feature/configurator-loop-p1-p8/scripts/qnap_pull_deploy.sh}"
REPO_ARCHIVE_BASE="${REPO_ARCHIVE_BASE:-https://github.com/dangelojohn/Southbrook_Configurator/archive}"
STATE_DIR="${STATE_DIR:-/share/CACHEDEV3_DATA/Container/southbrook/deploy-state}"
LOCK_PATH="${LOCK_PATH:-/tmp/sbk-qnap-deploy-poller.lock}"

log() { printf "[qnap-deploy-poller] %s\n" "$*" >&2; }
fail() { printf "[qnap-deploy-poller] ERROR: %s\n" "$*" >&2; exit 1; }

command -v curl >/dev/null || fail "curl not found on QNAP"
command -v flock >/dev/null || fail "flock not found on QNAP"
mkdir -p "$STATE_DIR"

exec 9>"$LOCK_PATH"
if ! flock -n 9; then
  log "another poller is running; skip"
  exit 0
fi

request_file="$(mktemp /tmp/sbk-qnap-request.XXXXXX)"
cleanup() { rm -f "$request_file"; }
trap cleanup EXIT

if ! curl -fsSL "$REQUEST_URL" -o "$request_file"; then
  log "no deploy request available at $REQUEST_URL"
  exit 0
fi

REQUEST_ID=""
REF=""
MODULES=""
TEST_TAGS=""
REQUEST_REPO_ARCHIVE_BASE=""
REQUEST_PULL_SCRIPT_URL=""

while IFS='=' read -r key value; do
  case "$key" in
    REQUEST_ID) REQUEST_ID="$value" ;;
    REF) REF="$value" ;;
    MODULES) MODULES="$value" ;;
    TEST_TAGS) TEST_TAGS="$value" ;;
    REPO_ARCHIVE_BASE) REQUEST_REPO_ARCHIVE_BASE="$value" ;;
    PULL_SCRIPT_URL) REQUEST_PULL_SCRIPT_URL="$value" ;;
    ""|"#"*) ;;
    *) log "ignoring unknown request key: $key" ;;
  esac
done < "$request_file"

[[ "$REQUEST_ID" =~ ^[A-Za-z0-9._:-]+$ ]] || fail "invalid or missing REQUEST_ID"
[[ "$REF" =~ ^[A-Za-z0-9._/-]+$ ]] || fail "invalid or missing REF"
[[ "$MODULES" =~ ^[A-Za-z0-9_,]+$ ]] || fail "invalid or missing MODULES"
if [[ -n "$TEST_TAGS" && ! "$TEST_TAGS" =~ ^[-A-Za-z0-9_:/.,]+$ ]]; then
  fail "invalid TEST_TAGS"
fi
if [[ -n "$REQUEST_REPO_ARCHIVE_BASE" ]]; then
  REPO_ARCHIVE_BASE="$REQUEST_REPO_ARCHIVE_BASE"
fi
if [[ -n "$REQUEST_PULL_SCRIPT_URL" ]]; then
  PULL_SCRIPT_URL="$REQUEST_PULL_SCRIPT_URL"
fi

state_file="$STATE_DIR/last_request_id"
last_request_id="$(cat "$state_file" 2>/dev/null || true)"
if [[ "$last_request_id" == "$REQUEST_ID" ]]; then
  log "request $REQUEST_ID already applied; skip"
  exit 0
fi

log "applying request: $REQUEST_ID"
log "ref: $REF"
log "modules: $MODULES"
log "script: $PULL_SCRIPT_URL"
log "archive-base: $REPO_ARCHIVE_BASE"

cmd="/sbin/curl -fsSL '$PULL_SCRIPT_URL' | REPO_ARCHIVE_BASE='$REPO_ARCHIVE_BASE' /bin/bash -s -- --ref '$REF' --modules '$MODULES'"
if [[ -n "$TEST_TAGS" ]]; then
  cmd="$cmd --test-tags '$TEST_TAGS'"
  log "test-tags: $TEST_TAGS"
fi

/bin/bash -lc "$cmd"
printf "%s\n" "$REQUEST_ID" > "$state_file"
log "request $REQUEST_ID applied"
