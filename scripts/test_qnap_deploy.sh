#!/usr/bin/env bash
# End-to-end smoke test for the QNAP no-SSH deploy pipeline.
#
# What it does:
#   1. Computes a unique REQUEST_ID for THIS test run.
#   2. Pushes deploy/qnap/request.env to the release branch
#      (default: deploy/release) pointing at the current HEAD.
#   3. Polls GitHub raw for the request.env contents until it
#      sees our REQUEST_ID land (proves push reached the branch
#      the QNAP is watching).
#   4. Polls the QNAP via SSH (if reachable) for the poller's
#      `last_request_id` state file until it matches our
#      REQUEST_ID, OR until --no-ssh / sandboxed mode is set.
#   5. Reports pass / fail with timing.
#
# Usage:
#   ./scripts/test_qnap_deploy.sh \
#     [--modules module1,module2] \
#     [--test-tags TAGS] \
#     [--branch deploy/release] \
#     [--timeout-s 480] \
#     [--no-ssh]      # skip the QNAP-side verification step
#                     # (e.g. when running from a sandboxed agent)
#
# Defaults are tuned for the canonical safe test request:
#   modules:   southbrook_floor_traveler,southbrook_premium_orchestration
#   test-tags: TestP8FloorTraveler.test_record_scan_creates_one_consumption_and_logs_workcenter

set -euo pipefail

MODULES="${MODULES:-southbrook_floor_traveler,southbrook_premium_orchestration}"
TEST_TAGS="${TEST_TAGS:-/southbrook_floor_traveler:TestP8FloorTraveler.test_record_scan_creates_one_consumption_and_logs_workcenter}"
BRANCH="${BRANCH:-deploy/release}"
TIMEOUT_S="${TIMEOUT_S:-480}"
QNAP_HOST="${QNAP_HOST:-admin@192.168.68.108}"
SKIP_SSH=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --modules) MODULES="$2"; shift 2 ;;
    --test-tags) TEST_TAGS="$2"; shift 2 ;;
    --branch) BRANCH="$2"; shift 2 ;;
    --timeout-s) TIMEOUT_S="$2"; shift 2 ;;
    --no-ssh) SKIP_SSH=1; shift ;;
    -h|--help)
      sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "[test-deploy] unknown arg: $1" >&2; exit 2 ;;
  esac
done

REMOTE="${REMOTE:-github-southbrook}"
REF="$(git rev-parse HEAD)"
SHORT_REF="$(git rev-parse --short=12 "$REF")"
REQUESTED_AT="$(date -u +%Y%m%dT%H%M%SZ)"
REQUEST_ID="${REQUEST_ID:-${REQUESTED_AT}-${SHORT_REF}-TEST}"
REQUEST_PATH="${REQUEST_PATH:-deploy/qnap/request.env}"
REPO_ARCHIVE_BASE="${REPO_ARCHIVE_BASE:-https://github.com/dangelojohn/Southbrook_Configurator/archive}"

log() { printf "[test-deploy] %s\n" "$*"; }
fail() { printf "[test-deploy] ❌ FAIL: %s\n" "$*" >&2; exit 1; }
pass() { printf "[test-deploy] ✅ PASS: %s\n" "$*"; }

if ! git diff --quiet || ! git diff --cached --quiet; then
  fail "worktree has uncommitted changes; commit first"
fi

log "test request: $REQUEST_ID"
log "deploying ref: $REF"
log "modules: $MODULES"
log "release branch: $BRANCH"

# ── 1. Switch to release branch, write request, push, switch back.
CURRENT_BRANCH="$(git branch --show-current)"
log "preparing release branch '$BRANCH'"
if ! git rev-parse --verify "refs/remotes/$REMOTE/$BRANCH" >/dev/null 2>&1; then
  fail "remote branch $REMOTE/$BRANCH does not exist — create it first"
fi
git fetch "$REMOTE" "$BRANCH" --quiet
git checkout -B "_test-deploy-tmp" "$REMOTE/$BRANCH" --quiet

mkdir -p "$(dirname "$REQUEST_PATH")"
cat > "$REQUEST_PATH" <<REQ
REQUEST_ID=$REQUEST_ID
REQUESTED_AT=$REQUESTED_AT
REF=$REF
MODULES=$MODULES
TEST_TAGS=$TEST_TAGS
REPO_ARCHIVE_BASE=$REPO_ARCHIVE_BASE
REQ

git add "$REQUEST_PATH"
git commit -m "test(deploy): smoke test request $REQUEST_ID" --quiet
TEST_PUSH_COMMIT="$(git rev-parse HEAD)"

log "pushing test commit $TEST_PUSH_COMMIT to $REMOTE/$BRANCH"
git push "$REMOTE" "_test-deploy-tmp:$BRANCH" --quiet
git checkout "$CURRENT_BRANCH" --quiet
git branch -D "_test-deploy-tmp" --quiet

# ── 2. Confirm GitHub raw sees the new REQUEST_ID.
RAW_URL="https://raw.githubusercontent.com/dangelojohn/Southbrook_Configurator/$BRANCH/deploy/qnap/request.env"
log "waiting for GitHub raw to surface our REQUEST_ID …"
START_T=$(date +%s)
SAW_GITHUB=0
while true; do
  if curl -fsSL --max-time 10 "$RAW_URL" 2>/dev/null \
       | grep -q "^REQUEST_ID=$REQUEST_ID$"; then
    SAW_GITHUB=1
    break
  fi
  ELAPSED=$(( $(date +%s) - START_T ))
  if [[ "$ELAPSED" -gt 120 ]]; then
    fail "GitHub raw never surfaced REQUEST_ID after 120s"
  fi
  sleep 5
done
pass "GitHub raw shows REQUEST_ID after $(( $(date +%s) - START_T ))s"

# ── 3. If SSH is allowed, watch the QNAP-side state file.
if [[ "$SKIP_SSH" -eq 1 ]]; then
  log "skip-ssh: not polling QNAP. Manual verification:"
  log "  ssh $QNAP_HOST cat /share/CACHEDEV3_DATA/Container/southbrook/deploy-state/last_request_id"
  log "  → expected: $REQUEST_ID"
  pass "test request pushed; QNAP verification skipped"
  exit 0
fi

log "polling QNAP state file via SSH …"
START_T=$(date +%s)
while true; do
  STATE="$(ssh -o ConnectTimeout=5 -o BatchMode=yes "$QNAP_HOST" \
            'cat /share/CACHEDEV3_DATA/Container/southbrook/deploy-state/last_request_id 2>/dev/null' \
            2>/dev/null || true)"
  if [[ "$STATE" == "$REQUEST_ID" ]]; then
    break
  fi
  ELAPSED=$(( $(date +%s) - START_T ))
  if [[ "$ELAPSED" -gt "$TIMEOUT_S" ]]; then
    log "current state file content: '$STATE'"
    log "tail of poller log:"
    ssh -o ConnectTimeout=5 -o BatchMode=yes "$QNAP_HOST" \
      'tail -20 /share/CACHEDEV3_DATA/Container/southbrook/deploy-state/poller.log 2>/dev/null' \
      2>/dev/null || true
    fail "QNAP did not mark REQUEST_ID applied after ${TIMEOUT_S}s"
  fi
  printf "."
  sleep 10
done
echo
pass "QNAP applied REQUEST_ID after $(( $(date +%s) - START_T ))s"

# ── 4. Print the relevant poller log so the user can read context.
log "poller log tail:"
ssh -o ConnectTimeout=5 -o BatchMode=yes "$QNAP_HOST" \
  'tail -10 /share/CACHEDEV3_DATA/Container/southbrook/deploy-state/poller.log 2>/dev/null' \
  2>/dev/null || true

log "🎉 end-to-end test passed"
