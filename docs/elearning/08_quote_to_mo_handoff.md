---
course: 8 — Estimating Deep Dive
chapter: 8.4
title: Quote to MO Handoff — What the Production Planner Inherits, What Gets Lost
duration: 50 minutes
audience: Estimator + Production Planner. The estimator needs to know what survives Confirm and what's an estimating-only artifact; the planner needs to know what to trust about the MO that lands in their queue.
prereqs: Lesson 5.1, Lesson 5.2, Lesson 8.1 (architecture), Lesson 8.2 (Order Builder walkthrough), Lesson 8.3 (pricing); ideally also Lesson 2.1 (Kitchen Projects vs Sale Orders)
custom_modules: southbrook_estimating, sale_mrp, product_configurator_mrp, mrp, southbrook_plm (optional but transformative)
---

# Quote to MO Handoff — What the Production Planner Inherits, What Gets Lost

## Who this lesson is for

You're the estimator who just clicked Confirm — and you want to know
what the planner sees on their side. Or you're the planner who just
got an MO in your queue from `SO00321` and want to know what
information came across, what's reliable, and what's missing.

This is the handoff lesson. The fault line between "estimating" and
"production" runs straight through `action_confirm`, and 70% of the
"why is my MO wrong?" tickets trace back to misunderstandings about
this transition.

## Where this lives on the site

The trigger for handoff:

> **Southbrook Estimating → Order Builder → (any draft) → Confirm**
> button (top of form, calls `action_confirm`)

What the planner sees post-Confirm:

> **Manufacturing → Operations → Manufacturing Orders** (filter by
> `origin = <SO name>` or by `sale_line_id.order_id`)

The cut-spec snapshot (when southbrook_plm is installed):

> **PLM → Cut Specs → (the active spec at confirm time)**

The analytics row that captures handoff metadata:

> **Settings → Technical → Database Structure → Models →
> southbrook.order.analytics** (filter `sale_order_id` by your SO)

## What your screen shows

When you click Confirm on a draft order, three things happen in
sequence (covered in detail below). Visually:

- The state pipeline (top right) moves from `sent` (or `draft`) →
  `sale`.
- A new statbutton labelled "Manufacturing" appears on the order
  form showing the count of MOs created.
- The order's lines stay visible but become readonly.
- The Pricelist field becomes readonly.
- The `southbrook.order.analytics` row gets created (or updated if
  this is a re-confirm).

What you DON'T see on the order form:
- The `mrp.bom` records the MOs reference.
- The cut-spec snapshot (lives in `southbrook_plm` if installed —
  Phase 1 estimating doesn't snapshot per-order).
- The `sb.production.package` rows (Phase 4 — created by
  `southbrook_kitchen_mrp` on MO confirm, if installed).

## Your daily flow

**1. Before clicking Confirm — what's about to happen.**

Confirm is a one-way door for most purposes. Lines lock, pricing
freezes, MOs spawn. So check first:

- Every cabinet line has been configured (no "Configure" button
  still visible — it should read "Re-configure" post-wizard).
- `sb_panel_count` is non-zero on every cabinet line.
- The Pricelist field shows the channel-appropriate name (not
  Retail when the customer is a Tier 3 contractor).
- Zone is set on every line (not blank — defaults to base_run).
- The customer has signed the Signature Spec Sheet PDF. The signed
  PDF should be attached to the order (chatter).

**2. Click Confirm — the override fires.**

`models/sale_order.py:action_confirm` runs:

```python
def action_confirm(self):
    result = super().action_confirm()
    Analytics = self.env["southbrook.order.analytics"]
    for order in self:
        Analytics.capture(order)
    return result
```

Three layers fire:

a. **`super().action_confirm()`** — standard Odoo's
   `sale.order.action_confirm`. State moves to `sale`. For each
   order_line whose product has a route through Manufacturing,
   `sale_mrp.SaleOrder._create_mo_per_order_line()` (the bridge
   addon) spawns one `mrp.production` record. The MO carries:
   - `product_id` = the line's variant.
   - `product_qty` = the line's `product_uom_qty`.
   - `origin` = the SO name (free-text fallback link).
   - `sale_line_id` = the originating line (M2O — the canonical
     link).
   - `bom_id` = resolved by Odoo's MRP engine via
     `mrp.bom._bom_find()` against the variant.

b. **Bill of Materials lookup** — for each MO,
   `mrp.bom._bom_find(product=variant)` walks the BoM table looking
   for a BoM whose `product_id` (or `product_tmpl_id`) matches the
   variant. If found, the MO's `bom_id` is set. If not, the MO
   spawns with `bom_id` blank — the planner gets a "no BoM" MO
   they'll have to attach a BoM to manually.

c. **`Analytics.capture(order)`** — `southbrook.order.analytics.capture`
   either creates or updates the analytics row. The values rolled
   up:
   - `channel` (related to `partner_id.channel`, stored).
   - `tradesperson_tier` (related, stored).
   - `dealer_id` (set to `partner_id.id` when channel == `dealer`,
     else False).
   - `series` (most-common Series attribute value across lines via
     `Counter.most_common(1)`).
   - `quoted_at` (related to `create_date`, stored).
   - `confirmed_at` (set to `sale_order.date_order`).
   - `cabinet_count` = sum of `product_uom_qty`.
   - `panel_count` = sum of `sb_panel_count` per line.
   - `door_count` = sum of `sb_door_count` per line.
   - `nest_yield_pct` = null (set later by the Phase 4 Accucutt
     bridge).

**3. What the MO carries — the planner's view.**

For each MO that lands in the planner's queue, the inheritance from
the SO line is:

- **Product variant** — exact same variant as on the SO line.
  `mo.product_id` = `sale_line.product_id`. So all the variant's
  attribute values (Series, Box Material, Door Style, Finish, etc.)
  travel along.
- **Quantity** — `mo.product_qty` = `sale_line.product_uom_qty`.
- **Originating SO** — `mo.sale_line_id.order_id` is the canonical
  link (NF25). `mo.origin` is the legacy free-text fallback.
- **BoM** — `mo.bom_id` populated by Odoo's MRP resolution.
- **Lead time** — `mo.date_planned_finished` computed by Odoo using
  `mo.bom_id.effective_produce_delay` (which is `produce_delay +
  southbrook_lead_time_extra`). So Maple's +14 days flows
  automatically into the planner's scheduled finish date.

What the MO does NOT carry from the SO line:
- `zone` — production doesn't care about kitchen zones. A wall
  cabinet runs the same way as a base cabinet on the shop floor;
  the carcass math is identical (modulo dims).
- `zone_label` — same logic.
- `price_unit`, `price_subtotal`, `discount` — no pricing flows to
  production.
- `sb_panel_count`, `sb_door_count` (the live-computed fields) —
  the MO recomputes these from its own BoM's bom_line_ids, not from
  the SO line's live compute. So if the SO line's compute returned
  0 (e.g. `southbrook_dims` import failed), the MO won't
  inherit that 0 — the BoM's actual bom_line_ids drive the cut list.

**4. The `_get_cut_constants` seam — where the cut spec attaches.**

This is the load-bearing PLM integration point. Read
`models/mrp_bom.py` for the canonical method:

```python
@api.model
def _get_cut_constants(self):
    return {
        "box_th": BOX_TH,           # 15.875 (5/8" melamine)
        "back_th": BACK_TH,         # 6.35  (1/4" hardboard)
        "rabbet": RABBET,           # 6.35
        "door_th": DOOR_TH,         # 18.0  (3/4")
        "door_reveal": DOOR_REVEAL, # 3.0
        "shelf_tol": SHELF_TOL,     # 1.5
        "shelf_vent_gap": SHELF_VENT_GAP,  # 12.7 (1/2")
        "toekick_h": TOEKICK_H,     # 101.6 (4")
    }
```

In a vanilla `southbrook_estimating` install, this returns the NF14
baseline constants (frameless euro construction, melamine standard).

When `southbrook_plm` is installed, it OVERRIDES the method:

```python
# southbrook_plm/models/mrp_bom.py:108-128
spec = self.env["southbrook.cut.spec"].sudo()._get_active()
if spec:
    return spec.constants_dict()
return super()._get_cut_constants()
```

So with PLM installed AND an active cut spec, every call to
`_compute_panel_dimensions` reads the cut spec's `box_th`,
`door_th`, etc. — meaning an ECO that updates the cut spec (e.g.
"door reveal is now 5mm not 3mm") propagates to every NEW MO BoM
math automatically.

**CRITICAL CAVEAT:** the cut-spec snapshot is not stored on the SO
or the MO. There is no `southbrook_cut_spec_version_id` field on
`sale.order` or `mrp.production` in `southbrook_estimating` itself
(TBD — search returns no hits in the addon). The "snapshot" is
implicit — the BoM was computed using the cut spec active at MO
creation time. If the cut spec changes after MO creation, the
already-computed BoM lines DON'T update; but if a planner runs
"recompute BoM" the new constants will apply. This is documented as
a Phase-1 limitation in `southbrook_plm` — the per-order snapshot
field is a planned extension, not a shipped one.

**5. `sb_panel_count` + `sb_door_count` — computed live, on the line.**

These are NOT stored on the MO. They're computed on the SO line by
`_compute_sb_panel_rollup` reading:
1. The variant's `product_template_attribute_value_ids` for Family,
   Width, Door Count.
2. Fallback to `line.name` regex parsing
   (`_WIDTH_INCHES_RE`, `_FAMILY_RE`, `_DOOR_COUNT_RE`).
3. Fallback to family defaults (`_SB_DEFAULT_HEIGHT_MM` family
   constants).

Then calls `southbrook_dims.panel_cut_list(W, H, D, family=..., door_count=...)`
to get a shelf_count + door tuple. Returns:
- `sb_panel_count = pieces * qty` where `pieces = 5 + shelf_count +
  door_count` (sides + top + bottom + back + shelves + door fronts).
- `sb_door_count = door_count * qty`.
- `sb_width_mm = derived W`.

These fields exist for two reasons: (a) display in the Order
Builder so the estimator sees panel/door counts; (b) feed
`southbrook.order.analytics` at confirm time. They are NOT used by
production scheduling — the planner trusts the BoM's
`bom_line_ids`.

**6. What gets lost in translation.**

- **Zone** — production-blind.
- **Pricing** — production-blind.
- **Customer notes** — production-blind unless they're on the BoM
  or the product. Customer-facing comments on order lines DO NOT
  flow to MO notes by default. (This catches everyone: "I told the
  estimator I want the soft-close upgrade" — soft-close is an
  attribute that affects the BoM hardware lines. If the estimator
  didn't pick the soft-close attribute, the customer's note isn't
  visible to the shop floor.)
- **Configurator-session attribute picks beyond what materialised
  on the variant** — only the variant's
  `product_template_attribute_value_ids` survive. If the configurator
  session captured a `value_custom` (free-text answer to an attribute),
  that text lives on the `product.config.session` record, NOT on
  the variant. The MO doesn't see it.
- **Pre-confirmation pricing iteration history** — the prior versions
  in the `parent_order_id` chain. The MO knows only about THIS
  confirmed order.

What DOES survive:
- Variant attributes (Series, Box Material, Door Style, Finish,
  Hinge Side, Finished Sides, Door Count, Family).
- BoM lines (panels + hardware + edge banding scalar).
- Lead time extras (e.g. Maple +14 days via
  `effective_produce_delay`).
- The link back to the SO line (`mo.sale_line_id`).
- The link back to the customer through the SO partner.

## Common mistakes + how to recover

**"I confirmed 8 hours ago and the planner can't find the MO."**

Three suspects:
1. The line products don't have `route_ids` including Manufacturing.
   No MO spawns for products without a Manufacturing route. Open
   the product → Inventory tab → Routes. (12 Q8 SKUs are seeded
   correctly; catalog-expansion products may not be.)
2. `sale_mrp` isn't installed. The manifest explicitly depends on
   it (NF25), but a partial cold install can skip it. Verify:
   `Apps → Filter: sale_mrp → Installed`.
3. The MO was created but assigned to a planner's queue you're not
   looking at. Search by `origin = <SO name>` across all
   Manufacturing menus.

**"The MO's BoM is empty — bom_line_ids is null."**

The variant doesn't have a matching BoM. Either:
1. No `mrp.bom` exists for this variant (the variant was
   materialised dynamically from the configurator but no BoM was
   created — this is a Phase-1 gap; the BoM rollup from
   `product_configurator_mrp` should run but sometimes silently
   fails). Recovery: create a BoM manually for the variant, run
   `mrp.bom._compute_panel_dimensions` via the developer shell to
   populate, attach to the MO.
2. The BoM exists but is in `state = 'draft'`. Move to `confirmed`.

**"Maple cabinets confirmed yesterday should have +14 days lead
time but the planner's date_planned_finished shows the baseline."**

Either `southbrook_lead_time_extra` didn't roll up, or
`effective_produce_delay` didn't get read at MO scheduling. Verify:
1. Open the BoM. Check
   `bom.southbrook_lead_time_extra` (should be 14.0).
2. Check `bom.effective_produce_delay` (should be `produce_delay +
   14`).
3. Open the MO. Check `mo.date_planned_finished`. If it doesn't
   reflect the bump, run "Update Scheduled Dates" from the MO form.

NF16 caught this exact bug at first live install: the
`@api.depends` path used to reference `bom.product_id.produce_delay`
which doesn't exist (`produce_delay` lives on `mrp.bom`, not on
`product.template`/`product.product`). Fixed; if you're on an old
install, `-u southbrook_estimating` brings the corrected compute.

**"The MO references a cut spec that's already been superseded by
an ECO."**

There's no per-MO cut-spec snapshot field today. The BoM compute
used the cut spec active at the time of MO creation; subsequent
ECOs don't retroactively re-run the math. If the ECO is critical,
the planner should:
1. Cancel the affected MO.
2. Reset to draft on the variant.
3. Recompute the BoM (which reads the now-active cut spec).
4. Spawn a fresh MO from the SO line (via `sale_mrp` re-trigger
   action).

The PLM-side fix for this is the planned per-order snapshot field
(`southbrook_cut_spec_version_id` on `sale.order` — TBD; not in
estimating addon today).

**"I cancelled an MO and now the analytics row says the order has
fewer panels than it did."**

`southbrook.order.analytics.capture` is idempotent — it rolls up
fields from the order at every Confirm. It does NOT subtract on MO
cancel. The analytics row reflects the SO state at the most recent
Confirm (or capture call). If you need to re-roll, call
`Analytics.capture(order)` manually after the cancellation — but
the analytics is intended as a confirmation snapshot, not a
real-time mirror.

## What the system is doing behind the scenes

The handoff sequence at Confirm, step-by-step:

1. User clicks Confirm. Form posts to `web/dataset/call_kw` with
   `model=sale.order, method=action_confirm`.
2. `sale.order.action_confirm` (Southbrook override) runs.
3. `super().action_confirm()` runs (Odoo standard +
   `sale_management` + `sale_mrp` chained inheritance).
4. Standard `sale.order.action_confirm` writes `state='sale'`,
   `date_order=now()`, posts a confirmation message to chatter.
5. `sale_mrp.SaleOrder._action_confirm` extension hooks fire. For
   each `order.order_line` whose `product_id.route_ids` includes
   Manufacturing route:
   - `mrp.production.create()` with `product_id`,
     `product_qty`, `origin`, `sale_line_id`, `bom_id` (resolved).
   - Procurement engine writes the BoM rollup via
     `mrp.bom._bom_find()`.
6. `Analytics.capture(order)` rolls up channel/tier/series/counts
   and creates or updates the `southbrook.order.analytics` row.
7. Form refreshes. Stat-button counters update. Lines lock.

Once an MO exists with a BoM, the BoM lookup chain for any panel
geometry question goes:

1. `mrp.bom._get_cut_constants()` returns the constants dict.
2. With `southbrook_plm` installed and a spec active:
   `southbrook.cut.spec._get_active().constants_dict()` is returned
   instead — every constant attribute (box_th, door_th, etc.) flows
   from the spec.
3. `mrp.bom._compute_panel_dimensions(W, H, D, family, door_count,
   drawer_count, finished_sides)` uses those constants to compute
   side_L, side_R, top, bottom, back, shelf, door tuples + counts +
   edge_banding scalar.

The constants are NAMED (uppercase module-level) so when the
canonical workbook (artifact #8 in CLAUDE.md §1) lands and changes
e.g. BOX_TH from 15.875 to 19.05 (3/4" instead of 5/8"), the swap
is mechanical — both cut list AND 3D geometry update because they
share the same imports.

The seam pattern is documented in the `southbrook_plm_deploy`
memory: REMOVING `_get_cut_constants` from `southbrook_estimating`
breaks every BoM operation in DBs with PLM installed with
`AttributeError: 'super' object has no attribute '_get_cut_constants'`.
Restored 2026-06-11 after a parallel session silently dropped it.

## Quiz (5 questions, applied)

**1.** An estimator confirms a 22-line order. The planner reports
"only 14 MOs spawned." Where do you look first?

> The 8 missing lines are probably non-cabinet products (hardware,
> install, service) without a Manufacturing route. Open the
> products: Inventory tab → Routes. If "Manufacture" is absent, no
> MO spawns — that's expected for service products. If a cabinet
> line failed to spawn an MO, the variant probably has no BoM
> assigned. Inspect `sale_line.product_id.bom_ids` — if empty,
> `_bom_find` returns no match and `sale_mrp` skips. Recovery:
> create a BoM for that variant.

**2.** The shop floor receives a Shop Copy PDF that shows an old
cut spec (door reveal 3mm) but PLM says the active spec is 5mm. The
MO was confirmed before the ECO. What's the correct resolution?

> Today, the BoM was computed against the 3mm spec at MO creation.
> There's no automatic re-compute on ECO. If the ECO is binding for
> this order: cancel the MO, reset the variant, recompute the BoM
> (which now reads 5mm via `_get_cut_constants` override), re-spawn
> the MO via `sale_mrp` from the SO line. If the ECO is forward-only
> (new orders use 5mm, this one ships at 3mm): document the
> exception on the MO chatter and run as-is. Long-term fix: the
> `southbrook_cut_spec_version_id` snapshot field on `sale.order`
> (TBD — not in estimating addon today).

**3.** `southbrook.order.analytics` shows `cabinet_count = 18` for
an order that has 22 lines. What's the discrepancy?

> `cabinet_count` = sum of `product_uom_qty` per line. Non-cabinet
> lines (hardware, install, service products) count in this sum if
> they have qty. But the analytics rollup uses `int(line.
> product_uom_qty)` for ALL lines that have a `product_id` —
> regardless of family. So 18 means: the sum of all line qtys was
> 18. Possibilities: 4 lines without product_id (free-text comments
> — skipped by the rollup); OR the cabinet lines genuinely had
> mixed qty (e.g. 4 lines at qty=1 + 14 lines at qty=1 = 18, with 4
> lines at qty=0). The rollup is "what the order said" — verify
> with the line list.

**4.** Lead time on a Maple-box MO shows the baseline 7 days when
you expect 21 (baseline + 14 maple). Where do you debug?

> The chain: `mo.date_planned_finished` ← Odoo scheduling using
> `mo.bom_id.effective_produce_delay` ← `_compute_effective_produce_delay`
> (`@api.depends("produce_delay", "southbrook_lead_time_extra")`)
> ← `southbrook_lead_time_extra` rolled up via
> `bom.product_id.product_template_attribute_value_ids.mapped(
> "product_attribute_value_id.lead_time_extra")`. Verify each step:
> 1. Variant has Maple attribute? `product_template_attribute_value_ids`
>    on the variant.
> 2. Maple `product.attribute.value.lead_time_extra` = 14.0 in the
>    seed? Check via the Attribute Values list.
> 3. `bom.southbrook_lead_time_extra` = 14.0? If not, the @api.depends
>    didn't propagate — try recomputing via developer mode.
> 4. `bom.effective_produce_delay` = `produce_delay + 14`?
> 5. Re-run Update Scheduled Dates on the MO.
> If step 2 shows 0, the seed is wrong; if step 3 shows 0, the
> rollup didn't run (cache invalidation issue); if step 5 doesn't
> fix step 1's date_planned_finished, your Odoo scheduling has
> another override in the chain.

**5.** An estimator says "I want the planner to see my customer
notes — should they go on the line description?" What's your
guidance?

> Customer notes on order lines DO NOT flow to MOs by default. The
> MO carries `origin` (the SO name, free-text), and that's it. If
> the customer note is binding ("must have soft-close on all base
> cabinets"), it should be captured as a configured attribute
> (soft-close attribute pick) so it flows through the variant and
> the BoM. If it's a non-binding note ("customer prefers paint
> applied within 5 days of delivery"), write it on the SO chatter
> and verbally communicate. The MO chatter is the planner's first
> stop — copy the relevant SO chatter to the MO if needed. This is
> a real product gap; per Course 8 audit findings, a "shop notes"
> field that propagates SO line → MO is on the candidate list.

---

## What this lesson does NOT cover

- The Order Builder UI walkthrough — lesson 8.2.
- Pricing mechanics — lesson 8.3.
- The QWeb reports themselves (Signature Spec Sheet, Shop Copy,
  Door Order) — lesson 8.5.
- Versioning / revision chains — lesson 8.6.
- The PLM addon internals (`southbrook.cut.spec`,
  `southbrook.eco.order`) — Course 4 (PLM + Design).
- The production-side workflow (workcenters, work orders, shop
  floor) — Course 1 (Workcenter Operators) and Course 2
  (Production Planning).
- The `sb.kitchen.project` model — lives in `southbrook_kitchen_mrp`,
  not in estimating. Covered in Lesson 2.1.
- The Hermes platform's interaction with confirmed orders — see
  the Hermes spec.
