---
course: 17
chapter: 17.23
title: Floor — Flag an Inline Defect and Open an NCR
duration: 3
audience: Any floor operator catching a defect mid-build
jtbd: flag an inline defect and open an ncr
department: Production Floor
custom_modules: southbrook_quality
---

# Floor — Flag an Inline Defect and Open an NCR

## When you use this

You catch a defect (chipped panel, wrong colour, mis-cut, scratch) DURING
your station's work. You need to stop the cabinet from progressing AND
get the quality team a record.

## The 3-tap flow

1. **On the work order card → *Hold → Inline NCR*.** This is the
   workcenter-side button (faster than navigating to the Quality menu).
2. **Fill the wizard:**
   - Defect type (`defect_type`): dimension, finish, hardware, material,
     handling
   - Severity (`severity`): minor, major, critical
   - One-sentence description + photo if you can grab one
3. **Submit.** Creates a `southbrook.ncr` record auto-linked to the
   `mrp.production` + `product.product`. Cabinet status → quarantine on
   the kanban (red border).

## What happens next

- The cabinet stops moving down the line until quality clears it
- Quality manager gets a notification (Course 3 deep dive)
- If severity = critical, the MI engine pages the Plant GM
- An ECO may follow if the defect points at a design issue

## Why "stop the line" is the right move

A defect that escapes the floor costs ~10x to fix at install. The
platform is intentionally biased toward catching it now — the kanban
turning red is by design, not a "you broke something" signal.

## Common gotchas

- **Inline NCR button greyed out** — your role's group doesn't include
  *Southbrook Quality / User*. Ask your supervisor.
- **NCR submitted but cabinet keeps moving** — the kanban relies on the
  `mrp.workorder.state`; if you tapped *Done* before *Hold → Inline
  NCR*, the cabinet already moved. Manual recovery from the NCR
  form's *Block downstream WOs* button.
- **Photo upload fails** — attach later from the NCR record. Don't let
  it block the submit.

## Deep dive

→ Course 1 lesson 1.6 *Logging Downtime* (companion flow)
→ Course 6 *Customer Touchpoints* (when NCRs escalate to customer)
