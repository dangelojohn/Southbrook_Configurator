---
course: 17
chapter: 17.12
title: Design — Manually Re-render a Cabinet via FreeCAD
duration: 2
audience: Designer / ECO engineer who needs to refresh a specific MO render
jtbd: manually re-render a cabinet via freecad
department: Design / Engineering
custom_modules: southbrook_freecad_bridge
---

# Design — Manually Re-render a Cabinet via FreeCAD

## When you use this

You updated the master template, a customer ECO changed dimensions, or the
auto-render failed and shipped a stale image to the spec sheet. Use this to
force a fresh render.

## Where to fire it

The MO form (`mrp.production`) — *Cog menu → Re-render via FreeCAD*.

You can also fire from the SO chatter once the MO exists; the button is on
the SO header dropdown under *Actions → Re-render Spec Visuals*.

## What happens

1. The MO posts a job to `services/freecad_bridge/` via the API key from
   the bridge-svc credential.
2. The bridge container spins up a headless FreeCAD process, loads the
   master FCStd, applies the parameter map for THIS cabinet's
   configurator selections, and renders.
3. PDF + STEP + screenshots come back; old `ir.attachment` records are
   archived (not deleted) and new ones attach to the MO.
4. The MO chatter logs the round-trip time.

## Round-trip time

Normal: **~8 seconds** end-to-end (see
`southbrook_freecad_bridge_deploy_recipe.md`). If it's >30 seconds,
investigate:

- Master file bloat (lesson 17.11 gotcha #3)
- Bridge container under load (`docker stats southbrook-freecad-bridge`)
- Network round-trip to the bridge over the internal docker net

## If it 404s

- API key rotation: bridge-svc credential may have changed; check
  `southbrook_freecad_bridge.config_parameter` for the current key
- Bridge container down: `docker ps` should show it healthy
- RO mount missing: the master file binding broke; recipe step 1

## Common gotchas

- **Re-render makes the OLD image still shows on the PDF** — Odoo caches
  attachments aggressively. Clear the QWeb cache: `docker exec
  southbrook-odoo bash -c "rm -rf /var/lib/odoo/.local/share/Odoo/sessions/*"`
  or just hard-refresh the print preview.
- **Re-rendered image has a "rendering pending" placeholder** — the v1
  fallback. Bridge job took too long; retry.

## Deep dive

→ Course 4 lesson 4.3 *FreeCAD Bridge*
→ Memory `southbrook_freecad_bridge_deploy_recipe.md`
