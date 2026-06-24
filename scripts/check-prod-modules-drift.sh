#!/usr/bin/env bash
# scripts/check-prod-modules-drift.sh
#
# Fail if the Makefile's CI MODULES list drifts from what's actually
# installed in prod. Symmetric drift detection:
#   PROD ∖ CI   = modules shipped to prod but not cold-install-validated
#   CI   ∖ PROD = modules in MODULES that aren't in prod (stale list)
#
# Acknowledged exclusions are honored via EXCLUDE list below — modules
# we KNOW we can't currently cold-install (e.g., southbrook_plm_productgraph
# pending product_graph_release vendoring) are subtracted from PROD before
# comparison. The Makefile comment block must stay in sync with EXCLUDE.
#
# Usage:
#   ./scripts/check-prod-modules-drift.sh           # via SSH (LAN dev)
#   ./scripts/check-prod-modules-drift.sh --local   # CI runner on QNAP
#
# Exit:
#   0 = MODULES list matches prod (minus EXCLUDEs)
#   1 = drift detected — see message
#   2 = could not reach prod

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Known-unfixable for now. Adding a module here means: "yes, we deploy it,
# yes, CI can't cold-install it, here's why" — and the Makefile header
# comment must match.
EXCLUDE=(
    # (formerly: southbrook_plm_productgraph — dropped from prod 2026-06-23
    # along with the ECO-to-ProductGraph bridge; vendor decision deferred. The
    # 4-addon vendor chain (product_graph_base/revision/ebom/release) lives in
    # ~/product_graph_v19/ if anyone restores the bridge later.)
)

LOCAL_FLAG="${1:-}"

# 1) Extract Makefile's MODULES list. (cut, not sed — portable across BSD/GNU.)
MAKEFILE_RAW=$(grep -E '^MODULES[[:space:]]*=' Makefile | head -1 | cut -d= -f2-)
[ -n "$MAKEFILE_RAW" ] || { echo "ERROR: MODULES not found in Makefile" >&2; exit 2; }
echo "$MAKEFILE_RAW" | tr ',' '\n' | tr -d ' \t' | grep -v '^$' | sort -u > /tmp/ci-modules.list

# 2) Get current prod-installed list.
if ! ./scripts/list-prod-southbrook-modules.sh $LOCAL_FLAG > /tmp/prod-modules.list; then
    echo "ERROR: could not query prod" >&2
    exit 2
fi

# 3) Subtract EXCLUDE from prod. The ${arr[@]+"${arr[@]}"} form expands to
# nothing when the array is empty (default behavior trips `set -u`).
printf '%s\n' ${EXCLUDE[@]+"${EXCLUDE[@]}"} | sort -u > /tmp/excludes.list
comm -23 /tmp/prod-modules.list /tmp/excludes.list > /tmp/prod-validatable.list

# 4) Symmetric diff.
ONLY_PROD=$(comm -23 /tmp/prod-validatable.list /tmp/ci-modules.list)
ONLY_CI=$(comm -13 /tmp/prod-validatable.list /tmp/ci-modules.list)

FAIL=0
if [ -n "$ONLY_PROD" ]; then
    echo "DRIFT: deployed to prod but NOT in Makefile MODULES (cold-install gap):"
    echo "$ONLY_PROD" | sed 's/^/  - /'
    FAIL=1
fi
if [ -n "$ONLY_CI" ]; then
    echo "DRIFT: in Makefile MODULES but NOT installed in prod (stale list):"
    echo "$ONLY_CI" | sed 's/^/  - /'
    FAIL=1
fi

if [ "$FAIL" -eq 0 ]; then
    PROD_COUNT=$(wc -l < /tmp/prod-validatable.list | tr -d ' ')
    CI_COUNT=$(wc -l < /tmp/ci-modules.list | tr -d ' ')
    EXCL_COUNT=${#EXCLUDE[@]}
    echo "OK: Makefile MODULES ($CI_COUNT) matches prod-installed ($PROD_COUNT) minus EXCLUDE ($EXCL_COUNT)."
    exit 0
fi

echo
echo "Fix options:"
echo "  - If module SHOULD be cold-install-validated: add to Makefile MODULES."
echo "  - If module CANNOT cold-install (yet): add to EXCLUDE in this script"
echo "    AND document why in the Makefile header comment."
echo "  - If module was removed from prod: drop from Makefile MODULES."
exit 1
