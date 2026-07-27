---
course: 7 — Sysadmin
chapter: 7.2
title: Backups — Verifying the Nightly Job Ran and the Artifacts Landed
duration: 30 minutes
audience: IT Admin / Sysadmin on call when a backup is missing, stale, or restoring after a corruption event
prereqs: SSH access to the QNAP host (192.168.68.108 on LAN, ssh.odooiq.com via Cloudflare tunnel), comfort with bash + docker, basic Postgres concepts (dropdb / createdb / psql)
custom_modules: none directly — the QNAP host owns the script. southbrook_premium_orchestration is **planned** to surface backup staleness as a Hermes recommendation (see "What this lesson does NOT cover")
---

# Backups — Verifying the Nightly Job Ran and the Artifacts Landed

## Who this lesson is for

You're the sysadmin on call when a Southbrook user opens a ticket saying
"the database is missing yesterday's orders" or "I deleted a kitchen
project and need it back." The QNAP host runs a nightly `backup-odoo.sh`
job at 03:00 that captures the Southbrook DB, filestore, and config to a
versioned tree under `/share/CACHEDEV3_DATA/OdooIQ-Backups/`. This lesson
is how you verify a backup actually ran, what to do when one didn't, and
how to restore a single site to a point-in-time dump.

## Where this lives on the site

The backup pipeline is **not** an Odoo feature — it's a QNAP host-level
shell script + a host crontab entry. Inspection is SSH-only:

> **`ssh admin@ssh.odooiq.com`** (via the Cloudflare tunnel — works from
> anywhere) **or** **`ssh admin@192.168.68.108`** (LAN-only)

The exact paths you'll touch are:

> **Backup script**: `/share/CACHEDEV3_DATA/Container/scripts/backup-odoo.sh`
> **Cron entry**: `/etc/config/crontab` line `0 3 * * * /share/CACHEDEV3_DATA/Container/scripts/backup-odoo.sh`
> **Artifact root**: `/share/CACHEDEV3_DATA/OdooIQ-Backups/`
> **Off-site stub**: `/share/CACHEDEV3_DATA/Container/scripts/offsite-sync.sh`

The artifact root is also exposed as an SMB share `OdooIQ-Backups` —
reachable from any LAN client at `smb://192.168.68.108/OdooIQ-Backups`
for quick browsing without SSH. The SMB share is **not** registered in
QTS Control Panel → Shared Folders UI; it was added directly to
`/etc/config/smb.conf` and is mode 777 for `everyone` (the QNAP is on a
LAN-only management VLAN, not a flat office network).

## What your screen shows

After `ssh admin@ssh.odooiq.com` and `cd
/share/CACHEDEV3_DATA/OdooIQ-Backups/`, you'll see:

- **One subdirectory per site** — `alfacore`, `southbrook`, `sapienzium`,
  `porterly`, `tribancs`, `odooiq`, `quattroporte`, `odooai`. Each holds
  the per-site artifacts.
- **`README.md`** — pinned doc with restore steps, retention table, and
  contact email for the on-call sysadmin.
- **`_meta/`** — pipeline metadata; contains:
  - `_meta/logs/backup-YYYYMMDD.log` — the full stdout+stderr of the
    night's run. **This is the file to read when a backup didn't land.**
  - `_meta/manifest.json` — latest inventory written at the end of every
    run: per-artifact sizes, sha256 prefix, mtime. The manifest is the
    fastest "did anything change?" diagnostic.

Inside each site's directory:

- **`db/daily/<site>-YYYYMMDD.sql.gz`** — gzipped `pg_dump` from
  `<site>-postgres`. Retention: **14 days**.
- **`db/weekly/<site>-YYYY-WNN.sql.gz`** — ISO-week-stamped dump,
  written on Sundays only. Retention: **12 weeks**.
- **`db/monthly/<site>-YYYY-MM.sql.gz`** — written on the 1st of
  every month. Retention: **12 months**.
- **`filestore/weekly/<site>-filestore-YYYYMMDD.tar.gz`** — tarball of
  `odoo-data/filestore/`. Retention: **4 weeks**.
- **`filestore/monthly/<site>-filestore-YYYYMMDD.tar.gz`** — written 1st
  of month. Retention: **4 months**.
- **`config/latest/`** — `docker-compose.yml` + redacted `odoo.conf`
  for that site. Always the latest; not retention-pruned (one snapshot
  is enough for "what did the stack look like that night").

## Daily / Weekly / On-call

**Daily (1 min, end-of-day):**

- SSH in, `ls -lat /share/CACHEDEV3_DATA/OdooIQ-Backups/_meta/logs/ |
  head -5`. The most recent file should be today's `backup-YYYYMMDD.log`
  and the modification time should be within the last 24 h.
- `cat /share/CACHEDEV3_DATA/OdooIQ-Backups/_meta/logs/backup-YYYYMMDD.log
  | tail -20` — last 20 lines confirm the pipeline finished. The
  expected tail is a per-site `OK` summary plus a final `manifest.json
  written`.

**Weekly (Monday morning, 5 min):**

- For each site, `ls -lat
  /share/CACHEDEV3_DATA/OdooIQ-Backups/southbrook/db/daily/ | head -10`
  — you should see 7 dumps from the last 7 nights.
- `ls /share/CACHEDEV3_DATA/OdooIQ-Backups/southbrook/filestore/weekly/`
  — confirm Sunday's filestore tarball is there.
- Spot-check sizes: a healthy southbrook daily dump is ~10-30 MB
  gzipped (grows ~5 MB per million records). A dump that suddenly shrunk
  to 1 KB is a Postgres connection failure mid-dump — investigate the
  log.

**Monthly (1st of month, 10 min):**

- Confirm `db/monthly/southbrook-YYYY-MM.sql.gz` and
  `filestore/monthly/southbrook-filestore-YYYYMMDD.tar.gz` both exist
  for the new month.
- Confirm 12-month retention is holding by checking the oldest monthly:
  `ls /share/CACHEDEV3_DATA/OdooIQ-Backups/southbrook/db/monthly/ |
  head -1`. Anything more than 12 entries means the rotation cron in
  the script's `find -mtime -delete` lines isn't pruning correctly.

**On-call (a backup didn't run, or a user needs a restore):**

The procedures are in the next two sections.

## How to verify the latest backup actually ran

A user opens a ticket: "did last night's backup happen?" The fastest
path:

1. `ssh admin@ssh.odooiq.com`
2. `cat /share/CACHEDEV3_DATA/OdooIQ-Backups/_meta/manifest.json | jq
   '.generated_at, .sites[] | select(.site=="southbrook") |
   {site, db_daily_count, db_daily_latest, filestore_weekly_latest}'`
   The `db_daily_latest` field is the most recent daily dump's path
   plus mtime — that's your authoritative "did the southbrook DB get
   dumped" answer.
3. If `jq` isn't comfortable, just `ls -lt
   /share/CACHEDEV3_DATA/OdooIQ-Backups/southbrook/db/daily/ | head -3`.
4. If the most recent dump is more than 25 h old, the cron missed. Go
   to the log: `cat
   /share/CACHEDEV3_DATA/OdooIQ-Backups/_meta/logs/backup-YYYYMMDD.log`
   (yesterday's date). If the log doesn't exist, the cron didn't fire
   at all — see *Common mistakes* below for the crontab-reload procedure.

## How to restore from a backup

The restore procedure for a single site, point-in-time, daily dump:

```bash
# 1. Pick a site + date. Example: southbrook, 2026-06-15.
S=southbrook
DATE=20260615

# 2. Stop the Odoo container — postgres MUST keep running for the
#    restore. Stopping odoo prevents the workers from holding connections.
docker stop ${S}-odoo

# 3. Drop and recreate the database. --force closes any orphan sessions.
docker exec ${S}-postgres dropdb -U odoo --force $S
docker exec ${S}-postgres createdb -U odoo -O odoo $S

# 4. Restore the dump.
gunzip -c /share/CACHEDEV3_DATA/OdooIQ-Backups/$S/db/daily/${S}-${DATE}.sql.gz \
  | docker exec -i ${S}-postgres psql -U odoo -d $S

# 5. Restore the filestore IF the user's complaint involves attachments,
#    PDFs, ir.attachment binary data, or images. Skip otherwise.
cd /share/CACHEDEV3_DATA/Container/$S/odoo-data
sudo rm -rf filestore
sudo tar xzf /share/CACHEDEV3_DATA/OdooIQ-Backups/$S/filestore/weekly/${S}-filestore-*.tar.gz

# 6. Start Odoo and watch the logs for a clean boot.
docker start ${S}-odoo
docker logs -f ${S}-odoo
```

**Important:**

- Filestore tarballs only exist **weekly**, not daily. The restored
  filestore will be from the most recent Sunday, not the exact date of
  the DB dump. For most ticket types this is fine (attachments don't
  change daily); for a strict point-in-time recovery, accept that the
  filestore is up to 7 days off.
- The `alfacore` site uses the legacy path
  `/share/CACHEDEV3_DATA/Container/odoo/` instead of `.../alfacore/` —
  the script's per-site mapping handles this, but the restore command
  above also needs the swap: `cd
  /share/CACHEDEV3_DATA/Container/odoo/odoo-data` for alfacore.
- After restore, **invalidate any sessions** by restarting the Odoo
  container once more. The post-restore boot can leave stale ormcache
  entries that produce 500s on `/web/login` ("Circular assets bundle"
  is the classic symptom — same recovery as the upgrade cache reset).

## Common mistakes + how to recover

**"The backup hasn't run for two nights and no log was written."**

The most common cause on QNAP: someone edited the cron via `crontab -e`
instead of `/etc/config/crontab`. The user-mode crontab gets **wiped on
reboot** because QTS regenerates it from `/etc/config/crontab`. Fix:

```bash
grep backup-odoo /etc/config/crontab   # should show "0 3 * * * /share/.../backup-odoo.sh"
# If missing, append it:
echo '0 3 * * * /share/CACHEDEV3_DATA/Container/scripts/backup-odoo.sh' >> /etc/config/crontab
crontab /etc/config/crontab            # reload user crontab from the persistent file
/etc/init.d/crond.sh restart           # restart crond
```

Re-fire the script manually once to seed today's backup:

```bash
/share/CACHEDEV3_DATA/Container/scripts/backup-odoo.sh
```

**"The backup ran but the log shows `find: ... non-zero exit` and the
script aborted halfway."**

Two likely causes, both encountered during initial deployment:

- `numfmt` not present on QNAP busybox. Pretty-printing of byte sizes
  fails under `set -euo pipefail`. The script was patched to print raw
  bytes; if you see this on a fresh QNAP, search the script for any
  remaining `numfmt --to=iec` and replace with the raw `$BYTES` print.
- `ls glob_with_no_match` returns non-zero. The script uses `find
  -name "*.ext" 2>/dev/null | wc -l` for counting; if you see a new
  `ls` introduced, swap it.

**"Disk filled up and the backup truncated."**

Check `df -h /share/CACHEDEV3_DATA`. The retention math is **14 daily +
12 weekly + 12 monthly DB dumps + 4 weekly + 4 monthly filestore
tarballs per site × 8 sites**. At ~30 MB per daily, ~200 MB per weekly
filestore, the steady-state is roughly 80 GB. If you're above 200 GB,
the rotation cron's `find -mtime -delete` isn't pruning — check the
script's retention block for a typo'd `-mtime` value.

**"The restore worked but Odoo boots into a maintenance screen."**

The `southbrook` DB carries module records that point at addon code
versions. If you restored a DB from a date *before* a module upgrade
(e.g. you restored a dump from 2026-06-10 but `southbrook_premium_orchestration`
was upgraded on 2026-06-15), the module registry is at the newer
version on disk but the DB has the older `ir.module.module.latest_version`.
Recovery: re-run `-u southbrook_premium_orchestration` to sync the DB
forward, then restart.

**"The off-site rsync didn't fire — was it supposed to?"**

Not yet. `offsite-sync.sh` is a stub with `exit 0` at the top. The
second QNAP isn't in place yet. **When it arrives**: set
`OFFSITE_HOST`, set up SSH key auth `admin → admin`, remove the early
`exit 0`, add a crontab entry `30 4 * * * /share/.../offsite-sync.sh`
so it lands one hour after the primary backup finishes. Until then,
this is **expected to be a no-op**, not a failure.

## What the system is doing behind the scenes

The script `backup-odoo.sh` is a single bash file run by QNAP's
host-level `crond` (not by Odoo's `ir.cron`). At 03:00 it iterates the
8 sites, and for each site it:

1. `docker exec ${S}-postgres pg_dump -U odoo -F p ${S}` and pipes
   through `gzip -9` to `db/daily/<site>-YYYYMMDD.sql.gz`. Plain SQL
   format (not custom) so a `psql` restore works with no `pg_restore`
   dependency.
2. On Sundays (`date +%u = 7`), additionally writes
   `db/weekly/<site>-YYYY-WNN.sql.gz` and `filestore/weekly/<site>-filestore-YYYYMMDD.tar.gz`.
3. On the 1st of the month, additionally writes the monthly variants.
4. After dumps, `find <site>/db/daily -mtime +14 -delete` etc. for
   each retention class.
5. Snapshots `docker-compose.yml` + a redacted `odoo.conf` (admin
   password stripped) into `config/latest/`.
6. Computes a `manifest.json` at the end with per-artifact size +
   sha256 prefix + mtime, written to `_meta/manifest.json`.
7. Tee'd stdout+stderr lands in `_meta/logs/backup-YYYYMMDD.log`.

`set -uo pipefail` (not `-euo`) so legitimate non-zero exits like
"glob with no match" don't abort the run; `nounset` + `pipefail`
still catch real bugs.

The script does **not** run inside any Odoo container — it runs on the
QNAP host, talks to each site's `${S}-postgres` and `${S}-odoo`
containers via `docker exec`. This decoupling is intentional: an Odoo
DB upgrade or container restart doesn't interrupt the backup, and a
backup script bug doesn't block Odoo from running.

## Quiz (5 questions, applied)

**1.** A user reports "I deleted a Kitchen Project today and need it
back." It's 11 AM. What dump do you restore from, and what's the
gotcha?

> The most recent daily dump (last night's, at
> `db/daily/southbrook-YYYYMMDD.sql.gz` where YYYYMMDD = today). The
> gotcha: any sale orders, configurator sessions, or work orders
> created **today** will be wiped by the restore. Confirm with the
> user that they accept a 24-hour rollback before proceeding — if
> not, the answer is "we cannot restore one record without restoring
> the whole DB; please re-enter the project."

**2.** It's Monday morning. You SSH in and
`db/daily/southbrook-` shows dumps from Friday and Saturday but
nothing for Sunday or this morning. The log dir shows
`backup-20260613.log` (Saturday) but no Sunday or Monday log. What
happened?

> The cron didn't fire on Sunday night. Most likely the QNAP was
> rebooted between Saturday's run and Sunday at 03:00 and the
> user-mode crontab got wiped (crontab edited via `crontab -e`
> instead of the persistent file). Recovery: check
> `/etc/config/crontab` for the `0 3 * * *` entry, restore if
> missing, `crontab /etc/config/crontab && /etc/init.d/crond.sh
> restart`, then re-fire today's backup manually to plug the gap.

**3.** Disk usage on `/share/CACHEDEV3_DATA` is at 92%. What's the
fastest legitimate cleanup that doesn't put data at risk?

> Don't touch the retention-pruned dump tree. The fastest legitimate
> cleanup is the QNAP `Container/scripts/` logs (the backup log dir
> is bounded by retention but `Container/` may hold other log trees).
> If the dump tree is genuinely the bloat, check
> `du -sh /share/CACHEDEV3_DATA/OdooIQ-Backups/*` — a site with
> 800 GB indicates the retention pruning has stopped working; fix the
> script's `find -mtime -delete` block before deleting anything by
> hand.

**4.** A restore worked, Odoo boots, but `/web/login` returns 500
with "Circular assets bundle: web.assets_frontend >
web.assets_frontend". You haven't run `-u` yet. What's wrong?

> The ormcache is poisoned by the restore — the registry on disk is
> ahead of the asset records the dump carried. Restart the Odoo
> container (`docker restart southbrook-odoo`). If that doesn't
> clear it, the dump pre-dates a module upgrade and you need to
> run `-u <module>` against the module that was upgraded between
> the dump date and now (typically the most recently deployed
> custom addon).

**5.** The off-site rsync stub is logging "exit 0" every night. Is
this a bug?

> No — by design. The second QNAP isn't in place yet, so
> `offsite-sync.sh` is a placeholder that exits 0 immediately and
> writes nothing. The fact that it logs at all means the cron is
> wired correctly; when the second QNAP arrives, edit the script's
> top to remove the early exit, set `OFFSITE_HOST` and SSH key auth,
> and the same cron entry begins doing real work.

---

## What this lesson does NOT cover

- Premium Orchestration's six in-Odoo crons → **lesson 7.1**.
- The external Hermes Console queue at hermes.odooiq.com, where the
  `backup_health` agent loop is supposed to file a recommendation when
  a backup is stale or failed (see `BackupHealthLoop` in
  `hermes-console/api/agent_loops.py`). The loop reads the same
  artifact tree and emits a queued recommendation when the most recent
  backup is older than `HERMES_BACKUP_MAX_AGE_HOURS` or the outcome
  was failure. Approval + apply flow → **lesson 7.3**.
- A `southbrook_premium_orchestration` "backup stale" recommendation
  that surfaces inside Odoo's *Kitchen Ops → MI Status* is **planned
  but not yet implemented** in the addon at the time of writing. Once
  it lands, the in-Odoo signal will mirror the Hermes Console signal;
  lesson 7.3 covers the external path until then.
- Cloudflare tunnel + Cloudflare Access OTP for the SSH path →
  separate platform doc (`~/.claude/projects/-Users-naadmin/memory/qnap_cloudflared_ssh_tunnel.md`).
- General Postgres administration → external docs; this lesson covers
  only the restore commands you need to run.
