# Southbrook Internal E-Learning — Custom Module Track

Internal training materials for Southbrook Cabinetry staff who use the
Southbrook-customized Odoo 19 CE platform every day. **This series covers
only the custom modules** layered on top of Odoo native — the OOTB Odoo
courses (Inventory, MRP, Sales, Accounting) are taught separately by Odoo's
own training site.

**Delivery target:** https://southbrookcabinetry.space/odoo/e-learning
**Module that hosts it:** `website_slides` (Odoo native eLearning) — we
publish these markdown files as slide "Document" content, one file per
slide, grouped into chapters by the course matrix below.

---

## Why a separate track

Native Odoo training covers *the Odoo platform*: how to create a Sales
Order, how to receive stock, how to confirm an MO. It does **not** cover:

- The custom **station types** (cutting / edge_banding / cnc / assembly)
  that drive Southbrook's workcenter scheduling decisions
- The custom **kitchen project** flow (`sb.kitchen.project`) that gates
  whether an MO can be released to production
- The custom **MI (Manufacturing Intelligence) checks** that produce
  recommendations for the Hermes Console
- The custom **PLM** (engineering change orders, cut spec sheets) that
  lives alongside MRP
- The custom **configurator** that turns a customer's design into a quote,
  a BoM, a cut list, and finally an MO

Every lesson here ties a real screen the user sees to the underlying
custom model so the user understands *what's changing in the database* when
they click a button — that's the difference between someone who follows
steps and someone who can recover from a mistake.

---

## Course matrix — Role × Module

The course matrix below organises lessons by the **role** the trainee
plays in the daily flow of a kitchen order. Each cell is one or more
lessons; every lesson lives in its own markdown file under this directory
and is referenced by the file path in the **File** column.

| Role | Daily job | Modules they touch | Course |
|---|---|---|---|
| Edge Banding Operator | Apply edge tape to cabinet panels coming out of CNC | `southbrook_mrp_kitchen_workcenters` | [Course 1: Workcenter Operators](#course-1-workcenter-operators) |
| CNC Operator | Cut panels on the CNC router from the day's cut list | `southbrook_mrp_kitchen_workcenters`, `southbrook_mrp_kitchen_tools` | [Course 1: Workcenter Operators](#course-1-workcenter-operators) |
| Assembler | Build the carcass from cut + banded panels | `southbrook_mrp_kitchen_workcenters` | [Course 1: Workcenter Operators](#course-1-workcenter-operators) |
| Sander / Finisher | Sand and apply finish to assembled cabinets | `southbrook_mrp_kitchen_workcenters`, `southbrook_mrp_kitchen_tools` | [Course 1: Workcenter Operators](#course-1-workcenter-operators) |
| Production Planner | Schedule MOs against workcenters, watch bottlenecks | `southbrook_kitchen_mrp`, `southbrook_mrp_pm`, `southbrook_premium_orchestration` | [Course 2: Production Planning](#course-2-production-planning) |
| Production Manager | Watch MI dashboards, approve Hermes recommendations | `southbrook_manufacturing_intelligence`, `southbrook_hermes`, `southbrook_premium_orchestration` | [Course 3: Floor Management](#course-3-floor-management) |
| Designer / ECO Engineer | Author cut specs, raise engineering change orders | `southbrook_plm`, `southbrook_freecad_bridge`, `southbrook_ai_design` | [Course 4: PLM + Design](#course-4-plm--design) |
| Estimator | Turn a customer requirement into a configured quote | `southbrook_estimating`, `product_configurator*`, `southbrook_hardware_catalog`, `southbrook_configurator_ux` | [Course 5: Estimating + Configurator](#course-5-estimating--configurator) |
| Customer Service | Manage customer-facing portal communications | `southbrook_customer_portal`, `southbrook_dealer_portal`, `southbrook_hermes` | [Course 6: Customer Touchpoints](#course-6-customer-touchpoints) |
| IT Admin / Sysadmin | Maintain the platform, watch backups, approve Hermes recs | `southbrook_premium_orchestration`, `southbrook_os`, `southbrook_api` | [Course 7: Sysadmin](#course-7-sysadmin) |

---

## Course 1 — Workcenter Operators

Frontline factory operators. Each lesson is anchored on **one workcenter
type** because the daily reality of an operator is "I work at the edge
bander, my goal is to keep tape on panels without missing the cut list
deadline." Generic operator lessons go ignored.

| # | Lesson | File |
|---|---|---|
| 1.1 | What is a Southbrook Kitchen Workcenter (5 min orientation, all operators) | `01_workcenters_orientation.md` |
| 1.2 | **Edge Banding Operator** — daily flow on SB-EDGE (HOMAG Edge Bander) | [`01_edge_banding_operator.md`](./01_edge_banding_operator.md) ⭐ sample |
| 1.3 | CNC Router Operator — daily flow on SB-CNC-BORE (Biesse Rover, primary) + CNC02 (ShopSabre, backup) | `01_cnc_router_operator.md` |
| 1.4 | Assembler — daily flow on SB-ASSY (parallel-jobs enabled) + SB-DOOR | `01_assembler.md` |
| 1.5 | Sander / Finisher — daily flow on SAND, PAINT, and CURE (three stations, not one) | `01_finisher.md` |
| 1.6 | Logging downtime — `southbrook_kitchen_workcenter_downtime` (all operators) | `01_logging_downtime.md` |
| 1.7 | Reading a Cut Spec from PLM — what the engineer expects you to follow | `01_reading_cut_spec.md` |

## Course 2 — Production Planning

For the human who sits in front of the Kitchen Ops menu and decides what
runs when. Native MRP is assumed knowledge; these lessons are the
Southbrook deltas.

| # | Lesson | File |
|---|---|---|
| 2.1 | Kitchen Projects vs Sale Orders — why we have a project layer | `02_kitchen_projects.md` |
| 2.2 | The `approved → in_production` gate (run by ENG01) | `02_release_gate.md` |
| 2.3 | Bottleneck-aware scheduling: cutting + edge_banding + cnc | `02_bottleneck_scheduling.md` |
| 2.4 | Premium Orchestration: the 6 nightly crons and what they touch | `02_premium_orchestration_crons.md` |
| 2.5 | Reading the MI report — what counts as a problem | `02_reading_mi_reports.md` |

## Course 3 — Floor Management

| # | Lesson | File |
|---|---|---|
| 3.1 | Manufacturing Intelligence dashboards — at-a-glance shop floor health | `03_mi_dashboards.md` |
| 3.2 | Approving Hermes (Fabio) recommendations from the Console | `03_hermes_fabio_approval.md` |
| 3.3 | OEE per workcenter — what `oee_target` means, when to investigate | `03_oee.md` |

## Course 4 — PLM + Design

| # | Lesson | File |
|---|---|---|
| 4.1 | Engineering Change Orders — when to raise one, what state means what | `04_ecos.md` |
| 4.2 | Authoring a Cut Spec Sheet — what fields drive the operator's job | `04_cut_specs.md` |
| 4.3 | FreeCAD bridge — generating renderings from a configured kitchen | `04_freecad_render.md` |
| 4.4 | AI design assist (Gemini) — when to use, when not | `04_ai_design.md` |

## Course 5 — Estimating + Configurator

| # | Lesson | File |
|---|---|---|
| 5.1 | Configurator basics — attributes, exclusions, construction rules | `05_configurator_basics.md` |
| 5.2 | Building a quote from a kitchen design | `05_estimating_a_quote.md` |
| 5.3 | Hardware catalog — adding non-cabinet line items | `05_hardware_catalog.md` |
| 5.4 | Configurator UX tweaks — Southbrook's UI deltas vs OCA stock | `05_configurator_ux.md` |

## Course 6 — Customer Touchpoints

| # | Lesson | File |
|---|---|---|
| 6.1 | Customer portal — what the customer can see and do | `06_customer_portal.md` |
| 6.2 | Dealer portal — separate from customer portal, scoped to one dealer | `06_dealer_portal.md` |
| 6.3 | Hermes / Fabio recommendation queue from the CS perspective | `06_hermes_cs_view.md` |

## Course 7 — Sysadmin

| # | Lesson | File |
|---|---|---|
| 7.1 | Premium Orchestration — the 6 crons, how to read their last-run state | `07_orchestration_admin.md` |
| 7.2 | Backups — verifying the nightly job ran and the artifacts landed | `07_backups.md` |
| 7.3 | Hermes Console — sysadmin recommendations queue | `07_hermes_sysadmin.md` |

---

## Authoring rules (for whoever writes the remaining lessons)

Every lesson follows the same shape so trainees know what to expect:

1. **Title** — verb-first, role-anchored. `Edge Banding Operator — Your Daily Flow` not `SB-EDGE Documentation`.
2. **Who this is for** — one sentence. Concrete role.
3. **Where it lives in the menu** — exact menu path the user clicks, e.g. *Kitchen Ops → Workcenters → Edge Bander (SB-EDGE)*.
4. **What the screen shows** — list the fields the trainee will see and interact with. Reference the actual model + field name in parentheses so a developer reading the lesson can trace it back to code: `Setup time (default_setup_time_min on mrp.workcenter)`.
5. **Your daily flow** — step-by-step. Use the words the operator uses. "I check the day's queue", not "the user navigates to the work order list view".
6. **Common mistakes + how to recover** — the most valuable section, because it covers what the operator does at 4pm when something has gone wrong.
7. **What the system is doing behind the scenes** — one paragraph, technical. Useful for the curious operator and essential for the supervisor who has to debug.
8. **5-question quiz** — short, applied. "Your CNC operator says SB-EDGE is showing up as 'busy' but you're standing in front of an empty machine — what do you check first?" — not "What is the difference between a work center and a work order?"

Avoid:
- Generic screenshots that go stale on every UI update — describe the screen in words, reference field names
- Long descriptions of Odoo native behavior — link to Odoo's own docs and stay focused on the Southbrook delta
- Sales-y language about how powerful the system is — trainees want to know what to *click*, not why the system is impressive

---

## How to publish (delivery format)

Three paths, in increasing automation:

1. **Manual**: an admin opens `Website → eLearning → Courses`, creates a course per row in the matrix above, then for each lesson creates a slide of type **Document** and pastes the markdown content into the slide body. Fast for one-time setup, but lessons drift from these source files immediately.
2. **Markdown-to-slide importer**: a small Odoo data XML file (one record per lesson, `slide.slide` with `slide_type='document'` and `description` set to the markdown body) that auto-creates courses + lessons on install. Source-of-truth stays in these files; an admin re-installs the data module to refresh. Recommended path.
3. **Fully scripted**: an `xmlrpc` script that reads `docs/elearning/*.md`, parses the front-matter for course / chapter / order, and upserts via the website_slides API. Best for "I edit a markdown file in a branch and the live course updates on merge."

Decision deferred until at least 4 lessons are written and validated against actual user feedback — the format work isn't worth doing until the content shape is settled.

---

## Status

All 29 lessons written, grounded in real model/field names from the
actual addon code. Each lesson follows the format of the edge banding
sample (8 fixed sections, 5-question scenario quiz with blockquote
answers, frontmatter with course/chapter/audience/prereqs/custom_modules).

### Audit findings (raised during authoring — keep these in mind when
reviewing)

The authoring pass surfaced several **product gaps and honest TBDs** the
trainers should know about. These are documented inline in the relevant
lessons but collected here for visibility:

| # | Finding | Lesson | Action |
|---|---|---|---|
| 1 | Workcenter codes EBP01/CNC01/ASM01/etc. don't exist; real codes are SB-EDGE, SB-CNC-BORE+CNC02, SB-ASSY+SB-DOOR, SAND+PAINT+CURE | All Course 1 | Fixed: all lessons now use real seeded codes |
| 2 | OEE has no stored `actual_oee` field; computed on demand from three factor sources | 3.3 | Documented in-lesson; if a stored OEE is wanted, file a ticket |
| 3 | No dealer→customer attribution model; uses native `parent_id` as Phase-1 workaround | 6.2 | Product gap — file a ticket for proper attribution |
| 4 | `_require_dealer` rejects tradesperson channel; dealer portal is dealer-channel only in Phase 1 | 6.2 | Product gap — file a ticket if tradesperson should access |
| 5 | No `team` field on Fabio recs; CS-vs-Production filter is convention only | 6.3 | Product gap — file a ticket for typed routing |
| 6 | In-Odoo backup-staleness recommendation NOT implemented in southbrook_premium_orchestration | 7.2 | Documented; covered by Hermes Console `BackupHealthLoop` until in-Odoo lands |
| 7 | Hermes Console backup sidecar status file (`OdooIQ-Backups/hermes/<file>`) — exact filename not traced | 7.3 | Operator-side detail; trace when next on QNAP |
| 8 | sale.order uses STOCK Odoo states (`draft → sent → sale → done`); the "Estimating/Approval/Confirmed/In-Production" pipeline is overlaid via `southbrook_submitted_date` milestone | 5.2 | Lesson written against real state machine, not the documented one |
| 9 | "BoM Preview tab" referenced in brief doesn't exist; actual notebook page is `kitchen_3d_preview` | 5.2 | Lesson uses real fields (`sb_panel_count`, `sb_door_count`) |
| 10 | FreeCAD bridge reads `_spec_for_bridge` from product-template defaults, not per-MO configurator spec (Phase-1 limitation from source comment) | 4.3 | Already flagged in source — repeated in lesson |
| 11 | Cut spec `_check_single_active` constraint enforces one active spec at a time | 1.7, 4.2 | Documented |

### Per-course completion

| Course | Lessons | Status |
|---|---|---|
| Course 1 — Workcenter Operators | 7 (1.1 - 1.7) | ✅ All written |
| Course 2 — Production Planning | 5 (2.1 - 2.5) | ✅ All written |
| Course 3 — Floor Management | 3 (3.1 - 3.3) | ✅ All written |
| Course 4 — PLM + Design | 4 (4.1 - 4.4) | ✅ All written |
| Course 5 — Estimating + Configurator | 4 (5.1 - 5.4) | ✅ All written |
| Course 6 — Customer Touchpoints | 3 (6.1 - 6.3) | ✅ All written |
| Course 7 — Sysadmin | 3 (7.1 - 7.3) | ✅ All written |
| **Total** | **29 lessons, ~11,000 lines** | ✅ |

### What's next

1. **Review pass by domain experts.** A real edge bander operator should
   read lesson 1.2; a real planner should read 2.x; etc. Catch the
   field/menu inaccuracies the agents couldn't catch.
2. **Pick a delivery format** (manual paste / data XML / scripted)
   per the "How to publish" section above.
3. **File tickets for the product gaps** in the audit table.
