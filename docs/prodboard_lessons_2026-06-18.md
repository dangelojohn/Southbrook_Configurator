# Prodboard / BetterKitchens Lessons & Actions

Source files (Downloads, 2026-06-17 / 2026-06-18):

- `Prodboard_BetterKitchens_UX_UI_Analysis.md`
- `Prodboard_BetterKitchens_Additional_Findings.md`
- `Prodboard_BetterKitchens_Complete_Products_Catalog.md`
- `Prodboard_BetterKitchens_Products_JSON.json`
- `Prodboard_BetterKitchens_Product_Image_Reference.md`

This doc captures what Prodboard's UX / data shape teaches the Southbrook
platform — patterns we can borrow, gaps we should fill, and the concrete
actions executed on `feature/prodboard-actions-1-5`.

---

## 1. Cabinet-SKU grammar (decoded)

Prodboard codes encode the cabinet **type**, not its configuration. The
grammar:

```
CC-                Classic Collection prefix
TH-                True Handleless prefix
─────────────────────────────────────────────
{body}             B = Base | W = Wall | T = Tall | C = Corner | D = Dresser
{type}             HL = Highline (door only)
                   DL = Drawerline (door + drawer)
                   MD = Multi-drawer
                   BN = Bin
                   BS = Belfast sink
                   HS = Highline sink
                   DS = Dummy sink (drawerless front)
                   PO = Pull out
                   UO = Under oven (built-under)
                   WO = Wine open
                   WP = Wine pull
                   OP = Open
                   OE = Open end
                   CV = Curved
                   SPLY = Splay end
{variant suffix}   1DR/2DR     = door count
                   1DW–5DW     = drawer count
                   {S}         = size template variable (width)
                   {H}         = height template variable
                   {h}         = sub-height template variable
                   [D300]      = depth override
                   [u]         = "unit" alternate (panel suffix)
{corner suffix}    BCO         = Blind Corner Optimiser
                   CPOS        = Corner Pull-Out Shelving
                   LVCPOS      = LAVA Corner Pull-Out Shelving
                   MC          = Magic Corner (LeMans-style)
                   PBCO        = Planero Blind Corner (Vauth-Sagel)
                   PSOC        = Planero Swing-Out Corner
```

The grammar is captured programmatically in
`addons/southbrook_estimating/models/cabinet_archetype.py:_TYPE_LABELS`.

## 2. What Southbrook already does (re-confirmed)

The first two analysis docs validated the platform direction:

- 3-pane OWL layout matches Prodboard's nav/catalog/viewport split.
- Chip selectors + live recalc are equivalent to Prodboard's reactive
  property panel.
- The audit P6 chip + missing-checklist work mirrors Prodboard's
  "X options still needed" + "Continue with warnings" pattern.
- Three.js for the Phase 3 3D layer is the right call — Prodboard
  built their own `constructorV2` engine, but going custom would be
  over-engineering for Southbrook's scope.
- Authentication gating (design freely, sign in to save) matches our
  portal-user `/commit` gate.

## 3. Tier 1 — completed actions (`feature/prodboard-actions-1-5`)

| # | Action | Commit | Module touched |
|---|---|---|---|
| A1 | Prodboard JSON imported as cabinet-archetype taxonomy seed (223 archetypes) | `1568be0` | `southbrook_estimating` |
| A2 | End-Panel mini-catalogue (15 end panels + 3 fillers, in-house brand) | `b2b6954` | `southbrook_hardware_catalog` |
| A3 | Corner-solution catalogue (10 specialty mechanisms across LAVA / Vauth-Sagel / Häfele / in-house) | `4d893ff` | `southbrook_hardware_catalog` |
| A4 | UUID-versioned catalog-icon URLs (`x_image_uuid` on `product.template` + `/southbrook/catalog/icon/<uuid>/<filename>` controller) | `16d16df` | `southbrook_estimating` |
| A5 | Type-encoded `SB-*` `default_code` on Q8 templates (parallel to P5 variant grammar) | `df5649c` | `southbrook_estimating` |

All five actions are **additive metadata work**. No behaviour change in
the existing UI / configurator surfaces until subsequent UI work consumes
the new data (a future P10/P11 series).

## 4. Tier 2 — deferred items (not in this branch)

These were identified from the analysis but explicitly left for a future
session:

- **MI rule "exposed cabinet side"** — a `southbrook.mi.check` rule that
  fires when a run-end cabinet has no `Finished Sides` value. Direct
  port of Prodboard's open-side detector.
- **Door-area in m² as a computed field** — for paint/lacquer pricelist
  rollup.
- **Commit-with-warnings server-side gate** — extend the P6
  `add_to_quote_enabled` logic to also surface warning-severity issues
  (instead of strictly required-missing only).
- **AURORA-style handle naming convention** — rename the existing handle
  product names to a consistent "Family + Type + Size" pattern.
- **GPU-detected 3D quality presets** (ULTRA / High / Medium / Low) —
  for `southbrook_estimating_website` Phase 3.
- **PBR toggle** — performance vs realism trade in Phase 3.
- **A/B/C/D elevation views + render layers toggle** — bottom toolbar
  in Phase 3.

## 5. Tier 3 — strategic / future

- **`kitchen.room` model** — walls, dimensions, doors / windows /
  columns / sockets / decorative panels / tiles / floor / ceiling. The
  biggest gap vs Prodboard. New addon `southbrook_room` in v1.1.
- **Furniture / Decor catalogue expansion** — fridges, stoves, hoods,
  washing machines, dining tables, chairs, curtains, TVs. Only if
  Southbrook positions as "kitchen experience" rather than "cabinet
  shop".
- **Multi-tenant / white-label theming** — dealer-specific brand colors,
  filtered catalog, own logo. Maps onto the `res.partner.channel`
  field that already exists per CLAUDE.md Q1.

## 6. What we did NOT do (intentionally)

- **No literal port of the UK Prodboard catalogue.** Belfast Sink Base,
  Boiler Housing Wall, 50/50 Fridge Freezer Housing are UK-specific.
  The archetype taxonomy (A1) ships *all 223 archetypes* as metadata so
  the platform can recognize them, but no UK-specific cabinet template
  was added to the price-bearing Southbrook product set.
- **No import of Prodboard image assets.** Licensing is unclear and the
  URLs reference `blobs.prodboard.com` directly. The archetype records
  carry `image_url` for reference only; the A4 controller serves
  Southbrook-owned `image_1920` content.
- **No restructure of the 12 Q8 Southbrook cabinet templates.** Per
  CLAUDE.md Q8 they have locked xml_ids. The A1 + A5 work is additive
  metadata alongside them.

## 7. Verification commands

After deploy, the following confirm the actions landed cleanly:

```bash
# A1 — 223 archetypes seeded
psql ... -c "SELECT collection, COUNT(*) FROM southbrook_cabinet_archetype GROUP BY collection;"
# expect: classic=160, handleless=63

# A2 — end-panel + filler count
psql ... -c "SELECT x_hardware_category, COUNT(*) FROM product_product WHERE x_hardware_category IN ('end_panel','filler') GROUP BY x_hardware_category;"
# expect: end_panel=15, filler=3

# A3 — corner mechanisms
psql ... -c "SELECT COUNT(*) FROM product_product WHERE x_hardware_category = 'corner_mech';"
# expect: 10

# A4 — controller reachable (returns 404 for unknown UUID)
curl -sS -o /dev/null -w '%{http_code}\n' \
  https://southbrookcabinetry.space/southbrook/catalog/icon/00000000-0000-0000-0000-000000000000
# expect: 404

# A5 — Q8 templates carry SB-* codes
psql ... -c "SELECT default_code, name->>'en_US' FROM product_template WHERE default_code LIKE 'SB-%' ORDER BY default_code LIMIT 20;"
```

## 8. Branch + PR

- Branch: `feature/prodboard-actions-1-5` (5 commits, off
  `feature/configurator-loop-p1-p8`)
- GitHub PR: open against `feature/configurator-loop-p1-p8` (or
  `feature/premium-orchestration-only` for a wider merge)
- Acceptance: each commit has its own TransactionCase tests; no
  destructive migrations; no widened ACLs (the new
  `southbrook.cabinet.archetype` model gets 3 new ACL rows in A1
  scoped to existing groups, no widening).
