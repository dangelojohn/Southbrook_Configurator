# `scripts/`

Operational helpers. None of these are required for `git clone && pip
install` — they accelerate common chores against the live QNAP stack.

## `deploy_to_qnap.sh`

Rsync one or more addons from this checkout to the live QNAP container
and run an Odoo `-u` upgrade.

```sh
# default: estimating + configurator_ux
./scripts/deploy_to_qnap.sh

# specific module
./scripts/deploy_to_qnap.sh southbrook_estimating

# comma-separated list
./scripts/deploy_to_qnap.sh southbrook_estimating,southbrook_plm

# dry-run (see commands without executing)
DRY_RUN=1 ./scripts/deploy_to_qnap.sh southbrook_estimating

# override target
QNAP_HOST=admin@10.0.0.5 ./scripts/deploy_to_qnap.sh ...
```

**Why it exists:** QNAP's Container Station runs Odoo under a hidden
inner docker daemon. The user-visible `docker` command sees a
different daemon and won't find the Odoo container. The actual binary
lives at `/share/CACHEDEV3_DATA/.qpkg/container-station/bin/system-docker`
— a path you only learn after a few hours of debugging "container not
found." This script encodes that knowledge.

**Knobs (env vars):**

| Var | Default | Meaning |
|---|---|---|
| `QNAP_HOST` | `admin@192.168.68.108` | ssh target |
| `QNAP_ADDONS_DIR` | `/share/CACHEDEV3_DATA/Container/southbrook/addons` | mounted volume |
| `QNAP_DOCKER` | `/share/.../system-docker` | container-station binary |
| `CONTAINER` | `southbrook-odoo` | Odoo container name |
| `DB` | `southbrook` | Odoo DB |
| `DRY_RUN` | `0` | print but don't execute |

## Other scripts (pre-existing)

- `gen_phase1_data.py` — generator for the Phase 1 seed data
- `lint-xml.sh` — XML validation pre-commit hook
- `smoke_browser.py` / `smoke_customer_flow.sh` — older smoke checks
  (the Playwright suite at `e2e/` is the canonical replacement)
