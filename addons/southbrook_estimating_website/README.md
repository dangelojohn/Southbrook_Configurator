# Southbrook Estimating — Website

The customer-facing one-page kitchen configurator at
`/kitchen-planner` on `southbrookcabinetry.space`.

This addon adds the Three.js + 2D-fallback planner layer on top of
the OCA `website_product_configurator` route engine. The Order
Builder backend lives in the companion `southbrook_estimating`
addon; both share one configurator engine + one data model
(per `CLAUDE.md` §2.3 — there must not be two configurators).

## Status

**Track 2 commit 1 — scaffold (2026-05-30).** Portal route resolves,
auth + breadcrumb + sidebar render. The OWL `<OrderBuilder/>`
component tree mounts in commit 2+. See
`docs/PHASE_2_CHARTER.md` amendment 1 for the strategic pivot
that reshaped this addon from "customer-facing kitchen-planner"
to "dealer + customer Order Builder portal".

- Charter (May 2026) chose Option C: SPA-primary + backend escape
  hatch. This addon hosts the SPA; `southbrook_estimating` stays
  as the backend Order Builder (power-user fallback).
- The customer-mode TOGGLE on `<OrderBuilder/>` replaces the older
  `/kitchen-planner` plan — same component, different visibility
  per Build Spec §2.3 ("There must not be two configurators").
- The Phase-3 Three.js viewport now lives in
  `southbrook_estimating`'s Track 1 commits 1-10 (mounted in the
  backend); Track 2 Phase 2.5 back-ports it into this portal.

## Dependencies

- `southbrook_estimating` — the engine (this addon's reason to exist)
- `website_product_configurator` — OCA module providing the route base
- `portal` — for `/my/estimates` (saved sessions per customer)

## Why two addons, not one

`southbrook_estimating` is the data + backend + rules — it can run
without the website addon for the sales-rep persona (useful for
integration testing and dealer-terminal-only deployments).
`southbrook_estimating_website` is the public Three.js layer —
independently deployable, has its own asset bundle, doesn't bloat
backend load.

See `../../CLAUDE.md` §3 for the full rationale.

## Canonical design docs

| Doc | What it answers |
|---|---|
| `../../docs/PHASE_2_CHARTER.md` | Why this addon is now an OWL portal SPA, not a kitchen-planner route |
| `../../docs/southbrook_owl_mockup.html` | The Phase-2 build target — full OWL component tree |
| `../../CLAUDE.md` | Original operating brief — superseded for Track 2 scope by the charter |
| `../../docs/PRODBOARD_MANIFEST.md` | §3, §5, §9, §11 — Three.js scene targets (Phase 2.5+) |
| `../../docs/SAMI_Southbrook_Odoo19_Build_Spec.md` | §2.4 + §7 (Phase 3) — Prodboard-class layer scoping |

## Route

```
/my/southbrook/order-builder
/my/southbrook/order-builder/<int:order_id>
```

Both forms render the OWL mount-point page. Auth: portal user;
`partner_id.parent_id` chain identifies the dealer / customer
relationship.

## Track 2 commit lineup

1. ✅ Scaffold — manifest, controller, portal template, ACL, README
2. Empty OWL mount point — `<OrderBuilder/>` root renders "hello"
3. Static palette / type / token CSS — Sky/Walnut/Linen
4. JSON-RPC controller — `/southbrook/api/order/<id>` normalised
   order shape
5. `<OrderBuilder/>` root + reactive state wired to (4)
6. `<HeaderStrip/>` (5 cells) — first visible deliverable
7. `<StagePipeline/>`, `<OrderTitlebar/>`, `<IllustrativeBanner/>` chrome
8. `<TabBar/>` + tab-panel routing (client-side)
9. `<ZoneGroup/>` + `<OrderLine/>` — multi-zone grid
10. `<ConfigDrawer/>` — inline live-edit autosave
11. `<BoMPreview/>`, `<ValidationStrip/>` — read-only tabs
12. `<FooterActions/>` — Save, Confirm, Duplicate, Customer Print
13. Customer-mode toggle — `mode` prop on `<OrderBuilder/>`
14. Gate review with John

## License

LGPL-3.
