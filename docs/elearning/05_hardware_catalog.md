---
course: 5 — Estimating + Configurator
chapter: 5.3
title: Hardware Catalog — Marathon SKUs, Auto-Resolution, Manual Lines
duration: 30 minutes
audience: Estimator + the person who adds non-cabinet items to a quote, plus the admin who keeps the Marathon catalog current.
prereqs: Lessons 5.1 (Configurator basics), 5.2 (Estimating a quote).
custom_modules: southbrook_hardware_catalog
---

# Hardware Catalog — Marathon SKUs, Auto-Resolution, Manual Lines

## Who this lesson is for

You're the estimator who realises a customer's quote needs an
appliance-pull on the fridge cabinet, or a matte-black handle upgrade,
or a soft-close kit on a vanity. You're also the person an admin asks
"can you take a Marathon catalog CSV from the trade-account portal and
import the 179 new SKUs?". This lesson covers both surfaces of the
Marathon Hardware catalog: what gets resolved automatically per
carcass (so you don't add 4 hinges manually on every base cabinet), and
what you add by hand.

## Where this lives on the site

> **Inventory → Hardware Catalog → Brands** — the 19 hardware
> manufacturers (`southbrook.hardware.brand`).

> **Inventory → Hardware Catalog → Import Marathon CSV** — the upload
> wizard (`southbrook.hardware.import.wizard`).

> **Inventory → Products → Products** — filter by Hardware Category to
> see every catalog SKU; each carries the "Hardware Catalog" tab on the
> product form.

The auto-resolution service is *not* on a menu — it runs from
`env['southbrook.hardware.catalog'].resolve(...)` when the FreeCAD
bridge or the BoM rollup needs hardware. You'll see its output as
extra BoM lines after you click Confirm on an order.

## What your screen shows

**Brand record** (`southbrook.hardware.brand`):

- **Name** (`name`) — display name (e.g. "Blum", "Salice", "Hettich",
  "Marathon").
- **Code** (`code`) — the snake-case key the `hardware_map.json` and
  the import wizard match on (`blum`, `salice`, `hettich`, `marathon`).
  Unique. Don't change it after seeded.
- **Sequence** (`sequence`) — display order.
- **Active** (`active`) — flip to false to hide a brand from selection
  without deleting it.

**Product variant — Hardware Catalog tab** (on `product.product`):

- **Hardware Category** (`x_hardware_category`) — selection: hinge /
  slide / pin / screw / handle / leveler / cam_lock / bumper / other.
  Drives the resolver's "this is a hinge" semantic.
- **Brand** (`x_hardware_brand_id`) — m2o to the brand record above.
- **Marathon SKU** (`x_marathon_sku`) — the vendor SKU as listed in
  Marathon's workbook (e.g. `BLM-110-SC` for the Blum 110° soft-close
  hinge, `MRH-HDL-PUL128` for the 128 mm pull). This is the join key
  the resolver uses; it must be unique and stable across catalog
  refreshes.
- **Pricing Pending** (`x_pricing_pending`) — boolean, set to true when
  the cost requires a trade-account login the Southbrook team doesn't
  have yet. Quotes including pricing-pending hardware get flagged so
  the customer doesn't see "$0.00 per hinge" by accident.
- **Standard / Length / Width / Projection / Diameter / Center-to-Center
  / Material / Lead Time / Package Quantity / Marathon Image URL** —
  spec fields populated by the import wizard from the trade workbook.

**Import wizard** (`southbrook.hardware.import.wizard`):

- **CSV File** (`csv_file` — binary upload) — the trade workbook
  exported as CSV.
- **Dry Run** (`dry_run`, default true) — parse-and-validate only; no
  writes.
- After running: **Created** / **Updated** / **Errors** counters plus a
  **Result Log** with row-by-row outcome.

## Your daily flow

You have two reasons to touch hardware: auto-resolution outcomes when
configuring a cabinet (passive — you read what the system produced),
and manual lines when the customer needs something off-catalog (active
— you add it by hand).

**1. Auto-resolution: what the system did per carcass.**

You configure a base cabinet in lesson 5.2. The FreeCAD bridge (or the
BoM rollup on confirm) calls:

```
env['southbrook.hardware.catalog'].resolve(
    cabinet_family='base',
    door_count=2,
    drawer_count=0,
    shelf_count=1,
    soft_close=True,
    pull_finish='brushed_nickel',
    pull_size_mm=128,
    handle_style='pull',
    mount_appliance=False,
)
```

…and gets back a list of `(product.product, qty)` tuples. For a 2-door
soft-close base with one shelf, brushed-nickel 128 mm pulls, the
result is:

| Marathon SKU | Source rule | Qty |
|--------------|-------------|-----|
| `BLM-110-SC` | per_door_soft_close (2 per door × 2 doors) | 4 |
| `MRH-DOORBUMP-CL` | per_door_soft_close (2 per door × 2 doors) | 4 |
| `MRH-HDL-PUL128` | per_door_soft_close (1 per door × 2 doors) | 2 |
| `MRH-SHLFPIN-5MM` | per_shelf (4 per shelf × 1 shelf) | 4 |
| `MRH-CAMLOCK-KIT` | per_cabinet | 1 |
| `MRH-LVL-50` | per_cabinet | 4 |
| `MRH-MTGSCR-25PK` | per_cabinet | 1 |

That's the full pick list for one cabinet. You don't add any of these
manually — they appear on the BoM as derived lines. The rules live in
`data/hardware_map.json` shipped inside the addon and cached on the
registry (`self.pool._southbrook_hardware_map`).

**2. Per-family extras.**

`per_family` in the JSON map adds extras for specific cabinet families:

- `tall`: +4 levelers (`MRH-LVL-50` — tall pantries need the extra
  load support)
- `sink`: +1 water barrier (`MRH-WATERBARRIER-1M`)

The resolver aggregates duplicates — a tall pantry gets `MRH-LVL-50`
once from `per_cabinet` and once from `per_family[tall]`, summed to 8
levelers, not two separate lines.

**3. Soft-close swap.**

When the configurator sets `soft_close = False` (e.g. Rule 4 fires on a
bi-fold corner cabinet), the resolver reads `per_door` instead of
`per_door_soft_close`. That swaps `BLM-110-SC` for `BLM-110-NSC` (the
non-soft-close hinge). All other hardware is unchanged.

**4. Finish-aware handle override.**

The default per-door / per-drawer rule places `MRH-HDL-PUL128` (brushed
nickel 128 mm pull) on every door. If the customer picks Matte Black
under the Handle attribute, the resolver:

- Strips `MRH-HDL-PUL128` from the totals (default pull SKU listed in
  `pull_default_skus`).
- Looks up the override in `by_pull_finish['matte_black']['128mm']` →
  `MRH-HDL-PUL128-MB`.
- Adds the override back with the same total quantity.

Same mechanism for knobs (`by_knob_finish`, `knob_default_skus`).
Appliance pulls are *added* on top (not swapped) when
`mount_appliance=True`, one per appliance-door front, from
`appliance_pulls[<finish>]`.

**5. When to add a hardware line manually.**

The auto-resolver covers ~90% of cabinets. Add a line yourself when:

- The customer brought their own pull / knob (customer-supplied — add
  as a non-Marathon `product.product` with zero cost, qty = door
  count).
- The customer wants a specialty hinge not in the rule (overlay vs
  inset hinge swap, exterior frameless conversion). Find the SKU in
  Inventory → Products, add it as an order line.
- The order needs install consumables (caulk, shims, screws beyond the
  `MRH-MTGSCR-25PK` standard).
- The hardware is *replacement* parts for a refacing job — those
  don't go through the carcass resolver at all.

For a manual hardware line:

> Order Builder → (your order) → Order Lines → Add a line → search
> "MRH-" or "BLM-" or the brand → pick → qty → save.

It goes on the order at the partner's pricelist price.

**6. Catalog admin: importing the Marathon trade workbook.**

When the Marathon trade-account workbook lands (the 179-row CSV), the
admin uses the import wizard:

> Inventory → Hardware Catalog → Import Marathon CSV

- Attach the CSV (UTF-8, with header row).
- Leave **Dry Run** checked. Click **Import**.
- Read the **Result Log**: every row reports `created` or `updated` or
  `ERROR: <message>`. Errors are typically:
  - `marathon_sku is required` — empty SKU column on a row.
  - `unknown brand_code 'foo'` — a brand code in the CSV that doesn't
    match a `southbrook.hardware.brand.code`. Fix: add the brand
    first under Inventory → Hardware Catalog → Brands.
  - `category 'foo' is not a HARDWARE_CATEGORY` — only `hinge`,
    `slide`, `pin`, `screw`, `handle`, `leveler`, `cam_lock`,
    `bumper`, `other` are accepted.
  - `list_price 'X' is not numeric` — non-number in a price column.
- Fix the source CSV, re-run dry-run until clean.
- Uncheck **Dry Run**, **Import** again. The import is upsert (matches
  existing SKUs by `x_marathon_sku`, updates them; creates the rest).
  Never deletes — a SKU removed from Marathon's workbook stays in
  Odoo until an admin archives it manually.

**7. Pricing and margin.**

Per-SKU pricing on `product.product`:

- `standard_price` — Southbrook's cost from Marathon.
- `list_price` — Southbrook's resale price (what the customer sees).
- `x_pricing_pending` — boolean flag. If true, the SKU's cost wasn't
  available at import time. The Signature Spec Sheet PDF flags
  pricing-pending lines with an asterisk; sales should clear the flag
  (set `x_pricing_pending = False` and supply the cost) before sending
  the quote.

Margin per SKU = `(list_price - standard_price) / list_price`. Southbrook
targets 35% on hardware (the same as on the refacing channel). No
automatic enforcement — the admin's responsibility to maintain
list_price as costs change.

## Common mistakes + how to recover

**"I confirmed an order and the BoM shows no hinges, no slides, no
hardware at all."**

The `resolve()` call ran but every SKU it returned was missing from the
installed seed (the resolver logs a warning per missing SKU and skips
it). Check the Odoo log for messages like `hardware_map references SKU
'BLM-110-SC' not present in the catalog`. Recovery: install the
hardware seed (`-u southbrook_hardware_catalog`) or import the trade
workbook. The cabinet's BoM stays valid — you just need to back-fill
the hardware seed.

**"My order's BoM has 8 copies of the same `MRH-LVL-50` leveler line."**

Aggregation failure — the resolver normally sums per_cabinet + per_family
contributions into one line via the `totals` dict. If they're separate
lines, you're looking at the configurator's preview, not the BoM
rollup. The BoM rollup runs at MO creation. Open the
`mrp.production` record and check the actual BoM — most likely it
shows one `MRH-LVL-50` line at qty 8, which is correct.

**"The customer wants brushed nickel pulls but the BoM shows
`MRH-HDL-PUL128` (default), not the brushed-nickel-specific SKU."**

The configurator wasn't passed a `pull_finish` argument. The Handle
attribute on the cabinet needs to be set; in the OCA wizard, pick a
specific finish, save. If the finish-specific SKU still doesn't
appear, the `by_pull_finish` map doesn't have the customer's finish +
size combination — fall back is the brushed-nickel default. The
finish key is snake_case (e.g. `matte_black`, `antique_bronze`) and
must match the `attr_pull_finish` value from `attributes.xml`.

**"I imported a 179-row CSV and it shows 178 updated, 1 created. I
expected 179 created on a fresh DB."**

You imported against a DB with the 20-row demo seed already installed.
The 20 demo SKUs hit upsert (match on `x_marathon_sku`) and get
`updated`; the 159 truly new SKUs come up as `created`. Math: 20
existing + 159 new = 179 rows processed. If you see 178 updated and 1
created, your demo seed had 178 rows somehow — investigate by querying
`product.product` filtered by `x_marathon_sku IS NOT NULL`.

**"A SKU shows `x_pricing_pending = True` but I have the cost from the
trade portal — how do I clear it?"**

Open the product variant (Inventory → Products → search by Marathon
SKU). Set `standard_price` to the cost. Set `list_price` to the
cost / (1 - 0.35) for 35% margin (or whatever margin sales policy
dictates). Set `x_pricing_pending = False`. Save. The Signature Spec
Sheet PDF will stop flagging the line as pending.

**"A hardware brand merged with another — Hettich bought Brand X. Can I
delete Brand X?"**

Brand has `ondelete='restrict'` on `x_hardware_brand_id` — you can't
delete a brand that has products referencing it. Don't delete. Instead:
(a) reassign each product's `x_hardware_brand_id` from Brand X to
Hettich (use the list view, multi-select, edit brand); (b) set Brand X's
`active = False` to hide it from selection while preserving history.
A code change to the brand `code` field will break `hardware_map.json`
lookups — don't change codes.

## What the system is doing behind the scenes

The hardware catalog is a small ecosystem:

- **`southbrook.hardware.brand`** — a tiny model so Odoo CE doesn't
  need OCA `product_brand`. 19 seeded brands; one Many2one from
  `product.product.x_hardware_brand_id`.
- **`product.product` extensions** — 12 added fields (the
  `x_hardware_*` set plus the spec fields). All are stored-related to
  `product.template` (Tier 1.2 audit refactor) so writes propagate
  cleanly across variants. The legacy XML seed that declared records as
  `product.product` continues to work because the related/stored
  declaration routes writes to the template.
- **`southbrook.hardware.catalog`** — an `AbstractModel` (no records;
  just a service) exposing `resolve(...)`. The mapping lives in
  `data/hardware_map.json` (sections: `per_door`, `per_door_soft_close`,
  `per_drawer`, `per_shelf`, `per_cabinet`, `per_family`,
  `pull_default_skus`, `knob_default_skus`, `by_pull_finish`,
  `by_knob_finish`, `appliance_pulls`).
- **`southbrook.hardware.import.wizard`** — a `TransientModel` that
  walks the CSV row by row inside a per-row savepoint, validates against
  `REQUIRED_COLS` + `HARDWARE_CATEGORY_KEYS`, upserts by `x_marathon_sku`,
  and returns a result-log view.

When you confirm an order and the FreeCAD bridge writes the cabinet
geometry, the bridge calls `resolve()` per cabinet line with the
configured family + counts + finish. The returned tuples become BoM
component lines on the cabinet's `mrp.bom` record. That BoM then flows
into the `mrp.production` record on order confirm.

Critical observation: the resolver fails *soft*. A missing SKU logs a
warning and skips the line; the resolver doesn't raise. So a partial
hardware catalog (the 20-row seed today vs the 179-row trade workbook
tomorrow) installs cleanly and produces working orders with
under-populated BoMs. The expectation is that the trade workbook lands
before production cutover.

## Quiz (5 questions, applied)

**1.** You configure an `SB-BASE-2DR` with soft-close, brushed nickel
128 mm pulls, one shelf. The customer also asks for an additional
matte-black appliance pull because they're swapping the dishwasher
later. Walk through how to get the appliance pull on the BoM.

> The standard resolve() call won't add an appliance pull on a base
> cabinet — `mount_appliance=True` is only set for tall_oven / tall_fridge
> by the configurator. For a manual appliance-pull add, edit the
> order: add a line for the matte-black appliance-pull SKU
> (`MRH-HDL-APP18-MB` if it exists in the catalog, otherwise the
> brushed-nickel `MRH-HDL-APP18-BN` is the seeded SKU). Qty 1, note
> "customer-supplied dishwasher pull, install on appliance door".
> Don't try to retrofit the resolver mid-quote.

**2.** Your admin asks you to import a 179-row Marathon CSV. You run
dry-run; the log shows 12 errors all on the `brand_code` column:
`unknown brand_code 'rev-a-shelf'`. What's the cause and the fix?

> The CSV references a Rev-a-Shelf brand that doesn't exist in
> `southbrook.hardware.brand`. Fix: add a brand record with name =
> "Rev-A-Shelf" and code = `rev-a-shelf` (the CSV's exact lowercase
> form). Re-run dry-run. If the 12 errors are now zero, run the
> non-dry-run import. The 12 rows will be created against the new
> brand. Lesson: when a new brand appears in a Marathon refresh, seed
> the brand before importing the products.

**3.** A confirmed order's BoM shows zero hinges on a 2-door base
cabinet that should have 4. What's the most likely cause, and where do
you start?

> Either (a) `BLM-110-SC` is missing from the installed catalog (most
> likely — check Odoo's log for `hardware_map references SKU
> 'BLM-110-SC' not present` warnings); or (b) the cabinet was
> configured with soft_close=False (an oversight or a Rule 4 hit on a
> bi-fold corner) so the resolver returned `BLM-110-NSC` instead — but
> that's also expected behaviour. Run `env['southbrook.hardware.catalog'].resolve()`
> manually in the shell with the cabinet's params to confirm what
> SKUs *should* be there, then check which are missing from
> `product.product`.

**4.** The customer's hardware budget is tight and they ask you to
swap the standard Blum soft-close hinges for the non-soft-close
variant. You don't want to disable soft-close on the configurator (the
customer might still want soft-close on the drawers). What's the right
move?

> The resolver's `soft_close` parameter is per-call — toggling it from
> the configurator UI affects every door + drawer on that cabinet
> uniformly. You can't currently split door soft-close from drawer
> soft-close at resolve time. Two options: (a) accept the constraint
> and tell the customer it's all-or-nothing for that cabinet; (b)
> after resolving, manually edit the cabinet's BoM to swap `BLM-110-SC`
> lines for `BLM-110-NSC` while leaving the drawer slides as soft-close
> (BLM-MOV-450 is the standard slide — independent of door soft-close).
> Document the override in the order's internal notes.

**5.** A new estimator says "I added a hardware line for `MRH-HDL-KNB30`
on the order but it's showing $0.00 — is that wrong?" What do you check?

> Look at the product variant's `x_pricing_pending` field. If true,
> Southbrook didn't have a cost for that SKU at import time and the
> list_price defaulted to 0. Don't sell at $0 — either look up the cost
> from the Marathon trade portal and update `standard_price` +
> `list_price` (then clear the pending flag), or pull the line and
> swap to a SKU that has a price. Recovery shortcut: if the
> Spec Sheet PDF flags pricing-pending lines, the customer would have
> seen the asterisk before signing — so the $0 is a visible signal,
> not a silent leak.

## What this lesson does NOT cover

- The configurator vocabulary (attributes / exclusions / construction
  rules) — lesson 5.1.
- How to build the actual quote — lesson 5.2.
- The Configurator UX v2 deltas vs OCA stock — lesson 5.4.
- The FreeCAD bridge that consumes `resolve()` output to generate
  cabinet renderings — Course 4 (PLM + Design), lesson 4.3.
- General Odoo Inventory administration — Odoo's own native eLearning
  track.
- The trade-account access workflow to obtain Marathon's catalog — an
  ops / purchasing concern, not estimating.
