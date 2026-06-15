# Southbrook Premium MRP Orchestration — Design Spec

Codename: *Closing the Loop*

This addon activates the triarchic architecture (analytical / creative / practical) already present
in the `southbrook_*` addon graph. Each component closes a specific data-flow gap identified in the
2026-06-15 audit. See `docs/AUDIT_FINDINGS.md` for the source findings and ranking.

## Phase summary

| Phase | Outcome | Files owned |
|---|---|---|
| 1 — Spine Activation | Project spine on 100% of confirmed SOs; 5 crons firing; MI engine has a body; Kitchen Ops menu surface | `models/sale_order.py`, `models/project_task.py`, `models/southbrook_mi_engine.py`, `data/ir_cron.xml`, `data/server_actions.xml`, `views/menus.xml`, `views/{kitchen_jobs,production_release,install_risk,workcenter_bottleneck,mi_engine,tool_lifecycle}_views.xml`, `wizards/test_user_archive.py` + `_views.xml`, `docs/OPL1_LEGAL_HOLD.md` |
| 2 — Practical-Intelligence Loop | Tool-asset records flowing; consumption ledger debiting on WO finish; cut-spec overrides → automatic ECO proposals | `data/tool_asset_seed.xml`, `models/mrp_workorder.py`, `models/cut_spec_override.py`, `data/eco_proposal_cron.xml`, `views/mrp_workorder_views.xml`, `views/cut_spec_override_views.xml` |
| 3 — Generative + Planning Activation | Gemini real-call wiring; FreeCAD enable + healthcheck; job templates spawn; data quality auto-populates | `models/gemini_activator.py`, `models/freecad_activator.py`, `models/project_task_template_spawn.py`, `models/data_quality_report.py`, `data/job_template_seed_links.xml`, `wizards/gemini_activation*.py/xml`, `wizards/freecad_activation*.py/xml`, `docs/GEMINI_GO_LIVE.md`, `docs/FREECAD_GO_LIVE.md` |

## Cross-cutting principles

1. **No new dependencies outside the existing `southbrook_*` graph.** Everything is Odoo 19 CE + already-installed modules.
2. **Strict file ownership.** Each implementation agent owns specific files; no two agents touch the same file. The manifest pre-declares every path.
3. **Idempotent data.** All XML data files use `noupdate="0"` only where safe; tool-asset and cron seeds use `noupdate="1"` after first install so manual edits stick.
4. **Tests first-class.** `tests/test_phase{1,2,3}_*.py` + `tests/test_full_flow.py` exercise each layer + the end-to-end sale → task → MO → WO → consumption → readiness → ECO loop.
5. **`sudo()` only with reason.** Any `.sudo()` call carries a one-line comment explaining the access-bypass justification.
6. **Odoo 19 quirks respected:** `models.Constraint` not `_sql_constraints`; `res.users.group_ids` not `groups_id`; no `res.groups.category_id`; `<group name="...">` not `<group expand="0" string="...">`.

## Deploy

Local build:
```bash
cd ~/southbrook-v19cr
git add addons/southbrook_premium_orchestration
git commit -m "feat: premium orchestration addon (Phase 1-3 spine + practical + generative)"
```

QNAP deploy (needs LAN):
```bash
./scripts/deploy_to_qnap.sh -m southbrook_premium_orchestration
# This uses the flock-locked recipe documented in CLAUDE.md §Deploy.
```

Acceptance per phase: see `docs/ACCEPTANCE_CRITERIA.md`.
