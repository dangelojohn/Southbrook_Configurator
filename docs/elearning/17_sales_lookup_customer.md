---
course: 17
chapter: 17.7
title: Sales — Look Up an Existing Customer and Reuse Their Last Quote
duration: 2
audience: Sales rep with a returning customer
jtbd: look up an existing customer and reuse their last quote
department: Sales
custom_modules: southbrook_estimating, southbrook_customer_portal
---

# Sales — Look Up an Existing Customer and Reuse Their Last Quote

## When you use this

Customer calls back, says *"just like last time, but add a pantry."* — don't
re-key the whole kitchen.

## The 3-step flow

1. **Find the customer.** *Contacts → Customers* or just type their name in
   the Order Builder partner field. The search hits both
   `res.partner.name` and `email`.
2. **Open their record → Sales tab.** All historical SOs are listed. Pick
   the most recent.
3. **Action menu → *Duplicate***. This copies the SO + every line + every
   `product.config.session` link. State resets to `draft`.

## Adding to the duplicate

Edit lines as needed, *+ Add Cabinet* for new ones, *Save*. Pricing
re-resolves automatically against the current pricelist (which may have
changed since their last order).

## Common gotchas

- **Customer record exists twice** — typo or email-vs-phone mismatch. Use
  *Contacts → Tools → Merge Contacts* before duplicating; otherwise the
  duplicate inherits the wrong channel.
- **Channel changed since their last order** — pricing on the duplicate will
  differ. Surface this to the customer up front.
- **Some cabinets are now end-of-life** — the duplicate will keep the
  original `product.template`. Test-confirm to see if the EOL warning fires;
  swap to current SKUs as needed.

## Portal-side equivalent

Customers can self-serve from `/my/kitchen-projects` — *Duplicate this
quote*. The action is the same; just runs as the portal user.

## Deep dive

→ Course 6 lesson 6.1 *Customer Portal*
