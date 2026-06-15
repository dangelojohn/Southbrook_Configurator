# KitchenForge Core

Project-template-as-spine for kitchen MRP, with an AI-agent-native
filesystem surface.

## What it does

- **`project.project.is_template`** + seed templates (Full Kitchen, Partial
  Reno, Single Custom, Vanity).
- **One-click instantiation wizard** that creates a Project + draft Sale
  Order with cabinet zones pre-populated from the template.
- **Auto-route to manufacture** on every `config_ok` product template —
  SO confirm spawns confirmed MOs through procurement, no
  Manufacturing-app side trip.
- **AI-Agent filesystem** at `/agent/v1/files/*` — magicpath.ai/files-style
  navigable tree (templates / projects / catalog / shop) that LLM agents
  can list, read, mutate.
- **Typed tool catalog** at `/agent/v1/tools` — JSON-Schema'd actions
  (`instantiate`, `add_zone`, `confirm_quote`, `release_mos`, `raise_eco`)
  for direct `tool_use` binding by Claude/GPT/Gemini.
- **Self-discovery manifest** at `/.well-known/ai-agent.json`.

## The 6-click salesperson flow

```
1. KitchenForge ▸ New Kitchen Project
2. Pick template + customer + room dims
3. ▸ Instantiate         → draft SO + Project, zones pre-populated
4. (Edit any zone inline if needed)
5. ▸ Confirm Quote       → MO auto-confirms via manufacture route
6. ▸ Plan                → work orders fire
```

Replaces the ~125-click status quo.

## AI Agent surface

```
GET  /agent/v1/files                  → root namespace listing
GET  /agent/v1/files/templates        → list templates
GET  /agent/v1/files/templates/full-kitchen-build.yaml
GET  /agent/v1/files/projects/42.yaml → project 42 manifest
PUT  /agent/v1/files/projects/42/zones/001-base-600.yaml
                                      → edit a zone (ETag concurrency)

GET  /agent/v1/tools                  → JSON-Schema tool catalog
POST /agent/v1/tools/instantiate      → kick off a project from a template
POST /agent/v1/tools/confirm_quote
POST /agent/v1/tools/release_mos
POST /agent/v1/tools/raise_eco

GET  /.well-known/ai-agent.json       → agent self-discovery
```

All routes use `X-Api-Key` (per-user, from southbrook_api) and the
`Idempotency-Key` header for retry safety.

## Dependencies

`southbrook_project_mrp`, `southbrook_estimating`, `product_configurator_sale`,
`product_configurator_mrp`, `southbrook_hardware_catalog`, `southbrook_api`.

## Tests

`-d <db> -i kitchenforge_core --test-tags kitchenforge`

## License

LGPL-3
