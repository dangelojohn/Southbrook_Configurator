---
course: 17
chapter: 17.10
title: Design — Issue an Engineering Change Order
duration: 3
audience: Designer / ECO engineer reacting to a design or scope change
jtbd: issue an engineering change order
department: Design / Engineering
custom_modules: southbrook_plm
---

# Design — Issue an Engineering Change Order

## When you use this

A confirmed SO needs a change: customer-driven (lesson 17.6), supplier-
driven (a hardware vendor discontinued a slide), or quality-driven (NCR
escalation, lesson 17.30). All three flows land here.

## Where this lives

**Engineering → PLM → ECOs**

## The 5-state flow

`draft → review → approved → released → closed`

1. **Draft.** *New*. Pick `eco_type` (customer / supplier / quality /
   internal). Pick `origin` — usually a `sale.order` or `mrp.production`
   reference. Describe the change in plain text.
2. **Review.** Submit. ECO routes to your designated reviewer chain (per
   `eco_stage` config in *Engineering → PLM → ECO Stage*).
3. **Approved.** Reviewer + Plant GM both click Approve. State auto-
   advances.
4. **Released.** Effective date stamped. From here, downstream models pick
   up the change — cut specs re-author, BoMs update, MOs flag affected
   lines.
5. **Closed.** Once the affected MO completes (or scraps), the ECO closes.

## What gets touched downstream

- `southbrook.cut.spec` — new active spec; old spec archived
- `mrp.bom` — version bump if BoM components change
- `mrp.production` — affected MOs flagged with `eco_id`; floor sees the
  banner

## Common gotchas

- **Reviewer chain wrong** — `eco_type` drives the chain via `eco_stage`.
  Internal-type ECOs go to ENG01 alone; customer-type ECOs need Sales
  Manager approval too.
- **ECO closes before MO completes** — bug; file a ticket. Should not
  happen.
- **Multiple ECOs against same MO** — allowed, but they apply in commit
  order. Latest released ECO wins.

## Deep dive

→ Course 4 lesson 4.1 *Engineering Change Orders*
