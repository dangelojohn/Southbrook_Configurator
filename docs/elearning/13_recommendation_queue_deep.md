---
course: 13 — Fabio Deep Dive
chapter: 13.2
title: Recommendation Queue — Source-Level Deep Dive
duration: 35 minutes
audience: Production Manager, CS Lead, and any developer reviewing the approval-boundary code
prereqs: Lesson 3.2 (`03_hermes_fabio_approval.md`) for the operator-level walkthrough; lesson 13.1 (`13_fabio_architecture.md`) for the four-pillar context; spec § 4 (tier matrix) + § 6 (tool catalog) at `docs/superpowers/specs/2026-06-16-southbrook-os-and-hermes-platform-design.md`
custom_modules: southbrook_hermes
---

# Recommendation Queue — Source-Level Deep Dive

## Who this lesson is for

You're a production manager or CS lead who already runs the queue daily
(lesson 3.2) and now needs to understand the model in full so you can
diagnose unusual states, train a peer, or partner with a developer to add
a new recommendation type. Or you're a developer who's about to touch
`models/hermes_recommendation.py` and wants to know what every field is
for before you change anything.

This lesson is the queue, end to end, at the source level. Lesson 3.2
covers the daily flow; this lesson covers *why each field exists*, *what
each method does*, and *what side effects every state transition fires*.

## Where this lives on the site

Same surface as lesson 3.2:

> **Fabio → Recommendations** — the list view, default `Open` filter.

But also, for source-level work:

> **Settings → Technical → Database Structure → Models** — search for
> `southbrook.hermes.recommendation`, open it to see the field list, the
> attached rules, the inherited mixins. Useful when an auditor asks "is
> there a record of this?" and you need to point at the schema.

> **Settings → Technical → Security → Groups** — search for
> `Fabio Reviewer` (`southbrook_hermes.group_hermes_reviewer`). This is
> the gate on the entire queue.

## What your screen shows

### The full field list (`southbrook.hermes.recommendation`)

The model lives at `addons/southbrook_hermes/models/hermes_recommendation.py`
and inherits `mail.thread` + `mail.activity.mixin` so it gets a chatter and
activity widget for free. Every field that ships, in the order they're
declared:

- **`name`** (Char, required, tracking=True) — the title shown in the
  list and the form header.
- **`state`** (Selection, required, tracking=True) —
  `draft / ready / approved / rejected / applied`. Default `draft`. Tracked
  in chatter on every change.
- **`recommendation_type`** (Selection, required, tracking=True) —
  `task / risk / note / followup`. Default `task`. Tells `action_apply`
  which side effect to fire (only `task` triggers `_create_project_task`).
- **`priority`** (Selection, required, tracking=True) —
  `low / normal / high / blocker`. Default `normal`. Blocker rows decorate
  red in the list view.
- **`agent_partner_id`** (Many2one `res.partner`, readonly, copy=False) —
  the agent that proposed the recommendation. Defaulted via
  `_default_agent_partner_id` to the seeded Fabio partner XML id
  `southbrook_hermes.partner_fabio_agent` (data record in
  `data/fabio_partner.xml`).
- **`summary`** (Text, required) — what Fabio is recommending, in one
  paragraph.
- **`rationale`** (Text) — why.
- **`proposed_action`** (Text) — what specifically should happen.
- **`source_model`** (Char) — the model the recommendation is about (e.g.
  `sale.order`, `res.partner`, `mrp.production`).
- **`source_res_id`** (Integer) — the record id within that model.
- **`payload_json`** (Text, required, default `"{}"`) — the structured
  payload Fabio sent. Validated as a JSON object on every save by
  `_check_payload_json` (raises `ValidationError` if it doesn't parse
  to a dict).
- **`agent_run_id`** (Char, indexed) — the sidecar's trace id for the
  agent loop that produced the recommendation. Indexed because
  diagnostic queries ("which recs came out of run X?") are common.
- **`model_provider`** (Char) — e.g. `anthropic`, `openai`. Free-form.
- **`model_name`** (Char) — e.g. `claude-opus-4-7`. Free-form.
- **`reviewer_id`** (Many2one `res.users`, readonly, copy=False,
  tracking=True) — set on `action_approve` and `action_reject`.
- **`reviewed_date`** (Datetime, readonly, copy=False) — same.
- **`applied_date`** (Datetime, readonly, copy=False) — set on
  `action_apply`.
- **`created_task_id`** (Many2one `project.task`, readonly,
  copy=False) — the task that `_create_project_task` produced. Only
  populated when `recommendation_type == 'task'`.

### The state machine — every transition, every guard

The state machine is implemented as four imperative methods. Each
enforces a guard and emits a chatter line.

**`action_mark_ready` — `draft → ready`.**

```python
def action_mark_ready(self):
    for rec in self:
        if rec.state != "draft":
            raise UserError(_("Only draft recommendations can be marked ready."))
        rec.state = "ready"
    return True
```

No reviewer field is written. No chatter post (the tracking=True on
`state` already logs the transition). Multi-record-safe by the for-loop.

**`action_approve` — `(draft | ready) → approved`.**

```python
def action_approve(self):
    now = fields.Datetime.now()
    for rec in self:
        if rec.state not in ("draft", "ready"):
            raise UserError(_("Only draft or ready recommendations can be approved."))
        rec.write({
            "state": "approved",
            "reviewer_id": self.env.user.id,
            "reviewed_date": now,
        })
        rec.message_post(body=_("Fabio recommendation approved."))
    return True
```

Writes `reviewer_id` + `reviewed_date`. Explicit `message_post` in
addition to the field tracking — the explicit post is what the auditor
reads as "approved by X at T."

**`action_reject` — `(any except applied) → rejected`.**

```python
def action_reject(self):
    now = fields.Datetime.now()
    for rec in self:
        if rec.state == "applied":
            raise UserError(_("Applied recommendations cannot be rejected."))
        ...
```

Note the guard is "anything except applied," not "draft or ready." This is
intentional: you can reject an *approved* recommendation as long as you
haven't pressed Apply yet. Reviewer + date are written; chatter post is
explicit.

**`action_apply` — `approved → applied`.**

```python
def action_apply(self):
    now = fields.Datetime.now()
    for rec in self:
        if rec.state != "approved":
            raise UserError(_("A recommendation must be approved before it can be applied."))
        values = {"state": "applied", "applied_date": now}
        if rec.recommendation_type == "task":
            task = rec._create_project_task()
            values["created_task_id"] = task.id
        rec.write(values)
        rec.message_post(body=_("Fabio recommendation applied."))
    return True
```

If the type is `task`, `_create_project_task` runs *before* the state
write. If it raises, the write is rolled back inside the same Odoo
transaction — the state stays `approved` and `applied_date` /
`created_task_id` stay null. This is the deliberate guarantee: a partial
apply never leaves the queue in an inconsistent state.

### The `recommendation_type` taxonomy

Four values, each with a different meaning:

- **`task`** — when applied, creates a `project.task`. This is the
  workhorse type; the trade-partner intent allow-list in `write_tools.py`
  (`request_revision`, `request_install_reschedule`,
  `request_clarification`) ships every draft as `task`. Reviewer applies
  → task lands on a Southbrook project with the original chatter line on
  the task pointing back to the recommendation ("Created from Fabio
  recommendation Hermes/request_revision/…").
- **`risk`** — purely informational. `action_apply` does NOT create a
  task. Use for "I noticed your install is 6 weeks out and the door
  vendor lead time is 8 weeks." The Apply button still fires (closes the
  record as "you saw it, you decided no action") but nothing downstream
  happens.
- **`note`** — also informational, lower priority than `risk`. Use for
  observations.
- **`followup`** — created by `action_create_recommendation` on the
  `southbrook.hermes.question` model when you want to turn a chat answer
  into a tracked follow-up. The created record carries
  `recommendation_type='followup'` and is wired up with `agent_run_id` =
  `fabio-ask-<question.id>`.

### `_create_project_task` — the side-effect path

```python
def _create_project_task(self):
    self.ensure_one()
    payload = self._payload()
    project_id = payload.get("project_id")
    if not project_id:
        raise UserError(_("Task recommendations require payload.project_id."))
    project = self.env["project.project"].browse(project_id).exists()
    if not project:
        raise UserError(_("Task recommendation project does not exist."))

    task_name = payload.get("task_name") or self.name
    task = self.env["project.task"].create({
        "project_id": project.id,
        "name": task_name,
        "description": self._task_description(payload),
    })
    task.message_post(
        body=_("Created from Fabio recommendation %s.") % self.display_name,
    )
    return task
```

The payload **must** contain `project_id` (integer id of a
`project.project`). May contain `task_name` (else uses `self.name`).
`_task_description(payload)` returns the description, which is either
`payload["description"]` verbatim or a synthesized
`summary + proposed_action + rationale` block. The task's chatter gets a
back-link to the recommendation so future-you can navigate one click
back.

This is what makes `task`-type recommendations feel "real" once applied:
the resulting task is what production sees in their project board, and
the back-link audits the why.

### The audit field set

When an auditor or a defensive review asks "who decided this and when?",
the answer is on five fields:

- `reviewer_id` — who clicked Approve or Reject.
- `reviewed_date` — when.
- `applied_date` — when it actually hit the database.
- `agent_partner_id` — who proposed (the Fabio partner).
- `agent_run_id` — the sidecar trace id, so you can dig back into what
  the LLM saw.

Plus the chatter, which has every state transition timestamped + every
explicit `message_post`. The combination is overdetermined on purpose —
state can be reconstructed even if one field is lost.

The trio (`agent_partner_id`, `agent_run_id`, `model_provider`,
`model_name`) is the *provenance* set: it tells you which Fabio agent
run, on which model, on which provider, produced this recommendation.
Useful when the prod team asks "which version of the model said this?"
during a quality-of-recommendations review.

## Your daily flow

This section deliberately complements lesson 3.2 — it covers what 3.2
doesn't.

**Reviewing in batch.**

The list view at **Fabio → Recommendations** supports the standard Odoo
batch-action pattern: tick multiple rows in the leftmost column → the
top **Actions** button reveals batch operations. The wired buttons in
the header are:

- **Mark Ready** — works only on rows in `draft`. Skips any non-draft
  selection (raises `UserError`, no transaction commits).
- **Approve** — works on `draft` + `ready` rows.
- **Reject** — works on anything not yet `applied`.
- **Apply** — works only on `approved` rows.

Because each transition method loops with `for rec in self`, batch
operations are all-or-nothing per the guard. One bad row aborts the
whole batch. If you've got 30 ready rows and one of them is somehow in
`applied`, the batch `Approve` will fail on iteration N — fix the odd
one out first.

**Filtering by source.**

The list view supports filtering by `source_model`. Useful filters:

- `source_model = 'res.partner'` — recommendations attached to a
  partner (these are the trade-partner-originated ones, since
  `propose_recommendation` sets `source_model='res.partner'`,
  `source_res_id=partner_id`).
- `source_model = 'sale.order'` — order-level recommendations.
- `source_model = 'mrp.production'` — manufacturing-order
  recommendations.

The form view shows source as a read-only `source_model` + `source_res_id`
pair; there's no Many2one widget that resolves the link automatically.
That's a deliberate v1 simplification — the model field is generic so
the queue can attach to anything; resolving the link is the reviewer's
job (open `Settings → Technical → Database Structure → Models`, search
the model name, jump to record by id).

**Cross-referencing the `agent_run_id`.**

Every recommendation carries a trace id. If the same run produced multiple
recommendations (common: a single trade-partner conversation that
proposed an install reschedule + a revision request), you can find them
all with the list filter `agent_run_id = <id>`. This is a debugging
workflow: "Fabio went sideways during run X, what did it propose?"

**Quarterly audit cadence.**

A standing list filter for the quarterly audit:

- `Reviewed Date is set in [last quarter]` — what got decided last
  quarter.
- Group by `Reviewer` — who decided what.
- Group by `Recommendation Type` then by `State` — what got applied vs
  rejected.

The data is overdetermined enough that this is a 10-minute report, not a
week.

## Common mistakes + how to recover

**"I want to reject a recommendation that's already `applied`."**

Can't. `action_reject` raises `UserError("Applied recommendations cannot
be rejected.")`. The change is in the database; rejecting the
recommendation now would be misleading. The right action: open the
`created_task_id` (if it's a task type), close or delete *that*, and
post a chatter note on the recommendation explaining the reversal. The
chatter is the audit log; the queue state stays `applied` because that
remains historically true.

**"`action_apply` raised `UserError("Task recommendation project does not
exist.")` — what does that mean?"**

The payload's `project_id` resolved to a project record that doesn't
exist (deleted or never existed). The state stays `approved` —
`_create_project_task` raised before the `rec.write({state: applied})`
landed. Edit `payload_json`, point at a real project id, save, click
Apply again. The save validates JSON-shape via `_check_payload_json`;
it does NOT validate that the project_id resolves — only Apply does.

**"I changed `payload_json` on an `applied` record. What happens?"**

The change saves (no state guard on writes). The `created_task_id` is
not regenerated. If you intended to "redo" the recommendation with a
new payload, the cleaner path is: leave this record applied, create a
new draft recommendation referencing the original, and apply that.
Mutating an applied record's payload pollutes the audit trail — past-you
applied with a different payload than what's now stored.

**"The queue is empty but I know the sidecar called `propose_recommendation`
30 seconds ago."**

Two suspects. (1) The sidecar got a 4xx/5xx from `POST /api/hermes/tools/propose_recommendation`
and the create never happened — check the sidecar's stderr / Vercel
log. (2) The reviewer group isn't on your user; the menu hides empty
states behind the group gate. Confirm via **Settings → Users → [your
user] → Other** that `Fabio Reviewer` is checked.

**"A draft recommendation has been sitting for 4 hours."**

Per lesson 3.2 — this is usually a sidecar error after the draft was
posted. You can mark it ready yourself (`action_mark_ready` is callable
from the button) and review it. The deeper question: who's monitoring
sidecar errors? In v1 that's a manual responsibility (no alerting
shipped); a stuck-drafts query in your morning standup catches it.

## What the system is doing behind the scenes

The model is small (160-odd lines of Python) but every line is doing a
specific job.

**Inheritance.** `_inherit = ["mail.thread", "mail.activity.mixin"]` —
that's what gets you chatter, the `message_post` API, the activity
widget, automatic following on `create()`, and the tracking diff on
fields marked `tracking=True`. Every state change writes a tracking row
because `state` has `tracking=True`. So does `recommendation_type`,
`priority`, `name`, `reviewer_id`. That's why the chatter is
auto-narrated even without the explicit `message_post` calls — those
calls are belt-and-braces.

**Default for agent partner.**

```python
@api.model
def _default_agent_partner_id(self):
    return self.env.ref(
        "southbrook_hermes.partner_fabio_agent",
        raise_if_not_found=False,
    )
```

`raise_if_not_found=False` so the model still loads if the seed XML
record was somehow uninstalled. New recommendations from a fully-installed
addon always carry the Fabio partner.

**Payload validation.**

```python
@api.constrains("payload_json")
def _check_payload_json(self):
    for rec in self:
        payload = rec._payload()
        if not isinstance(payload, dict):
            raise ValidationError(_("Payload JSON must be a JSON object."))

def _payload(self):
    self.ensure_one()
    try:
        return json.loads(self.payload_json or "{}")
    except json.JSONDecodeError as exc:
        raise ValidationError(_("Payload JSON is invalid: %s") % exc) from exc
```

Constraints run on every write that touches `payload_json`. The shape
guarantee is "it's a JSON object." Type-specific keys (`project_id`,
`task_name`) are enforced only at apply time by `_create_project_task` —
that's the deliberate split: queue state can carry incomplete payloads
during review; only the apply step requires the full thing.

**Access control.**

`security/ir.model.access.csv`:

```
access_hermes_recommendation_reviewer,southbrook.hermes.recommendation reviewer,
  model_southbrook_hermes_recommendation,group_hermes_reviewer,1,1,1,0
```

Read, write, create — yes; unlink — no. Reviewers cannot delete
recommendations. The audit trail is permanent. (If you absolutely must
remove a record, sysadmins with `base.group_system` can do it through
the technical menu — but `group_system` is on the
`group_hermes_reviewer.implied_ids` graph anyway, so this is a
deliberately narrow loophole.)

`security/hermes_security.xml` adds the `group_hermes_reviewer` group and
declares `base.group_system → group_hermes_reviewer` so sysadmins inherit
review rights. The menu items in `views/hermes_menus.xml` all carry
`groups="southbrook_hermes.group_hermes_reviewer"` — a non-reviewer user
sees no Fabio menu at all.

**Why the `sudo()` carve-out in `propose_recommendation`.**

The recommendation is created on behalf of the requesting trade partner
but must be visible to Southbrook reviewers, who are not the partner. If
the create ran as the partner's portal user, the resulting record would
fall under whatever record rules the partner has, and the reviewer's
search domain wouldn't pick it up. The spec § 4.4 calls this out as
the "explicitly tier-gated T2 sudo carve-out, with a documented reason."
The reason is in `write_tools.py`'s comment: a draft recommendation is
owned by the Fabio partner, not by the requesting user. See lesson 13.6.

## Quiz (5 questions, applied)

**1.** You approve a `task` recommendation. Before you click Apply, an
audit asks "what's the `created_task_id` on this record?" What does the
field show?

> Empty / `False`. `created_task_id` is written by `action_apply` →
> `_create_project_task`, not by `action_approve`. Approval is the
> review decision; apply is the database mutation. Between the two,
> `state='approved'`, `reviewer_id` and `reviewed_date` are populated,
> but `applied_date` and `created_task_id` are still null.

**2.** A `risk`-type recommendation needs to be closed because it's
obsolete. You click Approve, then look for an Apply button to dispose of
it. Apply runs cleanly but `created_task_id` is still null. Is that a
bug?

> No — that's the design. `action_apply` only calls
> `_create_project_task` when `recommendation_type == 'task'`. For
> `risk`, `note`, and `followup` types, applying just records "we've
> decided no action" — sets `applied_date` + `state='applied'` and
> posts the chatter "Fabio recommendation applied." `created_task_id`
> stays null because there's no task to point at.

**3.** A new junior dev wants to add a fifth recommendation type
called `chase` (for chasing a partner for missing info). Where do
they edit it, and what side effect will `action_apply` fire for that
type by default?

> They add the new value to the `state` Selection on
> `southbrook.hermes.recommendation.recommendation_type` in
> `models/hermes_recommendation.py`. By default `action_apply` will
> fire NO side effect for `chase`, because the only side effect
> branch in `action_apply` is `if rec.recommendation_type == "task":`.
> If `chase` should also create a task or send an email, they have to
> add an explicit branch.

**4.** Auditor asks "show me every recommendation approved by user
'Morgan Production' in March 2026 that was attached to a
`mrp.production` source." How do you build that list?

> Open **Fabio → Recommendations**. Apply filters:
> `reviewer_id = Morgan Production`, `reviewed_date >= 2026-03-01`,
> `reviewed_date < 2026-04-01`, `source_model = 'mrp.production'`. Group
> by `state` (so you can see how many were approved vs rejected vs
> applied). The audit fields are denormalized for exactly this query.

**5.** A reviewer accidentally rejects an `approved` recommendation
that should have been applied. Can they un-reject and apply it?

> No, not directly — the state machine has no `rejected → approved`
> transition. The path is: create a new recommendation with the same
> `summary`/`payload_json`/`source_*` fields (the original
> `payload_json` can be copy-pasted), mark it ready, approve, apply.
> Post a chatter note on both records explaining the reroute (the
> original record's chatter records the reversal; the new one carries
> the actual action). The audit reads as "rejected by mistake;
> superseded by REC-X." That's the conservative, defensible path; the
> alternative (a reopen transition) was deliberately not shipped.

---

## What this lesson does NOT cover

- The trade-partner-facing UI of proposing a recommendation —
  lesson 13.7 (chat panel) + lesson 13.6 (`propose_recommendation`
  intent allow-list).
- The CS-side filter conventions on the queue — lesson 6.3
  (`06_hermes_cs_view.md`).
- The five-state daily-flow walkthrough (start, ready, approve, apply,
  reject) — lesson 3.2 (`03_hermes_fabio_approval.md`).
- The sidecar trace that produced the recommendation — lesson 13.7.
- The JWT + persona that authenticated the proposing call —
  lesson 13.3.
- Sysadmin recommendations (separate operator surface) — lesson 7.3
  (`07_hermes_sysadmin.md`).
