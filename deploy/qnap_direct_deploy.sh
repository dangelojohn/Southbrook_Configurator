#!/usr/bin/env bash
# SPDX-License-Identifier: LGPL-3.0-only
#
# qnap_direct_deploy.sh — paste-and-run on the QNAP to land kitchenforge
# on the live southbrook stack. Bypasses Forgejo CI entirely.
#
# WHERE TO RUN: a shell on the QNAP (via SSH, QTS web shell, or Container
# Station's southbrook-odoo terminal — the script auto-detects docker access).
#
# WHAT IT DOES:
#   1. Discovers the addon path the live Odoo reads from
#   2. Pulls latest kitchenforge_* from the public GitHub mirror
#   3. Copies them into the container
#   4. Runs odoo -i kitchenforge_core (isolated — confirms simplest case)
#   5. Asserts kitchenforge_core is in state 'installed' in the DB
#   6. Restarts southbrook-odoo
#   7. Probes the live endpoint
#
# SAFE TO RE-RUN: every step is idempotent. Wipes the prior copy of each
# addon before re-copying; uses both -i and -u so install or upgrade both
# work. Locks with flock so concurrent invocations queue instead of racing.
#
# WHAT TO PASTE IF SOMETHING BREAKS: the script tails the odoo install log,
# the docker ps state, and the ir_module_module registry. Paste me the
# bottom 100 lines of output.

set -euo pipefail

CONTAINER="${CONTAINER:-southbrook-odoo}"
DB="${DB:-southbrook}"
BRANCH="${BRANCH:-feature/premium-orchestration}"
ADDONS=(kitchenforge_core)  # isolated start — add marathon/saas/seed after this works
GIT_REPO="${GIT_REPO:-https://github.com/dangelojohn/Southbrook_Configurator.git}"
WORK_DIR="${WORK_DIR:-/tmp/kf-direct-deploy}"

# Choose the right docker CLI. On QNAP, system-docker manages the
# southbrook-odoo container; the default `docker` CLI talks to QTS Container
# Station's own daemon which may not see it.
DOCKER="docker"
if [ -S /var/run/system-docker.sock ]; then
    DOCKER="docker -H unix:///var/run/system-docker.sock"
elif [ -x /share/CACHEDEV3_DATA/.qpkg/container-station/bin/system-docker ]; then
    DOCKER="/share/CACHEDEV3_DATA/.qpkg/container-station/bin/system-docker"
fi

heading() { printf "\n=== %s ===\n" "$*"; }

heading "1. verify $CONTAINER is reachable via docker"
if ! $DOCKER ps --filter "name=^${CONTAINER}$" --format '{{.Names}}' | grep -q "$CONTAINER"; then
    echo "FATAL: $CONTAINER not running on this docker daemon" >&2
    echo "Available containers:"
    $DOCKER ps --format '  {{.Names}} ({{.Status}})' | head -20
    exit 1
fi
echo "  ✓ $CONTAINER is up: $($DOCKER ps --filter "name=^${CONTAINER}$" --format '{{.Status}}')"

heading "2. discover the addon path the live Odoo reads from"
TARGET=$($DOCKER exec "$CONTAINER" bash -c '
for p in /mnt/extra-addons /opt/odoo/addons /var/lib/odoo/addons; do
    if [ -d "$p" ] && [ -w "$p" ]; then echo "$p"; exit 0; fi
done
echo /mnt/extra-addons
')
echo "  detected target: $TARGET"
$DOCKER exec "$CONTAINER" bash -c "ls -1 '$TARGET' | head -10 | sed 's|^|  existing: |'"

heading "3. fetch latest source from $GIT_REPO ($BRANCH)"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"
if [ -d .git ]; then
    git fetch origin "$BRANCH"
    git reset --hard "origin/$BRANCH"
else
    git clone --depth 1 --branch "$BRANCH" "$GIT_REPO" .
fi
echo "  HEAD: $(git rev-parse --short HEAD)"

heading "4. verify each addon exists in the fetched tree"
for addon in "${ADDONS[@]}"; do
    if [ ! -d "addons/$addon" ]; then
        echo "FATAL: addons/$addon not in checkout" >&2
        ls addons/ | head -20
        exit 1
    fi
    if [ ! -f "addons/$addon/__manifest__.py" ]; then
        echo "FATAL: addons/$addon/__manifest__.py missing" >&2
        exit 1
    fi
    echo "  ✓ addons/$addon ($(wc -c < "addons/$addon/__manifest__.py") byte manifest)"
done

heading "5. docker cp each addon into $CONTAINER:$TARGET"
for addon in "${ADDONS[@]}"; do
    $DOCKER exec "$CONTAINER" bash -c "rm -rf '$TARGET/$addon'" || true
    echo "  copying addons/$addon -> $CONTAINER:$TARGET/"
    $DOCKER cp "addons/$addon" "$CONTAINER:$TARGET/"
    if ! $DOCKER exec "$CONTAINER" bash -c "[ -f '$TARGET/$addon/__manifest__.py' ]"; then
        echo "FATAL: $addon/__manifest__.py not present in container after cp" >&2
        $DOCKER exec "$CONTAINER" bash -c "ls -la '$TARGET/' | head -30"
        exit 1
    fi
    echo "  ✓ $addon/__manifest__.py verified in container"
done

heading "6. update Odoo's apps list so the new addons are visible"
# `--update-list` on apps doesn't exist in CLI; we need to install/upgrade base
# so the registry picks up new addons. The -i flag below does this automatically.

heading "7. run odoo -i/-u for the addons (lock-protected; this can take 2-5 min)"
ADDON_CSV=$(IFS=, ; echo "${ADDONS[*]}")
echo "  ADDON_CSV=$ADDON_CSV"
echo "  command: odoo -d $DB -i $ADDON_CSV -u $ADDON_CSV --stop-after-init --no-http --workers=0 --max-cron-threads=0"
$DOCKER exec "$CONTAINER" bash -c "
flock -E 75 -w 600 /tmp/southbrook-odoo-upgrade.lock \
  odoo -d $DB \
    -i $ADDON_CSV \
    -u $ADDON_CSV \
    --stop-after-init --no-http \
    --workers=0 --max-cron-threads=0
" 2>&1 | tee /tmp/kf-install.log | tail -40

INSTALL_RC=${PIPESTATUS[0]}
echo "  --- install exit code: $INSTALL_RC ---"
if [ "$INSTALL_RC" -ne 0 ]; then
    echo "INSTALL FAILED. Last 80 lines of log:" >&2
    tail -80 /tmp/kf-install.log >&2
    exit "$INSTALL_RC"
fi

heading "8. HARD ASSERT — each addon is in state 'installed' in the DB"
for addon in "${ADDONS[@]}"; do
    STATE=$($DOCKER exec "$CONTAINER" bash -c "
        psql -h localhost -U odoo -d $DB -tA -c \
          \"SELECT state FROM ir_module_module WHERE name = '$addon';\"
    " | tr -d '[:space:]')
    echo "  $addon: $STATE"
    if [ "$STATE" != "installed" ]; then
        echo "FATAL: $addon is in state '$STATE'" >&2
        echo "=== full kitchenforge registry state ==="
        $DOCKER exec "$CONTAINER" bash -c "
          psql -h localhost -U odoo -d $DB -c \
            \"SELECT name, state, latest_version FROM ir_module_module WHERE name LIKE 'kitchenforge%' OR name = 'southbrook_api' ORDER BY name;\"
        "
        echo "=== last 60 lines of odoo log ==="
        $DOCKER logs "$CONTAINER" --tail 60 2>&1
        exit 1
    fi
done

heading "9. restart $CONTAINER to clear worker ormcache"
$DOCKER restart "$CONTAINER"
echo "  sleeping 12s for cold init..."
sleep 12

heading "10. probe the live endpoints"
for p in /web/login /.well-known/ai-agent.json /agent/v1/files /agent/v1/tools; do
    for i in 1 2 3; do
        c=$(curl -sk -o /dev/null -w '%{http_code}' --max-time 5 "https://southbrookcabinetry.space$p" 2>/dev/null || echo 000)
        if [ "$c" = "200" ] || [ "$c" = "401" ]; then break; fi
        sleep 3
    done
    case "$c" in
        200) mark="✓ public" ;;
        401) mark="✓ deployed (auth wall)" ;;
        404) mark="✗ not registered" ;;
        502) mark="? still booting" ;;
        *)   mark="? $c" ;;
    esac
    printf "  %-40s HTTP %s   %s\n" "$p" "$c" "$mark"
done

heading "DONE"
echo "  HEAD: $(git rev-parse --short HEAD)"
echo "  Install log: /tmp/kf-install.log on QNAP (~$(wc -l < /tmp/kf-install.log 2>/dev/null || echo '?') lines)"
echo ""
echo "  If /.well-known/ai-agent.json now returns 200, kitchenforge_core is live."
echo "  Next: add kitchenforge_marathon, kitchenforge_saas, kitchenforge_southbrook_seed"
echo "  to ADDONS=() at the top of this script and re-run."
