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

# ---- deploy-from-main gate --------------------------------------------
# Prevents the cold-install gap from regrowing by refusing to deploy
# from a non-main checkout unless explicitly overridden. See close-out
# doc ~/Downloads/Phase1_P0_CLOSE_OUT_2026-06-29.md for rationale.
# Gap-regrowth pattern: feature-branch deploys land code in prod that
# never reaches main, so CI cold-install on main is impossible and
# DR is broken. The whole point of the cold-install gap closure work.
if git rev-parse --git-dir >/dev/null 2>&1; then
  CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
  CURRENT_SHA=$(git rev-parse --short HEAD)
  if [[ "$CURRENT_BRANCH" != "main" ]]; then
    if ! git merge-base --is-ancestor HEAD main 2>/dev/null; then
      # HEAD is on a branch that has commits not in main = feature-branch deploy
      if [[ "${SOUTHBROOK_DEPLOY_OFF_MAIN:-0}" != "1" ]]; then
        cat >&2 <<GATE
[deploy] REFUSING TO DEPLOY: current HEAD ($CURRENT_BRANCH @ $CURRENT_SHA) is not in main.

Why this exists:
  Feature-branch deploys grow the cold-install gap. Deploys must
  ship from main once the work is reviewed + merged.
  See ~/Downloads/Phase1_P0_CLOSE_OUT_2026-06-29.md.

Options:
  - Open a PR + merge to main first (preferred).
  - Override for an emergency:
      SOUTHBROOK_DEPLOY_OFF_MAIN=1 $0 $*
    (override is logged to /tmp/southbrook-offmain-deploys.jsonl
    so it can be reconciled later.)

GATE
        exit 64
      fi
      # Override taken — log it for later reconciliation
      OVERRIDE_LOG="/tmp/southbrook-offmain-deploys.jsonl"
      printf '{"ts":"%s","branch":"%s","sha":"%s","user":"%s","modules":"%s"}\n' \
        "$(date -u +%FT%TZ)" "$CURRENT_BRANCH" "$CURRENT_SHA" "$USER" "$MODULES_ARG" \
        >> "$OVERRIDE_LOG"
      log "OFF-MAIN OVERRIDE: deploying from $CURRENT_BRANCH @ $CURRENT_SHA (logged to $OVERRIDE_LOG)"
    fi
  fi
fi

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

# ---- run the upgrade (COLD registry load, serialized by flock) --------
# `-u --stop-after-init` loads the FULL registry in a fresh process. If it
# fails, a later live restart will ALSO crash-loop — so we FAIL LOUDLY below
# unless we see a clean 'Modules loaded' with no load errors (this failure was
# once masked by `| grep ... || true` and a restart took the site down).
# We also wrap odoo -u in flock INSIDE the container so concurrent upgrade
# attempts queue instead of racing; `-E 75` makes a lock timeout return exit
# 75 (surfaced explicitly below) rather than silently "succeeding".
log "upgrading $MODULES_ARG on $CONTAINER (db=$DB, lock-wait=${LOCK_WAIT_SEC}s)"
inner_cmd="flock -E 75 -w $LOCK_WAIT_SEC $LOCK_PATH odoo -u $MODULES_ARG -d $DB --stop-after-init --no-http --logfile=/dev/stderr"
upgrade_cmd="$QNAP_DOCKER exec $CONTAINER bash -c \"$inner_cmd\""
if [[ "$DRY_RUN" == "1" ]]; then
  log "DRY: ssh $QNAP_HOST '$upgrade_cmd'"
  log "DRY: (would then assert cold-load success + live /web/login 200)"
else
  log "running cold upgrade under flock (validates a future restart will boot)…"
  set +e
  ssh "$QNAP_HOST" "$upgrade_cmd > /tmp/deploy_upgrade.log 2>&1"
  rc=$?
  set -e
  upgrade_log="$(ssh "$QNAP_HOST" 'cat /tmp/deploy_upgrade.log' 2>/dev/null || true)"
  # A flock timeout surfaces as exit 75 — surface it so the deploy doesn't
  # silently "succeed" on lock contention (the historical || true bug).
  if [[ "$rc" == "75" ]]; then
    fail "another odoo -u is holding $LOCK_PATH inside $CONTAINER — \
waited ${LOCK_WAIT_SEC}s. Find it with: ssh $QNAP_HOST '$QNAP_DOCKER \
exec $CONTAINER ps -ef | grep \"odoo.*-u\"'"
  fi
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
  log "cold upgrade OK — registry loads cleanly (no lock contention)."
fi

# ---- health gate: the LIVE server must actually serve -----------------
health_check() {
  ssh "$QNAP_HOST" "$QNAP_DOCKER exec $CONTAINER python3 -c \"import urllib.request as u
try: u.urlopen('http://localhost:8069/web/login', timeout=10); print(200)
except u.HTTPError as e: print(e.code)
except Exception: print('boot')\"" 2>/dev/null || true
}
# Poll for a 200 rather than a single shot: a `-u` signals the live workers to
# reload their registry, so the server is briefly unavailable mid-deploy and a
# one-shot check false-fails (it returned 'boot' and aborted a healthy deploy).
wait_healthy() {
  local tries="${1:-20}" i
  for ((i = 1; i <= tries; i++)); do
    [[ "$(health_check)" == "200" ]] && { log "live /web/login → 200 (after $i check(s))"; return 0; }
    sleep 6
  done
  return 1
}

if [[ "$DRY_RUN" != "1" ]]; then
  if [[ "${RESTART:-0}" == "1" ]]; then
    # We're about to hard-restart, which re-gates health definitively below.
    # Running this gate now only catches the transient `-u` reload — skip it.
    log "health gate deferred to the post-restart check (RESTART=1)."
  else
    log "verifying live server health (/web/login)…"
    wait_healthy || fail "live /web/login never returned 200 — deploy may have left the site unhealthy; investigate $CONTAINER."
  fi
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
  wait_healthy 30 || fail "after restart, $CONTAINER never returned 200 on /web/login — site may be DOWN. Roll back / investigate now."
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
