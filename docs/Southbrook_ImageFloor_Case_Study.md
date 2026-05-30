# Southbrook Image Floor Case Study

A multi-dealer operating-model and pricing case study, framed for the SAMI ERP/MRP + AI build.

**Purpose:** persona reference for the sales-rep Order Builder in `southbrook_estimating`. The four-dealer composition, the operating patterns, and the price-flow mechanics are the empirical ground on which the Order Builder's interaction model is sized and shaped.

**Source corpus:** the 2010–2017 Southbrook order pipeline, dealer correspondence, and Peter Tuschak's pricing workbook fragments. Names, numbers, and timings rounded for narrative clarity; the relationships and operating patterns are faithful.

---

## 0 · Why this exists

Phase 1 of the Southbrook build ships a sales-rep Order Builder. To get the Order Builder *right* — not just functional — Claude Code needs to know who's actually building orders and how their day looks. Generic ERP UX patterns don't survive contact with a real Vaughan-Ontario dealer running 8 open quotes, a customer on hold, and a renovation contractor wanting an off-spec end panel by Friday.

This document captures four dealer archetypes that recur across the corpus, the operating model each one uses, and the specific Order Builder affordances each one needs. When you're staring at `views/order_builder_views.xml` deciding whether a field belongs in the header strip, the inline drawer, or the validation tab — come back here.

---

## 1 · The four-dealer composition

Southbrook's Assembled Dealer Program runs four named dealers under the 50% off retail mechanic. They span the operating spectrum from "high-touch design studio" to "transactional volume". The composition is intentional: it covers most of the kitchen retail surface in Vaughan/Concord/Mississauga without saturating any single segment.

| Dealer | Operating model | Volume | Typical job |
|---|---|---|---|
| **Image Floor** | High-touch design-led studio | Mid (~25 jobs/yr) | Whole-kitchen renovation, $18–35k revenue per job, ~3 design iterations before order |
| **Amazing Window** | Window-and-door retailer that adds kitchens as a complementary upsell | Lower (~14 jobs/yr) | Tied to a window job; smaller kitchens, $8–14k revenue, single-iteration |
| **Pro Finish** | Trade-leaning, installs kitchens for contractor clients | Mid (~12 jobs/yr) | Mid-size kitchens for renovation contractors, $10–18k, often spec-driven (less iteration) |
| **Richwood Renovations** | Renovation contractor with a captive design service | High (~35 jobs/yr) | Full-renovation kitchens within larger projects, $15–28k, design + supply + install bundle |

The four together cover ~85 jobs/year against Southbrook's total dealer-channel output. The remaining ~15% comes from one-off retail and adjacent-territory dealers not in the named program.

### Why this matters for the Order Builder

The four dealers don't share an interaction style:

- **Image Floor** needs iterative quote management — same kitchen revised 3× before order. Implies: `crm.lead` → multiple `product.config.session` records → one `sale.order` at the end.
- **Amazing Window** needs *fast* quote-to-order conversion — they're closing the deal in the same visit as the window order. Implies: keyboard-driven, minimal-clicks single-screen flow.
- **Pro Finish** needs spec-import affordances — their contractors hand them dimensioned drawings; the rep keys those into the configurator. Implies: dimension-first entry mode (width/height/depth as the *primary* inputs, attributes second).
- **Richwood** needs bundle-aware pricing — they're often supplying labour separately, and want to see the cabinet subtotal isolated from the project total. Implies: zone aggregation (Q21) plus a "supply only" vs "supply + install" toggle on the order.

The Phase 1 Order Builder must accommodate all four. Defer the "supply + install" toggle to Phase 4; the other three styles are gating.

---

## 2 · The pricing flow — the Richwood −35% example, traced

To make the channel-pricelist mechanics concrete, here's the canonical Richwood example traced end-to-end. This is the smoke-test reference; the brief, the Build Spec, and the Mapping all cite it.

### Setup

- Customer: Richwood Renovations (`res.partner` with `channel = dealer`)
- Series: Contemporary
- Box material: white melamine (no maple uplift in this trace, for clarity)
- 9 cabinet lines, mid-size kitchen

### Step 1 — Retail list price

Pulled from the Price Master tab (illustrative seed numbers):

| Line | Template | Width | Retail Each | Qty | Line Retail |
|---|---|---|---|---|---|
| 1 | base_1dr      | 18″ | $366 | 1 | $366 |
| 2 | base_2dr      | 24″ | $531 | 1 | $531 |
| 3 | drawer_bank   | 18″ | $374 | 1 | $374 |
| 4 | sink_base     | 33″ | $778 | 1 | $778 |
| 5 | wall_1dr      | 15″ | $286 | 2 | $572 |
| 6 | wall_2dr      | 30″ | $696 | 1 | $696 |
| 7 | tall_pantry   | 24″ | $531 | 1 | $531 |
| 8 | accessory (end panel) | — | $95 | 2 | $190 |
| 9 | worktop       | — | $620 | 1 | $620 |
| **Retail total** | | | | | **$4,658** |

### Step 2 — Channel resolution

`res.partner.channel = dealer` → `_resolve_channel_pricelist` returns `southbrook.pricelist.dealer`.

The dealer pricelist mechanic: list × 0.50.

### Step 3 — Pricelist applied

$4,658 × 0.50 = **$2,329** delivered to Richwood.

### Step 4 — The header strip

The Order Builder's header strip shows, simultaneously:
- Customer: Richwood Renovations
- Channel: Dealer (−50%)
- Retail subtotal: $4,658
- Channel total: $2,329
- Savings: $2,329 (50%)

When the rep switches the customer to "Demo Tradesperson (Tier 3)" mid-order (a real Phase 1 smoke test), the header recomputes:
- Channel: Tradesperson (Tier 3, −35%)
- Retail subtotal: $4,658 (unchanged)
- Channel total: $4,658 × 0.65 = **$3,028**
- Savings: $1,630 (35%)

**This is the live recompute the smoke test asserts on.** Lines do not re-configure; only the pricelist factor changes. The rep sees the price update instantly across all 9 lines.

---

## 3 · The four operating patterns, distilled

### Pattern A — Image Floor: iterative design

The Image Floor rep, working with a homeowner over 2–3 visits:

1. Visit 1: rough kitchen layout, ~70% confidence. Saves as draft `sale.order`, stage = "Estimating".
2. Visit 2: revises 4 cabinets, adds 2, removes 1. Saves *new* draft with reference back to v1.
3. Visit 3: final spec, all 11 lines locked. Confirms.

**Order Builder affordance needed:** *"Duplicate as Draft"* action on an existing `sale.order` that creates a v2 with all lines copied and the original linked via `parent_order_id`. Stage stays "Estimating" until the rep confirms manually.

**Schema implication:** `sale.order.parent_order_id` Many2one self-reference, plus a `version` integer auto-incremented. Free side-effect: full revision history.

### Pattern B — Amazing Window: fast conversion

The Amazing Window rep, closing alongside a window deal:

1. Customer on premises, decision window ~30 minutes.
2. Rep keys 6 cabinets in the Order Builder, all defaults, Contractor series.
3. Hits Confirm. Customer pays deposit. Done.

**Order Builder affordance needed:** keyboard-driven everything — Tab through line entry, Enter to confirm. No mouse-required actions in the hot path. Defaults pre-filled where possible (Contractor series + white melamine + thermofoil slab door is the 80% default — make it the actual default).

**Schema implication:** `product.template.default_get` should pre-populate Contractor + thermofoil_slab + white_melamine for any non-Signature template. Settings field per user (`res.users.southbrook_default_series`) for reps who work outside the Contractor-default segment.

### Pattern C — Pro Finish: spec-driven entry

The Pro Finish rep, working from a contractor's dimensioned drawing:

1. Contractor emails a PDF with 8 cabinets and exact widths.
2. Rep opens the Order Builder, keys widths directly — *first* — then series, then door style.
3. Verifies each line against the drawing.

**Order Builder affordance needed:** width-first entry mode. The inline config drawer should let the rep enter the width before picking a template — the system suggests the matching template (e.g. "18″ width + base family → southbrook.base_1dr"). Reverses the normal cabinet-first flow.

**Schema implication:** width is an early-required attribute (it already is per Rule 3), but the UI flow needs a "spec-driven" toggle that surfaces width *above* family on the inline drawer. Implementation: a user preference field, not a schema change.

### Pattern D — Richwood: bundle and zone aware

The Richwood rep, building a whole-renovation kitchen:

1. 22 cabinet lines across 5 zones: BASE_RUN (8), WALL (6), TALL (4), ISLAND (2), ACCESSORY (2).
2. Wants subtotals per zone visible at all times (so the customer-facing print-out can be reorganised by zone).
3. Mid-build, customer wants island swapped from 36″ to 30″ — needs to find the island lines fast.

**Order Builder affordance needed:** the multi-zone grid Q21 mandated. Visible zone headers, per-zone subtotals, collapsible zones (Richwood lines usually have one zone open at a time during edit). The zone field on `sale.order.line` is the key here — and the QWeb spec sheet (custom routine #6) groups by zone for the customer print-out.

**Schema implication:** none beyond Q21's `zone` selection field. View XML does the work.

---

## 4 · The composite Order Builder

Combining the four patterns yields the Phase 1 Order Builder requirements list:

| Requirement | Driven by | Implementation |
|---|---|---|
| Header strip with live retail / channel / savings | All four | OWL component in `views/order_builder_views.xml` |
| Multi-zone grid with per-zone subtotals | Richwood (Pattern D) | Standard `<group expand="1" string="Zone">` + computed `zone_subtotal` field |
| Inline config drawer per line | All four | OCA `product_configurator` standard, themed |
| Keyboard-first navigation (Tab/Enter) | Amazing Window (Pattern B) | OWL key handlers |
| "Duplicate as Draft" action | Image Floor (Pattern A) | Server action + `parent_order_id` field |
| Width-first entry mode toggle | Pro Finish (Pattern C) | User preference flag + view conditional |
| BoM preview tab | All four (validation) | `product_configurator_mrp` standard |
| Validation tab (hard rules + soft suggestions) | All four | Custom panel reading from rule engine |
| Stage pipeline visible at top | Image Floor (Pattern A) | Odoo stages standard |
| Customer-switch re-pricing without re-config | Smoke test | `_resolve_channel_pricelist` + onchange |

This is the Phase 1 Order Builder surface. Nothing here requires a non-declarative business rule. Everything is data + view + standard Odoo affordances.

---

## 5 · Sales pipeline shape

The corpus reveals a typical month at Southbrook's dealer-channel desk:

- ~28 open quotes across the four dealers
- ~22 quote-to-order conversions per month (combined)
- Average quote-to-confirm latency: 9 days at Image Floor, 1 day at Amazing Window, 6 days at Pro Finish, 4 days at Richwood
- Win rate: Image Floor 78%, Amazing Window 92%, Pro Finish 75%, Richwood 82%

These are the values the Quote Log tab in the Consolidated Dataset is illustratively seeded with. Phase 2's customer-facing one-pager will *add* a channel — direct retail web orders — not yet represented in this pipeline shape. Phase 1 ships against the dealer-channel shape only.

### Implication for Phase 1 demo seed

`demo/southbrook_demo.xml` should seed:
- 4 dealer partners (one per archetype)
- 1 tradesperson partner (Demo Tradesperson Tier 3 — the smoke-test target)
- 6 open quotes spanning the dealers and series (the Quote Log seed)
- 5 confirmed orders spanning the channels (the Orders Summary seed)
- Linked `crm.lead` records for the 6 open quotes

The demo data should *look* like a real Southbrook month, so the Phase 1 gate review feels representative.

---

## 6 · What this case study does NOT settle

Out of scope for Phase 1, deferred to later briefs:

- **Lead-time prediction.** The corpus has enough data to train a lead-time predictor (input: cabinet count, series mix, box material; output: predicted days from confirm to ship). But this is AI-layer work, not Phase 1. The data spine in Build Spec §8 captures the training inputs from day one.
- **Quote win-rate by configuration.** Are 24″ corner cabinets associated with higher loss rates? Maybe. The Quote Log + Quote Line Items tables in the Consolidated Dataset enable this analysis; the model itself is post-Phase-4.
- **Dealer LTV ranking.** The Dealer Jobs tab has the seed data; the ranking model is AI-layer.
- **Geographic clustering.** All four dealers are within ~15 km of the Concord factory. Whether to add a 5th dealer in a different sub-market (Markham? Brampton?) is a business question outside this build.

---

## 7 · Cross-references

| To find… | Look at… |
|---|---|
| The smoke-test order shape (9 lines, Tier 3, maple) | `Southbrook_Excel_to_Odoo_Mapping.md` §6 + `Southbrook_Consolidated_Dataset.xlsx` Cabinet Line Items tab |
| The pricelist mechanics (the 6 channels) | `SAMI_Southbrook_Odoo19_Build_Spec.md` §6 + `Southbrook_Consolidated_Dataset.xlsx` Channel Economics tab |
| The 4 dealer partners as seed data | `demo/southbrook_demo.xml` (to be written in commit 11) |
| The data spine for future AI work | `SAMI_Southbrook_Odoo19_Build_Spec.md` §8 + `southbrook_order_analytics_DRAFT.py` |
| The zone selection on `sale.order.line` | `PUNCHLIST.md` Q21 |

---

**End of case study.**
