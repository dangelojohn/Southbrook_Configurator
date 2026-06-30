#!/usr/bin/env bash
# scripts/list-prod-southbrook-modules.sh
#
# Print every southbrook_* module currently installed in the live QNAP
# southbrook-postgres, one per line, alphabetically sorted. Used by the
# prod-module-drift CI workflow to verify the Makefile MODULES list
# matches actual prod state — the recurring failure mode is feature
# deploys (Hermes, Premium Orchestration, etc.) that ship to prod without
# being backfilled into MODULES, leaving them outside cold-install CI.
#
# Usage:
#   ./scripts/list-prod-southbrook-modules.sh          # via SSH from any host
#   ./scripts/list-prod-southbrook-modules.sh --local  # already on the QNAP
#                                                       (CI runner uses this)
#
# Requires either:
#   - SSH access to admin@192.168.68.108:22 (LAN dev)
#   - Or --local, with docker on the system-docker socket (CI runner / QNAP)
#
# Exit:
#   0 = printed list (may be empty)
#   1 = postgres unreachable

set -euo pipefail

LOCAL=0
if [ "${1:-}" = "--local" ]; then
    LOCAL=1
fi

QUERY="SELECT name FROM ir_module_module WHERE name LIKE 'southbrook_%' AND state='installed' ORDER BY name;"

if [ "$LOCAL" -eq 1 ]; then
    # Two environments hit --local:
    #  (a) Running on the QNAP host shell — needs the Container-Station
    #      docker binary + explicit system-docker socket.
    #  (b) Running inside a Forgejo runner job container — `docker` is on
    #      PATH and already targets the mounted system-docker socket.
    if [ -S /var/run/system-docker.sock ] \
       && [ -x /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker ]; then
        DOCKER="/share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker -H unix:///var/run/system-docker.sock"
    elif command -v docker >/dev/null 2>&1; then
        DOCKER="docker"
    else
        echo "ERROR: no docker available in --local mode" >&2
        exit 1
    fi
    $DOCKER exec southbrook-postgres \
        psql -U odoo -d southbrook -tAc "$QUERY" 2>/dev/null | grep -v '^$' || {
            echo "ERROR: cannot query southbrook-postgres locally" >&2
            exit 1
        }
else
    ssh -p 22 -o ConnectTimeout=10 admin@192.168.68.108 \
        "/share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker \
         -H unix:///var/run/system-docker.sock exec southbrook-postgres \
         psql -U odoo -d southbrook -tAc \"$QUERY\"" 2>/dev/null | grep -v '^$' || {
            echo "ERROR: cannot query southbrook-postgres via SSH" >&2
            exit 1
        }
fi
