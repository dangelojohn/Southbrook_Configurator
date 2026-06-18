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

## `deploy_to_qnap_pull.sh`

Sandbox-friendly deploy path. Instead of rsyncing files from this
machine, it sends one short SSH command to the QNAP. The QNAP then
downloads the committed repository archive from GitHub by default, replaces only
the requested addon directories, runs the cold Odoo upgrade gate, and
optionally runs targeted tests.

Use this when local SSH file transfer, rsync, scp, Docker, or DNS are
blocked by an agent sandbox.

```sh
# Commit and push first, then deploy the current HEAD by commit SHA.
./scripts/deploy_to_qnap_pull.sh southbrook_floor_traveler,southbrook_premium_orchestration

# Run a targeted Odoo test after the upgrade.
TEST_TAGS=/southbrook_floor_traveler:TestP8FloorTraveler.test_record_scan_creates_one_consumption_and_logs_workcenter \
  ./scripts/deploy_to_qnap_pull.sh southbrook_floor_traveler,southbrook_premium_orchestration
```

**Knobs (env vars):**

| Var | Default | Meaning |
|---|---|---|
| `QNAP_HOST` | `admin@192.168.68.108` | ssh target |
| `REF` | current `git rev-parse HEAD` | commit/archive ref to deploy |
| `SCRIPT_REF` | same as `REF` | commit containing `scripts/qnap_pull_deploy.sh` |
| `RAW_SCRIPT_URL` | GitHub raw URL for `SCRIPT_REF` | script URL the QNAP curls |
| `REPO_ARCHIVE_BASE` | `https://github.com/dangelojohn/Southbrook_Configurator/archive` | archive base passed to the QNAP-side script |
| `TEST_TAGS` | empty | optional Odoo `--test-tags` value |

## Other scripts (pre-existing)

- `gen_phase1_data.py` — generator for the Phase 1 seed data
- `lint-xml.sh` — XML validation pre-commit hook
- `verify_onshape_cad_link.sh` — static checks plus optional Docker/Odoo
  upgrade and `southbrook,onshape` tests for the per-product Onshape CAD link
- `smoke_browser.py` / `smoke_customer_flow.sh` — older smoke checks
  (the Playwright suite at `e2e/` is the canonical replacement)
