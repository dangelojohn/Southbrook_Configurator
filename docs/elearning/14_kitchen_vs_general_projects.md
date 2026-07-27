---
course: 14 — Project Module Deep Dive
chapter: 14.2
title: Kitchen Projects vs General Projects — Why Southbrook Has Both
duration: 30 minutes
audience: Project Manager + Developer (and the salesperson curious about why a "kitchen" needs two records)
prereqs: Lesson 14.1 (architecture overview); Course 2 lesson 2.1 (Kitchen Projects vs Sale Orders)
custom_modules: southbrook_kitchen_workspace, southbrook_project, southbrook_project_mrp, southbrook_estimating
---

# Kitchen Projects vs General Projects — Why Southbrook Has Both

## Who this lesson is for

You're a project manager who looks at the menu and sees both
**Sales → Kitchen Workspace → Projects** AND **/odoo/project** and
quietly suspects something is duplicated. Or you're a developer who
just inherited the codebase and finds two models — `project.project`
and `sb.kitchen.project` — that both seem to represent "the kitchen"
and you can't tell which is canonical. This lesson is the
reconciliation: WHY both exist, WHEN each is used, WHAT data flows
between them, and what the UI cues are.

Lesson 2.1 covers the planner's mental model. This lesson goes deeper
into the *data layer* and answers the developer's "is one record the
backing record of the other?" question definitively.

## Where this lives on the site

Sign in at **southbrookcabinetry.space/odoo**. The same physical
kitchen can be looked at through three different doors:

> **Sales → Kitchen Workspace → Projects** — opens the
> `sb.kitchen.project` list. This is the *design-stage* record. Owned
> by `southbrook_kitchen_workspace`. The salesperson lives here.

> **/odoo/project** — opens the stock Odoo Project app. The
> `project.project` records ("Test", "Vanity Refits", etc.) are
> *buckets* — each holds many `project.task` rows. The PM lives here.

> **Kitchen Ops → Kitchen Jobs** — opens the planner-facing kanban of
> the `project.task` spine for every confirmed kitchen order.
> Same `project.task` records as `/odoo/project`, different view.

The vocabulary clash is real: the word "Project" means three different
things depending on which door you open.

## What your screen shows

A single physical kitchen at Southbrook is represented as **three
linked records** during its lifecycle:

1. `sb.kitchen.project` — the *design engagement.* Created the moment
   the salesperson opens a Kitchen Workspace session. Custom model in
   `southbrook_kitchen_workspace/models/sb_kitchen_project.py`. Lives
   under **Sales → Kitchen Workspace → Projects**.

2. `sale.order` — the *commercial commitment.* Created when the
   salesperson finalises a quote (manually or from the Order Builder).
   Stock Odoo model. The `sb.kitchen.project.sale_order_id` Many2one
   points at it.

3. `project.task` — the *shop-floor job.* Created automatically when
   the `sale.order` confirms (via the override on
   `sale.order._action_confirm` in `southbrook_project_mrp/models/sale_order.py`).
   Lives on a *stock* `project.project` (typically project ID 1, "Test"
   on the live instance — see lesson 14.1 for how the post-init hook
   provisioned it). The PM works against it on `/odoo/project`.

Note the asymmetry: there's no `sb.kitchen.project` ⇄ `project.task`
direct link in the data model. They link **indirectly through the
sale order**:

```
sb.kitchen.project.sale_order_id  →  sale.order
                                         ↓ (on _action_confirm)
                                     project.task
                                       (x_southbrook_sale_order_id back-ref)
```

So if you're standing on a `project.task` and want to find the
originating Kitchen Workspace, you walk the chain:

```python
task.x_southbrook_sale_order_id  # the SO
sb_kp = env['sb.kitchen.project'].search(
    [('sale_order_id', '=', task.x_southbrook_sale_order_id.id)],
    limit=1)
```

The reverse direction (`sb.kitchen.project` → `project.task`) is the
same walk. No One2many shortcut, because the design-stage record
shouldn't *need* to know about the shop-floor task — by the time the
shop is involved, design is over.

### Fields you'll see on `sb.kitchen.project` (owner: `southbrook_kitchen_workspace`)

- `name` (Char) — free-form, e.g. "Smith Walnut U-Shape"
- `code` (Char) — sequential, "KP/2026/000123" format (seeded sequence)
- `state` (Selection) — draft / designing / awaiting_customer /
  approved / in_production / done / cancelled. **State machine**
  enforced via `action_set_state` with a `VALID_TRANSITIONS` set —
  off-graph transitions raise `UserError`.
- `theme` (Selection) — signature / elegance / contemporary /
  contractor (aligned with the four configurator series in
  `southbrook_estimating`)
- `partner_id` (Many2one to `res.partner`) — the customer, required
- `opportunity_id` (Many2one to `crm.lead`) — origin opportunity
- `salesperson_id` (Many2one to `res.users`) — the designer
- `date_created`, `date_target`, `date_completed` (Date)
- `design_option_ids` (One2many to `sb.kitchen.design.option`) —
  concept A / B / C
- `selected_design_option_id` (Many2one, computed-stored) — the
  selected concept; selecting one clears the others
- `ai_analysis_id` (Many2one to `sb.kitchen.ai.analysis`) — Gemini's
  output for the room
- `appliance_ids` (One2many to `sb.kitchen.appliance`) — stove,
  fridge, sink, etc. with clearances
- `approval_ids` (One2many to `sb.kitchen.approval`)
- `sale_order_id` (Many2one to `sale.order`) — the link out to commerce

### Fields you'll see on `project.task` (owners: stock `project`, `southbrook_project`, `southbrook_project_mrp`)

The cabinetry custom fields owned by `southbrook_project`
(`x_southbrook_material_species`, `x_southbrook_unit_count`,
`x_southbrook_hardware_specs`, `x_southbrook_sale_order_id`,
`x_southbrook_priority`) are catalogued in lesson 14.1. The full set
of `southbrook_*` MRP/coordination fields owned by
`southbrook_project_mrp` is catalogued in lessons 14.3 + 14.4 + 14.5.

The clearest **UI cue you're on a `project.task` (not an
`sb.kitchen.project`)** is the form heading: a task shows the
"Cabinetry Specs" notebook tab and (when an SO is linked) the
`display_name` is suffixed `[S0042]`. The Kitchen Project form has the
"Design Options" + "Appliances" + "Approvals" tabs and no `[S0042]`
suffix.

## Your daily flow

**As a salesperson, working pre-confirmation:**

1. Open **Sales → Kitchen Workspace → Projects**, create a new
   `sb.kitchen.project`, fill `name` + `partner_id`.
2. Move state draft → designing (click the button or call
   `action_start_designing`). The state machine logs the transition to
   chatter.
3. Add design options A / B / C, run AI analysis, capture appliances,
   capture customer feedback.
4. When the customer picks concept A, mark it selected (the One-of-N
   compute clears B + C).
5. Author the quote (Order Builder → generates `sale.order`).
6. Set `sb.kitchen.project.sale_order_id` to the freshly created SO.
7. Move state designing → awaiting_customer → approved.

At no point in the salesperson's flow does a `project.task` exist.
The shop hasn't seen the kitchen yet.

**As a planner / PM, working post-confirmation:**

1. Customer signs off → salesperson clicks *Confirm* on the SO.
2. `sale.order._action_confirm` calls `_southbrook_ensure_job`, which:
   - Checks the order lines carry products with a BoM. If not, skips
     (no shop work needed).
   - Searches for an existing `project.task` with
     `x_southbrook_sale_order_id = self.id`. If one exists, reuses it.
   - Otherwise creates a new `project.task` on the first
     `project.project` (or the project named in the
     `southbrook_project_mrp.job_project_id` ir.config_parameter
     override) with `name = "Job: <SO> — <customer>"` and
     `x_southbrook_sale_order_id = self.id`.
   - Back-links any existing MOs for that SO to the new task.
3. **You** (the PM) open the task from **Kitchen Ops → Kitchen Jobs**
   and work through the release gate (lesson 14.4).
4. Optionally, you flip `sb.kitchen.project.state` →
   `in_production` (manual button) to keep the salesperson's view in
   sync. This is a courtesy update — the data model doesn't enforce
   that the two states agree.

**As a developer, tracing a kitchen through the system:**

Start from the customer name on the `partner_id`. Search:

```
sb.kitchen.project where partner_id = X        →  design engagement
sale.order where partner_id = X                →  commercial
project.task where x_southbrook_sale_order_id  →  shop-floor
                  IN (those sale.order ids)
mrp.production where project_task_id           →  MOs
                    IN (those project.task ids)
```

That's the canonical walk. If a piece is missing (e.g. an SO confirmed
without a task created), see "Common mistakes" below.

## Common mistakes + how to recover

**"I confirmed a sale order but no `project.task` was created."**

Three possible reasons, in order of likelihood:

1. **The product on the SO line has no BoM.** The
   `_southbrook_ensure_job` guard is
   `drives_manufacturing = bool(tmpl_ids) and bool(mrp.bom.search_count([
   ('product_tmpl_id', 'in', tmpl_ids)]))`. No BoM = no task.
   Resolution: confirm the product has a BoM (Manufacturing → BoMs),
   then manually call the `_southbrook_ensure_job` method on the SO
   (developer mode → Action menu → Run Server Code, or run via shell:
   `env['sale.order'].browse(<id>)._southbrook_ensure_job()`).

2. **There is no `project.project` record in the database.** The
   `_southbrook_job_project` helper returns the first project it
   finds or the one referenced by the
   `southbrook_project_mrp.job_project_id` ir.config_parameter. If
   both are empty, the helper returns `False` and no task is
   created. Resolution: install `southbrook_project` (whose post-init
   hook ensures project ID 1 exists) or create a project manually.

3. **The override didn't fire.** `_action_confirm` is overridden in
   `southbrook_project_mrp/models/sale_order.py`. If the addon was
   uninstalled, the SO confirms but the task isn't created. Same
   resolution as case 1.

**"I have an `sb.kitchen.project` in state `in_production` but the
linked SO has no `project.task`."**

The Kitchen Workspace state machine is *independent* of the shop-floor
flow. Someone called `action_set_state('in_production')` without
confirming the SO. To recover: confirm the SO (which auto-creates the
task), or manually rewind `sb.kitchen.project.state` to `approved`.
The state machine allows the rewind via the
(`awaiting_customer`, `approved`) transition only — going back from
`in_production` requires a manual write or via cancel + restart.

**"My salesperson keeps editing the kitchen after I've started
production."**

This is a process question, not a system one. The data model lets it
happen because `sb.kitchen.project` and `project.task` are
independently mutable. Convention: once `sale.order.state == 'sale'`
the Kitchen Workspace should be locked (state moved to
`in_production`). Enforce via training, not by extending the model.

**"`sb.kitchen.project` shows a sale order that was cancelled."**

The `sale_order_id` Many2one has no `ondelete` cascade — cancelling a
SO doesn't touch the Kitchen Project. If you need a new quote, create
a new SO and update the Many2one. Don't archive the old Kitchen
Project unless you're sure no field is referencing its `code` for
auditing.

**"I see a `project.task` with no `x_southbrook_sale_order_id`. Is
that an orphan?"**

Not necessarily. The PM can create a task manually on /odoo/project
(stock Odoo behavior). What's *missing* is the orchestration spine —
no SO means the readiness cron skips it, no MOs auto-link, no
mission-control aggregation. The Data Quality Dry Run
(`action_southbrook_data_quality_dry_run` on `project.project`,
documented in lesson 14.7) flags these as `blank_kitchen_project`
warnings.

## What the system is doing behind the scenes

The two-model split is **deliberate** and reflects two different
ownership stages of the same physical kitchen:

- **`sb.kitchen.project` is owned by the design organisation.** Its
  state machine reflects what the *designer + customer* are doing
  (drafting, presenting options, awaiting feedback, approving).
- **`project.task` is owned by the shop.** Its stage reflects what
  the *PM + operators* are doing (cutting, assembling, finishing,
  installing).

A single record that covered both would have to multiplex two state
machines that almost never share fields. Splitting them lets:

- `sb.kitchen.project` carry photos, AI analysis, design options,
  appliances — none of which the shop cares about.
- `project.task` carry MO links, readiness compute, release sign-off
  booleans, install checklist — none of which the designer cares
  about.

The **glue between them is the sale order**, which is canonical for
commercial intent. The auto-create on `_action_confirm` makes the
glue automatic — by the time a confirmed SO exists, the
`project.task` exists too.

The `southbrook_kitchen_workspace` addon depends on
`southbrook_estimating`, not on `southbrook_project_mrp` — so the
design stage doesn't pull in the MRP bridge. The bridge is loaded
separately on the shop side. This is what lets a CE-only test
database run the Workspace without MRP and a Workspace-less PM-only
database run the bridge without Workspace.

The state-machine validation in `sb.kitchen.project.action_set_state`
is *not* mirrored on `project.task` — task stages on `/odoo/project`
are stock Odoo (any-to-any transitions allowed), and the gate that
matters (production release) is enforced via the readiness compute
in `southbrook_project_mrp`, not via stage transitions. See lesson
14.3 for how the gate actually works.

## Quiz (5 questions, applied)

**1.** A new salesperson asks "do I create the `project.task` or
does it create itself?" What do you tell them?

> Neither — you do not, and you should not. The `project.task` is
> auto-created by the `sale.order._action_confirm` override in
> `southbrook_project_mrp` once you confirm the SO. Your work is in
> the Kitchen Workspace + the Order Builder + Confirm. The PM sees the
> task appear under **Kitchen Ops → Kitchen Jobs** moments later.

**2.** You're tracing a problem: the customer says they signed off on
the kitchen but the shop says nothing is in their queue. Which records
do you check, in which order, and what's the diagnosis if the chain
breaks at step 2?

> Step 1: `sb.kitchen.project` — does it exist for this customer? Is
> `state` past `approved`? Step 2: `sale.order` — does it exist? Is
> `state = 'sale'` (confirmed)? Step 3: `project.task` — does one
> exist with `x_southbrook_sale_order_id` = that SO? If step 2 breaks
> (no confirmed SO), the salesperson hit Approve in the Workspace but
> never confirmed the order. Resolution: confirm the SO.

**3.** A developer wants to add a "kitchen complexity score" field.
The score is computed from `appliance_ids.count` + design-option
complexity. Which model do you add it to and why?

> `sb.kitchen.project` — because both source fields
> (`appliance_ids`, `design_option_ids`) live there. Adding it to
> `project.task` would force the compute to walk back through the SO
> to the Kitchen Project, which is the *wrong* direction (the shop
> shouldn't read design-stage fields). If the shop *also* needs the
> score, expose it as a `related` field from the SO Many2one chain:
> `project.task.kitchen_complexity = related='x_southbrook_sale_order_id.kitchen_project_id.complexity_score'`
> (and yes, you'd add the reverse Many2one from SO → Kitchen Project
> in `southbrook_kitchen_workspace` first).

**4.** Your QA dashboard shows an `sb.kitchen.project` in state
`in_production` but the linked SO has been cancelled. Is the data
model broken? What do you do?

> The data model isn't broken — `sale_order_id` has no `ondelete`
> cascade, by design (cancelled SOs are kept for audit). The Kitchen
> Project's state machine is independent and doesn't auto-rewind. To
> reconcile: either rewind `sb.kitchen.project.state` to `approved`
> manually (`action_set_state` only allows valid transitions, so
> you may need to cancel and re-author) or attach a new SO and
> leave the state as-is. Don't archive the Kitchen Project — the
> design-stage history is more valuable than the clean dashboard.

**5.** Two records claim to be "the project." A developer adds a
field to `project.project` thinking it'll show up on the salesperson's
Workspace form. Why doesn't it?

> `project.project` and `sb.kitchen.project` are unrelated models.
> `project.project` is the stock Odoo container that holds
> `project.task` rows. `sb.kitchen.project` is a custom model in
> `southbrook_kitchen_workspace` that has nothing to do with
> `project.project` — there is no `_inherit`, no `_inherits`, no FK.
> The new field will appear on `/odoo/project` (project list/form),
> not on `Sales → Kitchen Workspace → Projects`. To add a field to
> the Workspace form, extend `sb.kitchen.project` in the kitchen
> workspace addon (or a downstream addon that depends on it).

---

## What this lesson does NOT cover

- The state machine on `sb.kitchen.project` in detail (transition
  rules, button wiring) → `southbrook_kitchen_workspace` docs +
  Course 5/Estimating.
- The `sale.order` Order Builder flow that generates the SO →
  lessons 5.2 + 8.4 (`05_estimating_a_quote.md`, `08_quote_to_mo_handoff.md`).
- The auto-creation of `project.task` on SO confirm + MO backlinks
  in detail → lesson 14.5.
- The readiness + release gate on `project.task` → lessons 14.3 + 14.4.
- The Kitchen Workspace OWL UX (design options, appliance layout) →
  Course 5.
- The Hermes recommendation queue that reads from both sides →
  Course 3 (Floor Mgmt).
