#!/usr/bin/env bash
# scripts/lint-xml.sh — NF12 mitigation
#
# Validate every *.xml file in the southbrook addons by parsing it with
# Python's ElementTree. Fails fast on the first malformed file with a
# line+column hint, so the "double-dash inside a comment" class of slip
# (and every other XML well-formedness violation) is caught BEFORE commit.
#
# Usage:  ./scripts/lint-xml.sh
# Exit:   0 = all clean, non-zero = first bad file
#
# Wire into pre-commit (Phase 2) when the framework lands; until then,
# call manually before every XML-touching commit.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Limit scope to the southbrook addons. The vendored OCA modules are
# treated as immutable upstream.
# Widened 2026-06-22 from {estimating, estimating_website} to all
# southbrook_* via glob — covers the full deployed surface (~25 addons,
# 198 XML files). Dry-run was clean before widening. New addons matching
# the glob are auto-included.
TARGETS=(addons/southbrook_*)

FAIL=0
for dir in "${TARGETS[@]}"; do
    if [ ! -d "$dir" ]; then continue; fi
    while IFS= read -r f; do
        if ! python3 -c "import xml.etree.ElementTree as ET, sys; ET.parse('$f')" 2>&1; then
            echo "FAIL: $f"
            FAIL=1
        fi
    done < <(find "$dir" -name "*.xml" -type f)
done

if [ "$FAIL" -eq 0 ]; then
    echo "OK: all *.xml in southbrook addons parse clean"
fi
exit "$FAIL"
