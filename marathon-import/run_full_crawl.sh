#!/usr/bin/env bash
# Full Marathon-catalogue crawl via headed Chrome.
# Marathon's Cloudflare challenges headless browsers; the crawler's own
# help says use headed mode. Run this from a terminal session that has
# a desktop / display attached. Chromium will open visibly and close
# itself after each category.
#
# Per-category outputs land beside this script so the next ingest pass
# in southbrook_hardware_catalog can pick them up.
set -euo pipefail

OUT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER="$HOME/marathon_crawler/run_crawler.py"

if [[ ! -f "$RUNNER" ]]; then
  echo "marathon_crawler not found at $RUNNER" >&2
  exit 1
fi

# Marathon's published top-level categories, harvested from the
# homepage HTML during the Tier 2.2 brand audit (2026-06-10).
declare -A CATS=(
  [knobs]="https://marathonhardware.com/cat/Knobs/302591"
  [pulls]="https://marathonhardware.com/cat/Pulls/302592"
  [appliance_pulls]="https://marathonhardware.com/cat/Appliance-Pulls/1824225"
  [dtc_hinges]="https://marathonhardware.com/cat/DTC-Hinges/302730"
  [salice_hinges]="https://marathonhardware.com/cat/Salice-Hinges/302742"
  [other_hinges]="https://marathonhardware.com/cat/Other-Hinges/302795"
  [hinge_accessories]="https://marathonhardware.com/cat/Hinge-Accessories/302780"
  [undermount_slides]="https://marathonhardware.com/cat/Undermount-Slides/302721"
  [ball_bearing_slides]="https://marathonhardware.com/cat/Ball-Bearing-Slides/302719"
  [bottom_mount_slides]="https://marathonhardware.com/cat/Bottom-Mount-Slides/302720"
)

for key in "${!CATS[@]}"; do
  url="${CATS[$key]}"
  out="$OUT_DIR/marathon_${key}.json"
  csv="$OUT_DIR/marathon_${key}.csv"
  echo "[+] crawling $key -> $url"
  python3 "$RUNNER" \
    --browser chrome \
    --category-url "$url" \
    --delay 2 \
    --output "$out" \
    --csv "$csv" \
    || echo "[!] $key failed — continuing"
done

echo "[done] outputs in $OUT_DIR"
ls -la "$OUT_DIR"
