#!/usr/bin/env bash
# scripts/cold-install-test.sh
#
# Validate that a comma-separated module list cold-installs cleanly on a
# throwaway DB. Run BEFORE adding new modules to Makefile MODULES so the
# Makefile is always a guaranteed-installable set.
#
# Replaces the ad-hoc SSH+docker-exec recipe documented in
# memory/southbrook_cold_install_gaps.md. Used to validate Tier A
# (2026-06-23, 17 min) and Tier B (2026-06-23).
#
# Usage:
#   ./scripts/cold-install-test.sh                       # uses Makefile MODULES
#   ./scripts/cold-install-test.sh mod1,mod2,mod3        # explicit list
#   DB_SUFFIX=tier_c ./scripts/cold-install-test.sh ...  # custom test-db name
#
# Defaults / overrides (env vars):
#   QNAP_HOST       admin@192.168.68.108
#   CONTAINER       southbrook-odoo
#   PG_CONTAINER    southbrook-postgres
#   DB_USER         odoo
#   DB_SUFFIX       <epoch>           — used in db name ci_test_<suffix>
#
# Exit:
#   0 = cold-install clean (registry loaded, no install errors)
#   1 = install failed; throwaway DB dropped before exit
#   2 = usage error / unreachable QNAP

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

QNAP_HOST="${QNAP_HOST:-admin@192.168.68.108}"
CONTAINER="${CONTAINER:-southbrook-odoo}"
PG_CONTAINER="${PG_CONTAINER:-southbrook-postgres}"
DB_USER="${DB_USER:-odoo}"
# Date.now() is a stand-in here for "uniquify across overlapping runs". Tests
# self-clean (DROP at end), so an epoch suffix is fine.
DB_SUFFIX="${DB_SUFFIX:-$(date +%s)}"
DB_NAME="ci_test_${DB_SUFFIX}"
DOCKER="/share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker -H unix:///var/run/system-docker.sock"

# Module list: arg-1 wins, else read Makefile MODULES.
MODULES_ARG="${1:-}"
if [ -z "$MODULES_ARG" ]; then
    MODULES_ARG=$(grep -E '^MODULES[[:space:]]*=' Makefile | head -1 | cut -d= -f2- | tr -d ' \t')
    [ -n "$MODULES_ARG" ] || { echo "ERROR: MODULES not found in Makefile" >&2; exit 2; }
fi
mod_count=$(echo "$MODULES_ARG" | tr ',' '\n' | wc -l | tr -d ' ')

echo "=== cold-install-test ==="
echo "  modules ($mod_count): $MODULES_ARG"
echo "  throwaway db: $DB_NAME"
echo "  qnap: $QNAP_HOST"
echo

ssh -p 22 -o ConnectTimeout=10 "$QNAP_HOST" "
set -e
PG_PW=\$($DOCKER exec $CONTAINER bash -c 'grep -E \"^db_password\" /etc/odoo/odoo.conf 2>/dev/null | head -1 | cut -d= -f2 | tr -d \" \"')
[ -n \"\$PG_PW\" ] || { echo 'ERROR: cannot read pg password from odoo.conf' >&2; exit 2; }

echo '[setup] drop+create throwaway db'
$DOCKER exec $PG_CONTAINER psql -U $DB_USER -d postgres -c \"DROP DATABASE IF EXISTS $DB_NAME WITH (FORCE);\" >/dev/null
$DOCKER exec $PG_CONTAINER createdb -U $DB_USER $DB_NAME

echo '[install] starting cold-install (may take 10-20 min for full MODULES set)…'
START=\$(date +%s)
set +e
$DOCKER exec $CONTAINER odoo -d $DB_NAME -i $MODULES_ARG \\
    --stop-after-init --no-http --workers=0 --max-cron-threads=0 \\
    --db_host=$PG_CONTAINER --db_user=$DB_USER --db_password=\"\$PG_PW\" \\
    --http-port=8899 --gevent-port=8902 \\
    --logfile=/dev/stderr 2>&1 | tee /tmp/${DB_NAME}.log >/dev/null
# PIPESTATUS[0] is odoo's exit code (NOT tee's); without this we'd always
# see exit=0 because tee succeeds on every install regardless of outcome.
RC=\${PIPESTATUS[0]}
set -e
ELAPSED=\$(( \$(date +%s) - START ))
echo '[install] filtered tail of log:'
grep -E 'CRITICAL|ERROR|Modules loaded|Registry loaded|Failed' /tmp/${DB_NAME}.log | tail -10 || echo '  (no matching lines)'

echo '[cleanup] force-drop throwaway db'
$DOCKER exec $PG_CONTAINER psql -U $DB_USER -d postgres -c \"DROP DATABASE IF EXISTS $DB_NAME WITH (FORCE);\" >/dev/null

# Verdict: bash exit code AND log signals.
if [ \$RC -ne 0 ]; then
    echo \"[result] FAIL (odoo exit=\$RC after \${ELAPSED}s) — tail /tmp/${DB_NAME}.log on QNAP for full output\"
    exit 1
fi
if ! grep -q 'Modules loaded' /tmp/${DB_NAME}.log; then
    echo \"[result] FAIL — 'Modules loaded' marker missing (after \${ELAPSED}s)\"
    exit 1
fi
if grep -qE 'CRITICAL|Failed to load registry|Failed to initialize' /tmp/${DB_NAME}.log; then
    echo \"[result] FAIL — CRITICAL/Failed line in log (after \${ELAPSED}s)\"
    exit 1
fi
echo \"[result] OK — cold-installs cleanly (\${ELAPSED}s)\"
exit 0
"
