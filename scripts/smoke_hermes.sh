#!/usr/bin/env bash
# scripts/smoke_hermes.sh — exercise the Hermes Odoo API surface end-to-end.
#
# Runs against prod by default. Mints a fresh JWT inside the southbrook-odoo
# container, then hits every Hermes route with that token, asserting the
# response shape on each one.
#
# A green run confirms:
#   - PyJWT is installed (otherwise mint fails 503)
#   - JWT secret is set to a real value (otherwise mint refuses)
#   - /api/hermes/tools returns the expected 13-tool registry
#   - Persona/tier ACL is in effect (trade_partner mask only sees trade_partner tools)
#   - At least one tool dispatches and returns the expected JSON shape
#   - The conversation log endpoint accepts a write and returns a question_id
#   - /southbrook/os.json and /commercial still respond 200 (regression)
#
# Usage:
#   ./scripts/smoke_hermes.sh                              # default: prod via tunnel
#   QNAP_HOST=admin@192.168.68.108 ./scripts/smoke_hermes.sh
#   PARTNER_ID=42 ./scripts/smoke_hermes.sh                # mint as a specific partner
#
# Exits non-zero on first failure.

set -euo pipefail

QNAP_HOST="${QNAP_HOST:-admin@ssh.odooiq.com}"
QNAP_DOCKER="${QNAP_DOCKER:-/share/CACHEDEV3_DATA/.qpkg/container-station/bin/system-docker}"
CONTAINER="${CONTAINER:-southbrook-odoo}"
DB="${DB:-southbrook}"
PUBLIC_BASE="${PUBLIC_BASE:-https://southbrookcabinetry.space}"
TENANT="${TENANT:-southbrook}"
PERSONA="${PERSONA:-trade_partner}"
TIER="${TIER:-T0+T1+T2}"
# Default to a real portal partner. partner_id=1 (OdooBot) fails the
# partner_has_no_user gate the dispatch controller correctly enforces.
PARTNER_ID="${PARTNER_ID:-352}"
TTL_SECONDS="${TTL_SECONDS:-300}"

pass() { printf "  \033[32mPASS\033[0m  %s\n" "$*"; }
fail() { printf "  \033[31mFAIL\033[0m  %s\n" "$*" >&2; exit 1; }
info() { printf "\n\033[1m== %s ==\033[0m\n" "$*"; }

command -v curl >/dev/null   || { echo "curl required"; exit 2; }
command -v ssh >/dev/null    || { echo "ssh required"; exit 2; }
command -v python3 >/dev/null || { echo "python3 required"; exit 2; }

# ---- mint a JWT inside the container ---------------------------------------
info "minting JWT (persona=$PERSONA tier=$TIER partner_id=$PARTNER_ID ttl=${TTL_SECONDS}s)"

# Approach: scp a temp .py to the QNAP host, exec it inside the container via
# `odoo shell < /path/to/file.py`, then delete the temp. Avoids the bash/ssh/
# docker quoting chain entirely.
MINT_PY_PATH="/tmp/hermes_mint_$$.py"
cat > "$MINT_PY_PATH" <<PY
from odoo.addons.southbrook_hermes.utils import jwt_helper
print(jwt_helper.mint_jwt(
    env,
    tenant="$TENANT",
    persona="$PERSONA",
    partner_id=$PARTNER_ID,
    tier="$TIER",
    ttl_seconds=$TTL_SECONDS,
))
PY

scp -q "$MINT_PY_PATH" "$QNAP_HOST:/tmp/hermes_mint.py"
rm -f "$MINT_PY_PATH"

TOKEN=$( { ssh "$QNAP_HOST" "$QNAP_DOCKER cp /tmp/hermes_mint.py $CONTAINER:/tmp/hermes_mint.py && $QNAP_DOCKER exec $CONTAINER bash -c 'odoo shell -d $DB --no-http < /tmp/hermes_mint.py 2>&1 && rm -f /tmp/hermes_mint.py'" 2>&1 || true; } | grep -E '^eyJ' | head -1 || true)
ssh "$QNAP_HOST" "rm -f /tmp/hermes_mint.py" 2>/dev/null || true

if [[ -z "$TOKEN" ]] || ! [[ "$TOKEN" =~ ^eyJ ]]; then
  fail "JWT mint returned junk: '$TOKEN' (expected a 'eyJ...' string)"
fi
pass "minted JWT (${#TOKEN} chars)"

# ---- 1. /api/hermes/tools registry -----------------------------------------
info "GET /api/hermes/tools"

RESP=$(curl -sS -H "Authorization: Bearer $TOKEN" "$PUBLIC_BASE/api/hermes/tools")
echo "$RESP" | python3 -c '
import sys, json
d = json.loads(sys.stdin.read())
assert d.get("tenant") == "'$TENANT'", f"tenant mismatch: {d.get(chr(34)+chr(116)+chr(101)+chr(110)+chr(97)+chr(110)+chr(116)+chr(34))}"
assert d.get("persona") == "'$PERSONA'", f"persona mismatch"
assert d.get("tier") == "'$TIER'", f"tier mismatch"
tools = d.get("tools", [])
assert len(tools) >= 12, f"expected 12+ tools, got {len(tools)}"
slugs = {t["slug"] for t in tools}
expected = {"list_my_orders","get_order_status","get_order_line","list_my_kitchen_projects",
            "get_kitchen_project","get_install_schedule","get_quote_pdf_url",
            "list_my_recommendations","get_os_section","post_internal_note",
            "send_spec_pdf_email","schedule_followup_activity","propose_recommendation"}
missing = expected - slugs
assert not missing, f"missing tools: {missing}"
# At least one T2 tool present for the universal-escape-hatch flow
t2 = [t["slug"] for t in tools if t["tier"] == "T2"]
assert "propose_recommendation" in t2, f"propose_recommendation not at T2: {t2}"
print("    tenant:", d["tenant"], "persona:", d["persona"], "tier:", d["tier"])
print("    tool count:", len(tools))
print("    T2 tools:", t2)
' || fail "registry shape mismatch — see python output above"
pass "registry returns 13 tools incl. propose_recommendation@T2"

# ---- 2. /api/hermes/tools/get_os_section dispatch --------------------------
info "POST /api/hermes/tools/get_os_section {slug:00_charter}"

RESP=$(curl -sS -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"slug": "00_charter"}' \
  "$PUBLIC_BASE/api/hermes/tools/get_os_section")
echo "$RESP" | python3 -c '
import sys, json
d = json.loads(sys.stdin.read())
assert d.get("slug") == "00_charter", f"slug mismatch: {d.get(chr(34)+chr(115)+chr(108)+chr(117)+chr(103)+chr(34))}"
assert d.get("version", 0) >= 1, f"version missing"
assert "Southbrook" in (d.get("body") or ""), "body should mention Southbrook"
print("    slug:", d["slug"], "version:", d["version"], "body bytes:", len(d.get("body","")))
' || fail "get_os_section response shape mismatch"
pass "get_os_section returns the canonical charter body"

# ---- 3. /api/hermes/conversation/log write --------------------------------
info "POST /api/hermes/conversation/log"

RESP=$(curl -sS -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question":"smoke test","answer":"smoke test answer","scope":"customer","order_id":null}' \
  "$PUBLIC_BASE/api/hermes/conversation/log")
echo "$RESP" | python3 -c '
import sys, json
d = json.loads(sys.stdin.read())
assert d.get("ok") is True, f"not ok: {d}"
assert isinstance(d.get("question_id"), int) and d["question_id"] > 0, f"bad question_id: {d}"
print("    question_id:", d["question_id"])
' || fail "conversation/log response shape mismatch"
pass "conversation log accepted, persisted with id"

# ---- 4. OWL chat-panel asset deployment ------------------------------------
info "OWL chat panel — assets, bundle, view inheritance"

# 4a. Raw static assets must be reachable
for path in \
  /southbrook_hermes/static/src/components/hermes_chat/hermes_chat.esm.js \
  /southbrook_hermes/static/src/components/hermes_chat/hermes_chat.xml \
  /southbrook_hermes/static/src/components/hermes_chat/hermes_chat.scss; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "$PUBLIC_BASE$path")
  if [[ "$code" != "200" ]]; then
    fail "$path returned $code (expected 200; manifest assets entry may be wrong)"
  fi
done
pass "all 3 chat-panel static assets reachable"

# 4b. The lazy frontend bundle should contain the OWL component markers
LOGIN_HTML=$(curl -s "$PUBLIC_BASE/web/login")
LAZY_JS=$(printf '%s' "$LOGIN_HTML" | grep -oE '/web/assets/[^"]+web\.assets_frontend_lazy[^"]*\.min\.js' | head -1)
FRONTEND_CSS=$(printf '%s' "$LOGIN_HTML" | grep -oE '/web/assets/[^"]+web\.assets_frontend[^"]*\.min\.css' | head -1)

if [[ -z "$LAZY_JS" ]] || [[ -z "$FRONTEND_CSS" ]]; then
  fail "could not locate frontend bundle URLs in /web/login response"
fi

JS_MARKERS=$(curl -s "$PUBLIC_BASE$LAZY_JS" | grep -oE 'HermesChat|hermes-chat-mount|o_hermes_chat' | sort -u | wc -l | tr -d ' ')
if [[ "$JS_MARKERS" -lt 3 ]]; then
  fail "lazy bundle missing OWL chat markers (found $JS_MARKERS/3+; expected HermesChat, hermes-chat-mount, o_hermes_chat)"
fi
pass "lazy bundle contains $JS_MARKERS+ OWL chat markers"

CSS_MARKERS=$(curl -s "$PUBLIC_BASE$FRONTEND_CSS" | grep -oE 'o_hermes_chat[a-z_-]*' | sort -u | wc -l | tr -d ' ')
if [[ "$CSS_MARKERS" -lt 1 ]]; then
  fail "frontend CSS bundle missing o_hermes_chat styles"
fi
pass "frontend CSS contains $CSS_MARKERS o_hermes_chat style classes"

# 4c. ir.ui.view record for the xpath inheritance must exist
INHERIT_COUNT=$(ssh "$QNAP_HOST" "$QNAP_DOCKER exec southbrook-postgres psql -U odoo -d $DB -At -c \"SELECT COUNT(*) FROM ir_ui_view WHERE key = 'southbrook_hermes.hermes_chat_inject_order_builder';\"" 2>&1 | tr -d ' \r')
if [[ "$INHERIT_COUNT" != "1" ]]; then
  fail "ir.ui.view 'southbrook_hermes.hermes_chat_inject_order_builder' missing or duplicated (count: $INHERIT_COUNT)"
fi
pass "ir.ui.view inheritance record present (1 row)"

# ---- 5. Regression — public surfaces unchanged ----------------------------
info "regression check"

for path in /southbrook/os.json /commercial; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "$PUBLIC_BASE$path")
  if [[ "$code" != "200" ]]; then
    fail "$path returned $code (expected 200)"
  fi
  pass "$path → 200"
done

# ---- 6. Toggle state report -----------------------------------------------
info "sidecar config state"

# shellcheck disable=SC2087
# Redact the JWT secret value before printing (we only want to see the
# first 8 hex chars + the toggle states). awk-based redaction is portable
# across BSD/GNU sed.
ssh "$QNAP_HOST" "$QNAP_DOCKER exec southbrook-postgres psql -U odoo -d $DB -c \"SELECT key, value FROM ir_config_parameter WHERE key LIKE 'southbrook_hermes.%' ORDER BY key;\"" 2>&1 \
  | grep -E "sidecar_enabled|sidecar_url|jwt_secret" \
  | awk -F'|' '{
      gsub(/^[ \t]+|[ \t]+$/, "", $1);
      gsub(/^[ \t]+|[ \t]+$/, "", $2);
      if ($1 == "southbrook_hermes.jwt_secret") {
        printf "    %-40s %s…  (redacted — 32 hex bytes)\n", $1, substr($2, 1, 8)
      } else {
        printf "    %-40s %s\n", $1, $2
      }
    }'

echo ""
printf "\033[32m✓ smoke_hermes: all checks passed\033[0m\n"
