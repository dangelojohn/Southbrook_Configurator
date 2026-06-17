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
#   DEPLOY_VIA=tunnel ./scripts/deploy_to_qnap.sh ...
#     Route SSH + rsync through `cloudflared access ssh --hostname %h`
#     instead of going direct to the QNAP's LAN IP. Use this when the
#     LAN-side route to the QNAP is unreachable but the cloudflared
#     tunnel is healthy. Requires:
#       - cloudflared CLI on this machine (`brew install cloudflared`)
#       - an SSH ingress in the Cloudflare tunnel config that maps
#         $QNAP_TUNNEL_HOST → ssh://localhost:22 on the QNAP host
#     Override the tunnel hostname with QNAP_TUNNEL_HOST=... (default
#     admin@ssh.southbrookcabinetry.space).
#
set -euo pipefail

DEPLOY_VIA="${DEPLOY_VIA:-lan}"
QNAP_HOST="${QNAP_HOST:-admin@192.168.68.108}"
QNAP_TUNNEL_HOST="${QNAP_TUNNEL_HOST:-admin@ssh.southbrookcabinetry.space}"
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
#
# Place the lock on a path under /var/lib/odoo (the bind-mounted Odoo
# data dir) rather than /tmp — container tmpfs is wiped by the RESTART
# block below, so a /tmp lock cannot serialize across the stop+start.
LOCK_PATH="${LOCK_PATH:-/var/lib/odoo/.southbrook-odoo-upgrade.lock}"
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

# When DEPLOY_VIA=tunnel, swap the LAN host for the tunnel hostname and
# require the cloudflared CLI (needed for the ProxyCommand path).
if [[ "$DEPLOY_VIA" == "tunnel" ]]; then
  command -v cloudflared >/dev/null \
    || fail "DEPLOY_VIA=tunnel needs cloudflared CLI (brew install cloudflared)"
  QNAP_HOST="$QNAP_TUNNEL_HOST"
  log "tunnel mode: SSH routed through 'cloudflared access ssh --hostname %h'"
elif [[ "$DEPLOY_VIA" != "lan" ]]; then
  fail "DEPLOY_VIA must be 'lan' or 'tunnel' (got: $DEPLOY_VIA)"
fi

# Wrappers so every ssh/rsync invocation downstream picks up the right
# transport for the selected mode without each callsite having to branch.
_ssh() {
  if [[ "$DEPLOY_VIA" == "tunnel" ]]; then
    ssh -o ProxyCommand="cloudflared access ssh --hostname %h" "$@"
  else
    ssh "$@"
  fi
}
_rsync() {
  if [[ "$DEPLOY_VIA" == "tunnel" ]]; then
    rsync -e 'ssh -o ProxyCommand="cloudflared access ssh --hostname %h"' "$@"
  else
    rsync "$@"
  fi
}

log "target: $QNAP_HOST (via $DEPLOY_VIA)"
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
  run _rsync -az --delete-during \
    --exclude='__pycache__/' --exclude='*.pyc' --exclude='.DS_Store' \
    "$src/" "$QNAP_HOST:$QNAP_ADDONS_DIR/$mod/"
done

# ---- decide install vs upgrade per module -----------------------------
# `odoo -u <mod>` is a no-op if the module has never been registered in
# the `ir_module_module` table — the deploy then succeeds while the
# module is still "uninstalled / not in registry" and nothing visible
# changes. For a fresh addon you need `odoo -i <mod>` (which also
# performs the equivalent of `--update-list` first to discover it).
#
# Classify each requested module by looking it up via psql:
#   * already in ir_module_module with state='installed' / 'to upgrade'
#     → keep using -u
#   * not in ir_module_module OR state='uninstalled'
#     → switch to -i
# Mixed batch is OK — we pass two flag groups to odoo on the same
# command line: `-i to_install -u to_upgrade`. Odoo honours both.
#
# Done over psql instead of `odoo shell` because shell takes 30-90s to
# bootstrap; the classification query takes <100ms.
log "classifying $MODULES_ARG (install vs upgrade)…"
PG_PW=$(_ssh "$QNAP_HOST" "$QNAP_DOCKER exec $CONTAINER bash -c 'grep -E \"^db_password\" /etc/odoo/odoo.conf 2>/dev/null | head -1 | cut -d= -f2 | tr -d \" \"'" 2>/dev/null || true)
# A clean (unquoted) IN-list for the psql query.
mod_in_list=$(printf "'%s'," "${MODULES[@]}" | sed 's/,$//')
classify_query="SELECT name || ':' || state FROM ir_module_module WHERE name IN ($mod_in_list);"
known_states=$(_ssh "$QNAP_HOST" "$QNAP_DOCKER exec -e PGPASSWORD='$PG_PW' $CONTAINER psql -h southbrook-postgres -U odoo -d $DB -At -c \"$classify_query\"" 2>/dev/null || true)
to_install=()
to_upgrade=()
for mod in "${MODULES[@]}"; do
  state=$(printf '%s\n' "$known_states" | awk -F: -v m="$mod" '$1==m {print $2}')
  if [[ -z "$state" || "$state" == "uninstalled" ]]; then
    to_install+=("$mod")
  else
    to_upgrade+=("$mod")
  fi
done
INSTALL_ARG=$(IFS=','; echo "${to_install[*]:-}")
UPGRADE_ARG=$(IFS=','; echo "${to_upgrade[*]:-}")
if [[ -n "$INSTALL_ARG" ]]; then
  log "  install: $INSTALL_ARG"
fi
if [[ -n "$UPGRADE_ARG" ]]; then
  log "  upgrade: $UPGRADE_ARG"
fi
# Build the odoo command — combine -i and -u when both apply. Two single
# modules ('foo' to install, 'bar' to upgrade) become:
#   odoo -i foo -u bar -d southbrook --stop-after-init ...
ODOO_FLAGS=""
if [[ -n "$INSTALL_ARG" ]]; then ODOO_FLAGS="-i $INSTALL_ARG"; fi
if [[ -n "$UPGRADE_ARG" ]]; then
  if [[ -n "$ODOO_FLAGS" ]]; then ODOO_FLAGS="$ODOO_FLAGS -u $UPGRADE_ARG"; else ODOO_FLAGS="-u $UPGRADE_ARG"; fi
fi
if [[ -z "$ODOO_FLAGS" ]]; then
  fail "no modules to install or upgrade — classification produced empty buckets (bug in this script or in psql probe)"
fi

# ---- run the install/upgrade (COLD registry load, serialized by flock) -
# `--stop-after-init` loads the FULL registry in a fresh process. If it
# fails, a later live restart will ALSO crash-loop — so we FAIL LOUDLY below
# unless we see a clean 'Modules loaded' with no load errors (this failure was
# once masked by `| grep ... || true` and a restart took the site down).
# We also wrap odoo in flock INSIDE the container so concurrent attempts
# queue instead of racing; `-E 75` makes a lock timeout return exit
# 75 (surfaced explicitly below) rather than silently "succeeding".
log "running $ODOO_FLAGS on $CONTAINER (db=$DB, lock-wait=${LOCK_WAIT_SEC}s)"
# `: > $LOCK_PATH || true` makes sure the lock file exists (flock can't
# create one against a missing parent dir on first run).
#
# The sentinel `__SBK_COLD_OK__` is echoed AFTER odoo exits 0. Earlier we
# grep'd for the literal "Modules loaded" Odoo log line, but on very long
# deploys (the multi-GB OCA registry load) the grep against the captured
# $upgrade_log occasionally returned false-negative even when the log
# unambiguously contained the string. A short, unambiguous sentinel
# written by THIS script makes the gate deterministic regardless of how
# Odoo's logger frames the success line.
SENTINEL="__SBK_COLD_OK__"
inner_cmd="(: > $LOCK_PATH 2>/dev/null || true) && flock -E 75 -w $LOCK_WAIT_SEC $LOCK_PATH odoo $ODOO_FLAGS -d $DB --stop-after-init --no-http --logfile=/dev/stderr && echo $SENTINEL"
upgrade_cmd="$QNAP_DOCKER exec $CONTAINER bash -c \"$inner_cmd\""
if [[ "$DRY_RUN" == "1" ]]; then
  log "DRY: ssh $QNAP_HOST '$upgrade_cmd'"
  log "DRY: (would then assert cold-load success + live /web/login 200)"
else
  log "running cold upgrade under flock (validates a future restart will boot)…"
  set +e
  _ssh "$QNAP_HOST" "$upgrade_cmd > /tmp/deploy_upgrade.log 2>&1"
  rc=$?
  # Capture the log AND distinguish "log fetched, empty" from "log fetch
  # failed". Earlier we did `cat ... || true` which collapsed both into
  # an empty buffer, and the grep below then misdiagnosed an ssh blip as
  # "did not reach Modules loaded" — taking the next deploy down a fail
  # path it shouldn't.
  upgrade_log="$(_ssh "$QNAP_HOST" 'cat /tmp/deploy_upgrade.log' 2>/dev/null)"
  log_fetch_rc=$?
  set -e
  if [[ "$log_fetch_rc" != "0" ]]; then
    fail "could not fetch /tmp/deploy_upgrade.log from $QNAP_HOST (ssh rc=$log_fetch_rc). Cold upgrade exit was $rc; can't tell if it loaded or crashed. Investigate before restarting $CONTAINER."
  fi
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
  # NOTE: don't fail on bare 'Traceback' — py.warnings prints a stack for
  # every UserWarning, and a single benign 'should be searchable' warning
  # in an unrelated module was killing every deploy verdict. The real
  # failure markers (CRITICAL / AssertionError / Failed to load registry)
  # plus the Modules loaded gate below catch genuine load errors.
  if printf '%s\n' "$upgrade_log" | grep -qE 'Failed to load registry|CRITICAL|AssertionError'; then
    fail "cold upgrade hit a registry/load error (see [odoo] lines above). NOT trusting this deploy — a live restart would crash. Investigate before restarting $CONTAINER."
  fi
  # Success gate: the sentinel is echoed by `inner_cmd` after odoo exits 0.
  # If we see it, the upgrade ran to completion. Fall back to the literal
  # 'Modules loaded' line if the sentinel is missing — that handles the
  # case where ssh dropped between odoo finishing and our echo running
  # (rare but possible over a high-latency tunnel).
  if printf '%s\n' "$upgrade_log" | grep -q "$SENTINEL"; then
    :  # sentinel present → unambiguous success
  elif printf '%s\n' "$upgrade_log" | grep -q 'Modules loaded'; then
    log "sentinel missing but 'Modules loaded' line present — trusting the log."
  else
    log "tail of upgrade log:"; printf '%s\n' "$upgrade_log" | tail -20 >&2
    fail "cold upgrade did not reach success (no sentinel, no 'Modules loaded' line) — treat as FAILED. ssh rc was $rc."
  fi
  log "cold upgrade OK — registry loads cleanly (no lock contention)."
fi

# ---- health gate: the LIVE server must actually serve -----------------
# Print one of: '200' (live), an HTTP error code (3xx/4xx/5xx),
# 'boot' (server not accepting yet — transient), or 'ssh_err' (couldn't
# reach the QNAP at all). Earlier we collapsed 'ssh_err' into '' via a
# silent `|| true`, and wait_healthy spent its budget polling against
# what was actually a network blip — masking infra problems as "site
# unhealthy". Distinguishing them lets the caller decide whether to
# retry, escalate, or abort.
health_check() {
  set +e
  local out rc
  out="$(_ssh "$QNAP_HOST" "$QNAP_DOCKER exec $CONTAINER python3 -c \"import urllib.request as u
try: u.urlopen('http://localhost:8069/web/login', timeout=10); print(200)
except u.HTTPError as e: print(e.code)
except Exception: print('boot')\"" 2>/dev/null)"
  rc=$?
  set -e
  if [[ "$rc" != "0" ]]; then
    printf 'ssh_err'
  else
    printf '%s' "$out"
  fi
}
# Poll for a 200 rather than a single shot: a `-u` signals the live workers to
# reload their registry, so the server is briefly unavailable mid-deploy and a
# one-shot check false-fails (it returned 'boot' and aborted a healthy deploy).
wait_healthy() {
  local tries="${1:-20}" i status
  for ((i = 1; i <= tries; i++)); do
    status="$(health_check)"
    if [[ "$status" == "200" ]]; then
      log "live /web/login → 200 (after $i check(s))"; return 0
    fi
    # Surface the LAST observed status on each tick so a log scrape can
    # tell at a glance whether we were stuck on 'boot' (server reloading,
    # benign) versus 'ssh_err' (LAN gone) versus a real HTTP error code.
    log "health: $status (attempt $i/$tries)"
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
  _ssh "$QNAP_HOST" "$QNAP_DOCKER stop $CONTAINER && $QNAP_DOCKER start $CONTAINER"
  log "waiting for /web/login 200…"
  wait_healthy 30 || fail "after restart, $CONTAINER never returned 200 on /web/login — site may be DOWN. Roll back / investigate now."
fi

# ---- post-flight inventory (informational ONLY — not a success signal) -
if [[ "$DRY_RUN" != "1" ]]; then
  log "post-deploy module versions (informational; success was gated above):"
  _ssh "$QNAP_HOST" "$QNAP_DOCKER exec southbrook-postgres psql -U odoo -d $DB -t -c \"
    SELECT name, latest_version
    FROM ir_module_module
    WHERE name = ANY (string_to_array('$MODULES_ARG', ','))
    ORDER BY name;
  \"" || log "(postgres status query failed — non-fatal)"
fi

log "done."
