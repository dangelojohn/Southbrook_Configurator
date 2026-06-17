---
course: 10 — Configurator Deep Dive
chapter: 10.3
title: Configuration Sessions + the State Machine
duration: 40 minutes
audience: Developer or senior admin who has to debug a stuck session, recover a customer's lost configuration, or understand why a draft disappeared overnight.
prereqs: Course 5 (5.1). Lessons 10.1 (architecture) + 10.2 (new product setup). You can open `odoo-bin shell`.
custom_modules: product_configurator, product_configurator_mrp, website_product_configurator, southbrook_configurator_ux
---

# Configuration Sessions + the State Machine

## Who this lesson is for

You're a developer or senior admin and one of three things just
happened:

- A customer says "my configuration disappeared overnight, I had it
  set up yesterday."
- An estimator reports "I hit Configure and the wizard opens but
  picks aren't sticking."
- Your monitoring shows the `product_config_session` table grew by
  40k rows in a week and you want to know why.

All three are session-machine problems. This lesson is the model
walk-through: what a session is, what states it has, what writes to
it, what reads it, how it gets garbage-collected, and how to debug
it from the dev shell. No GUI here — this is shell + log work.

## Where this lives on the site

The session catalog UI:

> **Sales → Configurable Products → Configuration Sessions** — every
> session ever created, draft or done. Filterable by user, template,
> state. Where you go to confirm a customer's session exists before
> diagnosing further.

The cron status:

> **Settings → Technical → Scheduled Actions** — search "Config" — you
> see two crons:
> - `Product Configurator: GC stale draft sessions`
>   (`ir_cron_gc_draft_sessions`, daily)
> - `Delete inactive config-sessions`
>   (`cron_delete_sessions_with_no_activity`, daily)

The dev shell (terminal):

> `odoo-bin shell -d <db>` — your primary tool for any session-state
> work beyond eyeballing the list.

## What your screen shows

A `product.config.session` record carries:

- **`name`** — auto-assigned from `ir.sequence` "product.config.session".
  Format depends on the sequence config; usually `PCS00001` upward.
- **`product_tmpl_id`** — the configurable template (`config_ok=True`)
  this session is configuring. Required, M2O.
- **`user_id`** — the user who started the session. Required. Public
  visitors get `base.public_user`; portal customers get their own
  user; internal estimators get theirs.
- **`value_ids`** — Many2many to `product.attribute.value`. The
  current set of picks. Updated on every wizard step.
- **`custom_value_ids`** — One2many to
  `product.config.session.custom.value`. Free-text picks for
  attributes flagged `custom = True` (engraving, dimensions, notes).
- **`product_id`** — the materialised `product.product` variant. Null
  until `action_confirm()` writes it.
- **`price`** — computed via `_compute_cfg_price()` from value picks +
  PTAV `price_extra`. Stored.
- **`weight`** — computed via `_compute_cfg_weight()` from
  `weight_extra`. Not stored.
- **`config_step`** — Char holding the current step's
  `product.config.step.line.id` as a string. The OCA wizard reads
  this to know which step to render.
- **`config_step_name`** — computed display name.
- **`bookmark_name`** + **`is_saved`** — the "save configuration"
  feature; `is_saved = True` protects the session from the GC cron.
- **`state`** — the state machine. Selection: `draft` / `done`.
  Required, default `draft`.

The state machine is **two states, one transition**:

```
       create()                 action_confirm()
NULL ────────────► draft ────────────────────────► done
                    │                                 │
                    │ (write to value_ids)           │ (immutable)
                    └──── stays draft ───────────────┘
                    │
                    │ GC crons
                    ▼
                  DELETED
```

That's it. No `cancel`, no `pending`, no `error`. A session is born
draft, lives in draft (any number of writes / re-validations), and
ends one of two ways:

- **`done`** — `action_confirm(product_id)` was called. The session
  is permanently locked. `product_id` is set. The session is
  effectively the receipt for that variant.
- **DELETED** — a GC cron found it stale and unlinked it.

A draft session **cannot** be re-opened to `draft` once `done`. If a
customer wants to edit a confirmed configuration, the flow is
`sale.order.line.reconfigure_product()` (defined in
`product_configurator_sale/models/sale.py:38`) — that creates a
**new** session, prefilled from the existing variant. The old `done`
session is left alone.

## Your daily flow

You spend most of your "session" time in the dev shell. Three jobs:

**1. "Why won't my session validate?"**

```bash
odoo-bin shell -d <db>
```

Then:

```python
Session = env["product.config.session"]
# Find the suspect session
s = Session.search([
    ("user_id.login", "=", "customer@example.com"),
    ("state", "=", "draft"),
], limit=1, order="create_date desc")
print(s.read(["name", "product_tmpl_id", "value_ids", "state"]))
# Try validating
s.validate_configuration()  # defined at product_config.py:1482
```

If it raises `ValidationError`, the exception message tells you
which rule fired. The common shapes:

- `"Values must belong to the attribute …"` — a value in `value_ids`
  isn't allowed on the template's attribute_line. Usually means a
  rule removed it but the session still has it.
- `"Required field …"` — an attribute_line marked `required=True`
  has no value in `value_ids`.
- `"Default values provided generate an invalid configuration"` —
  the session's `default_val` picks (set at create) violate a rule.
  Means the template was misconfigured at install.

**2. "I have to recover a customer's lost configuration."**

If the session is `state='draft'` and not yet GC'd:

```python
# By customer email
s = Session.search([
    ("user_id.login", "=", "customer@example.com"),
    ("product_tmpl_id.name", "ilike", "Vanity 24"),
], order="create_date desc", limit=5)
# Show what they picked
for sess in s:
    print(sess.name, sess.state, sess.write_date,
          [v.name for v in sess.value_ids])
```

If `state = done`, the session is permanent — the customer's
configuration lives on the variant + the order line referencing
`config_session_id`. Open the sale order, find the line, call
`line.reconfigure_product()` to spawn a new editable session
prefilled from the variant.

If `state = draft` and the GC cron ran, the row is gone. Lost. The
only recovery is asking the customer to reconfigure.

**3. "I need to clean up stuck sessions without waiting for the cron."**

```python
# Force-run the OCA cron logic
env["product.config.session"]._gc_draft_sessions()
# Or the website cron logic (3-day threshold)
env["product.config.session"].remove_inactive_config_sessions()
env.cr.commit()
```

Both methods skip done sessions and respect the protection (sessions
attached to sale.order.lines via `config_session_id` are not touched
by either cron in normal operation — but verify by reading the
method source before running in production).

## Common mistakes + how to recover

**"A customer's draft session disappeared overnight even though I'd
seen it in the catalog yesterday."**

The two crons disagree on threshold. OCA's `_gc_draft_sessions` uses
`ir.config_parameter product_configurator.session_gc_days` (default
7 days). The website extension's `remove_inactive_config_sessions`
uses a **hard-coded 3 days** (see
`website_product_configurator/models/product_config.py:37`). The
website cron runs first chronologically (alphabetical model load
order); it deletes a 3-to-7-day-old draft before OCA's 7-day cron
sees it. Workaround: tell customers to use the "Save Configuration"
button (`action_save_config`) which sets `is_saved=True` and (in
theory) protects against GC. Verify the protection by reading
`_gc_draft_sessions`; if the website cron ignores `is_saved`,
that's a bug to file.

**"The session is `state=draft` but write to value_ids raises
'Invalid Configuration'."**

`product.config.session.write()` calls `validate_configuration(final=False)`
on every write. If the new write violates a rule, the entire write
is rolled back — including writes to unrelated fields. You can't
just clear `value_ids` from the UI to recover; the validation runs
even on `[]`. Workaround: in the shell, set `value_ids = [(5, 0, 0)]`
(the M2M clear) with `self.with_context(check_constraints=False)` —
but only if you understand the side effects.

**"I created a session in the shell and the `name` is `New` instead
of `PCS00001`."**

The `name` is auto-assigned by `ir.sequence.next_by_code('product.config.session')`
in the `create()` override (line 866). If the sequence is missing
(e.g. demo DB without `product_configurator/data/ir_sequence_data.xml`
loaded), the code falls through to the literal "New" via the
`or self.env._("New")` fallback. Diagnose: `env["ir.sequence"].search([("code", "=", "product.config.session")])`
— if empty, install/update `product_configurator` to load the
sequence.

**"Customer says they hit Save Configuration but coming back the
next day the configuration is gone."**

Likely the website cron isn't honouring `is_saved`. Read
`remove_inactive_config_sessions` — at the time of writing it
filters only on `state == 'draft'` and `write_date <`, ignoring
`is_saved`. **TBD: this is a gap; confirm in the latest code before
declaring a bug.** Workaround until fixed: add an
`ir.cron`-level overlay that explicitly excludes saved sessions, or
backport `is_saved` to the GC filter.

**"The same customer has 50 draft sessions for the same template."**

The customer is opening `/shop/<slug>` repeatedly. Each visit creates
a fresh session via `_get_or_create_session` (in
`southbrook_configurator_ux/controllers/main.py:311`). The OCA flow
on the backend tries to reuse but the Southbrook v2 surface always
creates a fresh draft. Mitigation: the cron clears them in 3 days;
operationally it's a non-problem unless DB size matters.

**"The session committed but `product_id` is empty and the line on
sale.order didn't get its config_session_id."**

Check the order in which the controller fires
`session.action_confirm(product_id=variant)` vs creating the line.
In `southbrook_configurator_ux/controllers/main.py:configurator_commit`,
the order is: create variant → write `default_code` → resolve order
→ create line → call `action_confirm`. If `action_confirm` raises,
the line is already created but the session stays draft (the
exception handler logs but doesn't re-raise). This is intentional —
the customer's order is preserved at the cost of leaving an
orphan draft. The GC cron will sweep it.

## What the system is doing behind the scenes

The OCA session's **write** path is the load-bearing piece:

```python
def write(self, vals):
    res = super().write(vals)
    if not self.product_tmpl_id:
        return res
    value_ids = self.value_ids.ids
    avail_val_ids = self.values_available(value_ids)
    if set(value_ids) - set(avail_val_ids):
        self.value_ids = [(6, 0, avail_val_ids)]  # auto-prune forbidden
    self.validate_configuration(final=False)
    return res
```

Three things to notice:

1. The session **auto-prunes** forbidden values. If you write
   `value_ids = [Contractor, Maple]` and a rule forbids Maple-on-
   Contractor, the write call removes Maple silently. The wizard
   notices because its next render shows Maple unchecked.
2. `validate_configuration(final=False)` runs on every write. The
   `final=False` mode allows missing required attributes (because
   you're still mid-wizard). On `action_confirm`, the variant
   creation calls `validate_configuration()` with `final=True`,
   which raises if required attributes are missing.
3. The validation surface area is `values_available()` (line 1377)
   which reads all `product.config.line` rules for the template and
   filters their domains against current picks. This is the
   declarative-rule engine the lessons keep referring to.

The OCA `update_config(attr_val_dict)` method (line 754) is the
canonical setter — it takes `{attr_id: value_id}` and re-builds
`value_ids` by removing old per-attribute picks and adding new
ones. This is what `/select` calls in the v2 controller.

`action_confirm(product_id=None)` (line 649) flips state to `done`
and writes `product_id`. There's no transition out of `done` — by
constraint (`_check_product_id` at line 657), done sessions must
have `product_id`, and there's no `action_cancel` or `action_revert`.

The two GC crons (covered in 10.1 too):

```xml
<!-- product_configurator/data/cron.xml -->
<record id="ir_cron_gc_draft_sessions" model="ir.cron">
  <field name="code">model._gc_draft_sessions()</field>
  <field name="interval_number">1</field>
  <field name="interval_type">days</field>
</record>

<!-- website_product_configurator/data/cron.xml -->
<record id="cron_delete_sessions_with_no_activity" model="ir.cron">
  <field name="code">model.remove_inactive_config_sessions()</field>
  <field name="interval_number">1</field>
  <field name="interval_type">days</field>
</record>
```

`_gc_draft_sessions` (OCA, the canonical one) — **TBD: read the actual
implementation to confirm `is_saved` protection.** The cron comment
in the XML claims "Sessions referenced by a sale.order.line via
config_session_id are NEVER collected" — verify in code.

`remove_inactive_config_sessions` (website) — **3 days hard-coded**,
draft-only. Does NOT respect `is_saved`. Bug-or-feature: file a
ticket if your team relies on Save Configuration.

The `product.config.session.custom.value` model (line 1819) is a
1:1-via-Many2one child carrying free-text custom values. One row per
custom attribute. Has its own validation (`unique_attribute`
constraint at line 1866) so you can't double-write the same attribute.

## Quiz (5 questions, applied)

**1.** You browse a session in the shell. `state = draft`,
`value_ids` has 8 values, `product_id` is False. The customer says
"I want to confirm this as my variant." Walk through what happens
when you call `s.action_confirm()`.

> `action_confirm()` calls `session.create_get_variant()` (because
> `product_id` is None). `create_get_variant` calls
> `validate_configuration()` first (final=True implied — raises
> on missing required or rule-violation), then either fetches the
> existing variant matching the picks or creates a new one. On
> success, it writes `state='done'` + `product_id=variant.id`. The
> `_check_product_id` constraint enforces the link is non-null.
> The session is now permanent.

**2.** A customer's draft session shows `value_ids = [Contractor,
Maple]` when you browse it in the shell. You know Rule 2 forbids
Maple-on-Contractor. Why didn't the auto-prune in `write()` strip
Maple?

> The auto-prune fires inside `write()` AFTER super().write() —
> which means it depends on `values_available()` being able to see
> the new picks AND the rule. If the session was created with both
> values in a single `create()` call (not write), the
> `create()` override (line 864) runs `validate_configuration`
> with `final=False` which allows the combination through if neither
> attribute is the "required" one being missed. Bug-or-feature
> debate. Recovery: in shell call
> `s.value_ids = [(6, 0, [Contractor.id])]` — write triggers the
> prune correctly when given a single value at a time.

**3.** A customer's session is `state=draft`, write_date is 4 days
ago. The website GC cron is set to 3-day threshold. The customer
opened it 4 days ago, paid attention, hit Save Configuration. Next
morning the session is gone. What happened, and what's the fix?

> The website cron `remove_inactive_config_sessions` doesn't
> currently filter on `is_saved` — it only checks
> `state='draft' AND write_date < now() - 3 days`. So the saved
> session gets swept anyway. Two fixes: (a) raise the website cron
> threshold to match OCA's 7-day param, or (b) patch
> `remove_inactive_config_sessions` to add `('is_saved', '=', False)`
> to its domain. Patch (b) is correct; (a) only delays.

**4.** You want to add a third state to the machine — "approved" —
between draft and done, gated by a senior estimator. Where do you
add it and what breaks?

> Inherit `product.config.session` in `southbrook_estimating`,
> override the `state` field's selection to add `('approved',
> 'Approved')`. Add an `action_approve` method to transition
> draft→approved. Override `action_confirm` to require
> `state='approved'` instead of `state='draft'`. What breaks:
> the `_check_product_id` constraint expects `state='done' implies
> product_id is set` — your new state needs the same guard. The
> OCA wizard's "Add to Cart" button calls `action_confirm` directly
> — you'll need a UI override too. And both GC crons treat
> `state='draft'` as the candidate; an `approved` session is not
> draft so won't be GC'd, but won't be `done` either — verify the
> behaviour you want.

**5.** Your monitoring shows 250 new sessions per hour created at
3am. None of your customers configure cabinets at 3am. What's
happening, and how do you confirm?

> A web crawler is hitting `/shop/<slug>` for configurable
> products. Each hit fires `/southbrook/api/configurator/state`,
> which calls `_get_or_create_session(tmpl)` — public visitors
> land on `base.public_user`, so EVERY anonymous request creates a
> fresh session. Confirm by `Session.search([
> ("user_id", "=", env.ref("base.public_user").id),
> ("create_date", ">=", "<3am window>"),
> ])` — count should match the alarm. Mitigation: tighten the
> `/state` route's rate limit at proxy level, OR change
> `_get_or_create_session` to NOT create-for-public on first hit
> (require an explicit pick action before creating).

---

## What this lesson does NOT cover

- Configurator vocabulary basics — Course 5, Lesson 5.1.
- 5-addon dependency graph — Lesson 10.1.
- Setting up a new configurable product — Lesson 10.2.
- Sale-flow integration of session→line — Lesson 10.4.
- MRP-flow integration of session→BoM — Lesson 10.5.
- V2 UX OWL component internals — Lesson 10.6.
- Common rule-authoring gotchas (exclusion explosion, sequencing) —
  Lesson 10.7.
- Native Odoo cron administration — Odoo's own native eLearning track.
