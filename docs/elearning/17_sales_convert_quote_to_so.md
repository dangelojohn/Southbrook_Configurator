---
course: 17
chapter: 17.4
title: Sales — Convert a Quote to a Sales Order
duration: 2
audience: Sales rep with a signed quote ready to confirm
jtbd: convert a quote to a sales order
department: Sales
custom_modules: southbrook_estimating
---

# Sales — Convert a Quote to a Sales Order

## When you use this

The customer has signed (or verbally approved). You want to release the
order to production.

## Stock vs Southbrook states

Native Odoo SO states: `draft → sent → sale → done`.
Southbrook also tracks: *Estimating → Approval → Confirmed → In Production*
via the `southbrook_submitted_date` milestone field overlay (see audit
note #8 in `docs/elearning/README.md`).

You work with the **native button** at the top: *Confirm*. The Southbrook
overlay updates automatically.

## The 3-step flow

1. **Verify channel + pricelist** still match the customer. If they renegotiated
   tier, change `res.partner.channel` first.
2. **Verify zones add up.** Multi-zone orders (BASE_RUN + WALL + TALL) should
   total what the customer signed.
3. **Click *Confirm*.** SO state → `sale`. The MI engine + kitchen-project
   release gate (Course 2 lesson 2.2) take over from here.

## What fires automatically on confirm

- Kitchen Project (`sb.kitchen.project`) created or linked
- Manufacturing Order(s) drafted via `product_configurator_mrp` BoM rollup
- Spec sheet PDF + 3D scene shipped to the production package
- Hermes channel notification (if the customer is a partner with a Hermes
  surface)

## If the Approval gate blocks you

Above-threshold orders need a Sales Manager approval click. The threshold
is a configurable system parameter; the form will surface a warning banner
telling you who can release it.

## Common gotchas

- **Order disappears from your queue after confirm** — that's correct; it
  moves to the Production Planning queue (Course 2).
- **MO didn't appear** — check `Kitchen Ops → Release Queue`. The release
  gate may be waiting on ECO clearance or cut-spec authoring.

## Deep dive

→ Course 8 lesson 8.5 *Quote-to-MO Handoff*
→ Course 2 lesson 2.2 *Release Gate*
