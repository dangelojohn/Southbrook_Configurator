# Testing the QNAP No-SSH Deploy Pipeline

Pick the path that matches your environment.

## TL;DR

| Path | Effort | When to use |
|---|---|---|
| `./scripts/test_qnap_deploy.sh` | One command | You have a terminal + git push to GitHub. Works from any Mac/Linux. |
| Same script + `--no-ssh` | Same | You're in a sandbox that blocks SSH (Codex). Pushes the request, verifies GitHub sees it, stops — QNAP-side verification is then a separate human check. |
| Web UI / browser (Claude Chrome) | A few clicks | You don't have a terminal in this session. See "Browser path" below. |

## Prerequisites (one-time)

1. The `deploy/release` branch must exist on the GitHub remote. To create it:

   ```bash
   cd ~/southbrook-v19cr
   git fetch github-southbrook
   git push github-southbrook github-southbrook/main:refs/heads/deploy/release
   ```

2. The QNAP-side poller must already be installed + cron-enabled. See `deploy/qnap/README.md` for the install snippet. Verify with:

   ```bash
   ssh admin@192.168.68.108 \
     'grep qnap_deploy_poller /etc/config/crontab && \
      ls -la /share/CACHEDEV3_DATA/Container/southbrook/qnap_deploy_poller.sh'
   ```

3. Optional but recommended: **enable branch protection on `deploy/release`** before treating this as a production deploy mechanism. See "Branch protection" below.

## Terminal path (humans + Claude Code)

```bash
cd ~/southbrook-v19cr

# Default safe smoke test: upgrades two modules, runs a 13s targeted test,
# health-checks /web/login. Takes ~4 minutes from push to "applied".
./scripts/test_qnap_deploy.sh

# Customize what gets deployed:
./scripts/test_qnap_deploy.sh \
  --modules southbrook_kitchen_mrp,southbrook_hardware_catalog \
  --test-tags /southbrook_kitchen_mrp

# Sandbox mode (skip QNAP SSH verification):
./scripts/test_qnap_deploy.sh --no-ssh
# Then manually:
ssh admin@192.168.68.108 'cat /share/CACHEDEV3_DATA/Container/southbrook/deploy-state/last_request_id'
# Expected output: the REQUEST_ID printed by the script.
```

What the script does:

1. Reads your current `git HEAD` SHA.
2. Writes a fresh `deploy/qnap/request.env` pointing at that SHA.
3. Pushes the request to the `deploy/release` branch (default).
4. Polls GitHub raw until the new REQUEST_ID is visible there (proves push reached the polled branch).
5. Polls the QNAP-side `last_request_id` state file until it matches (proves the poller + deploy + tests + health check all succeeded).
6. Prints the poller log tail so you can read context.

The script exits 0 on full success, non-zero with a clear `❌ FAIL: …` line on any step.

## Browser path (Claude Chrome + humans without a terminal)

You can drive the same test end-to-end from a browser. This path uses the GitHub web UI to push the request and the QNAP-exposed status to verify.

### Step 1 — Push a deploy request via GitHub web UI

Open: <https://github.com/dangelojohn/Southbrook_Configurator/edit/deploy/release/deploy/qnap/request.env>

(If GitHub shows you a "no such branch / file" page, see "Prerequisites" above — `deploy/release` must exist.)

Edit the file. Change ONLY `REQUEST_ID` and `REQUESTED_AT` to fresh values — pick anything alphanumeric+`-` that you can recognize later. Keep `REF`, `MODULES`, `TEST_TAGS`, and `REPO_ARCHIVE_BASE` the same as the previous successful deploy. Example:

```env
REQUEST_ID=20260618T154500Z-browser-test
REQUESTED_AT=20260618T154500Z
REF=<commit SHA on any branch you want deployed; usually current main>
MODULES=southbrook_floor_traveler,southbrook_premium_orchestration
TEST_TAGS=/southbrook_floor_traveler:TestP8FloorTraveler.test_record_scan_creates_one_consumption_and_logs_workcenter
REPO_ARCHIVE_BASE=https://github.com/dangelojohn/Southbrook_Configurator/archive
```

Click **Commit changes**, then **Commit directly to the `deploy/release` branch**.

### Step 2 — Watch GitHub propagate

Within ~10 seconds your edit lands on the branch. Verify by opening:

<https://raw.githubusercontent.com/dangelojohn/Southbrook_Configurator/deploy/release/deploy/qnap/request.env>

You should see your REQUEST_ID at the top.

### Step 3 — Wait for the QNAP poller to apply it

The poller runs every minute. Total wall-clock from push to "applied" is typically 3–5 minutes (most of it is the Odoo cold upgrade + targeted test).

### Step 4 — Verify the deploy succeeded

The browser-friendly verification surface depends on your setup:

- **Public live-state endpoint** — if `/deploy/state` is exposed via Caddy (recommended but not yet wired by default), open it and confirm your REQUEST_ID. Until that's wired, use one of:
- **GitHub commit history** — open <https://github.com/dangelojohn/Southbrook_Configurator/commits/deploy/release> and confirm your test commit is the latest. (Proves the push happened, not that the deploy applied.)
- **Live site health** — open <https://southbrookcabinetry.space/web/login> and confirm it renders without error. (Proves the deploy didn't break the site; doesn't prove it picked up your REQUEST_ID specifically.)
- **Ask someone with SSH** to run:
  ```bash
  ssh admin@192.168.68.108 'cat /share/CACHEDEV3_DATA/Container/southbrook/deploy-state/last_request_id'
  ```
  The output must match your REQUEST_ID. If it doesn't, also run:
  ```bash
  ssh admin@192.168.68.108 'tail -30 /share/CACHEDEV3_DATA/Container/southbrook/deploy-state/poller.log'
  ```
  to see why.

## Branch protection (recommended before production use)

The poller trusts whatever lives on `deploy/release`. Anyone who can push to that branch can swap the deploy script. Before treating this as a production mechanism, enable branch protection.

### CLI (one-time)

Requires `gh` CLI logged in as a repo admin (`gh auth login`).

```bash
gh api -X PUT \
  /repos/dangelojohn/Southbrook_Configurator/branches/deploy/release/protection \
  -F required_status_checks=null \
  -F enforce_admins=false \
  -F required_pull_request_reviews.required_approving_review_count=1 \
  -F required_pull_request_reviews.dismiss_stale_reviews=true \
  -F restrictions=null \
  -F allow_force_pushes=false \
  -F allow_deletions=false
```

### Browser

Open <https://github.com/dangelojohn/Southbrook_Configurator/settings/branches> and add a rule for `deploy/release`:

- ✅ Require a pull request before merging (1 reviewer)
- ✅ Dismiss stale pull request approvals when new commits are pushed
- ✅ Restrict who can push to matching branches (limit to maintainers)
- ❌ Allow force pushes
- ❌ Allow deletions

After enabling, the `test_qnap_deploy.sh` script won't be able to direct-push to `deploy/release` anymore — testers will need to PR + merge, OR carve a separate `deploy/staging` branch (recommended pattern: dev → staging → release).

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `remote branch github-southbrook/deploy/release does not exist` | One-time setup not done | Run the `git push github-southbrook github-southbrook/main:refs/heads/deploy/release` command in Prerequisites. |
| `GitHub raw never surfaced REQUEST_ID after 120s` | Push failed silently OR DNS issue | Re-run `git push github-southbrook deploy/release` manually, watch the output. |
| `QNAP did not mark REQUEST_ID applied after 480s` | Poller cron disabled, OR the deploy is hanging | SSH to the QNAP and check `ps -ef \| grep qnap_pull_deploy` and `tail /tmp/qnap_pull_deploy_upgrade.log`. |
| Poller log shows `SerializationFailure … giving up` | postgres concurrency race exhausted retries | Bump `MAX_ATTEMPTS` in `scripts/qnap_pull_deploy.sh`. Or re-run the test (transient). |
| Deploy applies but `/web/login` returns non-200 | Real registry-load failure post-upgrade | Read `/tmp/qnap_pull_deploy_upgrade.log` on the QNAP for the Odoo error trace. |
