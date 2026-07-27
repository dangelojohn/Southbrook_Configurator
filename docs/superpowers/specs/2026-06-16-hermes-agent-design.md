# HERMES Agent Design

## Decision

HERMES will run as a sidecar service beside Odoo and will integrate with Odoo
through a small addon named `southbrook_hermes`.

The sidecar may call external AI APIs and Southbrook tools. It may not directly
apply business changes in Odoo. Its Odoo write boundary is limited to creating
draft recommendation records for human review.

## Architecture

```
External AI APIs / tools
        |
        v
services/hermes_agent sidecar
        |
        | POST /hermes/api/v1/recommendations
        | X-Api-Key
        v
southbrook_hermes Odoo addon
        |
        v
Draft HERMES recommendations
        |
        v
Human approve / reject / apply
```

## Trust Boundary

The sidecar is trusted to propose work. Odoo remains the system of record and
the enforcement point for approval. HERMES-created records start in `draft`.

Only an Odoo user with HERMES reviewer access can approve or reject a
recommendation. Only an approved recommendation can be applied.

## Odoo Responsibilities

The addon owns:

- `southbrook.hermes.recommendation` records.
- The review queue menu, list, form, and search views.
- Workflow actions: mark ready, approve, reject, apply.
- API endpoint for creating draft recommendations.
- Audit trail through chatter fields and reviewer/date fields.

For v1, applying a `task` recommendation creates a `project.task`. Other
recommendation types can be approved or rejected, but they do not perform
autonomous production writes.

## Sidecar Responsibilities

The sidecar owns:

- Reading runtime configuration from environment variables.
- Building recommendation payloads.
- Posting draft recommendations to Odoo using `X-Api-Key`.
- Leaving model provider keys out of git.

The sidecar does not store Odoo credentials in source and does not bypass the
Odoo approval workflow.

## Runtime Fit On QNAP

This design is intentionally light enough for the existing QNAP host because
HERMES calls external AI APIs instead of serving a local model. The expected
runtime footprint is one small Python container plus Odoo addon code.

The host still needs normal operational controls: outbound HTTPS for model
providers, secret injection through environment variables, container restart
policy, logs, and backups for the Odoo database.

The QNAP sidecar runs passively by default. Container startup validates
configuration and keeps the process alive, but it does not create
recommendations automatically and does not poll Odoo on a schedule. Test or
operator-triggered recommendations use an explicit CLI command. Scheduled
agent behavior should be added later as a separate, reviewed feature after the
draft recommendation queue is stable.

For testing, the default model route is `google` / `gemini-3.5-flash`, selected
because it is free-tier capable and suitable for agent/coding-style checks.
Free-tier prompts must not include confidential production data.

## Out Of Scope

- Local GPU model hosting.
- Direct write access from HERMES to sales, MRP, accounting, inventory, or PLM
  records.
- Autonomous approval.
- Storing external AI API keys in Odoo source code.
