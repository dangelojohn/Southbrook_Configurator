# `wc_type` is empty on 13 of 14 work centres, and that costs money

## What this module fixed

`mrp_product_costing` marks **Work Center Type** required in the work-centre form
(`views/mrp_workcenter_views.xml:17`, view `mrp_workcenter_view_mpc`). Nothing populates
it. Every work-centre form was therefore unsaveable, and because Odoo's web client saves
the record before running a header button, **Open Tablet Queue** failed too — with a
generic "Missing required fields" toast naming no field. The shop floor could not reach
its queue.

This module drops that one attribute. The Southbrook button and action were correct all
along and are unchanged.

## What this module did NOT fix, deliberately

`wc_type` has exactly one consumer in the entire codebase —
`mrp_product_costing/models/mrp_workorder.py:61`:

```python
if record.workcenter_id.wc_type == "H":
    variable_account_id = ...labour_cost_account_id
else:
    variable_account_id = ...machine_run_cost_account_id
```

It picks which GL account absorbs a work order's direct cost. With 13 of 14 work centres
NULL, that `else` fires on nearly every work order, so **labour is posting to the Machine
Run account across almost the whole shop**. Production today:

```
wc_type NULL : 13 work centres
wc_type 'H'  :  1
```

This is a live financial-accuracy defect. It is not in the Kitchen Ops audit — it was
found while tracing why the form would not save — and it is **not** fixed here, because
deciding which stations are Man and which are Machine is a finance decision, not an
engineering one. Making that call in code, quietly, would put a guess into the general
ledger.

## Decisions taken

**2026-07-31 — `sanding` and `finishing`.** Asked whether these were Man or Machine, the
answer was "both are plausible". That turned out to be correct and to be the answer:
`finishing` is not one station, it is two, and they genuinely differ — the Paint Booth has
an operator standing there spraying (Man) while the Cure/Dry Room is an oven running
unattended (Machine). The mapping is therefore per WORK CENTRE, not per station type.
`sanding` has one station, Sanding Prep, and prep sanding here is hand and orbital work
rather than a wide-belt line, so Man.

**2026-07-31 — `SB-EDGE` corrected from Man to Machine.** The 19.0.1.1.0 backfill refused
to touch it because it already carried a hand-set 'H', and flagged it instead. Confirmed
and corrected by 19.0.1.2.0: an edge bander runs a heated glue pot and a feed motor, so its
cost is machine time. Its work-order direct cost now posts to the machine-run account
alongside the panel saw, CNC boring, CNC router and door shop.

## The backfill, as applied

`wc_type` is a two-value flag: `H` = Man, `M` = Machine. Proposed mapping from the
populated `x_sbk_station_type` taxonomy. **The last two need a human answer.**

| `x_sbk_station_type` | proposed `wc_type` | reasoning |
|---|---|---|
| engineering | H — Man | design review, no machine run time |
| assembly | H — Man | carcass and door assembly is manual |
| hardware | H — Man | hardware fitting is manual |
| quality | H — Man | inspection is manual |
| packing | H — Man | packing and dispatch is manual |
| cutting | M — Machine | panel saw, machine-time dominant |
| cnc | M — Machine | CNC router/borer, machine-time dominant |
| edge_banding | M — Machine | edge bander, machine-time dominant |
| **SAND** (Sanding Prep) | **H — Man** | prep sanding is hand and orbital, not a wide-belt line |
| **PAINT** (Paint Booth) | **H — Man** | an operator stands there and sprays |
| **CURE** (Cure/Dry Room) | **M — Machine** | an oven running unattended |
| **SB-EDGE** (Edge Bander) | **M — Machine** | corrected from 'H' on 2026-07-31 |

`drilling`, `countertop`, `subcontract` and `other` exist in the selection but no seeded
work centre uses them, so they need no mapping today.

Once the two open rows are answered, the backfill is a one-off data migration. It is not
written yet, on purpose — a mapping this consequential should be approved before it exists
as code, not after.
