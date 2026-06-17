---
course: 2 — Production Planning
chapter: 2.5
title: Reading the MI Report — What Counts as a Problem
duration: 25 minutes
audience: Production Planner (the person who acts on Manufacturing Intelligence findings before the floor does)
prereqs: Lessons 2.1-2.4. Lesson 2.4 in particular — you should know what the MI refire cron does.
custom_modules: southbrook_manufacturing_intelligence, southbrook_premium_orchestration, southbrook_kitchen_mrp
---

# Reading the MI Report — What Counts as a Problem

## Who this lesson is for

You're the planner who's seen the MI Status badge on an MO turn red
and wants to know whether to escalate, reroute, or ignore. The MI
engine surfaces checks at three severities (blocker / warning / info)
across six categories (cut / production / assembly / install / cad /
hardware). Not all of them are emergencies; some are deliberately
chatty. This lesson teaches you to triage MI output in the time you
have before you have to make a decision.

There's no "P0 / P1 / P2" priority field in the underlying schema —
the MI engine uses `severity` (blocker / warning / info) and the
planner's mental model maps that onto P0/P1/P2 the same way: blockers
hold up the floor (P0), warnings need a planner decision before
release (P1), info goes on chatter for the audit trail (P2). When
this lesson uses P0/P1/P2 it's the user-side label; when it cites a
field it uses the actual `severity` value.

## Where this lives on the site

For the planner — two surfaces:

> **Southbrook PM -> MI Checks**

The flat list of every `southbrook.mi.check` record. Default filter
is **Blockers**, grouped by **Category**. This is where you start
when something turned red on the Kitchen Jobs board and you want to
see the underlying reasons.

> **Southbrook PM -> MI Production Board**

A list of `sb.production.package` records (one per MO) showing
per-package `x_mi_status` (ok / review / blocked), blocker count,
warning count, and the auto-generated `x_mi_next_action` string —
which is the human-readable "do this first" recommendation.

From inside an MO:

> **Manufacturing -> Manufacturing Orders -> <open one>**

The MO form view has an `x_mi_check_ids` field surfaced in a tab.
That's the per-MO subset of the MI Checks list, scoped to this one
manufacturing order.

For the MI engine's last-run health:

> **Kitchen Ops -> MI Engine Status**

Singleton telemetry — when the refire cron last ran, how many checks
fired, how many milliseconds. Lesson 2.4 covers this in depth.

## What your screen shows

Each row on **MI Checks** carries:

- **Severity** (`severity` on `southbrook.mi.check`) — `blocker` /
  `warning` / `info`. Rendered as a red / amber / blue row decoration.
  Sorts via the computed `severity_rank` field (0/1/2) so the most
  urgent are always first.
- **Category** (`category`) — `cut` / `production` / `assembly` /
  `install` / `cad` / `hardware`. Search defaults group by this so
  similar problems cluster.
- **Name** (`name`) — the check's title, e.g. "Oversized panel",
  "Hardware pricing pending", "Low sheet yield".
- **Production Package** (`production_package_id`) — the
  `sb.production.package` the check is scoped to, when the check
  was raised at package level.
- **Manufacturing Order** (`production_id`) — the `mrp.production`
  when raised at MO level. A check has one or the other, not both.
- **Message** (`message`) — the specific finding text, with numbers
  filled in. E.g. "Side L is 2900 x 600 mm and does not fit a 2440
  x 1220 mm sheet."
- **Recommendation** (`recommendation`) — the engine's suggested
  action, e.g. "Split the part, select a larger sheet, or confirm
  a special-order blank before cutting."

The MI Production Board adds the per-package rollup:

- **MI Status** (`x_mi_status` on `sb.production.package`) — `ok` /
  `review` / `blocked`. Computed from the severities of the linked
  checks: any blocker -> blocked, any warning (no blocker) -> review,
  otherwise ok.
- **MI Blockers** (`x_mi_blocker_count`) — count of blocker-severity
  checks on this package. Zero is green.
- **MI Warnings** (`x_mi_warning_count`) — count of warning-severity
  checks. The planner's "stuff I should look at" pool.
- **MI Next Action** (`x_mi_next_action`) — the recommendation text
  from the most-urgent blocker (or warning if no blocker), or
  "Manufacturing intelligence checks are clear" when there's
  nothing pending.

Per-MO mirror fields on `mrp.production`:

- `x_mi_yield_pct` — sheet yield % from the cut summary
  (`panel_area / gross_sheet_area * 100`). Below 45% triggers a
  "Low sheet yield" warning.
- `x_mi_waste_area_m2` — leftover sheet area. Above 0.09 m2 triggers
  a "Reusable offcut" info check (so the floor labels and stores
  the offcut).
- `x_mi_bottleneck_workcenter_id` — the LIVE bottleneck for this
  MO at the moment of the last MI recompute. Different from
  `x_sbk_is_bottleneck` on the workcenter (which is structural —
  see lesson 2.3).

## The check catalog

The MI engine in `southbrook_manufacturing_intelligence/models/
mi_engine.py` generates these checks; they're the entire vocabulary
the planner needs to recognise. Memorise the blockers; warnings and
info are situational.

**`cut` category:**

- **Oversized panel** (blocker) — a cutlist line exceeds the sheet
  envelope (configured via `southbrook_mi.sheet_width_mm` /
  `sheet_height_mm` parameters, default 2440 x 1220 mm). The MO
  cannot proceed until the panel is split, a larger sheet sourced,
  or the cabinet redesigned. **P0.**
- **Grain direction rotation review** (warning) — panel fits the
  sheet only when rotated, and grain direction is something other
  than "no_grain". The floor needs a human-visible grain decision
  before nesting. **P1.**
- **Low sheet yield** (warning) — yield is below 45%. The nesting
  is suboptimal; review duplicate panels and sheet selection.
  Not a release blocker, but worth tightening on. **P1.**
- **Reusable offcut** (info) — projected waste is >= 0.09 m2,
  which is a stockable offcut. Label it (material / thickness /
  grain / usable dimensions) before moving the sheet. **P2.**
- **Missing cutlist** (blocker) — the package has no
  `sb.cutlist`. Generate one via `generate_from_mo()`. **P0.**

**`production` category:**

- Reserved for general production-state notes raised by other
  agents (default category). Few baseline checks in the engine; the
  category exists so the gate-refire cron can attach
  recommendations here without polluting the category-specific
  buckets.

**`assembly` category:**

- **Long shelf requires assembly review** (warning) — a panel with
  "shelf" in its name longer than 900mm. The floor needs to confirm
  support pin spacing, handling, and pin material before release.
  **P1.**

**`install` category:**

- **Tall cabinet install review** (warning) — cabinet height >=
  2400mm. The on-site lift path and ceiling clearance need to be
  confirmed against the install drawings. **P1.**
- **Filler and scribe confirmation** (info) — always raised. The
  floor needs to read the install drawings for filler, scribe,
  and site tolerance — this check exists to force the read. **P2.**

**`cad` category:**

- **CAD not complete** (warning) — `x_cad_status` on the MO is
  anything other than `done`. The MO can proceed if the planner
  accepts the risk, but the FreeCAD render hasn't validated the
  geometry. **P1.**

**`hardware` category:**

- **Missing hardware package** (blocker) — production package has
  no linked `sb.hardware.package`. Generate or link before release.
  **P0.**
- **Empty hardware pick list** (blocker) — the package exists but
  has zero `sb.hardware.package.line` records. **P0.**
- **Hardware pricing pending** (warning) — at least one hardware
  SKU has `x_pricing_pending = True`. The cost rollup is wrong
  until pricing lands; don't lock the customer-facing price.
  **P1.**
- **Hardware not picked** (warning) — the hardware package is
  still in `draft` state instead of `picked`. Move to `picked`
  before sending to assembly. **P1.**

## Your daily flow

**1. Start of day (10 min): triage MI status across packages.**

- Open **Southbrook PM -> MI Production Board**. The default sort
  puts `blocked` packages at the top (via `x_mi_status` decoration).
- Click into each `blocked` package. The `x_mi_next_action` field
  tells you the most-urgent recommendation. Read it; decide whether
  it's a planner action or a chase-someone-else action.
- For each blocked package, open the underlying MO and look at the
  `x_mi_check_ids` tab. Read the actual check messages — the
  next-action text only carries the top finding; there may be five
  more behind it.
- Anything in `review` (any warnings, no blockers) is your "things
  to think about before the day starts" pile. Walk through them;
  they're rarely emergencies but they accumulate if ignored.

**2. Per release decision (the loop):**

When you're about to release an MO to production (lesson 2.2), the
ENG01 engineer ALREADY checked the MI tab during their gate review.
But check it again from your seat:

- Open the MO. Look at `x_mi_status`. If it's `blocked`, do NOT
  release even if the engineer signed off (they might have missed
  a check that fired after their sign-off — the MI cron re-fires
  hourly, see lesson 2.4).
- If `review`, look at the warnings list. For each warning, decide:
  - **`Hardware pricing pending`** — release anyway but lock the
    customer price as "estimate"; flag finance to update the
    invoice when pricing lands.
  - **`Low sheet yield`** — release; the cost is internal, not
    customer-facing. Note for the production manager's weekly
    review.
  - **`Tall cabinet install review`** / **`Long shelf`** — open
    the chatter and confirm the install team has been told.
    Don't release if they haven't.
  - **`CAD not complete`** — usually a hold. Release only with
    the PLM engineer's verbal sign-off on chatter.

**3. End of day (5 min):**

- Open MI Production Board, filter `x_mi_warning_count > 0`. Anything
  that's accumulated more than 3 warnings is technically OK to ship
  but the rework risk is growing. Add a chatter note for the
  morning planner to recheck.
- Open MI Engine Status. Confirm `last_run_at` is within the last
  hour. If the refire cron has stalled, the warnings you're seeing
  may be stale — and the checks you AREN'T seeing may have fired
  since the last run.

## When MI output drives tomorrow's schedule

This is the part that distinguishes a trained planner from someone
ticking off Odoo screens.

When the MI engine raises a per-MO check that's recoverable but
costly (e.g. `Low sheet yield` warning at 38%), the right move is
**not** to immediately re-cut. The right move is to:

1. Note the MO in `x_sbk_planning_notes` on the affected workcenter.
2. Tomorrow morning, when sequencing the day, batch similar-sized
   cabinets together for that workcenter. Edge banding colour and
   panel substrate are the two batchable dimensions; the operation
   template doesn't auto-batch, but you can.
3. Re-fire the MI engine manually via **Kitchen Ops -> MI Engine
   Status -> Run Now** (`action_run_now`) and watch the warning
   count drop on the freshly-batched MOs.

For `Tall cabinet install review` warnings: aggregate them weekly
into a single install-team briefing. The check fires once per MO and
once per day on the refire; the install team doesn't need 14
duplicate warnings, they need a Monday morning summary of "5 tall
cabinets going out this week, here's the lift list."

For the auto-generated recommendation file: when an MI check fires
and the engine writes a recommendation (the `recommendation` field
on `southbrook.mi.check`), that recommendation is the seed for the
production manager's Hermes / Fabio approval queue (Course 3,
lesson 3.2). The planner doesn't approve recommendations — the PM
does — but the planner SEES them on the MI Checks list and decides
whether to act before the PM gets to the queue. That's the planner's
edge: anticipating what the PM will approve and pre-acting on it.

## Common mistakes + how to recover

**"The MO shows `x_mi_status = ok` but I can see a hardware pricing
pending issue on the package."**

The MO-level status and the package-level status are different fields.
`mrp.production.x_mi_status` is computed from MO-level checks (CAD,
production-category items). `sb.production.package.x_mi_status` is
computed from the cut + assembly + hardware + install checks. They
can disagree when the issue lives at the package layer (hardware
typically does). Check the package status, not just the MO status.

**"I opened the MI Checks list and there are 47 rows. Most look
identical."**

The refire cron creates new check rows on each tick; the previous
rows are deleted by `_unlink_existing_checks` before the new ones
are written, BUT only for the scope being refired (per-MO or
per-package). If you're seeing 47 rows, either (a) you're looking
at 47 different MOs each with a couple checks, or (b) a partial
recompute left stale rows. The list view's grouping by category +
package_id collapses duplicates visually; try the group view.

**"`x_mi_yield_pct` shows 0.0 on an MO but the cutlist looks fine."**

The yield compute only writes on a successful cut summary. If the
cutlist was deleted and a fresh recompute fired, the engine writes
0.0 + 0.0 to the MO's yield/waste fields explicitly (per the
"zero-write on missing cutlist" branch in `_recompute_production`).
Recovery: generate a fresh cutlist via the production package's
`generate_from_mo`, then trigger
`action_recompute_manufacturing_intelligence` on the MO. The yield
should populate on the next save.

**"A `Low sheet yield` warning has been on the same MO for three
days but the cut is already done."**

The refire cron re-evaluates on the current cutlist + current state.
Once the cut is done, the warning shouldn't keep firing IF the
cutlist's `state` advanced to `done`. If the cutlist is still in
`draft` state on a finished MO, the cutlist wasn't progressed —
the planner or the operator should have moved it. Open the cutlist,
set state to `done`, the warning clears on the next refire.

**"The MI Next Action text is generic — 'Manufacturing intelligence
checks are clear' — even though I'm staring at a blocker."**

The `x_mi_next_action` field is computed by `_next_action_from_checks`
which takes the first blocker's recommendation, or the first
warning's recommendation, or the "clear" string. If you're seeing
"clear" alongside a visible blocker, the check rows were written
in a different transaction than the next-action field — refresh
the page or trigger a recompute. If it persists, the blocker
might be on the package and the MO field is computed from MO-only
checks (or vice versa).

## What the system is doing behind the scenes

The MI engine is a stateless calculator. Every recompute call
(`_recompute_production(mo)` or `_recompute_package(package)`):

1. Deletes the existing checks scoped to the MO or package via
   `_unlink_existing_checks`.
2. Walks the cutlist (`sb.cutlist.line_ids`) and computes a cut
   summary: panel area, sheet count, yield %, waste, edge band
   length, duplicate groups.
3. Runs the cut checks (oversized / grain / yield / offcut),
   assembly checks (long shelf), hardware checks (missing pkg /
   empty list / pricing / not-picked), install checks (tall
   cabinet / filler).
4. Writes the new checks via `_create_check`.
5. Computes the rollup status (`_status_from_severities`) and
   writes it to the MO or package along with blocker/warning
   counts and the `x_mi_next_action` recommendation text.

Three caches matter:

- **Sheet dimensions** are config-param-driven
  (`ir.config_parameter.southbrook_mi.sheet_width_mm` /
  `sheet_height_mm`, defaults 2440 / 1220). Changing these
  invalidates every oversized-panel and yield check; trigger a
  full re-recompute after a change.
- **Cutlist substrate / grain dir** on each line drive the
  edge-band length math and the duplicate-group bucketing. A wrong
  substrate value on one panel can move yield by 5%.
- **Hardware package state** (`draft` / `picked` / `delivered`)
  is read into the `hardware_summary` dict that drives the
  hardware checks. If a hardware package state is stale, the
  warning persists.

The MI gate refire cron (lesson 2.4 cron 2) is what re-fires gate
checks (`southbrook.mi.check` with `is_gate = True`) against every
in-flight MO every hour. The MI engine state singleton record
records the last run's telemetry; lesson 2.4 walks you through
reading that.

The chain from a fired check to an action: the engine writes a
`southbrook.mi.check` row -> the package or MO's `x_mi_status` is
recomputed -> a Hermes recommendation can be auto-generated from
the check's recommendation text (this wiring is in
`southbrook_hermes`, Course 3 / Course 6). The recommendation is
what the production manager approves; once approved, it can become
a scheduler instruction (re-route, batch differently) or an ECO
draft (Course 4).

## Quiz (5 questions, applied)

**1.** An MO shows `x_mi_status = blocked` with two blocker checks:
"Oversized panel" and "Missing hardware package". The customer's
install is in 4 days. Which do you address first?

> The hardware package, because it's recoverable today — call
> `generate_from_mo()` on the production package and the hardware
> resolves from the catalog in seconds. The oversized panel needs
> either a design change (split the panel) or a sheet-stock change
> (source non-standard 3050x1220); both are multi-day. Solve the
> easy blocker first so you can isolate whether the install date
> is still achievable on just the panel issue.

**2.** You see a warning "Hardware pricing pending" on a package
about to release. The customer has already paid. What's the right
action?

> Release the MO — the warning is a planner-facing concern, not a
> floor blocker. The customer price is already locked. The
> internal cost rollup is incomplete, so the finance team's COGS
> for this MO will be wrong until pricing lands. Drop a note in
> the MO chatter for finance ("hardware price pending at release —
> reconcile when SKU pricing updates") and let the floor proceed.

**3.** Your MI Production Board shows 8 packages in `review` state,
all with the single warning "Tall cabinet install review." The
install team is doing a delivery this Thursday. What's the most
efficient action?

> Don't action each MI check individually. Aggregate: open the 8
> packages, list the install dates, and confirm 4 of them are
> for this Thursday's delivery. Compose ONE briefing for the
> install team — lift list, ceiling clearance constraints per
> address. After the team confirms, post on each MO's chatter
> "install team briefed for tall cabinets on YYYY-MM-DD." The
> warning will keep firing on each refire (it's threshold-based,
> not state-based), but the chatter note is the audit trail
> that says "yes, we handled this."

**4.** The MI Engine Status board shows `last_run_at` was 38
minutes ago, but a blocker on one of your MOs has been there
since yesterday. Why isn't the refire cron clearing it?

> Because the underlying issue hasn't been fixed. The refire cron
> re-evaluates checks against current state — it doesn't dismiss
> old findings. If the cutlist still has an oversized panel, the
> "Oversized panel" check fires anew on each tick. The way to
> clear the blocker is to fix the upstream artifact (cutlist line
> width), then either wait for the next refire or click **Run
> Now** on the MI Engine Status form to re-fire synchronously.

**5.** A planner asks "is there a P0/P1/P2 priority on each check?"
What's your answer?

> Not as a stored field — there's `severity` (`blocker` /
> `warning` / `info`) which the user-side reads as P0/P1/P2 by
> convention. Blockers stop release (P0), warnings need a planner
> decision before release (P1), info goes on the audit trail
> (P2). The `severity_rank` field on `southbrook.mi.check` is the
> numeric sort key (0/1/2) but it's not surfaced in the UI. If
> you need to filter by "show me everything P0", filter by
> `severity = blocker` in the search bar.

---

## What this lesson does NOT cover

- The shape of the Kitchen Jobs board where MI status surfaces
  back onto your home screen -> lesson 2.1.
- The ENG01 release gate where the engineer also reads the MI
  checks before signing off -> lesson 2.2.
- Bottleneck scheduling, including how the LIVE bottleneck
  (`x_mi_bottleneck_workcenter_id`) differs from the structural
  one (`x_sbk_is_bottleneck`) -> lesson 2.3.
- The MI refire cron in detail — schedule, last-run reading,
  failure modes -> lesson 2.4, cron 2.
- Course 3 — what the production manager does with the MI
  recommendations once they reach the Hermes / Fabio approval
  queue.
- How MI checks become Hermes recommendations and how those flow
  through the Console -> Course 3, lesson 3.2.
- Authoring new MI checks (the developer-side work) — out of
  scope for any course; refer to the MI engine source under
  `southbrook_manufacturing_intelligence/models/`.
