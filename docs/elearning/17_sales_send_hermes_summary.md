---
course: 17
chapter: 17.8
title: Sales — Send a Hermes Trade-Partner Summary
duration: 2
audience: Sales rep working a dealer or contractor channel order
jtbd: send a hermes trade-partner summary
department: Sales
custom_modules: southbrook_hermes
---

# Sales — Send a Hermes Trade-Partner Summary

## When you use this

A dealer or contractor sales partner just confirmed a substantial order and
you want to notify them with a Hermes-styled summary they can drop into
their CRM or share with their client.

## What Hermes can do for you

Trade partners get persona-bound access (`trade_partner` persona, tiers
T0/T1/T2). For a *send summary* job, T0 is enough — read-only assembly of
SO state + spec sheet URL + delivery window.

## The 3-step flow

1. **Open the SO.** Header shows a *Hermes* button if the customer is a
   trade partner with Hermes enabled.
2. **Click *Compose Summary*.** Opens the OWL chat panel mounted below the
   header (the `[data-hermes-chat-mount]` injection point).
3. **Pick *Send to partner*** in the action chips. Hermes assembles the
   summary using the `list_my_orders` + `get_order_status` + `get_quote_pdf_url`
   tools, formats it per the partner's preferred style, and posts it to
   their inbox (email + portal notification).

## What the partner sees

A Hermes-styled markdown card with order ID, line items, channel pricing,
spec sheet PDF link, and a *Reply via Hermes* button that opens their own
authenticated chat panel scoped to that single order.

## Common gotchas

- **No Hermes button on header** — the customer's `res.partner.share` is
  False or they're missing the Hermes group. Check both.
- **Summary missing the spec sheet URL** — `get_quote_pdf_url` returns
  empty if the QWeb report hasn't rendered yet. Print the spec sheet once,
  then re-compose.
- **Partner says they got an empty message** — the v1 sidecar JSON stub
  fires if `southbrook_hermes.sidecar_enabled` is False. Flip it on, then
  redeploy the summary.

## Deep dive

→ Course 13 (Fabio Module) lessons 13.1 - 13.7
→ Course 6 lesson 6.3 *Hermes CS View*
