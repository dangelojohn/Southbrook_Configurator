# Southbrook Odoo DR Restore Runbook

**Audience:** anyone with admin SSH on the QNAP (`admin@192.168.68.108`).
**Last verified:** 2026-06-26 (Phase 9 of executive uplift).
**Target RPO:** 24h (next daily backup at 03:00 local).
**Target RTO:** 30 min (single-host restore).

## When to use this

- Postgres data file corruption (after a hard QNAP power cut).
- Accidental data wipe via Odoo UI (no soft delete).
- Failed module install left registry inconsistent and rollback can't recover.
- Pre-VPS-migration cutover validation.

## Pre-flight

1. SSH to QNAP:
   ```
   ssh admin@192.168.68.108
   export PATH=/share/CACHEDEV3_DATA/.qpkg/container-station/bin:$PATH
   export DOCKER_HOST=unix:///var/run/system-docker.sock
   ```
2. Identify the backup file:
   ```
   ls -lah /share/CACHEDEV3_DATA/OdooIQ-Backups/southbrook/db/daily/  | tail -5
   ls -lah /share/CACHEDEV3_DATA/OdooIQ-Backups/southbrook/db/ad-hoc/ | tail -5
   ```
   Pick the most recent `southbrook-YYYYMMDD.sql.gz` for daily, or a phase-specific `southbrook-prephaseN-*.sql.gz` for surgical recovery.
3. Decide target DB name. If overwriting live → `southbrook`. If parallel → `southbrook_restore_test`.

## Restore steps

### Option A — Restore to a parallel DB (safest, validates the backup)

```
# Create empty DB
docker exec southbrook-postgres createdb -U odoo southbrook_restore_test

# Stream backup in
zcat /share/CACHEDEV3_DATA/OdooIQ-Backups/southbrook/db/daily/southbrook-YYYYMMDD.sql.gz \
  | docker exec -i southbrook-postgres psql -U odoo -d southbrook_restore_test

# Spot-check row counts
docker exec southbrook-postgres psql -U odoo -d southbrook_restore_test -c \
  "SELECT 'sale_order' AS t, COUNT(*) FROM sale_order
   UNION ALL SELECT 'mrp_production', COUNT(*) FROM mrp_production
   UNION ALL SELECT 'account_move', COUNT(*) FROM account_move
   UNION ALL SELECT 'res_partner', COUNT(*) FROM res_partner;"
```

If counts look right, the backup is good.

### Option B — Overwrite live `southbrook` DB (DESTRUCTIVE)

**STOP** — make a fresh backup of current live first:
```
ts=$(date -u +%Y%m%dT%H%M%SZ)
docker exec southbrook-postgres pg_dump -U odoo -d southbrook -F p \
  | gzip > /share/CACHEDEV3_DATA/OdooIQ-Backups/southbrook/db/ad-hoc/southbrook-before-restore-${ts}.sql.gz
```

Then:
```
# Stop the Odoo container (workers will release DB connections)
docker stop southbrook-odoo

# Drop + recreate the DB
docker exec southbrook-postgres dropdb -U odoo southbrook
docker exec southbrook-postgres createdb -U odoo southbrook

# Stream backup in
zcat /share/CACHEDEV3_DATA/OdooIQ-Backups/southbrook/db/daily/southbrook-YYYYMMDD.sql.gz \
  | docker exec -i southbrook-postgres psql -U odoo -d southbrook

# Restart Odoo (will boot ~45s, run reentrant cache rebuild)
docker start southbrook-odoo

# Wait for healthy
for i in $(seq 1 12); do sleep 5; \
  H=$(docker inspect southbrook-odoo --format "{{.State.Health.Status}}"); \
  echo "[$i] $H"; [ "$H" = "healthy" ] && break; done
```

### Filestore (attachments)

The Postgres backup does NOT include `/var/lib/odoo/filestore/southbrook/`. For full restore you'll also need the latest filestore snapshot under `/share/CACHEDEV3_DATA/OdooIQ-Backups/southbrook/filestore/`. Rsync the directory back:
```
rsync -a --delete \
  /share/CACHEDEV3_DATA/OdooIQ-Backups/southbrook/filestore/YYYY-MM-DD/ \
  /share/CACHEDEV3_DATA/Container/southbrook/odoo-data/filestore/southbrook/
```

## Post-restore validation

1. Public login responds: `curl -sS -o /dev/null -w "%{http_code}\n" https://southbrookcabinetry.space/web/login` → 200
2. Spot-check Odoo version: `curl -X POST https://southbrookcabinetry.space/web/webclient/version_info` → `server_version`
3. Log in as admin, check 5 recent SOs, 5 recent MOs, 5 recent invoices look right.
4. Run a Hermes smoke if Hermes is active: `bash ~/southbrook-v19cr/scripts/smoke_hermes.sh`.

## Known traps

- `pg_restore` is NOT used — backups are `pg_dump -F p` (plain). Use `psql` to load.
- **Never `pg_resetwal`** or set `fsync=off` to "speed up" recovery. Per memory `qnap_postgres_recovery_hazard.md`, fsync crashes recover naturally — do not interfere.
- After Option B (live overwrite), the worker ormcache is stale → expect a "Circular assets bundle" 500 on the first /web/login hit. The container restart fixes it.

## Path to ≥99.9% (out of scope for this runbook)

Single-QNAP can't hit 99.9% by definition. The path is the **VPS migration** (Q-4 of the executive uplift):

1. Provision the VPS host (Hetzner CCX or AWS r6i.large).
2. Streaming replication slave on the QNAP → promote slave on failover.
3. PgBouncer in front for connection pooling.
4. cloudflared tunnel + WAF in front for ingress.
5. Off-site backup target (S3 / B2) for the daily dump.

That migration is a separate workstream from this uplift.

---
*Phase 9 of the Southbrook executive uplift — see `docs/superpowers/plans/2026-06-26-executive-uplift-to-7-of-10.md`.*
