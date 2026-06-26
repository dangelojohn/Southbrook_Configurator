---
course: 19
chapter: 19.4
title: Payroll Admin — EFT Generation and Bank Upload
duration: 8
audience: Payroll administrator on Friday morning, post-approval
prereqs: Lessons 19.1 + 19.2 + 19.3
custom_modules: southbrook_payroll_ca
---

# Payroll Admin — EFT Generation and Bank Upload

## Who this lesson is for

You're the payroll admin on Friday morning. The Plant GM approved the
run yesterday. Today you turn it into money in employees' accounts.
This lesson covers the EFT (Electronic Funds Transfer) file
generation + bank upload mechanics + recovery when things break.

## Where this lives on the site

**Payroll → Payroll Runs → [the approved run]** — the *Generate EFT
File* button.

Supporting:
- **Settings → Companies → Banking** — your business banking info
  (transit, account, ICR).
- **Employees → Employees → [employee] → Private Info → Banking** —
  each employee's deposit account.

## What your screen shows

### Run header (state = approved)
- *Generate EFT File* button (primary)
- *Mark Posted* button (visible after EFT generated)

### Generated EFT
- Lands as `ir.attachment` on the run
- File name: `southbrook_payroll_<pay_date>_<bank>.aba`
- Plus a human-readable summary CSV for your records

## The bank file formats

Canadian banks support several EFT formats. The platform supports the
common ones:

| Bank | Format | File extension |
|---|---|---|
| RBC | RBC ACH 80 | `.aba` |
| TD | TD EFT | `.efx` |
| BMO | BMO Direct Deposit | `.txt` |
| Scotiabank | Scotia eDeposit | `.csv` |
| CIBC | CIBC ACH | `.dat` |
| National | NBC EFT | `.txt` |

Configure your bank in *Settings → Companies → Banking → EFT Format*.
Once set, the *Generate EFT File* button produces the right format.

## The 3-step generate + upload

### 1. Generate
- Open the approved run
- Click *Generate EFT File*
- File downloads + attaches to the run
- Open the run's *Attachments* sidebar to confirm

### 2. Upload to bank
- Log in to your business banking portal
- Navigate to *Payroll → Upload EFT File* (varies by bank)
- Select the downloaded file
- Enter:
  - **Posting date** — must match the pay date on the file
  - **Total amount** — must match the file's header total
  - **Recipient count** — must match the file's recipient count
- Submit + confirm

### 3. Mark posted in Odoo
- Once the bank accepts the upload, return to Odoo
- Click *Mark Posted* on the run
- State → `done`
- Payslips become visible to employees on `/my/payroll`
- A confirmation email goes to each employee

## What's in the EFT file

The file is a fixed-width record per employee with:
- Recipient name
- Bank transit + account
- Amount (net pay)
- Posting date
- Originator reference

The header has the total + count for verification.

## Common mistakes + how to recover

- **"Bank rejected the file: invalid format."** Wrong format
  configured. Open *Settings → Companies → Banking → EFT Format*,
  pick the right bank, regenerate.

- **"Bank rejected: posting date in the past."** Pay date on the
  run is in the past (e.g. you tried to backdate). Change pay date,
  recompute, regenerate.

- **"Bank rejected: recipient #15 invalid account."** That
  employee's bank info is missing or formatted wrong. Open their
  *Private Info → Banking*, verify transit (5 digits), account
  (7-12 digits), institution (3 digits, e.g. 003 for RBC).
  Regenerate.

- **"One employee got paid twice."** Bank uploaded the file twice
  (operator error). Reach out to the bank to reverse the
  duplicate; don't try to do this in Odoo. The bank's NSF /
  reverse-charge tools fix it.

- **"One employee didn't get paid."** Their bank info was invalid
  AND the bank skipped that record silently (some banks do).
  Issue a manual cheque or wire; mark on their payslip's chatter.

- **"I clicked *Mark Posted* but the bank later failed the file."**
  Reverse: open the run, *Cog → Reset to Approved*. Fix the bank
  upload issue. Regenerate file. Re-upload.

## What the system is doing behind the scenes

- **Generate** iterates `hr.payslip` rows where `state = done` for
  the run. For each, reads employee banking + net pay; writes the
  bank-specific format.
- **Mark Posted** updates the run state + each payslip state. Posts
  an email to each employee via a configurable template
  (`southbrook_payroll_ca.payslip_published_email`).
- **Portal visibility** — payslips become visible on
  `/my/payroll` once `state = done`. The portal route is gated on
  `mail.alias` ownership of the slip.

## Quiz (5 questions, applied)

**Q1.** EFT file generated. You upload to RBC's portal; portal
says "file uploaded successfully" but bank account didn't debit.
What do you check?

> The bank's posting status screen (separate from upload status).
> Some banks queue uploads for nightly batch; others reject silently
> after upload. Look for a separate confirmation or batch status
> view in the bank portal.

**Q2.** Bank's portal asks for a "control total." The file should
contain it. Where is it?

> The file's header line includes the count + total. Open the file
> in a text editor (it's plain text), header row has the values.
> Or read off the run's *Totals* tab — total net pay matches.

**Q3.** Friday afternoon, EFT uploaded successfully. Employee
emails: "I didn't get paid." What do you do first?

> Open their payslip; verify `net_pay > 0` and banking info is
> filled. If both are fine, the bank may have rejected that
> specific recipient. Pull the bank's payment status; if rejected,
> issue a manual cheque + escalate to bank for the rejected record.

**Q4.** You generated EFT before the Plant GM approved. The run is
still `pending_approval`. Now Plant GM approves with edits. What
do you do?

> Discard the original EFT (it's stale). Regenerate after edits to
> ensure the file matches the approved totals. Bank will reject a
> file whose totals don't match the run anyway, so this is forced.

**Q5.** Half the employees use direct deposit, half want
cheques. How do you handle the cheque half?

> *Generate EFT File* skips employees with no banking info — they
> appear in a separate *Cheque List* attached to the run. Print
> the cheque list, run them through your physical cheque-printing
> process. Mark the run posted only after BOTH the EFT lands and
> cheques are issued.

## What this lesson does NOT cover

- Mid-cycle adjustments — lesson 19.5.
- Bank-specific portal navigation (varies; bank training).
- T4 year-end EFT to CRA (entirely separate mechanism, lesson 17.40).
