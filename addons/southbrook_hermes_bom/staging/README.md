# Hermes staging mock

This directory contains a tiny stand-in for the real Hermes research
endpoint so a developer (or a CI staging job) can exercise the
`southbrook_hermes_bom` wizard end-to-end without a real Hermes service.

It is **not** a unit test (those live under `tests/` and patch
`HermesService.research`); it is a runnable HTTP server that responds to
the same shape the production endpoint will.

## Files

- `mock_hermes_server.py` — standard-library HTTP server, no external
  deps. Binds to loopback by default. Validates the bearer token,
  parses the inbound payload, tailors a canned but product-aware
  response.
- `Dockerfile` — `python:3.12-slim` based image. Stdlib only — no pip
  install, no wheels, two layers.
- `docker-compose.yml` — long-lived service definition. Health-checked,
  restart=unless-stopped, published to host loopback only by default.

## Quick start

```bash
# 1. Run the mock (any Python 3.10+).
python3 staging/mock_hermes_server.py --port 7100 --token TEST-KEY-XYZ

# 2. Point the live southbrook_hermes_bom at it (Odoo shell or settings):
#    southbrook_hermes_bom.api_key      = TEST-KEY-XYZ
#    southbrook_hermes_bom.endpoint     = http://127.0.0.1:7100/v1/research
#
#    (If running Odoo inside docker on the QNAP and the mock on your
#    laptop, replace 127.0.0.1 with whatever the container can reach —
#    typically the host's docker0 gateway.)

# 3. Open a Configurable Template, click "Research & Build BOM with
#    Hermes", run the wizard. The dispatch hits THIS server and the
#    review pane fills with canned-but-shaped data.

# 4. Health probe (no auth required):
curl http://127.0.0.1:7100/health
# → {"ok": true}
```

### Or run it as a container

```bash
# Build + bring up the mock as a long-lived service.
docker compose -f staging/docker-compose.yml up -d --build

# Watch the request log.
docker compose -f staging/docker-compose.yml logs -f

# Reachable on the host's loopback (NOT the LAN) — same /health probe.
curl http://127.0.0.1:7100/health
```

The compose definition publishes the port on `127.0.0.1:7100` only. If
you need an Odoo container on a different docker network to reach the
mock, attach it via the `networks:` block at the bottom of
`docker-compose.yml`.

## Safety

- Defaults to `--host 127.0.0.1` so the mock can never be exposed
  accidentally. Override to `0.0.0.0` only when running on an
  isolated staging VM and you know what you're doing.
- The bearer-token check is real — wrong tokens return 401 — but the
  token itself ships as the default `TEST-KEY`. Rotate via `--token`
  for any non-toy use.
- The mock returns the same BOM lines (`HBOM-MOCK-A`, `HBOM-MOCK-B`)
  on every call. The wizard's BOM-line matcher won't resolve these
  unless you seed matching `product.product` records first — the
  wizard's chatter will list them as skipped, which is the correct
  behavior on a fresh DB.

## Adding more variation

Edit `_build_response` in `mock_hermes_server.py`. The function
receives the verbatim payload the wizard sent, so the response can
echo product name, attribute values, custom fields, etc. — handy for
demo screenshots.

## When to retire this

When a real Hermes endpoint is online (Vercel sidecar or otherwise),
flip `southbrook_hermes_bom.endpoint` to the real URL, flip the
`api_key` to the real token, and the wizard talks to production with
zero code change. The mock stays in-repo for offline development.
