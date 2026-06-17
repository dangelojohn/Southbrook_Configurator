---
course: 12 — Kitchen Ops Deep Dive
chapter: 12.7
title: Cut Lists, Hardware Packages, Production Packages — The Shop-Floor Trio
duration: 40 minutes
audience: Project Manager + Production Planner (the two who own these records day-to-day)
prereqs: Course 1 lesson 1.7 (Reading a Cut Spec). Familiarity with `mrp.production` (Odoo native MO).
custom_modules: southbrook_kitchen_mrp, southbrook_manufacturing_intelligence, southbrook_hardware_catalog, southbrook_dealer_portal
---

# Cut Lists, Hardware Packages, Production Packages — The Shop-Floor Trio

## Who this lesson is for

You're the PM or planner who has to answer "what does the floor
actually get when we release this MO?" The answer is **three linked
records**, each owned by `southbrook_kitchen_mrp`, plus a fourth
read-side projection from `southbrook_manufacturing_intelligence`
that decorates them with MI checks. This lesson is the inside view
of that record trio — what each contains, when each is created in
the project lifecycle, how the MI engine reads them, and how the
dealer portal exports them.

Get the trio wrong and the floor cuts wrong panels, picks wrong
hardware, and the customer's cabinets are scrap.

## Where this lives on the site

For the planner:

> **Southbrook Kitchen → Production Packages**

The list view of `sb.production.package` records. One per MO. The
menu is in
`southbrook_kitchen_mrp/views/southbrook_kitchen_mrp_menus.xml`.

> **Southbrook Kitchen → Cut Lists**

The list view of `sb.cutlist` records. One per MO (typically),
created by the production package's `generate_from_mo`.

> **Southbrook Kitchen → Hardware Packages**

The list view of `sb.hardware.package` records. One per MO,
created alongside the cutlist.

For the MI-decorated planner view:

> **Southbrook PM → MI Production Board**

A list of `sb.production.package` records decorated with the
`x_mi_status` / `x_mi_blocker_count` / `x_mi_warning_count` /
`x_mi_next_action` fields. Same model, MI-extended view.

From inside an MO:

> **Manufacturing → Manufacturing Orders → \<open one\>**

The `mrp.production` form. Links to the production package via the
package's `mo_id` field; reverse navigation via smart buttons (when
present).

For the dealer (export endpoint):

> `https://southbrookcabinetry.space/my/dealer/production-package/<pkg_id>/kd`
> `https://southbrookcabinetry.space/my/dealer/production-package/<pkg_id>/installation-pdf`

Routes defined in
`southbrook_dealer_portal/controllers/main.py`. Dealer-channel
partners only.

## The model trio — what each holds

### `sb.production.package` (the orchestrator)

Defined in
`southbrook_kitchen_mrp/models/sb_production_package.py`. The
**bundle** record that links a cutlist + a hardware package to a
single MO and carries the shop-floor state machine.

Fields:

- **Name** (`name`) — auto-sequence (`sb.production.package`).
- **Manufacturing Order** (`mo_id`) — Many2one to `mrp.production`,
  required, `ondelete=cascade`.
- **State** (`state`) — Selection:
  - `draft` — initial
  - `ready` — written by `generate_from_mo` once cutlist + hardware
    package created
  - `released` — operator-facing state (the floor is working it)
  - `done` — closed
- **Cut List** (`cutlist_id`) — Many2one to `sb.cutlist`,
  `ondelete=restrict`.
- **Hardware Package** (`hardware_package_id`) — Many2one to
  `sb.hardware.package`, `ondelete=restrict`.
- **Has Pricing Pending** (`has_pricing_pending`) — related from
  hardware_package_id.

Plus MI-extended fields (added by
`southbrook_manufacturing_intelligence/models/sb_production_package.py`):

- **MI Status** (`x_mi_status`) — Selection: `ok` / `review` /
  `blocked`. Computed from the severities of linked
  `southbrook.mi.check` rows.
- **MI Checks** (`x_mi_check_ids`) — One2many to
  `southbrook.mi.check` filtered by `production_package_id = self`.
- **MI Blockers** (`x_mi_blocker_count`) — Integer.
- **MI Warnings** (`x_mi_warning_count`) — Integer.
- **MI Install Warnings** (`x_mi_install_warning_count`) — Integer,
  the count of `category = install` warnings (filler / scribe /
  tall cabinet review).
- **MI Next Action** (`x_mi_next_action`) — Text. The top
  recommendation, or "Manufacturing intelligence checks are clear."
- **MI Yield %** (`x_mi_yield_pct`) — Float. Sheet yield from cut
  summary.
- **MI Waste Area m²** (`x_mi_waste_area_m2`) — Float.
- **MI Edge Band (m)** (`x_mi_edge_band_m`) — Float.

Constraints:

- `@api.constrains("mo_id"): _check_unique_mo` — only one
  production package per MO (enforced at Python level because
  Odoo 19 deprecated `_sql_constraints`).

### `sb.cutlist` + `sb.cutlist.line` (the panels)

Defined in `southbrook_kitchen_mrp/models/sb_cutlist.py`. The
panel cut list for one MO.

`sb.cutlist`:

- **Name** (`name`) — auto-sequence.
- **MO** (`mo_id`) — Many2one to `mrp.production`,
  `ondelete=cascade`.
- **State** (`state`) — Selection: `draft` / `exported` /
  `nested` / `done`. Tracked.
- **Lines** (`line_ids`) — One2many to `sb.cutlist.line`.
- **Line Count** (`line_count`) — computed.
- **Nesting Result JSON** (`nesting_result_json`) — Text. Round-trip
  stash from the nesting tool.

`sb.cutlist.line`:

- **Panel Name** (`panel_name`) — Selection (7 fixed values:
  `side_L`, `side_R`, `top`, `bottom`, `back`, `adjustable_shelf`,
  `door`).
- **Sequence** (`sequence`) — Integer, default 10.
- **Qty** (`qty`) — Integer, default 1.
- **Length / Width / Thickness (mm)** (`length_mm`, `width_mm`,
  `thickness_mm`) — Floats.
- **Substrate** (`substrate`) — Selection: `melamine_white_5_8` /
  `melamine_oak_5_8` / `mdf_5_8` / `hardboard_1_4` / `ply_3_4`.
- **Grain Direction** (`grain_dir`) — Selection: `with_grain` /
  `cross_grain` / `no_grain`.
- **Edge Banding Config** (`edge_banding_config`) — Text (JSON).

**The toe-kick contract.** The panel formula
(`shared.southbrook_dims.panel_cut_list`) returns a panel dict that
INCLUDES a `toe_kick` key as a METADATA descriptor (dict). The
cutlist generation INTENTIONALLY skips it because toe-kick is
integrated into the side panels and emitting it as a cutlist line
would create a phantom panel. The contract is enforced by tests
and the generation code asserts the iteration explicitly. This is
the only place in the platform where "missing record" is the
correct outcome — never look for a toe-kick cutlist line.

### `sb.hardware.package` + `sb.hardware.package.line` (the hardware)

Defined in
`southbrook_kitchen_mrp/models/sb_hardware_package.py`. The
resolved hardware pick list for one MO. Generated by calling
`env['southbrook.hardware.catalog'].resolve(...)` (owned by
`southbrook_hardware_catalog`), which aggregates per_door +
per_drawer + per_shelf + per_cabinet + per_family rules into one
line per SKU.

`sb.hardware.package`:

- **Name** (`name`) — auto-sequence.
- **MO** (`mo_id`) — Many2one to `mrp.production`,
  `ondelete=cascade`.
- **State** (`state`) — Selection: `draft` / `picked` /
  `delivered`. Tracked.
- **Lines** (`line_ids`) — One2many to
  `sb.hardware.package.line`.
- **Line Count** (`line_count`) — computed.
- **Has Pricing Pending** (`has_pricing_pending`) — computed from
  any line whose product has `x_pricing_pending = True`.

`sb.hardware.package.line`:

- **Package** (`package_id`) — Many2one, `ondelete=cascade`.
- **Product** (`product_id`) — Many2one to `product.product`,
  filtered to hardware SKUs
  (`[('x_hardware_category', '!=', False)]`).
- **Qty** (`qty`) — Integer.
- **Pricing Pending** (`pricing_pending`) — related from
  `product_id.x_pricing_pending`.
- **Hardware Category** (`hardware_category`) — related from
  `product_id.x_hardware_category` (`hinge` / `pull` / `slide` /
  `mounting`).
- **Brand** (`brand_id`) — related from
  `product_id.x_hardware_brand_id`.

## When each record gets created

The lifecycle of the trio:

### 1. At sale.order confirmation

The `action_confirm` override on `sale.order` (in
`southbrook_premium_orchestration`) creates the project.task spine
and any new `mrp.production` records from order lines. **No
production package, cutlist, or hardware package is created yet.**
The MO has a routing and a BoM but no Southbrook trio.

### 2. At gate review (planner / engineer action)

When the engineer is about to flip Cutlist Approved on the release
gate (lesson 12.4), they need a cutlist to look at. They (or the
planner) open the MO and click the **Generate Production Package**
action button OR run
`env['sb.production.package'].generate_from_mo(mo, width, height,
depth, family, door_count, drawer_count, soft_close)` from a shell.

`generate_from_mo` is the ONE orchestration method that creates the
trio. It:

1. **Deletes any existing package** for the MO (idempotency — calling
   twice rebuilds rather than duplicating). Deletion order matters
   because of `ondelete='restrict'` on the m2o references: the
   package is deleted FIRST, then the cutlist + lines, then the
   hardware package + lines.
2. **Calls `shared.southbrook_dims.panel_cut_list`** to get the
   geometry dict. Same module the FreeCAD bridge renders from, so
   cutlist geometry is guaranteed identical to rendered geometry.
3. **Creates the `sb.cutlist`** for the MO, generates lines via
   `generate_lines_from_panel_dict` (skipping toe_kick).
4. **Calls `env['southbrook.hardware.catalog'].resolve`** with the
   cabinet family, door count, drawer count, shelf count, soft_close
   flag. Returns a list of (product, qty) tuples.
5. **Creates the `sb.hardware.package`** and generates lines via
   `generate_lines_from_resolution`.
6. **Creates the `sb.production.package`** linking both, sets
   `state = 'ready'`.

After this runs, the MI engine has data to score:
`action_recompute_manufacturing_intelligence` on the package
walks the cutlist + hardware package + install context and writes
`southbrook.mi.check` rows + the per-package
`x_mi_status` / `x_mi_blocker_count` / etc.

### 3. At dealer / nesting export

When the cutlist is sent to the cutting / nesting division:

- The planner calls `cutlist.to_nesting_envelope()` → returns a
  deterministic JSON dict with `schema: "southbrook.nesting.v1"`,
  cutlist_id, mo_id, and the panel list.
- The nesting division processes the envelope, returns a payload
  with sheets_used / yield_pct / waste_pct.
- The planner calls `cutlist.from_nesting_result(payload)` →
  validates `schema == southbrook.nesting.v1`, stores the
  `nesting_result_json`, sets `state = 'nested'`.

For KD-channel (knockdown) dealers:

- The dealer logs in to the portal, lands at
  `/my/dealer/orders`.
- Selects a production package.
- Hits `/my/dealer/production-package/<pkg_id>/kd` →
  `kd_export()` controller method calls
  `package.export_kd_envelope()` (Phase-1 method on
  `sb.production.package`, **not yet documented in lesson scope —
  see TBD below**) and returns a JSON download.
- Or hits
  `/my/dealer/production-package/<pkg_id>/installation-pdf` →
  `installation_pdf()` calls `package.export_installation_pdf()`,
  returns a PDF download.

The `_require_dealer` guard in the controller ensures only
`channel = 'dealer'` partners get through. Tradesperson partners
are blocked (Phase-1 limitation; see audit finding 4 in
`docs/elearning/README.md`).

### 4. At end of MO

When the MO is done (`state = 'done'`), the production package's
state moves to `done` via a manual or operator action. The cutlist
and hardware package states should also be `done`.

## The relationship to `mrp.production`

Each record in the trio has a Many2one `mo_id` to
`mrp.production`. There's no direct link from `mrp.production`
back to the trio — you find the package via search:

```python
package = env['sb.production.package'].search(
    [('mo_id', '=', mo.id)], limit=1
)
```

The MO carries the:
- **Quantity** (`product_qty`) — how many cabinets.
- **Routing** (`routing_id`) — workcenter sequence (cutting →
  edge banding → CNC boring → assembly → ...).
- **BoM** (`bom_id`) — bill of materials (panels + hardware as
  components).

The trio carries the:
- **Cutlist** — the panel-level CUT spec (lengths, substrates,
  grain).
- **Hardware package** — the resolved hardware PICK list (which
  hinges, which pulls, qty).
- **Production package** — the BUNDLED state for the shop floor.

The BoM is the BUSINESS contract ("this MO uses these
components"). The trio is the SHOP-FLOOR detail ("here's how to
cut and pick those components"). Both must agree; the MI engine's
**BoM Verified** sub-signal checks them.

## The per-package MI fields — what each tells you

These live on `sb.production.package` via
`southbrook_manufacturing_intelligence`:

- **`x_mi_status`** (`ok` / `review` / `blocked`) — banded status.
  Any blocker → `blocked`. Any warning (no blocker) → `review`.
  Otherwise `ok`.
- **`x_mi_blocker_count`** — count of blocker-severity checks on
  this package. Zero is green.
- **`x_mi_warning_count`** — count of warning-severity checks.
- **`x_mi_install_warning_count`** — count of install-category
  warnings specifically (lift, scribe, filler).
- **`x_mi_next_action`** — Text. The TOP blocker's recommendation
  (or top warning if no blocker, or "Manufacturing intelligence
  checks are clear").
- **`x_mi_yield_pct`** — from cut summary (panel_area /
  gross_sheet_area × 100). Below 45% triggers a "Low sheet yield"
  warning.
- **`x_mi_waste_area_m2`** — leftover sheet area. Above 0.09 m²
  triggers a "Reusable offcut" info check.
- **`x_mi_edge_band_m`** — total edge banding length the cutlist
  requires. Helps the edge bander operator pre-stage tape.

The action button **Recompute Manufacturing Intelligence**
(`action_recompute_manufacturing_intelligence`) on the package
form fires `env['southbrook.mi.engine']._recompute_package(package)`
synchronously. Use it after editing cutlist lines manually or
after a hardware SKU pricing update.

## Your daily flow

### The planner (per release)

1. Open the MO from Kitchen Jobs (lesson 12.3) or from
   Manufacturing → MOs.
2. Check whether a production package exists. If not, click
   **Generate Production Package** OR run `generate_from_mo` from
   shell.
3. Open the package. Verify:
   - Cutlist line count > 0 and substrate is set on every line.
   - Hardware package line count > 0 and `has_pricing_pending =
     False`.
   - `x_mi_status = ok` (or `review` for non-blocking).
4. If `x_mi_blocker_count > 0`, open `x_mi_check_ids` tab, read
   each blocker. Resolve before the gate review (lesson 12.4).
5. Hand off to the engineer for gate review.

### The PM (weekly)

- Filter MI Production Board by `has_pricing_pending = True`. These
  packages have hardware lines whose product has
  `x_pricing_pending = True` — the customer price is locked but
  internal COGS is wrong. Send to finance for pricing reconciliation.
- Filter by `x_mi_install_warning_count > 0`. These need install
  team coordination (tall cabinet, long shelf, filler/scribe).

### The dealer (per order)

1. Log in to `/my/dealer/orders`. See the list of own orders.
2. For each, navigate to the production package (the route via
   `/my/dealer/production-package/<pkg_id>/...`).
3. For KD orders: hit the `/kd` route → download the JSON envelope.
   Forward to the cutting partner.
4. For all orders: hit the `/installation-pdf` route → download the
   installation drawings. Pack with the cabinets for the install
   team.

## Common mistakes + how to recover

**"I ran generate_from_mo twice and now I have duplicate cutlists
in the DB."**

You shouldn't — the method's first step is to delete the prior
package for the MO. If you have duplicates, either (a) the deletion
failed silently (DB integrity error on `ondelete='restrict'`), or
(b) you ran generate_from_mo as a different user with different
ACLs. Inspect the duplicates' MO links; the older one is the stale
copy. Delete it by hand: package first, then cutlist + lines, then
hardware package + lines (mind the `ondelete='restrict'`).

**"The cutlist line for the back panel shows substrate = false."**

The line's substrate wasn't set on creation. Default is
`hardboard_1_4` (from `DEFAULT_SUBSTRATE_BY_PANEL` in
`models/sb_cutlist.py`). If it's blank, the dict iteration found
the back key but the default lookup failed (extremely unlikely).
Recovery: edit the line, set substrate manually. Re-run
`action_recompute_manufacturing_intelligence` so the MI engine
re-evaluates.

**"The hardware package has zero lines but the cabinet definitely
needs hinges."**

The `southbrook.hardware.catalog.resolve` call returned an empty
list. Causes: (a) the cabinet family isn't in the catalog rules,
(b) door_count + drawer_count both passed as 0, (c) the catalog
records were unseeded. Open the catalog
(`Southbrook Configuration → Hardware Catalog`), check rule
records exist for the family. Re-run `generate_from_mo` after
fixing.

**"The MI Status shows `ok` but the cutlist has a 2900mm panel that
shouldn't fit any sheet."**

The MI cut check uses
`ir.config_parameter.southbrook_mi.sheet_width_mm` (default 2440)
and `southbrook_mi.sheet_height_mm` (default 1220). If those
parameters were edited to larger values, the 2900mm panel doesn't
trip "Oversized panel" anymore. Cross-check the parameter values.
Lesson 2.5 has the full check catalog.

**"The dealer can't download the KD envelope — the page errors."**

Three likely causes. (a) Their partner record doesn't have
`channel = 'dealer'` — `_require_dealer` throws AccessError.
Fix: set channel on the partner. (b) The production package ID in
the URL is wrong (typo or stale). The controller raises
MissingError. Fix: navigate from the orders list. (c) The package
exists but `export_kd_envelope()` raises an error (e.g. cutlist not
in `nested` state). Check the package state and the cutlist state.

**"Installation PDF download returns garbage / empty bytes."**

The QWeb report wasn't generated. Open the package form, look for
the **Print → Installation PDF** action; run it directly. If it
errors, the PDF template has a regression. Page the dev team —
the route's `export_installation_pdf()` is delegating to the same
report.

## What the system is doing behind the scenes

The trio is owned by **`southbrook_kitchen_mrp`**. The MI extension
is owned by **`southbrook_manufacturing_intelligence`**. The dealer
portal routes are owned by **`southbrook_dealer_portal`**.

`generate_from_mo` is the only sanctioned way to create the trio.
Bypassing it (creating cutlist/hardware/package records by hand)
will:
- Skip the idempotent delete-and-recreate guard.
- Skip the `shared.southbrook_dims.panel_cut_list` formula (your
  geometry won't match the FreeCAD bridge's rendering).
- Skip the hardware catalog resolve (your hardware list won't
  match the configured rules).

Always go through `generate_from_mo` or its UI action wrapper.

The `_check_unique_mo` constraint on `sb.production.package` is
Python-side because Odoo 19 deprecated `_sql_constraints` (which
the old codebase used). The `ValidationError` message tells you to
use `generate_from_mo` to replace rather than duplicate.

The nesting envelope's `schema: "southbrook.nesting.v1"` is the
contract version. Future nesting tools may produce
`southbrook.nesting.v2` (different fields); the
`from_nesting_result` method validates the schema string before
accepting, so a v2 payload fails cleanly until the platform is
upgraded.

The MI checks (`southbrook.mi.check`) are written by
`southbrook.mi.engine._recompute_package(package)`. Each check
carries:
- `severity` — `blocker` / `warning` / `info`.
- `category` — `cut` / `production` / `assembly` / `install` /
  `cad` / `hardware`.
- `production_package_id` — back-link to the package.
- `production_id` — back-link to the MO (when the check is
  MO-scoped rather than package-scoped).
- `message` — specific finding text.
- `recommendation` — engine's suggested action.

The MI engine's `_recompute_package` deletes the prior checks for
this package first, then walks the cut summary + hardware summary
+ install context and writes new ones. This is why "edit a cutlist
line, refresh, MI checks change immediately" works — they're
recomputed from scratch on each invocation.

## TBD — the dealer export methods

The dealer portal controllers call
`package.export_kd_envelope()` and
`package.export_installation_pdf()`. These methods live on
`sb.production.package` but the **exact implementation isn't in
the addon code I traced for this lesson** — they're called from
the controller but the method bodies are either in a Phase-2
extension or a dynamically-installed module on the live DB. The
test file
`southbrook_dealer_portal/tests/test_kd_export.py` confirms the
methods exist and return the expected envelope schema, but the
trainer should TBD-flag this for the dealer-portal trainer until
the method source is traced.

What we know works (from tests):

- `export_kd_envelope()` returns a dict matching the nesting
  envelope schema PLUS pre-drilled hole data on sides + tops PLUS
  the hardware list. JSON-serialisable.
- `export_installation_pdf()` returns PDF bytes (≥1KB in test
  fixtures, asserted by `test_installation_pdf_emits_bytes`).
- Both methods reject if `state` is `draft` (cutlist must be at
  least in `exported` or `nested`).

## Quiz (5 questions, applied)

**1.** A planner opens an MO, sees no production package, and runs
`generate_from_mo(mo, 600, 900, 600, "base", door_count=1)`. The
call succeeds. They run it again with the same arguments. What
happens, and what's the rationale?

> The second call deletes the prior package + its cutlist +
> hardware package, then recreates everything. Idempotency: calling
> twice doesn't duplicate. Rationale: `generate_from_mo` is the
> intended entry point AND debug tool; the planner can regenerate
> after edits to the cabinet dimensions or catalog without
> manually cleaning up old records. The deletion order
> (package → cutlist → hardware) respects the `ondelete='restrict'`
> constraints; reverse order would error.

**2.** The MI Production Board shows a package with
`x_mi_blocker_count = 2, x_mi_status = blocked, x_mi_next_action =
"Split the part, select a larger sheet, or confirm a special-order
blank before cutting."` What do you do first?

> Open the package, click into `x_mi_check_ids`. The "next action"
> text comes from the top blocker's recommendation; there are 2
> blockers, so there's at least one more. Read both. Most common
> combo: an `Oversized panel` blocker + a `Missing cutlist` (the
> second often appears when the first prevents a fresh
> generate_from_mo). Resolve the panel size first (split design,
> source larger sheet, or push back to the designer), then re-run
> `generate_from_mo` to rebuild the cutlist clean.

**3.** A dealer says "I can see the order list but the KD download
link errors with 'access denied.'" Walk through diagnosis.

> The `_require_dealer` guard in `southbrook_dealer_portal/
> controllers/main.py` checks `partner.channel == 'dealer'`. Open
> the dealer's res.partner, look at the channel field. If it's
> `tradesperson`, `kd`, `bigbox`, or `retail`, the guard rejects
> with the 'dealer-only' error. (This is Phase-1 audit finding 4
> — tradesperson channel was rejected even when business logic
> says they should access; ticket to be filed.) Fix for this
> dealer: set channel to `dealer` on the partner; refresh the
> page; the guard passes.

**4.** A PM asks "why does the cutlist have 7 panels for a base
cabinet but no toe-kick line?" What's your answer?

> By design. The panel formula
> (`shared.southbrook_dims.panel_cut_list`) returns a `toe_kick`
> key as a METADATA descriptor (dict), not a panel tuple. The
> cutlist generation INTENTIONALLY skips it because toe-kick is
> integrated into the side panels — emitting it as a cutlist line
> would create a phantom panel that the floor would try to cut.
> The contract is enforced by tests; never look for a toe-kick
> line. The 7 panels are side_L, side_R, top, bottom, back,
> adjustable_shelf, door — that's the full cabinet's cut spec.

**5.** A planner sends a cutlist to the nesting tool, gets back a
payload with `{"schema": "southbrook.nesting.v2", ...}` and calls
`from_nesting_result`. The method raises UserError. Why, and what
should they do?

> The method validates `schema == "southbrook.nesting.v1"` and
> raises UserError on mismatch. The v2 schema is a future contract
> the platform doesn't accept yet. Two paths: (a) wait for the
> platform upgrade that adds v2 support; (b) downgrade the nesting
> tool to emit v1 envelopes. Don't manually stuff the v2 payload
> into v1 — schema versioning exists precisely to prevent silent
> field-name mismatches that would scramble yield + waste
> reporting.

---

## What this lesson does NOT cover

- The Kitchen Jobs board and how the production package's MI
  status surfaces back onto release readiness → lesson 12.3 +
  Course 2 lesson 2.1.
- The MI check catalog (cut / assembly / hardware / install
  checks, what each says, severity bands) → Course 2 lesson 2.5.
- The MI Engine Status singleton and the gate refire cron →
  lesson 12.6 + Course 2 lesson 2.4 cron 2.
- The release gate engineer's flow (the five booleans, how the
  cutlist gets approved) → lesson 12.4 + Course 2 lesson 2.2.
- The hardware catalog rules — per_door / per_drawer / per_shelf
  / per_cabinet / per_family — and how `resolve()` aggregates them
  → Course 5 lesson 5.3.
- The dealer portal's other surfaces (customer-facing dealer
  views, order portal) → Course 6 lesson 6.2.
- Native Odoo `mrp.production` mechanics, BoM authoring, routing
  definitions → Odoo's own training.
