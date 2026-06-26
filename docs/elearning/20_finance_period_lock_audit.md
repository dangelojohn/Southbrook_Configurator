---
course: 20
chapter: 20.5
title: Controller — Period Lock and Audit-Ready Close-Out
duration: 10
audience: Controller closing the books + producing the monthly audit pack
prereqs: Lessons 20.1 - 20.4 of this course
custom_modules: southbrook_finance_pack
---

# Controller — Period Lock and Audit-Ready Close-Out

## Who this lesson is for

You're at step 7 of the monthly close (lesson 20.1). Everything else
is reconciled. Time to lock the period and produce a delivery pack
for ownership, auditor, lender, or whoever consumes your monthly
financials.

## Where this lives on the site

**Accounting → Configuration → Fiscal Years** — the lock.
**Accounting → Reporting** — financial statements.
**Finance** (all submenus) — supporting schedules.

## The 3 phases of the close-out

### Phase 1: Verify pre-lock state

Before locking, the following MUST be true:

- [ ] Bank reconciliation complete for the month
- [ ] AR + AP reconciled
- [ ] Inventory variance posted
- [ ] All journal entries posted (no drafts in period)
- [ ] WIP variance < $1
- [ ] CCA depreciation computed for the year (or month, if
  monthly basis)
- [ ] HST return prepared (if filing month)
- [ ] All payroll runs posted

If any of these aren't true, fix them BEFORE locking. Once locked,
edits in that period require a manager unlock + an audit-log entry.

### Phase 2: Lock

#### How to lock
- *Accounting → Configuration → Fiscal Years*
- Find the period you're closing (e.g. "May 2026")
- *Edit → State → Closed*
- *Save*

#### What the lock does
- `account.move.line.create()` rejected for dates in the locked
  period (with `UserError`)
- `account.move.write()` rejected for moves in the locked period
- `account.move.button_draft()` (reopen) requires manager + creates
  an audit log entry

#### What the lock does NOT do
- Read access — viewing the period is fine
- Reports — financial statements + supporting reports run fine
- Soft deletes — the data stays
- Adjustments via reversing entries in the next period — those are
  always allowed

### Phase 3: Deliver the audit pack

This is what makes the close-out *audit-ready*.

#### Standard contents of the pack

1. **Financial statements** (3 standard):
   - Balance Sheet (`Accounting → Reporting → Balance Sheet`)
   - Profit & Loss (`Accounting → Reporting → Profit & Loss`)
   - Cash Flow Statement (`Accounting → Reporting → Cash Flow Statement`)

2. **Supporting schedules**:
   - WIP Report (Finance → WIP Report)
   - Asset Register summary (Finance → Asset Register)
   - HST Return (if filed this month)
   - Aged AR (Accounting → Reporting → Aged Receivable)
   - Aged AP (Accounting → Reporting → Aged Payable)
   - Trial Balance (Accounting → Reporting → Trial Balance)

3. **Reconciliations**:
   - Bank reconciliation summary
   - WIP reconciliation memo (explain any variance > $1)
   - Inventory valuation snapshot

4. **Adjustments log**:
   - List of manual journal entries posted during close
   - Reason for each
   - Approver

5. **Memo from controller**:
   - 1-page summary of the month
   - Notable items (large adjustments, anomalies, planned
     follow-up)
   - Sign-off date + signature

#### Delivery

- PDF the pack (Odoo's *Print* on each report; merge externally
  if needed)
- Save to your audit-pack folder (e.g.
  `/share/CACHEDEV3_DATA/Audit-Packs/2026-05/`)
- Email or share-link to the recipients (ownership, accountant,
  lender)

## When auditors arrive (quarterly or annually)

The monthly packs become the audit-trail input. Auditors will ask:
- Show me the adjustments log from May 2026
- Walk me through the WIP variance reconciliation in March
- Where's the supporting doc for the $50k journal entry on
  2026-04-15?

With the monthly packs in place, the answer is fast.

## Common mistakes + how to recover

- **"Locked May; need to add an adjustment dated May 28."** Unlock
  via *Fiscal Years → State → Open*. Make the edit. Re-lock. Log
  the reason in the period's audit log via a chatter post on the
  fiscal year record.

- **"Auditor asks for a journal that doesn't show on my report."**
  The report's filter may exclude it. Re-run with broader filter
  (date range, journal type, account). If still missing, the
  journal may have been deleted (rare) — check `audit.log` for
  delete events.

- **"WIP variance was $5 at lock; auditor flagged it."** Document
  the cause in the next month's chatter. Acceptable if explained;
  unacceptable if hidden.

- **"Asset disposal was missed in the May pack."** Was disposed
  June 1; the asset register summary for May correctly shows it
  active. Not an error.

- **"Pack delivered but recipient says they didn't get an
  attachment."** Check email; some firms reject PDF attachments
  > 10MB. Share via secure link instead.

## What the system is doing behind the scenes

- **Fiscal Year close** is native Odoo; sets a constraint on
  account.move date insertion + edits
- **Audit log** is the chatter on the fiscal year + the
  `account.move.line` row's `create_date / write_date`
- **Reports** read from `account.move.line` aggregated; respect
  closed-period rules
- **No Southbrook addon writes to the close mechanism** — we use
  the native gate

## Quiz (5 questions, applied)

**Q1.** It's day 7 of close; you've completed steps 1-6; about to
lock. WIP variance is $0.15. Action?

> Document the rounding in the close audit memo. Lock. Move on.

**Q2.** Locked May. Found a missed invoice from May 22 that posted
to June. Action?

> Two options. (a) Reverse the June entry, post the entry correctly
> in May — requires unlock + relock with audit log. (b) Leave both
> entries; the financial statements close as-is, but P&L will be
> $X higher in May next year-over-year and $X lower in June. (a) is
> cleaner for the year-end; (b) is faster and OK if the amount is
> immaterial.

**Q3.** Auditor asks for the supporting doc for journal entry
#1234 from March. Where do you find it?

> Open the journal entry → chatter → attachments. If not attached,
> trace via `create_uid` and ask the creator. Documents should
> attach at creation time — establish this as policy if not
> already.

**Q4.** Lender wants the May P&L by the 10th of June. Your close
typically lands the 8th. Pressure to publish early. Action?

> Don't publish a non-closed P&L. If the 8th is your target, hit
> it. If you slip to the 10th, communicate; reset expectations.
> A wrong P&L is worse than a late one — especially to a lender.

**Q5.** Year-end is December. December close + year-end audit pack
overlap. Order of operations?

> Close December as a normal month FIRST (steps 1-7). THEN add
> the year-end specifics: CCA computes for the year, T2 prep, T4
> distribution. Year-end is a SUPERSET of month-end, not a
> replacement.

## What this lesson does NOT cover

- Specific report customisation (separate Odoo Accounting
  training).
- Year-end T2 corporate tax prep — accountant's job; you supply
  the data.
- Audit firm engagement letter logistics — finance ops topic.
- Legal entity consolidation if Southbrook has multiple companies
  — separate workflow.
