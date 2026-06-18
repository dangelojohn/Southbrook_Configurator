#!/usr/bin/env bash
# Run this ON THE QNAP host.
#
# Pull a committed Southbrook repo archive from Forgejo, replace one or more
# addon directories in the live addons mount, then cold-upgrade Odoo locally.
# This avoids rsync/scp/stdin-over-SSH, which restricted agent sandboxes often
# block even when short SSH commands work.

set -euo pipefail

REF=""
MODULES_ARG=""
TEST_TAGS="${TEST_TAGS:-}"
REPO_ARCHIVE_BASE="${REPO_ARCHIVE_BASE:-http://192.168.68.108:9080/git/qnap/southbrook-v19cr/archive}"
QNAP_ADDONS_DIR="${QNAP_ADDONS_DIR:-/share/CACHEDEV3_DATA/Container/southbrook/addons}"
QNAP_DOCKER="${QNAP_DOCKER:-/share/CACHEDEV3_DATA/.qpkg/container-station/bin/system-docker}"
CONTAINER="${CONTAINER:-southbrook-odoo}"
DB="${DB:-southbrook}"
LOCK_PATH="${LOCK_PATH:-/var/lib/odoo/.southbrook-odoo-upgrade.lock}"
LOCK_WAIT_SEC="${LOCK_WAIT_SEC:-600}"

log() { printf "[qnap-pull-deploy] %s\n" "$*" >&2; }
fail() { printf "[qnap-pull-deploy] ERROR: %s\n" "$*" >&2; exit 1; }

usage() {
  cat >&2 <<'EOF'
Usage:
  qnap_pull_deploy.sh --ref <commit-or-branch> --modules <module[,module...]> [--test-tags <tags>]

Environment:
  REPO_ARCHIVE_BASE  default: http://192.168.68.108:9080/git/qnap/southbrook-v19cr/archive
  QNAP_ADDONS_DIR    default: /share/CACHEDEV3_DATA/Container/southbrook/addons
  QNAP_DOCKER        default: /share/CACHEDEV3_DATA/.qpkg/container-station/bin/system-docker
  CONTAINER          default: southbrook-odoo
  DB                 default: southbrook
  TEST_TAGS          optional Odoo --test-tags value
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref)
      REF="${2:-}"; shift 2 ;;
    --modules)
      MODULES_ARG="${2:-}"; shift 2 ;;
    --test-tags)
      TEST_TAGS="${2:-}"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      fail "unknown argument: $1" ;;
  esac
done

[[ -n "$REF" ]] || { usage; fail "--ref is required"; }
[[ -n "$MODULES_ARG" ]] || { usage; fail "--modules is required"; }
[[ -d "$QNAP_ADDONS_DIR" ]] || fail "addons dir not found: $QNAP_ADDONS_DIR"
[[ -x "$QNAP_DOCKER" ]] || fail "system-docker not executable: $QNAP_DOCKER"
command -v curl >/dev/null || fail "curl not found on QNAP"
command -v tar >/dev/null || fail "tar not found on QNAP"

ARCHIVE_URL="${REPO_ARCHIVE_BASE}/${REF}.tar.gz"
WORKDIR="$(mktemp -d /tmp/sbk-pull-deploy.XXXXXX)"
ARCHIVE="$WORKDIR/repo.tar.gz"
EXTRACT="$WORKDIR/extract"
mkdir -p "$EXTRACT"
cleanup() { rm -rf "$WORKDIR"; }
trap cleanup EXIT

log "ref: $REF"
log "modules: $MODULES_ARG"
log "archive: $ARCHIVE_URL"
curl -fsSL "$ARCHIVE_URL" -o "$ARCHIVE" || fail "could not download archive"
tar -xzf "$ARCHIVE" -C "$EXTRACT" || fail "could not extract archive"

SRC_ROOT="$(find "$EXTRACT" -mindepth 1 -maxdepth 1 -type d | head -1)"
[[ -n "$SRC_ROOT" && -d "$SRC_ROOT/addons" ]] || fail "archive has no addons directory"

IFS=',' read -ra MODULES <<< "$MODULES_ARG"
for mod in "${MODULES[@]}"; do
  [[ "$mod" =~ ^[A-Za-z0-9_]+$ ]] || fail "invalid module name: $mod"
  src="$SRC_ROOT/addons/$mod"
  dest="$QNAP_ADDONS_DIR/$mod"
  tmp_dest="$QNAP_ADDONS_DIR/.${mod}.pull-tmp"
  [[ -d "$src" ]] || fail "module not found in archive: addons/$mod"

  log "replace $dest"
  rm -rf "$tmp_dest"
  cp -a "$src" "$tmp_dest"
  rm -rf "$dest"
  mv "$tmp_dest" "$dest"
done

log "classifying install vs upgrade"
PG_PW="$($QNAP_DOCKER exec "$CONTAINER" bash -c "grep -E '^db_password' /etc/odoo/odoo.conf 2>/dev/null | head -1 | cut -d= -f2 | tr -d ' '" 2>/dev/null || true)"
mod_in_list="$(printf "'%s'," "${MODULES[@]}" | sed 's/,$//')"
classify_query="SELECT name || ':' || state FROM ir_module_module WHERE name IN ($mod_in_list);"
known_states="$($QNAP_DOCKER exec -e PGPASSWORD="$PG_PW" "$CONTAINER" psql -h southbrook-postgres -U odoo -d "$DB" -At -c "$classify_query" 2>/dev/null || true)"

to_install=()
to_upgrade=()
for mod in "${MODULES[@]}"; do
  state="$(printf '%s\n' "$known_states" | awk -F: -v m="$mod" '$1==m {print $2}')"
  if [[ -z "$state" || "$state" == "uninstalled" ]]; then
    to_install+=("$mod")
  else
    to_upgrade+=("$mod")
  fi
done

ODOO_FLAGS=()
if [[ "${#to_install[@]}" -gt 0 ]]; then
  INSTALL_ARG="$(IFS=','; echo "${to_install[*]}")"
  ODOO_FLAGS+=("-i" "$INSTALL_ARG")
  log "install: $INSTALL_ARG"
fi
if [[ "${#to_upgrade[@]}" -gt 0 ]]; then
  UPGRADE_ARG="$(IFS=','; echo "${to_upgrade[*]}")"
  ODOO_FLAGS+=("-u" "$UPGRADE_ARG")
  log "upgrade: $UPGRADE_ARG"
fi
[[ "${#ODOO_FLAGS[@]}" -gt 0 ]] || fail "no modules to install or upgrade"

SENTINEL="__SBK_PULL_COLD_OK__"
UPGRADE_LOG="/tmp/qnap_pull_deploy_upgrade.log"

# Combine cold upgrade + targeted tests into ONE Odoo invocation. The
# previous design ran two separate `-u` passes (one cold-upgrade,
# one test-enable) which redundantly loaded the registry twice
# (~3 min/pass on the southbrook DB). Combining them halves the
# wall-clock and removes a class of "passed in pass 1, failed in
# pass 2 with a stale registry" foot-guns.
ODOO_RUN_FLAGS=("${ODOO_FLAGS[@]}" -d "$DB" --stop-after-init --no-http
                "--logfile=/dev/stderr")
if [[ -n "$TEST_TAGS" ]]; then
  ODOO_RUN_FLAGS+=("--test-enable" "--test-tags=$TEST_TAGS")
  log "running cold Odoo upgrade + targeted tests under flock"
  log "test-tags: $TEST_TAGS"
else
  log "running cold Odoo upgrade under flock"
fi

set +e
$QNAP_DOCKER exec "$CONTAINER" bash -c \
  "(: > '$LOCK_PATH' 2>/dev/null || true) && flock -E 75 -w '$LOCK_WAIT_SEC' '$LOCK_PATH' odoo ${ODOO_RUN_FLAGS[*]} && echo '$SENTINEL'" \
  > "$UPGRADE_LOG" 2>&1
rc=$?
set -e
grep -E 'Modules loaded|Registry loaded|ParseError|CRITICAL|ValidationError|AssertionError|Failed to load registry|Traceback|Starting .*test_|post-tests|^FAIL|tests\.stats|__SBK_PULL_COLD_OK__' "$UPGRADE_LOG" \
  | sed 's/^/[odoo] /' >&2 || true
[[ "$rc" -ne 75 ]] || fail "another Odoo upgrade is holding $LOCK_PATH"
[[ "$rc" -eq 0 ]] || fail "cold Odoo upgrade failed with rc=$rc; see $UPGRADE_LOG"
grep -q "$SENTINEL" "$UPGRADE_LOG" || grep -q 'Modules loaded' "$UPGRADE_LOG" \
  || fail "cold Odoo upgrade did not reach success; see $UPGRADE_LOG"
if grep -qE 'Failed to load registry|CRITICAL|AssertionError' "$UPGRADE_LOG"; then
  fail "cold Odoo upgrade hit a registry/load error; see $UPGRADE_LOG"
fi
# Test-failure surface: --test-enable returns 0 even when individual
# tests fail (it only flips on registry-load problems). Promote any
# test FAIL line or post-test ERROR to a script failure here.
if [[ -n "$TEST_TAGS" ]]; then
  if grep -qE '^FAIL: |Test .* failed|post-tests .* with [1-9][0-9]* errors' \
       "$UPGRADE_LOG"; then
    fail "targeted tests failed; see $UPGRADE_LOG"
  fi
fi

log "checking live health"
# `docker exec` (without `-i`) closes stdin → any heredoc to a
# command-line python `-` reads empty and prints nothing, which
# was the v1 health-check bug (`live /web/login health check
# failed: ` with an empty health value). Switching to a curl
# inside the container avoids the stdin question entirely.
health="$($QNAP_DOCKER exec "$CONTAINER" curl -s -o /dev/null \
  -w '%{http_code}' --max-time 20 http://127.0.0.1:8069/web/login 2>&1 \
  || echo ERR)"
[[ "$health" == "200" ]] || fail "live /web/login health check failed: $health"
log "deploy OK"
