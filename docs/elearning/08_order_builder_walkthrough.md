---
course: 8 — Estimating Deep Dive
chapter: 8.2
title: Order Builder Walkthrough — Blank Quote to Confirmed-for-Engineering, Field by Field
duration: 50 minutes
audience: Estimator. You build quotes every day. This lesson covers every keystroke from "I have a kitchen design on my desk" to "the planner has an MO" — including the auto-compute behaviour you can't see and the validation gates that prevent you from shipping broken quotes downstream.
prereqs: Lesson 5.1 (Configurator basics), Lesson 5.2 (intro walkthrough), Lesson 8.1 (architecture overview)
custom_modules: southbrook_estimating, product_configurator_sale, product_configurator_mrp, sale_mrp
---

# Order Builder Walkthrough — Blank Quote to Confirmed-for-Engineering, Field by Field

## Who this lesson is for

You're the estimator. You've done the basic walk-through (lesson 5.2)
and you can build a passable quote in 20 minutes. This lesson is what
turns that into a 12-minute quote where nothing breaks downstream —
because you know exactly which fields are auto-computed, which are
manual, and where the validation gates sit. Read this before your next
kitchen.

## Where this lives on the site

Two entry points, same action (`action_order_builder`):

> **Southbrook Estimating → Order Builder** (top-level app drawer)
> **Sales → Orders → Order Builder** (Build-Spec §2.2 placement)

Both open the same filtered `sale.order` list scoped to `state in
('draft', 'sent')`. The list view shows the standard sale columns plus
the Southbrook channel + savings columns when configured.

For configuration on a per-cabinet basis:

> **(from inside a line)** Configure (button injected by
> `product_configurator_sale`)

For the printable PDF:

> **(from the order form)** Print → Signature Spec Sheet

## What your screen shows

The Order Builder form is `sale.order` with Southbrook xpaths from
`view_order_form_southbrook`. Top to bottom, here's what you see and
where it comes from:

- **ILLUSTRATIVE SEED banner** (xpath 1) — yellow alert above the
  sheet, gated by `context.get('seed_mode_canonical')`. You should
  NOT see this in production. If you do, your demo context flag is
  leaking.
- **Stat-button row** (top right of the sheet) — Odoo standard stat
  buttons, plus **Duplicate as Draft** (xpath 3) calling
  `action_duplicate_as_draft`. The button shows for users in
  `sales_team.group_sale_salesman`.
- **Customer block** — `partner_id` (standard); inject after it:
  - `parent_order_id` — readonly, invisible if no parent.
  - `version` — readonly, shown only in developer mode
    (`groups="base.group_no_one"`).
- **Pricelist** — standard Odoo `pricelist_id`. Set automatically by
  the `_onchange_partner_id_southbrook_pricelist` hook reading
  `partner_id.channel` (and `tradesperson_tier`) through
  `_resolve_channel_pricelist`. You CAN override it manually — but
  read the warning in "Common mistakes" before you do.
- **Notebook → Order Lines tab** (standard, with xpath additions):
  - `zone` column (xpath 4) — optional="show", default visible.
  - `zone_label` column (xpath 4) — optional="hide" by default; only
    visible when `zone == 'other'`.
  - Lines auto-group by `zone` (xpath 5) — `default_group_by="zone"`
    + `expand="1"` so the groups open by default.
  - `price_subtotal` carries a `sum="Zone Subtotal"` aggregation
    (xpath 6) shown in the zone group header row.
  - Each line shows the standard **Configure** button from
    `product_configurator_sale`.
- **Notebook → 3D Kitchen Preview tab** (xpath 7) — 520px high panel
  hosting the OWL `kitchen_viewport` widget. Calls
  `sale.order.get_kitchen_3d_payload` at render time.
- **Notebook → Other Info, Customer Signature tabs** — standard Odoo.
- **State pipeline (top right)** — standard `sale.order.state`:
  `draft` → `sent` → `sale` → `done`. Plus `cancel` off-pipeline. There
  are NO Southbrook custom states. The "submitted" milestone is
  captured separately in `southbrook_submitted_date` (Datetime).

## Your daily flow

The order matters. Working out of sequence is the source of 80% of
the recoverable mistakes in this lesson.

**1. Read the design (5 min). No keyboard yet.**

Before opening Odoo, look at what's on your desk:
- Cabinet count by family (Base / Wall / Tall / Vanity / Accessory /
  Worktop).
- Series intent (Contractor, Contemporary, Elegance, Signature).
- Box material (White Melamine baseline, or Maple +10% +2 weeks).
- Door style requested.
- Finish/colour requested.
- Hardware requests (handles, soft-close, special hinges).
- Custom zones beyond Base Run / Wall / Tall / Island / Accessory
  (e.g. Mudroom, Laundry, Bar).

Spend 5 minutes here. The most expensive mistake is starting Odoo,
building 18 lines, and discovering the customer wanted Maple on a
Contractor series — which Rule 2 blocks (see lesson 8.3).

**2. Customer pick + channel resolution (1 min).**

> Southbrook Estimating → Order Builder → Create

- Type the customer name in `partner_id`. If they exist, pick them.
- If they don't, click Create-and-Edit. In the partner form:
  - Set **Sales tab → Southbrook Channel** (`channel` on
    res.partner). The six values mean exactly what their labels
    say. The default is `retail`.
  - If channel = tradesperson, set **Tradesperson Tier**. The
    `_onchange_channel_default_tier` defaults a new tradesperson
    to Tier 3 (the entry tier). Override to 1 or 2 if known.
- Save the partner; return to the order.
- The `_onchange_partner_id_southbrook_pricelist` hook fires
  automatically: it calls `_resolve_channel_pricelist(partner)`
  which dispatches through `_CHANNEL_PRICELISTS` or
  `_TRADESPERSON_TIER_PRICELISTS` and writes `pricelist_id`.

**Sanity check:** glance at the **Pricelist** field. For a Tier 3
tradesperson, it should read "Contractor Tier 3 (-35%)". If it reads
"Retail (List Price)", either the channel didn't save on the
partner record, or you forgot to set it.

**3. Order line construction (the loop, ~30 sec per line).**

For each cabinet in the design, click **Add a line**:

a. **Product** (`product_id`) — type `SB-` and pick. The 12 Q8-locked
   anchors:
   - `SB-WALL-1DR`, `SB-WALL-2DR`, `SB-BASE-1DR`, `SB-BASE-2DR`
   - `SB-DRAWER`, `SB-SINK-BASE`
   - `SB-TALL-PANTRY`, `SB-TALL-OVEN`
   - `SB-CORNER`, `SB-VANITY`
   - `SB-ACCESSORY` (with `accessory_type` sub-attribute:
     end_panel/filler/cornice/pelmet/plinth)
   - `SB-WORKTOP`

b. **Zone** (`zone`) — Selection: Base Run / Wall / Tall / Island /
   Accessory / Other. Default `base_run`. The line will auto-group
   under its zone in the embedded list.

c. **Zone Label** (`zone_label`) — appears only when `zone == 'other'`
   (the view xpath enforces `invisible="zone != 'other'"`). Free
   text — "Laundry", "Mudroom", "Bar", "Bath 2". When you change
   `zone` away from `other`, the `_onchange_zone_clear_label` hook
   clears this field automatically (so a stale label doesn't ride
   along after a zone change).

d. **Configure** button — from `product_configurator_sale`. Click it
   to open the OCA wizard. Walk the 11 attributes (or 13 — Family,
   Family Subtype for corner cabinets, Width, Height, Depth, Series,
   Box Material, Door Style, Finish, Hinge Side, Finished Sides,
   Door Count, Handle). The wizard groups them into 4 step buckets
   per `data/config_steps.xml`:
   - Construction (Family, Family Subtype, Width, Height, Depth)
   - Door & Finish (Series, Door Style, Finish)
   - Hardware (Handle, Hinge Side, Door Count)
   - Interior (Finished Sides, Accessories)

   When you Finish the wizard, a `product.product` variant
   materialises (`create_variant='dynamic'`) — or an existing one is
   reused if you happen to pick the same combo as another line.

e. **Quantity** (`product_uom_qty`) — usually 1 per line, but pairs
   of identical wall cabinets are a valid case for qty=2.

f. **Price** (`price_unit`) — recomputes automatically from the
   resolved pricelist + the variant's `list_price` (+ any
   `price_extra` on variant attribute values, e.g. Maple +10%).

g. Watch the right side of the row: `sb_panel_count` and
   `sb_door_count` recompute live via `_compute_sb_panel_rollup`.
   These are NOT stored — they're live-computed every time the line
   is accessed. If `sb_panel_count` reads 0, see the Common
   Mistakes section.

A typical mid-range kitchen has 18-25 lines. Hard ceiling is around
50 (any more and the form gets sluggish; consider splitting into
phased orders).

**4. Hardware + install + accessory lines (varies).**

Cabinets are configured. You still need:

- **Hardware lines** — most hardware is computed per carcass from
  `_compute_panel_dimensions` (handle_count, hinge_pair_count,
  drawer_slide_pair_count). You add a hardware order line manually
  ONLY when:
  - The customer wants an upgraded handle (catalog product, e.g.
    `HW-PULL-BLACK-128`).
  - The customer is supplying their own appliance pulls.
  - A specialty hinge (corner pocket, blind-corner mechanism).

- **Install / service lines** — service products like `INST-DAY`,
  `DELIVERY-GTA`, `SITE-VISIT`. Not configurable; just SKU + qty.

- **Filler / end-panel / cornice / pelmet / plinth lines** —
  `SB-ACCESSORY` with `accessory_type` set. These render as a
  carcass-less "end_panel" geometry in the 3D preview
  (`_3d_payload_accessory` short-circuit).

**5. Inspect the 3D Kitchen Preview (~30 sec).**

Open the **3D Kitchen Preview** tab. The OWL component calls
`get_kitchen_3d_payload()`:

- Base Run + Tall + Accessory lines share the **ground** cursor
  (advance left-to-right at Y=0).
- Wall lines share the **wall** cursor (Y=1400mm, share X range with
  base for visual alignment).
- Island lines sit on their own Z plane (Z=-2500mm).
- Other lines tuck even further back (Z=-3000mm).
- Worktops always sit at Y=762mm and share the ground X cursor
  (override).

If your kitchen run renders weirdly (e.g. a wall cabinet floating mid-
air over nothing because no base is under it), you've probably mis-
zoned a line. Fix the `zone` on the line; the preview re-renders.

**6. The Q7 smoke-test swap (~30 sec, every order).**

This isn't a phase-1 gate exercise — do it on every real order as a
sanity check:

- Note the order total.
- Open the partner field, switch to **Demo Tradesperson (Tier 3)**.
- All lines reprice via the Tier 3 pricelist. Total should drop ~35%
  (against cost+5% floor).
- Switch back to your real customer.
- Total returns to its original value.

If it doesn't return — i.e. a line is "stuck" — the line's
`price_unit` was manually overridden. See Common Mistakes.

**7. Validation gates before sending.**

Before clicking Send or Confirm, sanity check:

- **Every line has a non-zero `sb_panel_count`.** Open Other Info or
  hover the line to see it. Zero = unconfigured.
- **Every Wall line is in zone=`wall`.** Otherwise it'll render at
  floor level in the 3D preview, and downstream planners will treat
  it as a base.
- **The pricelist matches the partner's channel.** Look at the
  Pricelist field — it should match the channel label.
- **`southbrook_submitted_date` is empty for orders that haven't been
  submitted yet.** This is set by the portal "Request a Price"
  action; if it's set on a draft you just created, something's
  wrong.

**8. Send → Confirm → MO creation.**

- Click **Send by Email** with the Signature Spec Sheet attached.
  State moves to `sent`.
- Customer signs.
- Click **Confirm**. `action_confirm` override runs:
  1. `super().action_confirm()` — standard Odoo, state → `sale`,
     creates `mrp.production` records via `sale_mrp`.
  2. `Analytics.capture(order)` — writes one
     `southbrook.order.analytics` row with channel, tier, dealer_id,
     series (predominant), cabinet_count, panel_count, door_count.
- The planner now sees the MOs in Manufacturing.

## Common mistakes + how to recover

**"I built 22 lines and the 3D Kitchen Preview is empty."**

The OWL component only renders SKUs in `_SKU_DEFAULTS`. Non-SB
products (hardware, service lines) are skipped. If your kitchen is
all hardware lines and no cabinets, you'll see an empty scene with
the default camera (this is the `cumulative_x == 0` branch in
`get_kitchen_3d_payload`). Add some SB-* cabinet lines to see the
3D render.

**"I switched the customer and the lines didn't reprice."**

Three possibilities:
1. The partner has no `channel` set — defaults to `retail`. Fix
   the partner record.
2. A line's `price_unit` was manually overridden (you typed in the
   price field directly). The pricelist link is broken for that
   line. Recovery: re-trigger by changing then restoring the
   quantity on the line, or duplicate the order and reconfigure
   cleanly.
3. The `_onchange_partner_id_southbrook_pricelist` hook didn't fire
   because the partner pick happened via XML import or scripting
   bypassing onchange. Manually set the pricelist or trigger an
   onchange.

**"`sb_panel_count` reads 0 on a line I configured."**

Most often: the variant has no `product_template_attribute_value_ids`
because the wizard was cancelled before Finish. The
`_sb_derive_dimensions` helper then falls back to parsing
`line.name`, and if `line.name` is just the product display name
without a width hint (e.g. "Base 1-Door"), it falls back to
defaults — but the `panel_cut_list` import from `southbrook_dims`
might also have failed (it lives in `/srv/shared` via PYTHONPATH; on
a misconfigured environment, the `try/except` returns 0). Open the
Odoo log: if you see "ModuleNotFoundError: southbrook_dims", that's
the env. If not, the line genuinely lacks variant data — reconfigure.

**"Zone Label is showing on every line and I can't get rid of it."**

The view xpath has `invisible="zone != 'other'"` — if you see it on
every line, the view inheritance broke and the legacy view is
rendering. Clear browser cache (developer mode → Reload Views) and
re-open. If still broken, your local DB is missing the latest view
update — run `-u southbrook_estimating`.

**"I clicked Confirm but no MOs appeared."**

Several possible causes — but the most common is that one or more
lines lack a variant with a BoM. The `sale_mrp` bridge creates one
`mrp.production` per line's variant; if a line has a "draft" variant
that was never finished in the wizard, `sale_mrp` skips it. Open
each line and check the Configure status (if the button still reads
"Configure" rather than "Re-configure", the wizard wasn't finished).

Other possibilities:
- `sale_mrp` isn't installed. Check the modules list.
- The product's `route_ids` don't include "Manufacture". Edit the
  product template's Inventory tab.
- The order confirmed but moved straight to `done` without creating
  MOs (e.g. service products only). Verify by looking at
  `order.production_ids` (in developer mode).

**"I duplicated an order as draft, edited a line, and the parent
order also changed."**

This shouldn't happen — `copy()` deep-clones order_lines. If it did,
one of two things:
1. You edited a `product.product` variant directly (via the product
   form), and that variant is shared between both orders. Variant
   edits propagate to every line that references it. Recovery:
   re-configure the affected line on the duplicate so a new variant
   is materialised.
2. You edited the partner record (e.g. changed the partner's
   default address). Partner is shared across both orders by ID.
   This is by design.

## What the system is doing behind the scenes

Every line save triggers:

1. `_compute_sb_panel_rollup` recompute (live, not stored).
2. Odoo's standard pricing chain: `_compute_price_unit` on the line
   reads the order's `pricelist_id` and the variant's `list_price` +
   `price_extra` from variant attributes.
3. If `zone == 'other'` and you change zone, the onchange fires
   `_onchange_zone_clear_label` to blank `zone_label`.

The Duplicate-as-Draft action does:

```
new_order = self.copy({
    "parent_order_id": self.id,
    "version": self.version + 1,
    "state": "draft",
})
```

— so the new order is in `draft`, its `parent_order_id` points back
at this one, and its `version` is one higher. Lines copy with their
config_session references intact.

When you confirm, `action_confirm` override:

```
result = super().action_confirm()  # creates MOs via sale_mrp
for order in self:
    Analytics.capture(order)       # NF1 AI data spine
return result
```

`Analytics.capture` is idempotent — searching by `sale_order_id` and
writing or creating. The analytics row carries `cabinet_count` =
sum of `product_uom_qty`, `panel_count` = sum of `sb_panel_count`,
`door_count` = sum of `sb_door_count`, plus `series` = most-common
Series attribute via `Counter.most_common(1)`.

The 3D Kitchen Preview tab calls `get_kitchen_3d_payload` which:
- Sets up four cursors (ground / wall / island / other) at X=0.
- Loops `order_line` in display order.
- Per line: looks up the SKU in `_SKU_DEFAULTS`, computes panel
  geometry via `_compute_panel_dimensions`, translates each panel
  by `(x_offset, y_floor, z_offset)` where `x_offset` is the zone
  cursor's current position + cabinet half-width, `y_floor` is from
  `_ZONE_LAYOUT[zone][1]` (or 762 for worktops), and `z_offset` is
  from `_ZONE_LAYOUT[zone][2]`.
- Advances the cursor by the cabinet's full width.
- Concatenates per-line panels with a `L{line.id}_` prefix.
- Frames the camera around the widest cursor's extent.
- Returns panels + metadata + camera + bounds.

The OWL component (`cabinet_viewport.esm.js`) consumes this same
payload shape regardless of whether it came from a single-cabinet
wizard or the multi-cabinet order tab — dispatched by `resModel`
internally.

## Quiz (5 questions, applied)

**1.** You build an order with 14 lines. Eight of them are SB-BASE-2DR
in zone=base_run. The 3D Kitchen Preview shows all eight at the same
X=0 spot — overlapping. What did you forget?

> Nothing — that's the bug. Re-check: did you set `zone` on each
> line? If `zone` is blank (rare; the default is `base_run`), the
> payload uses `("ground", 0, 0)` defaults. If all eight are
> overlapping at X=0, then `get_kitchen_3d_payload` ran with a
> broken cursor advance — the cursor at line 312 of `sale_order.py`
> reads `cursors[cursor_name] += w` AFTER the panel translation
> uses `cursor + w/2` as offset. If cursors is somehow reset per
> iteration, all cabinets land at the same X. Inspect the JSON-RPC
> response in the browser dev tools — if each cabinet has the same
> `pos.x`, the cursor logic broke. Escalate.

**2.** A customer changed their mind about cabinet 7 of 18 — wants
the door colour different. Do you re-configure that line, or
duplicate the order?

> Re-configure that line. Duplicate-as-Draft is for when the customer
> wants ITERATIVE-DESIGN — multiple revisions tracked via
> parent_order_id. A single colour swap on one cabinet doesn't
> warrant a new version chain entry. Open line 7's Configure button,
> change the Finish attribute, finish the wizard, save. The new
> variant materialises (or reuses an existing one), price recomputes
> against the pricelist, and the analytics row will get updated at
> next confirm.

**3.** You add a line with `SB-WORKTOP`. In the 3D preview it sits at
floor level, not at counter height. What's wrong?

> Worktops have a FAMILY-based override at line 273 of
> `get_kitchen_3d_payload`: if `fam == "worktop"`, the cursor name is
> forced to `_WORKTOP_CURSOR` ("ground") and `y_floor` is forced to
> `_WORKTOP_Y_FLOOR` (762mm). If the worktop is rendering at floor,
> either: (a) the SKU isn't `SB-WORKTOP` exactly (so the
> `_SKU_DEFAULTS` lookup fails and the family resolves to "base"); or
> (b) the line's product_id is missing. Check the line's product
> default_code in developer mode.

**4.** Your audit found a line where `sb_panel_count = 0` but the
line is fully configured. Where do you look first?

> The `_compute_sb_panel_rollup` method does
> `from southbrook_dims import panel_cut_list` and on any exception
> returns 0,0,width. The most common cause is `southbrook_dims` not
> being on `PYTHONPATH` in the container (lives in `/srv/shared` per
> the in-line comment). Verify with `docker exec ... python -c "import
> southbrook_dims; print(southbrook_dims.__file__)"`. Second cause:
> the `panel_cut_list` call raised because the family or width
> derivation returned something `panel_cut_list` doesn't recognise.
> Inspect via developer mode → "View Field" on `sb_panel_count` to
> see the compute exception trail.

**5.** You confirm an order and the Manufacturing menu shows the MOs.
But `southbrook.order.analytics` has no row for this order. What's
broken?

> The `action_confirm` override expects `Analytics.capture(order)` to
> run after `super().action_confirm()`. If the analytics row is
> missing, either: (a) the override didn't fire — another module's
> `action_confirm` short-circuited via early return; (b) the
> `Analytics.capture` raised silently — check the Odoo log;
> (c) you confirmed via a script that bypassed `action_confirm`
> (direct `state = 'sale'` write). Recovery: manually call
> `self.env["southbrook.order.analytics"].capture(order)` once for
> the affected order; the method is idempotent.

---

## What this lesson does NOT cover

- The architectural map of `southbrook_estimating` — lesson 8.1.
- The pricing deep dive (channel resolution, dealer 50%-off math,
  tradesperson tiers, refacing margin target) — lesson 8.3.
- Quote → MO handoff details, cut-spec snapshot semantics — lesson
  8.4.
- Report generation timing + field mapping — lesson 8.5.
- Versioning and customer-changed-their-mind handling — lesson 8.6.
- OCA configurator wizard internals — its own upstream documentation.
- The customer-facing one-page configurator — Phase 2, not yet
  shipped.
