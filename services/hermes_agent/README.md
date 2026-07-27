# HERMES Agent Sidecar

This service is the lightweight HERMES runtime for Southbrook. In Odoo the
human-facing identity is Fabio. The sidecar calls Odoo through the
`southbrook_hermes` addon and can only create draft recommendations. Human
approval inside Odoo is required before any work is applied.

The optimized QNAP setup runs this as a passive long-running container beside
Odoo. It does not create recommendations on startup and it does not run a
scheduled autonomous loop yet. Manual/test commands can create draft
recommendations when needed.

## Configuration

Required environment variables:

- `HERMES_ODOO_BASE_URL`
- `HERMES_ODOO_API_KEY`

Optional environment variables:

- `HERMES_MODEL_PROVIDER` defaults to `google`
- `HERMES_MODEL` defaults to `gemini-3.5-flash`
- `HERMES_TIMEOUT_SECONDS` defaults to `30`
- `HERMES_SERVICE_INTERVAL_SECONDS` defaults to `300`

External AI provider keys, such as `GOOGLE_API_KEY` or `OPENAI_API_KEY`, are
runtime secrets and must not be committed to git. The default Gemini model is
intended for free-tier testing; Google notes that free-tier content may be used
to improve its products.

## QNAP Compose Service

The repo `docker-compose.yml` defines `hermes-agent` with no public ports. It
uses the internal Docker network URL `http://odoo:8069` and the Odoo API key
from `HERMES_ODOO_API_KEY`.

Local/dev commands:

```bash
make hermes-build
make hermes-restart
make hermes-check
make hermes-recommend-test
```

On the QNAP production host, run the equivalent targets or compose commands
from `/share/CACHEDEV3_DATA/Container/southbrook` using QNAP's
`system-docker compose`, as documented in the repo guidelines.

## Local Test

```bash
python3 -m unittest discover -s services/hermes_agent/tests
```

## Runtime Commands

Run the passive sidecar loop:

```bash
python -m hermes_agent.main serve
```

Validate required runtime configuration:

```bash
python -m hermes_agent.main check
```

Create one manual draft recommendation:

```bash
python -m hermes_agent.main recommend \
  --name "Review estimate" \
  --summary "Fabio found a discrepancy for a human to review." \
  --type note
```
