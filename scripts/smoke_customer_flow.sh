#!/usr/bin/env bash
# ----------------------------------------------------------------------
# Customer-flow harness smoke test.
#
# Walks every page Sarah Johnson hits between the homepage and her
# first submitted quote, asserting DOM markers + DB state at each
# step. Pure curl + psql probes — no real browser, but exercises
# every HTTP route, every JSON-RPC, and every DB write touched by
# the G1-G17 work landed 2026-06-01.
#
# Run with:
#     bash scripts/smoke_customer_flow.sh
#
# Exits 0 if everything passes; 1 if any assertion fails. Reports the
# full list of pass/fail at the end.
# ----------------------------------------------------------------------
set -uo pipefail

CURL_BASE='curl -sk --resolve www.southbrookcabinetry.local:9443:192.168.68.108'
H=https://www.southbrookcabinetry.local:9443
QSSH='ssh -o ConnectTimeout=10 admin@192.168.68.108'
QDB='/share/CACHEDEV3_DATA/.qpkg/container-station/usr/bin/docker --host unix:///var/run/system-docker.sock exec southbrook-postgres psql -U odoo -d southbrook -tAc'

PASS=0
FAIL=0
FAILS=()

assert() {
    local desc="$1" actual="$2" expected="$3"
    if [ "$actual" = "$expected" ] || echo "$actual" | grep -q -F "$expected"; then
        PASS=$((PASS + 1))
        printf '  ✓ %-60s\n' "$desc"
    else
        FAIL=$((FAIL + 1))
        FAILS+=("$desc :: expected '$expected', got '$actual'")
        printf '  ✗ %-60s  expected=%s got=%s\n' "$desc" "$expected" "$actual"
    fi
}

assert_present() {
    local desc="$1" haystack="$2" needle="$3"
    if echo "$haystack" | grep -q -F "$needle"; then
        PASS=$((PASS + 1))
        printf '  ✓ %-60s\n' "$desc"
    else
        FAIL=$((FAIL + 1))
        FAILS+=("$desc :: needle '$needle' not in haystack")
        printf '  ✗ %-60s  needle=%s missing\n' "$desc" "$needle"
    fi
}

assert_in_file() {
    # Same as assert_present but takes a file path instead of inlining
    # a big string into bash — avoids broken-pipe issues on bundle-size
    # haystacks (5 MB JS, 1 MB CSS).
    local desc="$1" path="$2" needle="$3"
    if grep -q -F "$needle" "$path"; then
        PASS=$((PASS + 1))
        printf '  ✓ %-60s\n' "$desc"
    else
        FAIL=$((FAIL + 1))
        FAILS+=("$desc :: needle '$needle' not in $path")
        printf '  ✗ %-60s  needle=%s missing\n' "$desc" "$needle"
    fi
}

CJ=$(mktemp); trap 'rm -f $CJ /tmp/sm_*.html' EXIT

echo
echo "================================================================"
echo " Customer-flow harness smoke ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
echo "================================================================"

# ----------------------------------------------------------------------
# G1 + G2 — anonymous /
# ----------------------------------------------------------------------
echo
echo "[G1+G2] Anonymous homepage"
STATUS=$($CURL_BASE -o /tmp/sm_home.html -w '%{http_code}' "$H/")
assert "GET / returns 200" "$STATUS" "200"
HOME=$(cat /tmp/sm_home.html)
assert_present "title shows Southbrook brand" "$HOME" "Southbrook Cabinetry"
assert_present "hero copy 'Custom kitchen cabinets'" "$HOME" "Custom kitchen cabinets"
assert_present "primary CTA 'Design Your Kitchen'" "$HOME" "Design Your Kitchen"
assert_present "Signature Series card" "$HOME" "Signature Series"
assert_present "Configure feature block" "$HOME" "Configure"
assert_present "Visualize feature block" "$HOME" "Visualize"
assert_present "Start Now secondary CTA" "$HOME" "Start Now"

# ----------------------------------------------------------------------
# G6 — branded /web/login
# ----------------------------------------------------------------------
echo
echo "[G6] Branded /web/login chrome"
$CURL_BASE -c "$CJ" -o /tmp/sm_login.html "$H/web/login"
LOGIN=$(cat /tmp/sm_login.html)
assert_present "login chrome row" "$LOGIN" "o_sb_auth_row"
assert_present "walnut brand panel" "$LOGIN" "o_sb_auth_brand"
assert_present "Welcome heading" "$LOGIN" "Welcome to"
assert_present "FREE TO START mono badge" "$LOGIN" "FREE TO START"
assert_present "Back to home link" "$LOGIN" "Back to home"

# ----------------------------------------------------------------------
# G5 + G6 — /web/signup with project_name field
# ----------------------------------------------------------------------
echo
echo "[G5+G6] /web/signup form"
$CURL_BASE -c "$CJ" -o /tmp/sm_signup.html "$H/web/signup"
SIGNUP=$(cat /tmp/sm_signup.html)
assert_present "signup brand panel" "$SIGNUP" "o_sb_auth_brand"
assert_present "project_name field present" "$SIGNUP" 'name="project_name"'
assert_present "project prompt label" "$SIGNUP" "What should we call"
assert_present "placeholder example" "$SIGNUP" "Smith Family Kitchen"

# ----------------------------------------------------------------------
# G4 + G5 + G8 — POST signup → project name → client_order_ref
# ----------------------------------------------------------------------
echo
echo "[G4+G5+G8] POST /web/signup with project_name"
TS=$(date +%s)
EMAIL="smoke${TS}@southbrook-test.local"
PROJECT="Smoke Test Kitchen ${TS}"
TOK=$(grep -oE 'name="csrf_token" value="[^"]+"' /tmp/sm_signup.html | head -1 | sed 's/.*value="//;s/".*//')
SU=$($CURL_BASE -c "$CJ" -b "$CJ" -o /tmp/sm_signup_post.html -w 'FINAL=%{url_effective}' \
    -L \
    --data-urlencode "csrf_token=$TOK" \
    --data-urlencode "login=$EMAIL" --data-urlencode "name=Smoke User" \
    --data-urlencode "project_name=$PROJECT" \
    --data-urlencode "password=demo12345!" --data-urlencode "confirm_password=demo12345!" \
    --data-urlencode "redirect=/my/southbrook/order-builder/new" \
    "$H/web/signup")
echo "  $SU"
ORDER_ID=$($QSSH "$QDB \"SELECT id FROM sale_order WHERE partner_id IN (SELECT partner_id FROM res_users WHERE login='$EMAIL') ORDER BY id DESC LIMIT 1;\"" | tr -d '[:space:]')
assert "redirect lands on /my/southbrook/order-builder/<id>" "$SU" "order-builder/$ORDER_ID"
CLIENT_REF=$($QSSH "$QDB \"SELECT client_order_ref FROM sale_order WHERE id=$ORDER_ID;\"" | tr -d '\n')
assert "client_order_ref equals project name" "$CLIENT_REF" "$PROJECT"
STATE=$($QSSH "$QDB \"SELECT state FROM sale_order WHERE id=$ORDER_ID;\"" | tr -d '[:space:]')
assert "new order state=draft" "$STATE" "draft"

# ----------------------------------------------------------------------
# G14 — order builder page renders with data-mode='customer'
# ----------------------------------------------------------------------
echo
echo "[G14] Order Builder mount mode"
$CURL_BASE -c "$CJ" -b "$CJ" -o /tmp/sm_ob.html "$H/my/southbrook/order-builder/$ORDER_ID"
OB=$(cat /tmp/sm_ob.html)
MODE=$(echo "$OB" | grep -oE 'data-mode="[^"]+"' | head -1)
assert "mount div has data-mode='customer'" "$MODE" 'data-mode="customer"'

# ----------------------------------------------------------------------
# G11+G12+G13 — POST /api/order/<id>/add-line
# ----------------------------------------------------------------------
echo
echo "[G11+G12+G13] Add cabinet via API"
TMPL=$($QSSH "$QDB \"SELECT id FROM product_template WHERE default_code='SB-BASE-1DR';\"" | tr -d '[:space:]')
ADD=$($CURL_BASE -c "$CJ" -b "$CJ" -X POST "$H/southbrook/api/order/$ORDER_ID/add-line" \
    -H "Content-Type: application/json" \
    -d "{\"jsonrpc\":\"2.0\",\"method\":\"call\",\"params\":{\"product_tmpl_id\":$TMPL},\"id\":1}")
LINE_OK=$(echo "$ADD" | python3 -c "import json,sys;print(json.load(sys.stdin)['result'].get('ok'))")
LINE_ID=$(echo "$ADD" | python3 -c "import json,sys;print(json.load(sys.stdin)['result'].get('line_id',''))")
assert "add-line returns ok=True" "$LINE_OK" "True"
PRICE_UNIT=$($QSSH "$QDB \"SELECT price_unit FROM sale_order_line WHERE id=$LINE_ID;\"" | tr -d '[:space:]')
assert "line price_unit = 295.0" "$PRICE_UNIT" "295.0"

# ----------------------------------------------------------------------
# G15 — attribute picker + value swap
# ----------------------------------------------------------------------
echo
echo "[G15] Attribute picker"
ATTRS=$($CURL_BASE -c "$CJ" -b "$CJ" -X POST "$H/southbrook/api/line/$LINE_ID/attributes" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"call","params":{},"id":1}')
ATTR_COUNT=$(echo "$ATTRS" | python3 -c "import json,sys;print(len(json.load(sys.stdin)['result']['attributes']))")
assert "attribute count >= 10" "$([ "$ATTR_COUNT" -ge 10 ] && echo "True" || echo "False")" "True"

DOOR_ATTR=$($QSSH "$QDB \"SELECT id FROM product_attribute WHERE name->>'en_US'='Door Style';\"" | tr -d '[:space:]')
WG=$($QSSH "$QDB \"SELECT id FROM product_attribute_value WHERE name->>'en_US' LIKE '%Woodgrain%' LIMIT 1;\"" | tr -d '[:space:]')
SET=$($CURL_BASE -c "$CJ" -b "$CJ" -X POST "$H/southbrook/api/line/$LINE_ID/set-attribute" \
    -H "Content-Type: application/json" \
    -d "{\"jsonrpc\":\"2.0\",\"method\":\"call\",\"params\":{\"attribute_id\":$DOOR_ATTR,\"value_id\":$WG},\"id\":1}")
SET_OK=$(echo "$SET" | python3 -c "import json,sys;print(json.load(sys.stdin)['result'].get('ok'))")
assert "set-attribute Door Style → Woodgrain ok" "$SET_OK" "True"

# Verify combination_indices actually changed (variant swap occurred)
COMB=$($QSSH "$QDB \"SELECT count(*) FROM product_template_attribute_value ptav JOIN product_variant_combination pvc ON pvc.product_template_attribute_value_id = ptav.id WHERE pvc.product_product_id = (SELECT product_id FROM sale_order_line WHERE id=$LINE_ID) AND ptav.attribute_id=$DOOR_ATTR;\"" | tr -d '[:space:]')
assert "line variant carries the Door Style PTAV" "$COMB" "1"

# ----------------------------------------------------------------------
# G16+G17 — submit + state flip + chatter
# ----------------------------------------------------------------------
echo
echo "[G16+G17] Request a Price"
REQ=$($CURL_BASE -c "$CJ" -b "$CJ" -X POST "$H/southbrook/api/order/$ORDER_ID/action" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"call","params":{"action_code":"request_price"},"id":1}')
REQ_OK=$(echo "$REQ" | python3 -c "import json,sys;r=json.load(sys.stdin)['result'];print(r.get('ok'))")
REQ_STATE=$(echo "$REQ" | python3 -c "import json,sys;r=json.load(sys.stdin)['result'];print(r.get('new_state'))")
ALREADY=$(echo "$REQ" | python3 -c "import json,sys;r=json.load(sys.stdin)['result'];print(r.get('already_submitted'))")
assert "request_price returns ok=True" "$REQ_OK" "True"
assert "new_state = sent" "$REQ_STATE" "sent"
assert "already_submitted = False on first submit" "$ALREADY" "False"

DB_STATE=$($QSSH "$QDB \"SELECT state FROM sale_order WHERE id=$ORDER_ID;\"" | tr -d '[:space:]')
DB_DATE=$($QSSH "$QDB \"SELECT southbrook_submitted_date IS NOT NULL FROM sale_order WHERE id=$ORDER_ID;\"" | tr -d '[:space:]')
assert "DB order.state = sent" "$DB_STATE" "sent"
assert "DB southbrook_submitted_date stamped" "$DB_DATE" "t"

# Chatter post + outgoing mail
SUBMIT_CHATTER=$($QSSH "$QDB \"SELECT count(*) FROM mail_message WHERE model='sale.order' AND res_id=$ORDER_ID AND subject='Quote submitted for review';\"" | tr -d '[:space:]')
QUOTE_EMAIL=$($QSSH "$QDB \"SELECT count(*) FROM mail_message WHERE model='sale.order' AND res_id=$ORDER_ID AND message_type='email_outgoing';\"" | tr -d '[:space:]')
assert "chatter 'Quote submitted for review' posted" "$SUBMIT_CHATTER" "1"
assert "outgoing quotation email queued" "$QUOTE_EMAIL" "1"

# Idempotent re-submit
REQ2=$($CURL_BASE -c "$CJ" -b "$CJ" -X POST "$H/southbrook/api/order/$ORDER_ID/action" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"call","params":{"action_code":"request_price"},"id":1}')
ALREADY2=$(echo "$REQ2" | python3 -c "import json,sys;r=json.load(sys.stdin)['result'];print(r.get('already_submitted'))")
assert "second submit returns already_submitted=True" "$ALREADY2" "True"

# Order payload timeline — save response to a file first so a
# transient session/cookie issue produces a debuggable artifact
# rather than vanishing into a Python KeyError.
$CURL_BASE -c "$CJ" -b "$CJ" -X POST "$H/southbrook/api/order/$ORDER_ID" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"call","params":{},"id":1}' > /tmp/sm_payload.json
HAS_RESULT=$(python3 -c "import json;d=json.load(open('/tmp/sm_payload.json'));print('result' in d)")
if [ "$HAS_RESULT" = "True" ]; then
    CREATED=$(python3 -c "import json;d=json.load(open('/tmp/sm_payload.json'));print(bool(d['result']['order']['created_date']))")
    SUBMITTED=$(python3 -c "import json;d=json.load(open('/tmp/sm_payload.json'));print(bool(d['result']['order']['submitted_date']))")
    assert "payload.created_date present" "$CREATED" "True"
    assert "payload.submitted_date present after submit" "$SUBMITTED" "True"
else
    FAIL=$((FAIL + 1))
    FAILS+=("/api/order payload returned no 'result' key — see /tmp/sm_payload.json")
    printf '  ✗ %-60s  (see /tmp/sm_payload.json)\n' "payload fetch returned no result"
fi

# ----------------------------------------------------------------------
# Bundle delivery (JS + CSS reach the order-builder page)
# ----------------------------------------------------------------------
echo
echo "[bundles] JS + CSS assets"
JS=$(grep -oE '/web/assets/[^"]+frontend_lazy\.min\.js' /tmp/sm_ob.html | head -1)
CSS=$(grep -oE '/web/assets/[^"]+frontend\.min\.css' /tmp/sm_ob.html | head -1)
$CURL_BASE "$H$JS" > /tmp/sm_bundle.js
$CURL_BASE "$H$CSS" > /tmp/sm_bundle.css
JS_SIZE=$(wc -c < /tmp/sm_bundle.js)
CSS_SIZE=$(wc -c < /tmp/sm_bundle.css)
assert "JS lazy bundle > 4 MB" "$([ "$JS_SIZE" -gt 4000000 ] && echo "True" || echo "False")" "True"
assert "CSS bundle > 500 KB" "$([ "$CSS_SIZE" -gt 500000 ] && echo "True" || echo "False")" "True"
# Bundle assertions go through file paths (assert_in_file) — piping
# multi-MB strings into grep produces broken-pipe errors.
assert_in_file "CatalogPicker in JS" /tmp/sm_bundle.js "CatalogPicker"
assert_in_file "_onPickCabinet in JS" /tmp/sm_bundle.js "_onPickCabinet"
assert_in_file "_loadAttributes in JS" /tmp/sm_bundle.js "_loadAttributes"
assert_in_file "_stages getter in JS" /tmp/sm_bundle.js "_stages"
assert_in_file "Designing label in JS" /tmp/sm_bundle.js "Designing"
assert_in_file "o_sb_hero in CSS" /tmp/sm_bundle.css "o_sb_hero"
assert_in_file "o_sb_auth_brand in CSS" /tmp/sm_bundle.css "o_sb_auth_brand"
assert_in_file "o_owl_catalog_tile in CSS" /tmp/sm_bundle.css "o_owl_catalog_tile"
assert_in_file "o_owl_attr_picker_grid in CSS" /tmp/sm_bundle.css "o_owl_attr_picker_grid"
assert_in_file "o_owl_stage_date in CSS" /tmp/sm_bundle.css "o_owl_stage_date"
# QWeb chain sanity: <CatalogPicker> must appear AFTER the first
# 'o_owl_loaded' occurrence in the bundle. This catches the
# regression where CatalogPicker sat between t-elif and t-else
# (bug 1b598bb hotfix).
LOADED_POS=$(grep -boE 'o_owl_loaded' /tmp/sm_bundle.js | head -1 | cut -d: -f1)
CATALOG_TAG_POS=$(grep -boE '<CatalogPicker' /tmp/sm_bundle.js | head -1 | cut -d: -f1)
if [ -n "$LOADED_POS" ] && [ -n "$CATALOG_TAG_POS" ] && [ "$CATALOG_TAG_POS" -gt "$LOADED_POS" ]; then
    PASS=$((PASS + 1))
    printf '  ✓ %-60s\n' "<CatalogPicker> sits inside loaded branch"
else
    FAIL=$((FAIL + 1))
    FAILS+=("CatalogPicker position regression: loaded@$LOADED_POS, tag@$CATALOG_TAG_POS")
    printf '  ✗ %-60s\n' "<CatalogPicker> position regression"
fi
rm -f /tmp/sm_bundle.js /tmp/sm_bundle.css

# ----------------------------------------------------------------------
# Final report
# ----------------------------------------------------------------------
echo
echo "================================================================"
echo " Summary: $PASS passed · $FAIL failed"
echo "================================================================"
if [ $FAIL -gt 0 ]; then
    printf '\nFailures:\n'
    for f in "${FAILS[@]}"; do printf '  - %s\n' "$f"; done
    exit 1
fi
exit 0
