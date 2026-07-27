---
course: 17
chapter: 17.30
title: Quality — Score a Supplier After a Defect
duration: 2
audience: Quality manager
jtbd: score a supplier after a defect
department: Quality
custom_modules: southbrook_quality
---

# Quality — Score a Supplier After a Defect

## When you use this

A defect traced to incoming materials (warped boards, scratched hardware,
wrong colour finish) — you want to log it against the supplier so
purchasing has the data for the next contract negotiation.

## Where this lives

**Quality → Supplier Defects** (`menu_southbrook_quality_supplier_defects`).

## The 4-field minimum

1. **`supplier_id`** — `res.partner` flagged as vendor
2. **`po_id`** — the purchase order the defect came from (auto-narrows
   product list)
3. **`product_id`** — the SKU
4. **`defect_count`** + **`defect_type`** + **`severity`**

## How scoring rolls up

The supplier scorecard (`res.partner` form, *Supplier* tab) auto-derives:
- `defect_rate_pct` — defects per receipt over 90 days
- `on_time_delivery_pct` — comes from PO receipt timestamps
- `consolidated_score` — weighted blend; visible to purchasing

## Common gotchas

- **Supplier doesn't have a Supplier tab** — they're not flagged as
  vendor. Tick *Is a Vendor* on their partner record.
- **PO not in dropdown** — check that PO state is `purchase` or `done`;
  drafts don't show.
- **Defect logged but score doesn't move** — there's a nightly recompute
  cron; same-day saves don't reflect until tomorrow.

## Deep dive

→ Course 18 (Quality Module — to be authored)
