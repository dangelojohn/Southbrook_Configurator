# Southbrook Cabinetry Odoo — Executive Uplift to ≥7/10 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Phase 0 is a hard gate — no Phase 1+ code may be written until Phase 0 answers are recorded in `answers/2026-06-26-executive-uplift.md`.**

**Goal:** Lift every pillar of the live `southbrookcabinetry` Odoo 19 deployment to ≥7/10 against the SAMI Odoo MRP Cabinetry PRD (`/Users/naadmin/Downloads/SAMI_Odoo_MRP_Cabinetry_PRD.md`), so a large kitchen manufacturer's executive (CEO/COO/CFO/VP Ops/CIO) would adopt it without preconditions.

**Architecture:** Gated phased uplift. Phase 0 = scoping questions (blocker). Phase 1 = no-code configuration wins (install + tune). Phases 2–9 = pillar-by-pillar builds, each with its own acceptance test and a verification gate (re-score the pillar; if <7, loop the phase). Phase 10 = composite re-scoring. Each pillar verification step deploys 1–3 fresh agents (Explore for inventory, code-review for diff audit) and a smoke test on the live instance per the standing "always smoke test + code review at end" rule (memory: `feedback_smoke_test_and_review.md`).

**Tech Stack:** Odoo 19 CE/EE (per Phase 0 answer), OCA modules, Southbrook custom addons (25), Postgres 16, QNAP system-docker, alfacore-caddy, cloudflared, Forgejo CI, FreeCAD bridge sidecar, optional frePPLe + EDI sidecar.

## Global Constraints

- Honor `~/southbrook-v19cr/CLAUDE.md` co-development brief (authoritative). Read it before each phase.
- **Never touch router/DHCP/DNS/QNAP-NIC config** (memory: `feedback_no_network_or_router_changes.md`). All ops sizing is host/container-side only.
- **Never use Claude Opus 4.8** for executing agents (memory: `feedback_no_opus_4_8.md`). Default Opus 4.7.
- Every deploy uses the `flock`-wrapped `deploy_to_qnap.sh` recipe (memory: `southbrook_deploy_flock_lock.md`). Never run `-u` against southbrook-odoo while another install is in flight (memory: `qnap_odoo_upgrade_cache_reset.md`).
- After any `deploy_to_qnap.sh` "Failed to load registry" error, verify version via `odoo shell` before re-deploying. **Do NOT restart odoo** (memory: `qnap_postgres_recovery_hazard.md`, `qnap_serialization_failure_transient.md`).
- Every phase ends with (a) end-to-end smoke test on the live instance and (b) `/code-review` pass on the diff. (memory: `feedback_smoke_test_and_review.md`)
- All OWL templates pre-commit-linted via `~/southbrook-v19cr/scripts/lint-owl-expr.py` (memory: `owl_tokenizer_constraints.md`, `southbrook_owl_precommit_hook.md`).
- Every new addon must be added to the Makefile `MODULES` list (CI cold-install gate) AND the prod-module drift detector (memory: `southbrook_cold_install_gaps.md`, `southbrook_prod_module_drift_detector.md`).
- Use `models.Constraint` not `_sql_constraints` (v19) (memory: `odoo19_sql_constraints_deprecated.md`).
- `res.users` uses `group_ids` not `groups_id`; `res.groups` has no `category_id` (memory: `odoo19_res_users_group_ids_rename.md`).
- `ir.cron` no longer has `numbercall` / `doall` fields (memory: `odoo19_ir_cron_schema_change.md`).
- Manual fields (`x_*`) and non-stored computed fields cannot be used in view domains/filters/invisible (memory: `odoo19_view_validation_manual_fields.md`).
- AbstractModel may not be `_inherit`-ed as `models.Model`; use a new `_name` (memory: `odoo19_abstract_model_inherit_trap.md`).
- Live production data — every destructive migration must be preceded by a fresh `backup-odoo.sh` snapshot (memory: `qnap_backup_strategy.md`).

---

## Pillar Scorecard Baseline (2026-06-26)

| Pillar | Today | Target | Pillar phase |
|---|---:|---:|---|
| 1. CPQ / Order entry | 8 | 8 (maintain) | (no work) |
| 2. MES / Shop floor visibility | 5 | 7 | Phase 6 |
| 3. BOM / Routing / Variants | 7 | 7 (maintain) | (no work) |
| 4. MRP / MPS / Finite scheduling | 5 | 7 | Phase 6 |
| 5. PLM / ECO | 7 | 7 (maintain) | (no work) |
| 6. Quality | 3 | 7 | Phase 2 |
| 7. Finance & Canadian compliance | 4 | 7 | Phase 4 |
| 8. HR / Payroll | 3 | 7 | Phase 3 |
| 9. Integrations (SSO/EDI/Homag/3PL) | 3 | 7 | Phase 5 |
| 10. Ops / Reliability / Scale | 3 | 7 | Phase 9 |
| 11. Reporting / Mgmt dashboards | 5 | 7 | Phase 7 |
| 12. CMMS | 5 | 7 | Phase 8 |
| 13. Inventory / WMS | 6 | 7 | Phase 8 |
| 14. Purchasing | 7 | 7 (maintain) | (no work) |

**Composite today:** 4.7/10. **Composite target:** ≥7.0/10 with every pillar ≥7.

---

## Phase 0 — Scoping Questions (HARD GATE)

**No code is written until every answer is recorded in `docs/superpowers/answers/2026-06-26-executive-uplift.md`.**

The 12 questions cover budget, license, infra, partners, and risk authority. They are listed verbatim in the chat reply to the user. After answers land, this section is updated with the locked answers and Phase 1 unblocks.

### Q-01 Edition: Odoo CE or Odoo Enterprise?
Determines whether l10n_ca payroll is the Enterprise version (full CRA T4/ROE/WSIB) or the OCA community payroll stack. Materially affects Phase 3 + Phase 4 task code.

### Q-02 Time/budget envelope
Calendar weeks available + concurrent agent budget (cheap vs unconstrained). Determines whether Phase 5 EDI is built or deferred behind a "planned" stub.

### Q-03 Target customer for the uplift
Southbrook itself growing to 200+ FTE, OR positioning the platform for a SAMI-class licensee (Mattamy/Tridel/Brookfield), OR purely internal demo? Reorders Phases 3–5 priority.

### Q-04 Hosting model post-uplift
Stays on single QNAP, OR provisioning a second QNAP for HA / DR, OR migrating to cloud (Hetzner / Vultr / AWS)? Phase 9 work depends on this.

### Q-05 Live data vs parallel dev DB
Build straight on the live `southbrook` DB with backup safety net, OR clone to `southbrook_dev` for staging? Affects every phase's deploy recipe.

### Q-06 Mattamy / builder EDI
Is there a named builder customer who'd pilot EDI 850/856 (and pay for it), OR is this speculative? Speculative path = build the `southbrook_api` REST adapter only; defer the EDI translator sidecar.

### Q-07 Azure AD tenant
Is there an actual M365 tenant + admin who can register an app for SSO, OR is this conceptual? If conceptual, Phase 5 SSO becomes a documented runbook only.

### Q-08 Homag iX physically present?
Real iX on a shop floor we can talk to, OR integration spec only? Without a real machine, IOT-04 production-count loop is just a unit-tested stub.

### Q-09 CSA A277 in scope?
Is Southbrook pursuing modular cert (the volumetric panelized angle), OR is this strictly cabinetry? CSA A277 records add ~1 week to Phase 2.

### Q-10 frePPLe finite scheduler?
Adopt frePPLe sidecar for finite capacity (richer but adds an OPS surface), OR settle for Odoo native MPS + work-center capacity hard-blocks (lighter)? Phase 6 task code differs.

### Q-11 Pre-existing l10n_ca data
Is there a Canadian CoA / payroll history to migrate, OR clean greenfield seed? Affects Phase 4 migration tasks.

### Q-12 Final acceptance authority
Who signs off "this pillar reached 7/10"? Self-attested vs Southbrook ownership (John) vs an external reviewer? Determines whether Phase 10 gates on a person or on an automated re-score.

---

## Phase 1 — Quick-Win Configuration (no custom code)

**Goal:** Lift Finance to 5, HR to 5, Integrations to 5, Ops to 5, Quality to 5, MRP/MPS to 6 with module installs + odoo.conf tuning only.

**Files:**
- Modify: `~/southbrook-v19cr/Makefile` — add new modules to `MODULES`
- Modify: container `odoo.conf` via deploy recipe
- Create: `~/southbrook-v19cr/docs/superpowers/answers/2026-06-26-executive-uplift.md` (Phase 0 answers, frozen)

**Interfaces:**
- Consumes: Phase 0 answers Q-01 (CE vs EE), Q-04 (host), Q-05 (DB target), Q-11 (l10n_ca seed).
- Produces: a baseline-tuned `southbrook-odoo` capable of supporting Phases 2–9.

- [ ] **Step 1.1 — Fresh backup before any module install**

```bash
ssh admin@192.168.68.108 'export PATH=/share/ZFS530_DATA/.qpkg/container-station/bin:$PATH; bash /share/CACHEDEV3_DATA/scripts/backup-odoo.sh southbrook'
```
Expected: new tar in `/share/CACHEDEV3_DATA/OdooIQ-Backups/southbrook/<DATE>/`. Verify file size matches yesterday's ±20%.

- [ ] **Step 1.2 — Install l10n_ca + companions (CE) or Enterprise payroll (EE)**

If Q-01 = CE:
```bash
# Add to Makefile MODULES:
# l10n_ca, account_accountant, mrp_mps, auth_oauth, auth_saml, quality_control, quality_mrp, mrp_workorder
make deploy-modules MODULES="l10n_ca account_accountant mrp_mps auth_oauth quality_control quality_mrp"
```
If Q-01 = EE:
```bash
make deploy-modules MODULES="l10n_ca l10n_ca_hr_payroll account_accountant mrp_mps auth_oauth quality_control quality_mrp hr_payroll hr_payroll_account"
```

Expected: `ir_module_module` query shows `state='installed'` for all of the above. Verify no upgrade-cache-reset trap by running `docker restart southbrook-odoo` after the install per memory `qnap_odoo_upgrade_cache_reset.md`.

- [ ] **Step 1.3 — Raise worker / cron / memory budget**

Edit container `odoo.conf` via the deploy recipe (NOT directly on host):
```ini
workers = 6                       # was 2
max_cron_threads = 4              # was 1
limit_memory_soft = 1610612736    # was 768 MB → 1.5 GB
limit_memory_hard = 2415919104    # was 1.15 GB → 2.25 GB
db_maxconn = 48                   # was 16
```

Run: `docker restart southbrook-odoo`. Watch for "Circular assets bundle" 500 (memory). If hit, escalate to `docker restart` twice + clear `web.assets_*` from `ir_attachment`.

- [ ] **Step 1.4 — Configure quality_control: 1 seed QCP per work-center category**

```python
# Use odoo shell, not data file (data file would force -i on a v19 in-flight install)
checks = env['quality.point'].create([
    {'name': 'Incoming MDF moisture check', 'product_ids': [...], 'team_id': ...},
    {'name': 'Carcass squareness pre-assembly', ...},
    {'name': 'Door gap tolerance pre-pack', ...},
])
```
Acceptance: each QCP visible under Quality → Control Points and triggers on a test MO.

- [ ] **Step 1.5 — Smoke test + Phase 1 score check**

Smoke: log in, create a sale_order, fire MRP, confirm an MO, see a QCP raise. Time the tablet pageload (target <3s).

Score check (dispatch one fresh Explore agent):
```
Re-score Finance, HR, Integrations, Ops, Quality, MRP/MPS pillars
on the live instance. Each must be ≥5/10.
If any <5, list which Phase 1 step failed.
```

If any <5 → loop back; do not proceed to Phase 2.

- [ ] **Step 1.6 — Commit**

```bash
cd ~/southbrook-v19cr
git add Makefile docs/superpowers/answers/2026-06-26-executive-uplift.md
git commit -m "chore: phase 1 quick-win module install + ops sizing"
```

---

## Phase 2 — Quality Pillar 3 → 7/10

**Goal:** SAMI PRD §4.6 must pass 8 of 10 binary tests. NCR workflow, FPY/Cpk dashboard, supplier defect tracking, photo-on-alert via tablet, and (if Q-09 = YES) CSA A277 record skeleton.

**Files:**
- Modify: `addons/southbrook_manufacturing_intelligence/models/mi_engine.py` — add FPY, defect-rate, Cpk computed fields
- Create: `addons/southbrook_quality/__manifest__.py` — new addon
- Create: `addons/southbrook_quality/models/southbrook_ncr.py`
- Create: `addons/southbrook_quality/models/southbrook_spc_sample.py`
- Create: `addons/southbrook_quality/views/ncr_views.xml`
- Create: `addons/southbrook_quality/views/spc_views.xml`
- Create: `addons/southbrook_quality/security/ir.model.access.csv`
- Create: `addons/southbrook_quality/tests/test_ncr_workflow.py`
- Create: `addons/southbrook_quality/tests/test_spc_sample.py`
- If Q-09 = YES, create: `addons/southbrook_quality/models/southbrook_asbuilt.py`

**Interfaces:**
- Consumes: `quality.alert` (native), `mrp.production`, `stock.production.lot`, `southbrook.production.package` (from southbrook_kitchen_mrp).
- Produces: `southbrook.ncr` model with state machine `draft → quarantine → rework | scrap | release`. `southbrook.spc.sample` with rolling Cpk calc per dimension/work-center.

*(Detailed bite-sized steps with TDD code blocks — to be appended after Phase 0 answers Q-01, Q-05, Q-09 land. Skeleton scaffolded; first test-failing step is `test_ncr_state_machine_transitions`.)*

**Gate:** Re-score the Quality pillar. Must hit ≥7/10. Dispatch one Explore agent with the PRD §4.6 binary test list. If any of QC-01, QC-04, QC-05, QC-10 fails, loop. Also run `/code-review` on the diff.

---

## Phase 3 — HR / Payroll Pillar 3 → 7/10

**Goal:** Bi-weekly Canadian payroll runs on test data. T4 preview valid. ROE generates. WSIB premium calc passes a sanity check. Training matrix wires to `southbrook_elearning_internal`.

**Files (CE path, Q-01 = CE):**
- Create: `addons/southbrook_payroll_ca/` (community-flavored payroll, leverages OCA `payroll_canada` if available; otherwise hand-rolled rule sets)
- Modify: `addons/southbrook_elearning_internal/models/training_matrix.py` — add cert_expiry m2o to hr.employee
- Create: `addons/southbrook_payroll_ca/data/cra_brackets_2026.xml`
- Create: `addons/southbrook_payroll_ca/data/wsib_rates_ontario_2026.xml`
- Create: `addons/southbrook_payroll_ca/tests/test_t4_calc.py`

**Files (EE path, Q-01 = EE):**
- Configure: `l10n_ca_hr_payroll` (no new addon; pure data/config)
- Modify: `addons/southbrook_elearning_internal/models/training_matrix.py`
- Create: `addons/southbrook_hr_ca_config/data/payroll_structures_2026.xml`

**Interfaces:**
- Consumes: `hr.employee`, `hr.contract`, `hr.attendance`, `account.move` (payroll posts).
- Produces: a `hr.payslip` for one test employee with valid CRA T4 line items.

*(Detailed steps appended post-Phase 0.)*

**Gate:** Test payroll run for 3 fictitious employees succeeds; T4 preview shows expected boxes; WSIB premium = 0.95% × insurable earnings (Ontario manufacturing rate). Dispatch one Explore agent to verify; one /code-review.

---

## Phase 4 — Finance Pillar 4 → 7/10

**Goal:** Canadian CoA loaded, HST/GST tax codes active, WIP accounting verified, multi-entity skeleton (Stelumar GC sibling stub or equivalent), CCA depreciation on a sample asset, budget-vs-actual MI tile rendering.

**Files:**
- Configure: `account.chart.template` set to `l10n_ca`
- Create: `addons/southbrook_finance_pack/data/cca_classes.xml` (CCA Class 8/10/29/53 templates)
- Create: `addons/southbrook_finance_pack/data/budget_seed.xml` (a sample budget tied to MI engine analytic dim)
- Modify: `addons/southbrook_manufacturing_intelligence/views/mi_dashboard.xml` — add budget vs actual tile
- Create: `addons/southbrook_finance_pack/tests/test_hst_return.py`
- Create: `addons/southbrook_finance_pack/tests/test_cca_depreciation.py`

**Interfaces:**
- Consumes: `account.move`, `account.asset`, `account.budget`, `account.tax`.
- Produces: HST return preview, 1 valid CCA schedule, 1 budget-vs-actual chart entry.

*(Detailed steps appended post-Phase 0.)*

**Gate:** Re-score Finance pillar ≥7. SAMI PRD FIN-04, FIN-05, FIN-08, FIN-10 must pass. Plus standing smoke + /code-review.

---

## Phase 5 — Integrations Pillar 3 → 7/10

**Goal:** Azure AD SSO working for a real M365 user (if Q-07 = YES). EDI 850/855/856/810 cycle against a stub trading partner (or against the real one if Q-06 surfaces a sponsor). Homag bidirectional production-count + scrap feedback (if Q-08 = YES; else unit-tested stub). 3PL ASN scaffolding.

**Files:**
- Configure: `auth_oauth.provider` row for Azure AD with tenant ID + app reg client ID (from Q-07)
- Create: `sidecar/edi/` — Vercel-deployed translator (mirrors Hermes sidecar pattern from memory `hermes_v1_deploy`)
- Create: `addons/southbrook_edi/` — Odoo-side hooks to consume EDI events via `southbrook_api`
- Create: `addons/southbrook_homag_bridge/` — bidirectional Homag adapter (consumes BTL/MPR output, emits count/scrap events into MO)
- Create: `addons/southbrook_3pl/` — ASN + EDI 214 stub
- Tests: integration tests per adapter; OAuth dance mocked via `requests-mock`

**Interfaces:**
- Consumes: `southbrook.api.endpoint`, `mrp.production`, `stock.picking`, `auth_oauth.provider`, `res.users`.
- Produces: EDI 850 → SO; SO → 855; MO done → 856; invoice → 810. Homag BTL → MO operation; Homag count → mrp.workorder.qty_produced.

*(Detailed steps appended post-Phase 0 answers Q-06, Q-07, Q-08.)*

**Gate:** Dispatch 3 agents in parallel: SSO test, EDI roundtrip, Homag count test. Each binary pass. Then /code-review.

---

## Phase 6 — MES + MRP/MPS Pillars 5 → 7/10

**Goal:** OEE per work-center calculated in real time. Live Bottleneck Report tile on supervisor dashboard. MPS configured for 13-week rolling plan. Finite scheduler — either frePPLe sidecar (Q-10 = frePPLe) OR native MPS + work-center capacity hard-block (Q-10 = native).

**Files:**
- Modify: `addons/southbrook_manufacturing_intelligence/models/mi_engine.py` — add `_compute_oee_per_workcenter`, `_compute_bottleneck`
- Create: `addons/southbrook_mrp_kitchen_workcenters/views/oee_dashboard.xml`
- Create: `addons/southbrook_mps_config/data/mps_seed.xml` (13-week rolling + product-family targets)
- If Q-10 = frePPLe: create `sidecar/freppl-bridge/` + `addons/southbrook_freppl_bridge/`
- If Q-10 = native: extend work-center capacity hard-block via `mrp.workcenter.capacity` model

**Interfaces:**
- Consumes: `mrp.workcenter.productivity`, `mrp.workorder`, `mps.production.schedule` (native), `southbrook.mi.engine`.
- Produces: `southbrook.mi.tile` rows for OEE and Bottleneck.

*(Detailed steps appended post-Phase 0 Q-10.)*

**Gate:** Bottleneck cell must highlight on the dashboard within 60s of a simulated event (a `mrp.workcenter.productivity` row with `loss_id` of type "performance"). Re-score MES + MRP pillars ≥7.

---

## Phase 7 — Reporting / Management Dashboards 5 → 7/10

**Goal:** GM morning dashboard loads on a phone in <3s. Shows: yesterday shift output vs takt, FPY, OTD to builder, WIP value, units planned today, top bottleneck. Material yield viz (W-10). Multi-pane mobile-friendly OWL layout.

**Files:**
- Create: `addons/southbrook_exec_dashboard/__manifest__.py`
- Create: `addons/southbrook_exec_dashboard/static/src/js/morning_dashboard.js` (OWL component — pre-commit-lint via lint-owl-expr.py)
- Create: `addons/southbrook_exec_dashboard/static/src/xml/morning_dashboard.xml`
- Create: `addons/southbrook_exec_dashboard/controllers/api.py`
- Create: `addons/southbrook_exec_dashboard/tests/test_morning_dashboard.py`

**Interfaces:**
- Consumes: `southbrook.mi.engine`, `account.move`, `mrp.production`, `sale.order`, `stock.picking`.
- Produces: `/exec/morning` HTTP route returning JSON aggregated KPIs.

*(Detailed steps appended post-Phase 0.)*

**Gate:** Phone test via `southbrookcabinetry.space/exec/morning` (over cloudflared) — Chrome devtools shows DCL <3000ms on 4G throttling. Re-score Reporting ≥7. /code-review.

---

## Phase 8 — CMMS + Inventory Uplift 5/6 → 7/10

**Goal:**
- CMMS: MTBF/MTTR analytics, breakdown alert blocks affected MOs, vendor service-contract expiry alerts.
- Inventory: landed cost configured, 3PL ASN scaffolding (shared with Phase 5), oversize permit flag on stock.picking.

**Files:**
- Modify: `addons/southbrook_mrp_kitchen_tools/models/maintenance_ext.py` — MTBF/MTTR computed fields
- Create: `addons/southbrook_mrp_kitchen_tools/data/breakdown_block_rule.xml` — server action blocking in-flight MOs on a high-severity breakdown
- Modify: `addons/southbrook_kitchen_mrp/models/production_package.py` — add `oversize_permit_required`, `oversize_permit_state`
- Configure: `stock.landed.cost` rules for European automation parts
- Tests: `tests/test_mtbf_mttr.py`, `tests/test_breakdown_blocks_mo.py`, `tests/test_oversize_flag.py`

**Interfaces:**
- Consumes: `maintenance.request`, `maintenance.equipment`, `stock.picking`, `stock.landed.cost`.
- Produces: `southbrook.mi.tile` for MTBF/MTTR, `oversize_permit_state` on every outbound delivery.

*(Detailed steps appended post-Phase 0.)*

**Gate:** Simulated breakdown triggers correct WO + blocks affected MO. 1 inbound receipt allocates landed cost correctly. Re-score CMMS and Inventory each ≥7. /code-review.

---

## Phase 9 — Ops / Reliability Hardening 3 → 7/10

**Goal:** 99.9% uptime achievable in production hours. Tablet response <2s under load. DR runbook tested. Backup integrity verified. HA Postgres path decided.

**Files:**
- Modify: container compose to add `restart: always`, healthchecks, log limits
- Modify: `~/southbrook-v19cr/scripts/deploy_to_qnap.sh` — flock lock tuning
- Create: `docs/runbooks/dr-restore.md`
- Create: `docs/runbooks/ha-postgres-decision.md` (decide: streaming replication vs pgbackrest vs Patroni)
- Create: `scripts/load_test_tablet.py` — k6-style synthetic load on shop-floor endpoints

**Interfaces:**
- Consumes: container state, postgres state, backup archives.
- Produces: a verified DR restore on a sibling host, a documented load-test pass.

**Constraint reminder:** "Never touch router/DHCP/DNS/QNAP-NIC config" — Phase 9 sizing is purely container/host config.

*(Detailed steps appended post-Phase 0 Q-04 [host model].)*

**Gate:** Run the load-test script. p95 tablet response <2s with 50 concurrent simulated operators. Perform 1 actual DR restore on a secondary host (per Q-04 answer). Re-score Ops ≥7.

---

## Phase 10 — Final Composite Re-Score

**Goal:** Dispatch the same agent fleet used in the 2026-06-26 baseline scoring. Confirm every pillar ≥7 and composite ≥7.0.

**Steps:**
- [ ] Re-run the 3-agent baseline (live SSH inventory + local addon map + PRD requirement matrix)
- [ ] Re-compute the weighted composite using the same weight table from the baseline
- [ ] If any pillar <7, identify which phase failed and loop that phase
- [ ] If composite ≥7.0 and every pillar ≥7, publish the new scorecard to `docs/superpowers/reports/2026-XX-XX-executive-uplift-final.md`
- [ ] Final /code-review on the entire diff since baseline
- [ ] Hand the report to Q-12 acceptance authority

---

## Self-Review (run after each phase completes)

1. **Spec coverage:** Every SAMI PRD §4 requirement assigned to a task? Every Nice-to-Have and Wish-List item explicitly scoped in or scoped out with reason?
2. **Placeholder scan:** No "TBD", "implement later", "appropriate error handling".
3. **Type consistency:** Models / fields / API names match across tasks. `southbrook.ncr` not `southbrook.non_conformance` in one place and `southbrook.ncr` in another.
4. **Cold-install gap check:** Every new addon in Makefile MODULES. Prod drift detector still green.
5. **OWL lint:** Every new template passes `scripts/lint-owl-expr.py`.

---

## Execution Handoff

**This plan stays in PLAN-ONLY mode until Phase 0 answers land.** After answers are recorded in `docs/superpowers/answers/2026-06-26-executive-uplift.md`, the user picks an execution mode:

**1. Subagent-Driven (recommended)** — Fresh subagent per task; review between tasks; fast iteration.

**2. Inline Execution** — Tasks executed in the same session with checkpoints for review.
