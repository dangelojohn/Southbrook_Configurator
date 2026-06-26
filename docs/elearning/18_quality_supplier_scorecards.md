---
course: 18
chapter: 18.5
title: Quality Inspector — Supplier Defect Tracking and Monthly Scorecards
duration: 14
audience: Quality manager working with purchasing on supplier performance
prereqs: Lesson 18.2 (NCR lifecycle), basic understanding of POs in Odoo
custom_modules: southbrook_quality
---

# Quality Inspector — Supplier Defect Tracking and Monthly Scorecards

## Who this lesson is for

You're the quality manager who attends the monthly supplier review
meeting with the purchasing manager. You bring data; they bring
contracts and lead times. The decisions made together affect cost,
quality, and customer experience. This lesson is how you build the
defensible data.

## Where this lives on the site

**Quality → Supplier Defects** (`menu_southbrook_quality_supplier_defects`).

Supporting menus:
- **Contacts → Vendors** — supplier master records, scorecard lives
  here in a notebook tab.
- **Purchase → Orders** — the PO records each defect references.

## What your screen shows

### Supplier Defects list view
- Grouped by `supplier_id` by default
- Decoration-warning: defects in last 7 days
- Decoration-danger: severity = critical OR defect_count > 5

### Supplier Defect form view
- `supplier_id` — `res.partner` flagged as vendor (mandatory)
- `po_id` — the PO this came from (mandatory, auto-narrows products)
- `product_id` — the SKU (mandatory)
- `defect_count` — how many units affected
- `defect_type` — selection
- `severity` — selection
- `description` — free text
- `linked_ncr_ids` — NCRs that this defect triggered downstream
- `is_warranty_claim` — boolean; flag if supplier should cover cost

### Vendor scorecard tab (on res.partner)
- `defect_rate_pct` — defects per receipt over 90 days
- `on_time_delivery_pct` — comes from PO receipt vs `date_planned`
- `consolidated_score` — weighted blend (40% defect, 40% delivery,
  20% lead time consistency)
- `score_trend` — last 6 months as a sparkline

## Logging a supplier defect

The flow is short — but doing it well is what matters.

### 1. Identify the source
- Was the defect in a material lot you received from this supplier?
- Was the PO recent enough that the supplier is reasonably
  accountable? (Within 90 days is the workbook standard.)
- Is there a Southbrook handling cause that explains it instead?
  (Pallet drop during receiving, warehouse damage, etc.) If so, log
  it as `defect_type = handling` with NO supplier link.

### 2. Open the supplier defect
- *Quality → Supplier Defects → New*
- Pick `supplier_id`. PO dropdown auto-narrows to their recent POs.
- Pick `po_id`. Product dropdown auto-narrows to that PO's lines.
- Pick `product_id`. Enter `defect_count` + `defect_type` +
  `severity`.
- Describe what you saw + ideally attach a photo.

### 3. Link to downstream NCRs
- If this supplier defect surfaced through customer-side NCRs, link
  them via `linked_ncr_ids`. The scoring weights `linked_ncr_count`.

### 4. Mark warranty (if applicable)
- `is_warranty_claim = True` if the supplier should absorb the cost
  (replacement material, scrap reimbursement). Sends a notification
  to the purchasing manager who triggers the claim.

## The monthly review meeting

A typical first-Monday-of-the-month, 60 minutes with the purchasing
manager:

1. **Open the consolidated scorecard.** *Contacts → Vendors* list,
   sorted by `consolidated_score` ascending. Bottom 5 are the focus.

2. **For each bottom-5 supplier**, open their record + Supplier tab:
   - Read `defect_rate_pct`, `on_time_delivery_pct`,
     `consolidated_score`
   - Click through to *Quality → Supplier Defects* filtered to that
     supplier — read the defects from the last 90 days
   - Decide actions:
     - **Talk to them** (purchasing's lead) — share the data; ask
       for corrective action
     - **Switch** — start sourcing alternates if a contract pivot
       is feasible
     - **Tier down** — keep them but reduce volume + change
       inspection protocol
     - **Document for renewal** — file the data for the contract
       renewal conversation

3. **For your top-5 suppliers**, also worth a 2-minute scan — has
   anything degraded? Catching the slip before it's chronic.

4. **Cross-check with quality outcomes** — has a supplier issue
   surfaced as a finished-goods NCR or customer return? Trace the
   chain; raise it if so.

5. **Document the meeting**. Post a summary to a shared *Quality
   Monthly Reviews* knowledge article (or chatter on the partner
   records if no knowledge article exists).

## Common mistakes + how to recover

- **"I logged a supplier defect but I'm not sure the right PO."**
  Edit the `po_id` before the monthly run. Wrong PO + right
  supplier still affects the scorecard correctly; wrong supplier is
  what matters.

- **"Scorecard hasn't moved despite 5 defects logged."** Nightly
  cron recompute. Today's logs are visible tomorrow morning. Don't
  retry-click *Compute*; the field is `compute_sudo=False` and
  recomputes on cron.

- **"Supplier protests the defect rate."** Show them the underlying
  records (use the *Print → Supplier Defect List* report). If they
  identify a logging error, fix it — the scorecard recomputes
  cleanly.

- **"Receiving handed me damaged boards. The supplier's manifest
  marks them shipped clean. Who logs the defect?"** You log it as
  the quality team; mark `is_warranty_claim = True`. Purchasing
  decides whether to file the warranty claim based on the freight
  contract.

- **"Supplier provided a credit. Do I close the defect record?"**
  No — close means archive. The defect record stays for trend
  analysis. Mark `is_warranty_claim = True` and post the credit
  reference in the chatter.

## What the system is doing behind the scenes

- **Defect create** writes the record. No immediate score effect.
- **Nightly cron** at 03:30 (`southbrook_quality.mi_engine_ext.
  rollup_supplier_scores`) recomputes every active supplier:
  - `defect_rate_pct = sum(defect_count) over last 90d / sum(received qty) over last 90d`
  - `on_time_delivery_pct = (received within ±3d of date_planned)
    over last 90d / total receipts over last 90d`
  - `consolidated_score = 0.4 * (1 - defect_rate) + 0.4 *
    on_time_delivery + 0.2 * lead_time_consistency`
- **Trend sparkline** stores the last 6 monthly snapshots in a JSON
  field on the partner.
- **Warranty claim** posts a `mail.activity` to the purchasing
  manager group.

## Quiz (5 questions, applied)

**Q1.** Receiving identifies 3 damaged boards in a 50-board lot from
Marathon. Lot was received 2 days ago. Severity?

> `major`, `defect_count = 3`. The 3 damaged boards are out of spec.
> Mark `is_warranty_claim = True` since they were damaged at receipt.
> Photos attached.

**Q2.** A supplier scorecard shows `defect_rate_pct = 2.5%` but you
remember logging more defects than that. What's the explanation?

> The rate is defect units / received units, not defect events /
> receipts. If the supplier ships large lots, the defect rate stays
> low even with several events. The event count is on the related
> defect list.

**Q3.** A finished cabinet NCR (`defect_type = hardware`) was traced
to a Marathon hinge from a specific PO. Action?

> Open a supplier defect linked to that PO + product + the Marathon
> partner. `linked_ncr_ids` = the original NCR. Severity major (you
> shipped customer-facing). Mark `is_warranty_claim = True` if cost
> recovery is appropriate.

**Q4.** Monthly review: a supplier's `consolidated_score` is 0.75
(your bar is 0.85). Purchasing wants to renew. Your evidence?

> Open the supplier's defect list (last 90 days) + the score trend
> (last 6 months). If trend is degrading, that's the argument.
> Quantify customer impact: NCRs that traced to their materials,
> warranty claims, scrap cost. Bring numbers, not feelings.

**Q5.** Same supplier — score recovered to 0.88 this month. Purchasing
wants to celebrate. Your read?

> One month doesn't make a trend. Look at the underlying defect
> count — did volume drop because of a supplier improvement, or
> because Southbrook ordered less? Look at delivery — was the
> improvement luck or a fixed root cause? Cautious optimism;
> revisit next month.

## What this lesson does NOT cover

- NCR lifecycle on the customer-facing side — lesson 18.2.
- SPC + Cpk for in-house process — lessons 18.3 + 18.4.
- The Purchase side of supplier management — separate course (native
  Odoo Purchase training).
- Vendor PIM / contract management — currently in spreadsheets;
  v1.2 candidate for a Southbrook addon.
