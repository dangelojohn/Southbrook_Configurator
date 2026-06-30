---
slug: 07_partner_faq
title: Partner FAQ
source: canonical
version: 1
audience: [trade_partner]
last_reviewed: 2026-06-16
---

# Partner FAQ

Twenty common partner questions and the canonical answer. Hermes will
match against these to keep its tone consistent.

## Where is my kitchen?

Look at the order's PM Phase in the Kitchen Job Command Center.
The phases are Design & Quote → Cutting & Machining → Assembly →
Finishing → Delivery & Install. For confirmed orders, the Kitchen Job
also surfaces a Manufacturing Reality line ("6 Confirmed; 47 WOs / 39
not scheduled") and a current bottleneck work center. Hermes can read
all of this and translate it to plain language on request.

## What's blocking my install?

The Kitchen Job's "Top Blocker" field carries this directly. Common
blockers: CAD approval pending, cutlist not validated, components not
available, doors back-ordered, finished panels not yet finished.

## Can I still change the door finish on a confirmed order?

Confirmed orders are technically locked, but a request to change a
finish goes through the recommendation flow — Hermes can draft the
request and your sales rep approves it. Whether the change is actually
possible depends on whether your kitchen has cleared the Finishing stage.
If it has, the change becomes a partial remake at additional cost.

## When will my install be ready?

The Kitchen Job carries `install_due`. The risk flag (`On Track`, `At
Risk`, `Blocked`) tells you whether that date is currently believable.
"At Risk" means the install date is in the calendar but at least one
upstream blocker exists that would have to clear immediately to hold it.

## What does Series=Signature mean for my order?

Signature is our premium tier. It mandates a Maple box, ships flat-pack,
adds 2 weeks of lead time over our standard 2 weeks, and unlocks the
full attribute range (all door styles, all finishes, all wood species).
Pricing is roughly 1.4–1.6× Contractor for the same shape.

## Why is Cherry costing more than Maple on my Signature?

Wood species pricing scales with material cost. Cherry, Walnut, and
White Oak typically run 15–25% above Maple. The Order Builder shows
the per-line uplift; your dealer pricelist may bury some of it under a
channel discount.

## I selected Five-Piece doors but the configurator now says I need
Elegance series. Why?

Rule R2: Five-Piece doors are only manufactured on the Elegance series.
Switching series will re-price your line. The configurator blocks the
combination so you can't accidentally promise a customer something we
can't make.

## Where do I see the BoM for my order?

Order Builder → BOM Preview tab. The BoM updates live as you change
attributes. It shows the carcass panel list, the door schedule, and
the hardware pick list. It's also what the shop floor will use to cut
your panels — so what you see is what gets manufactured.

## Can I get a PDF of the spec sheet to send my customer?

Order Builder → Customer Print. There are two prints: a customer-friendly
"Signature Series" PDF, and a separate Door Order print for production.
Hermes can resend either to your own email via `send_spec_pdf_email`.

## My customer wants to reschedule install — what do I do?

Hermes can draft a reschedule request from any Confirmed-or-later order.
The request goes to your sales rep, then to manufacturing. If the new
date is achievable (work-center capacity + dispatch slots), it gets
approved without you doing anything else.

## Why did you cancel my draft revision?

Drafts auto-expire after 30 days if not approved. If you want to revive
one, your sales rep can duplicate it as a new v2.

## What does "Carcass Assembly" mean in the Kitchen Job?

It's the work center where the cabinet box (carcass) is built from the
panels we cut at CNC. It's the most common bottleneck in our shop, so
Kitchen Jobs often surface it as the Top Blocker even when other
stations are also behind.

## What if I disagree with the price?

The price is computed from the live pricelist + channel discount +
attribute uplifts. If it looks wrong, contact your sales rep — they can
see the breakdown and adjust if there's an error. Hermes will not
negotiate pricing.

## Can I add a custom cabinet outside the catalog?

Not directly through the configurator. Request a Custom line through
your sales rep. Custom lines route through Engineering before pricing.

## My quote expired — does that mean I lost the design?

No. Configurations are saved as `product.config.session` records and
the quote can be re-issued as a new version. Your sales rep can
duplicate-as-draft.

## How do I know if a configuration violates a rule?

The Validation tab in the Order Builder. Hard violations are blocking
(red); soft suggestions are advisory (yellow). Hermes can list current
violations via `get_order_line` and explain which rule was hit.

## What's the difference between Retail and Channel pricing?

Retail is list price. Channel is your dealer-specific pricelist (Dealer
−50%, Contractor tier-discount, etc.). The Order Builder shows both
side-by-side with a Savings column.

## When do I owe payment?

Payment terms are set on the order header. Standard is 50% deposit
on Confirmation, 50% on Delivery. Some channels (Big-Box wholesale)
have different terms.

## Can I see my orders from last year?

Yes — list filter on the My Orders page, or ask Hermes to list. Hermes
can summarize trends ("you confirmed 14 orders last quarter, average
deal $28K").

## Why is my Kitchen Job showing 39 unscheduled work orders?

That means manufacturing has confirmed the MOs but hasn't yet pinned
each Work Order to a specific time slot. This is normal in the first
few days post-confirmation; the scheduling cron runs nightly to lay
them out. If the count doesn't drop within 3 business days, that's a
real bottleneck signal — Hermes can flag it via the Kitchen Job's
`unscheduled_wos` field.
