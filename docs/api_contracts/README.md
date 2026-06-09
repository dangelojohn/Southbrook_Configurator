# API contracts

Per-contract specs live here. Each contract is a load-bearing artifact —
downstream modules cannot start until the relevant contract is signed off.

| Contract | Owner module | Status | Gate it unblocks |
|---|---|---|---|
| `gemini_odoo_contract.md` | Module 6 (`southbrook_ai_design`) | TODO | G3 |
| `flutter_odoo_contract.md` | Flutter app | TODO | G6 |
| `bridge_webhook.md` | Module 2 (`southbrook_freecad_bridge`) | TODO | — |

See `CLAUDE_CODE_PROJECT_INIT.md` §7 (Critical Gates Summary) at repo root for
the full gate dependency graph. Each contract file must include: schema (JSON
Schema preferred), failure modes, auth mechanism, idempotency rules, and at
least one worked end-to-end example.
