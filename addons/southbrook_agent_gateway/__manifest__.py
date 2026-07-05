# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook AI Agent Gateway",
    "version": "19.0.1.0.0",
    "category": "Website/CRM",
    "summary": (
        "Machine-readable front door for AI shopping/research agents: "
        "llms.txt + OpenAPI + public offerings/quote-request endpoints "
        "that validate customer contact info and land it in Contacts + CRM."
    ),
    "description": """
Southbrook AI Agent Gateway
===========================
Lets a third-party AI agent (an AI shopping assistant acting for a
prospective customer) discover Southbrook, read what we offer, and
submit a quote request on its customer's behalf — with the customer's
contact information validated and captured as a res.partner (Contacts)
plus a crm.lead (CRM), and a double-opt-in verification email sent to
the human customer so we know the info is real.

Surface:
  * GET  /llms.txt                          — plain-text agent briefing
  * GET  /agent/api/v1/openapi.json         — machine-readable contract
  * GET  /agent/api/v1/offerings            — public catalog summary
  * POST /agent/api/v1/quote-request        — submit a quote request
  * GET  /agent/api/v1/quote-request/<ref>/status?token= — poll status
  * GET  /agent/verify/<token>              — customer email-verify link

Discoverability (origin side): appends an AI-agent-friendly section to
the website robots.txt field, injects LocalBusiness JSON-LD into the
public layout, and replaces the placeholder homepage meta description.
NOTE: the Cloudflare-managed robots.txt section (which currently sends
Disallow: / to GPTBot/ClaudeBot/etc.) is edge-injected and can only be
relaxed in the Cloudflare dashboard — an owner action, out of scope
for this module.
""",
    "author": "Southbrook Cabinetry",
    "license": "LGPL-3",
    "depends": [
        "southbrook_estimating",
        "sale",
        "website",
        "crm",
        "utm",
        "mail",
        "phone_validation",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "data/utm_data.xml",
        "data/res_partner_category.xml",
        "data/crm_tag.xml",
        "data/mail_template.xml",
        "views/agent_inquiry_views.xml",
        "views/website_templates.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
