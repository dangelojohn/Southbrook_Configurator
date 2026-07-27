# QNAP Pull Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deploy path that avoids sandbox-blocked rsync/stdin transfers by having the QNAP pull committed code from Forgejo and run the Odoo upgrade locally.

**Architecture:** Keep the existing `deploy_to_qnap.sh` rsync flow for normal developer machines. Add a QNAP-side pull deploy script that downloads a Forgejo archive for a pushed commit, replaces only requested addon directories, runs the same cold Odoo upgrade gate, optionally runs targeted test tags, and checks live health. Add a local trigger wrapper whose SSH payload is a short command, so restricted agent environments do not need rsync, scp, or streamed stdin.

**Tech Stack:** Bash, Forgejo raw/archive URLs, QNAP Container Station `system-docker`, Odoo CLI, PostgreSQL `psql`, SSH.

## Global Constraints

- Do not require local Docker/OrbStack.
- Do not require rsync/scp/stdin streaming over SSH.
- Use the existing QNAP `system-docker` path: `/share/CACHEDEV3_DATA/.qpkg/container-station/bin/system-docker`.
- Preserve the existing cold-upgrade safety gate before trusting a deploy.
- Keep `scripts/deploy_to_qnap.sh` available for unrestricted developer machines.
- Deploy only explicitly named addon modules.

---

### Task 1: QNAP-Side Pull Deploy Script

**Files:**
- Create: `scripts/qnap_pull_deploy.sh`

**Interfaces:**
- Consumes: Forgejo archive URL for a pushed ref.
- Produces: QNAP-side command `bash qnap_pull_deploy.sh --ref <commit> --modules <csv> [--test-tags <tags>]`.

- [x] **Step 1: Write the script**

Create `scripts/qnap_pull_deploy.sh` with argument parsing for `--ref`, `--modules`, and `--test-tags`. The script downloads `http://192.168.68.108:9080/git/qnap/southbrook-v19cr/archive/<ref>.tar.gz`, extracts it, atomically replaces each requested `addons/<module>` directory, classifies modules as install/upgrade, runs Odoo under `flock`, checks the cold-upgrade sentinel, optionally runs tagged tests, and checks `/web/login` health from inside the Odoo container.

- [x] **Step 2: Run static checks**

Run:

```bash
bash -n scripts/qnap_pull_deploy.sh
```

Expected: exit `0`.

### Task 2: Local Short-SSH Trigger

**Files:**
- Create: `scripts/deploy_to_qnap_pull.sh`
- Modify: `scripts/README.md`

**Interfaces:**
- Consumes: local Git HEAD and module CSV.
- Produces: short SSH command that makes QNAP curl and execute `qnap_pull_deploy.sh` from Forgejo.

- [x] **Step 1: Write the trigger**

Create `scripts/deploy_to_qnap_pull.sh`. It resolves `git rev-parse HEAD`, requires a module CSV argument, defaults to the LAN SSH host, and runs:

```bash
ssh "$QNAP_HOST" "/sbin/curl -fsSL '$RAW_SCRIPT_URL' | /bin/bash -s -- --ref '$REF' --modules '$MODULES'"
```

- [x] **Step 2: Document usage**

Add examples to `scripts/README.md`:

```bash
./scripts/deploy_to_qnap_pull.sh southbrook_floor_traveler,southbrook_premium_orchestration
TEST_TAGS=/southbrook_floor_traveler:TestP8FloorTraveler.test_record_scan_creates_one_consumption_and_logs_workcenter ./scripts/deploy_to_qnap_pull.sh southbrook_floor_traveler,southbrook_premium_orchestration
```

### Task 3: Verify on QNAP

**Files:**
- No new files.

**Interfaces:**
- Consumes: committed/pushed scripts from Forgejo.
- Produces: deployed addon directories and Odoo upgrade/test evidence.

- [ ] **Step 1: Commit and push to Forgejo**

Run:

```bash
git add scripts/qnap_pull_deploy.sh scripts/deploy_to_qnap_pull.sh scripts/README.md docs/superpowers/plans/2026-06-18-qnap-pull-deploy.md
git commit -m "feat(deploy): add qnap pull deploy path"
git push origin feature/configurator-loop-p1-p8
```

- [ ] **Step 2: Dry run static syntax**

Run:

```bash
bash -n scripts/qnap_pull_deploy.sh scripts/deploy_to_qnap_pull.sh
```

Expected: exit `0`.

- [ ] **Step 3: Run a harmless module deploy with targeted tests**

Run:

```bash
TEST_TAGS=/southbrook_floor_traveler:TestP8FloorTraveler.test_record_scan_creates_one_consumption_and_logs_workcenter \
  ./scripts/deploy_to_qnap_pull.sh southbrook_floor_traveler,southbrook_premium_orchestration
```

Expected: QNAP downloads the commit archive, replaces the two addon directories, Odoo cold-upgrade exits `0`, the targeted test exits `0`, and health returns 200.

## Self-Review

- Spec coverage: the plan removes rsync/stdin dependence, preserves cold upgrade and health gates, and keeps the old deploy script.
- Placeholder scan: no placeholders remain.
- Type consistency: script interfaces use the same `--ref`, `--modules`, and `--test-tags` names throughout.
