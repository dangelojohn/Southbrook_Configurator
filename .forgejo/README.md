# Forgejo Actions

`workflows/tests.yml` is the CI pipeline. It boots the full docker-compose
stack (postgres + sami-odoo + freecad-bridge), installs every SAMI addon,
and runs `make test` (which is the same target you run locally).

## Runner setup

Workflows queue but do not execute until a Forgejo Runner is online and
advertising the right label.

The label `tests.yml` looks for: **`linux-amd64`**. If your runner
advertises a different label (default Forgejo runners advertise
`self-hosted`), either edit `runs-on:` here or relabel the runner.

### Quick runner install on the QNAP

```bash
# As admin on the QNAP. The runner installs to /share/CACHEDEV3_DATA/Container/forgejo-runner/.
curl -L https://code.forgejo.org/forgejo/runner/releases/download/v6.3.1/forgejo-runner-6.3.1-linux-amd64 \
  -o /usr/local/bin/forgejo-runner
chmod +x /usr/local/bin/forgejo-runner

# Register against the southbrook-v19cr repo (or org-wide). Token from
# https://192.168.68.108/git/-/admin/runners (admin-only) OR per-repo
# at /repo-name/settings/actions/runners.
forgejo-runner register \
  --instance http://192.168.68.108:9080 \
  --token <TOKEN> \
  --name qnap-runner-1 \
  --labels "linux-amd64,docker"

# Run as a daemon. Add to /etc/init.d/ or systemd as appropriate.
forgejo-runner daemon
```

The runner needs `docker` + `docker compose` on its PATH. The QNAP host
already has them in `/share/CACHEDEV3_DATA/.qpkg/container-station/bin`.

## What the pipeline does

1. **Checkout** the pushed ref
2. **Build images** — `sami-odoo:dev` (custom with Mako baked in) +
   `freecad-bridge` (~2.6 GB, cached aggressively after first run)
3. **Bring up the stack** — postgres + odoo + bridge
4. **Wait for health** — both postgres and odoo report healthy
5. **`make install`** — installs all 9 SAMI addons
6. **`make test`** — runs every `@tagged("southbrook")` test plus the
   18 render-smoke matrix
7. **On failure** — upload odoo + bridge logs as artifacts
8. **Tear down** — `docker compose down -v` always

## Cold-cache time budget

| Step | Cold | Warm |
|---|---|---|
| Build sami-odoo image | 30 s | <1 s |
| Build freecad-bridge image | 5 min | <1 s |
| Bring up postgres + healthy | 15 s | 15 s |
| Bring up odoo + healthy | 60 s | 60 s |
| Install 9 addons | 90 s | 90 s |
| Full test sweep | 30 s | 30 s |
| 18 render-smoke renders | 10 s | 10 s |
| **Total cold** | **~8 min** | |
| **Total warm** | | **~4 min** |

If you cancel the runner cache, the first build is 8 min; subsequent
runs reuse the layer cache and complete in ~4 min.

## Triggering manually

Use the Forgejo web UI: repo → Actions → tests workflow → "Run workflow".

Or via API:

```bash
curl -X POST -H "Authorization: token $TOKEN" \
  http://192.168.68.108:9080/api/v1/repos/qnap/southbrook-v19cr/actions/workflows/tests.yml/dispatches \
  -d '{"ref":"feature/module-0-skeleton"}'
```
