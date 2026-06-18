# QNAP Deploy Requests

`request.env` is a Git-backed handoff file for the QNAP deploy poller.
It is created by `scripts/request_qnap_deploy.sh` and read by
`scripts/qnap_deploy_poller.sh` on the QNAP.

Do not put secrets in this directory. The request file contains only a commit
ref, addon module names, optional Odoo test tags, and public GitHub URLs.

## Release branch model

The poller is hardcoded to watch the **`deploy/release`** branch — separate
from day-to-day developer branches. Day-to-day work on feature branches does
NOT trigger a production deploy, even if a developer pushes a malformed
`request.env` elsewhere. The deploy-release branch should be branch-protected
(PR + review required); see `deploy/qnap/TESTING.md` "Branch protection".

The poller honors `REPO_ARCHIVE_BASE` overrides in the request file (which only
chooses where to pull addon code from) but **does NOT honor `PULL_SCRIPT_URL`
overrides** — the deploy script itself is always loaded from `deploy/release`
to keep the supply-chain surface tied to the branch-protection boundary.

For testing the pipeline end-to-end, see `deploy/qnap/TESTING.md`.

## How the pipeline works

```
agent  ──► GitHub push (deploy/qnap/request.env)
                              │
                              ▼
QNAP cron ──► poller pulls request.env, dedups against
                              │   /share/.../deploy-state/last_request_id
                              ▼
poller curl-pipes scripts/qnap_pull_deploy.sh into bash with
the request's --ref / --modules / --test-tags
                              │
                              ▼
qnap_pull_deploy.sh: download GitHub archive → replace addons →
cold-upgrade Odoo (temporarily pausing active `ir.cron` rows owned by
the modules being upgraded, with restore-on-exit; embedded targeted tests if requested) →
HTTP-probe /web/login → mark request applied if all green
```

## Installing the poller on the QNAP host

The poller runs **on the QNAP host**, not inside a container. It does
not depend on `flock` being available on the host (the busybox shipped
with QTS does not include it); a PID-file guards against concurrent
runs.

```bash
mkdir -p /share/CACHEDEV3_DATA/Container/southbrook/deploy-state
curl -fsSL \
  https://raw.githubusercontent.com/dangelojohn/Southbrook_Configurator/feature/configurator-loop-p1-p8/scripts/qnap_deploy_poller.sh \
  -o /share/CACHEDEV3_DATA/Container/southbrook/qnap_deploy_poller.sh
chmod +x /share/CACHEDEV3_DATA/Container/southbrook/qnap_deploy_poller.sh
# Manual one-shot: applies any pending request immediately.
/share/CACHEDEV3_DATA/Container/southbrook/qnap_deploy_poller.sh
```

## Enabling cron (every minute)

QTS rewrites `/etc/config/crontab` on firmware updates and on some
reboots. To keep the poller cron-installed across reboots, you must
ALSO add a small autorun snippet that re-installs the crontab line
on boot. Both edits are needed.

```bash
# 1. Add the cron line right now.
printf '* * * * * /share/CACHEDEV3_DATA/Container/southbrook/qnap_deploy_poller.sh >> /share/CACHEDEV3_DATA/Container/southbrook/deploy-state/poller.log 2>&1\n' \
  >> /etc/config/crontab
crontab /etc/config/crontab

# 2. Make it durable across reboots. /etc/config/autorun.sh runs at
#    boot; it should reinstall the cron line if it's missing.
cat >> /etc/config/autorun.sh <<'AUTORUN'
# southbrook deploy poller
if ! grep -q qnap_deploy_poller.sh /etc/config/crontab; then
  printf '* * * * * /share/CACHEDEV3_DATA/Container/southbrook/qnap_deploy_poller.sh >> /share/CACHEDEV3_DATA/Container/southbrook/deploy-state/poller.log 2>&1\n' >> /etc/config/crontab
  crontab /etc/config/crontab
fi
AUTORUN
chmod +x /etc/config/autorun.sh
```

## Supply-chain caveat — read this

The poller does `curl … | bash` on `PULL_SCRIPT_URL`. Both
`PULL_SCRIPT_URL` and `REPO_ARCHIVE_BASE` are read FROM the request
file the poller just fetched, and the request file CAN override
those URLs. That means anyone with write access to the polled branch
(`feature/configurator-loop-p1-p8` by default) can swap the script
the QNAP runs.

Mitigations to put in place when this goes from "test setup" to
"production deploy mechanism":

1. **Protect the polled branch.** Require pull-request review for any
   write to `feature/configurator-loop-p1-p8`. The poller trusts the
   contents of that branch; treat it like a CI-deploy key.
2. **Pin the poller's hardcoded `REQUEST_URL` / `PULL_SCRIPT_URL` to a
   tag or release branch you control**, separate from day-to-day
   developer branches.
3. **Audit the request file via the GitHub commit history.** Every
   request leaves a commit; every commit has an author.

Until those are in place, treat the polled branch as a deploy
secret — anyone with write to it has root-equivalent on
`southbrook-odoo`.
