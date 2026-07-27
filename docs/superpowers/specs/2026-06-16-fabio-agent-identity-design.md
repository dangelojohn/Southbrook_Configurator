# Fabio Agent Identity Design

## Decision

Fabio will be represented in Odoo as a contact (`res.partner`), not as an
internal login user.

This gives the Fabio/Fabio-agent work queue a real avatar-capable identity
without adding a user account, password, login, access rights, or seat-like
security concerns.

## Scope

The `southbrook_hermes` addon will create a partner record named `Fabio` with a
stable external ID. HERMES/Fabio recommendations will default to that partner
through a new `agent_partner_id` field.

The field will be visible in the recommendation list and form with Odoo's
avatar-capable many2one rendering.

## Data Flow

1. The sidecar posts a recommendation through `/hermes/api/v1/recommendations`.
2. The Odoo controller creates a `southbrook.hermes.recommendation`.
3. The model default assigns `agent_partner_id` to the Fabio partner.
4. Reviewers see Fabio as the recommendation's agent/source identity in Odoo.

## Boundaries

The following technical names remain unchanged:

- `southbrook_hermes`
- `southbrook.hermes.recommendation`
- `/hermes/api/v1/recommendations`
- `HERMES_...` sidecar environment variables
- Python class and package names

Fabio is the human-facing identity. HERMES remains the internal integration
codename.

## Not Included

- Creating an Odoo login user named Fabio.
- Giving Fabio access rights or an API key.
- Building a separate chat UI.
- Shipping a custom binary avatar image in v1. Odoo will render the partner as
  an avatar-capable contact and can be given a custom image later through the
  normal contact form.
