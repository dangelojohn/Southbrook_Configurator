---
slug: 04_lifecycle
title: Order Lifecycle
source: canonical
version: 1
audience: [trade_partner, sales_rep, mfg_manager]
last_reviewed: 2026-06-16
---

# Order Lifecycle

Every order travels through eight defined stages.

## Stages

| # | Stage | What it means |
|---|---|---|
| 1 | Draft | Partner is actively configuring. No commitment. |
| 2 | Estimating | Partner clicked "Send to Production." Southbrook's estimating team reviews and validates. |
| 3 | Approval | Internal sign-off. CAD and cutlist must be approved. BoM confirmed. |
| 4 | Confirmed | Locked. Manufacturing Orders are generated. Work Orders assigned. |
| 5 | In Production | Active manufacturing. Real-time tracking via Kitchen Job Command Center. |
| 6 | Quality Control | Final QC. |
| 7 | Delivery | Packed by project/room, shipped flat-pack. |
| 8 | Install | On-site install support if contracted. |

## What a partner can change at each stage

| Stage | Attribute changes | Quantity changes | Door/finish swaps | Cancellation |
|---|---|---|---|---|
| Draft | yes | yes | yes | yes |
| Estimating | yes — produces v2 | yes | yes | yes (no fee) |
| Approval | rep-mediated | rep-mediated | rep-mediated | yes (no fee) |
| Confirmed | request only — via OSRO-like flow | request only | request only | yes (with cancellation fee) |
| In Production | no — production has started | no | no | yes (with fee + may be partial) |
| QC / Delivery / Install | no | no | no | only by full return |

## Order Builder data structure

Each order in the portal is a `sale.order` record carrying:

- Order number (`S0XXXX`).
- Customer + version (`v1`, `v2`, `v3` after revisions).
- Invoice address / delivery address.
- Quotation date / expiration date / payment terms.
- Pricing channel (Retail or Channel).
- Retail subtotal / channel total / savings / lead time.
- Order lines grouped by zone (Base Run, Wall Run, etc.).

Each order has six visible tabs: **Order Lines**, **3D Kitchen**, **BOM
Preview**, **Validation**, **History**, **Customer Print**.

## Standard lead time

Two weeks from confirmation for Contractor / Contemporary / Elegance
series. Signature series adds two weeks. Maple box on any series adds
two weeks. These are rules of thumb — the live lead-time computation in
the Order Builder is authoritative.
