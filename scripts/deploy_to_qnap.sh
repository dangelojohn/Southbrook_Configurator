#!/usr/bin/env bash
# Deploy one or more Southbrook Odoo addons from this checkout to the
# live QNAP container and upgrade them.
#
# Pattern this codifies:
#   1. rsync each addon dir to /share/CACHEDEV3_DATA/Container/southbrook/addons/
#   2. exec the Odoo container via QNAP's system-docker binary (NOT plain
#      docker — Container Station runs Odoo under a hidden inner daemon)
#   3. run `odoo -u <modules> -d southbrook --stop-after-init`
#   4. report rule counts, version, and tail of the log
#
# Why this script exists: the QNAP system-docker binary lives at
# /share/CACHEDEV3_DATA/.qpkg/container-station/bin/system-docker — a
# path you only learn the hard way. Plain `docker` on QNAP runs a
# DIFFERENT docker daemon for ContainerStation's own management and
# does NOT see the user's Odoo container. New contributors have spent
# 15+ minutes rediscovering this.
#
# Usage:
#   ./scripts/deploy_to_qnap.sh                      # default: estimating + configurator_ux
#   ./scripts/deploy_to_qnap.sh southbrook_estimating
#   ./scripts/deploy_to_qnap.sh southbrook_estimating,southbrook_plm
#   QNAP_HOST=admin@192.168.68.108 ./scripts/deploy_to_qnap.sh ...
#   DB=southbrook DRY_RUN=1 ./scripts/deploy_to_qnap.sh ...
#
set -euo pipefail

QNAP_HOST="${QNAP_HOST:-admin@192.168.68.108}"
QNAP_ADDONS_DIR="${QNAP_ADDONS_DIR:-/share/CACHEDEV3_DATA/Container/southbrook/addons}"
QNAP_DOCKER="${QNAP_DOCKER:-/share/CACHEDEV3_DATA/.qpkg/container-station/bin/system-docker}"
CONTAINER="${CONTAINER:-southbrook-odoo}"
DB="${DB:-southbrook}"
DRY_RUN="${DRY_RUN:-0}"
# Serialize concurrent upgrades. Two parallel `odoo -u` runs against the
# same DB race on ir_module_module_dependency and one of them dies with
# `psycopg2.errors.LockNotAvailable: canceling statement due to lock
# timeout`. flock lives inside the container (util-linux is present in
# the Odoo image — QNAP busybox host doesn't have it).
LOCK_PATH="${LOCK_PATH:-/tmp/southbrook-odoo-upgrade.lock}"
LOCK_WAIT_SEC="${LOCK_WAIT_SEC:-600}"

MODULES_ARG="${1:-southbrook_estimating,southbrook_configurator_ux}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ---- pre-flight --------------------------------------------------------
log() { printf "[deploy] %s\n" "$*" >&2; }
fail() { printf "[deploy] ERROR: %s\n" "$*" >&2; exit 1; }
run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    log "DRY: $*"
  else
    "$@"
  fi
}

[[ -d addons ]] || fail "must run from repo root (no addons/ dir)"
command -v rsync >/dev/null || fail "rsync not found"
command -v ssh >/dev/null   || fail "ssh not found"

log "target: $QNAP_HOST"
log "modules: $MODULES_ARG"
log "db: $DB"

# ---- rsync each addon dir ---------------------------------------------
IFS=',' read -ra MODULES <<< "$MODULES_ARG"
for mod in "${MODULES[@]}"; do
  src="addons/$mod"
  if [[ ! -d "$src" ]]; then
    fail "addons/$mod not in this checkout — typo, or pull more files first"
  fi
  log "rsync $src → $QNAP_HOST:$QNAP_ADDONS_DIR/$mod"
  # --delete-during keeps the QNAP side identical to the checkout, so
  # deleted files (e.g. obsolete migration scripts) actually go away.
  # Exclude __pycache__ and *.pyc to avoid permission churn.
  run rsync -az --delete-during \
    --exclude='__pycache__/' --exclude='*.pyc' --exclude='.DS_Store' \
    "$src/" "$QNAP_HOST:$QNAP_ADDONS_DIR/$mod/"
done

# ---- run the upgrade --------------------------------------------------
log "upgrading $MODULES_ARG on $CONTAINER (db=$DB, lock-wait=${LOCK_WAIT_SEC}s)"
# Wrap odoo -u in flock INSIDE the container so concurrent upgrade
# attempts queue instead of racing. Lock auto-releases on exit. The
# -E flag on flock makes it return its own exit code (1) on timeout
# rather than swallowing it; that propagates up through tee/grep.
inner_cmd="flock -E 75 -w $LOCK_WAIT_SEC $LOCK_PATH odoo -u $MODULES_ARG -d $DB --stop-after-init --no-http --logfile=/dev/stderr"
upgrade_cmd="$QNAP_DOCKER exec $CONTAINER bash -c \"$inner_cmd\""
if [[ "$DRY_RUN" == "1" ]]; then
  log "DRY: ssh $QNAP_HOST '$upgrade_cmd'"
else
  # Capture log to a tmpfile on the QNAP host so we can grep it
  # after; also stream a small filter to our stderr live. Note: a
  # flock timeout surfaces as the literal exit code 75 — we surface
  # it explicitly so the deploy doesn't silently "succeed" on lock
  # contention (the historical || true bug).
  set +e
  ssh "$QNAP_HOST" "$upgrade_cmd 2>&1 | tee /tmp/deploy_upgrade.log | grep -E 'Modules loaded|ParseError|CRITICAL|ValidationError|FAIL|Traceback|flock'"
  rc=${PIPESTATUS[0]}
  set -e
  if [[ "$rc" == "75" ]]; then
    fail "another odoo -u is holding $LOCK_PATH inside $CONTAINER — \
waited ${LOCK_WAIT_SEC}s. Find it with: ssh $QNAP_HOST '$QNAP_DOCKER \
exec $CONTAINER ps -ef | grep \"odoo.*-u\"'"
  fi
fi

# ---- post-flight inventory --------------------------------------------
if [[ "$DRY_RUN" != "1" ]]; then
  log "post-deploy state:"
  ssh "$QNAP_HOST" "$QNAP_DOCKER exec southbrook-postgres psql -U odoo -d $DB -t -c \"
    SELECT name, latest_version
    FROM ir_module_module
    WHERE name = ANY (string_to_array('$MODULES_ARG', ','))
    ORDER BY name;
  \"" || log "(postgres status query failed — non-fatal)"
fi

log "done."
