#!/usr/bin/env bash
# Verify the Southbrook Configurator UX Onshape CAD link feature.
#
# Usage:
#   ./scripts/verify_onshape_cad_link.sh
#   STATIC_ONLY=1 ./scripts/verify_onshape_cad_link.sh
#
# Environment:
#   DB=southbrook
#   CONTAINER=sami-odoo
#   STATIC_ONLY=0

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DB="${DB:-southbrook}"
CONTAINER="${CONTAINER:-sami-odoo}"
STATIC_ONLY="${STATIC_ONLY:-0}"

log() { printf "[onshape-verify] %s\n" "$*" >&2; }
fail() { printf "[onshape-verify] ERROR: %s\n" "$*" >&2; exit 1; }

required_files=(
  "addons/southbrook_configurator_ux/models/product_template.py"
  "addons/southbrook_configurator_ux/views/product_template_views.xml"
  "addons/southbrook_configurator_ux/views/website_configurator_onshape.xml"
  "addons/southbrook_configurator_ux/tests/test_onshape_cad_url.py"
)

for file in "${required_files[@]}"; do
  [[ -f "$file" ]] || fail "missing required file: $file"
done

log "checking manifest registration"
python3 - <<'PY'
import ast
from pathlib import Path

manifest = ast.literal_eval(Path("addons/southbrook_configurator_ux/__manifest__.py").read_text())
data = manifest["data"]
required = [
    "views/product_template_views.xml",
    "views/website_configurator_onshape.xml",
]
for item in required:
    if item not in data:
        raise SystemExit(f"manifest missing {item}")
print(f"manifest version: {manifest['version']}")
PY

log "checking XML well-formedness"
python3 - <<'PY'
import xml.etree.ElementTree as ET

for path in [
    "addons/southbrook_configurator_ux/views/product_template_views.xml",
    "addons/southbrook_configurator_ux/views/website_configurator_onshape.xml",
]:
    ET.parse(path)
    print(f"XML OK {path}")
PY

log "checking Onshape bootstrap JavaScript syntax"
python3 - <<'PY'
import xml.etree.ElementTree as ET
from pathlib import Path

tree = ET.parse("addons/southbrook_configurator_ux/views/website_configurator_onshape.xml")
script = tree.find(".//script")
if script is None or not script.text:
    raise SystemExit("Onshape website view has no inline bootstrap script")
Path("/tmp/southbrook_onshape_bootstrap.js").write_text(script.text)
PY
node --check /tmp/southbrook_onshape_bootstrap.js

log "checking Python syntax"
python3 -m py_compile \
  addons/southbrook_configurator_ux/__manifest__.py \
  addons/southbrook_configurator_ux/models/product_template.py \
  addons/southbrook_configurator_ux/tests/test_onshape_cad_url.py

log "checking for Onshape credential-shaped strings in addon"
if rg -n "X-Goog-Api-Key|Api-Key\\s*:|API_KEY\\s*=|AQ\\." addons/southbrook_configurator_ux; then
  fail "possible secret/API credential string found"
fi

if [[ "$STATIC_ONLY" == "1" ]]; then
  log "STATIC_ONLY=1, skipping Docker/Odoo runtime checks"
  exit 0
fi

command -v docker >/dev/null || fail "docker not found; rerun with STATIC_ONLY=1 for static checks only"
docker info >/dev/null || fail "docker daemon unavailable; start OrbStack/Docker or rerun with STATIC_ONLY=1"

log "running Odoo module upgrade"
docker exec "$CONTAINER" odoo \
  -d "$DB" \
  -u southbrook_configurator_ux \
  --stop-after-init \
  --no-http

log "running tagged Odoo tests"
docker exec "$CONTAINER" odoo \
  -d "$DB" \
  -u southbrook_configurator_ux \
  --test-enable \
  --test-tags=southbrook,onshape \
  --stop-after-init \
  --no-http

log "runtime checks complete"
