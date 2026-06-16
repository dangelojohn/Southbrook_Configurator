# HERMES Agent Sidecar

This service is the lightweight HERMES runtime for Southbrook. It calls Odoo
through the `southbrook_hermes` addon and can only create draft
recommendations. Human approval inside Odoo is required before any work is
applied.

## Configuration

Required environment variables:

- `HERMES_ODOO_BASE_URL`
- `HERMES_ODOO_API_KEY`

Optional environment variables:

- `HERMES_MODEL_PROVIDER` defaults to `openai`
- `HERMES_MODEL` defaults to `gpt-5`
- `HERMES_TIMEOUT_SECONDS` defaults to `30`

External AI provider keys, such as `OPENAI_API_KEY`, are runtime secrets and
must not be committed to git.

## Local Test

```bash
python3 -m unittest discover -s services/hermes_agent/tests
```

## Manual Draft Creation

```bash
python -m hermes_agent.main \
  --name "Review estimate" \
  --summary "HERMES found a discrepancy for a human to review." \
  --type note
```
