#!/usr/bin/env bash
# Rec D Sprint 2d tripwire — verifies the backend asset bundle
# actually compiles + contains the expected extraction markers.
# Runs *after* deploy_to_qnap.sh to catch the specific WebClient
# mount-hang signature that broke at 4.20.0 + 4.23.0 (registry
# loads clean, /web/login 200, no log errors — but the bundle
# build silently fails on first authenticated hit).
#
# Usage:
#   ./scripts/rec_d_sprint2d_tripwire.sh          # default markers
#   ./scripts/rec_d_sprint2d_tripwire.sh makeMesh computeViewSpecs
#
# Exit codes:
#   0 = tripwire passed — bundle compiles and every marker is present
#   2 = bundle build raised in odoo shell (SCSS/JS error)
#   3 = a required marker is MISSING from the compiled bundle
#   4 = bundle suspiciously small (<500KB — likely truncated)
set -euo pipefail

QNAP_HOST="${QNAP_HOST:-admin@ssh.odooiq.com}"
QNAP_DOCKER="${QNAP_DOCKER:-/share/CACHEDEV3_DATA/.qpkg/container-station/bin/system-docker}"
CONTAINER="${CONTAINER:-southbrook-odoo}"
DB="${DB:-southbrook}"

# Default markers if none passed — every Sprint 2d step's public
# export gets added here so future steps' extractions self-verify.
if [[ $# -eq 0 ]]; then
  MARKERS=(
    "loadThreeJS" "ndcFromEvent"
    "computeViewSpecs" "makeMesh"
    "packRow" "easeInOutCubic" "computeOrthoFrustum"
    "southbrook_kitchen_configurator"
  )
else
  MARKERS=("$@")
fi

# Serialize markers as a Python list literal for the shell script.
MARKERS_PY="["
for m in "${MARKERS[@]}"; do MARKERS_PY+="\"$m\","; done
MARKERS_PY+="]"

# Pipe the Python script directly through SSH → docker-exec-stdin →
# odoo shell stdin. No intermediate files, no chmod dance.
out=$(ssh "$QNAP_HOST" \
  "$QNAP_DOCKER exec -i $CONTAINER odoo shell -c /etc/odoo/odoo.conf -d $DB --no-http --stop-after-init 2>&1" <<PYEOF
import sys, traceback
try:
    env['ir.attachment'].sudo().search([
        ('url', '=like', '/web/assets/%web.assets_backend%'),
    ]).unlink()
    env.cr.commit()
    bundle = env['ir.qweb']._get_asset_bundle(
        'web.assets_backend', debug_assets=False)
    js_attach = bundle.js()
    env.cr.commit()
    att = env['ir.attachment'].sudo().browse(js_attach.id)
    blob = (att.raw or b'').decode('utf-8', 'replace')
    print('BUNDLE_SIZE:%d' % len(blob))
    for m in ${MARKERS_PY}:
        print('MARKER:%s:%s' % (m, 'FOUND' if m in blob else 'MISSING'))
    print('TRIPWIRE_OK')
except Exception:
    traceback.print_exc()
    print('TRIPWIRE_FAIL')
    sys.exit(2)
PYEOF
)

# Print only the relevant marker/status lines.
echo "$out" | grep -E 'BUNDLE_SIZE|MARKER|TRIPWIRE_|Traceback|Error' || true

# Gate decisions.
grep -q 'TRIPWIRE_OK' <<< "$out" || { echo "[tripwire] BUILD FAILED"; exit 2; }
if grep -q 'MARKER:.*:MISSING' <<< "$out"; then
  echo "[tripwire] EXTRACTION MISSING — one or more markers absent from the bundle"
  exit 3
fi
size=$(grep -oE 'BUNDLE_SIZE:[0-9]+' <<< "$out" | head -1 | cut -d: -f2)
if [[ -z "$size" || "$size" -lt 500000 ]]; then
  echo "[tripwire] bundle suspiciously small ($size bytes)"
  exit 4
fi
echo "[tripwire] OK — bundle $size bytes, all ${#MARKERS[@]} markers found"
