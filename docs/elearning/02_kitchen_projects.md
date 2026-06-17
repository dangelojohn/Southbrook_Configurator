---
course: 2 — Production Planning
chapter: 2.1
title: Kitchen Projects vs Sale Orders — Why We Have a Project Layer
duration: 25 minutes
audience: Production Planner (the person who decides what runs when on the shop floor)
prereqs: Native Odoo Sales + MRP basics (Quote -> SO -> MO). Course 1 not required.
custom_modules: southbrook_kitchen_workspace, southbrook_premium_orchestration, southbrook_project_mrp
---

# Kitchen Projects vs Sale Orders — Why We Have a Project Layer

## Who this lesson is for

You're the planner who looks at the queue every morning and decides what
goes to cutting today. Before you can do that you need to know which
records are real customer commitments, which are still being designed,
and which got confirmed at the till but aren't actually ready for the
shop floor. This lesson is about the three records — `sb.kitchen.project`,
`sale.order`, `project.task` — that all describe "the same kitchen" but
at different points in its life. You need to know which one to look at
for which question.

## Where this lives on the site

Sign in at **southbrookcabinetry.space/odoo** with your planner account.
Three menus give you three different views of the same kitchen:

> **Sales -> Kitchen Workspace -> Projects** — the design-stage record
> (`sb.kitchen.project`) the salesperson opens before a quote exists.

> **Sales -> Quotations / Orders** — the standard Odoo sale.order list,
> filterable by stage. Confirmed orders are the ones you care about.

> **Kitchen Ops -> Kitchen Jobs** — the planner-facing kanban of every
> confirmed order's downstream `project.task` spine, grouped by
> readiness decision. **This is your home screen.**

Don't try to plan from the Sales list. The Sales list shows revenue
state, not shop state — an order can be `sale` (confirmed) and still
have zero MOs because the engineering gate hasn't released it. The
Kitchen Jobs board shows shop state and is the only screen that tells
you the truth.

## What your screen shows

On **Kitchen Ops -> Kitchen Jobs** (the kanban) each card represents
one customer kitchen and shows:

- **Job name** (`name` on `project.task`) — composed by the orchestration
  layer as `Kitchen Cabinet Set - <style> (<species>) [<order ref>]`.
  Pulled live from the order's line names at confirmation time.
- **Customer** (`partner_id`) — the same partner as on the sale order.
- **Linked SO** (`x_southbrook_sale_order_id` on `project.task`) — click
  this to jump back to the sale.order. **This is the only reliable
  bidirectional link between an order and its kitchen job.**
- **Install due date** (`install_due_date`) — read from
  `sale.order.commitment_date` at confirmation time, then editable on the
  task. If a customer pushes their install date, change it HERE, not on
  the sale order.
- **Readiness decision** (`readiness_decision`) — `ready` / `review` /
  `blocked`. Computed nightly by the readiness cron from upstream signals
  (BoM exists, drawings exist, tooling reserved, crew assigned). The
  kanban groups cards by this so you see your blocked queue at a glance.
- **Readiness score** (`readiness_score`) — 0-100. Useful for sorting
  "most-ready first" inside a column.
- **Production release state** (`southbrook_production_release_state`) —
  separate from readiness. `ready` means the ENG01 engineer has signed
  off the gate (covered in lesson 2.2). A job can be `readiness=ready`
  and `release=blocked` if the engineer hasn't approved yet.
- **At-risk badge** (`job_at_risk`) — red badge when the readiness score
  and install date together suggest the job won't make its deadline.
  Surfaced by the orchestration's risk compute.

The `sb.kitchen.project` record (the **Sales -> Kitchen Workspace ->
Projects** view) is a different shape. It shows:

- **Project state** (`state` on `sb.kitchen.project`) — `draft` ->
  `designing` -> `awaiting_customer` -> `approved` -> `in_production`
  -> `done`. Transitions are enforced by `VALID_TRANSITIONS` in the
  model, so you can't yank a project straight from `designing` to
  `in_production` even from the API.
- **Theme** (`theme`) — `signature` / `elegance` / `contemporary` /
  `contractor`, matching the configurator series.
- **Design options** (`design_option_ids`) — the alternatives the
  customer is choosing between; exactly one becomes
  `selected_design_option_id`.
- **AI room analysis confirmation** (`ai_analysis_id.confirmed_by_human`)
  — gate that the configurator refuses to run against unless True.
- **Linked sale order** (`sale_order_id`) — populated once the customer
  approves and a quote/order is generated.

## Your daily flow

This is a **start-of-day** lesson — your loop here is "wake up, figure
out what's planning-ready, plan it." Per-job decisions live in the
later lessons.

**1. Start of day (10 min): triage the Kitchen Jobs board.**

- Open **Kitchen Ops -> Kitchen Jobs**.
- Default filter is **Open** (excludes done / cancelled). Leave it on.
- Sort within each readiness column by `install_due_date` ascending
  (tightest deadline first). The kanban remembers your sort.
- Scan the **Blocked** column first — these jobs need something the
  readiness cron decided is missing. Click each card; the chatter shows
  the most recent readiness flip note posted by the
  `_cron_recompute_readiness_all` cron, e.g.
  "Decision: ready -> blocked, Release state: ready -> blocked." That
  tells you what tripped overnight.
- Move to the **Review** column. These need a human decision — usually
  a missing cabinet spec field (door style, wood species, finish) the
  designer hasn't filled in yet. Click the card, look at the
  `x_door_style` / `x_wood_species` / `x_finish` fields. If any are
  blank, ping the designer; don't try to fill them in yourself.
- The **Ready** column is your planning pool. These are the kitchens
  you can release today.

**2. When a designer creates a new project (per-design loop):**

The designer (not you) opens **Sales -> Kitchen Workspace -> Projects**,
hits **Create**, fills in customer + theme, and clicks **Start Designing**.
The project moves `draft -> designing`. You don't see this work; it
hasn't reached your queue yet.

When the customer approves the design, the designer clicks **Customer
Approves**. The project moves `awaiting_customer -> approved` and a
quote is generated. When the customer confirms the quote, **two things
happen in the same transaction**:

- The `sale.order` moves to `sale` (confirmed) state.
- The orchestration layer's `action_confirm` override creates a
  `project.task` spine for this order (job name, install due date,
  partner, customer specs inferred from line names) and stamps
  `x_premium_orchestration_managed = True` on the order.

The new task appears on your Kitchen Jobs board, almost always in the
**Blocked** column at first — because nothing downstream (BoM, drawings,
tooling) is wired yet. It moves to **Review** then **Ready** as the
readiness cron flips it overnight.

**3. End of day (5 min): handoff.**

- Note any `Blocked` cards whose blocker you can't unblock yourself
  (e.g. waiting on the designer, waiting on the customer). Drop a
  chatter note on the task so the next shift sees the context.
- Check the **At Risk** filter — any job whose install date is tight
  and whose readiness is still review/blocked. Escalate to the PM
  before you leave.

## Common mistakes + how to recover

**"I confirmed the sale order in Odoo Sales but no card appeared on
Kitchen Jobs."**

The `action_confirm` override caught an exception during spine creation
and silently logged it — see the order's chatter for a "failed to create
kitchen project.task spine" note. Recovery: open the sale order and run
the **Backfill Kitchen Task** server action (it calls
`action_backfill_kitchen_task` on the order, which is idempotent and
safe to re-run). The card appears the moment the task lands.

**"I edited install_due_date on the sale order and the Kitchen Jobs
card still shows the old date."**

The install date is copied **at confirmation time** from
`sale.order.commitment_date` onto `project.task.install_due_date`, then
the two drift apart. The task is the truth for the shop; the order is
the truth for the customer. Edit the task date if the floor needs to
know, then update the order's commitment date separately so the
customer-facing artifacts (invoice, install confirmation email) stay
honest. This is by design — the planner often needs to negotiate an
internal install date that's distinct from the contract date.

**"A card shows up under a customer whose project isn't even out of
designing yet."**

You're looking at the `Kitchen Jobs` board, which is wired to
`project.task` records, not to `sb.kitchen.project` records. A
`sb.kitchen.project` in `designing` state has no sale order and no
task, so it can't be the cause. What probably happened: the same
customer has TWO kitchens going — the design project (in designing)
and an older one that was already confirmed. Cross-check the SO link
on the card. If it points to an order that ALREADY shipped, the task
should have been archived; use the **Archive Test Users** wizard
admin path (or ask a sysadmin) to clean up.

**"The card is `readiness=ready` and `release=blocked` — what do I
do?"**

Readiness and release are separate gates. Readiness is the cron's view
of "do the upstream artifacts exist?" Release is the ENG01 engineer's
view of "is this safe to send to the floor?" A `ready+blocked` card
means the data is complete but the engineer hasn't approved. That's
lesson 2.2; for now, leave it alone — it's not your decision.

**"I deleted a task by accident and now the order has no spine."**

Don't recreate the task by hand. Open the sale order, run **Backfill
Kitchen Task** from the server action menu. The orchestration code
will re-resolve the project, recreate the task, and re-backlink any
MOs that became orphans when you deleted (the `_backlink_orphan_mos`
helper covers both `sale_line_id.order_id` and bare `origin`
references).

## What the system is doing behind the scenes

You're looking at three records that describe the same kitchen at
three different points in its life:

- **`sb.kitchen.project`** (defined in `southbrook_kitchen_workspace`)
  is the **pre-sale** record. It's where the salesperson and the
  customer work out the design before money changes hands. Its state
  machine is the only one of the three with hard-enforced transitions
  (`VALID_TRANSITIONS` set) — you can't skip a step. Required AI-room
  analysis confirmation gate (`is_ready_for_config_engine`) lives here.

- **`sale.order`** is the **commercial** record. It owns the price, the
  channel pricelist, the customer, and the install due date as a
  contractual commitment. The configurator writes its line items.
  Confirming it triggers `action_confirm`, which fires the override in
  `southbrook_premium_orchestration.sale_order._create_kitchen_project_task`.

- **`project.task`** is the **shop floor** record. It carries readiness
  state, release state, install date, MO backlinks (`production_ids`),
  and the cabinet spec heuristics (`x_door_style`, `x_wood_species`,
  `x_finish`) inferred from the order's product names at confirmation
  time. The orchestration layer also stores `readiness_last_recomputed_at`
  on this record so the cron can sort "stalest first."

The bridge between them: `sale.order.x_southbrook_project_task_id`
(direct, on the live DB only) and
`project.task.x_southbrook_sale_order_id` (the reverse-side link that
exists on every DB, fresh or live). The orchestration's
`_find_existing_kitchen_task` probes both so it works in either DB
shape.

When the readiness cron fires, it walks open kitchen tasks
(`x_southbrook_sale_order_id IS NOT NULL`, state not in done/cancelled),
calls the readiness recompute (`action_recompute_readiness_lines` from
`southbrook_project_mrp`), stamps `readiness_last_recomputed_at`, and
if `readiness_decision` flipped between runs, posts a chatter note on
the task so YOU see the transition tomorrow morning.

## Quiz (5 questions, applied)

**1.** A designer tells you "I just sent quote SO-12455 to the
customer, why isn't it on Kitchen Jobs?" What do you check first?

> The order's state. The Kitchen Jobs board is wired to project.tasks
> created at sale.order.action_confirm — a quote (`sale.order` in
> `draft` / `sent` state) never triggers it. Once the customer
> confirms, the task appears. If they confirmed but no task exists,
> open the order, look at the chatter for a "failed to create kitchen
> project.task spine" note, and run the **Backfill Kitchen Task**
> server action.

**2.** You see a Kitchen Jobs card whose readiness score is 90 (well
into the Ready band) but whose `southbrook_production_release_state`
is `blocked`. The customer is angry because their install date is
next week. Can you release it yourself?

> No. Readiness and release are separate. Release is the ENG01
> engineer's gate (lesson 2.2). What you CAN do: open the task, look
> at the release-gate checklist booleans
> (`southbrook_release_cad_approved`, `_cutlist_approved`,
> `_bom_verified`, `_crew_reserved`, `_equipment_available`) and see
> which one is unchecked — then chase the right person to fix it.
> Don't try to flip the booleans yourself.

**3.** A customer phones in and asks to push their install date from
the 22nd to the 29th. Where do you record the change?

> Update `install_due_date` on the `project.task` (Kitchen Jobs card
> -> open -> change the date). Then ALSO update `commitment_date` on
> the `sale.order` so the contract record stays honest. The two
> fields don't auto-sync after confirmation by design — the planner
> often wants the shop-floor date to differ from the customer
> contract date to build slack.

**4.** A designer asks "what's the difference between the sb.kitchen.project
'in_production' state and the project.task being released to production?"

> The `sb.kitchen.project.state = in_production` is the SALES-side
> record that the kitchen has crossed from quoted/approved into
> manufacturing — it's set by the **action_release_to_production**
> button after the customer commits. The project.task release state
> is the SHOP-side gate (ENG01 engineering approval). They typically
> agree but are independent on purpose, because you can have a
> project in production for accounting while the engineer hasn't yet
> approved a specific MO in the spine.

**5.** You open a task and see the chatter line "Decision: review ->
blocked, Release state: ready -> blocked." What just happened, and
what do you do?

> Last night the readiness cron re-ran and an upstream artifact went
> missing (a BoM was deleted, an MO was cancelled, a tooling
> reservation expired). The release state ALSO flipped to blocked,
> which means the engineer's previous approval no longer applies.
> Open the task, look at the readiness-line breakdown (cad / cutlist
> / bom / crew / equipment), identify which one tripped, and chase
> the owner of that artifact. Once it's restored, the next cron tick
> (within 30 minutes) will recompute and flip the card back if it's
> truly resolved.

---

## What this lesson does NOT cover

- The ENG01 release gate (what the engineer actually checks and how
  the planner releases through them) -> lesson 2.2.
- Bottleneck-aware scheduling once a job is released -> lesson 2.3.
- The 6 nightly crons that drive readiness, MI re-fire, and analytics
  -> lesson 2.4.
- How the MI engine produces the recommendations the production
  manager acts on -> lesson 2.5.
- Native Odoo sale.order lifecycle, partner setup, and pricelist
  resolution -> Odoo's own training.
- Designer-side workflows (creating design options, recording
  customer approvals, AI room analysis) -> lesson 4.4 / Course 4.
