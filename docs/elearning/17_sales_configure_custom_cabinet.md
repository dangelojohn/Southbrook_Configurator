---
course: 17
chapter: 17.2
title: Sales — Configure a Custom Cabinet
duration: 3
audience: Sales rep building a non-standard cabinet for a customer
jtbd: configure a custom cabinet
department: Sales
custom_modules: southbrook_estimating, product_configurator
---

# Sales — Configure a Custom Cabinet

## When you use this

You hit *+ Add Cabinet* in the Order Builder and the inline drawer opens.
This is the 30-second tutorial on the 11-attribute wizard.

## The 11 attributes, in order

1. **family** — Wall, Base, Drawer Bank, Sink Base, Tall Pantry, Tall Oven,
   Corner, Vanity, Accessory, Worktop. Drives every downstream filter.
2. **width** — snap-list 200-1000 mm (default 600). Slider visible in
   sales-rep mode only; customer-mode shows the snap list.
3. **series** — Signature, Contemporary, Elegance, Contractor.
4. **box_material** — White Melamine (default), Maple (+10%, +2 weeks lead).
5. **door_style** — gated by series. Contractor → white thermofoil slab only.
   Elegance → five-piece woodgrain only.
6. **finish** — colour applied to the door style.
7. **hinge_side** — L, R, or N/A for centre-opening.
8. **finished_sides** — neither / left / right / both.
9. **gables** — none / matching / custom.
10. **handle** — pull, knob, integrated, none.
11. **accessories** — optional add-ons (soft-close upgrade, lazy susan, etc.).

## Rule-blocked options

If you can't click an option, the rule blocking it shows in the disabled-state
tooltip — example *"Contractor series only ships white thermofoil slab"*. The
customer-facing flow hides blocked options entirely; the sales-rep view shows
them with the rule reason.

## Save behaviour

Clicking *Save* in the drawer adds the cabinet as a `sale.order.line` with
the resolved `product.product` variant (auto-created by OCA if it's a new
combination per Q6) and a `product.config.session` link for traceability.

## Common gotchas

- **Family change wipes everything below it** — that's expected. Start the
  family decision first.
- **Saved variant won't open the drawer again** — that's also expected. To
  edit a saved cabinet, delete the line and re-add. (v1.1: in-line edit.)
- **Maple silently bumps lead time** — see lesson 17.1 gotcha #3.

## Deep dive

→ Course 5 lesson 5.1 *Configurator Basics*
→ Course 10 lesson 10.3 *Session State Machine*
