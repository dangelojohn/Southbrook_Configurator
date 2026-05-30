# Southbrook Estimating — Website

The customer-facing one-page kitchen configurator at
`/kitchen-planner` on `southbrookcabinetry.space`.

This addon adds the Three.js + 2D-fallback planner layer on top of
the OCA `website_product_configurator` route engine. The Order
Builder backend lives in the companion `southbrook_estimating`
addon; both share one configurator engine + one data model
(per `CLAUDE.md` §2.3 — there must not be two configurators).

## Status

**Phase 1 = empty skeleton.** Manifest + controllers/ stub only.

- Phase 2 (weeks 4-5) populates the `/kitchen-planner` route with
  the three-pane layout, catalog tiles, attribute selection panel,
  Tier-3 SVG cabinet renders, Signature-Series-styled spec-sheet PDF.
- Phase 3 (weeks 6-9) adds the Three.js scene + procedural
  `BufferGeometry` + automatic dimensioning + collision detection.

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
| `../../CLAUDE.md` | The operating brief — Persona A (customer) is the consumer of this addon |
| `../../docs/PRODBOARD_MANIFEST.md` | §3, §5, §9, §11 — what the Three.js scene mirrors + the four-tier image cascade |
| `../../docs/SAMI_Southbrook_Odoo19_Build_Spec.md` | §2.4 + §7 (Phase 3) — the Prodboard-class layer scoping |

## License

LGPL-3.
