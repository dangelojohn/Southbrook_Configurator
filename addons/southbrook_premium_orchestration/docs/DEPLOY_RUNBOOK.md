# Deploy Runbook — Southbrook Premium MRP Orchestration

**Branch:** `feature/premium-orchestration`
**Commit:** `4211dfb` (46 files / 6198 insertions)
**Target:** QNAP southbrook stack at `192.168.68.108` (DB `southbrook`)
**Date:** 2026-06-15

## Pre-deploy verification (LOCAL — already complete)

| Check | Status |
|---|---|
| Python AST parse (23 files) | PASS |
| XML parse (18 files) | PASS |
| Manifest coherence (every `data` entry exists) | PASS |
| Import graph (11 model + 3 wizard + 4 test imports resolve) | PASS |
| Odoo 19 quirk audit | PASS (no `_sql_constraints`, no `groups_id`, no `category_id`, no search `<group expand=>`) |
| Cross-agent contract integrity | PASS (after 2 fixes: `action_open_kitchen_job` + `action_open_cut_spec_override_for_wo`) |
| `.sudo()` justification | PASS (system-scoped config + tests) |
| 16 test methods defined | DEFERRED to QNAP-side `--test-enable` run |

## Deploy steps (REQUIRES LAN — currently blocked from this workstation)

### 1. Push the branch to Forgejo

```bash
cd ~/southbrook-v19cr
git push -u origin feature/premium-orchestration
```

This requires SSH/HTTPS access to the Forgejo remote on the QNAP. Confirm via:
```bash
git remote -v
```

### 2. Sync source onto the QNAP container

If `scripts/deploy_to_qnap.sh` is the canonical recipe (per `southbrook_deploy_flock_lock` memory):
```bash
./scripts/deploy_to_qnap.sh -m southbrook_premium_orchestration --install
```

Recipe quirks (per `southbrook_deploy_flock_lock` + `southbrook_plm_deploy` memories):
- Uses `flock -E 75 -w 600 /tmp/southbrook-odoo-upgrade.lock` to serialise.
- `DOCKER_HOST=unix:///var/run/system-docker.sock` (the second daemon).
- `/share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker` (not on the default PATH).
- `mako` must be present in the running container (already there). If running via `compose run`, prepend `pip install --break-system-packages -q Mako`.
- Prefer `docker exec southbrook-odoo odoo -d southbrook -i southbrook_premium_orchestration --stop-after-init --no-http --http-port=8899 --gevent-port=8902 --workers=0 --max-cron-threads=0 --logfile=/var/log/odoo/KEEP-orch-install.log` — `compose run` collides on port 8069 if the main odoo is up.

### 3. After install, restart the worker (per `qnap_odoo_upgrade_cache_reset` memory)

```bash
ssh admin@192.168.68.108 \
  'DOCKER_HOST=unix:///var/run/system-docker.sock \
   /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker restart southbrook-odoo'
```

The registry signal alone leaves the worker ormcache poisoned and triggers
`Circular assets bundle` 500s on `/web/login`. Restart is mandatory.

### 4. Caddy upstream cache flush

```bash
ssh admin@192.168.68.108 \
  'DOCKER_HOST=unix:///var/run/system-docker.sock \
   /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker \
   exec alfacore-caddy caddy reload --config /etc/caddy/Caddyfile'
```

(Per `qnap_demo_stacks` Gotcha #7 — Caddy caches upstream IPs for minutes after
upstream restart.)

## Acceptance gates (post-deploy)

### Phase 1
- [ ] Module shows `installed` on `ir.module.module` filter `name=southbrook_premium_orchestration`
- [ ] All 100% of `sale.order WHERE state='sale'` have `x_southbrook_project_task_id != False` after running the **Backfill Kitchen Tasks** server action on the list (already only 1/9 today)
- [ ] All 6 new crons in `ir.cron` filtered by `name ILIKE 'Southbrook:%'` show `active=True` and `nextcall <= now()+interval`
- [ ] After 1 hour: `southbrook.mi.engine` singleton has `last_run_at` within the last hour and `last_run_check_count > 0`
- [ ] **Kitchen Ops** top-level menu visible to admin; Kitchen Jobs board renders all confirmed SOs grouped by `readiness_decision`
- [ ] Test-user archive wizard previews ≈86 users, archive flips them to `active=False`
- [ ] After 6 hours: `southbrook.order.analytics` count ≥ count of `sale.order WHERE state='sale'`

### Phase 2
- [ ] `southbrook.tool.asset` count = 30 after install
- [ ] After one work-order `button_finish` cycle: `southbrook.workorder.tool.consumption` count > 0, the consumed asset's `remaining_life_qty` decreased
- [ ] `mrp.workorder.duration` populated (`> 0.0`) on any completed WO
- [ ] After seeding 12 cut-spec overrides on `width_to_door_count` and running `_cron_propose_eco_for_high_frequency_overrides`: one new `southbrook.eco` with type `Construction-Rule Change`, state `open`, referencing the rule_key

### Phase 3
- [ ] **Gemini Go-Live** completed per `docs/GEMINI_GO_LIVE.md` — OR — capability marked DEFERRED in pitch deck
- [ ] **FreeCAD Go-Live** completed per `docs/FREECAD_GO_LIVE.md` — OR — capability marked DEFERRED
- [ ] `mrp.planning.run` count ≥ 1 weekly entry; ≥ 1 `mrp.planning.line` with `capacity_overloaded=True` or `is_delayed=True`
- [ ] `southbrook.project.data.quality.report` count > 0 after first nightly run
- [ ] At least one `project.task` created from a job template (`x_kitchen_job_template_id IS NOT NULL`)

### Hygiene
- [ ] OPL-1 memo (`docs/OPL1_LEGAL_HOLD.md`) reviewed; OpenValue contract confirmed or alternative path chosen — BEFORE any external peer-manufacturer offer

## Rollback

If install fails or production behaviour regresses:
```bash
ssh admin@192.168.68.108 \
  'DOCKER_HOST=unix:///var/run/system-docker.sock \
   /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker \
   exec southbrook-odoo odoo -d southbrook \
     --uninstall=southbrook_premium_orchestration \
     --stop-after-init --no-http --workers=0'
```

Then `docker restart southbrook-odoo` again.

The addon is **purely additive** — uninstalling drops the new menus, crons,
models, and the 30 tool assets seeded by `tool_asset_seed.xml` (noupdate=1 keeps
operator edits but uninstall removes the records). It does **not** touch any
data on the parent `southbrook_*` modules.

## Tests (post-install)

```bash
docker exec southbrook-odoo \
  odoo -d southbrook --test-enable -i southbrook_premium_orchestration \
       --stop-after-init --no-http --workers=0 \
       --log-handler=odoo.addons.southbrook_premium_orchestration:DEBUG \
       2>&1 | tee /tmp/orch-tests.log

grep -E "TEST|FAIL|PASS" /tmp/orch-tests.log | head -40
```

16 test methods are expected. Tagged `post_install` `-at_install` so they only
run after dependencies are loaded.

## Known follow-ups (not blocking deploy)

1. **OpenValue OPL-1 contract** — `docs/OPL1_LEGAL_HOLD.md` action items #1–3
2. **Replace `ir.config_parameter` cleartext for `gemini.api_key` with `tools.config` from `odoo.conf`** in production — wizard sets via config_parameter for dev convenience; prod should set at container boot
3. **FreeCAD daemon** — confirm `southbrook-freecad-bridge:8000` is actually deployed before flipping `freecad_bridge.enabled=True`
4. **Cron stagger** — if memory pressure observed on the 2G Odoo container, stagger the 5 new cron nextcalls (currently centred on top of hour)
