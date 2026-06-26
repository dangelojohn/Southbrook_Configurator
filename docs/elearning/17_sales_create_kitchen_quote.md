---
course: 17
chapter: 17.1
title: Sales — Create a Kitchen Quote
duration: 4
audience: Sales rep with a customer on the phone or in the showroom
jtbd: create a kitchen quote
department: Sales
custom_modules: southbrook_estimating, southbrook_configurator_ux
---

# Sales — Create a Kitchen Quote

## When you use this

A customer says "what would this kitchen cost?" — start here. Works for both
walk-in retail and channel-priced orders (dealer, contractor, KD, big-box,
refacing). The same Order Builder serves all six channels — pricing flips
automatically when the customer changes.

## Where this lives

**Sales → Order Builder → New**

The Order Builder menu (`menu_southbrook_order_builder`) is the canonical
entry point. Native Sales → Quotations also works but skips the multi-zone
grid + channel auto-resolution.

## The 5-step flow

1. **New record.** Top-right *New*.
2. **Customer.** Search the partner field. If a walk-in, use `Retail Walk-In`
   (seeded as a partner with `channel=retail`).
3. **Add a zone.** Default zone is BASE_RUN. Switch to WALL / TALL / ISLAND /
   ACCESSORY / OTHER as appropriate. (For OTHER, fill in `zone_label`.)
4. **+ Add Cabinet.** Opens the inline config drawer with all 11 attributes —
   family, width, series, box_material, door_style, finish, hinge_side,
   finished_sides, gables, handle, accessories.
5. **Save.** Spec sheet PDF generates and attaches to the SO; price reflects
   the customer's resolved pricelist.

## Common gotchas

- **Customer not found** → use the *Quick-create* dropdown at the end of the
  partner list. Set their `channel` immediately after creating, or they'll
  default to `retail`.
- **Wrong price** → check `res.partner.channel` on the header; it drives the
  pricelist. Switching the customer mid-build re-prices every line in place.
- **Maple box adds +10%** silently — that's the config rule from
  `Southbrook_Excel_to_Odoo_Mapping.md §3.4`, not a bug.
- **9-21″ cabinet shows as 1-door only** — also a config rule (width → door
  count). Door style options 2-door are correctly hidden.

## Want the deep dive?

→ Course 5 lesson 5.2 *Building a Quote from a Kitchen Design*
→ Course 8 lesson 8.4 *Order Builder Walkthrough*
