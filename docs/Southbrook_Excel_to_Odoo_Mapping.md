# Southbrook Excel-to-Odoo Mapping

Module-by-module mapping of the Southbrook Excel order workbook into the Odoo 19 CE build.

**Source workbook:** `Southbrook_Cabinetry_Dealer_Kitchen_Program.xls` (18 MB, authored by Peter Tuschak, Director of Sales)
**Target:** Odoo 19.0 Community Edition + OCA Product Configurator suite
**Status:** Authoritative for business rules; cross-reference the workbook for any number not stated here

---

## 0 · Document purpose

The Southbrook workbook is an ERP-by-spreadsheet. Every formula in it is one of three things:

1. **Governed master data** — values that belong in `product.template`, `product.attribute.value`, or `product.pricelist`.
2. **Carry-forward mirror** — values Odoo renders for free once #1 is in place (subtotals, line totals, order summaries).
3. **Genuine business logic** — values that require configuration rules or a small custom rule.

This document maps every piece of the workbook to one of those three buckets and names the Odoo module that owns it. Claude Code's job is to instantiate the data and rules; it should never re-invent the logic.

---

## 1 · The series model

Southbrook ships **four series**, each with its own door style, finish set, and price point:

| Series | Position | Door style | Finish vocabulary | Box default |
|---|---|---|---|---|
| **Contractor** | entry / builder | white thermofoil slab only | white only | white melamine |
| **Contemporary** | mid | thermofoil slab + 5-piece options | broad colour palette | white melamine; maple optional |
| **Elegance** | upper-mid | 5-piece woodgrain only | woodgrain palette | white melamine; maple optional |
| **Signature** | premium | full custom range | full palette + custom | maple standard; custom optional |

The series is the **single most discriminating attribute** in the configurator — it gates door style, finish palette, box options, lead time, and pricelist mechanics. Encode it as the first attribute in `data/attributes.xml`.

---

## 2 · The two pricing mechanics

The workbook computes price two different ways depending on series + channel:

### 2.1 List-price mechanic (Contractor, Contemporary, Elegance, Signature on Dealer / Retail / Big-box channels)

Cabinet **list price** is a `width × series` lookup in the Price Master tab:

| Width (in) | Contractor | Contemporary | Elegance | Signature |
|---|---|---|---|---|
| 9 | $X | $X | $X | $X |
| 12 | $X | $X | $X | $X |
| 15 | $X | $X | $X | $X |
| 18 | $X | $X | $X | $X |
| 21 | $X | $X | $X | $X |
| 24 | $X | $X | $X | $X |
| 27 | $X | $X | $X | $X |
| 30 | $X | $X | $X | $X |
| 33 | $X | $X | $X | $X |
| 36 | $X | $X | $X | $X |

*(Actual $-values live in `Southbrook_Consolidated_Dataset.xlsx` Price Master tab. Claude Code seeds these as `product.template.attribute.value.price_extra` records.)*

Channel discount is then applied as a pricelist multiplier on the list price.

### 2.2 Cost-plus-margin mechanic (Contractor channel — confusingly named, distinct from Contractor *series*)

For the **Contractor channel** (i.e. business-to-tradesperson sales, not the entry-level series), price is:

```
contractor_channel_price = cabinet_cost × 1.05  (5% margin floor)
```

Then a tier discount of 25% / 30% / 35% is applied on top depending on the dealer's account standing. This is the only channel where price flows up from cost rather than down from list.

**Implementation:** seed two pricelist records for the Contractor channel — `pricelist.cost_plus_5pct` (the floor) and `pricelist.contractor_tier_discount` (the −25/−30/−35 selector on `res.partner`). Stack them.

---

## 3 · Module-by-module mapping

This is the canonical mapping Claude Code follows when seeding `southbrook_estimating`.

### 3.1 Sales / Products / Variants — `product.template` + `product.attribute`

**Source:** Dealer Order Form tab (the spreadsheet's main entry point); Vanity Program tab; Door Style sheet.

The workbook lists ~40 wall cabinet codes hand-enumerated by width and series. Collapse to **one configurable template per cabinet family**, with width and series as attributes:

| Family | Template | Width attribute values | Series attribute values |
|---|---|---|---|
| Wall 1-door | `southbrook.wall_1dr` | 9, 12, 15, 18, 21 in | Contractor / Contemporary / Elegance / Signature |
| Wall 2-door | `southbrook.wall_2dr` | 24, 27, 30, 33, 36 in | Contractor / Contemporary / Elegance / Signature |
| Base 1-door | `southbrook.base_1dr` | 9, 12, 15, 18, 21 in | All |
| Base 2-door | `southbrook.base_2dr` | 24, 27, 30, 33, 36 in | All |
| Drawer bank | `southbrook.drawer_bank` | 12, 15, 18, 24, 30 in | All |
| Sink base | `southbrook.sink_base` | 30, 33, 36 in | All |
| Tall pantry | `southbrook.tall_pantry` | 18, 24, 30 in | All |
| Tall oven | `southbrook.tall_oven` | 27, 30 in | All |
| Corner | `southbrook.corner` | 33, 36 in | All |
| Vanity | `southbrook.vanity` | varies (see Vanity Program tab) | Contemporary / Elegance only |
| End panel / filler | `southbrook.accessory` | varies | All |
| Worktop | `southbrook.worktop` | length-based | All |

**Result:** ~40 hand-listed wall codes collapse to 12 templates. Variants are created **dynamically** (Odoo's "Dynamically" creation mode on the attribute), so a variant/SKU is only realized when actually ordered.

#### The maple-box rule (price_extra + lead-time bump)

When the box material attribute is set to **maple** (instead of the default white melamine):

- Add **+10% price** as a `price_extra` on the `product.template.attribute.value`.
- Add **+2 weeks lead time** as an `mrp.bom` lead-time bump (see §3.5).

This is the cleanest declarative rule in the entire workbook. Do not implement it in Python.

### 3.2 Pricelists — `product.pricelist`

**Source:** the five channel tabs (Dealer, Contractor Tiered, Central KD, Big-box, Refacing) in the workbook.

| Channel | Pricelist record | Mechanic | Auto-assigned via |
|---|---|---|---|
| Retail | `southbrook.pricelist.retail` | List price ×1.00 | walk-in customers / `res.partner.channel = retail` |
| Dealer | `southbrook.pricelist.dealer` | List price ×0.50 | `res.partner.channel = dealer` (Image Floor, Amazing Window, Pro Finish, Richwood) |
| Contractor (tiered) | `southbrook.pricelist.contractor` | Cost ×1.05, then −25 / −30 / −35% | `res.partner.channel = contractor` + tier field |
| Central KD | `southbrook.pricelist.kd` | ≈46% of retail, component pricing (no assembly) | `res.partner.channel = kd` |
| Big-box | `southbrook.pricelist.bigbox` | Fixed $65 cost / $98 retail per SKU | `res.partner.channel = bigbox` (Lowe's, Home Depot) |
| Refacing (CTHS) | `southbrook.pricelist.refacing` | Per-SF door pricing, target 35% margin | `res.partner.channel = refacing` |

**Channel resolution:** add `channel` field to `res.partner` (selection field, the six values above) plus a `tier` field that only applies when channel = contractor. On `sale.order` creation, the partner's channel resolves the pricelist automatically via a default method.

**Refacing channel margin-target rule:** this is the **one place** where a true margin-target computed field is needed (price set live to hit 35% off current cost). Implement as a computed field on `product.pricelist.item`; flag it explicitly in `models/product_pricelist.py` as the only non-declarative pricing logic. Do **not** hand-roll the other four channels.

### 3.3 Product Configurator — the one-page order form `[OCA product_configurator]`

**Source:** Dealer Order Form tab (the heart of the workbook).

The Dealer Order Form tab is what the customer-facing one-page configurator replaces. The form flow is:

1. Customer / dealer selects **family** (wall, base, drawer, sink, tall, corner, vanity, worktop, accessory)
2. → **width** (snap-grid from the family's allowed values)
3. → **series** (Contractor / Contemporary / Elegance / Signature)
4. → **box material** (white melamine / maple — gated by series, see §3.4 Rule 2)
5. → **door style** (gated by series, see §3.4 Rule 1)
6. → **colour / finish** (from the series' palette)
7. → **hinge side** (L / R / N-A) — only if family has hinged doors
8. → **finished sides** (none / left / right / both)
9. → **gables** (standard / finished / decorative)
10. → **handle** (from the handle catalog)
11. → **accessories** (per-line: soft-close, drawer organisers, pull-outs, etc.)

Each selection re-prices live (via `product_configurator_sale`) and re-renders the cabinet preview (via the website Three.js layer in `southbrook_estimating_website`).

#### 3.4 The four declarative configurator rules — **THIS IS THE CORE BUSINESS LOGIC**

These four rules go in `southbrook_estimating/data/config_rules.xml` as `product.config.line` records. They are the configurator's restriction rules. **Encode them declaratively — do not write Python `if` branches that duplicate them.**

##### Rule 1 — Series → door style

- **Contractor** series exposes only **white thermofoil slab** doors.
- **Elegance** series exposes only **five-piece woodgrain** doors.
- Contemporary and Signature expose the full door catalog.

Encoded as `product.config.line` records with domain `[('attribute_id', '=', door_style), ('value_ids', 'in', [thermofoil_slab_white])]` keyed off the series attribute value.

**Acceptance:** selecting Contractor series in the UI causes the door style dropdown to show only thermofoil slab. Selecting Contractor + five-piece is **unselectable** (option is greyed out in sales-rep mode with the rule reason visible; option is absent in customer mode).

##### Rule 2 — Box material → series

- **Maple box** is available only on **Contemporary** and **Elegance** series.
- Contractor and Signature series do not offer maple box (Contractor is white-only; Signature already includes maple as standard).

Encoded as the inverse domain on the box_material attribute keyed off series.

**Acceptance:** selecting Contractor series greys out / hides the maple option.

##### Rule 3 — Width → door count

- **9–21 inch** cabinets are **1-door** (or 1-drawer-front for drawer banks).
- **24–36 inch** cabinets are **2-door** (or 2-drawer-front).

This rule drives the BoM rollup automatically — hinge quantity, door count, and door material consumption are all functions of the door count, which is a function of width.

Encoded as a `product.config.line` rule that sets door_count = `1 if width <= 21 else 2`.

**Acceptance:** changing width from 21 to 24 in the configurator flips door_count from 1 to 2 and the BoM preview shows one extra door + one extra hinge pair.

##### Rule 4 — Family → soft-close

- **Bi-fold corner cabinets** ship without soft-close hinges (mechanical incompatibility).
- All other families offer soft-close as an upgrade.

Encoded as a domain that hides the soft-close option entirely when family = corner_bifold. **Hide, not disable** — the customer never sees the option exists, so they don't ask why they can't have it.

**Acceptance:** selecting corner_bifold causes the soft-close toggle to disappear from the accessories panel.

### 3.5 Manufacturing — BoM & the Shop Copy `[CE mrp module + small CUSTOM extension]`

**Source:** Shop Copy tab (254 formulas mirroring the order form).

The Shop Copy tab in the workbook is a manual mirror of the order form, with 254 cell-level formulas duplicating order data for the shop floor. **Stop mirroring.** When the configured sale order is confirmed:

1. The MO (`mrp.production`) is generated automatically.
2. The BoM (`mrp.bom`) is attribute-driven — component quantities and sizes are functions of the chosen dimensions, not hand-listed.
3. The Shop Copy QWeb report (`reports/shop_copy.xml`) renders the MO in Southbrook's familiar layout — same visual format the shop already reads, but rendered, not mirrored.

#### The parametric BoM rollup

Each cabinet template's BoM is parametric:

| Component | Quantity formula | Source attribute |
|---|---|---|
| Side panel (L) | 1 | (constant per cabinet) |
| Side panel (R) | 1 | (constant per cabinet) |
| Top panel | 1 | (constant) |
| Bottom panel | 1 | (constant) |
| Back panel | 1 | (constant) |
| Shelf | 1–3 (depends on height) | height attribute |
| Door | 1 if width ≤ 21 else 2 | width attribute (Rule 3) |
| Hinge pair | 1 per door | derived from door count |
| Handle | 1 per door | derived from door count |
| Drawer slide pair | 1 per drawer | drawer count attribute |
| Edge banding | sum of exposed edges × perimeter formula | finished_sides attribute |

Panel dimensions are computed by a small custom routine (`models/mrp_bom.py::_compute_panel_dimensions`) that takes the cabinet's W×H×D and outputs each panel's L×W×T. **This is the one piece of genuinely custom logic** — flagged in the SAMI build spec as the parametric cut-dimension module.

#### Lead-time bump for maple box

When box material = maple, add 2 weeks to the BoM's `produce_delay`. This is enforced via the `price_extra` rule from §3.1 plus a parallel `lead_time_extra` field on the attribute value.

### 3.6 Inventory — `stock` (CE native)

**Source:** the workbook's implicit inventory tracking (it has none — Southbrook tracks inventory in a separate set of spreadsheets entirely).

The configured variants flow into `stock.move` automatically once they exist as `product.product` records. **Labels** (the workbook's manual label-printing step) become stock-move-driven via a QWeb label report rendered at the picking stage.

### 3.7 Purchase — `purchase` (CE native)

**Source:** Door Order tab.

The Door Order tab in the workbook is a manual aggregation of doors needed across all open orders, by series + colour + door style + size, to send to the door supplier. Replace with:

- A `purchase.order` auto-generated per supplier from confirmed `mrp.production` demand.
- A custom report (`reports/door_order.xml`) that renders the open door demand in the same format the door supplier already accepts.
- For the Signature series doors (custom), the PO carries the door spec line-by-line. For Contractor series (single white thermofoil), the PO aggregates total square footage.

### 3.8 Accounting — `account` (CE native)

**Source:** Invoice tab (a manual format).

Channel margin reporting: add **analytic tags** to every sale order at confirm-time, capturing `channel`, `series`, and `dealer_tier`. This is what the SAMI build spec calls "the data spine" — it's free during Phase 1 and enables Phase 2's quote analytics without retrofit.

### 3.9 CRM — `crm` (CE native)

**Source:** Quote Log tab + Dealer Jobs tab.

- The Quote Log tab becomes `crm.lead` records with the configured order line items attached as `product.config.session` records (saved but un-confirmed sessions).
- The Dealer Jobs tab becomes `sale.order` records grouped by dealer (`res.partner` filter).

### 3.10 Website — `website_product_configurator` (OCA) + `southbrook_estimating_website` (NEW)

The customer-facing one-page configurator on `southbrookcabinetry.space`. The OCA `website_product_configurator` provides the route engine; `southbrook_estimating_website` provides the Three.js layer, the Signature Series styling, and the four-tier image cascade from `PRODBOARD_MANIFEST.md` §11.

---

## 4 · The pipeline transformation

Old (Excel pipeline):
```
order form → shop copy (254 formulas) → labels → door order → cutlist
   ↑              ↑                       ↑          ↑           ↑
   manual         manual mirror           manual     manual      manual
```

New (Odoo pipeline):
```
configured sale.order  → mrp.production → stock.picking labels → purchase.order (doors) → cut-list export
        ↑                       ↑                ↑                       ↑                       ↑
        configurator            rendered         rendered                rendered                rendered
        (rules in data)         from BoM         from picking            from BoM demand         from BoM panel rollup
```

Every manual hand-off is replaced by a rule that's either:
- (a) data in `data/*.xml`,
- (b) a `product.config.line` declarative configurator rule (§3.4),
- (c) the parametric BoM rollup in `models/mrp_bom.py` (§3.5),
- (d) a QWeb report template in `reports/*.xml`, or
- (e) the refacing channel computed field in `models/product_pricelist.py` (§3.2 — the only non-declarative pricing rule).

That's the entire custom surface area. Everything else is data or configuration.

---

## 5 · The custom register

The pieces of code that are genuinely custom (not data, not configuration). Claude Code should keep this list short — anything that grows it needs a justification in `PUNCHLIST.md`.

| # | Routine | Owns | Reason it's custom |
|---|---|---|---|
| 1 | `models/mrp_bom.py::_compute_panel_dimensions` | The parametric panel cut sizes from W×H×D | Cannot be expressed as a simple variant attribute |
| 2 | `models/product_pricelist.py::_compute_refacing_price` | The 35% margin-target rule for the refacing channel | Live-cost-targeting cannot be expressed declaratively |
| 3 | `models/sale_order.py::_resolve_channel_pricelist` | Auto-assigns pricelist from `res.partner.channel` | One method, ~10 lines, dispatch logic only |
| 4 | `static/src/js/parametric_carcass.esm.js` | The Three.js procedural BufferGeometry from cabinet dimensions | The whole point of the planner layer |
| 5 | `reports/shop_copy.xml`, `reports/door_order.xml`, `reports/signature_spec_sheet.xml` | The Southbrook-format QWeb reports | Layout templates, not logic |
| 6 | `controllers/accucutt_bridge.py` | The Accucutt nest hand-off (JSON export + result ingest) | External-system integration |

Six custom files. That is the entire custom code surface for `southbrook_estimating`. Anything beyond this is a smell.

---

## 6 · Acceptance test — the smoke test

Once the addon is installed and seeded:

1. Create a `res.partner` named "Richwood Renovations" with `channel = dealer`.
2. Open Sales → Order Builder, create a new order, customer = Richwood.
3. Configure 9 lines: base 1-door 18", base 2-door 24", drawer bank 18", sink base 33", wall 1-door 15"×2, wall 2-door 30", tall pantry 24", end panel.
4. Each line uses Contemporary series, white maple box (+10%), thermofoil slab door, white finish, soft-close on.
5. Confirm the rule engine fires correctly:
   - Selecting Contractor on any line should hide maple from the box options (Rule 2).
   - Trying to set 5-piece door on a Contractor line should be unselectable (Rule 1).
   - Switching the 21" base to 24" should flip its BoM from 1-door to 2-door (Rule 3).
6. Open the BoM preview tab — every line shows its parametric BoM, the maple lines carry the +2-week lead time.
7. Total at footer: should match the Richwood −35% Contractor pricelist applied to Contemporary list prices, plus the +10% maple uplift.
8. Switch customer to "Walk-in Retail" — every line re-prices to retail, nothing else changes.
9. Hit Confirm — `mrp.production` records are created, one per cabinet, with the correct parametric BoMs.
10. The Shop Copy QWeb report renders correctly.

This is the Phase 1 gate.

---

## 7 · What the workbook contains that is **not** in scope for Phase 1

Defer to later phases / future briefs:

- **Vanity Program tab** — vanities are a distinct sub-product (Contemporary/Elegance only, smaller width range, different hardware vocabulary). Implement in Phase 2 as a vanity-specific template family.
- **Sample Kitchens tab** — pre-configured kitchen designs as starting templates. These become `product.config.session` template records in Phase 3 when the planner UI is built.
- **Imports comparison tab** — the cost/margin comparison vs Chinese imports (the Central KD channel context). Reporting concern, not configurator concern.
- **Signature Series spec book PDF parsing** — the visual reference is in `southbrook_book_templates.pdf`; Claude Code doesn't parse it, just uses it as the styling target for the QWeb spec sheet report.

---

## 8 · Cross-reference index

| If Claude Code needs… | Read… |
|---|---|
| The 11 configurator attributes and their values | This doc §3.3, then seed from `Southbrook_Consolidated_Dataset.xlsx` Price Master tab |
| The four declarative business rules | This doc §3.4 |
| The five channel pricelist mechanics | This doc §3.2 |
| The parametric panel cut math | This doc §3.5, then look for any prior `mrp_bom.py` skeleton in past Project deliverables |
| The Prodboard recipe grammar and 18 element types | `PRODBOARD_MANIFEST.md` §5 |
| The DimensionEnvelope schema | `PRODBOARD_MANIFEST.md` §4.3 |
| The locked architecture and phasing | `SAMI_Southbrook_Odoo19_Build_Spec.md` §0–§4 |
| Real-world dealer behaviour patterns | `Southbrook_ImageFloor_Case_Study.md` |
| Actual $-values and pricelist data | `Southbrook_Consolidated_Dataset.xlsx` |
| The visual target for the customer flow | `southbrook_book_templates.pdf` (Signature Series spec book) |

---

**End of mapping document.**
