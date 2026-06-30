# Gemini Go-Live Checklist

**Date:** 2026-06-15
**Owner:** Southbrook Cabinetry — Premium MRP Orchestration (Phase 3.1)
**Scope:** Flip `southbrook_ai_design` from mock-driven to live Gemini API calls.

---

## Prerequisite

A paid Gemini API key from <https://aistudio.google.com> (fastest) or a
service-account key from Google Cloud Vertex AI (preferred for ops). The
target model is `gemini-2.5-pro`. Pricing at the time of writing is roughly
**$0.10 – $0.50 per `sb.kitchen.ai.analysis` record** — well inside
rounding-error at our throughput, but log the key under the AI cost-centre.

---

## Steps

1. **Get the API key.** Sign in to <https://aistudio.google.com>, create a key,
   copy it once (you cannot re-display it).
2. **Open the activation wizard.** Either:
    - Settings → Technical → Actions → "Activate Gemini" (`action_gemini_activation_wizard`); or
    - Kitchen Ops → Generative → Activate Gemini (once the menu lands in Phase 3.5).
3. **Paste the key.** Leave model at `gemini-2.5-pro`, leave both toggles on,
   click **Apply**. The wizard:
    - writes `ir.config_parameter.gemini.api_key`,
    - pings the model with a one-token request,
    - flips `gemini.use_mock` to `False` if and only if the ping returned 200.
   A green notification means the integration is live.
4. **Trigger one real analysis.** Create one `sb.kitchen.project` with a real
   uploaded test image. Watch the activator's `production_call_count` go from
   0 → 1, and `sb.kitchen.ai.analysis` gain a new row. Open the row and confirm
   `raw_response_json` is real model output, not the mock fixture.
5. **Verify the prompt guardrail.** Open
   `sb.gemini.prompt.template` → the active row — confirm the prompt still says
   *"NEVER recommend cabinets"* (room understanding only; cabinet recommendations
   are the planner's job, not the LLM's).
6. **Document the first analysis in the pitch deck.** Take a screenshot of the
   analysis form and the project's "AI Analysis" smart-button — that's the proof
   the AI claim is real.

---

## Rollback

Open the Gemini Activator record → click **Revert to Mock**. This sets
`gemini.use_mock` back to `True`; the next call falls back to
`data/mock_responses/default_kitchen.json`. The key stays in
`ir.config_parameter` (no key rotation required).

---

## Risk & Mitigation

The Gemini API key sits in `ir.config_parameter` as **cleartext** —
readable by any `base.group_system` user. For production, prefer
`tools.config['gemini_api_key']` injected at the container level via
`odoo.conf`, and treat the wizard as a **dev / verification tool only**.
The QNAP container stack should bake the key into
`/etc/odoo/odoo.conf` from a sealed secret store, not the database.
