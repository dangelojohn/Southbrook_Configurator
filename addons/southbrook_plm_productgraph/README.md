# Southbrook PLM ↔ ProductGraph Bridge

Glue module wiring `southbrook_plm` to `product_graph_release`.

## What it does

Adds three fields to `southbrook.eco`:

| Field | Purpose |
|---|---|
| `pg_ebom_id` | Optional pointer to a released `pg.ebom`. |
| `pg_release_id` | Read-only handle to the resulting `pg.release` record (set on apply). |
| `pg_auto_release` | Opt-in toggle (default True). |

Wraps `southbrook.eco.action_apply` with a post-step: if `pg_auto_release` is on and `pg_ebom_id` is set, create a `pg.release` against that EBOM and execute it. The PLM side runs first and unchanged.

## What it does *not* do

- Does not replace `_apply_bom` / `_apply_cut_spec` / `_apply_rule` / `_apply_document`.
- Does not roll back the ECO if the bridge release fails — failure posts a chatter note and the Approver can retry from the EBOM form.
- Does not reach back into ProductGraph (one-way coupling, Decision D1 in `~/product_graph_v19/DECISIONS.md`).

## Where this lives

This addon is **Southbrook-specific**. It lives in `~/southbrook-v19cr/addons/` and is intentionally NOT in the generic `productgraph-v19` repo — that repo is publishable LGPL-3 and must not contain any reference to `southbrook_plm`.

## Deploy

```
addons/southbrook_plm_productgraph/  →  /mnt/extra-addons/  on southbrook-odoo
odoo -i southbrook_plm_productgraph -d southbrook --stop-after-init
```

Then restart the running container so the module registry refreshes.

## Test

```bash
odoo-bin -d southbrook --test-enable --test-tags southbrook_plm_productgraph \
  -i southbrook_plm_productgraph --stop-after-init
```

Four cases:
1. `test_bridge_fires_release` — ECO with `pg_ebom_id` → `pg.release.state == completed` + `mrp.bom` created.
2. `test_bridge_skips_without_ebom` — no `pg_ebom_id` → no release fired.
3. `test_bridge_skips_when_auto_release_off` — toggle off → no release fired.
4. `test_bridge_idempotent` — already-released ECO would not re-fire.

## Failure semantics

| PLM result | Bridge result | ECO state | mrp.bom result |
|---|---|---|---|
| OK | OK | `applied` | `pg.release.mrp_bom_id` set |
| OK | Fail | `applied` | Chatter note flags the failure; retry from EBOM wizard |
| Fail | (not run) | unchanged | unchanged |
