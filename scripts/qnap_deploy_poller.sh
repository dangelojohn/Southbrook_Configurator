#!/usr/bin/env bash
# Run this ON THE QNAP host, typically from cron.
#
# Poll a GitHub-hosted deploy request file and, when REQUEST_ID changes, run
# qnap_pull_deploy.sh locally on the QNAP. This is the no-SSH deploy path for
# restricted agent sandboxes: the agent only pushes to GitHub; the QNAP pulls.

set -euo pipefail

# Hardcoded against the `deploy/release` branch — separate from
# day-to-day developer branches. ONLY commits to `deploy/release`
# trigger a production deploy. Day-to-day work on feature branches
# does NOT, even if a developer pushes a malformed request.env
# elsewhere. The deploy-release branch is intended to be branch-
# protected (PR + review required); see deploy/qnap/README.md.
#
# An override from `request.env` is honored for REPO_ARCHIVE_BASE
# (which only chooses WHERE to pull addon code from), but NOT for
# PULL_SCRIPT_URL (which controls WHAT script the QNAP runs).
# Allowing the request to swap the script would defeat the
# branch-protection model.
RELEASE_BRANCH="${RELEASE_BRANCH:-deploy/release}"
REQUEST_URL="${REQUEST_URL:-https://raw.githubusercontent.com/dangelojohn/Southbrook_Configurator/$RELEASE_BRANCH/deploy/qnap/request.env}"
PULL_SCRIPT_URL="${PULL_SCRIPT_URL:-https://raw.githubusercontent.com/dangelojohn/Southbrook_Configurator/$RELEASE_BRANCH/scripts/qnap_pull_deploy.sh}"
REPO_ARCHIVE_BASE="${REPO_ARCHIVE_BASE:-https://github.com/dangelojohn/Southbrook_Configurator/archive}"
STATE_DIR="${STATE_DIR:-/share/CACHEDEV3_DATA/Container/southbrook/deploy-state}"
LOCK_PID_FILE="${LOCK_PID_FILE:-/tmp/sbk-qnap-deploy-poller.pid}"

log() { printf "[qnap-deploy-poller] %s\n" "$*" >&2; }
fail() { printf "[qnap-deploy-poller] ERROR: %s\n" "$*" >&2; exit 1; }

command -v curl >/dev/null || fail "curl not found on QNAP"
# Note: QTS busybox does NOT ship `flock` on the host (only inside
# containers at /usr/bin/flock). We use a PID-file based single-
# instance guard instead. Keeps the poller portable to any QTS
# build without forcing util-linux on the host.
mkdir -p "$STATE_DIR"

if [[ -f "$LOCK_PID_FILE" ]]; then
  prev_pid="$(cat "$LOCK_PID_FILE" 2>/dev/null || true)"
  if [[ -n "$prev_pid" ]] && kill -0 "$prev_pid" 2>/dev/null; then
    log "another poller (pid $prev_pid) is running; skip"
    exit 0
  fi
  # Stale PID file (prior poller died without clean exit). Drop it.
  rm -f "$LOCK_PID_FILE"
fi
echo "$$" > "$LOCK_PID_FILE"
trap 'rm -f "$LOCK_PID_FILE"' EXIT

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

while IFS='=' read -r key value; do
  case "$key" in
    REQUEST_ID) REQUEST_ID="$value" ;;
    REF) REF="$value" ;;
    MODULES) MODULES="$value" ;;
    TEST_TAGS) TEST_TAGS="$value" ;;
    REPO_ARCHIVE_BASE) REQUEST_REPO_ARCHIVE_BASE="$value" ;;
    PULL_SCRIPT_URL)
      # IGNORED. The script the QNAP runs is controlled by the
      # poller's hardcoded RELEASE_BRANCH only; honoring a request-
      # supplied override would defeat the branch-protection model.
      # Surface the attempted override so the operator notices.
      log "ignoring request-supplied PULL_SCRIPT_URL override"
      ;;
    REQUESTED_AT) ;;  # metadata only; not used by the poller
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
# PULL_SCRIPT_URL is deliberately NOT overridable from the request
# — see the case-statement comment above.

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
