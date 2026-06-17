---
course: 14 — Project Module Deep Dive
chapter: 14.4
title: Production Release Fields — The 5 Sign-Off Booleans + the Release State Enum
duration: 30 minutes
audience: Production Planner + ENG01 Engineer + Developer
prereqs: Lesson 14.3 (readiness compute); Course 2 lesson 2.2 (release gate run by ENG01); Course 12 lesson 12.4 (release queue)
custom_modules: southbrook_project_mrp, southbrook_project, southbrook_premium_orchestration
---

# Production Release Fields — The 5 Sign-Off Booleans + the Release State Enum

## Who this lesson is for

You're ENG01, the engineer who runs the release gate every morning,
and you keep clicking through 12 things on the task form to figure
out why a job is still blocked. Or you're a developer asked "can you
add a sixth sign-off boolean for tariff sourcing?" and you need to
know how the existing 5 interlock. Or you're a planner who wants to
override a release on a critical job and you need to know what
flipping the booleans actually does. This lesson is the *full*
catalogue of release fields on `project.task` — names, owners,
permissions, transitions, and downstream impact.

Course 2's lesson 2.2 introduces the gate. Course 12's lesson 12.4
covers the Release Queue dashboard. This lesson is the underlying
data model + state machine.

## Where this lives on the site

Sign in at **southbrookcabinetry.space/odoo** as ENG01 or as a user
with Project Manager rights.

> **/odoo/project → any project → any task** — opens the task form.
> Scroll past the smart buttons to the "Production Release" group of
> fields (typically in a notebook tab or top-level group).

> **Kitchen Ops → Production Release Queue** — the dashboard of all
> tasks with `southbrook_production_release_state in
> ('blocked', 'review')`. Detailed in lesson 12.4.

> **(task form) → Readiness smart button** — shows the readiness
> drill-down. The Production Release Checklist gate (line 3 of
> ~13) carries the same status + reason as the release state field.

## What your screen shows

Open any kitchen task. The release section shows **5 user-editable
sign-off booleans** plus **2 computed read-only state fields**.

### The 5 sign-off booleans (all owned by `southbrook_project_mrp`)

All five are `fields.Boolean(string="…", tracking=True)` on
`project.task`. `tracking=True` means every flip is logged to the
chatter with `(who, when, old → new)`.

| Field name                                  | UI label                | Default | Owner                       |
|---------------------------------------------|-------------------------|---------|-----------------------------|
| `southbrook_release_cad_approved`           | CAD Approved            | False   | `southbrook_project_mrp`    |
| `southbrook_release_cutlist_approved`       | Cutlist Approved        | False   | `southbrook_project_mrp`    |
| `southbrook_release_bom_verified`           | BoM Verified            | False   | `southbrook_project_mrp`    |
| `southbrook_release_crew_reserved`          | Crew Assigned / Reserved| False   | `southbrook_project_mrp`    |
| `southbrook_release_equipment_available`    | Critical Equipment Avail.| False  | `southbrook_project_mrp`    |

They're user-editable on the form. Permission to flip them is
governed by the **stock Project ACL** (Project Manager group:
`project.group_project_manager` can write all of them; Project User
can read but not write). The `southbrook_project_mrp` manifest
explicitly does NOT touch ACL/security
(`security/ir.model.access.csv` only grants access to the new
custom models — `southbrook.project.job.template`,
`southbrook.project.readiness.line`, etc. — not to additional fields
on `project.task`).

**TBD:** there is no Southbrook-specific group for "release authority"
in the addon. If you want a tighter "only ENG01 can flip CAD-approved"
ACL, that's a product gap — see the README's "Guardrails respected"
section in `southbrook_project/README.md`.

### The release state + reason (computed, read-only)

| Field name                                  | Type      | Owner                       |
|---------------------------------------------|-----------|-----------------------------|
| `southbrook_production_release_state`       | Selection (ready / review / blocked / info) | `southbrook_project_mrp` |
| `southbrook_production_release_reason`      | Char      | `southbrook_project_mrp`    |

Compute method: `_compute_southbrook_production_release`. Dependencies
(from the `@api.depends` decorator):

- `southbrook_site_measurement_status`
- All 5 release sign-off booleans listed above
- `job_cad_status` (read from linked MOs)
- `southbrook_specs_complete` (the Cabinet Specs roll-up)
- `production_count`
- `components_available`
- `workorder_count`
- `unscheduled_workorder_count`
- `crew_gap`
- `equipment_blocked`
- `job_install_due`

The compute calls `_southbrook_missing_production_release_items` which
walks **12 checks**:

1. **Final site measurements** — `southbrook_site_measurement_status
   in ('received', 'waived')`
2. **CAD approved** — `southbrook_release_cad_approved == True` OR
   the linked MO `job_cad_status` string contains "done"
3. **Cutlist approved** — `southbrook_release_cutlist_approved == True`
4. **Door/finish/hardware specs** — `southbrook_specs_complete == True`
   (the 4-field Cabinet Specs roll-up — see lesson 14.3)
5. **BoM verified** — `southbrook_release_bom_verified == True`
6. **Linked MOs** — `production_count > 0`
7. **Components available** — `components_available == 'ready'`
8. **WOs generated** — `workorder_count > 0`
9. **Schedule work orders** — `unscheduled_workorder_count == 0`
10. **Crew assigned/reserved** — `not crew_gap` OR
    `southbrook_release_crew_reserved == True`
11. **Critical equipment available** — `not equipment_blocked` AND
    `southbrook_release_equipment_available == True`
12. **Install due date confirmed** — `job_install_due != False`

If the missing-items list is empty, `state = "ready"` and
`reason = "Production release checklist is complete."` Otherwise,
`state = "blocked"` and `reason = "Missing <comma-separated list>."`

Note: the compute uses only **two values for state — "ready" or
"blocked"** — even though the Selection allows four (ready / review /
blocked / info). The "review" and "info" values are reachable only
via the alias compute (`_compute_phase1_operational_context`) for the
generic `readiness_decision` field. So if you write a domain like
`[('southbrook_production_release_state', '=', 'review')]` against
this specific field, you'll get an empty set in practice.

### Auxiliary state on the task

These are not "release" fields strictly but the compute reads them:

- `southbrook_site_measurement_status` (Selection: pending / received /
  waived, default pending, tracking=True). Owned by
  `southbrook_project_mrp`. User-editable.
- `southbrook_specs_complete` (Boolean, computed). Owned by
  `southbrook_project_mrp`. True when all 4 required cabinet specs are
  set (see lesson 14.3).

## Your daily flow

**As ENG01 running the release gate (morning, ~30 min for a normal day):**

1. Open **Kitchen Ops → Production Release Queue**.
2. Cards in the "Blocked" lane are your queue. Sort by
   `install_due_date` ascending — earliest install first.
3. Open the first blocked card. Look at the
   `southbrook_production_release_reason` value — it lists the
   missing items in checklist order.
4. For each missing item:
   - **Final site measurements** → if the install crew has measured,
     set `southbrook_site_measurement_status = 'received'`. If it's
     a re-order of a known cabinet, set it to `'waived'`.
   - **CAD approved** → review the CAD package. If approved, flip
     `southbrook_release_cad_approved = True`. The chatter will
     record (you, now, false → true). Alternative: have the linked
     MO's `job_cad_status` set to "done" (this is upstream and
     covers the field automatically).
   - **Cutlist approved** → review the cut spec sheet. Flip
     `southbrook_release_cutlist_approved = True`.
   - **Door/finish/hardware specs** → not yours to fix; bounce to
     the salesperson if missing.
   - **BoM verified** → open the linked MO's BoM tab. Spot-check
     the parts list. Flip `southbrook_release_bom_verified = True`.
   - **Linked MOs / WOs generated / scheduled** → not yours to fix;
     bounce to the production planner.
   - **Components available** → not yours; bounce to procurement.
   - **Crew assigned/reserved** → if a crew exists but not on MOs/WOs,
     flip `southbrook_release_crew_reserved = True` (overrides the
     `crew_gap` flag).
   - **Critical equipment available** → if a workcenter has an open
     maintenance ticket but the equipment is still usable, flip
     `southbrook_release_equipment_available = True` (overrides
     `equipment_blocked`).
   - **Install due date confirmed** → set the MO's
     `x_sbk_install_due_date` (this propagates to the task via
     `job_install_due`).
5. When all 12 items clear, the release state flips to "ready" and
   the task moves out of your queue. The chatter logs the
   transition (and the readiness cron posts a flip note within 30
   min — see lesson 14.3).

**As a planner overriding a release:**

You can shortcut the gate by flipping the 5 sign-off booleans
yourself if you have Project Manager rights. **Don't.** The chatter
is permanent and your signature is on every transition. Use the
override only when:

- You're authorising a job to start production despite a known soft
  blocker (e.g. equipment is technically blocked by a 1-day
  preventative maintenance ticket but you're fine running it the
  hour before).
- ENG01 is unavailable and the install date is tomorrow.

The system trusts the booleans; flipping them un-blocks the gate.
There's no second-stage approval (TBD — could be a product
enhancement if "release authority" needs to be tighter).

**As a developer:**

If you're adding a sixth sign-off boolean (e.g.
`southbrook_release_tariff_sourced` for items with tariff exposure):

1. Add the field to `project_task.py` in `southbrook_project_mrp`
   with `tracking=True`.
2. Add it to the `@api.depends` of
   `_compute_southbrook_production_release`.
3. Add it as a check inside
   `_southbrook_missing_production_release_items`.
4. Add it to `_southbrook_production_release_evidence` so the drill-
   down shows its state.
5. Add it to `_southbrook_production_release_next_action` so the
   first-missing-item lookup table has a recommended action.
6. Add it to the view (`southbrook_project_mrp/views/project_task_views.xml`)
   in the Production Release notebook page.

Don't reorder the existing checks — operators have built mental
models around the current order.

## Common mistakes + how to recover

**"I flipped all 5 booleans and the state is still 'blocked'."**

5 of the 12 checks are booleans you control. The other 7 are
upstream conditions (specs, MOs, WOs, components, install due
date, equipment, crew). Read the `_reason` string — it lists what's
still missing. Common: `southbrook_site_measurement_status` still
'pending' (the booleans don't cover it), `job_install_due` blank
(needs to be set on the MO, not the task), `southbrook_specs_complete`
False (a cabinet spec is empty).

**"The chatter shows I flipped CAD approved, then 30 minutes later
it un-flipped to False."**

The boolean doesn't auto-reset — but the compute that *reads* it
will return "blocked" if some OTHER check fails, and the release
state will flip back to blocked. The boolean is still True, the
state is just computed from the *full* checklist. Open the form and
read the reason; the boolean isn't the problem.

**"I want to revert a release sign-off — can I just flip it back to
False?"**

Yes. Flip and save; chatter logs the revert. The release state will
re-evaluate. Be aware that downstream work may have started against
"ready" — e.g. the planner may have already moved WOs to "in
progress" based on your sign-off. Reverting the boolean doesn't
unwind shop-floor activity.

**"A boolean stays True after I duplicate a task."**

`tracking=True` doesn't imply `copy=False`. Duplicating a task
carries over the sign-off booleans. **This is wrong** — a copied
task should start from scratch. **TBD:** consider adding
`copy=False` to all 5 release sign-off fields in
`southbrook_project_mrp/models/project_task.py`. Workaround for now:
after duplicating, manually reset the 5 booleans.

**"The release state shows 'ready' but I never approved anything."**

The 5 booleans aren't the only sources for the 12 checks. CAD
approval (check #2) is satisfied if EITHER the boolean OR the linked
MO's `job_cad_status` contains "done" — so an upstream MO that PLM
marked CAD-done auto-satisfies the gate without you flipping the
boolean. Similarly, "Crew" (check #10) is satisfied if EITHER
`crew_gap == False` (MOs/WOs have users assigned) OR the boolean
override. The booleans are *overrides*, not the only source of truth.

**"My release state still says 'blocked' even after fixing
everything visible. The reason says 'Missing Components available'."**

`components_available == 'ready'` only when EVERY linked MO has
`reservation_state == 'assigned'`. One MO that's still 'waiting' or
'partially_available' blocks the gate. Open the MOs (smart button) and
check the per-MO reservation state.

## What the system is doing behind the scenes

The release state is a **pure function of 12 inputs** — no state
machine, no persisted enum, no transition graph. Every read of the
field re-evaluates the 12 checks and returns the result. This is by
design: the gate is *idempotent*, so the cron sweep (which runs the
compute every 30 min as part of
`action_recompute_readiness_lines`) can't get the state wrong, and
two operators editing the same task at the same time can't desync
the gate.

The 5 sign-off booleans are persisted (regular `fields.Boolean`)
and `tracking=True` means every write goes to `mail.tracking.value`
which the chatter renders. The 5 are the **only persisted state** of
the gate; everything else is computed.

`_southbrook_production_release_next_action` is a small lookup
table that maps the *first* missing item to a recommended-action
string:

```python
{
    "Final site measurements": "Confirm final site measurements before release.",
    "CAD approved": "Approve CAD before releasing production.",
    "Cutlist approved": "Approve the cutlist before releasing production.",
    "Door/finish/hardware specs": "Confirm cabinet specs before releasing production.",
    "BoM verified": "Verify the BoM against the released cutlist.",
    "Linked MOs": "Link or create manufacturing orders for this kitchen job.",
    "Components available": "Resolve component shortages before release.",
    "WOs generated": "Generate work orders from the linked MOs.",
    "Schedule work orders": "Schedule work orders before advancing this job.",
    "Crew assigned/reserved": "Assign or reserve crew for critical operations.",
    "Critical equipment available": "Confirm critical equipment is available.",
    "Install due date confirmed": "Confirm the install due date before release.",
}
```

This is what feeds the `next_best_action` field on the task form
(which shows the *single* most important next step). The other 11
missing items, in checklist order, are summarised in the
`southbrook_production_release_reason` Char.

The Production Release Checklist gate is **one of 13 gates** in the
overall readiness algorithm (see lesson 14.3). Its verdict is
BLOCKED if `state != "ready"` AND READY otherwise. Because it's a
blocker gate (not a warning), it contributes 25 points of penalty
when not ready AND clamps the score to ≤65. So a task with the
release checklist still open *cannot* score above 65 regardless of
how clean everything else is.

The relationship to downstream MO creation: there's no hard
foreign-key check that blocks MO creation when release_state ==
"blocked". MOs are created on SO confirm regardless. The release
state is a **signal to the planner** that the task isn't yet ready
to *start* — but it doesn't prevent the MOs from existing. This is
deliberate: procurement may need to start ordering long-lead-time
parts even before the release gate clears.

## Quiz (5 questions, applied)

**1.** ENG01 flips all 5 sign-off booleans on a task to True. The
release state stays "blocked" with reason "Missing Components
available, Install due date confirmed." What does ENG01 do?

> Neither of those is owned by ENG01. "Components available" requires
> all linked MOs to be `reservation_state = 'assigned'` — bounce to
> procurement to confirm POs/stock. "Install due date confirmed"
> requires the upstream MO `x_sbk_install_due_date` to be set — bounce
> to the planner or sales rep who owns the install schedule. ENG01's
> work is done; the task can't release until those two clear.

**2.** A new release sign-off is being added for "tariff sourcing
verified". Where, in code, does each piece go?

> Field declaration: `southbrook_project_mrp/models/project_task.py`
> as `fields.Boolean(... tracking=True)`. Add to the `@api.depends`
> of `_compute_southbrook_production_release`. Add to the
> `_southbrook_missing_production_release_items` walker. Add to
> `_southbrook_production_release_evidence` (so the drill-down
> shows it). Add to `_southbrook_production_release_next_action`'s
> lookup table. Add to the form view at
> `southbrook_project_mrp/views/project_task_views.xml`. No ACL or
> security changes needed.

**3.** A task's release_state is "ready" but ENG01 hasn't flipped
the CAD-approved boolean. Bug or feature?

> Feature. Check #2 (CAD approved) is satisfied if EITHER
> `southbrook_release_cad_approved == True` OR the linked MO's
> `job_cad_status` string contains "done". A PLM engineer can mark
> CAD done upstream and the gate auto-clears without needing ENG01
> to flip the boolean. The two paths exist because CAD approval
> sometimes happens at the MO level (per cabinet) and sometimes at
> the task level (per customer job) depending on the shop's flow.

**4.** You duplicate a task to create a sister job. You notice the
new task already has `southbrook_release_bom_verified = True`
inherited from the original. Why is this risky and how do you fix it?

> The duplicate carries the original's release sign-offs because
> `copy=False` isn't set on the booleans. Risky because the chatter
> on the *new* task doesn't show who originally signed off (it shows
> the duplication action only), and the new task may shortcut its
> own release gate based on the *original's* approvals. Fix:
> manually reset all 5 booleans (and `southbrook_site_measurement_status`)
> on the new task before working it. Long-term: add `copy=False` to
> all 5 fields in `project_task.py` (TBD per this lesson's "Common
> mistakes" item).

**5.** A planner says "I authorised this job for production but the
score still shows 65 — what gives?" Score caps notwithstanding —
what's the *most likely* cause?

> The Production Release Checklist gate is contributing a 65 cap
> because `southbrook_production_release_state != "ready"`. The
> planner authorised "the job" (verbally or via comment) but
> didn't actually flip the persisted booleans that the compute
> reads. Resolution: open the task → release group → flip the
> remaining booleans → save. The state will recompute to "ready",
> the cap clears, the score recomputes (typically jumping into the
> 85-95 range).

---

## What this lesson does NOT cover

- The full readiness algorithm and 13-gate waterfall → lesson 14.3.
- The site measurement workflow (when to mark received vs waived) →
  Course 1 lesson 1.7 (Reading a Cut Spec from PLM).
- The CAD status field on `mrp.production` (`job_cad_status`,
  upstream of the release gate) → Course 4 PLM lessons.
- Component availability + procurement loop → Course 2 (Production
  Planning) + native Odoo Inventory.
- The Install Readiness state field
  (`southbrook_install_readiness_state`) and the 7-item install
  checklist — separate from production release. See the
  `_compute_southbrook_install_readiness` compute, lesson 12.x.
- The Hermes / Fabio recommendation queue that consumes release state
  → Course 3 lesson 3.2.
