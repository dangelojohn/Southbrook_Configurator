---
course: 14 — Project Module Deep Dive
chapter: 14.6
title: Task Views + Dashboards — Custom Kanban, Lists, and Search on /odoo/project
duration: 30 minutes
audience: Project Manager (the person who lives on the project surface every day)
prereqs: Lesson 14.1 (architecture); lesson 14.3 (readiness compute — many views surface its fields)
custom_modules: southbrook_project, southbrook_project_mrp
---

# Task Views + Dashboards — Custom Kanban, Lists, and Search on /odoo/project

## Who this lesson is for

You're the PM who looks at the same kanban board four hours a day and
wants to know what every badge, color, and column means — so you can
read the board faster. Or you're a developer about to extend a view
and need to know which inherit chain to insert into without breaking
the existing layout. This lesson catalogues every Southbrook view
inherit on `project.task` (and a few on `project.project`), what each
one adds, what the search filters mean, and the mobile considerations.

## Where this lives on the site

Sign in at **southbrookcabinetry.space/odoo**.

> **/odoo/project** — the stock entry. The project kanban tile shows
> `southbrook_top_level_task_count` (when the corrected kanban is
> activated; see below) instead of stock `open_task_count`.

> **/odoo/project → any project** — the task kanban grouped by
> `stage_id`. Kanban cards are decorated with Southbrook badges
> (At Risk, ECO, Rush, Urgent).

> **/odoo/project → any project → List view** — the corrected list
> with Southbrook priority + material + SO ref + readiness columns
> as optional toggleable columns.

> **/odoo/project → any project → Search bar** — extended with
> Southbrook quick filters (Rush, Urgent) and Group-By options
> (Southbrook Priority, Material / Species).

> **Kitchen Ops → Production Release Queue** — a separate window
> action filtered to tasks where
> `southbrook_production_release_state in ('blocked', 'review')`.
> Owned by `southbrook_premium_orchestration` (see Course 12).

## What your screen shows

### The form (inherited views)

Two addons extend the task form:

**`southbrook_project`** (`views/project_task_views.xml`):
- ID: `view_project_task_form_inherit_southbrook`
- Inherits: `project.view_task_form2`
- Adds a "Cabinetry Specs" notebook page (after stock Description tab)
  with `x_southbrook_material_species`, `x_southbrook_unit_count`,
  `x_southbrook_priority` (badge widget), `x_southbrook_sale_order_id`,
  and `x_southbrook_hardware_specs`.
- Adds `x_southbrook_priority` as a badge in the header bar
  (decoration-warning for rush, decoration-danger for urgent).
- Adds the class `o_southbrook_project_chatter_bottom` to the form so
  the chatter renders at the bottom (CSS in
  `southbrook_project/static/src/scss/kanban_responsive.scss`).

**`southbrook_project_mrp`** (`views/project_task_views.xml`):
- ID: `project_task_form_mrp`
- Inherits: `project.view_task_form2`
- Adds 12 smart buttons (MOs, ECOs, WOs, Calculations, Readiness,
  POs, Maint., Rework WOs, Remakes, Scrap, Unbuilds, etc.).
- Adds 4 alert banners below the smart buttons:
  - Danger (red): "At risk: <reason>" — when `job_at_risk == True`
  - Warning (yellow): "Spec change in flight: N pending ECO(s)" —
    when `eco_pending_count > 0`
  - Warning (yellow): stage/MO divergence note
  - Warning (yellow): material-at-risk note
- Adds the Production Release section (the 5 sign-off booleans
  plus the computed state — see lesson 14.4).
- Adds the Install Readiness section (the 7-item install checklist).
- Adds embedded lists for: linked MOs, work orders, readiness
  evidence lines (the `southbrook.project.readiness.line` rows),
  scrap, unbuilds, etc.

### The list

`southbrook_project` extends `project.view_task_tree2`
(`view_project_task_list_inherit_southbrook`) — adds 4 optional
columns: `x_southbrook_priority` (badge, shown by default),
`x_southbrook_material_species` (hidden), `x_southbrook_unit_count`
(hidden), `x_southbrook_sale_order_id` (hidden).

`southbrook_project_mrp` adds a separate full list view ID
`project_task_list_readiness` (around line 667 of
`project_task_views.xml`) — includes `cad_cutlist_review_required`,
`install_date_missing`, and readiness fields. This is the list
attached to the Production Release Queue and the
mission-control drill-down actions on `project.project`.

### The kanban

`southbrook_project_mrp` extends `project.view_task_kanban`
(`project_task_kanban_mrp`, line ~821):
- Adds two badges in the kanban card footer:
  - Red "At risk" badge when `job_at_risk == True`
  - Yellow "ECO" badge when `eco_pending_count > 0`
- No swimlane / column reshuffling — the stock `stage_id` swimlanes
  are intact.
- No color-rule changes — Southbrook reads readiness via the
  separate Kitchen Ops kanban (lesson 12.4) rather than recolouring
  the stock board.

**Mobile considerations:** the responsive SCSS in
`southbrook_project/static/src/scss/kanban_responsive.scss` defines
three breakpoints:
- **Desktop ≥1280 px** — all 5 stage columns side-by-side
  (`flex: 1 1 0`, capped at 380 px wide).
- **Tablet 480–1279 px** — horizontal scroll preserved, column
  min-width raised so 1.5 columns visible at start.
- **Phone <480 px** — full-viewport single column, swipe-to-next
  preserved.

Scoped to `.o_kanban_view.o_kanban_project_task` and
`[data-model="project.task"]` so other models' kanbans aren't
affected.

### The search view

`southbrook_project` extends `project.view_task_search_form`
(`view_project_task_search_inherit_southbrook`):
- Quick-filter chips: **Rush** (`x_southbrook_priority = 'rush'`),
  **Urgent** (`x_southbrook_priority = 'urgent'`).
- Searchable Many2one: `x_southbrook_sale_order_id` (type the SO ref
  to filter).
- Searchable Selection: `x_southbrook_material_species`.
- Group-By options: **Southbrook Priority**, **Material / Species**.

`southbrook_project_mrp` adds a separate inherited search view
(`project_task_search_readiness`, line ~736) with additional
filters:
- **Needs CAD / Cutlist** (`cad_cutlist_review_required = True`)
- **Install Date Missing**
- **Manufacturing Readiness: Ready / Review / Blocked** (selection
  on `manufacturing_readiness_state`)
- **Material at Risk**, **Crew Gap**, **Equipment Blocked**, **WC
  Over Capacity**, **Late / At Risk**, **Missing Cabinet Specs**,
  **Install Readiness Review**

### The project-level kanban

`southbrook_project_mrp` declares a project kanban override
(`project_project_kanban_mission_control`, line ~856) — **shipped
inactive by default** (`<field name="active" eval="False"/>`).

When activated (toggle to True in Settings → Technical → User
Interface → Views), the project tile gains:
- A "mission prompt" line based on
  `southbrook_intelligence_prompt` + `_severity` (color-coded:
  green = "Clear", yellow = "Review", red = "Stop").
- 7 stat badges: ready jobs, at-risk jobs, material risk,
  unscheduled WOs, crew gap, equipment blocked, capacity issues.
- An "Open Production Board" button that opens the project's
  manufacturing jobs filtered to `production_count > 0`.

The reason it's inactive by default: the project-level kanban is the
right home for executive triage but is too noisy for the day-to-day
PM who wants to drill into tasks. Activate it for the production
manager's view; leave it off for everyone else.

## Your daily flow

**Morning kanban scan (5 min):**

1. Open **/odoo/project → <your project>**. Kanban view (default).
2. Read the swimlanes left → right: Design & Quote → Cutting &
   Machining → Assembly → Finishing → Delivery & Install. Cards in
   each lane are the tasks at that stage.
3. Scan for red **At risk** badges. Open any you find — the form's
   top-of-page alert tells you why.
4. Scan for yellow **ECO** badges. These don't block — they're a
   heads-up that engineering is changing the spec mid-flight.

**Mid-day priority sort (1 min):**

1. Switch to List view.
2. Click *Group By → Southbrook Priority*. Three groups (Standard,
   Rush, Urgent) appear.
3. Click into the Urgent group — those are your fires.

**End-of-day search:**

1. Search bar → click **Rush** filter. See all Rush jobs across all
   stages.
2. Search by SO number — type the SO ref into the search bar; it
   matches `x_southbrook_sale_order_id`.

**Activating the mission-control kanban (one-time, per user):**

1. **Settings → Technical → User Interface → Views**.
2. Search for `project.project.kanban.southbrook.mission.control`.
3. Toggle `active = True`.
4. Reload `/odoo/project`. Project tiles now carry the mission-
   prompt line + badges.

Do this only for the production manager and yourself. Other users
prefer the stock kanban for routine project management.

## Common mistakes + how to recover

**"The 'At risk' badge isn't appearing on a task I know is at risk."**

The compute `_compute_mrp_status` evaluates `job_at_risk` from MO
state + reservation_state + date_deadline. If the MO's
`date_deadline` is in the future (or null) and `reservation_state`
== 'assigned', the task isn't *at risk* by the system's definition
— even if you know the customer is breathing down your neck. The
red banner is for *manufacturing* risk, not customer risk. For
customer risk, use the `x_southbrook_priority` badge in the header
(Rush / Urgent).

**"The 'Cabinetry Specs' tab doesn't appear on the form."**

Form-inherit failed because another addon altered the notebook
structure. Open developer mode → right-click form → Edit View →
look at the View Metadata for inherits. If a downstream addon
removed the notebook, the Southbrook tab can't anchor. Fix: re-
order view inheritance (lower `sequence` on the Southbrook view) or
adjust the xpath to a more stable anchor.

**"Kanban columns don't fit on my screen."**

The responsive SCSS is breakpoint-gated. If you're between 1024 and
1279 px, you're in the "tablet" range and get horizontal scroll.
This is intentional — at 1024 px there's no way to fit 5 columns
side-by-side without each being <200 px wide, which renders the
cards illegible. Fix: zoom out browser to 90%, OR collapse a
column you don't use (kanban column header → kebab → Fold).

**"Search filter 'Material at Risk' shows the wrong tasks."**

The filter calls `_search_material_at_risk`, which uses the
`_search_boolean_compute` pattern — it searches all tasks and
filters by computed-field value. This is **slow on large
databases** (>10K tasks) because it bypasses the SQL index. If
performance is a problem, materialise the field as
stored=True (TBD — currently all readiness/risk fields are
non-stored, by design to avoid stale-data bugs).

**"The 5-column kanban renders 6 columns at desktop width."**

Someone added a stage. The SCSS doesn't know about stage count —
it just makes every column flex-share at ≥1280 px. With 6 columns
at 1280 px, each gets ~213 px width which is below the
card-readable threshold. Fix: either bump the desktop breakpoint
up (e.g. 1440 px for 6 columns) or fold one column.

**"I activated the mission-control project kanban and now my
project list is too tall."**

The mission-control kanban adds a multi-line prompt + badge row to
each project tile, roughly doubling tile height. If you have 20+
projects in the list, scrolling is painful. Mitigation: filter the
project list to only `Active = True` and `My Projects` so you're
scanning 5-10 tiles, not 50.

## What the system is doing behind the scenes

The Southbrook view layer is **strictly inherit-and-add**, never
replace. Every customisation is a `<record id="..."
model="ir.ui.view">` with an `inherit_id` pointing at a stock view,
and the changes are `<xpath>` blocks (`position="inside"`, `"after"`,
`"before"`, occasionally `"replace"` for a single field reference).

The advantage: stock Odoo upgrades land cleanly because the stock
view IDs (`project.view_task_form2`,
`project.view_task_kanban`, etc.) are stable. The disadvantage:
xpath anchors are brittle — if Odoo renames a field or moves a
notebook, the xpath fails on next upgrade. The brittleness is
managed by:

1. Anchoring on **field names**, not positional indices. E.g.
   `xpath expr="//field[@name='priority']" position="after"`,
   not `xpath expr="//field[3]"`.
2. Anchoring on **notebook pages by name**, not by tab order.
3. Keeping each addon's xpaths small — most of the inherits in
   `southbrook_project` are 5–10 lines, so a broken upgrade is
   easy to repair.

The kanban field-list pattern (the `<field name="..."/>` records
right before `<templates>` in the xpath of
`project_task_kanban_mrp`) is **required** by Odoo — every field
the kanban template references must be in the record's field list
or the renderer can't read it. This is why those views have a
seemingly-redundant block of `<field>` tags before the actual
template changes.

The corrected project-kanban tile field
(`southbrook_top_level_task_count`) is shipped on the
`view_project_kanban_inherit_southbrook` view but **the view is
inactive by default** in `southbrook_project` (Tier 1; see
`views/project_views.xml` line ~80). Activating it (toggle
`active=True` on the view) replaces the inflated open_task_count
on the project tile with the correct subtask-aware count.

The Production Release Queue + Kitchen Jobs dashboards
(under **Kitchen Ops** menu) are owned by
`southbrook_premium_orchestration` and use the *same*
`project.task` records but with different search domains. See
Course 12 lesson 12.4 for those view definitions.

## Quiz (5 questions, applied)

**1.** You want to add a new optional column on the task list — say,
"# Linked POs" (procurement count). Which addon and which view
record do you edit?

> `southbrook_project_mrp`, file `views/project_task_views.xml`,
> view record `project_task_list_readiness` (the readiness-aware
> list). Add a `<field name="procurement_count" optional="hide"/>`
> inside the existing list. Don't add it to
> `southbrook_project`'s `view_project_task_list_inherit_southbrook`
> — that's the polish layer and doesn't depend on MRP fields.

**2.** A user complains the kanban scrolls horizontally on their
laptop. You check — their screen is 1366×768 px. What's happening
and how do you respond?

> 1366 px is in the "tablet 480–1279 px" range *just barely* —
> wait, 1366 > 1279 so they're in the desktop range. Likely cause:
> they have the kanban view at 90% browser zoom or there's an extra
> sidebar (Discuss panel, etc.) reducing effective viewport.
> Confirm: F12 → check `window.innerWidth`. If <1280, the SCSS
> falls back to horizontal scroll, which is correct.

**3.** The "At Risk" red badge is showing on the kanban card but
the task form's at-risk banner isn't. Bug?

> No — same underlying field (`job_at_risk`). The kanban card reads
> the stale-cached value from the list payload; the form re-fires
> the compute on open and may return False if the underlying
> condition changed (e.g. someone reserved the missing component
> just now). Refresh the kanban (browser reload) to re-read.

**4.** You want the search bar to default-filter to "My Rush
Jobs" when a user opens /odoo/project. How do you do that?

> Add a `search_default_southbrook_rush=1` to the action context
> on whichever ir.actions.act_window the user is reaching. For the
> kanban opened from a project, that's the stock
> `project.act_project_project_2_project_task_all`. To customise
> per user, you can't — the action is shared. Better: create a new
> menu item under Kitchen Ops with a custom context
> `{'search_default_southbrook_rush': 1}` pointing at the same
> action. Don't modify the stock action.

**5.** The project kanban tile still shows "8 Tasks" even though
`southbrook_top_level_task_count` is 3 (because 5 are subtasks).
What do you do?

> The corrected kanban view
> (`view_project_kanban_inherit_southbrook` in
> `southbrook_project/views/project_views.xml`) is shipped
> *inactive* (`active="False"`). Toggle it active under Settings →
> Technical → User Interface → Views, search for "project.project.
> kanban.inherit.southbrook", and flip the Active checkbox. The
> kanban tile will then read `southbrook_top_level_task_count`
> instead of `open_task_count`. Caveat: any module that depends on
> the inflated count's appearance on the tile may break — but
> there shouldn't be any.

---

## What this lesson does NOT cover

- The readiness compute that drives many of these badges →
  lesson 14.3.
- The 5 release sign-off booleans + release section of the form →
  lesson 14.4.
- The Production Release Queue + Kitchen Jobs custom Kanban
  surfaces under Kitchen Ops → Course 12 lesson 12.4 +
  Course 2 lesson 2.1.
- Reporting / dashboards at the project level → lesson 14.7.
- The Cabinetry Specs custom fields and how they feed readiness →
  lesson 14.3 (Cabinet Specs gate).
- Mobile-native UX (the mobile responsive SCSS is for the *web*
  client only; Odoo's mobile app uses its own renderer and ignores
  these SCSS files).
