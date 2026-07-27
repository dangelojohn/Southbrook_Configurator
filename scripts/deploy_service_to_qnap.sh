#!/usr/bin/env bash
# Deploy one Southbrook side-car SERVICE (docker container built from
# this checkout's services/ dir) from this repo to the live QNAP stack
# and rebuild + recreate its container.
#
# Companion to scripts/deploy_to_qnap.sh (which deploys ODOO ADDONS).
# That script rsyncs into the addons/ tree and runs `odoo -u` inside
# the running Odoo container. This script rsyncs into the SERVICE
# build-context dir, runs `docker compose build <svc>`, then
# `docker compose up -d --force-recreate <svc>`.
#
# Why this script exists (the gotchas you only learn the hard way):
#
#   1. The QNAP stack's services live under
#      /share/CACHEDEV3_DATA/Container/southbrook/<svc> — NOT under
#      a services/ subdir like the repo. The compose file's build
#      context is the flat path. This script handles that mapping
#      via SVC_REMOTE so the operator never has to remember it.
#
#   2. Service-side code (services/freecad_bridge/main.py and
#      friends) has NO equivalent of an Odoo addon `-u` upgrade. The
#      ONLY way to ship new code is rebuild the image + recreate the
#      container. Before this script, that was a manual SCP + ssh
#      sequence that was easy to bungle (wrong target path: the
#      services/ vs flat-dir mismatch nailed at least one session).
#
#   3. The QNAP host runs TWO docker daemons — system-docker (where
#      Odoo + bridge actually run) and Container-Station's outer
#      daemon. `docker compose` on the QNAP needs DOCKER_HOST pointed
#      at system-docker.sock AND PATH including container-station's
#      bin dir for the helper binaries (containerd-shim, runc). See
#      [[qnap_cron_docker_exec_path_trap]] for the cron-side variant.
#
# Usage:
#   ./scripts/deploy_service_to_qnap.sh freecad_bridge
#
#   DEPLOY_VIA=tunnel ./scripts/deploy_service_to_qnap.sh freecad_bridge
#     Route SSH + rsync through `cloudflared access ssh` instead of
#     the LAN IP. Same semantics as scripts/deploy_to_qnap.sh.
#
#   DRY_RUN=1 ./scripts/deploy_service_to_qnap.sh freecad_bridge
#     Print everything that would happen, change nothing.
#
#   NO_REBUILD=1 ./scripts/deploy_service_to_qnap.sh freecad_bridge
#     Skip `docker compose build` — useful when you've already built
#     the image manually and just want to recreate the container.
#
# Adding a new service: extend the four SVC_* tables below. Each
# service needs:
#   - SVC_LOCAL[name]   relative path in this checkout (under services/)
#   - SVC_REMOTE[name]  relative path under QNAP_STACK_DIR/
#   - SVC_NAME[name]    docker compose service name (note the - vs _)
#   - SVC_SMOKE[name]   string to grep for inside the running
#                       container's /app/main.py to confirm the new
#                       image is actually running the new code.
#                       Should be a function name or marker added in
#                       the same commit as the deploy.
set -euo pipefail

DEPLOY_VIA="${DEPLOY_VIA:-lan}"
QNAP_HOST="${QNAP_HOST:-admin@192.168.68.108}"
QNAP_TUNNEL_HOST="${QNAP_TUNNEL_HOST:-admin@ssh.southbrookcabinetry.space}"
QNAP_STACK_DIR="${QNAP_STACK_DIR:-/share/CACHEDEV3_DATA/Container/southbrook}"
QNAP_DOCKER_HOST="${QNAP_DOCKER_HOST:-unix:///var/run/system-docker.sock}"
QNAP_CSTATION_BIN="${QNAP_CSTATION_BIN:-/share/CACHEDEV3_DATA/.qpkg/container-station/bin}"
DRY_RUN="${DRY_RUN:-0}"
NO_REBUILD="${NO_REBUILD:-0}"

# ---- service registry --------------------------------------------------
# Each service entry below sets five vars when the SERVICE arg matches.
# Add a new sidecar by appending a case branch. Bash 3.2 (the default
# macOS shell) does not support associative arrays, so we use a case.
#
# Each branch must set:
#   LOCAL_PATH      relative path in this checkout (under services/)
#   REMOTE_PATH     relative path under QNAP_STACK_DIR/
#   COMPOSE_SVC     docker compose service name (note - vs _)
#   SMOKE_GREP      string to grep inside the running container's
#                   /app/main.py to confirm the new image carries the
#                   new code. Pick a function name or marker added
#                   in the same commit as the deploy. Empty = skip.
#   CONTAINER_NAME  container name on the QNAP — almost always
#                   southbrook-<svc> per existing compose convention.
KNOWN_SERVICES="freecad_bridge"

SERVICE="${1:-}"
if [[ -z "$SERVICE" ]]; then
  printf "[deploy-svc] Usage: %s <service>\n  Known: %s\n" \
    "$(basename "$0")" "$KNOWN_SERVICES" >&2
  exit 2
fi

case "$SERVICE" in
  freecad_bridge)
    LOCAL_PATH="services/freecad_bridge"
    REMOTE_PATH="freecad_bridge"
    COMPOSE_SVC="freecad-bridge"
    SMOKE_GREP="_post_callback_to_odoo"
    CONTAINER_NAME="southbrook-freecad-bridge"
    ;;
  *)
    printf "[deploy-svc] ERROR: unknown service '%s'\n  Known: %s\n" \
      "$SERVICE" "$KNOWN_SERVICES" >&2
    exit 2
    ;;
esac

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ---- pre-flight --------------------------------------------------------
log() { printf "[deploy-svc] %s\n" "$*" >&2; }
fail() { printf "[deploy-svc] ERROR: %s\n" "$*" >&2; exit 1; }
run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    log "DRY: $*"
  else
    "$@"
  fi
}

[[ -d "$LOCAL_PATH" ]] || fail "local path '$LOCAL_PATH' not in this checkout"
command -v rsync >/dev/null || fail "rsync not found"
command -v ssh >/dev/null   || fail "ssh not found"

if [[ "$DEPLOY_VIA" == "tunnel" ]]; then
  command -v cloudflared >/dev/null \
    || fail "DEPLOY_VIA=tunnel needs cloudflared CLI (brew install cloudflared)"
  QNAP_HOST="$QNAP_TUNNEL_HOST"
  log "tunnel mode: SSH routed through 'cloudflared access ssh --hostname %h'"
elif [[ "$DEPLOY_VIA" != "lan" ]]; then
  fail "DEPLOY_VIA must be 'lan' or 'tunnel' (got: $DEPLOY_VIA)"
fi

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

log "target  : $QNAP_HOST (via $DEPLOY_VIA)"
log "service : $SERVICE ($COMPOSE_SVC)"
log "local   : $LOCAL_PATH"
log "remote  : $QNAP_STACK_DIR/$REMOTE_PATH"

# ---- rsync the service's build context --------------------------------
# Same exclude set as the addon deploy script — keeps the QNAP side
# byte-identical with the checkout but doesn't ship pycache pollution.
log "rsync $LOCAL_PATH/ → $QNAP_HOST:$QNAP_STACK_DIR/$REMOTE_PATH/"
run _rsync -az --delete-during \
  --exclude='__pycache__/' --exclude='*.pyc' --exclude='.DS_Store' \
  "$LOCAL_PATH/" "$QNAP_HOST:$QNAP_STACK_DIR/$REMOTE_PATH/"

# ---- docker compose build + recreate ----------------------------------
# Everything below runs on the QNAP host inside a single ssh call so
# we don't pay the tunnel-setup cost per command. The DOCKER_HOST +
# PATH exports are mandatory — see the script header.
remote_script=$(cat <<REMOTE
set -euo pipefail
export DOCKER_HOST="$QNAP_DOCKER_HOST"
export PATH="$QNAP_CSTATION_BIN:\$PATH"
cd "$QNAP_STACK_DIR"

echo "[remote] docker compose config validate"
docker compose config --quiet

if [[ "$NO_REBUILD" != "1" ]]; then
  echo "[remote] docker compose build $COMPOSE_SVC"
  docker compose build $COMPOSE_SVC
fi

echo "[remote] docker compose up -d --force-recreate $COMPOSE_SVC"
docker compose up -d --force-recreate $COMPOSE_SVC

echo "[remote] wait for container healthy (max 60s)"
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  sleep 5
  state=\$(docker inspect "$CONTAINER_NAME" --format '{{.State.Status}}' 2>/dev/null || echo missing)
  health=\$(docker inspect "$CONTAINER_NAME" --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' 2>/dev/null || echo n/a)
  echo "[remote] attempt \$i  state=\$state  health=\$health"
  if [[ "\$state" == "running" && ( "\$health" == "healthy" || "\$health" == "n/a" ) ]]; then
    break
  fi
done
if [[ "\$state" != "running" ]]; then
  echo "[remote] container is not running after recreate — printing last 30 log lines:"
  docker logs --tail 30 "$CONTAINER_NAME" 2>&1 || true
  exit 1
fi

# Smoke grep — confirms the running image carries the new code.
# Skipped silently when SVC_SMOKE is empty.
if [[ -n "$SMOKE_GREP" ]]; then
  echo "[remote] smoke grep for '$SMOKE_GREP' inside running container"
  count=\$(docker exec "$CONTAINER_NAME" sh -c "grep -c '$SMOKE_GREP' /app/main.py" 2>/dev/null || echo 0)
  if [[ "\$count" -lt "1" ]]; then
    echo "[remote] smoke grep returned \$count — new code is NOT in the running image"
    exit 1
  fi
  echo "[remote] smoke OK (grep count: \$count)"
fi
REMOTE
)

if [[ "$DRY_RUN" == "1" ]]; then
  log "DRY: would now execute remote_script (build + recreate + smoke)"
else
  log "executing remote build + recreate sequence…"
  _ssh "$QNAP_HOST" "bash -s" <<<"$remote_script"
fi

log "done. service $SERVICE redeployed."
