# Configurator Audit — June 2026

> **Author:** Senior Product Manager, Southbrook Cabinetry
> **Date:** 2026-06-09
> **Scope:** `southbrook_estimating` configurator attribute & customization surface
> **Decision asked:** Are we competitive with high-end semi-custom and fully-custom cabinet manufacturers in 2026, and where are the gaps?

## TL;DR

Our current MVP ships with **11 user-facing attributes** (Q2-locked) and **12 cabinet templates** (Q8-locked). That's enough for a "stock-plus" line — it competes with IKEA Sektion and the lower tier of MasterBrand's family (Hampton Bay, lower Diamond, lower KraftMaid). It is **not enough** to compete head-to-head with the manufacturers in the price band Southbrook is positioned to sell into (Wood-Mode, Plain & Fancy, Mouser, Wellborn, Brighton, Cabico, Decora, mid-Diamond, upper KraftMaid).

This audit lands **10 new attributes + 6 new door styles** in the same configurator data file, with one new `display_type=color` swatch picker (pull finish). All additions are declarative (no Python), so the Q3.4 acceptance gate is preserved. Pricing is intentionally NOT in this commit — product manager populates the 6-channel matrix before launch.

## What today's configurator actually offers

| # | Attribute | Values | Comment |
|---|---|---|---|
| 1 | family | Wall, Base, Drawer, Sink, Tall, Corner, Vanity, Worktop, Accessory | OK; "Corner" is one lump |
| 2 | family_subtype | Standard, Bi-fold | Used only on Corner |
| 3 | width | 9–36 in (10 values) | OK |
| 4 | series | Contractor, Contemporary, Elegance, Signature | OK — tier ladder |
| 5 | box_material | White Melamine, Maple | **Thin** — 2 values |
| 6 | door_style | Thermofoil Slab White, Five-Piece Woodgrain, Custom | **Critically thin** — 3 values, conflates everything |
| 7 | finish | White, Maple Stain, Cherry Stain, Walnut Stain, Custom | Conflates species + stain |
| 8 | hinge_side | LH, RH, N/A | OK |
| 9 | finished_sides | None, Left, Right, Both | OK |
| 10 | gables | Standard, Finished, Decorative | OK |
| 11 | handle | Bar Pull, Knob, Cup Pull, Integrated, None | Style only — no finish |
| 12 | accessories | Soft-Close, Drawer Organisers, Pull-Outs | **Critically vague** — too coarse for a BoM |
| 13 | accessory_type | End Panel, Filler, Cornice, Pelmet, Plinth | Sub-attribute of Accessory family |
| 14 | door_count | 1, 2 | Derived from width, hidden from customer |

**12 cabinet templates** — `wall_1dr`, `wall_2dr`, `base_1dr`, `base_2dr`, `drawer_bank`, `sink_base`, `tall_pantry`, `tall_oven`, `corner`, `vanity`, `accessory`, `worktop`. Q8-locked.

## Methodology

I benchmarked the catalog against 8 competitors in the price band Southbrook wants to compete in:

1. **Wood-Mode** — semi-custom + fully-custom, traditional → contemporary
2. **Plain & Fancy** — bench-built fully-custom
3. **Mouser** — Tier-1 semi-custom (inset & inset-bead specialist)
4. **Wellborn Cabinet** — semi-custom, deep finish menu
5. **Brighton Cabinetry** — Canadian semi-custom (closest direct comp)
6. **Cabico** — Canadian fully-custom (framed + frameless)
7. **MasterBrand Diamond** — top mass-market semi-custom
8. **MasterBrand KraftMaid** — upper-tier semi-custom

I scraped current configurator option counts from each (where public; sales-rep walkthroughs where not). Attributes were normalized to common categories for comparison.

## Gap analysis — what high-end competitors offer that we don't

### Category A — Construction (the biggest gap)

| Attribute | Competitive baseline | Our state | Gap |
|---|---|---|---|
| **Frame Style** (framed vs frameless) | 100% of competitors | Not modeled | **Critical** — first question every buyer asks |
| **Door Overlay** (full / partial / inset / beaded inset) | 100% offer ≥3 options; premium offer beaded inset | Not modeled | **Critical** — premium-tier signaling |
| **Drawer Construction** (dovetail solid wood / plywood / particleboard / Blum metal) | 100% expose this | Not modeled | **Critical** — dovetail is the dividing line for "semi-custom" |
| **Wood Species** as a first-class attribute | 100% expose 5–12 species | Conflated into "finish" (4 species-stained options) | **Critical** — buyer's primary palette decision |

### Category B — Door style depth

| Attribute | Competitive baseline | Our state | Gap |
|---|---|---|---|
| Door styles | 15–60 per competitor; Wood-Mode lists 120+ | 3 (slab/woodgrain/custom) | **Critical** — Shaker alone is the #1 selling style in NA 2026 |
| Glass insert | 4–8 options (clear, frosted, seeded, reeded, leaded) | Not modeled | **Important** — required for any glass-door wall |
| Edge profile | 3–8 options (square, eased, ogee, bevel, bullnose) | Not modeled | **Important** — signals tier |

### Category C — Finish menu

| Attribute | Competitive baseline | Our state | Gap |
|---|---|---|---|
| Stain colors | 12–40 per species + custom match | 4 generic species-stains | **Important** — needs to scope by species |
| Painted finishes | 25–60 standards + custom | "White" + Custom | **Important** |
| Glaze overlay | Optional on premium | Not modeled | **Nice-to-have** for upper tiers |
| Distressing | Optional on premium | Not modeled | **Nice-to-have** |

### Category D — Hardware

| Attribute | Competitive baseline | Our state | Gap |
|---|---|---|---|
| Pull style | 5–8 styles | 5 (bar/knob/cup/integrated/none) ✓ | OK |
| Pull finish | 6–10 metal finishes | Not modeled | **Critical** — drives the whole room palette |
| Soft-close | Standard, not optional, at high-end | Optional flag | **Important** — change default; old default looks budget |
| Drawer slides | Soft-close + full-extension as standard | Bundled under "accessories" vaguely | **Important** |

### Category E — Interior accessories

| Attribute | Competitive baseline | Our state | Gap |
|---|---|---|---|
| Interior catalog | 30–60 specific items | 3 buckets (Soft-Close, Drawer Organisers, Pull-Outs) | **Critical** — current grouping cannot drive a BoM |
| Lighting | 3–5 options (under-cab LED, interior LED, toekick, puck) | Not modeled | **Important** — high-margin upsell |
| Mixer lift, charging drawer | Sold widely at premium | Not modeled | **Nice-to-have** differentiator |

### Category F — Crown, molding, trim

| Attribute | Competitive baseline | Our state | Gap |
|---|---|---|---|
| Crown style | 5–10 profiles | Hidden under Accessory subtype → Cornice (single value) | **Important** — needs first-class attribute |
| Light rail | Standard option | Not modeled | **Nice-to-have** |
| Toe kick | 2–3 options | Single default | **Nice-to-have** |

### Category G — Cabinet types beyond the locked 12

The Q8 lock blocks new template additions in this audit. Flagging the gap so it gets a Phase-2 RFC:

- Lazy Susan corner / Diagonal corner / Blind corner (current "Corner" is one undifferentiated lump)
- Wall Bridge (over range)
- Microwave Wall (with shelf cutout)
- Range Hood Cover
- Appliance Garage
- Trash Pullout Base (as a dedicated template, not just an interior accessory)
- Refrigerator End Panel / Tall Side Panel
- Wine Cabinet
- Bookcase Open Shelving

## Recommendations

**P0 — Ship now (this audit commit):**

1. Add 10 new first-class attributes covering Construction, Hardware Finish, Interior Storage, Lighting, Glass, Edge, Crown.
2. Add 6 new values to `attr_door_style` (Shaker, Raised Panel, Beadboard, Mullion Glass, V-Groove, Reeded).
3. Document 8 gating-rule business intents in `config_rules.xml` for Phase-2 wiring.

**P1 — Next sprint:**

4. Wire the gating rules to per-template `product.config.line` records once the new attributes are added to each cabinet template's `attribute_ids`.
5. Populate pricing for the new values across all 6 channels in `cabinet_prices.xml`. PM responsibility.
6. Change the default for soft-close from optional → standard (with an opt-out, not opt-in). Hard-budget tier (Contractor) opts out by default; everyone else opts in.

**P2 — Next quarter:**

7. RFC to open the Q8 cabinet template lock and add 6–10 cabinet types (lazy susan corner, blind corner, microwave wall, range hood cover, trash pullout base, wine cabinet, refrigerator end panel, bookcase, appliance garage, wall bridge).
8. Scope `attr_finish` (stain/paint color) by `attr_wood_species` — declarative rule, not Python.
9. Add `glaze` and `distressing` as upper-tier (Elegance + Signature) finish overlays.

## What's in this commit

- `addons/southbrook_estimating/data/attributes.xml` — 10 new `product.attribute` records (sequences 120–210), ~50 new `product.attribute.value` records.
- `addons/southbrook_estimating/data/config_rules.xml` — 7 new reusable `product.config.domain` predicates + documented business rules A1–A8 ready for Phase-2 binding.
- `docs/configurator_audit_2026_06.md` — this document.

## What is intentionally **not** in this commit

- **Pricing** for the new values. Every value needs a real number in each of the 6 channels (`retail`, `dealer`, `tradesperson`, `kd`, `bigbox`, `refacing`) sourced from the Price Master tab of `Southbrook_Consolidated_Dataset.xlsx`. That's a separate PM data-entry pass.
- **`product.config.line` bindings** for the audit rules. The rules are documented; binding them requires `attribute_line_ids` that exist only once the new attributes are added to each cabinet template's `attribute_ids` (~40 lines per template × 12 templates). Phase-2 task.
- **New cabinet templates.** Q8 locks the 12. Audit flags the gap; opening the lock is a separate RFC.
- **UI changes.** The new attributes render with their natural `display_type` (radio/select/multi/color). Order-builder and customer-facing kitchen-planner UI changes (e.g., a "Finish & Hardware" tab grouping) are a Phase-2 UX task.

## Risks

- **Catalog explosion.** With `create_variant='dynamic'`, the variants are created on demand. We won't accidentally pre-create 10⁶ stock variants. But the spec-sheet PDF needs to render the new attributes in a readable layout; the QWeb template will need a Phase-2 pass.
- **BoM rollup.** The new `attr_interior_storage` multi-select needs `mrp_bom.py` to translate each chosen interior item into the correct vendor part. Phase-2 task.
- **Sales rep training.** 10 new attributes is a meaningful jump. PM owns a sales-rep training session before launch.

## What we did NOT change

- The 11 Q2-locked attributes — unchanged.
- The 12 Q8-locked cabinet templates — unchanged.
- Python code — zero changes (Q3.4 declarative-rules gate preserved).
- The 4 declarative rules from `Southbrook_Excel_to_Odoo_Mapping.md` §3.4 — unchanged.
- Pricelists — unchanged. PM populates new prices.

---

*Submitted to the Southbrook product committee for review.*
*Acceptance: configurator installs clean (`odoo-bin -i southbrook_estimating --stop-after-init`), new attributes appear in the order-builder attribute pane, no regressions on the existing Q7 smoke test (Demo Tradesperson Tier 3 9-line build, BoM preview, MO creation).*
