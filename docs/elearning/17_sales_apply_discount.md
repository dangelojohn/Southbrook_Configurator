---
course: 17
chapter: 17.5
title: Sales — Apply a Discount Above Your Threshold
duration: 3
audience: Sales rep being asked for a discount past their auto-approval limit
jtbd: apply a discount above my threshold
department: Sales
custom_modules: southbrook_estimating
---

# Sales — Apply a Discount Above Your Threshold

## When you use this

Customer asks for 10% off; your tier auto-allows 5%. This is the manager-
approval workflow.

## Where the threshold lives

The threshold is the difference between the resolved pricelist line and the
manual discount you enter. Sales reps have a personal threshold on their
`hr.employee` record; sales managers have a higher one; some big-box channel
discounts have no cap because they're locked to a fixed wholesale price.

## The 3-step flow

1. **Apply the discount.** Open the SO line, edit `discount` field. The header
   highlights in amber when you cross your threshold — *Pending Manager
   Approval*.
2. **Click *Request Approval*** in the header. This stamps
   `southbrook_submitted_date` + posts an activity to your designated
   approval chain (a sales manager partner).
3. **Approver clicks Approve.** Header turns green. You can confirm the SO.

## Common gotchas

- **Approval activity goes to the wrong manager** — chain is determined by
  `hr.employee.parent_id` (your reporting manager). Update HR if wrong.
- **Approver edits the discount** — that's allowed; the approval covers the
  edited value, not the originally requested one.
- **Auto-confirm bypass** — if you confirm before approval, the state machine
  rejects with a UserError. Don't try to work around it.

## Channel-specific notes

| Channel | Discount cap behaviour |
|---|---|
| Retail | Standard threshold table |
| Dealer | Capped at signed-agreement floor — can't be exceeded |
| Contractor | Tier 1/2/3 (25/30/35%) auto-applied; rep can stack 5% extra without approval |
| KD | Component pricing only, ~46% of retail; no further discount allowed |
| Big-box | Fixed wholesale — discount field disabled |
| Refacing | Margin-target rule recomputes; manual override needs manager OK |

## Deep dive

→ Course 8 lesson 8.3 *Pricing Zones and Channels*
