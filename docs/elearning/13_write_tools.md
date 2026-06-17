---
course: 13 — Fabio Deep Dive
chapter: 13.6
title: The Four Write Tools and the T0 / T1 / T2 Tier Model
duration: 35 minutes
audience: Developer working in `tools/write_tools.py`; production manager who needs to understand the human-approval boundary for trade-partner-proposed writes
prereqs: Lesson 13.4 (`13_tool_registry.md`) for registry + dispatch; lesson 13.5 (`13_read_tools.md`) for the read-side companion; lesson 13.2 (`13_recommendation_queue_deep.md`) for the queue side effects; spec §§ 4.2 + 6 (tier matrix + tool catalog) at `docs/superpowers/specs/2026-06-16-southbrook-os-and-hermes-platform-design.md`
custom_modules: southbrook_hermes
---

# The Four Write Tools and the T0 / T1 / T2 Tier Model

## Who this lesson is for

You're the developer adding a fifth write tool and need to know which
tier it should be. You're the production manager who's been asked "can
Fabio actually book installs?" and you need a precise answer. You're
the auditor reading the source and checking that the safety boundary
holds.

The four write tools are the ones with consequences — they change
state, send email, create activities, or queue recommendations. Each
sits at a tier that defines what kind of consequence: T0 is reversible
internal logging, T1 is communication-with-side-effects, T2 is business
mutation that always flows through the human approval queue.

## Where this lives on the site

You don't see the write tools on a screen directly. You see their
*output* in multiple places:

> **(Internal note)** — `post_internal_note` writes via
> `message_post(subtype_xmlid='mail.mt_note')`. Appears on the chatter
> of any record the tool can write to, with the author as the
> calling user.

> **(Email)** — `send_spec_pdf_email` triggers
> `sale.email_template_edi_sale.send_mail(order.id)`. Appears in
> **Settings → Technical → Email → Mass Mailing** outgoing logs.

> **(Activity)** — `schedule_followup_activity` creates a
> `mail.activity` row. Appears in the user's **Activity** widget
> (top-right bell icon).

> **(Recommendation)** — `propose_recommendation` creates a
> `southbrook.hermes.recommendation` draft. Appears in
> **Fabio → Recommendations** with default `Open` filter, awaiting
> reviewer action (lesson 3.2 + lesson 13.2).

## What your screen shows

### The T0 / T1 / T2 tier model from the spec

Spec § 4.2 defines three tiers. The implementation in `utils/jwt_helper.py`
gives all three personas the full mask `"T0+T1+T2"` — but per spec § 14.1,
the safety boundary moved into individual tool guards rather than the
mask. So the practical model is:

**T0 — internal logging / record-rule-bounded writes.**

Reversible, low-stakes, no out-of-system effects. A note posted via
`post_internal_note` is visible in the chatter; deleting it requires no
external coordination. Per spec § 4.2 row: "own-order chatter,
internal notes, conversation log."

**T1 — communication, side effects you can't reach into and undo.**

An email sent to a partner; an activity created on a user. These
trigger external behavior (the partner reads the email; the user
sees the activity in their queue). You can't unsend the email. Per
spec § 4.2 row: "resend spec PDF, schedule own follow-up activity"
for trade partners; "partner emails, internal calls" for sales reps.

**T2 — business mutation.**

The actual database change to business state (book an install,
revise a quote, confirm an MO). For trade partners, T2 always goes
through the human-approval queue via `propose_recommendation` (spec
§ 6 — the "universal T2 escape hatch"). For sales reps in v1.1,
some T2 paths will autonomously write under threshold; for mfg
managers in v1.2, T2 paths will go through a 2-eyes review modal.
Trade partners never write business state directly through Fabio,
period.

### The 4 write tools

In `addons/southbrook_hermes/tools/write_tools.py`, registered in
this order:

| # | Slug | Tier | Personas | Scope | Side effect |
|---|---|---|---|---|---|
| 1 | `post_internal_note` | T0 | trade, sales, mfg | own | Posts `mail.message` of type `mt_note` |
| 2 | `send_spec_pdf_email` | T1 | trade, sales | own_order | Sends `sale.email_template_edi_sale` |
| 3 | `schedule_followup_activity` | T1 | trade, sales, mfg | own | Creates `mail.activity` (todo) |
| 4 | `propose_recommendation` | T2 | trade, sales, mfg | own | Creates draft `southbrook.hermes.recommendation` |

### Tool 1 — `post_internal_note(record_model, record_id, content)`

Tier: T0. Personas: all three. Scope: own.

```python
def post_internal_note(env, record_model: str, record_id: int, content: str):
    allowed_models = ("sale.order", "project.task", "southbrook.hermes.question")
    if record_model not in allowed_models:
        raise UserError(
            f"Hermes can't post notes on '{record_model}'. "
            f"Allowed: {', '.join(allowed_models)}.")
    record = env[record_model].browse(record_id)
    record.check_access_rights("write")
    record.check_access_rule("write")
    msg = record.message_post(
        body=content, message_type="comment",
        subtype_xmlid="mail.mt_note")
    return {"ok": True, "message_id": msg.id}
```

Three explicit guards:
- **Model allowlist.** Three models are postable: `sale.order`,
  `project.task`, `southbrook.hermes.question`. Anything else raises
  `UserError`. This is the model-level allowlist — even with broader
  write access on other models, Fabio can't note them.
- **Record-rule check.** `check_access_rights("write")` +
  `check_access_rule("write")` — the partner must be able to write to
  this specific record. Internal notes count as writes, so the
  partner needs write access to the record.
- **Internal note subtype.** `subtype_xmlid="mail.mt_note"` makes the
  message an internal note (not a public message). Trade partners
  can see internal notes on records they have write access to, but
  they're not sent as emails. Posting "comment" without the note
  subtype would be a public message that could fire email
  notifications.

The result: trade partners can log "remind me later" notes on their
own orders. Sales reps can log notes on opportunities. Mfg managers
can log notes on tasks.

Common confusions:
- "Why is this a T0 tool if it writes to the database?" Because
  reversible, scoped to records the caller already controls, and
  doesn't trigger external behavior. The chatter note can be deleted
  from the record. The spec's tier model is about *consequence*, not
  *write*.
- "Why doesn't trade-partner have a model allowlist different from
  mfg manager?" Because the record-rule check already filters —
  trade partners can't write to a `project.task` they don't own. The
  model allowlist exists to prevent a wider class of mistakes (e.g.
  posting a note on a `res.users` record) regardless of persona.

### Tool 2 — `send_spec_pdf_email(order_id)`

Tier: T1. Personas: trade, sales. Scope: own_order.

```python
def send_spec_pdf_email(env, order_id: int):
    order = env["sale.order"].browse(order_id)
    order.check_access_rights("read")
    order.check_access_rule("read")
    template = env.ref(
        "sale.email_template_edi_sale", raise_if_not_found=False)
    if not template:
        raise UserError("Standard sale email template not available.")
    target_email = env.user.email or order.partner_id.email
    template.send_mail(order.id, force_send=False, email_values={
        "email_to": target_email,
    })
    return {"ok": True, "sent_to": target_email}
```

The "resend me the spec sheet" tool. Constraints:
- **Read-only check on the order** — `check_access_rights("read")` +
  `check_access_rule("read")`. Sending an email doesn't require write
  access; only reading the order to build the PDF.
- **Send to caller's email, not arbitrary recipient.** `target_email
  = env.user.email or order.partner_id.email`. The function does NOT
  accept a recipient argument. This is deliberate: per spec § 4.2,
  T1 trade-partner communication is "resend spec PDF to *partner's
  own email*." A trade partner can't ask Fabio to send the PDF to a
  competitor's email.
- **`force_send=False`** — queues the mail through the standard
  outgoing-mail queue rather than blocking the HTTP response.

Common confusions:
- "Why is this T1 if it doesn't change order state?" Because of the
  out-of-system side effect (email sent). T0 is reversible
  internal-only writes; T1 is communication that can't be undone.
- "Could a malicious user spoof `env.user.email` to redirect?" No
  — `env.user` is the dispatched portal user resolved from the JWT.
  The user record's email is set at admin time, not by the chat.

### Tool 3 — `schedule_followup_activity(order_id, summary, due_date)`

Tier: T1. Personas: all three. Scope: own.

```python
def schedule_followup_activity(env, order_id: int, summary: str, due_date: str):
    parsed_date = datetime.date.fromisoformat(due_date)
    if parsed_date < datetime.date.today():
        raise UserError("Activity due_date must be today or in the future.")
    order = env["sale.order"].browse(order_id)
    order.check_access_rights("read")
    order.check_access_rule("read")  # record-rule scope per spec § 4.4
    activity_type = env.ref("mail.mail_activity_data_todo")
    activity = env["mail.activity"].create({
        "res_id": order.id,
        "res_model_id": env["ir.model"]._get("sale.order").id,
        "activity_type_id": activity_type.id,
        "summary": summary,
        "date_deadline": due_date,
        "user_id": env.user.id,
    })
    return {"ok": True, "activity_id": activity.id}
```

Creates a `mail.activity` on the *order* with the caller as `user_id`
— i.e. an activity for the caller themselves, attached to the order.
Constraints:
- **Date validation.** `datetime.date.fromisoformat` raises
  ValueError on a malformed string (caught by dispatch as
  `tool_exception`); past dates raise `UserError`.
- **Read-only on the order**, not write. Creating an activity on a
  record doesn't require write to the record (Odoo's
  `mail.activity.mixin` ACL).
- **`user_id=env.user.id`** — the activity goes to the caller's
  user. The trade partner can't assign activities to other users.
  Sales reps and mfg managers also can't escalate to others through
  this tool.

Delta § 14.5 added `check_access_rule` here. Originally only
`check_access_rights`.

Common confusions:
- "Why is this T1?" Same reason as `send_spec_pdf_email` — it adds
  to someone's activity queue (visible to them, expected to be
  acted on), which is a communication side effect even though no
  email is sent.
- "Can the partner schedule an activity on someone else's record?"
  Only if they have read access to that record. Record rule denies
  → dispatch returns `tool_exception`.

### Tool 4 — `propose_recommendation(intent, payload, summary, ...)`

Tier: T2. Personas: all three. Scope: own.

**This is the universal T2 escape hatch — the ONLY way trade partners
get business state to change.**

```python
_TRADE_PARTNER_INTENTS = (
    "request_revision",
    "request_install_reschedule",
    "request_clarification",
)

@hermes_tool(
    personas=["trade_partner", "sales_rep", "mfg_manager"],
    tier="T2", scope="own",
    description=(
        "Create a draft southbrook.hermes.recommendation for human review. "
        "The actual business mutation only happens when an approver clicks "
        "Approve. For trade-partner persona, only request_revision, "
        "request_install_reschedule, and request_clarification intents "
        "are allowed."),
)
def propose_recommendation(env, intent: str, payload: dict, summary: str,
                            partner_id: int = None, persona: str = None,
                            name: str = None):
    import json
    if persona == "trade_partner" and intent not in _TRADE_PARTNER_INTENTS:
        raise UserError(
            f"Trade partners cannot propose '{intent}' recommendations. "
            f"Allowed intents: {', '.join(_TRADE_PARTNER_INTENTS)}.")
    if not partner_id:
        partner_id = env.user.partner_id.id
    Rec = env["southbrook.hermes.recommendation"]
    full_payload = {"intent": intent, "data": payload or {}}
    rec = Rec.sudo().create({
        "name": name or f"Hermes/{intent}/{summary[:48]}",
        "summary": summary,
        "recommendation_type": "task",
        "payload_json": json.dumps(full_payload, default=str),
        "source_model": "res.partner",
        "source_res_id": partner_id,
        "state": "draft",
    })
    return {"ok": True, "rec_id": rec.id, "summary": summary, "intent": intent}
```

The function declares `persona: str = None` and `partner_id: int = None`
— both **claim-bound**. Dispatch overrides them from JWT (delta § 14.2)
before the function runs. The function trusts those values absolutely.

**The trade-partner intent allow-list.** Three intents only:

- `request_revision` — "please revise my order to swap door colour
  to walnut" → reviewer files a project task to do the revision.
- `request_install_reschedule` — "can we push install to next month?"
  → reviewer files a task to coordinate with the install team.
- `request_clarification` — "what does 'soft-close' include?" → reviewer
  files a task to respond to the partner.

Any other intent raises `UserError`. This is the safety boundary —
trade partners cannot propose recommendations for arbitrary intents.
The list is enforced *inside the tool*, not at the dispatch tier check.

**Why `sudo()` here.** The created recommendation is owned by the
Fabio partner (`agent_partner_id` defaults to the Fabio seed partner),
not by the requesting trade partner. Reviewers in
`group_hermes_reviewer` see the queue; the requesting partner does
not. If the create ran as `env.user` (the partner's portal user), the
resulting record would be invisible to reviewers under their record
rules. The `.sudo()` is spec § 4.4 rule 2's documented exception.

**The recommendation always starts in `draft`.** Reviewer must mark
ready → approve → apply. See lesson 13.2 for the full state machine.

**`recommendation_type = 'task'` regardless of intent.** All three
trade-partner intents map to `task` because applying needs to create
a `project.task` for someone to action. If a future intent wants to
fire a different side effect, the `recommendation_type` selection
in `models/hermes_recommendation.py` would need to expand and the
`action_apply` method would need a new branch.

**The `payload_json` shape.**

```json
{
  "intent": "request_install_reschedule",
  "data": {
    "preferred_date": "2026-08-15",
    "reason": "kitchen renovation delayed by drywall contractor"
  }
}
```

The `intent` key tells the reviewer what the partner wanted. `data` is
arbitrary JSON the LLM filled in based on the conversation. The
reviewer reads both fields when deciding whether to approve.

**`recommendation_type='task'` means `_create_project_task` runs on
apply.** Which means the payload also needs `project_id` to be set
before apply. The LLM's `propose_recommendation` call doesn't set
`project_id` — the reviewer adds it to `payload_json` before clicking
Apply. This is the "human bridges" step: the partner's intent is
captured by the LLM; the project assignment is captured by the
reviewer. (Or: the apply raises `UserError("Task recommendations
require payload.project_id.")` and the reviewer fills it in. See
lesson 13.2.)

Common confusions:
- "Why is the tier T2 if it can't actually write business state?"
  Because *applying* the recommendation writes business state. The
  *creating* of the draft is the request side; the approval is the
  authorize side. The combined path is T2 because the eventual effect
  is a database mutation. The split makes the boundary auditable.
- "Why can sales reps and mfg managers also propose recommendations?"
  Because the queue is a useful pattern for them too — e.g. a sales
  rep using the chat panel to propose a re-quote that needs manager
  approval. v1.1/v1.2 will extend their tool set with more
  autonomous writes, but `propose_recommendation` remains a universal
  escape hatch.
- "What stops a malicious prompt from elevating the intent to
  `request_arbitrary_change`?" Two guards: (1) dispatch
  claim-binding sets `persona='trade_partner'` from the JWT,
  overriding any LLM-supplied value (delta § 14.2); (2) the function
  body's `if persona == 'trade_partner' and intent not in
  _TRADE_PARTNER_INTENTS` raise. Both must be defeated for an
  elevation to succeed — and the first is enforced by the dispatch
  controller, which the LLM cannot touch.

## Your daily flow

### As a developer adding a write tool

1. Decide the tier honestly.
   - Is the change reversible and internal-only? → T0.
   - Does it trigger out-of-system communication (email, activity,
     external API)? → T1.
   - Does it mutate business state (book, schedule, confirm,
     cancel)? → T2 — and route through `propose_recommendation`,
     don't write directly.
2. Decide the persona allowlist. For T2 tools written for
   trade-partner use, route everything through
   `propose_recommendation` rather than adding a new T2 tool.
3. For T0 tools: include both `check_access_rights("write")` and
   `check_access_rule("write")`. Use `mail.mt_note` subtype for
   chatter writes.
4. For T1 tools: think about who receives the side effect. Scope
   recipients tightly (caller's own email, caller's own user). Never
   accept arbitrary recipient args.
5. Avoid `.sudo()`. The only allowed use is the
   `propose_recommendation` carve-out where the recommendation is
   owned by Fabio, not the caller.
6. Smoke test with `scripts/smoke_hermes.sh`. If the tool changes
   state, verify rollback if the test fails mid-flight (Odoo's
   per-request transaction usually handles this).

### As a production manager reviewing the trade-partner T2 path

Per spec § 6, the trade-partner T2 path is:

1. Trade partner asks Fabio a question that implies a state change.
2. LLM emits `propose_recommendation(intent=..., payload=..., summary=...)`.
3. Tool creates a draft `southbrook.hermes.recommendation` with
   `source_model='res.partner'`, `source_res_id=<partner.id>`,
   `state='draft'`.
4. Chat answer to the partner: "I've queued a draft (#REC-1234)."
5. Reviewer (you) opens **Fabio → Recommendations**, finds the draft,
   reads, decides.
6. If approve: `state='approved'`, you fill in `project_id` in the
   payload, click Apply → `_create_project_task` creates the task,
   `state='applied'`.
7. The task is now in the project board for someone to action.

Failure modes to watch for:
- **Drafts stuck for hours.** The sidecar errored after the draft
  was posted but before the LLM told the partner. Mark ready
  yourself, review.
- **Drafts with malformed payloads.** The LLM filled in
  `payload.data` with wrong types (datetime instead of date string,
  user id instead of partner id). Fix the payload, then approve.
- **Drafts for the wrong partner.** Shouldn't happen — dispatch's
  claim-binding sets `source_res_id` from JWT. If it does happen,
  there's an auth bug; escalate.

### As an auditor checking the safety boundary

Three queries:
- Show every recommendation created by `propose_recommendation` (find
  `source_model = 'res.partner'`).
- Show every recommendation applied with `recommendation_type='task'`
  (state=applied AND created_task_id IS NOT NULL).
- Show every internal note posted by Fabio (search `mail.message`
  where `author_id` resolves through the chat panel — typically via
  the calling partner's user).

The combination tells you "what business state did Fabio touch this
quarter?" — recommendation applications are the only T2 writes;
internal notes are T0; emails are T1 logged in mail queue.

## Common mistakes + how to recover

**"I want to add a T2 tool that writes directly without going through
recommendations."**

For trade partners: NO. The recommendation queue is the only T2 path
in v1.0. The spec is unambiguous: "No write actions for trade
partners that don't pass through a recommendation" (§ 11
non-goals).

For sales reps and mfg managers: spec § 4.2 says future tiers may
auto-apply under a threshold or require 2-eyes review. v1.1 and v1.2
will add those paths. Until then, route through
`propose_recommendation` and approve in the queue.

**"`post_internal_note` raised `UserError("Hermes can't post notes on
'res.partner'")`."**

The allowlist is `("sale.order", "project.task",
"southbrook.hermes.question")`. To post a note on a partner, file
a `propose_recommendation` with a `request_clarification` intent and
have the reviewer post the partner-level note manually. Or, if this
is genuinely a new use case, add `res.partner` to the allowlist —
but pause first and ask whether the use case is really "log on
partner" or "queue for reviewer to log."

**"`send_spec_pdf_email` sent the PDF to my email, not the
customer's."**

Working as designed. The recipient is `env.user.email or
order.partner_id.email` — the caller's email takes precedence. Trade
partners using Fabio get the PDF themselves; they re-share manually
if the customer wants a copy. This is the spec § 4.2 boundary:
T1 trade-partner communication is "to partner's own email," not
arbitrary recipients.

**"A `schedule_followup_activity` call returned 500 with
`activity_type_data_todo not found`."**

The standard mail activity types are seeded by the `mail` addon. If
they're missing, the `mail` addon needs reinstalling. Verify:
**Settings → Technical → Activity Types**. Should see "To-Do" and
"Email" at minimum.

**"A trade partner's `propose_recommendation` call returned 400
`Trade partners cannot propose 'request_install_cancel'
recommendations.'"**

Intent not in the allowlist. The fix is NOT to widen the allowlist;
it's to map "cancel install" to a `request_install_reschedule` with
a payload of "reschedule to indefinite hold." The allowlist is small
on purpose — every addition is a new risk surface that gets
audited.

**"A reviewer asked 'who authored this recommendation?' and the
answer was 'Fabio' but they want the trade partner's name."**

The `agent_partner_id` is Fabio; the *source* is the partner. Read
`source_model + source_res_id` — for trade-partner-proposed recs,
that's `('res.partner', <partner.id>)`. The reviewer can browse the
partner to see who actually triggered the proposal. This is the
intentional split: provenance (agent) vs subject (partner).

## What the system is doing behind the scenes

### Why the tier matrix mask is "T0+T1+T2" for every persona

Spec § 14.1's implementation delta is the canonical explanation. The
short version: strict mask enforcement (trade partners get only
"T0+T1") would prohibit them from calling `propose_recommendation`,
which is a T2 tool they MUST be able to call. The fix was to widen the
mask for everyone, and move the trade-partner safety boundary INTO the
function: `_TRADE_PARTNER_INTENTS` is the actual gate.

This is a "the tool itself is the ACL" pattern. The dispatch's tier
check is still there (defense in depth), but the trade-partner safety
isn't dependent on it.

### Why the recommendation flow is "always draft, never autonomous"

For trade partners, the answer is in the spec § 11 non-goals: "No write
actions for trade partners that don't pass through a recommendation."
The trade-partner persona is the lowest-trust persona in the system;
every business-state change must have a human authorize it.

For sales reps and mfg managers in v1.0, same thing — they get the
same `propose_recommendation` path. v1.1 / v1.2 will add tier-specific
auto-approve paths, but those have their own approval-after-the-fact
audit gates.

### Why `payload_json` mixes intent (LLM-provided) and data (LLM-provided)

The split between `intent` (one of three) and `data` (arbitrary JSON)
lets the reviewer make fast filtering decisions ("show me all
`request_install_reschedule` proposals") while preserving the
unstructured details ("preferred date 2026-08-15, reason kitchen
delayed"). The reviewer reads the summary, eyeballs the data, decides
go / no-go quickly.

### Why `recommendation_type='task'` even when the intent is
`request_clarification`

Because every approved recommendation should result in a tracked unit
of work for a Southbrook user. "Clarification request" → "task to
respond to partner" is the same pipeline as "install reschedule" →
"task to coordinate with install team." Treating all three intents as
tasks keeps the apply mechanic simple. If a future intent really has
no associated task (e.g. "FYI only"), the recommendation_type would
be `note` or `risk` and `_create_project_task` would not fire.

### Why `name` is auto-generated as `"Hermes/<intent>/<summary[:48]>"`

So the queue list view has scannable titles. A trade-partner-originated
draft might be:

```
Hermes/request_install_reschedule/Push install to August 15 due to drywal...
```

The truncation at 48 chars keeps the list view tidy. The full summary
is in the `summary` field. The `name` is meant to be a glanceable
title, not the full text.

### Why `force_send=False` on `send_spec_pdf_email`

Avoids blocking the HTTP response on SMTP. The mail queue runs every
60 seconds (Odoo native cron), so the email goes out within a minute.
Trade partner expectations are "I asked, I'll get an email"; a 60-second
wait is fine. If we used `force_send=True`, an SMTP timeout would
stall the chat panel.

## Quiz (5 questions, applied)

**1.** A trade partner asks Fabio "can you mark my order as urgent in
the planner?" The LLM tries to call a tool that writes
`order.priority='urgent'` directly. What stops this?

> Nothing exists to call. The 4 write tools don't include a "set
> order priority" tool. The LLM may try `propose_recommendation`
> with `intent='request_urgent_priority'`, which raises `UserError`
> ("Trade partners cannot propose 'request_urgent_priority'.").
> The LLM recovers by surrendering ("I can't mark orders urgent; ask
> your salesperson to flag it.") The closed allowlist of trade-
> partner intents is the safety boundary.

**2.** A sales rep uses `propose_recommendation` with
`intent='reprice_order'`. Does the tool reject this?

> No — the `_TRADE_PARTNER_INTENTS` allow-list guard is gated by
> `if persona == 'trade_partner'`. For sales rep or mfg manager
> persona, any intent is accepted at the tool layer. The downstream
> approval gate still applies (a reviewer must approve), and v1.1
> may add a sales-rep auto-approve under threshold. The tool's
> safety boundary is persona-specific.

**3.** `propose_recommendation` is decorated `tier="T2"`, but the JWT
tier mask is `"T0+T1+T2"` for trade partners. Why not strict mask
"T0+T1" with a special exemption?

> Because the strict mask would block every trade-partner call to
> `propose_recommendation` at the dispatch's tier check, before
> the function ever runs and could enforce its intent allow-list.
> Spec § 14.1 documents the decision: "the trade-partner safety
> boundary moves from the tier mask (always going to leak the
> moment one T2 tool needed to be addressable by trade partners) to
> the tool's own intent allow-list." The mask is permissive; the
> tool function is restrictive.

**4.** You approve a trade-partner `propose_recommendation` draft.
Apply raises `UserError("Task recommendations require
payload.project_id.")`. What does this mean and how do you fix it?

> The `propose_recommendation` tool doesn't set `project_id` in the
> payload — it only sets `intent` and `data`. Apply tries to create
> a `project.task`, which needs `project_id`. The reviewer's job is
> to add the project: edit `payload_json` to inject `"project_id":
> <id>`, save (the JSON-shape validator passes; the field isn't
> validated until apply), then click Apply again. The split is
> intentional: the LLM captures partner intent; the reviewer
> captures project assignment.

**5.** A junior dev wants to add an `email_partner` write tool that
sends arbitrary text to the calling trade partner's email. What
tier should it be, and what guards must it have?

> Tier T1 (communication side effect). Guards:
> (a) personas restricted (probably trade_partner, sales_rep only —
> mfg managers shouldn't be emailing trade partners through chat);
> (b) `check_access_rights("read")` + `check_access_rule("read")` on
> any record-context arg (e.g. an order_id);
> (c) recipient is always `env.user.email`, NEVER an arbitrary
> recipient arg — mirrors `send_spec_pdf_email`'s pattern;
> (d) body is the text param, no template substitution that could
> exfiltrate other data;
> (e) `force_send=False` so SMTP queues asynchronously.
> Document the design and code-review heavily — anything that sends
> email is a security-sensitive surface.

---

## What this lesson does NOT cover

- The recommendation queue's state machine and audit fields — that's
  lesson 13.2 (`13_recommendation_queue_deep.md`).
- The 9 read tools — lesson 13.5 (`13_read_tools.md`).
- The tool registry mechanics — lesson 13.4 (`13_tool_registry.md`).
- JWT + persona resolution — lesson 13.3 (`13_jwt_auth_personas.md`).
- The chat panel + sidecar (consumers of these tools) — lesson 13.7.
- The reviewer's daily flow (approve / reject / apply) — lesson 3.2
  (`03_hermes_fabio_approval.md`).
- Sales-rep and mfg-manager tool sets (v1.1 + v1.2 — not shipped in
  v1.0) — see spec § 8 phasing.
