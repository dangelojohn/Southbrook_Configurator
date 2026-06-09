# Southbrook audit Phase 2 — Playwright E2E

Headless-browser smoke tests that drive the **live** QNAP configurator at
`192.168.68.108:9443` (Caddy vhost: `southbrookcabinetry.local` /
`southbrookcabinetry.space`) and verify the post-audit UX is intact:

- Login lands on the backend
- Opening a Q8 cabinet's configurator wizard shows the 4 audit step
  buckets (Construction & Sizing / Door & Finish / Hardware & Sides /
  Interior & Accessories)
- Soft-Close appears as a pre-selected default

These tests complement the Python `test_audit_phase2.py` suite — those
verify schema and rule cardinality; these verify the wizard renders
those rules correctly.

## Setup

```sh
npm install
npx playwright install chromium
```

## Run

The QNAP cert is self-signed and the `southbrookcabinetry.space`
hostname resolves to the Cloudflare tunnel from the public internet —
neither suits a LAN test run. The Playwright config sets a
`--host-resolver-rules` map so Chromium routes that hostname to the
QNAP IP, and `ignoreHTTPSErrors:true` accepts the self-signed cert.

Set the admin password (don't commit it):

```sh
export SB_ADMIN_LOGIN=admin
export SB_ADMIN_PASSWORD='<your admin password>'
# Optional: override base URL or QNAP IP if not on the default LAN.
# export SB_BASE_URL=https://southbrookcabinetry.space:9443
npm test
```

Or one-shot:

```sh
SB_ADMIN_PASSWORD='…' npm test
```

The HTML report opens with:

```sh
npm run report
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Access Denied` from `/web/session/authenticate` | wrong admin password | set `SB_ADMIN_PASSWORD` |
| `Database not found.` | wrong vhost hostname or dbfilter mismatch | the config maps `southbrookcabinetry.space` to the QNAP IP via `--host-resolver-rules`; if Caddy's vhost is `.local`, pass `SB_BASE_URL=https://southbrookcabinetry.local:9443` AND adjust the resolver rule |
| `ETIMEDOUT 172.64.80.1:9443` | Node DNS resolved to Cloudflare tunnel | the spec uses `page.evaluate(fetch)` for all RPCs so the resolution goes through Chromium (which respects `--host-resolver-rules`) — should not hit anymore; if you see it, an `apiRequestContext.post` slipped back in |
| Login form not found | `quick_login:true` keeps `oe_login_form` `d-none` until JS toggle | the spec removes `d-none` via `evaluate` before filling — already handled |
| Slow first run | live QNAP module registry takes ~2 min to load on a cold container | wait it out, or pre-warm with one `curl /web/login` before `npm test` |

## What's deliberately out of scope

- 3D viewport rendering (Three.js can't be asserted without screenshot
  pixel diff; revisit when there's a reference image)
- Mobile breakpoint (Playwright's Mobile Chrome project — easy to add
  if needed)
- Live price-update animation (would need a longer pick-a-value flow)
- The customer `/kitchen-planner` flow (separate from the backend
  wizard; would need its own login as a portal user)
