# KitchenForge — Deploy Hierarchy

Four-stage deploy pipeline for the `kitchenforge_*` addon family:

```
┌────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   local    │ ──▶ │ QNAP staging │ ──▶ │  QNAP prod   │ ──▶ │  future k8s  │
│ dev compose│     │  tenants     │     │ (southbrook) │     │ (Helm chart) │
└────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
   make test       deploy_kitchen-      deploy_kitchen-      helm upgrade
   make lint       forge.sh             forge.sh             kitchenforge ./k8s
                   --tenant <demo>      --tenant southbrook
```

## Layout

| Path | What |
|---|---|
| `.forgejo/workflows/kitchenforge_ci.yml` | CI: lint → test → deploy-staging |
| `deploy/deploy_kitchenforge.sh` | Mac/CI-side wrapper, calls `scripts/deploy_to_qnap.sh` per addon in dependency order |
| `deploy/provision_tenant.sh` | QNAP-SIDE script — stand up a brand-new tenant stack |
| `deploy/k8s/` | Forward-looking Helm chart (one tenant per release) — not wired to ArgoCD yet |
| `scripts/deploy_to_qnap.sh` | Pre-existing per-addon deploy primitive; this stack composes on top |

## Workflows

### Develop → staging
```
make lint           # mirrors the CI lint job locally
make test           # full Odoo test sweep on the dev compose stack
git push origin feature/kitchenforge-x
# CI runs lint + test on every push to feature/kitchenforge-**; deploy-staging
# fires only on push-to-main.
```

### Promote to prod
```
make deploy-prod    # interactive confirm + runs deploy_kitchenforge.sh on
                    # southbrook in upgrade mode
```

### Add a new tenant
```
# On the QNAP, NOT on a Mac:
sudo /share/CACHEDEV3_DATA/scripts/provision_tenant.sh \
  --slug myshop --admin-email ops@myshop.com --tier marathon_channel
```

The provisioner is idempotent and bails out if `/share/CACHEDEV3_DATA/Container/<slug>/`
already exists.

## Cold-install gap warnings (READ THIS BEFORE PROVISIONING)

Per memory `southbrook_cold_install_gaps.md`, the broader Southbrook platform
**cannot currently rebuild from scratch** — 5 of 17 deployed modules fail a
fresh cold install on a clean DB:

- `southbrook_estimating_website` — xpath fails against the unpatched
  configurator currency view
- `southbrook_mrp_pm` — depends on `it` (a module that isn't in our path)
- `southbrook_plm_productgraph` — depends on the unvendored
  `product_graph_release`
- Two more off-main modules (see the memory file)

What this means for KitchenForge:

1. `kitchenforge_core` depends on `southbrook_estimating` and
   `southbrook_project_mrp`. **Those must be installed first**, by a path
   that bypasses the broken siblings (the validated CI subset in the root
   `Makefile`'s `MODULES =` is your reference).
2. `provision_tenant.sh` runs `-i base --stop-after-init` first, then
   `-i kitchenforge_core,kitchenforge_marathon,kitchenforge_saas`. The
   transitive Southbrook deps must already be present in
   `/mnt/extra-addons/` — copy them in before running the provisioner, or
   stage them via `addons/` rsync from the dev checkout.
3. Treat any tenant build as "warm" until the cold-install gaps close —
   the QNAP-staging step is load-bearing for verification.

## Lock + restart recipe (live deploys)

Two memory files govern live behavior:

- `southbrook_deploy_flock_lock.md` — every `odoo -u` is wrapped in
  `flock -E 75 -w 600 /tmp/<tenant>-odoo-upgrade.lock` to serialize
  concurrent upgrades.
- `qnap_odoo_upgrade_cache_reset.md` — a `docker restart` follows every
  multi-addon upgrade or the live workers' ormcache stays poisoned and
  `/web/login` 500s with "Circular assets bundle".

Both are baked into `deploy_kitchenforge.sh` — do not bypass them.

## Future: k8s + ArgoCD

The `deploy/k8s/` chart is a minimal viable shape, not a target deployment.
When we move off the QNAP:

1. Stand up one Helm release per tenant: `helm install southbrook ./k8s -f values/southbrook.yaml`
2. Drop an ArgoCD `Application` CRD pointing at this chart in a GitOps repo
3. Cutover order: provision the k8s tenant, dump+restore the QNAP DB, swap
   DNS, decommission the QNAP stack

The chart deliberately omits ArgoCD wiring so the first cluster is a clean
manual install — automation comes second.
