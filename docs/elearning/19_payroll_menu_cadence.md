---
course: 19
chapter: 19.1
title: Payroll Admin — Your Menu and the Bi-Weekly Cadence
duration: 10
audience: New payroll administrator onboarding to the Southbrook Canadian payroll module
prereqs: Familiarity with Canadian payroll concepts (CRA, CPP, EI, T4, ROE)
custom_modules: southbrook_payroll_ca
---

# Payroll Admin — Your Menu and the Bi-Weekly Cadence

## Who this lesson is for

You're stepping into the payroll admin role. You'll run payroll every
other Friday for Southbrook's bi-weekly employees. This lesson hands
you the map: what menus, what cadence, what the deadlines look like.

## Where this lives on the site

**Payroll** (root menu, `menu_southbrook_payroll_root`).

Submenus:

| Submenu | XML id | Purpose |
|---|---|---|
| Contracts | `menu_southbrook_payroll_contracts` | hr.contract records — wages, schedules, deductions |
| Runs | `menu_southbrook_payroll_runs` | the bi-weekly payroll batch (`hr.payroll.run` extension) |
| Payslips | `menu_southbrook_payroll_payslips` | individual slips inside a run |
| T4 | `menu_southbrook_payroll_t4` | year-end T4 slips |
| ROE | `menu_southbrook_payroll_roe` | Records of Employment |
| Certifications | `menu_southbrook_payroll_certifications` | employee certifications (WHMIS, first aid, etc.) — touches pay differentials |
| Tax Brackets | `menu_southbrook_payroll_tax_brackets` | CRA 2026 federal + provincial brackets (read-only for most) |

## The Southbrook bi-weekly cadence

| Day | What happens | Who acts |
|---|---|---|
| Sunday EOD | Pay period ends | (auto) |
| Monday | Employees finish entering hours | Employees |
| Tuesday | Supervisors approve timesheets | Supervisors |
| Wednesday | You pull the run + spot-check | Payroll admin |
| Thursday | Compute payroll + Plant GM approves | Payroll admin + Plant GM |
| Friday | EFT file generated + uploaded to bank | Payroll admin |
| Friday EOD | Payslips visible to employees on portal | (auto) |
| Following Monday | First-Monday banking deposits | (bank) |

Hard deadlines:
- **CPP / EI / income tax remittance** to CRA: monthly (by the 15th
  of the following month) for most employer sizes; quarterly only if
  prior-year remittances were under $25k.
- **T4 distribution** to employees: by Feb 28.
- **T4 Summary filing** to CRA: by Feb 28.
- **ROE filing** to Service Canada: within 5 calendar days of pay
  period end (or 30 days from employment end if no pay period crosses
  it).

## What your screen shows

### Payroll Runs list
- Decoration-info: state `draft`
- Decoration-warning: state `pending_approval`
- Decoration-success: state `done`

### Payroll Run form
- `name` — auto, "Bi-Weekly Run YYYY-MM-DD to YYYY-MM-DD"
- `period_start`, `period_end`, `pay_date`
- `state` widget: draft → computing → pending_approval → approved → done
- Statusbar buttons gated on state
- Notebook tab *Payslips* — embedded list
- Notebook tab *Totals* — gross / CPP / EI / income tax / net per the
  whole run
- Notebook tab *Audit Log* — chatter + activity history

### Payslip form
- `employee_id`, `contract_id`
- Notebook tab *Earnings* — regular, overtime, holiday, bonuses
- Notebook tab *Deductions* — CPP, EI, income tax, RRSP, benefits, garnishments
- Notebook tab *YTD Snapshot* — running totals for CPP / EI / income tax
  caps
- Summary group at top — Gross / Total Deductions / Net

## Your daily flow (the Monday-Friday cycle)

### Monday — verify timesheets are flowing
- *Timesheets → Timesheets to Approve* (native) — you don't approve,
  but you check the queue is moving.
- Watch for employees who haven't submitted by Monday EOD; nudge
  their supervisors.

### Tuesday — supervisor approval
- Same view; you watch for approvals being completed.
- Last-call EOD if anyone's still draft.

### Wednesday — pull the run + spot-check
- *Payroll → Payroll Runs → New*. Pick `period_start` (Sunday last
  week) + `period_end` (Saturday this week) + `pay_date` (this
  Friday).
- Click *Pull*. Payslip records create for every active employee
  with bi-weekly contract.
- Spot-check 3 slips (lesson 19.2 walks the picks).

### Thursday — compute + approve
- Click *Compute* on the run. Math runs (lesson 19.3 explains).
- Read the *Totals* tab — gross + deductions should look like last
  cycle ± expected variance.
- Click *Submit for Approval*. Plant GM gets an activity.
- Plant GM approves → state `approved`.

### Friday — generate EFT + upload to bank
- Click *Generate EFT File* (lesson 19.4 walks).
- Download the `.aba` file. Upload to the bank business portal.
- Click *Mark Posted*. State → `done`. Payslips become visible to
  employees on `/my/payroll`.

## Where Plant GM fits in

The Plant GM has approval rights on the payroll run. Their click is
the gate between *compute done* and *EFT file generated*. They
typically scan the totals + check no one's gross moved unexpectedly.

## Where the Controller fits in

The Controller doesn't touch the run — but they verify:
- The payroll journal entry posted to the right accounts (wages, CPP,
  EI, income tax payable)
- The bank reconciliation picks up the EFT debit
- Month-end remittance journal entries to CRA tie to the run totals

Two sides of the same coin; coordinate during the monthly close
(Course 20).

## Where HR fits in

HR maintains:
- Employee record (`hr.employee`) — name, SIN, address, hire date,
  manager
- Contract (`hr.contract`) — wage, schedule, benefits, start/end
- TD1 federal + provincial — tax credit amounts

You consume what HR sets up. If HR is wrong, your run is wrong.

## Common mistakes + how to recover

- **"My run pulled 47 employees but we have 50."** Three employees
  are likely missing an active contract. Open *Payroll →
  Contracts*, filter state `running`; check who's missing.

- **"Payroll run says state `pending_approval` but Plant GM has
  approved."** Refresh; the activity may have closed without
  triggering the state advance. Click *Refresh State* in the run
  cog menu.

- **"EFT file generated but bank rejected the upload."** Bank
  format mismatch. The platform defaults to RBC `.aba`; if you bank
  with TD or BMO, format differs. *Configuration → Banking → EFT
  Format* fixes this once per session.

## What the system is doing behind the scenes

- **Pull** queries `hr.contract` where `state = running` AND
  `pay_frequency = bi_weekly` AND active employees.
- **Compute** iterates payslips → for each, runs salary rules in
  sequence per CRA 2026 brackets + employee TD1 + contract
  deductions. Heavy work; CPU-bound for 60s on 50-employee runs.
- **EFT generation** writes a `.aba` (or other bank format) file as
  an `ir.attachment` on the run. Bank ICR + account number come from
  *Settings → Companies → Banking*.

## Quiz (5 questions, applied)

**Q1.** It's Friday morning. You ran *Compute* yesterday. Plant GM
hasn't approved yet. What's the right move?

> Walk to Plant GM or message them; do NOT click *Approve* as
> yourself — the gate exists for a reason. If they're unavailable, the
> backup approver is the Controller (per the `approval_chain` on the
> run).

**Q2.** Run pulled 50 employees. After compute, *Totals* shows gross
$8k lower than last cycle. What's the likely explanation?

> Holiday in the period reduced regular hours OR new hire didn't start
> until mid-cycle OR a salaried employee was on unpaid leave. Drill
> into the *Payslips* tab sorted by gross delta vs prior period to find
> the source.

**Q3.** EFT file generated; bank reports the file uploaded but funds
didn't move. What do you check?

> The file has a *Posting Date* line — verify it matches the pay
> date. Banks reject files with past dates and silently queue some
> formats; check the bank's confirmation screen for actual posting
> status.

**Q4.** Employee asks why their net pay is $30 less than last
period. What do you check?

> Open their payslip → *Deductions* tab. CPP / EI may have caught up
> mid-period (employees front-loaded contributions); a benefit
> premium may have started; an income tax bracket may have crossed.
> Walk them through the deduction line that changed.

**Q5.** Your boss says "skip approval, the run is fine." What do you
do?

> Don't skip. The approval is for audit + segregation of duties.
> If the boss is the approver, get the click in writing
> (`activity_done` posts to chatter as a record). If they want to
> push past, escalate to the Controller.

## What this lesson does NOT cover

- The pre-run checklist for timesheets, new hires, terminations —
  lesson 19.2.
- The compute math + spot-check methodology — lesson 19.3.
- EFT file generation + bank upload mechanics — lesson 19.4.
- Mid-cycle garnishments + RRSP changes — lesson 19.5.
- Year-end T4 generation — Course 17 lesson 17.40 + future Course 24
  deep-dive.
