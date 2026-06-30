#!/usr/bin/env bash
# scripts/test_lint_owl_expr.sh — self-test for lint-owl-expr.py
#
# Verifies:
#   1. bad.xml fixtures (inside <templates>) flag every known-bad case
#   2. good.xml fixtures pass cleanly:
#       - Section A (inside <templates>): superficially-similar OK forms
#       - Section B (outside <templates>): server-side QWeb word ops
#         are NOT entered — proves the OWL context check works
#   3. line numbers match the bad.xml fixture layout

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCAN="$ROOT/scripts/lint-owl-expr.py"
FIX_DIR="$ROOT/scripts/_test_fixtures/lint-owl"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

EXPECTED_BAD=7

echo "=== Test 1: BAD fixture must be rejected with >= $EXPECTED_BAD violations ==="
if "$SCAN" "$FIX_DIR/bad.xml" > "$TMP/bad.out" 2>&1; then
    echo "FAIL: scanner exited 0 on bad.xml — should have rejected"
    cat "$TMP/bad.out"
    exit 1
fi
BAD_COUNT=$(grep -c 'bad.xml:' "$TMP/bad.out" || true)
if [ "$BAD_COUNT" -lt "$EXPECTED_BAD" ]; then
    echo "FAIL: expected >= $EXPECTED_BAD violations in bad.xml, got $BAD_COUNT"
    cat "$TMP/bad.out"
    exit 1
fi
echo "OK: $BAD_COUNT violations flagged in bad.xml (>= $EXPECTED_BAD expected)"

echo
echo "=== Test 2: GOOD fixture must pass cleanly ==="
if ! "$SCAN" "$FIX_DIR/good.xml" > "$TMP/good.out" 2>&1; then
    echo "FAIL: scanner rejected good.xml — false positives:"
    cat "$TMP/good.out"
    exit 1
fi
echo "OK: good.xml accepted clean (both OWL and server-QWeb sections)"

echo
echo "=== Test 3: line numbers for known-bad cases (B01..B07) ==="
# bad.xml layout: <templates> opens at line 11; B01..B07 on lines 12..18.
for expected_line in 12 13 14 15 16 17 18; do
    if ! grep -q "bad.xml:$expected_line:" "$TMP/bad.out"; then
        echo "FAIL: no violation reported at bad.xml:$expected_line"
        cat "$TMP/bad.out"
        exit 1
    fi
done
echo "OK: all expected line numbers (12..18) reported"

echo
echo "=== Test 4: server-side QWeb word ops (good.xml Section B) NOT flagged ==="
# Section B includes obvious word ops like "not order.archived and order.state".
# If the scanner mis-enters that region we'd see flagged lines. Already
# confirmed by Test 2's clean exit, but explicitly check for the QWeb markers.
if grep -qE "good\.xml:.*(qweb-word-ops|qweb-or-default|mail-template-or)" "$TMP/good.out"; then
    echo "FAIL: scanner entered server-side QWeb region in good.xml"
    cat "$TMP/good.out"
    exit 1
fi
echo "OK: server-side QWeb region correctly skipped"

echo
echo "=== Test 5: inherit-view heuristic (file with no <templates> but uses"
echo "             record.X.raw_value access — OWL after view combination) ==="
if "$SCAN" "$FIX_DIR/bad_inherit.xml" > "$TMP/bad_inherit.out" 2>&1; then
    echo "FAIL: scanner missed inherit-view OWL bug — heuristic broken"
    cat "$TMP/bad_inherit.out"
    exit 1
fi
if ! grep -q "bad_inherit.xml:14: word operator 'and'" "$TMP/bad_inherit.out"; then
    echo "FAIL: expected 'word operator and' on bad_inherit.xml:14"
    cat "$TMP/bad_inherit.out"
    exit 1
fi
echo "OK: inherit-view heuristic catches OWL bug in a file lacking <templates>"

echo
echo "All OWL scanner self-tests passed."
