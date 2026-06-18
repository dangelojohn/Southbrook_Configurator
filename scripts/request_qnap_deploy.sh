#!/usr/bin/env bash
# Create and push a GitHub-backed QNAP deploy request.
#
# The QNAP poller reads deploy/qnap/request.env from GitHub and performs the
# deploy locally. This script is intentionally Git-only: no SSH, rsync, scp, or
# local Docker.

set -euo pipefail

MODULES_ARG="${1:-}"
[[ -n "$MODULES_ARG" ]] || {
  echo "Usage: $0 module[,module...]"
  echo "Example: $0 southbrook_floor_traveler,southbrook_premium_orchestration"
  exit 2
}
[[ "$MODULES_ARG" =~ ^[A-Za-z0-9_,]+$ ]] || {
  echo "[qnap-deploy-request] ERROR: invalid module list: $MODULES_ARG" >&2
  exit 2
}

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "[qnap-deploy-request] ERROR: worktree has uncommitted changes; commit first." >&2
  exit 2
fi

REMOTE="${REMOTE:-github-southbrook}"
BRANCH="${BRANCH:-$(git branch --show-current)}"
REF="${REF:-$(git rev-parse HEAD)}"
SHORT_REF="$(git rev-parse --short=12 "$REF")"
REQUEST_PATH="${REQUEST_PATH:-deploy/qnap/request.env}"
REPO_ARCHIVE_BASE="${REPO_ARCHIVE_BASE:-https://github.com/dangelojohn/Southbrook_Configurator/archive}"
PULL_SCRIPT_URL="${PULL_SCRIPT_URL:-https://raw.githubusercontent.com/dangelojohn/Southbrook_Configurator/$BRANCH/scripts/qnap_pull_deploy.sh}"
TEST_TAGS="${TEST_TAGS:-}"
REQUESTED_AT="$(date -u +%Y%m%dT%H%M%SZ)"
REQUEST_ID="${REQUEST_ID:-$REQUESTED_AT-$SHORT_REF}"

mkdir -p "$(dirname "$REQUEST_PATH")"
{
  printf "REQUEST_ID=%s\n" "$REQUEST_ID"
  printf "REQUESTED_AT=%s\n" "$REQUESTED_AT"
  printf "REF=%s\n" "$REF"
  printf "MODULES=%s\n" "$MODULES_ARG"
  printf "TEST_TAGS=%s\n" "$TEST_TAGS"
  printf "REPO_ARCHIVE_BASE=%s\n" "$REPO_ARCHIVE_BASE"
  printf "PULL_SCRIPT_URL=%s\n" "$PULL_SCRIPT_URL"
} > "$REQUEST_PATH"

git add "$REQUEST_PATH"
git commit -m "chore(deploy): request qnap deploy $SHORT_REF"
git push "$REMOTE" "$BRANCH"

echo "[qnap-deploy-request] pushed request $REQUEST_ID" >&2
echo "[qnap-deploy-request] deploy ref: $REF" >&2
echo "[qnap-deploy-request] modules: $MODULES_ARG" >&2
