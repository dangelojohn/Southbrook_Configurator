# HERMES Agent Implementation Plan

## Goal

Implement the approved hybrid sidecar plus small Odoo addon so HERMES can use
external AI APIs and Southbrook tools while only creating draft
recommendations/tasks that a human approves.

## Constraints

- Do not commit credentials.
- Reuse `southbrook_api` key authentication.
- HERMES-created Odoo records must start as drafts.
- Applying work must be gated by human approval.
- Keep v1 focused on project task creation after approval.

## Steps

1. Add tests for the Odoo recommendation workflow.
   - Validate draft creation.
   - Validate JSON payload constraints.
   - Validate approval is required before apply.
   - Validate an approved task recommendation creates a `project.task`.

2. Add tests for the HERMES API endpoint.
   - Missing/invalid key returns 401.
   - Bad JSON returns 400.
   - Valid payload creates a draft recommendation.

3. Add tests for the sidecar payload/client.
   - Configuration fails without required Odoo settings.
   - Payload builder emits a draft recommendation payload.
   - Client sends `X-Api-Key` and JSON.

4. Implement `addons/southbrook_hermes`.
   - Manifest, imports, security, access rules, views, menus.
   - `southbrook.hermes.recommendation` model.
   - `/hermes/api/v1/recommendations` controller.

5. Implement `services/hermes_agent`.
   - Python package, configuration, client, Dockerfile, README.
   - No real external AI provider call in v1; provider keys are runtime-only.

6. Add `southbrook_hermes` to the Makefile module list.

7. Verify.
   - Run sidecar unit tests.
   - Run targeted Odoo tests if the local Docker/Odoo stack is available.
   - Run `make test-quick DB=southbrook` when feasible.
