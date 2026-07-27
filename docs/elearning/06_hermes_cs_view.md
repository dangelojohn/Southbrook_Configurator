---
course: 6 — Customer Touchpoints
chapter: 6.3
title: Customer Service Lead — The Fabio Recommendation Queue
duration: 30 minutes
audience: Customer Service Lead who triages Fabio (Hermes) recommendations that affect customer communication, distinct from the Production Manager who triages MO-related recs
prereqs: Lessons 6.1 (customer portal) and 6.2 (dealer portal). Awareness that lesson 3.2 covers the same queue from the Production Manager's perspective.
custom_modules: southbrook_hermes, southbrook_customer_portal, southbrook_kitchen_workspace
---

# Customer Service Lead — The Fabio Recommendation Queue

## Who this lesson is for

You're the Customer Service Lead. You don't approve manufacturing
recommendations — that's the Production Manager's job (lesson 3.2). You
*do* approve the recommendations Fabio raises about **customers who
need attention**: somebody who hasn't logged into the portal for three
weeks, somebody whose A/B/C concepts were published nine days ago and
who hasn't picked, a dealer whose order has been sitting in draft. Your
queue is the customer-side of Fabio's output. This lesson is the
practical reality of triaging it without sending a customer two
follow-ups in the same week.

## Where this lives on the site

Sign in to Odoo back office, then:

> **Fabio → Recommendations**

The same queue, filtered to only the rows that came from a
customer-communication signal:

> **Fabio → Recommendations** → Search bar → Filter on Source Model =
> `sb.kitchen.project` OR `res.partner` AND State = `draft` or `ready`

There's also an **Ask** menu:

> **Fabio → Ask**

That's the chat surface (`southbrook.hermes.question`) where you can
ask Fabio about a specific customer or project in natural language and
optionally promote the answer to a draft recommendation. The
recommendation queue is what you act *on*; the Ask surface is what you
probe *with*.

To see ALL of Fabio's recommendations including production ones (the
Production Manager's queue):

> **Fabio → Recommendations** → clear all filters

You and the Production Manager share one table — different filters,
different rows.

## What your screen shows

The Fabio Recommendation list (`southbrook.hermes.recommendation`)
columns:

- **Name** (`name` on `southbrook.hermes.recommendation`) — short
  one-line summary, e.g. "Wilson Coastal — awaiting customer 12d".
- **Type** (`recommendation_type`) — selection of `task / risk / note /
  followup`. CS-relevant rows are usually `followup` (a customer needs
  contact) or `task` (a measurable action to schedule).
- **Priority** (`priority`) — selection of `low / normal / high /
  blocker`. The list view colours `priority='blocker'` rows red.
- **Agent** (`agent_partner_id`) — always Fabio (defaults to the
  seeded `partner_fabio_agent` record).
- **State** (`state`) — `draft → ready → approved → applied`, plus
  `rejected` off the side. The list view colours `applied` green and
  `rejected` muted.
- **Agent run id** (`agent_run_id`) — traces back to the Fabio sidecar
  batch that produced the rec; useful when several recs share a root
  cause.
- **Model provider** + **Model name** — which LLM (or rule engine)
  produced the rec. CS-relevant recs are typically rule-based, not
  LLM-generated.
- **Reviewer** (`reviewer_id`) — set when you approve / reject.
- **Reviewed date** / **Applied date** — timestamps of the human gate.

The form view adds:

- **Summary** (`summary`) — the body of what Fabio thinks.
- **Proposed action** (`proposed_action`) — Fabio's suggested next
  step in human terms.
- **Rationale** (`rationale`) — why Fabio raised it (which signal fired).
- **Source model** + **Source res_id** — the record the rec is about.
  For CS-relevant recs, source_model is usually `sb.kitchen.project`
  or `res.partner`.
- **Payload** tab (`payload_json`) — structured JSON. For task recs
  this carries `project_id`, `task_name`, `description`; the
  `action_apply` flow reads it to create a `project.task` record.

The **chatter** at the bottom (`mail.thread`) is where you record what
you actually did. Every approve / reject / apply posts an automatic
message; you can add a manual note ("called customer, voicemail").

## Your daily flow

**1. Start of shift (5 min):**

- Open **Fabio → Recommendations**.
- Filter on **State = Ready** (and **Source Model = sb.kitchen.project**
  OR **= res.partner**) — that's your queue. The Production Manager's
  filter excludes those source models and picks up `mrp.production`,
  `sb.production.package`, etc.
- Group by **Priority** to surface blockers first.

**2. Per recommendation (the loop):**

For each row in your filtered queue:

- Open the row. Read **Summary** → **Proposed action** → **Rationale**
  in that order. Summary tells you the symptom; proposed action tells
  you what Fabio thinks to do; rationale tells you why Fabio thinks
  so (and whether the signal is still valid — sometimes by the time
  you read the rec, the customer already logged in).
- Click into the **Source res_id** record if you need context (Fabio
  links it but the form doesn't auto-jump — read `source_model` +
  `source_res_id` and navigate manually).
- Decide:
  - **Approve** if Fabio's proposed action is what you'd do anyway.
    Click *Approve*. State flips to `approved`. `reviewer_id` and
    `reviewed_date` are set automatically.
  - **Reject** if the signal is stale (customer already logged in
    yesterday) or the proposed action is wrong for context (e.g.
    Fabio suggests calling the customer but you already emailed them
    this morning). Click *Reject*; record a manual chatter note
    explaining why.
- After approval, do the thing. Then click **Apply** — state flips to
  `applied`, `applied_date` is set. For `task`-type recs, *Apply*
  creates a `project.task` record from the payload's `project_id` +
  `task_name` (`_create_project_task` on the recommendation model).
  For `followup` / `risk` / `note` types, *Apply* is the manual gate
  — it doesn't create a task, but it does record that you followed
  through and prevents Fabio from re-raising the same rec.

**Hot rule:** approval ≠ done. The model's `action_apply` constraint
checks `state == 'approved'` — you can't skip approval and go straight
to applied. The two-stage gate is deliberate; approval says "yes this
is the right move", apply says "yes I did it".

**3. CS-relevant recommendation types you'll see:**

These are the patterns Fabio emits for the customer-communication
surface. Each is a `southbrook.hermes.recommendation` row with the
shape described:

- **Customer awaiting approval (Nd)** — `source_model =
  'sb.kitchen.project'`, `recommendation_type = 'followup'`. Triggered
  when project state has been `awaiting_customer` for more than N
  days (N defaults to 7). Proposed action: call the customer to
  walk them through the approval click. **Your action:** open the
  project, call the customer, log a chatter note on the project
  with the conversation outcome, then approve + apply the rec.
- **Design A/B/C choice abandoned** — `source_model =
  'sb.kitchen.project'`, `recommendation_type = 'followup'`. Triggered
  when project state has been `designing` for more than 21 days and
  no `selected_design_option_id` has been set. Proposed action:
  contact the customer about whether the concepts landed at all.
  **Your action:** check the customer's `res.users.login_date` — if
  they've never opened the portal, the welcome path is broken;
  re-issue the portal invite before calling.
- **Portal not logged into for X weeks** — `source_model =
  'res.partner'`, `recommendation_type = 'followup'`. Triggered when
  the partner has an active kitchen project and the linked user's
  `login_date` is more than X weeks ago (X defaults to 3). Proposed
  action: check whether the project is stalled awaiting a customer
  action; phone the customer if so. **Your action:** look at the
  project state; if it's `designing` or `in_production` the customer
  isn't holding the ball — they can be quiet — but if it's
  `awaiting_customer` or `approved` (i.e. they should be looking),
  phone them.
- **Dealer order stalled in draft** — `source_model = 'sale.order'`,
  `recommendation_type = 'task'`. Triggered when a dealer's sale
  order has been in `draft` state for more than 14 days. Proposed
  action: contact the dealer to confirm they're still working on the
  quote. **Your action:** phone the dealer-portal contact; if they
  abandoned the quote, cancel the order to clean up the dealer's
  portal list.

**4. End of shift (5 min):**

- Re-filter to **State = Approved** (yours). These are recs you
  approved earlier in the day but haven't applied yet. Either apply
  them (action complete) or convert to a `project.task` for tomorrow.
  Leaving rows in `approved` overnight is fine; leaving them in
  `approved` for a week is sloppy — Fabio will re-emit a similar rec
  and your queue will bloat.

## When to escalate to the Production Manager

These look like CS recs but actually need the Production Manager's
gate (lesson 3.2). If you open one of these by mistake, click
**Reject** with a chatter note "wrong queue, see Production":

- `recommendation_type = 'risk'` with `source_model = 'mrp.production'`
  — production-floor risk, not your call.
- `priority = 'blocker'` with `source_model` in
  (`mrp.production`, `sb.production.package`, `mrp.workorder`) — that's
  a shop-floor blocker; the Production Manager has authority to
  approve a workaround.
- Any rec where the proposed action involves moving a date on a
  manufacturing order, changing a workcenter assignment, or releasing
  an MO early. Those are production decisions; CS doesn't touch them.

Conversely, the Production Manager should hand you anything where
the proposed action is "contact the customer" or "contact the dealer"
— those are your queue, regardless of what the source model is.

## Common mistakes + how to recover

**"I approved the rec but I didn't do the thing — I forgot. Two days
later Fabio raised the same rec again."**

Fabio's deduplication keys off the source record + signal type, not
off whether you remembered. The duplicate is the signal that the
underlying issue is still there. Open the original (search
`agent_run_id`), see what state it's in:
- If still `approved` (you never applied): apply it now AND act on
  the duplicate. Both rows close out.
- If `applied` but the action didn't actually work: reject the
  duplicate with a chatter note "previous follow-up didn't land,
  escalating to manager".

**"I clicked Apply on a `followup` rec but the customer never picked
up — did Apply actually do anything?"**

For `followup` / `risk` / `note` types, *Apply* sets `state='applied'`
and `applied_date=now`. It does NOT create a project.task, send an
email, or update anything outside the recommendation itself — it's a
manual gate that says "I acknowledged this and I acted on it." If
the customer didn't pick up, your chatter note should say so, and
you should leave the recommendation `applied` (don't un-apply it —
there's no un-apply path; the state machine treats `applied` as
terminal). Fabio will raise a fresh rec tomorrow if the project is
still stuck.

**"I clicked Reject by mistake — can I undo it?"**

The state machine allows `rejected → approved` only via the *Approve*
button (`action_approve` accepts state in `('draft', 'ready')`, so
no — once `rejected`, you can't approve it again on the same row).
You can re-create an equivalent rec manually (create a draft
recommendation, mark ready, approve), but Fabio will probably re-emit
the original signal soon anyway. Leave it; wait for the next emit.

**"The Production Manager keeps approving recs that should be mine
and I keep approving recs that should be theirs."**

You're both filtering the same table. Agree on the filter contract:
the Production Manager filters source_model to
(`mrp.production`, `sb.production.package`, `mrp.workorder`,
`southbrook.mi.check`); you filter to (`sb.kitchen.project`,
`res.partner`, `sale.order`). If a rec doesn't fit either filter,
read `proposed_action` — whoever's named in the action ("CS to call
customer" / "Production Manager to release MO") is the owner.

**"A customer-flagged followup says 'call customer about A/B/C
abandonment' but the customer already picked Option B yesterday."**

Stale signal. The rec was emitted by the Fabio sidecar before the
customer acted. Reject with a chatter note "customer selected Option
B on <date>, signal pre-dates that". Fabio's next batch will not
re-raise because the underlying signal (no `selected_design_option_id`)
no longer fires.

## What the system is doing behind the scenes

Each click on the recommendation view writes to
`southbrook.hermes.recommendation` plus its `mail.thread`:

- **Approve** — sets `state='approved'`, `reviewer_id=current user`,
  `reviewed_date=now`. Posts to `mail.thread`: "Fabio recommendation
  approved."
- **Reject** — sets `state='rejected'`, same reviewer fields. Posts:
  "Fabio recommendation rejected." Constraint: applied recommendations
  cannot be rejected.
- **Apply** — only allowed when `state=='approved'`. Sets
  `state='applied'`, `applied_date=now`. For `recommendation_type='task'`,
  runs `_create_project_task()`, which reads `payload_json` for
  `project_id` + `task_name`, creates a `project.task`, links it to
  `created_task_id`, and posts a confirmation to both threads.

The state machine is enforced in `action_*` methods on
`southbrook.hermes.recommendation`. Off-graph transitions raise
`UserError` — you can't bypass approve to apply, you can't approve a
recommendation that's already rejected, you can't reject an applied
one. Fabio emits drafts (`state='draft'`); a sidecar lifecycle hook
marks them `ready` after validation; only humans can move
`ready → approved → applied`.

The CS-only filter (Source Model in (`sb.kitchen.project`,
`res.partner`, `sale.order`)) is a **convention**, not a hard rule.
The model itself doesn't know about CS-vs-Production scope — there's
no `team` field on `southbrook.hermes.recommendation`. You and the
Production Manager are filtering the same table by source_model
agreement. If that gets confusing, raise a ticket to add a `team`
selection.

The seeded **Fabio Reviewer** group (`group_hermes_reviewer` in
`southbrook_hermes/security/hermes_security.xml`) is what gates
visibility of the Fabio menu and the approve / reject / apply
buttons. Both CS and Production Managers are members of that group;
your access to the table is identical. Filter discipline is the only
thing separating the two queues today.

## Quiz (5 questions, applied)

**1.** You open Fabio → Recommendations, filter on **State = Ready,
Source Model = sb.kitchen.project**, and see a rec named "Smith
Modern — awaiting customer 9d". You click in, the rationale says
"project has been in `awaiting_customer` for 9 days, customer last
logged in 11 days ago." What's your first move?

> Don't approve yet. Open the project (use the source_res_id), check
> whether `selected_design_option_id` is set (they may have selected
> but not approved) and read recent project chatter. THEN call the
> customer — if they've selected, walk them through the green button.
> Once the customer either acts or commits to acting, return to the
> rec: approve + apply if they're going to act today, reject with a
> chatter note if they need a longer follow-up that you'll schedule
> as a separate task.

**2.** You see a `priority=blocker` rec in your queue. The source
model is `mrp.production` and the proposed action says "release MO
early to hit customer install date." What do you do?

> This is not your queue. Reject the rec with a chatter note "wrong
> queue, source_model is mrp.production — Production Manager owns
> the MO release decision (lesson 3.2)." Then ping the Production
> Manager so they pick it up from their own filtered queue. Don't
> approve it — you don't have manufacturing authority and clicking
> approve creates a paper trail that says you did.

**3.** You approved a `followup` rec yesterday ("call Wilson about
A/B/C choice") but you never actually called. Today Fabio raised a
duplicate. What do you do with the duplicate?

> The duplicate is the signal that the underlying issue is still
> there. Open yesterday's rec — it'll still be in `approved` state.
> Apply it today (after actually calling the customer), and reject
> the duplicate with a chatter note "rolled up into yesterday's rec
> <id>." Both rows close out; Fabio's dedup won't raise a third.

**4.** A `followup` rec for a dealer's stalled draft order has been
sitting in your queue for two days. You phone the dealer, they
confirm they're not progressing the quote and want it cancelled.
What's the right sequence in Odoo?

> (1) Cancel the dealer's `sale.order` (the dealer's portal list will
> stop showing it as draft). (2) Open the Fabio rec, click Approve,
> then Apply — `state='applied'`, `applied_date=now`. (3) Add a
> chatter note on the rec: "dealer confirmed abandonment, order
> cancelled <date>." Order of operations matters: cancel the order
> *first* so the dealer's view is clean before you log the rec as
> applied.

**5.** You click Reject on a rec by mistake (meant to click
Approve). You realise immediately. Can you un-reject?

> No. The state machine allows approve from `draft` or `ready` only
> — once rejected, the rec is terminal for that row. You can
> manually create a fresh draft recommendation with the same body,
> mark ready, approve, apply — that's the workaround. In practice
> the cleaner move is to act on the customer / dealer directly (do
> the thing) and trust that Fabio will re-emit the signal tomorrow
> if it still applies; your chatter note on the rejected row should
> say "rejected in error, action taken outside the queue on <date>."

---

## What this lesson does NOT cover

- Production-side Fabio recommendations (the MO + workcenter +
  scrap recs) — covered from the Production Manager's perspective in
  lesson 3.2.
- Sysadmin-side Fabio recommendations (orchestration crons, backup
  warnings, system-health recs) — lesson 7.3.
- The Fabio sidecar itself — how it produces recommendations, the
  rule rules + LLM pipeline, the JWT-based API gating. That's
  infrastructure, not CS workflow.
- The Ask Fabio chat surface in depth (Fabio → Ask) — covered as a
  cross-cutting tool in lesson 3.2 alongside the production view.
- The customer-facing /my/fabio surface (customers asking Fabio
  about their own project) — that's the customer's experience, not
  the CS Lead's queue.
