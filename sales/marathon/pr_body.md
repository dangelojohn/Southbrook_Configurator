## Summary

Four new Odoo addons + sales kit + SDKs + CI/deploy infra implementing the Sternberg-framed "Project as spine" architecture for cabinet-shop manufacturing, with Marathon Hardware as the white-label channel partner.

- **kitchenforge_core** — project-template-as-spine + AI-agent filesystem at `/agent/v1/files` (magicpath.ai/files-style navigable tree) + typed tool catalog at `/agent/v1/tools` (Claude/GPT/Gemini tool_use ready) + self-discovery manifest at `/.well-known/ai-agent.json`. Drops quote-to-released-MO from ~125 clicks to ~6.
- **kitchenforge_marathon** — channel-partner integration: spec.event telemetry stream (15-min cron flush to Marathon webhook), $8/cabinet rebate ledger (idempotent per SO), auto-RFQ draft on SO confirm filtering by `x_hardware_brand_id`, read-only `/agent/v1/marathon/{telemetry,rebates}` endpoints.
- **kitchenforge_saas** — multi-tenant control plane: tenant lifecycle (provision/suspend/resume/cancel), Stripe subscription stub with signature-verified webhook, 3 seed plans ($149 Marathon channel, $599 direct, $2500 enterprise), `/saas/v1/tenants` REST.
- **kitchenforge_southbrook_seed** — bridge addon filling the 4 KitchenForge template projects with 17 cabinet zones drawn from southbrook_estimating's 12 locked product templates per CLAUDE.md §3.

Plus:
- 5-doc Marathon sales kit (deck, 1-pager, conservative/base/aggressive ROI calc, 3 cold-email variants + send-ready outreach, CTO technical appendix)
- OpenAPI 3.1 spec + Python SDK (18/18 unit tests pass) + TypeScript SDK
- Claude `tool_use`, OpenAI function-calling, MCP-bridge integration examples
- Forgejo Actions CI (lint/test/deploy-staging)
- `deploy_kitchenforge.sh` (flock-wrapped per QNAP cache-reset recipe) + `provision_tenant.sh` (codifies the 7-demo-stack pattern from memory)
- Helm chart skeleton (future k8s target)
- Makefile KF targets

## Verification

```
$ python3 deploy/smoke_test_kitchenforge.py

Phase 1 (addon hygiene): 4 addons, 45+ .py, 21+ .xml, ~3,800 LoC
Phase 2 (code smells): clean
Phase 3 (cross-addon refs): clean
Phase 4 (sales kit): 5 files present
Phase 5 (SDKs): openapi:✓ python:4 ts:3 examples:3
Phase 6 (deploy infra): 2 scripts, CI workflow present

errors: 0   warnings: 0
```

## Test plan

- [ ] Forgejo CI lint + test jobs pass on `linux-amd64` runner
- [ ] `make deploy-staging` lands on southbrook stack
- [ ] Backend smoke: KitchenForge ▸ New Kitchen Project ▸ Full Kitchen → instantiate → confirm SO → MO auto-confirms via auto-applied `manufacture` route
- [ ] Agent surface smoke: `curl -H "X-Api-Key: …" https://southbrookcabinetry.space/agent/v1/files/templates` returns the 4 templates with 17 zones populated
- [ ] Marathon hooks smoke: confirm a SO with a configurator line — verify `kitchenforge.marathon.rebate` row created AND draft `purchase.order` exists against the Marathon partner

🤖 Generated with [Claude Code](https://claude.com/claude-code)
