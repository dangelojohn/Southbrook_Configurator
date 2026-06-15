#!/usr/bin/env bash
# deploy_kitchenforge.sh
#
# Wraps scripts/deploy_to_qnap.sh to deploy the three KitchenForge addons in
# dependency order, against any tenant on the QNAP (default: southbrook).
#
# Dependency order (matters — manifests would catch it but we'd waste an
# upgrade cycle):
#   kitchenforge_core
#     └─ kitchenforge_marathon  (depends on core)
#     └─ kitchenforge_saas      (depends on core)
#
# Per-deploy steps:
#   1. dry-run validation: parse each __manifest__.py, count files
#   2. rsync each addon dir to /share/CACHEDEV3_DATA/Container/<tenant>/addons/
#   3. flock -E 75 -w 600 <lock> odoo -u <addon> inside the container
#   4. docker restart <tenant>-odoo (cache-reset recipe per memory:
#      qnap_odoo_upgrade_cache_reset — ormcache poisoning otherwise causes
#      "Circular assets bundle" 500s on /web/login)
#   5. health probe https://<tenant>.local:9444/web/login
#
# Usage:
#   ./deploy/deploy_kitchenforge.sh                                 # southbrook upgrade
#   ./deploy/deploy_kitchenforge.sh --tenant sapienzium              # other tenant upgrade
#   ./deploy/deploy_kitchenforge.sh --tenant southbrook --init       # fresh install (-i)
#   QNAP_HOST=admin@192.168.68.108 ./deploy/deploy_kitchenforge.sh ...

set -euo pipefail

# ---- defaults ----------------------------------------------------------
TENANT="southbrook"
MODE="upgrade"                                       # upgrade | init
QNAP_HOST="${QNAP_HOST:-admin@192.168.68.108}"
QNAP_DOCKER="${QNAP_DOCKER:-/share/CACHEDEV3_DATA/.qpkg/container-station/bin/system-docker}"
LOCK_WAIT_SEC="${LOCK_WAIT_SEC:-600}"
DRY_RUN="${DRY_RUN:-0}"

# Dependency-ordered. core MUST land before marathon/saas — otherwise the
# upgrade inside the container will fail registry validation and the deploy
# script will refuse to restart.
ADDONS=(kitchenforge_core kitchenforge_marathon kitchenforge_saas)

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ---- arg parse ---------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tenant)  TENANT="$2"; shift 2 ;;
    --init)    MODE="init"; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help)
      sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

CONTAINER="${TENANT}-odoo"
DB="${DB:-$TENANT}"
QNAP_ADDONS_DIR="/share/CACHEDEV3_DATA/Container/${TENANT}/addons"
LOCK_PATH="/tmp/${TENANT}-odoo-upgrade.lock"

log()  { printf "[kf-deploy] %s\n" "$*" >&2; }
fail() { printf "[kf-deploy] ERROR: %s\n" "$*" >&2; exit 1; }

log "tenant=$TENANT  mode=$MODE  db=$DB  container=$CONTAINER"
log "addons=${ADDONS[*]}"

# ---- pre-flight: dry-run validation ------------------------------------
log "pre-flight validation…"
for mod in "${ADDONS[@]}"; do
  src="addons/$mod"
  [[ -d "$src" ]] || fail "missing source dir: $src"
  manifest="$src/__manifest__.py"
  [[ -f "$manifest" ]] || fail "missing manifest: $manifest"
  python3 -c "import ast; d=ast.literal_eval(open('$manifest').read()); \
    assert 'depends' in d, 'manifest $manifest missing depends'" \
    || fail "manifest parse failed: $manifest"
  fcount=$(find "$src" -type f \( -name '*.py' -o -name '*.xml' -o -name '*.csv' \) | wc -l | tr -d ' ')
  log "  $mod  files=$fcount  manifest=OK"
done

# ---- deploy each addon in order ----------------------------------------
for mod in "${ADDONS[@]}"; do
  src="addons/$mod"
  log "=== $mod ==="

  # 1. rsync
  rsync_target="$QNAP_HOST:$QNAP_ADDONS_DIR/$mod/"
  log "rsync $src → $rsync_target"
  if [[ "$DRY_RUN" == "1" ]]; then
    log "DRY: rsync skipped"
  else
    rsync -az --delete-during \
      --exclude='__pycache__/' --exclude='*.pyc' --exclude='.DS_Store' \
      "$src/" "$rsync_target"
  fi

  # 2. install or upgrade
  flag=$([[ "$MODE" == "init" ]] && echo "-i" || echo "-u")
  inner_cmd="flock -E 75 -w $LOCK_WAIT_SEC $LOCK_PATH \
    odoo $flag $mod -d $DB --stop-after-init --no-http --logfile=/dev/stderr"
  log "running: $flag $mod inside $CONTAINER (flock-wrapped, wait=${LOCK_WAIT_SEC}s)"
  if [[ "$DRY_RUN" == "1" ]]; then
    log "DRY: ssh $QNAP_HOST '$QNAP_DOCKER exec $CONTAINER bash -c \"$inner_cmd\"'"
  else
    set +e
    ssh "$QNAP_HOST" "$QNAP_DOCKER exec $CONTAINER bash -c \"$inner_cmd\" \
      > /tmp/kf_${mod}.log 2>&1"
    rc=$?
    set -e
    upgrade_log="$(ssh "$QNAP_HOST" "cat /tmp/kf_${mod}.log" 2>/dev/null || true)"
    if [[ "$rc" == "75" ]]; then
      fail "$mod: flock timeout ($LOCK_WAIT_SEC s) — another odoo -u is holding $LOCK_PATH"
    fi
    printf '%s\n' "$upgrade_log" \
      | grep -E 'Modules loaded|ParseError|CRITICAL|ValidationError|Traceback' \
      | sed "s/^/[odoo:$mod] /" >&2 || true
    if printf '%s\n' "$upgrade_log" \
        | grep -qE 'Failed to load registry|CRITICAL|AssertionError|Traceback \(most recent'; then
      fail "$mod: cold $flag hit a registry/load error — NOT restarting; fix before retrying"
    fi
    if ! printf '%s\n' "$upgrade_log" | grep -q 'Modules loaded'; then
      printf '%s\n' "$upgrade_log" | tail -20 >&2
      fail "$mod: cold $flag did not reach 'Modules loaded' — treat as FAILED"
    fi
    log "$mod: cold $flag OK"
  fi
done

# ---- post-deploy: restart container (cache reset) ----------------------
# Per qnap_odoo_upgrade_cache_reset.md, a `-u` against a multi-addon batch can
# leave the live workers' ormcache poisoned (we just saw this on southbrook).
# A hard stop+start re-loads Python code AND re-builds the cache from disk.
log "restarting $CONTAINER (cache reset)…"
if [[ "$DRY_RUN" == "1" ]]; then
  log "DRY: ssh $QNAP_HOST '$QNAP_DOCKER stop $CONTAINER && $QNAP_DOCKER start $CONTAINER'"
else
  ssh "$QNAP_HOST" "$QNAP_DOCKER stop $CONTAINER && $QNAP_DOCKER start $CONTAINER"
fi

# ---- health probe ------------------------------------------------------
# Try the LAN address first (TLS via Caddy on :9444 per qnap_demo_stacks). If
# the caller exports KF_PUBLIC_URL we probe that too.
probe() {
  local url="$1"
  curl -sk -o /dev/null -w '%{http_code}' --max-time 10 "$url" 2>/dev/null || echo "000"
}

probe_url_lan="https://${TENANT}.local:9444/web/login"
log "probing $probe_url_lan …"
if [[ "$DRY_RUN" != "1" ]]; then
  ok=0
  for i in $(seq 1 30); do
    code=$(probe "$probe_url_lan")
    [[ "$code" == "200" ]] && { log "LAN probe → 200 after ${i} tries"; ok=1; break; }
    sleep 4
  done
  [[ "$ok" == "1" ]] || fail "$probe_url_lan never returned 200 — investigate $CONTAINER"

  if [[ -n "${KF_PUBLIC_URL:-}" ]]; then
    log "probing public $KF_PUBLIC_URL …"
    code=$(probe "$KF_PUBLIC_URL")
    [[ "$code" == "200" ]] || log "WARN: public probe returned $code (Cloudflare edge cache lag is normal up to 4h)"
  fi
fi

log "done. tenant=$TENANT addons=${ADDONS[*]} mode=$MODE"
