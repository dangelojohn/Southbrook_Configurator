---
course: 17
chapter: 17.28
title: Quality — Open an NCR Linked to a Specific MO
duration: 3
audience: QC inspector or quality manager
jtbd: open an ncr linked to a specific mo
department: Quality
custom_modules: southbrook_quality
---

# Quality — Open an NCR Linked to a Specific MO

## When you use this

Inline NCRs (lesson 17.23) come from the floor. Sometimes you need to
open one yourself — from a post-build inspection, a returned cabinet, or a
customer complaint.

## Where this lives

**Quality → NCRs** (`menu_southbrook_quality_ncr`).

## The 4-field minimum

1. **`production_id`** — the MO this NCR points at. Search by MO ref.
2. **`product_id`** — auto-fills from the MO usually; verify it points at
   the cabinet, not a component.
3. **`defect_type`** — dimension / finish / hardware / material / handling
4. **`severity`** — minor / major / critical

Description + photos go in the body. Activity assignment routes to the
quality manager (`group_southbrook_quality_manager`).

## State flow

`draft → quarantine → rework / scrap / accept`

- **quarantine** — cabinet is held, downstream WOs blocked
- **rework** — back to a relevant station to fix; original NCR stays
  open until the rework signs off
- **scrap** — log the loss; cabinet re-MO'd; cost rolls to scrap account
- **accept** — Quality manager decision; downstream WOs resume

## Common gotchas

- **Can't find the MO** — it may have been moved to history. Toggle the
  *Show Done MOs* filter in the search bar.
- **NCR linked to wrong product variant** — easy mistake on cabinets with
  variant attributes. Use *Open Variant Picker* on the form to swap.
- **NCR doesn't show on the SO chatter** — there's no auto-link
  from NCR to SO; trace via MO → SO origin manually.

## Deep dive

→ Memory `southbrook_quality` module deep-dive (to be authored as Course
18 in the next wave)
