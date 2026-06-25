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

## Status: deployed live 2026-06-25 under `http://southbrookcabinetry.local/wall/shipping`

The kiosk is wired into the existing `(southbrook_routes)` snippet in
alfacore-caddy's Caddyfile (not a new site block). Routes live under
the existing LAN-only `southbrookcabinetry.local:80` site that already
serves `/app/`, `/git/`, `/mcp/`, etc.

For a customer-visible public hostname (`display.southbrookcabinetry.space`)
you'd need separate DNS + Cloudflare-Access setup — that's stakeholder
territory per `[[feedback_no_network_or_router_changes]]`.

## Activation (first install — what actually works)

1. **Drop the HTML on the QNAP alfacore-caddy data volume:**
   ```
   ssh qnap-tunnel 'mkdir -p /share/CACHEDEV3_DATA/.qpkg/container-station/system-docker/volumes/odoo_caddy-data/_data/southbrook-wall/shipping'
   scp services/southbrook_wall/wall/shipping/index.html \
     qnap-tunnel:/share/CACHEDEV3_DATA/.qpkg/container-station/system-docker/volumes/odoo_caddy-data/_data/southbrook-wall/shipping/index.html
   ```
   Caddy sees this at `/data/southbrook-wall/shipping/index.html`.

2. **Inject the wall routes into `(southbrook_routes)` snippet** at
   `/share/CACHEDEV3_DATA/Container/odoo/config/Caddyfile`. **Edit
   on the local side and `scp` up — BusyBox awk chokes on regex
   escapes (`\(`, `\)`, `\{`).** See `caddy_snippet.example` for the
   canonical block. Backup first:
   ```
   ssh qnap-tunnel 'cp /share/CACHEDEV3_DATA/Container/odoo/config/Caddyfile{,.bak-pre-wall-$(date +%Y%m%d-%H%M%S)}'
   scp qnap-tunnel:/share/CACHEDEV3_DATA/Container/odoo/config/Caddyfile /tmp/Caddyfile.live
   # edit /tmp/Caddyfile.live to inject the wall block right before
   # the existing `@longpoll path /longpolling/* /websocket` line
   # WITHIN the (southbrook_routes) snippet (NOT the (odoo_routes)
   # snippet — they look similar, the marker is `southbrook-odoo:8069`
   # vs `odoo:8069`).
   scp /tmp/Caddyfile.live qnap-tunnel:/share/CACHEDEV3_DATA/Container/odoo/config/Caddyfile
   ```
   Per `[[qnap_caddyfile_bind_mount_trap]]`, the destination MUST be
   the same file (scp overwrites in place, preserving the inode). Do
   NOT `mv` a renamed file onto the destination.

3. **Validate + force-restart Caddy** — per
   `[[caddy_v2_routing_gotchas]]`, `caddy reload` sometimes silently
   no-ops on Caddyfile changes on this stack. A `docker restart` is
   the cure:
   ```
   ssh qnap-tunnel 'export DOCKER_HOST=unix:///var/run/system-docker.sock; \
     export PATH=/share/CACHEDEV3_DATA/.qpkg/container-station/bin:$PATH; \
     docker exec alfacore-caddy caddy validate --config /etc/caddy/Caddyfile && \
     docker restart alfacore-caddy'
   ```
   The restart takes ~52s. Try `caddy reload` first if you want
   zero downtime; only escalate to `restart` if the new behavior
   doesn't take effect.

4. **Confirm the feed responds:**
   ```
   ssh qnap-tunnel 'docker exec alfacore-caddy curl -sS \
     -H "Host: southbrookcabinetry.local" \
     http://localhost/wall/api/shipping.json | head -c 200'
   ```
   Should return a JSON envelope with `schema_version: 1`, `station:
   "shipping"`, `payload.kpis`, `payload.rows`.

5. **Open the kiosk** from any device on the LAN:
   `http://southbrookcabinetry.local/wall/shipping`

## Critical gotchas discovered during the 2026-06-25 wire-up

- **Named matcher does NOT strip the prefix.** `@wall_api path /wall/api/*`
  + `handle @wall_api { rewrite * /southbrook/wall{path} ... }` produces
  `/southbrook/wall/wall/api/shipping.json` (double `wall`). Use
  `handle_path /wall/api/*` directly when you want the prefix stripped.
  See `[[caddy_v2_routing_gotchas]]` §1.

- **There are TWO snippets** that both contain `@longpoll path
  /longpolling/* /websocket`: `(odoo_routes)` proxies to plain
  `odoo:8069` (alfacore), `(southbrook_routes)` proxies to
  `southbrook-odoo:8069`. A regex insertion at the first match lands
  in the WRONG snippet. Inject into the right one — the marker is
  `southbrook-odoo` (with hyphen) within the catchall handler.

- **`caddy reload` can silently no-op** on this bind-mounted Caddyfile.
  Symptoms: behavior doesn't match what `caddy adapt --config
  /etc/caddy/Caddyfile | grep '"path":\[.*/wall.*]'` says is in the
  parsed config. Cure: `docker restart alfacore-caddy`. Full writeup
  in `[[caddy_v2_routing_gotchas]]` §2.

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
