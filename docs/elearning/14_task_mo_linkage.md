---
course: 14 — Project Module Deep Dive
chapter: 14.5
title: Task → MO Linkage — How project.task Connects to mrp.production
duration: 30 minutes
audience: Production Planner + Developer (anyone who's wondered "why is this MO not on my task?")
prereqs: Lesson 14.1 (architecture); native Odoo SO → MO procurement basics
custom_modules: southbrook_project_mrp, southbrook_project
---

# Task → MO Linkage — How project.task Connects to mrp.production

## Who this lesson is for

You're a planner who opens a customer job task and sees "4 MOs" on
the smart button but you can see in Manufacturing that this customer
has 6 confirmed MOs. Or you're a developer asked "why does adding an
MO not auto-link to the task?" and you need to know what the chain
of automatic backlinks actually is. This lesson is the FK direction,
the auto-create rules, the manual repair action, and the upstream
sale.order linkage that anchors everything.

Course 2's lessons treat MOs as a planner primitive. This lesson is
how MOs and tasks find each other.

## Where this lives on the site

Sign in at **southbrookcabinetry.space/odoo**.

> **/odoo/project → any project → any task** — the task form. Smart
> button "MOs" shows `production_count`. Click to open the linked
> MOs list.

> **Manufacturing → Operations → Manufacturing Orders → any MO** —
> open an MO. Field "Customer Job"
> (`project_task_id` on `mrp.production`) is the back-pointer.

> **(task form) → Action → Link MOs from Sale** — manual repair
> action (`action_link_productions_from_sale`) that re-walks the SO
> linkage and links any orphan MOs to the task. Use when procurement
> created MOs after the task was created but they didn't auto-link.

## What your screen shows

The linkage is a **classic One2many / Many2one pair**:

- **`mrp.production.project_task_id`** (Many2one to `project.task`,
  the FK side). Defined by `southbrook_project_mrp/models/mrp_production.py`.
  Indexed. `copy=False`.
- **`project.task.production_ids`** (One2many — reverse pointer).
  Defined by `southbrook_project_mrp/models/project_task.py` at
  ~line 51. Maps to the field above.

So the *MO* knows which task it belongs to (single Many2one), and the
*task* sees all its MOs (the reverse One2many). One task → many MOs;
one MO → at most one task. A typical full-kitchen task has 4–8 MOs
(one per cabinet family + worktop + pantry + appliance trim).

### The upstream linkage: SO → Task

On `project.task`:

- **`x_southbrook_sale_order_id`** (Many2one to `sale.order`) — the
  upstream link to the originating quote/sale order. Owned by
  `southbrook_project`. `ondelete='set null'` (SO cancellation leaves
  the task; the link just goes blank).

The chain is therefore:

```
sale.order (1)  ──◄  project.task.x_southbrook_sale_order_id (∞)
                          │
                          ▼ (reverse — One2many)
                     project.task (1) ──◄  mrp.production.project_task_id (∞)
                                                │
                                                ▼ (FK back to SO line)
                                           mrp.production.sale_line_id  →  sale.order.line.order_id
```

A `mrp.production` knows three things at once:
- Which task it belongs to (`project_task_id`)
- Which SO line generated it (`sale_line_id`) — native Odoo
- Which SO that line belongs to (`sale_line_id.order_id`)

That overlap is *deliberate redundancy* — it means orphan repair
(below) can re-walk the SO chain and re-bind MOs without trusting
the existing (possibly stale) `project_task_id`.

## Your daily flow

**The happy path (zero manual work):**

1. Salesperson confirms a `sale.order` for a kitchen.
2. **At confirm time**, the override
   `sale.order._action_confirm` in
   `southbrook_project_mrp/models/sale_order.py` runs
   `_southbrook_ensure_job`:
   - Checks the order has products with a BoM
     (`mrp.bom.search_count([('product_tmpl_id', 'in', tmpl_ids)]) > 0`).
     If no BoM, skip — the SO is not driving manufacturing.
   - Searches for an existing task with
     `x_southbrook_sale_order_id == self.id`. If found, reuse it.
   - Otherwise creates a new task on the target `project.project`
     (configurable via `southbrook_project_mrp.job_project_id`
     ir.config_parameter, default = first project found) with
     `name = "Job: <SO> — <customer>"`.
   - Writes `project_task_id = task.id` onto every existing
     `mrp.production` whose `sale_line_id.order_id == self.id`
     AND `project_task_id == False`.
3. **For MOs created later by procurement** (the SO confirm triggers
   procurement, which spawns MOs from BoMs over the next minute or
   so), the override `mrp.production.create` in
   `southbrook_project_mrp/models/mrp_production.py` runs the same
   back-link logic on creation:
   ```python
   if mo.project_task_id or not mo.sale_line_id:
       continue
   task = Task.search([
       ('x_southbrook_sale_order_id', '=',
        mo.sale_line_id.order_id.id)], limit=1)
   if task:
       mo.project_task_id = task.id
   ```
   This means MOs created by procurement minutes/hours/days after SO
   confirm still find their way to the right task.

**The unhappy path (you have to repair manually):**

If MOs exist but aren't linked (typical causes in "Common mistakes"
below), open the task and use the `Action → Link MOs from Sale`
button. It runs `action_link_productions_from_sale`:

```python
order = task.x_southbrook_sale_order_id
mos = self.env['mrp.production'].search([
    ('sale_line_id.order_id', '=', order.id),
    ('project_task_id', '=', False),
])
mos.write({'project_task_id': task.id})
```

This walks the SO chain from the task side, finds orphan MOs (those
with no `project_task_id`), and binds them. It will NOT re-bind MOs
already linked to a *different* task — if you need to do that,
clear the wrong link by hand first.

### Completion signals — does one side reflect to the other?

**The task's stage is *not* auto-updated when MOs finish.** The
linkage is for read-time aggregation only. If you finish all the
MOs on a job, the task doesn't auto-flip to "Done" — the PM moves
the stage on `/odoo/project` manually.

What *is* auto-aggregated on the task side from the MOs:

- `production_count` (Integer) — count of linked MOs
- `mo_reference` (Char) — comma-separated MO names
- `mo_product_summary` (Char) — comma-separated product SKUs
- `mo_state_summary` (Char) — readable roll-up like "4 confirmed /
  2 in progress"
- `components_available` (Selection: none / ready / partial /
  waiting) — derived from MOs' `reservation_state`
- `job_industrial_cost` (Monetary) — sum of MOs'
  `planned_direct_cost` (with `industrial_cost` fallback)
- `job_estimated_cost` (Monetary) — sum of `standard_price × qty`
- `job_install_due` (Date) — min of MOs' `x_sbk_install_due_date`
- `job_cad_status` (Char) — unique non-empty values of MOs'
  `x_cad_status`
- `job_next_action` (Char) — first non-empty of MOs'
  `x_mi_next_action`
- `job_at_risk` (Boolean) + `job_risk_reason` (Char) — true if any
  started MO isn't fully reserved or any MO is past `date_deadline`
- `workorder_ids` (Many2many, computed) — all WOs across all MOs
- `workorder_count`, `unscheduled_workorder_count` (Integers)
- Workcenter load, crew, equipment, ECO, material readiness
  rollups — see lesson 14.3's compute catalogue

All of these are **computed, non-stored** on the task. They re-fire
on every read. So a MO completion DOES reflect to the task — the
next time the task is read.

The flow in the other direction (task action triggers something on
the MO) is **minimal**. The task is a read-only lens onto MO state,
not a controller. The one exception is
`action_recompute_readiness_lines` which iterates the task's MOs
and calls `action_recompute_manufacturing_intelligence` on each one
to refresh the MI checks. That's the only "task pushes to MO"
direction in the bridge.

## Common mistakes + how to recover

**"The MOs smart button shows 4 but Manufacturing shows 6 MOs for
this customer."**

Two MOs were created without their `project_task_id` being set.
Most common reason: they were created **before** the SO was
confirmed (manual MO creation), so the
`mrp.production.create` override didn't have a task to bind to.
Less common: the SO override `_southbrook_ensure_job` was bypassed
(direct DB write, or the addon was uninstalled at the time).

Fix: open the task → Action → Link MOs from Sale. The repair
walker binds any orphan MOs whose `sale_line_id.order_id` matches
the task's SO.

**"The MOs smart button shows 0 but I just confirmed the SO."**

If the SO has no products with a BoM, `_southbrook_ensure_job`
skipped task creation (the `drives_manufacturing` guard is False).
If a task DOES exist but production_count == 0, no MOs were
spawned yet — procurement may not have triggered. Check the SO's
"Manufacturing" smart button on the sale order form.

**"A MO is linked to the wrong task."**

The `action_link_productions_from_sale` action won't fix this — it
only binds orphans (`project_task_id == False`). Manual fix: open
the MO → Customer Job field → clear it → save → go to the right
task → Link MOs from Sale (which will now find it).

**"Procurement re-created an MO after I closed the original one,
and the new one isn't linked."**

The `create` override only runs on initial creation. A re-create
(close + new) should go through the create override and link
correctly. If it doesn't, the MO probably has no `sale_line_id`
(some procurement paths don't carry the SO line through). Fix:
manual link via the MO's Customer Job field, or
`Link MOs from Sale` (if the SO line IS set on the new MO).

**"A new task I created manually has no MOs and `Link MOs from
Sale` does nothing."**

`Link MOs from Sale` requires the task to have
`x_southbrook_sale_order_id` set. If you created the task manually
without setting the upstream SO, the walker has nothing to chain
from. Fix: set `x_southbrook_sale_order_id` to the right SO, then
re-run the action.

**"I want to merge two customer jobs into one task."**

Manually clear `project_task_id` on the MOs of one task, then run
`Link MOs from Sale` on the destination task (assuming they share
an SO — which is the only case merging makes sense for). If they
don't share an SO, you can't merge cleanly — the SO linkage is the
identity of the job.

**"The data quality report flagged 'blank_kitchen_project' on an
MO."**

That means `project_task_id` is null on a non-done, non-cancelled
MO. The report is `southbrook.project.data.quality.report`,
triggered by `action_southbrook_data_quality_dry_run` on the
project. Detailed in lesson 14.7. To fix, find the task that
*should* own the MO and run `Link MOs from Sale`, or set
`project_task_id` directly.

## What the system is doing behind the scenes

The linkage is **redundant by design** — three FKs point at the
same SO:

```
project.task.x_southbrook_sale_order_id      → sale.order
mrp.production.project_task_id               → project.task (whose .x_southbrook_sale_order_id is the SO)
mrp.production.sale_line_id.order_id         → sale.order (directly)
```

This redundancy is what makes the orphan-repair logic deterministic.
The walker re-derives the binding from the SO side, ignoring any
stale `project_task_id` it might find.

The `_southbrook_ensure_job` method (in
`southbrook_project_mrp/models/sale_order.py`) is intentionally
idempotent: calling it twice on the same SO doesn't create a
second task. It searches by `x_southbrook_sale_order_id` and reuses
any existing match.

The choice of `x_southbrook_sale_order_id` vs the OCA
`sale_project.sale_order_id` is documented in the
`_southbrook_ensure_job` comment: we deliberately use the
Southbrook-owned field to avoid pulling in the OCA addon's
*auto-service-task creation*, which would create unwanted service
tasks for every SO line.

The bridge **does not depend on `mrp_product_costing`** even
though it reads cost fields (`planned_direct_cost`,
`industrial_cost`). All cost reads use `getattr(..., 0.0)` so a
database without the costing addon installed degrades cleanly to
zero rather than crashing the form. Documented in the manifest:

> mrp_product_costing is NOT depended on (it lives outside this
> repo) — its cost fields are read defensively via getattr.

The `mrp.production.create` override uses
`@api.model_create_multi` and writes the back-link in a single
pass *after* `super().create(vals_list)`. This avoids interfering
with native MO creation (which has a lot of side effects —
reservation, scheduling, etc.) and only adds the binding once the
MO record exists.

Finally — **procurement creates MOs in a background flush**, not
synchronously with `sale.order.action_confirm()`. So at the
moment `_southbrook_ensure_job` runs, the only MOs that exist for
the SO are ones a human created manually pre-confirm. The override
covers BOTH cases: the synchronous bind in `_southbrook_ensure_job`
(catches manual MOs) and the per-MO bind in `mrp.production.create`
(catches procurement-spawned MOs).

## Quiz (5 questions, applied)

**1.** You open a task and see `production_count = 0` but you know
the customer has manufacturing scheduled. Walk the chain — what do
you check, in order?

> (a) Is `x_southbrook_sale_order_id` set on the task? If not, the
> task isn't a kitchen job — it's a hand-created task. (b) Is the
> SO in state `sale` (confirmed)? If not, procurement hasn't fired.
> (c) Does the SO have products with a BoM? If not,
> `_southbrook_ensure_job` skipped task creation (but you have a
> task somehow — likely manual). (d) Are MOs visible from the SO's
> Manufacturing smart button? If yes but `production_count = 0` on
> the task, they're orphan; run `Link MOs from Sale` from the task
> Action menu.

**2.** A procurement run at 14:30 spawned 6 MOs against an SO whose
task was created at 09:00. Did the 6 MOs auto-link?

> Yes, via the `mrp.production.create` override. Each MO at
> creation time runs the search:
> `Task.search([('x_southbrook_sale_order_id', '=',
> mo.sale_line_id.order_id.id)], limit=1)`. The task exists (created
> at 09:00 by `_southbrook_ensure_job`), so the override finds it
> and writes `project_task_id`. No manual action needed.

**3.** A developer asks "why do we have both
`project_task_id` on the MO AND `x_southbrook_sale_order_id` on
the task — isn't that double bookkeeping?" What do you say?

> Yes, deliberately. The MO's `project_task_id` is the *fast*
> lookup for reading rollups (task → MOs via One2many). The
> task's `x_southbrook_sale_order_id` is the *anchor* for orphan
> repair — if the MO link is wrong or missing, the SO link is the
> ground truth we walk back to. The third link
> (`mo.sale_line_id.order_id`) is native Odoo and lets the SO walk
> *its* MOs without going through the task. Three paths to the same
> identity = resilience.

**4.** You manually create an MO from Manufacturing without an SO
line. Does it link to any task?

> No. The `create` override skips MOs with no `sale_line_id`:
> `if mo.project_task_id or not mo.sale_line_id: continue`. The MO
> exists, has no task, and won't appear on any task's smart button.
> To link it manually, open the MO and set Customer Job to the
> right task. If you want it auto-linked, create the MO from the SO
> form (which sets `sale_line_id`) or from a confirmed SO's
> Manufacturing smart-button-driven flow.

**5.** A task shows 6 MOs but 2 of them are for a DIFFERENT
customer. The original SO got merged with another and the bind
went stale. How do you clean up?

> (a) Open each of the 2 wrong MOs, clear `project_task_id` (the
> Customer Job field) — chatter will log who did this and when.
> (b) Find the correct task for those 2 MOs (likely the other
> customer's task) and run `Link MOs from Sale` from that task —
> the orphan walker will pick them up (or if their SO is still the
> wrong one, you'll need to update `sale_line_id` upstream first).
> (c) Run the data-quality dry run on the project to confirm no
> remaining orphans (`action_southbrook_data_quality_dry_run`).

---

## What this lesson does NOT cover

- The `sale.order` state machine, channel pricelists, and quote
  pipeline → Course 5 (Estimating + Configurator).
- The MRP planner's workflow once MOs are linked — bottleneck
  scheduling, WO sequencing → Course 2.
- ECO linkage via `southbrook.eco.bom_id` → Course 4 lesson 4.1
  (Engineering Change Orders).
- The MI check linkage to MOs (`southbrook.mi.check.production_id`)
  → Course 3 lesson 3.1.
- The 5 release sign-off booleans + checklist → lesson 14.4.
- The readiness compute that aggregates over linked MOs → lesson 14.3.
- Project-level rollups of MO counts and costs → lesson 14.7.
