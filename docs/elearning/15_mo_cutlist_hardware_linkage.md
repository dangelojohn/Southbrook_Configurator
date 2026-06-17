---
course: 15 — Manufacturing Module Deep Dive
chapter: 15.7
title: MO ↔ Cut List ↔ Hardware Package ↔ Production Package — The Per-MO Artefact Triple
duration: 35 minutes
audience: Planner + Production Manager + Developer wiring up the dealer export pipeline
prereqs: Lesson 15.1, Lesson 15.4, Course 4 lesson 4.2 (cut specs), Course 6 lesson 6.2 (dealer portal), comfortable with Odoo M2O relationships
custom_modules: southbrook_kitchen_mrp, southbrook_manufacturing_intelligence, southbrook_dealer_portal
---

# MO ↔ Cut List ↔ Hardware Package ↔ Production Package

## Who this lesson is for

You're standing in front of a confirmed Manufacturing Order and
trying to figure out where the cut list, hardware pick list, KD
flat-pack envelope, and installation PDF actually come from. The
answer is **three first-class models**: `sb.cutlist`,
`sb.hardware.package`, `sb.production.package` — all owned by
`southbrook_kitchen_mrp`, all M2O-linked back to `mrp.production`,
all with their own state machines, and all decorated by
`southbrook_manufacturing_intelligence`. This lesson is the
load-bearing chain from "MO confirmed" to "dealer downloads the
KD envelope JSON" — every model, every join, every state, every
HTTP route.

## Where this lives on the site

> **/odoo/manufacturing → Manufacturing Orders → <MO>** — the MO form; production package opens from a smart button
> **Southbrook PM → MI Packages** — `sb.production.package` list (decorated by MI verdict)
> **/my/dealer/orders** — Dealer Portal orders list
> **/my/dealer/production-package/<int:pkg_id>/kd** — KD JSON download
> **/my/dealer/production-package/<int:pkg_id>/installation-pdf** — installation PDF download

The cutlist + hardware package don't get their own top-level menu;
they're reached from the production package's smart buttons or by
typing `sb.cutlist` in the global search.

## What your screen shows — the model triple

### `sb.cutlist`

**Owner**: `southbrook_kitchen_mrp` (`models/sb_cutlist.py`).
**Description**: Panel cut list for one MO, generated from the
panel formulas in `_compute_panel_dimensions` (lesson 15.4).

Schema:

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Sequence `sb.cutlist` |
| `mo_id` | M2O → `mrp.production` | ondelete=cascade, indexed — **canonical FK** |
| `state` | Selection: **draft** / exported / nested / done | Tracked |
| `line_ids` | O2M → `sb.cutlist.line` (inverse `cutlist_id`) | |
| `line_count` | Integer | Stored compute |
| `nesting_result_json` | Text | Round-trip stash for the nest result |

`sb.cutlist.line` schema:

| Field | Type | Notes |
|---|---|---|
| `cutlist_id` | M2O, cascade | |
| `sequence` | Integer | |
| `panel_name` | Selection `PANEL_NAMES` | Excludes `toe_kick` by contract |
| `qty` | Integer | |
| `length_mm` / `width_mm` / `thickness_mm` | Float(8,3) | |
| `substrate` | Selection `SUBSTRATE_CHOICES` | |
| `grain_dir` | Selection `GRAIN_DIRECTIONS` | |
| `edge_banding_config` | Text (JSON) | Per-edge tape colour and material |

### `sb.hardware.package`

**Owner**: `southbrook_kitchen_mrp` (`models/sb_hardware_package.py`).
**Description**: Resolved hardware pick list for one MO, generated
by calling `env['southbrook.hardware.catalog'].resolve(...)`.

Schema:

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Sequence |
| `mo_id` | M2O → `mrp.production` | Cascade, indexed |
| `state` | Selection: **draft** / picked / delivered | Tracked |
| `line_ids` | O2M → `sb.hardware.package.line` | |
| `line_count` | Integer | Stored compute |
| `has_pricing_pending` | Boolean | Stored compute, depends `line_ids.product_id.x_pricing_pending` |

`sb.hardware.package.line`:

| Field | Type | Notes |
|---|---|---|
| `package_id` | M2O, cascade | |
| `sequence` | Integer | |
| `product_id` | M2O → `product.product` | Domain `x_hardware_category != False` |
| `qty` | Float | |
| `pricing_pending` | Boolean | Related, stored |
| `hardware_category` | Selection | Related to `product_tmpl_id.x_hardware_category` |
| `brand_id` | M2O → `product.brand` | Related |

### `sb.production.package`

**Owner**: `southbrook_kitchen_mrp` (`models/sb_production_package.py`)
+ extended by `southbrook_manufacturing_intelligence` and
`southbrook_dealer_portal`.

The **per-MO bundle** that ties cutlist + hardware package + MI
verdict + state machine together.

Base schema (from kitchen_mrp):

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Sequence |
| `mo_id` | M2O → `mrp.production` | **Required**, cascade, indexed, **one-per-MO** enforced via `@api.constrains` `_check_unique_mo` (Python-level due to v19 `_sql_constraints` deprecation) |
| `state` | Selection: **draft** / ready / released / done | Tracked |
| `cutlist_id` | M2O → `sb.cutlist` | ondelete=restrict |
| `hardware_package_id` | M2O → `sb.hardware.package` | ondelete=restrict |
| `has_pricing_pending` | Boolean | Related from hardware package, stored |

MI extension schema (from `southbrook_manufacturing_intelligence`):

| Field | Type | Notes |
|---|---|---|
| `x_mi_status` | Selection: ok / review / blocked | The badge |
| `x_mi_check_ids` | O2M → `southbrook.mi.check` (inverse `production_package_id`) | Check rows for this package |
| `x_mi_blocker_count` | Integer | |
| `x_mi_warning_count` | Integer | |
| `x_mi_install_warning_count` | Integer | Specific to install-category checks |
| `x_mi_next_action` | Text | |
| `x_mi_yield_pct` | Float | |
| `x_mi_waste_area_m2` | Float | |
| `x_mi_edge_band_m` | Float | Total edge band metres |

Plus: `action_recompute_manufacturing_intelligence()` (calls
`southbrook.mi.engine._recompute_package`),
`_mi_install_check_lines_for_pdf()` (filters checks where
`category='install'` for inclusion in the installation PDF).

Dealer Portal extension schema (from `southbrook_dealer_portal`):

| Field | Type | Notes |
|---|---|---|
| `is_kd_variant` | Boolean | True for KD orders |
| `export_kd_envelope()` | Method | Returns the JSON envelope |
| `export_installation_pdf()` | Method | Returns a ReportLab PDF |
| `_derive_box_dimensions()` / `_fetch_elevation_svgs()` / `_derive_predrilled_holes(panel)` | Helpers | Used by the two exporters |

## The FK direction — who points at whom

```
mrp.production (MO)
  ▲   ▲   ▲
  │   │   │
  │   │   └── sb.production.package.mo_id  (REQUIRED, unique-per-MO)
  │   │                  │
  │   │                  ├── cutlist_id ─→ sb.cutlist
  │   │                  └── hardware_package_id ─→ sb.hardware.package
  │   │
  │   └── sb.hardware.package.mo_id  (multi allowed at ORM, de-facto 1)
  │
  └── sb.cutlist.mo_id  (multi allowed at ORM, de-facto 1)
```

Important: **all three FKs are forward refs from the package side to
the MO**. `mrp.production` has no inverse fields declared for these
three models in this addon's code — if you want to navigate from MO
to package, you do `env['sb.production.package'].search([('mo_id',
'=', mo.id)])`.

The one-per-MO contract on `sb.production.package` is enforced at
Python level via `@api.constrains` because v19 silently drops legacy
`_sql_constraints`. Don't try to create two packages for the same MO
— the constrain will raise.

## State machines

| Model | States | Notes |
|---|---|---|
| `sb.cutlist` | draft → exported → nested → done | `from_nesting_result()` writes `state='nested'`. `exported` and `done` transitions are TBD — not present in the current model file. |
| `sb.hardware.package` | draft → picked → delivered | No transition methods in the model file. Set externally (TBD which addon owns the transitions). |
| `sb.production.package` | draft → ready → released → done | `generate_from_mo()` creates with `state='ready'`. `released` and `done` transitions are TBD. |

The brief and manifest doc say "draft → exported → nested → done" —
that's the **cutlist** state machine, not the production package's
(which terminates `released → done`). Don't conflate.

## Creation lifecycle

The orchestrator is `sb.production.package.generate_from_mo(mo, w,
h, d, family, door_count, drawer_count, soft_close)`:

1. Idempotent: deletes any prior package + lines + cutlist + hw pkg
   for this MO.
2. Calls `panel_cut_list(...)` (which internally calls
   `_compute_panel_dimensions` from lesson 15.4) → returns panel
   dict.
3. Calls `sb.cutlist.generate_lines_from_panel_dict(cutlist,
   panel_dict)` — skips `toe_kick` key by construction
   (`keys_to_emit` tuple excludes it).
4. Calls `env['southbrook.hardware.catalog'].resolve(cabinet_family,
   door_count, drawer_count, shelf_count, soft_close)` → returns
   `[(product.product, qty), ...]`.
5. Calls `sb.hardware.package.generate_lines_from_resolution(package,
   picks)` — drops qty<=0 lines.
6. Creates `sb.production.package` with `mo_id=mo.id, cutlist_id=...,
   hardware_package_id=..., state='ready'`.
7. Returns the package.

**The MO-confirm hook** — `shop_copy.xml` comment says
"`generate_from_mo()` spawns at MO confirm" but the actual
`mrp.production` override that calls `generate_from_mo()` is NOT in
the addon files. TBD — this is either invoked from outside the
addon (likely from a sale.order or product_configurator_mrp hook)
or the wiring is still pending. Smoke test: confirm a Southbrook MO
and check whether `sb.production.package` exists — if not, the hook
isn't wired in your env.

## MI fields per package — green/amber/red walkthrough

**Only `sb.production.package` carries MI fields.** Cutlist and
hardware package are not MI-decorated.

When the MI engine pass runs against a package:

1. Iterates check definitions in
   `southbrook_manufacturing_intelligence/models/mi_check.py`.
2. Runs each check against the package's cutlist + hardware package
   + parent MO.
3. Inserts `southbrook.mi.check` rows with
   `production_package_id = self.id`, severity, category,
   `next_action`.
4. Aggregates: `x_mi_blocker_count`, `x_mi_warning_count`,
   `x_mi_install_warning_count`.
5. Sets `x_mi_status`: `'blocked'` if blockers, else `'review'` if
   warnings, else `'ok'`.
6. Writes `x_mi_next_action` (top blocker's next-action sentence).
7. If cutlist is `nested`, reads yield + waste metadata from the
   nest result JSON into `x_mi_yield_pct`, `x_mi_waste_area_m2`.
8. Computes `x_mi_edge_band_m` by summing
   `_compute_edge_banding_length` across cabinets.

The badge appears on:
- The package form (`view_sb_production_package_form_mi`).
- The **Southbrook PM → MI Packages** list, decorated by
  `decoration-success / warning / danger`.

## The Accucutt JSON envelope contract

`sb.cutlist.to_nesting_envelope()` returns a deterministic dict:

```
{
  "schema": "southbrook.nesting.v1",
  "cutlist_id": <int>,
  "cutlist_name": <str>,
  "mo_id": <int>,
  "panels": [
    {
      "panel_name": "side_L",
      "qty": 2,
      "length_mm": 762.0,
      "width_mm": 590.5,
      "thickness_mm": 15.875,
      "substrate": "melamine_white",
      "grain_dir": "vertical",
      "edge_banding": <parsed_json>
    },
    ...
  ]
}
```

`sb.cutlist.from_nesting_result(payload)` ingests:
```
{
  "schema": "southbrook.nesting.v1",
  "sheets_used": <int>,
  "yield_pct": <float>,
  "waste_pct": <float>,
  ...
}
```

The ingester:
- Validates `schema == "southbrook.nesting.v1"`; mismatch → raises
  `UserError`.
- Stores the raw payload in `nesting_result_json`.
- Flips `state` to `'nested'`.
- Stashes yield + waste for the MI engine to pick up on its next pass.

Full payload schema validation is deferred to Phase 4 (per source
comment). For now, the schema-name check is the only guard.

## The toe-kick-never-emitted contract

A Southbrook-shop convention: **toe-kick is integrated into the
side panels** (the bottom of each side panel runs down to the
floor, with a notch cut for the toe-kick). It is NEVER emitted as a
separate cutlist line. Three layers enforce this:

1. **Doc contract** — `sb_cutlist.py` lines 9-12; docstring of
   `generate_lines_from_panel_dict` at lines 126-131.
2. **Code enforcement** — `keys_to_emit` tuple in
   `generate_lines_from_panel_dict` at `sb_cutlist.py:133-134`
   omits `toe_kick`; the line-creation loop literally cannot emit
   a toe-kick row.
3. **Test enforcement** —
   `southbrook_kitchen_mrp/tests/test_cutlist_generation.py::test_toe_kick_never_emitted_as_line`
   asserts no line has `panel_name == "toe_kick"`. Refactor break
   the test, refactor fails CI.

## The dealer portal export endpoints

`southbrook_dealer_portal/controllers/main.py` exposes three HTTP
routes consuming the production package:

| Route | Method | Handler | Auth | Output |
|---|---|---|---|---|
| `/my/dealer/orders` | GET | `dealer_orders` | user (+ channel=dealer gate) | Renders `portal_dealer_orders_list` template |
| `/my/dealer/production-package/<int:pkg_id>/kd` | GET | `kd_export` | user (+ dealer gate) | `application/json` attachment from `package.export_kd_envelope()` — schema `southbrook.kd_flatpack.v1`, includes panels with `predrilled_holes`, hardware with `marathon_sku` |
| `/my/dealer/production-package/<int:pkg_id>/installation-pdf` | GET | `installation_pdf` | user (+ dealer gate) | `application/pdf` from `package.export_installation_pdf()` (ReportLab; optional FreeCAD-bridge elevation SVGs via `_fetch_elevation_svgs`) |

**ACL gate**: `_require_dealer()` raises `AccessError` unless
`request.env.user.partner_id.channel == 'dealer'`. The handler
comment flags TBD: "ACL: package's MO must trace to an SO with the
dealer's partner... a real production deployment must wire SO ↔ MO ↔
package linkage."

**`sb.hardware.package` is NOT directly exposed by a route** — it's
reached transitively via `package.hardware_package_id` from
`sb.production.package`.

Course 6 lesson 6.2 covers the customer-facing dealer flow. This
lesson covers the manufacturing-side construction; the dealer
download is the LAST step in the chain.

## Your daily flow

**1. Planner / Manager confirming an MO:**

- Confirm the MO via native button. If wired, `generate_from_mo()`
  fires and creates the production package automatically.
- Open the MO. Click the production package smart button (if
  present) → opens `sb.production.package` form.
- Look at `x_mi_status`. If `blocked`, read `x_mi_next_action`
  and decide. If `ok`, proceed to flip `state` to `released`.

**2. Mid-flight — nest result lands:**

- Cut shop runs the nest, calls
  `sb.cutlist.from_nesting_result(payload)` (via internal API).
- Cutlist `state` flips to `nested`, `nesting_result_json` is
  stashed.
- Next MI engine pass writes `x_mi_yield_pct` and
  `x_mi_waste_area_m2` on the package.
- Manager reviews on the MI Packages list — anything yielding
  below 75% gets a warning.

**3. Dealer wants the KD envelope:**

- Dealer logs into portal, navigates to **/my/dealer/orders**.
- Clicks the KD download link on the relevant order — routes
  through `/my/dealer/production-package/<pkg_id>/kd`.
- Server serves the JSON attachment. Dealer's downstream system
  (e.g. flat-pack assembly partner) ingests.

## Common mistakes + how to recover

**"MO confirmed but no `sb.production.package` exists."**

The MO-confirm → `generate_from_mo()` hook isn't wired in your
addon set. Either the addon you'd expect to wire it isn't installed
(check whether `southbrook_estimating_website` or another orchestrator
is present), or the hook is genuinely missing. Workaround: manually
call `env['sb.production.package'].generate_from_mo(mo, w, h, d,
family, door_count, drawer_count, soft_close)` from a server action.

**"Two packages exist for the same MO."**

Shouldn't happen — `_check_unique_mo` raises. If you see it, your
DB pre-dates the constrain. Run a one-off cleanup script merging
the duplicates (keep the one with the highest `id`, deactivate the
others).

**"Cutlist `state` is stuck at `draft` — never went to `exported` or
`nested`."**

The `exported` and `done` transitions are TBD (not in the model
file). The `nested` transition only fires from
`from_nesting_result()`. If your cut shop's nest tool doesn't call
that API, the cutlist stays `draft`. File a ticket for the bridge.

**"Dealer says the KD download is empty."**

Check three things: (a) is the dealer's `channel = 'dealer'` on
their partner? (b) is `is_kd_variant = True` on the package? (c)
does the package's hardware pick list have lines with
`marathon_sku` populated? `export_kd_envelope()` skips lines
missing the SKU.

**"Installation PDF generates but has no elevation drawings."**

`_fetch_elevation_svgs()` calls the FreeCAD bridge. If the bridge
isn't responding, the PDF generates without the elevation section
(graceful degradation). Check `southbrook_freecad_bridge` health.

**"`x_mi_status` on the package says `ok` but the MO's
`x_mi_status` says `blocked`."**

Two separate aggregations. The MO's MI badge counts checks
where `production_id == mo.id`. The package's MI badge counts
checks where `production_package_id == pkg.id`. Different cohorts
— same engine pass but different aggregations. Both can disagree
legitimately: an MO-level data quality blocker doesn't
automatically map to a package-level blocker, and vice versa.

## What the system is doing behind the scenes

The triple model is the **MO's downstream artefact bundle**.
Native Odoo gives you the MO + workorders + BoM; Southbrook adds
the cutlist (panel-level cut list with substrate, grain, edge
banding), the hardware package (resolved hardware picks with
brand + SKU), and the production package (the wrapper that ties
them together with a state machine + MI verdict).

**Why three models and not one?**
- Cutlist is consumed by the cut shop (internal cutting/nesting
  division). It needs its own state and round-trip with the nest
  tool.
- Hardware package is consumed by purchasing + warehouse. It
  needs its own state for pick/deliver.
- Production package is consumed by the dealer portal + manager.
  It's the wrapper carrying the MI verdict.

Each model has its own audit trail, its own pull/push contracts
with external systems (Accucutt for cutlist; PO chain for
hardware; dealer portal for production package). Bundling them
into one model would mean every state change on any sub-component
triggers a write to the parent.

**Idempotency** — `generate_from_mo()` is idempotent by design.
Re-confirming an MO (e.g. after a deliberate cancel + reconfirm)
deletes the old package + lines + cutlist + hw pkg and rebuilds.
Don't manually edit cutlist lines or hardware lines — they're
computed state. If you need to override, edit the BoM math
(lesson 15.4) or the hardware catalog rules.

**The MI engine cohort split** — one engine pass writes both
MO-level and package-level checks. The split is by check
definition: cut-category and assembly-category checks land on the
package; production-category and install-category checks land on
the MO. This is invisible to the user but matters when you're
debugging "why is this blocker on the MO not on the package?"

## Quiz (5 questions, applied)

**1.** An MO is confirmed but no production package was created.
What's your first three checks?

> (a) Is `southbrook_kitchen_mrp` installed in this env?
> `env['ir.module.module'].search([('name','=','southbrook_kitchen_mrp'),('state','=','installed')])`.
> (b) Was `generate_from_mo()` called? Look in the MO's chatter
> for a creation message; if absent, the hook isn't wired.
> (c) Manually try `env['sb.production.package'].generate_from_mo(mo, w, h, d, family, door_count, drawer_count, soft_close)` —
> if it succeeds, the wiring is the only gap.

**2.** A dealer downloads the KD envelope and says "panel 7 is
missing the `predrilled_holes` array." Where do you trace?

> `_derive_predrilled_holes(panel)` is the helper that generates
> the holes per panel. It's defined in
> `southbrook_dealer_portal/models/sb_production_package.py`. If
> panel 7's `panel_name` isn't in the helper's mapping (a new
> panel type was added without updating the helper), holes are
> empty. Add the mapping. The KD envelope schema is
> `southbrook.kd_flatpack.v1`; bump to `v2` if the change is
> incompatible.

**3.** Cut shop runs the nest, yield is 78%, `from_nesting_result`
writes `state='nested'` and stashes the JSON. The next MI engine
pass should write `x_mi_yield_pct = 78` on the package. But the
package still shows 0. Why?

> The MI engine pass hasn't run yet, OR the engine pass ran but
> didn't pick up the new nest result because the
> `nesting_result_json` parsing failed silently. Hit Recompute on
> the package (`action_recompute_manufacturing_intelligence`).
> If yield still 0, the JSON's `yield_pct` key is missing or
> mis-spelled. Open the cutlist's `nesting_result_json` field
> and inspect.

**4.** Why does `_check_unique_mo` run in Python (`@api.constrains`)
instead of as a SQL UNIQUE constraint?

> Odoo 19 silently ignores legacy `_sql_constraints` lists (per
> session memory). Even if the model declared
> `_sql_constraints = [('mo_unique', 'UNIQUE(mo_id)', 'msg')]`,
> the constraint wouldn't reach Postgres. The team migrated to
> Python-level constrains as a stopgap. The proper v19 fix is
> `_name = models.Constraint('UNIQUE(mo_id)', 'msg')` on the model
> — file a ticket if you spot stragglers.

**5.** A test asserts `toe_kick` is never emitted as a cutlist
line. A junior developer wants to "make toe-kick optional" by
adding it to the `keys_to_emit` tuple. What do you tell them?

> No. The toe-kick-integrated-into-side-panel decision is a
> shop convention enforced at three layers (doc, code, test). The
> side panel geometry from `_compute_panel_dimensions()` ALREADY
> includes the toe-kick (the side panel's `length_mm` includes the
> toe-kick height). Adding a separate toe-kick line would
> double-count material. If the shop wants to split toe-kick into
> a separate panel in future, the engineering decision is
> upstream — change the side panel formula to exclude toe-kick
> first, THEN add the toe-kick panel emission. Don't just flip
> the tuple.

---

## What this lesson does NOT cover

- MO field walkthrough → lesson 15.2.
- Workorder fields + tool readiness + downtime → lesson 15.3.
- BoM math + cut constants (which feed the cutlist) → lesson 15.4.
- Workcenter form + alternative chain → lesson 15.5.
- MO views + Kanbans → lesson 15.6.
- Dealer portal customer-facing flow → Course 6 lesson 6.2.
- Cut spec authoring (PLM side) → Course 4 lesson 4.2.
- The MI engine's check rule catalog → Course 3 lesson 3.1.
- Native Odoo MO confirm + procurement → Odoo native training.
