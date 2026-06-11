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

# ---- run the upgrade (a COLD registry load — validate it!) ------------
# `-u --stop-after-init` loads the FULL registry in a fresh process. If it
# fails, a later live restart will ALSO crash-loop. This failure was once
# masked here (`| grep ... || true`) and a restart took the site down, so we
# now FAIL LOUDLY unless we see a clean 'Modules loaded' with no load errors.
log "upgrading $MODULES_ARG on $CONTAINER (db=$DB)"
upgrade_cmd="$QNAP_DOCKER exec $CONTAINER odoo -u $MODULES_ARG -d $DB --stop-after-init --no-http --logfile=/dev/stderr"
if [[ "$DRY_RUN" == "1" ]]; then
  log "DRY: ssh $QNAP_HOST '$upgrade_cmd'"
  log "DRY: (would then assert cold-load success + live /web/login 200)"
else
  log "running cold upgrade (this validates a future restart will boot)…"
  ssh "$QNAP_HOST" "$upgrade_cmd > /tmp/deploy_upgrade.log 2>&1 || true"
  upgrade_log="$(ssh "$QNAP_HOST" 'cat /tmp/deploy_upgrade.log' 2>/dev/null || true)"
  printf '%s\n' "$upgrade_log" \
    | grep -E 'Modules loaded|Registry loaded|ParseError|CRITICAL|ValidationError|AssertionError|Failed to load registry|Traceback' \
    | sed 's/^/[odoo] /' >&2 || true
  if printf '%s\n' "$upgrade_log" | grep -qE 'Failed to load registry|CRITICAL|AssertionError|Traceback \(most recent'; then
    fail "cold upgrade hit a registry/load error (see [odoo] lines above). NOT trusting this deploy — a live restart would crash. Investigate before restarting $CONTAINER."
  fi
  if ! printf '%s\n' "$upgrade_log" | grep -q 'Modules loaded'; then
    log "tail of upgrade log:"; printf '%s\n' "$upgrade_log" | tail -20 >&2
    fail "cold upgrade did not reach 'Modules loaded' — treat as FAILED."
  fi
  log "cold upgrade OK — registry loads cleanly."
fi

# ---- health gate: the LIVE server must actually serve -----------------
health_check() {
  ssh "$QNAP_HOST" "$QNAP_DOCKER exec $CONTAINER python3 -c \"import urllib.request as u
try: u.urlopen('http://localhost:8069/web/login', timeout=10); print(200)
except u.HTTPError as e: print(e.code)
except Exception: print('boot')\"" 2>/dev/null || true
}
if [[ "$DRY_RUN" != "1" ]]; then
  log "verifying live server health (/web/login)…"
  h="$(health_check)"
  [[ "$h" == "200" ]] || fail "live /web/login returned '$h' (expected 200) — deploy may have left the site unhealthy; investigate $CONTAINER."
  log "live /web/login → 200 ✓"
fi

# ---- optional hard restart (controller/Python changes need it) --------
# Python controller code is loaded at server start; a `-u` alone won't swap
# it. Set RESTART=1 to hard stop+start (cold-load already validated above),
# then re-gate on health. A soft `restart` can leave stale workers — use
# stop+start. See memory: qnap-odoo-upgrade-cache-reset (warm-vs-cold trap).
if [[ "${RESTART:-0}" == "1" && "$DRY_RUN" != "1" ]]; then
  log "RESTART=1 → hard stop+start $CONTAINER (loads new Python code)…"
  ssh "$QNAP_HOST" "$QNAP_DOCKER stop $CONTAINER && $QNAP_DOCKER start $CONTAINER"
  log "waiting for /web/login 200…"
  ok=0
  for i in $(seq 1 30); do
    [[ "$(health_check)" == "200" ]] && { ok=1; log "live /web/login → 200 after $i checks ✓"; break; }
    sleep 6
  done
  [[ "$ok" == "1" ]] || fail "after restart, $CONTAINER never returned 200 on /web/login — site may be DOWN. Roll back / investigate now."
fi

# ---- post-flight inventory (informational ONLY — not a success signal) -
if [[ "$DRY_RUN" != "1" ]]; then
  log "post-deploy module versions (informational; success was gated above):"
  ssh "$QNAP_HOST" "$QNAP_DOCKER exec southbrook-postgres psql -U odoo -d $DB -t -c \"
    SELECT name, latest_version
    FROM ir_module_module
    WHERE name = ANY (string_to_array('$MODULES_ARG', ','))
    ORDER BY name;
  \"" || log "(postgres status query failed — non-fatal)"
fi

log "done."
