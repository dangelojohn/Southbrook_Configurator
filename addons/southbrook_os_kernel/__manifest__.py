# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook OS Kernel",
    "summary": "Platform operating-system layer: AI kernel, kill-switches, "
               "shared memory, agent budgets, tool registry.",
    "description": """
Southbrook OS Kernel
=====================

The platform's operating-system layer (SBV2 doc 03). A near-leaf module by
design — depends on nothing Southbrook-specific, so anything may depend on
it. Provides:

* **AI Kernel** (`southbrook.os.ai.kernel`, AbstractModel) — the single
  ``run()`` entry point every AI feature is meant to route its chat-
  completion calls through, so kill-switches, budgets, and the ledger are
  always honoured. Never raises; always returns a result dict.
* **Kill-switch registry** (`southbrook.os.switch`) — a master switch plus
  per-feature switches any AI/agent/integration surface can gate itself on.
* **AI request ledger** (`southbrook.os.ai.request`) — one row per kernel
  call (done/error/blocked), with token/cost/duration accounting.
* **Shared memory** (`southbrook.os.memory`) — a namespaced key/value store
  with optional TTL expiry, for cross-feature/cross-agent state.
* **Agent registry + daily budgets** (`southbrook.os.agent`) — call/token
  budgets per named agent, reset daily by cron.
* **Tool registry** (`southbrook.os.tool`) — a manifest of callable HTTP
  surfaces (path, method, auth) for agent/tool-calling consumers.

Ships dark: the master AI switch (`os.ai.enabled`) is seeded **disabled**.
No existing feature is refactored onto the kernel in this PR — that
migration happens one feature per branch, later.
""",
    "author": "Southbrook Cabinetry / OdooIQ",
    "website": "https://southbrookcabinetry.space",
    "license": "LGPL-3",
    "category": "Technical",
    "version": "19.0.1.0.0",
    "depends": [
        "base",
        "mail",
    ],
    "data": [
        "security/groups.xml",
        "security/ir.model.access.csv",
        "data/os_switch_seed.xml",
        "data/os_tool_seed.xml",
        "data/ir_cron.xml",
        "views/os_switch_views.xml",
        "views/os_ai_request_views.xml",
        "views/os_memory_views.xml",
        "views/os_agent_views.xml",
        "views/os_tool_views.xml",
        "views/menu.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
