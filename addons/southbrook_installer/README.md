# Southbrook Cabinet Installer

Phase 1.1 of the SAMI installer build per `~/Downloads/SAMI_ClaudeCode_Prompts.md` (v1).

## What ships in this version (`19.0.1.0.0`)

| Layer | Model / Asset | Status |
|---|---|---|
| Workflow | `southbrook.installer.stage` | 8 seeded stages with exit-gate flags |
| Workflow | `southbrook.installer.phase` | 11 seeded phases with photo gates |
| Per-job | `southbrook.installer.stage.log` | 1:1 with active phases; start/done/skip + photo-gated completion |
| Central | `southbrook.installer.job` | Sequence-numbered, chatter-tracked, gate-checked stage advance |
| Security | 6 groups | Helper ⊂ Lead ⊂ Dispatcher ⊂ Ops Manager; Warehouse + Finance flat |
| Views | Kanban + list + form + search on job, admin views on stage/phase/log | Stage statusbar, photo-gate UX, smart-button phase counter |
| Data | Sequence `INST-<year>-<5-digit>`, 8 stages, 11 phases | Seeded on install |
| Tests | `test_southbrook_installer_job.py` | 5 tests: create + 7-step workflow walk + gate aggregation + photo gate + skip math |

## What is intentionally *not* in this version

| Field | Today | Replaced by |
|---|---|---|
| `delivery_confirmed` | Manual Boolean | Computed from `southbrook.delivery.manifest` in Phase 1.2 |
| `sign_off_received` + `sign_request_ref` | Manual Boolean + Char | `Many2one → sign.request` in Phase 2.3 (sign module is not in this stack today) |
| `closeout_done` | Manual Boolean | Computed from `southbrook.installer.closeout` in Phase 1.3 |
| `is_blocked` | Manual Boolean | Computed from open blocking damage flags in Phase 1.2 |
| REST API | — | `/api/installer/v1/*` extended into `southbrook_api` in Phase 3 |
| Flutter UI | — | Installer-role screens added to `flutter_app/` in Phase 4 |

These placeholders are documented inline in `models/southbrook_installer_job.py` and the manifest description.

## Architecture

### Gate philosophy

Each stage carries **exit-gate** booleans (`gate_require_*`). When `action_advance_stage()` is invoked, every failing gate on the current stage is collected and surfaced together in a single `UserError`. The installer is never asked to submit ten times to discover ten problems.

### 8-stage workflow

```
SCHEDULED        →  PRE_SITE_CONFIRM  →  DELIVERY_RECEIVED  →
INSTALLATION_IN_PROGRESS  →  FINAL_SIGN_OFF  →  CLOSED_OUT  →
COMPLETE  →  INVOICED (terminal)
```

| Stage | Exit gate |
|---|---|
| `SCHEDULED` | — (advances on GPS arrival) |
| `PRE_SITE_CONFIRM` | delivery confirmed |
| `DELIVERY_RECEIVED` | — |
| `INSTALLATION_IN_PROGRESS` | all phase logs done/skipped |
| `FINAL_SIGN_OFF` | builder sign-off received |
| `CLOSED_OUT` | close-out checklist done |
| `COMPLETE` | — |
| `INVOICED` | terminal |

### 11-phase template

`PHASE_01` Site Assessment → `PHASE_02` Layout → `PHASE_03` Uppers → `PHASE_04` Bases → `PHASE_05` Tall → `PHASE_06` Fillers → `PHASE_07` Doors → `PHASE_08` Hardware → `PHASE_09` Lighting (optional) → `PHASE_10` Crown/Trim → `PHASE_11` Final Clean.

Each phase carries `require_photo` + `min_photos`. The per-job `stage.log` enforces the gate at `action_mark_done()` time.

## Install

```bash
# Inside the southbrook-odoo container:
odoo -d southbrook -i southbrook_installer --stop-after-init
```

## Test

```bash
odoo -d southbrook --test-tags southbrook_installer --stop-after-init
```

## Security groups

| Group | Read | Write | Create | Unlink |
|---|---|---|---|---|
| `group_sami_installer_helper` | job, log | log | — | — |
| `group_sami_installer_lead` | job, log | job, log | log | — |
| `group_sami_dispatcher` | job, log | job, log | job, log | log |
| `group_sami_warehouse` | job, log | job | — | — |
| `group_sami_finance` | job | — | — | — |
| `group_sami_operations_mgr` | all | all | all | all |

Stage + Phase config is admin-only (Operations Manager).
