# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook AI Design",
    "summary": "Gemini-backed room-analysis service. Reads a kitchen photo, "
               "produces a sb.kitchen.ai.analysis + sb.kitchen.appliance "
               "records per the G3 contract.",
    "description": """
Southbrook AI Design (Module 6)
================================

Implements the G3 contract at docs/api_contracts/gemini_odoo_contract.md.

Components:

* sb.gemini.prompt.template — versioned prompts stored as records so a
  prompt rev does not require a code deploy (per ai_prompt_spec.md §3).
* southbrook.gemini.client (AbstractModel) — the caller. Handles auth,
  schema validation, retry/backoff per G3 §6, and idempotency via
  image-hash dedup.
* sb.kitchen.project extension — analyze_photo(attachment_id) orchestrates
  the flow; consume_gemini_analysis(payload) lands the data.

Two backends:

* Real Gemini — set ir.config_parameter `gemini.api_key`; the client
  POSTs to https://generativelanguage.googleapis.com/ ...
* Mock — set ir.config_parameter `gemini.use_mock = True`. Returns a
  canned payload from data/mock_responses/default_kitchen.json so tests
  + dev work without an API key or network access.

Failure modes per G3 §6:
  network / auth / quota / malformed JSON / schema mismatch / out-of-range
  — each has explicit handling; some retry, some surface immediately,
  none partially-land.

Idempotency contract (G3 §7): (project_id, image_hash) is the key; a
duplicate call returns the existing analysis record unchanged.

GAP-02 gate: every record this module creates has confirmed_by_human=False.
The designer confirms in the workspace before is_ready_for_config_engine()
returns True and Module 7 (config engine) proceeds.
""",
    "author": "Southbrook Kitchens / OdooIQ",
    "license": "LGPL-3",
    "category": "Manufacturing",
    "version": "19.0.0.1.0",
    "depends": [
        "base",
        "southbrook_kitchen_workspace",
    ],
    # httpx is imported lazily inside _call_gemini_real(). Mock mode
    # (the default; controlled by ir.config_parameter `gemini.use_mock`)
    # has no Python deps beyond stdlib. If you flip to the real backend,
    # `pip install httpx` in the Odoo container or bake it into the image.
    "data": [
        "security/ir.model.access.csv",
        "data/prompt_template_default_v1.xml",
        "data/config_parameters.xml",
        "views/sb_gemini_prompt_template_views.xml",
        "views/sb_kitchen_project_views.xml",
        "views/southbrook_ai_design_menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
