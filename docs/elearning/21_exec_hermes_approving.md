---
course: 21
chapter: 21.4
title: Executive — Approving and Delegating via Hermes
duration: 8
audience: Owner or Plant GM acting on Hermes recommendations
prereqs: Lessons 21.1 + 21.2 + 21.3
custom_modules: southbrook_hermes, southbrook_os
---

# Executive — Approving and Delegating via Hermes

## Who this lesson is for

You're the owner / Plant GM and Hermes recommendations are landing
in your queue. This lesson is the discipline of acting on them
quickly + correctly without becoming the bottleneck.

## Where this lives on the site

**Exec Dashboard → Hermes-flagged tile** — the inbox.
**(also visible at Hermes Recommendation queue when Plant GM is on
a recommendation persona)**

The Hermes chat panel may also surface mid-conversation
recommendations directly.

## What Hermes is

Hermes is the trade-partner-facing AI assistant + an internal
recommendation engine. Three persona models:

- **trade_partner** — external; partners chat about their orders
- **sales_rep** — internal sales-facing
- **mfg_manager** — internal manufacturing-facing (you live here)

Tools the engine has access to are tiered:

- **T0** — read only (status, lookup)
- **T1** — small writes (add a note, schedule a follow-up)
- **T2** — proposed actions (recommendations) requiring human
  approval

You see **T2 proposed recommendations** in your queue. T0/T1 happen
without you.

## Where this lives on the site (specific)

**Hermes Console** queue (external) for full ops.
**Exec Dashboard** Hermes-flagged tile for the daily exec lens.

The Console is what sysadmin uses; the dashboard tile is your
filtered view.

## What your screen shows

### Hermes-flagged tile (drill-through)
- List view of `hermes.recommendation` records
- Filtered to `state = pending_review` AND your persona
- Columns: `subject`, `recommended_action`, `confidence`,
  `created_at`, `requested_by`

### Recommendation form view
- `subject` — one-line summary
- `recommendation_body` — full text with context
- `recommended_action` — what Hermes proposes
- `confidence` — Hermes' self-assessed (0-100)
- `affected_records` — links to the SOs, MOs, etc. involved
- *Apply* / *Reject* / *Modify* action buttons

## The triage decision tree

For each recommendation, in order:

### 1. Read the subject (3 seconds)
- Reject if obviously wrong / not applicable
- Continue if it's worth thinking about

### 2. Read the body (30-60 seconds)
- Get the context — Hermes lays out the situation
- Note any links to records — open one if needed for context

### 3. Check confidence
- High (>80%): Hermes is sure; usually fine to apply
- Medium (50-80%): worth your own check
- Low (<50%): Hermes is unsure — investigate before applying

### 4. Decide
- **Apply** — execute as proposed. Audit log captures who applied.
- **Modify + Apply** — tweak the proposal then execute (e.g.
  different threshold, different recipient)
- **Reject** — don't execute. Captures why in chatter.
- **Defer** — assign to someone else or schedule a re-review

### 5. Document
- Apply / Reject decisions auto-log
- Modify writes the modifications + reason to the chatter

## When to delegate vs decide yourself

Some recommendations are obvious; some need your judgment.

### Delegate when
- Operational impact is clear AND the operational lead is the right
  decision-maker
- The recommendation is below a financial threshold
- Pattern: recurring recommendations of the same kind go to the same
  delegate

### Decide yourself when
- Recommendation affects multiple departments
- Customer-facing trade-off
- Above a financial threshold
- Strategic or precedential (others will follow this decision)

## A worked example: "Push delivery date for Order #1234 by 5 days"

You see the recommendation in your queue.

### Read body
"SB-CNC-BORE is overcommitted week of June 28 (lesson 17.17).
Customer for Order #1234 has historically been flexible on dates.
Pushing #1234 by 5 days frees 8 cabinet-equivalent hours, allowing
Order #1257 (newer, premium customer) to ship on time. Confidence
72%."

### Check
- Customer chatter on #1234: yes, they've been flexible
- Order #1257 customer: top-10 by margin
- Bottleneck report confirms overcommitment

### Decision
Apply. Hermes will email Order #1234 customer (template ready),
re-MO with new dates, notify production.

### Audit
Log captures: applied by [you] at [time], reason "trading flexibility
for customer relationship priority."

## What NOT to do

- **Don't apply blindly.** Hermes can be wrong; the queue is for
  your judgment.
- **Don't reject without context.** Document why so the engine
  learns.
- **Don't sit on recommendations.** Daily queue work is part of the
  job.
- **Don't make Hermes the decision-maker.** It surfaces options;
  you decide.

## Common mistakes + how to recover

- **"Applied a rec; result was wrong."** All actions are auditable.
  Reverse the action manually if possible; if not, document the
  consequences. The platform learns from these.

- **"Queue keeps growing; I can't keep up."** Triage. Reject the
  obvious ones fast; delegate the operational ones; reserve the
  judgment ones for yourself. Aim for inbox-zero on the queue
  daily.

- **"Hermes recommends something against my strategy."** Reject
  with a reason. The engine should learn over time. If it keeps
  recommending the same thing, the underlying loop may need tuning
  (sysadmin task).

- **"Recommendation has no context links."** Hermes failed to
  surface the affected records. Reject; ask sysadmin to investigate
  why the linking failed.

- **"Other staff thinks Hermes is making decisions."** Coach them
  on the recommendation model. Hermes proposes; humans apply.
  Reinforce by visibly applying or rejecting, not by silently
  letting the queue manage itself.

## What the system is doing behind the scenes

- `hermes.recommendation` records — created by background loops
  via various tools
- Persona resolution — sysadmin's persona is the auditor; yours is
  approver
- Apply executes the `recommended_action` via the appropriate tool
  call
- Reject + Modify post to chatter; the engine indexes for future
  learning
- All actions audit-logged to `mail.thread` on the recommendation

## Quiz (5 questions, applied)

**Q1.** Recommendation: "Pay supplier early for 2% discount on
$50k invoice." Confidence 65%. Action?

> Drill — check cash position + the discount math. $50k × 2% =
> $1,000 saved. If cash is tight, reject + note. If cash is fine,
> apply.

**Q2.** Recommendation: "Decline new order from Customer X due to
bad payment history." Confidence 88%. Action?

> Check Customer X's AR history. If confirmed, reject the
> recommendation (let sales handle the conversation directly).
> Hermes shouldn't be the one declining orders unilaterally; you
> + sales decide.

**Q3.** Same recommendation as Q1, but your queue has 30 items
to process today. Speed?

> ~2 minutes per rec for triage. For low-confidence + low-impact,
> faster reject. For high-confidence + high-impact, more time. 30
> recs at average 2 min = 60 minutes. Plan accordingly.

**Q4.** Recommendation: "Promote Mary from junior to senior CNC
operator." How does this get here?

> It shouldn't — that's an HR decision, not a Hermes loop. Reject;
> flag to sysadmin that the engine is over-reaching. Document.

**Q5.** You modify a rec ("push delivery 3 days instead of 5") and
apply. Customer was emailed with the original 5-day date by the
auto-template. Now what?

> Manual recovery: email the customer the corrected 3-day date.
> Apologise for the confusion. Document on the order chatter.
> Configuration issue: Modify should re-run the template; flag to
> sysadmin for fix.

## What this lesson does NOT cover

- Hermes architecture + tool registration — Course 13 (Fabio
  Module deep-dive).
- The trade-partner-facing chat experience — Course 6 lesson 6.3.
- Sysadmin recommendation queue — Course 7 lesson 7.3.
