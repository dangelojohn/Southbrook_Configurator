# SAMI PRD-driven Production Plan — Southbrook Improvements

**Source PRD:** `~/Downloads/SAMI_Odoo_MRP_Cabinetry_PRD.md` (SAMI v1.0, June 2026)
**Gap analysis:** `/tmp/sami_prd_gap_analysis.md` (347 lines, generated 2026-06-25)
**Locked decisions:** see § Out-of-Scope below
**Owner:** Southbrook engineering
**Last revised:** 2026-06-25

---

## Out-of-Scope (locked by owner, do not re-propose)

These five categories are explicitly excluded from any Southbrook implementation
work going forward. Rationale frozen here so a future planning pass doesn't
re-add them.

1. **§4.7 Supply Chain / Purchasing** — stock Odoo CE native handles it
   sufficiently; no Southbrook extension warranted.
2. **§4.11 Finance & Cost Accounting** — stock Odoo CE accounting + external
   Canadian payroll processor (Ceridian / ADP). No Southbrook finance addon.
3. **§4.12 HR, Payroll & Shift Management** — payroll outsourced to Ceridian /
   ADP; no Canadian payroll localization addon to deploy or maintain.
4. **§4.10 MAINT-05 (MTBF / MTTR per machine)** — insufficient telemetry data
   to compute meaningful reliability metrics. Revisit after 6+ months of
   machine event log accumulation.
5. **§6 W-07 (Industry education forum)** — already covered by
   `southbrook_elearning_internal` (29 lessons, 7 courses on website_slides).

**Note:** When a future pass through the PRD or a new feature request lands in
any of these five buckets, the answer is "use stock / outsourced / existing"
unless the owner explicitly relaxes the decision.

---

## Wave 1 — Quick wins (1-2 days each, ship this week)

Framework already exists; finish the last 20%.

| # | PRD § | Work | Effort | Impact |
|---|-------|------|--------|--------|
| 1 | MO-06 | Wire `stock.scrap` wizard into Southbrook MOs + auto-debit components | 1 d | Captures real scrap rate; needed for cost accuracy |
| 2 | INV-06 | NCR auto-quarantine: failed QC → auto-move to quarantine location | 1 d | Removes the "manual quarantine memo" trap |
| 3 | MO-08 | Make "Check availability" a BLOCKING gate on MO confirm | 0.5 d | Prevents shop-floor surprise on missing components |
| 4 | MAINT-03 | Auto-escalate operator downtime → maintenance.request creation | 0.5 d | Closes loop between operator + maintenance crew |
| 5 | N-12 | Mobile-responsive MI dashboard (CSS-only pass) | 0.5 d | Supervisors check from phone, not just desktop |
| 6 | N-13 | Compute "units/operator-hour by cell" KPI from existing WO time data | 1 d | Labor productivity KPI — data already captured |
| 7 | §7.1 | Configure Azure AD SSO (if Stelumar tenant exists) | 0.5 d | Reduces login friction across the team |

**Total: ~5 dev-days, 7 visible wins.**

---

## Wave 2 — Real value adds (1 week each)

| # | PRD § | Work | Priority |
|---|-------|------|----------|
| 8 | QC-05 | Build `southbrook.ncr` model + rework routing — blocks CSA A277 readiness | **HIGH** |
| 9 | MO-07 | Rework order creation (NCR → rework cell) — pairs with #8 | **HIGH** |
| 10 | PLM-02 | ECO impact analysis: when ECO applied, scan all live MOs for affected items + flag them | MEDIUM |
| 11 | MO-09 | Real-time MO cost roll-up (actual vs. standard) — fields exist; needs aggregation logic | MEDIUM |
| 12 | MES-08 | Real-time bottleneck detection (replace daily cron with WO-state push) | MEDIUM |
| 13 | W-08 | As-built record model: `southbrook.asbuilt` linking production.package + QC + drawings | **HIGH** (Phase 4 prereq) |

---

## Wave 3 — Integration projects (1-3 weeks each)

| # | PRD § | Work | Blocker for SAMI go-live? |
|---|-------|------|----------------------------|
| 14 | IOT-05 | Validate Homag BTL/MPR export end-to-end against a real Homag iX | **YES** — currently unverified |
| 15 | IOT-07 | Accucutt nesting feedback → scrap-as-by-product ingest | **YES** — accurate yield reporting |
| 16 | N-11 | Mattamy EDI 850/856 stub middleware (CSV ingest first, EDI later) | **YES** if SAMI deal lands |
| 17 | IOT-02 | OPC-UA gateway prototype (Homag → mrp.workorder state) | NO — but high signal |
| 18 | MES-10 | Shift handover digital log (replace paper notes) | NO — operational improvement |

---

## Recommended next-up (top 3)

If only three things ship next:

1. **#8 + #9** (NCR + rework workflow) — ~3 days; biggest single QC gap; unlocks CSA A277 prep
2. **#5 + #6** (mobile MI dashboard + units/hour KPI) — ~1.5 days; supervisors get value immediately
3. **#14** (Homag BTL/MPR validation) — until proven end-to-end, the cut-spec pipeline is a paper claim

**Total: ~6 dev-days for the three highest-impact tickets.**

---

## What's already SHIPPED (no work needed)

For reference and to avoid re-proposing things that are live:

- §4.1 BOM Management — 9/10 shipped (BOM-01 to BOM-09)
- §4.2 Manufacturing Orders — 6/11 shipped (MO-01, MO-04, MO-10, plus partials)
- §4.4 Shop Floor / MES — 5/10 shipped (MES-01, MES-02, MES-03, MES-04, MES-05)
- §4.5 Inventory — 3/10 shipped (INV-01, INV-02, INV-09) plus 3 partials
- §4.8 PLM — PLM-01, PLM-03, PLM-05 shipped
- §5 Nice-to-Have — N-02 (customer portal) shipped
- §6 Wish List — W-02, W-05, W-06 shipped; W-07 via elearning
- §10.4 Gap Analysis — Gap-03, Gap-06 shipped; Gap-01, Gap-02, Gap-04, Gap-05, Gap-07 workarounds

---

## Status legend

- **SHIPPED** — live in prod, no work needed
- **PARTIAL** — framework exists, data or last-mile wiring needed
- **GAP** — completely absent; build from scratch
- **N/A** — stock Odoo / external system covers it
- **WORKAROUND** — alternate implementation chosen vs. PRD spec

Full per-feature table at `/tmp/sami_prd_gap_analysis.md`.
