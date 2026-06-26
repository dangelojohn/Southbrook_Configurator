---
course: 17
chapter: 17.26
title: Maintenance — Close a Breakdown and Capture Downtime
duration: 2
audience: Maintenance technician returning from a fix
jtbd: close a breakdown and capture downtime
department: Maintenance
custom_modules: southbrook_cmms_wms
---

# Maintenance — Close a Breakdown and Capture Downtime

## When you use this

You've fixed the machine. You need to close the breakdown alert + log the
downtime so MTBF / MTTR (lesson 17.27) compute correctly.

## The 4-step close

1. **CMMS → Breakdown Alerts**, find your dispatched alert.
2. **Click *Mark Fixed*** at the top. Wizard asks for:
   - `total_downtime_min` — when the equipment came back online
   - `root_cause` — free text (or pick from common list)
   - `parts_used` — m2m to inventory
3. **Submit.** State → `fixed`. The auto-linked
   `maintenance.request` also closes with the same data.
4. **Unblock affected MOs** (if you used *Block Affected MOs* earlier).
   The MO unblock is on the alert form's secondary action menu.

## Why downtime accuracy matters

- MTBF (lesson 17.27) = (period_runtime - total_downtime) / breakdown_count
- MTTR = sum(total_downtime) / breakdown_count
- Under-reporting downtime makes the equipment look better than it is;
  over-reporting makes you look slow to fix
- These numbers drive PM schedule decisions and capex justifications

## Common gotchas

- **Downtime field blank** — close is rejected. Estimate honestly; you
  can edit later if the audit pass catches an issue.
- **Forgot to log parts** — open the linked `maintenance.request` and
  edit. Parts-used drives the spare-stock auto-reorder.
- **Same equipment broke again 2 hours later** — open a NEW alert; don't
  reopen the closed one. MTBF math depends on distinct events.

## Deep dive

→ Course 12 lesson 12.6 *MI Engine Observability*
