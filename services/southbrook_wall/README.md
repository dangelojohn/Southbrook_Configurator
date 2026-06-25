# Southbrook Wall — 1-day proof-of-concept

Vanilla-web kiosk surface, served by `alfacore-caddy`, fed by Odoo
controllers in `southbrook_premium_orchestration`. Implements the
"build `/wall/shipping` in a single day" recipe from
[`~/Downloads/southbrook_kiosk_dashboard_spec.md`](../../docs/) §11.

## What's here

```
services/southbrook_wall/
├── README.md                ← this file
├── caddy_snippet.example    ← Caddyfile snippet for alfacore-caddy
└── wall/
    └── shipping/
        └── index.html       ← responsive single-file kiosk
```

The Odoo side (JSON feed controller) lives in:
- `addons/southbrook_premium_orchestration/controllers/wall.py`

The kiosk reads `/wall/api/shipping.json` (proxied by Caddy to
Odoo's `/southbrook/wall/shipping.json`), with a fallback to
`/wall/static/shipping.json` for when Odoo is mid-restart.

## Activation (first install)

1. **Rsync the HTML to the Caddy data volume on the QNAP:**
   ```
   rsync -av services/southbrook_wall/wall/ \
     admin@ssh.southbrookcabinetry.space:/share/CACHEDEV3_DATA/Container/alfacore/data/southbrook-wall/
   ```
   (Adjust the destination path to where alfacore-caddy's volume is
   actually bind-mounted. The compose file in the alfacore stack
   has the canonical path.)

2. **Wire the Caddy snippet** — copy the contents of
   `caddy_snippet.example` into alfacore-caddy's Caddyfile under
   the `display.southbrookcabinetry.space` site block (or wherever
   you want the URL to live).

3. **Reload Caddy in-place** — per `[[qnap_caddyfile_bind_mount_trap]]`,
   use `cp` to overwrite the Caddyfile, never `mv`:
   ```
   docker exec alfacore-caddy caddy reload --config /etc/caddy/Caddyfile
   ```

4. **Confirm the feed responds:**
   ```
   curl http://display.southbrookcabinetry.space/wall/api/shipping.json | jq .
   ```
   Should return a JSON envelope with `schema_version: 1`, `station:
   "shipping"`, `payload.kpis`, `payload.rows`.

5. **Open the kiosk:** `http://display.southbrookcabinetry.space/wall/shipping`
   on a phone or browser. Should render a dark table with KPIs and
   the active shipping rows. "Updated Xs ago" stamp top-right;
   auto-refresh every 30s.

## Open decisions before production

Per spec §7 (20 weak points), the following need stakeholder input
BEFORE pointing this at a customer-visible URL:

1. **IP allowlist scope (§7.8)** — currently the JSON feed is
   `auth='public'`. Anyone who can reach the hostname can read SO
   numbers + customer names. Add a Caddy IP allowlist OR Cloudflare
   Access policy before exposing publicly.

2. **Privacy redaction tier (§7.9)** — order content, addresses,
   value: which fields are OK to render on a dock TV visible to
   walk-in visitors? Default this POC includes customer NAME but
   NOT address, value, or item details.

3. **Carrier integration state (§7.1)** — `carrier_id.name` +
   `carrier_tracking_ref` are read from the standard `delivery`
   module fields. If Southbrook uses a TMS (Shippo, EasyPost,
   Project44, etc.), the rows can carry richer ETA / status data.

4. **Static fallback population** — the `/wall/static/` path
   expects a cron-dropped JSON snapshot. POC doesn't ship that
   cron — the fallback layer is empty until you wire it up. The
   kiosk JS handles the empty case gracefully (renders "DATA STALE"
   banner if neither layer responds).

## Adding another station

The pattern from spec §3 is per-station URLs. To add `/wall/receiving`:

1. Add a `_build_receiving()` method to
   `addons/southbrook_premium_orchestration/controllers/wall.py`
   and register it in the `builders` dict.
2. Add a `wall/receiving/index.html` here (or `cp -r shipping/
   receiving/` and tweak the table columns for inbound — see spec
   §3.5 for the column layout).
3. Add the Caddy `handle_path /wall/receiving*` route to
   `caddy_snippet.example`.
4. Reload Caddy.

No Odoo addon upgrade required — controllers reload with `-u
southbrook_premium_orchestration`, which also reloads the addon's
view/menu changes if any.

## What's INTENTIONALLY not in this POC

Per spec phasing (§6 build sequence — weeks 1-4):
- Static fallback cron (week 1-2)
- Service Worker / offline cache (week 2)
- Scanner integration (week 2)
- Handheld auth + QR pairing (week 3)
- Push notifications (week 3)
- SVG dock-door floor plan (week 4)
- Per-carrier color persistence (week 4)
- Print manifest via QWeb (week 4)
- Receiving, Cut, Assembly, Install, Manager, Shift-Change kiosks
  (week 1-4 progressively)

Each lands as a separate commit. The POC validates the architecture
(vanilla web + Caddy snippet + Odoo controller + dual-layer feed)
before committing to the broader build.
