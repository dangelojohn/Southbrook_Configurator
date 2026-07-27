# OdooIQ Factory Intelligence Engine — v1.0 Technical Specification

> **Status:** Draft 1 — 2026-07-10
> **Purpose:** The bridge between product strategy and Claude Code agent execution. Every section is written to be built from.
> **Scope:** Odoo-native (Community) v1.0. A thin vertical slice that proves the entire product thesis end-to-end on one real factory (Southbrook = tenant zero).
> **Doctrine:** CE-native LGPL, owned code, no OPL-1 vendor dependency (`openvalue mrp_sfc_*` is a reference/replacement target, not a runtime dependency). AI is the *interface*, not the *engine*.

---

## 0. What already exists (verified against the repo 2026-07-10)

The build is mostly *assembly + generalization*, not invention. Verified assets to reuse:

| Asset | Location (verified) | Role in v1.0 |
|---|---|---|
| Calendar-aware daily capacity | `southbrook_mrp_kitchen_workcenters/models/southbrook_capacity_day.py` (`southbrook.capacity.day`) | Feeds available-vs-loaded per (workcenter, day). **Reuse.** |
| Duration formula engine | `…/southbrook_kitchen_operation_template.py:232` `compute_expected_duration()` | Baseline estimate before calibration. **Reuse.** |
| Panel actuals | `southbrook_panel_twin/models/` (`sb.panel`, `sb.panel.cycle`, `sb.machine.event`) | Actual-time capture → calibration input. **Reuse.** |
| WO variance fields | `…/mrp_workorder.py` (`x_sbk_kitchen_expected_min`, `x_sbk_variance_min`, actual/expected cost) | Ready-made estimate-vs-actual signal. **Reuse.** |
| Slip/snapshot tracking | `southbrook_mrp_pm/…` (`sbk_initial_date_planned_start`, `sbk_slipped_days`, `southbrook.shop.daily`) | Date-churn + on-time signals. **Reuse.** |
| Bottleneck fields | `…/mrp_workcenter.py` (`x_sbk_is_bottleneck`, `x_mi_bottleneck_workcenter_id`, congestion level) | Risk weighting in scheduler. **Reuse.** |
| MI gate engine + cron pattern | `southbrook_manufacturing_intelligence/models/mi_engine.py`, `mi_check.py` | Pattern to mirror for the audit refresh cron. **Reuse pattern.** |
| AI advisor | Hermes Fabio sidecar + Gemini-2.5-pro, `/hermes/v1/ask`, recommendation queue (draft→ready→approved→applied) | The advisor layer — already production-ready. **Reuse.** |
| Greedy scheduler (reference) | `~/Downloads/openvalue/mrp_sfc_scheduling_engine` — `mrp.scheduling.run.action_run()` | **OPL-1, not installed in repo.** Mirror the `scheduling.run` *pattern*; build CE-native. Do **not** depend on it. |

**Correction to prior audit:** `southbrook_schedule_whatif` does **not** exist. The scenario/what-if engine is a **build**, not a reuse.

---

## 1. Product thesis

**Category:** Manufacturing Intelligence Layer for Odoo. *Not* an AI scheduler, *not* an APS replacement, *not* an MES.

**One-line positioning:**
> *Odoo tells you what exists. OdooIQ tells you what will happen and what to do next.*

**Core promise, by persona:**
- **Owner:** "Understand whether your factory schedule can be trusted, improve it systematically, and know what commitments you can safely make."
- **Production manager:** "Explain *why* the factory is late and *what actions* will recover it."
- **Sales / dealer:** "Promise realistic delivery dates instead of guessing."

**The wedge (why this sells where 'AI scheduling' doesn't):** SMB manufacturers have ERP data but no operational-intelligence layer. We do not try to out-schedule Siemens Opcenter. We sit on top of the ERP the customer already runs and turn its data into a *delivery-confidence + explanation + data-health* product.

**Positioning guard:** Never sell on "we schedule better" — that invites an algorithm bake-off against existing Odoo scheduling addons (`openvalue mrp_sfc`, Enterprise MPS). Sell on **delivery confidence, explanation, and data health**, which none of them have.

**The moat is not OR-Tools.** Anyone can call OR-Tools. The moat is the **Factory Learning Graph** (§6): a per-tenant model of how *that* factory really behaves, accumulated from actual-vs-predicted history. It compounds and is not copyable.

---

## 2. Ideal Customer Profile (ICP)

The serviceable target is narrower than "cabinet shops on Odoo." **Must have:**

- ✅ Odoo Manufacturing (MRP) installed and *actively used*
- ✅ 5+ work centers
- ✅ Routings enabled (operations with times)
- ✅ 50+ manufacturing orders / month
- ✅ Owner complains about delivery promises
- ✅ Scheduling decisions currently made in spreadsheets / email

**Best verticals:** cabinet manufacturers, custom furniture, woodworking, metal fabrication, industrial assembly.

**Avoid:** job shops with no routing discipline; companies using Odoo only for invoicing/inventory; pure inventory users. (For these the audit correctly returns "you're not using MRP" — nothing to schedule.)

**Commercial note:** target price ~$500/mo/shop (validate). Acquisition motion = the Factory Intelligence Audit (§4) as a low-friction, read-only "find out how reliable your factory really is." Retention = the delivery-confidence + calibration engine they can't leave without losing their trained model.

---

## 3. Data model

New addon: **`odooiq_factory_intelligence`** (LGPL-3, `depends: ['mrp']`; soft-integrates with Southbrook addons when present but does **not** require them). All new models namespaced `oiq.*`.

### 3.1 Audit / reliability (§4)
- **`oiq.factory.audit`** — one health-analysis run. Fields: `date`, `readiness_level` (1–5, computed), `structural_score` (0–100), `behavioral_score` (0–100, null until history), `horizon_days`, `state` (draft/complete), `summary_text`.
- **`oiq.factory.audit.finding`** — one detected issue per run. Fields: `audit_id`, `signal_code` (see §4), `tier` (structural/behavioral), `severity` (info/warn/blocker), `title`, `detail`, `affected_count`, `recommended_action`, `expected_improvement` (low/med/high).

### 3.2 Shadow scheduling (§5)
- **`oiq.schedule.run`** — a shadow scheduling pass (mirrors the `mrp.scheduling.run` pattern, CE-native). Fields: `date`, `horizon_days`, `algorithm` (edd_greedy), `state`, `makespan_min`, `predicted_late_count`, `notes`. **Read-only** w.r.t. Odoo — never writes `mrp.production` dates.
- **`oiq.schedule.slot`** — proposed assignment. Fields: `run_id`, `production_id`, `workorder_id`, `workcenter_id`, `seq`, `planned_start`, `planned_finish`, `predicted_complete`, `late_risk` (0–100), `vs_odoo_delta_min`, `vs_actual_delta_min` (backfilled).

### 3.3 What-if scenarios (§5.4 — BUILD, does not exist)
- **`oiq.scenario`** — a non-destructive what-if. Fields: `name`, `base_run_id`, `mutation_json` (add order / overtime / Saturday shift / rush job), `state`, `result_completion_start`, `result_completion_end`, `confidence_label`, `delta_summary`.
- Execution invariant: run inside a DB savepoint; apply mutations to in-memory/temp state; solve; capture KPIs; **roll back all live mutations**. A test must assert zero net writes to `mrp.production` after a scenario run.

### 3.4 Calibration — the Factory Learning Graph (§6, the moat)
- **`oiq.completion.observation`** — one actual-vs-predicted record per completed WO. Fields: `workorder_id`, `production_id`, `product_id`, `product_family`, `operation_category`, `workcenter_id`, `estimated_min`, `actual_min`, `ratio` (actual/estimated), `context_json`, `delay_reason` (optional, reuse downtime reason taxonomy).
- **`oiq.calibration.factor`** — learned multiplier. Fields: `scope` (operation_category | workcenter | product_family | composite), `key`, `multiplier` (median ratio), `sample_count`, `confidence` (fn of sample size + variance), `last_recomputed`. Feeds both the scheduler's duration estimates and the delivery estimator.

### 3.5 Delivery confidence (§4-late / §7)
- **`oiq.delivery.estimate`** — computed per MO. Fields: `production_id`, `completion_start`, `completion_end` (a **range**, never a false point), `prediction_quality` (low/med/high), `historical_accuracy_pct`, `accuracy_window_days`, `sample_count`, `basis_text`.

**Field-name caution for the implementing agent:** confirm exact v19 field names on `mrp.workorder` (`duration_expected`, `duration`), `mrp.production` (`date_start`, `date_finished`, `date_deadline`, `create_date`), `mrp.routing.workcenter` (`time_cycle_manual`, `time_mode`, `workcenter_id`), and `mrp.workcenter` (`resource_calendar_id`, `time_efficiency`, `capacity`) before coding.

---

## 4. Reliability scoring algorithm

**Output framing (psychology matters):** never a bare "42%." Always a **Readiness Level (1–5)** + a *fast, visible improvement path*. A low score shown to a prospect mid-evaluation must read as "here's the ladder up," not "this product is broken."

### 4.1 Two tiers

**Structural signals — available Day 1** (config + current-state; no history required):

| Code | Signal | Detection |
|---|---|---|
| `S1_ROUTING_COVERAGE` | Manufactured products with routings | % of `mrp.bom` (type=normal, manufactured) having ≥1 operation |
| `S2_WC_ASSIGNED` | Operations with a work center | % `mrp.routing.workcenter` rows with `workcenter_id` set |
| `S3_TIME_REALISM` | Operation times look real | flag operations with default/zero `time_cycle_manual`, or suspiciously uniform/round times across distinct products |
| `S4_CALENDAR` | Work-center calendars configured | % workcenters with a non-default `resource_calendar_id` (not implicit 24/7) |
| `S5_CAPACITY` | Capacity / efficiency defined | workcenters with `time_efficiency`/`capacity`/OEE set away from defaults |
| `S6_DATE_AUTHENTICITY` | Dates are commitments, not artifacts | detect the fiction signature `date_deadline ≈ create_date + Σ routing_time`; report % of open MOs with system-generated vs human-set dates |
| `S7_OVERLOAD` | Factory already overloaded | from `capacity.day`: workcenters where Σ`loaded_minutes` > `available_minutes` across horizon |

**Behavioral signals — accrue over 2–4+ weeks** (require history; surface as "locked, unlocking in N days" until enough data):

| Code | Signal | Detection |
|---|---|---|
| `B1_DATE_CHURN` | Planners constantly move dates | compare `sbk_initial_date_planned_*` snapshots vs current; count reschedules/MO |
| `B2_ESTIMATE_ACCURACY` | Standard times reliable | distribution of `x_sbk_variance_min` (actual − expected) per operation category |
| `B3_OVERRIDE_RATE` | Floor ignores the plan | shadow-run sequence vs actual completion order divergence |
| `B4_ON_TIME` | MOs finish by deadline | % MOs with `sbk_slipped_days ≤ tolerance` |

### 4.2 Readiness Levels

| Level | Name | Meaning |
|---|---|---|
| **1** | Blind | Dates fictional, routings/capacity missing. Predictions impossible. |
| **2** | Structured | Routings + work centers exist; times unvalidated; no history. |
| **3** | Observed | Shadow scheduler running; actuals being captured. |
| **4** | Calibrated | Enough history that estimates are learning-corrected; delivery *ranges* defensible. |
| **5** | Predictive | High historical accuracy, tight intervals, advisor-grade commitments. |

Level = min gate across structural completeness (caps at 2–3) and behavioral history depth (unlocks 4–5). Report **the two or three highest-leverage fixes** and their expected improvement — that is the acquisition hook.

### 4.3 Delivery of the audit
Read-only. No writes to `mrp.*`. Refresh via cron (mirror `mi_engine._cron_refire_gates`) + on-demand server action. Renders as a single "Factory Scheduling Readiness" screen.

---

## 5. Shadow scheduling architecture

**Principle:** OdooIQ **observes**, it does **not** control Odoo. It never mutates `mrp.production` planned dates. It computes an alternative and compares.

```
 Odoo planned schedule ─┐
                        ├─► OdooIQ Shadow Engine ─► compare(Odoo, OdooIQ, Actual)
 capacity.day ──────────┘
```

### 5.1 Algorithm (v1.0): capacity-aware EDD greedy
Because setup-cost optimization is **out of scope** (owner decision 2026-07-10), the problem is finite-capacity flow-shop with due dates — no sequence-dependent setups — so a solver is *not* required for v1.

1. Gather ready MOs (state confirmed/progress, components available, approved) — reuse the existing ready-queue filter.
2. Sort by **earliest due date**, tie-broken by risk weight (bottleneck exposure `x_sbk_is_bottleneck`, `x_sbk_priority_level`, slack).
3. Forward-pass: assign each WO to its work center's next free slot from `capacity.day` availability, honoring calendars; roll finish times forward through routing stages (flow-shop precedence).
4. Compute `predicted_complete` per MO; flag `late_risk` where predicted > deadline.
5. Apply **calibration multipliers** (§6) to every duration estimate before scheduling — this is what makes predictions real.

Persist as `oiq.schedule.run` + `oiq.schedule.slot`. Compute `vs_odoo_delta_min`; backfill `vs_actual_delta_min` on MO completion. **This three-way compare (Odoo plan / OdooIQ plan / Actual) is the "now you're learning" moment.**

### 5.2 Runtime
In-process cron + on-demand (greedy is cheap, no setup constraints). **Do not** build a CP-SAT sidecar in v1. Only graduate to OR-Tools-in-a-sidecar if shadow data proves greedy leaves schedulable jobs late — and even then, sidecar only (own container 2GB/1CPU), never in-process on a shared host.

### 5.3 Future API boundary (design, don't build)
Keep the scheduler behind a `SchedulingIntelligence` service interface (`analyze()`, `shadow_schedule()`, `simulate()`, `estimate_delivery()`) so a future non-Odoo connector (SAP/Epicor/JobBOSS/Cabinet Vision) can feed it. **Build the Odoo connector only.**

### 5.4 What-if scenarios (BUILD)
`oiq.scenario` runs the shadow algorithm over a mutated copy of state inside a savepoint (add order / overtime / Saturday shift / rush job), captures completion range + KPI deltas, then rolls back. Answers "Can I promise Sept 15?" as a **range with a quality label**, plus the deltas for each recovery lever.

---

## 6. Calibration engine — the Factory Learning Graph (the moat)

Every completed work order teaches the model how *this* factory really behaves.

```
Product → Operation → Estimated time → Actual time → Delay reason → Correction
```

### 6.1 Capture
On WO completion, write an `oiq.completion.observation` (`estimated_min` from operation template / prior calibration; `actual_min` from `duration` / panel cycle; `ratio`; context; optional delay reason from the downtime taxonomy). Reuse `sb.panel.cycle` where present for machine-accurate actuals.

### 6.2 Learn
Recompute `oiq.calibration.factor` on a cron: for each scope (operation_category, optionally × workcenter × product_family), `multiplier = median(ratio)`, with `sample_count` and a `confidence` that grows with samples and shrinks with variance. Guard against small-N overfitting (require a minimum sample count before a factor influences scheduling; blend toward 1.0 below threshold).

Example learned graph:
```
Painting  → actual multiplier 2.4×
Assembly  → actual multiplier 1.8×
CNC       → actual multiplier 0.9×
```

### 6.3 Feed back
Multipliers correct every duration estimate in the scheduler (§5) and the delivery estimator (§7). Result: routing-estimate accuracy climbs from ~45% (month 1) toward ~85%+ (month 6) **per tenant**. That accumulated, tenant-specific graph is the churn-proof moat.

---

## 7. Delivery confidence

Introduced **only after** calibration has data (Level 4+). Never a fabricated point percentage.

- Output is a **range**: `Sept 15–19`.
- Accompanied by **prediction quality** (low/med/high) and a **defensible accuracy claim**: "Historical accuracy: 86% within 3 days, based on 243 completed work orders."
- Computed from calibrated estimates + `capacity.day` load + the historical completion-error distribution for similar jobs.
- Early tenants (low N) get deliberately **wide ranges that tighten** as history accrues — honesty preserves the credibility the audit built.

`oiq.delivery.estimate` powers both the internal manager view and the customer/dealer promise view (design COMPLETE → materials AVAILABLE → manufacturing 72% → expected completion range → prediction quality).

---

## 8. AI advisor integration

**AI is the interface, the engine is the truth.** Reuse the existing Hermes Fabio + Gemini-2.5-pro stack (`/hermes/v1/ask`, recommendation queue with human-approval gate). Before calibration the advisor would be guessing; after, it *interprets real engine output*.

Responsibilities:
- **Explain lateness:** "Kitchen 417 is 4 days late because paint-booth capacity was exceeded Friday; two earlier jobs consume the booth; material arrives Wednesday."
- **Answer promises:** feed `oiq.scenario` + `oiq.delivery.estimate` → "Recommended completion Sept 18–20; similar kitchens average 18.5 production days; paint booth at 78%; risk medium. Adding a Saturday shift moves it to Sept 15–17."
- **Recommend actions:** surface recovery levers with their date-range deltas into the recommendation queue for human approval.

Every AI answer must cite the underlying engine facts (the numbers come from `oiq.*` records, not the model's imagination). No standalone AI claims.

---

## 9. Southbrook tenant-zero implementation plan

Southbrook is the reference install that produces the first customer story.

| Month | Milestone | OdooIQ capability proven |
|---|---|---|
| **1** | "Your scheduling data health" | Factory Intelligence Audit (§4) live on real Southbrook MRP data; structural signals + readiness level + top fixes |
| **2** | "Shadow scheduler" | `oiq.schedule.run` shadowing the real floor; three-way compare accumulating |
| **3** | "Actual vs predicted" | `oiq.completion.observation` capture running; first behavioral signals unlock |
| **6** | "Factory-specific intelligence model" | Calibration factors mature; delivery ranges defensible; advisor interpreting |

**Prerequisite (blocks credible delivery dates):** fix Southbrook's MO-date fiction — introduce a material-lead-time model and anchor `date_deadline` to real commitments, not `create_date + routing`. Until then, the audit correctly reports Level 1–2 and the delivery estimator stays in wide-range mode.

**Case study outcome:** "Southbrook reduced scheduling uncertainty by turning Odoo manufacturing data into operational intelligence."

### Build sequence (for Claude Code agents)
1. Scaffold `odooiq_factory_intelligence` addon (LGPL, depends `mrp`); models §3.1 + audit signals §4.1 structural tier; readiness screen. *(Read-only, ships value alone — the acquisition wedge.)*
2. Shadow engine §5.1 + `oiq.schedule.run/slot`; three-way compare; behavioral signals §4.1.
3. Calibration §6 (`observation` + `factor` + crons); wire multipliers into the scheduler.
4. Delivery estimate §7; customer/dealer promise view.
5. What-if `oiq.scenario` §5.4; advisor wiring §8.

Each step: end with a smoke test on real Southbrook data + a code review before moving on.

---

## 10. Roadmap to commercial product

- **v1.0 — Odoo-native Factory Intelligence** (this spec): audit → shadow → calibration → delivery confidence → AI explanation. **No machine telemetry, no CNC integration, no digital-twin requirement.**
- **v2.0 — Southbrook advanced reference:** panel genealogy, quality history, cycle learning, machine integrations (DRILLTEQ/HOMAG). Tenant-specific; **off the core product's critical path.** This is where `panel_twin` + the DRILLTEQ roadmap return, as Southbrook's own deep install.
- **v3.0 — Industrial intelligence:** predictive maintenance, autonomous recommendations, multi-machine optimization; and (if market proven) the multi-ERP connectors behind the §5.3 API boundary.

**Guiding discipline:** ship the intelligence layer for Odoo first, prove the customer problem, and resist becoming an MES/APS company before a proven wedge. Keep the API seam; don't build the right side of it yet.
