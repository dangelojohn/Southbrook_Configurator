---
course: 3 — Floor Management
chapter: 3.2
title: Approving Fabio Recommendations from the Queue
duration: 25 minutes
audience: Production Manager (reviews and approves manufacturing recommendations submitted by the Fabio sidecar agent)
prereqs: Lesson 3.1 (MI dashboards), familiarity with the manufacturing intelligence checks
custom_modules: southbrook_hermes
---

# Approving Fabio Recommendations from the Queue

## Who this lesson is for

You're the **Production Manager**. The Fabio sidecar agent (an external AI/tool
orchestrator) drafts recommendations against the Southbrook database — things
like "reschedule MO-1042 because the planner overloaded SB-EDGE" or "create a
rework task for cabinet kit 248-A". The agent **cannot** make business changes
on its own. Every recommendation lands in your queue first; you read it,
decide, and either approve, reject, or apply it.

This lesson is about that in-Odoo queue — the human approval boundary that
sits between the agent and the database.

## Where this lives on the site

Sign in at **southbrookcabinetry.space/odoo** with an account in the
*Hermes Reviewer* group (`southbrook_hermes.group_hermes_reviewer`), then:

> **Fabio → Recommendations**

The top-level menu is **Fabio** (sequence 55, between Project and Settings).
It has two children: *Ask* (the conversational interface) and *Recommendations*
(the queue you work in). The recommendation list opens with the default search
filter `Open` applied — that's `state in ('draft', 'ready', 'approved')`, i.e.
everything that still needs a human action.

The internal addon code-name is `southbrook_hermes`. The user-facing label
everywhere — menus, partner record, ribbon — is **Fabio**.

> **Aside — not in scope here.** There is a separate operator-side surface at
> **hermes.odooiq.com** (the Hermes Console) where sysadmin-targeted
> recommendations live. That's Course 7 territory and is run by IT. This
> lesson is only about the in-Odoo manufacturing-recommendation queue. The
> two queues do *not* share records.

## What your screen shows

### The recommendation list (Fabio → Recommendations)

One row per `southbrook.hermes.recommendation`. Columns:

- **Name** (`name`) — the recommendation title.
- **Type** (`recommendation_type`) — one of `task` / `risk` / `note` /
  `followup`. The `task` type, when applied, creates a `project.task` record;
  the others don't.
- **Priority** (`priority`) — `low` / `normal` / `high` / `blocker`. Rows with
  `priority='blocker'` decorate red.
- **Agent** (`agent_partner_id`) — usually the Fabio partner (the partner XML id
  is `southbrook_hermes.partner_fabio_agent`, seeded by
  `data/fabio_partner.xml`).
- **State** (`state`) — the workflow state, rendered as a coloured badge. See
  the state machine below.
- **Agent Run ID** (`agent_run_id`) — the sidecar's trace id for the
  conversation that produced this recommendation. Use it when something
  doesn't make sense and you need to trace back to what the agent saw.
- **Provider / Model** (`model_provider`, `model_name`) — which LLM produced
  the recommendation (e.g. `anthropic` / `claude-opus-4-7`).
- **Reviewer** / **Reviewed** / **Applied** — your user, the timestamp you
  approved or rejected, and the timestamp it was applied.

### The state machine — verbatim values

There are **five** states defined on `southbrook.hermes.recommendation.state`:

1. **`draft`** — Fabio has just posted it via API. Not yet ready for review.
2. **`ready`** — Marked ready for human review (either by Fabio or by you
   clicking **Mark Ready** on a draft).
3. **`approved`** — You read it, you agreed. Not yet applied; the database
   has not changed.
4. **`rejected`** — You read it, you disagreed. Closed; will not be applied.
5. **`applied`** — Approval has been carried out. For `task` recommendations,
   the linked `project.task` (`created_task_id`) now exists.

The status bar at the top of the form shows the visible flow as
**draft → ready → approved → applied** (rejected is a sideways exit and is
indicated by a red ribbon, not a bar position). There is **no** `pending`
state and **no** `failed` state — if `action_apply` raises (e.g. because a
task recommendation is missing `payload.project_id`), the record stays in
`approved` and the error surfaces as a `UserError`. Re-attempt after fixing
the payload.

### The form view

When you open a recommendation:

- **Header** — the action buttons surface conditionally based on state:
  - **Mark Ready** appears when `state == 'draft'`.
  - **Approve** appears when `state in ('draft', 'ready')`.
  - **Reject** appears when `state != 'applied'`.
  - **Apply** appears when `state == 'approved'` (with a confirmation
    dialog: *"Apply this Fabio recommendation? This creates only the approved
    v1 target record."*).
- **Title** (`name`) — the recommendation summary line.
- **Left group**: type, priority, agent partner, `source_model`, `source_res_id`
  — the model and record id the recommendation refers to.
- **Right group**: agent run id, provider, model name, reviewer fields.
- **Recommendation tab**: `summary`, `proposed_action`, `rationale` — these
  are what Fabio wrote.
- **Payload tab**: `payload_json` — the structured payload Fabio sent. For
  `task` recommendations, this must contain `project_id` and may contain
  `task_name` and `description`. The form validates `payload_json` is a JSON
  object on every save (`_check_payload_json`).
- **Chatter** — every state transition posts a message
  ("Fabio recommendation approved.", "Fabio recommendation rejected.",
  "Fabio recommendation applied."), so the audit trail is on the record
  itself. Approval/rejection also writes `reviewer_id` and `reviewed_date`;
  apply writes `applied_date`.

## Your daily flow

**Per investigation (the loop you run every time a Fabio recommendation
needs review):**

1. Open **Fabio → Recommendations**. The default `Open` filter shows you
   `draft`, `ready`, and `approved` rows. Group by *State* (it's the
   default sort decoration order).
2. Pick the top `ready` row. (`draft` rows are usually still in transit
   from the agent; you can mark a stuck `draft` ready yourself, but be
   suspicious — it usually means the sidecar errored mid-write.)
3. Read in this order:
   - **Summary** — what does Fabio think should happen?
   - **Proposed Action** — what specifically?
   - **Rationale** — why? This is the most important field; if the
     rationale doesn't actually support the action, **reject** with a note
     and stop reading.
   - **Source record** (`source_model` + `source_res_id`) — open the
     referenced record in a new tab. Look at the live data the
     recommendation is based on. If the data has moved on since Fabio
     wrote the recommendation, **reject** with a one-line note in the
     chatter explaining "stale — original condition no longer holds."
   - **Payload tab** — for `task` recommendations, verify `project_id`
     resolves to a real project and `task_name` (if present) is sensible.
4. Decide:
   - **Approve** — you agree with both action and rationale.
   - **Reject** — you disagree, or the underlying data has changed.
   - **Apply** — once approved, click **Apply** to make the change. For
     `task` recommendations this calls `_create_project_task` which creates
     a `project.task` on the payload's `project_id` and posts a message on
     it linking back to the recommendation.
5. Add a chatter note explaining your reasoning if the decision wasn't
   obvious. The chatter is the audit trail that survives the recommendation;
   future-you (and any auditor) needs it to be able to reconstruct *why*.

**Per shift (5 min at start, 5 min at end):**

- Start of shift: scan for any `priority='blocker'` recommendations
  (red-decorated rows). These jump the queue.
- End of shift: clear out `approved` recommendations that have been sitting
  approved-but-not-applied — that's the manager's backlog, not the agent's.
  Either apply them or reject them.

## Common mistakes + how to recover

**"I approved it, then realised I shouldn't have. Can I reject it now?"**

Yes — `action_reject` is allowed from any state *except* `applied`. The
**Reject** button stays visible on the form until the recommendation has
actually been applied. Click it, add a chatter note explaining the
reversal, and the state flips to `rejected`. The reviewer fields update to
your user and the time.

**"I clicked Apply and got a `UserError` saying 'Task recommendations
require payload.project_id'."**

The payload is malformed. The recommendation stays in `approved` state — it
did not move to `applied`. Open the **Payload** tab, add a valid `project_id`
key (an integer matching a real `project.project.id`), save, then click
Apply again. If the payload was wrong because Fabio mis-extracted the
project, that's the kind of thing to mention in the chatter — it's
diagnostic feedback for whoever tunes the sidecar.

**"A recommendation has been sitting in `draft` for an hour and Fabio isn't
marking it ready."**

The agent posted it but didn't complete the `action_mark_ready` transition.
You can mark it ready yourself (the **Mark Ready** button is visible on
drafts to reviewers), but check the *Agent Run ID* first — paste it into
your IT contact's chat and ask whether the sidecar errored. A flood of
stuck drafts is usually a sidecar incident, not a per-recommendation issue.

**"I approved a `task` recommendation but the project task doesn't exist."**

Approval (`action_approve`) does **not** create the task. Only
`action_apply` creates it. Confirm the state on the recommendation: if it
shows `approved` (not `applied`), the task hasn't been created yet. Click
**Apply**.

**"How do I know who approved last quarter's recommendations?"**

The list view's **Reviewer** and **Reviewed** columns. They're populated on
the `action_approve` and `action_reject` paths only. For application audit,
sort by **Applied** descending. For a full timeline including any
intermediate comments, open the record and read the chatter — every state
transition is logged there as well.

## What the system is doing behind the scenes

The recommendation queue is a thin Odoo model with a state machine,
designed as a human approval boundary for the external Fabio sidecar.

The model `southbrook.hermes.recommendation` inherits `mail.thread` and
`mail.activity.mixin`, which is why you get chatter + activity for free.
Five state values are declared on the `state` selection field:
`draft / ready / approved / rejected / applied`. Each transition is a
separate Python method:

- `action_mark_ready` — `draft → ready`. Raises `UserError` if state isn't
  `draft`.
- `action_approve` — `(draft|ready) → approved`. Writes `reviewer_id` and
  `reviewed_date`. Raises if state isn't draft or ready.
- `action_reject` — `(any except applied) → rejected`. Same reviewer/date
  fields. Raises if state is `applied`.
- `action_apply` — `approved → applied`. Writes `applied_date`. For
  `recommendation_type == 'task'`, calls `_create_project_task`, which
  creates a `project.task` on `payload['project_id']` and stores the new
  task id in `created_task_id`. Raises `UserError` if state isn't `approved`.

The payload is stored as a JSON string in `payload_json` (default `"{}"`)
and validated as a JSON object on every save. The `_payload()` helper
decodes it; `_check_payload_json` is the `@api.constrains` hook that runs
on write.

**Outbound bridge — where Fabio actually talks to Odoo.** The
`/hermes/v1/ask` controller in `controllers/hermes_proxy.py` is the
browser entry point; the controller mints a JWT (using the helper in
`utils/jwt_helper.py`, requires `PyJWT` at runtime) and POSTs to a
configured sidecar URL. The sidecar URL and enable flag are read from
`ir.config_parameter` keys `southbrook_hermes.sidecar_url` and
`southbrook_hermes.sidecar_enabled`; when the flag is off, the controller
returns a stub answer so the OWL chat panel still works end-to-end. The
sidecar then writes draft recommendations back through the inbound API
(controllers in `hermes_conversation_api.py` and `hermes_tools_api.py`).
You don't need to touch any of this for normal review work — it's listed
here only so you know the loop is real and that the sidecar's writes are
authenticated, not freeform.

Access control: the `group_hermes_reviewer` group gates the entire Fabio
menu tree and is the only group with read/write/create on the
recommendation and question models. Production managers should be in this
group; operators should not.

## Quiz (5 questions, applied)

**1.** A `ready` recommendation says "Reschedule MO-1042 from SB-EDGE
Monday morning to Tuesday afternoon because SB-EDGE has 14 hours of work
queued for Monday." You open the source record (MO-1042) and see the
planner already moved it to Wednesday this morning. What do you do?

> **Reject** with a chatter note like "Stale — planner has already moved
> MO-1042 to Wednesday." The recommendation's rationale is no longer
> true. The reject writes your user and timestamp into `reviewer_id` /
> `reviewed_date` so the audit trail captures who closed it.

**2.** You click **Approve** on a `task`-type recommendation, then realise
the payload's `project_id` doesn't exist. What state is the record in,
and what's the right next move?

> The record is `approved`. **Apply** has not been clicked yet, so no task
> was created. Fix the payload (edit `payload_json` to point at the right
> project), then click **Apply**. If you decide it shouldn't be applied at
> all, click **Reject** instead — that's still allowed because the state
> isn't `applied`.

**3.** Three weeks after applying a recommendation, an auditor asks who
approved it. Where do you find that?

> The **Reviewer** field (`reviewer_id`) and **Reviewed** field
> (`reviewed_date`) on the record. The chatter also has the
> "Fabio recommendation approved." message timestamped with the same data.
> For full context, the same form shows `applied_date` and (if it was a
> task) `created_task_id` so you can jump to the resulting task.

**4.** A `draft` recommendation has been sitting for 6 hours and Fabio
isn't picking it up. The agent run id is filled in. What's most likely
wrong, and what do you do?

> The sidecar most likely errored after posting the draft but before
> marking it ready. Flag it to IT with the `agent_run_id` so they can
> trace the sidecar log. If the content looks reasonable and is still
> relevant, you can click **Mark Ready** yourself and proceed with normal
> review — but log the manual transition in the chatter so it's clear the
> agent didn't complete the handoff.

**5.** A recommendation has `state='applied'` and `created_task_id` set.
Can you reject it?

> No. `action_reject` raises `UserError` when the state is `applied`
> ("Applied recommendations cannot be rejected."). The change has already
> hit the database. If the task was created in error, close or delete the
> resulting `project.task` directly, and post a note in the recommendation
> chatter explaining the cleanup.

---

## What this lesson does NOT cover

- The Hermes Console at hermes.odooiq.com — separate operator surface for
  sysadmin recommendations. Covered in lesson 7.3
  (`07_hermes_sysadmin.md`).
- Customer-service view of the recommendation queue (different filters,
  different priorities) — lesson 6.3 (`06_hermes_cs_view.md`).
- How to author and deploy the Fabio sidecar itself — that's an IT topic
  outside the trainee track.
- The OWL chat panel ("Ask Fabio") behaviour — covered in `06_hermes_cs_view.md`.
- Approving non-Fabio recommendations from the MI engine — those are
  *checks*, not recommendations, and live in **Southbrook PM → MI Checks**
  (lesson 3.1).
