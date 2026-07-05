# SPDX-License-Identifier: LGPL-3.0-only
from . import controllers
from . import models

# Marker comment used to keep the robots.txt append idempotent across
# repeated -u upgrades (post_init_hook only runs on -i, but keep the
# guard anyway so a manual re-run can't duplicate the block).
_ROBOTS_MARKER = "# BEGIN southbrook_agent_gateway"

_ROBOTS_AI_SECTION = """
# BEGIN southbrook_agent_gateway — AI agent guidance
# Southbrook Cabinetry welcomes AI shopping/research agents for
# reference use. Machine-readable entry points:
#   /llms.txt                    — agent briefing
#   /agent/api/v1/openapi.json   — API contract (offerings + quote requests)
# Content-Signal: search=yes, ai-input=yes, ai-train=no

User-agent: GPTBot
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: Claude-User
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: OAI-SearchBot
Allow: /

User-agent: Google-Extended
Allow: /
# END southbrook_agent_gateway
"""

_PLACEHOLDER_META = "This is the homepage of the website"

_META_DESCRIPTION = (
    "Southbrook Cabinetry designs and manufactures custom kitchen "
    "cabinets — configurable base, wall, tall, drawer and vanity "
    "cabinetry across four series, with dealer, contractor and retail "
    "programs, an online kitchen designer, and fast quote turnaround."
)


def post_init_hook(env):
    """One-time origin-side discoverability fixes.

    1. Append the AI-agent robots.txt section to every website record's
       robots_txt field (Odoo serves this appended to its default
       /robots.txt output). Idempotent via _ROBOTS_MARKER.
    2. Replace the stock placeholder homepage meta description if it is
       still the untouched Odoo default. This is a plain FIELD write on
       the page record (website.seo.metadata mixin) — it does NOT touch
       the view arch, so it cannot trigger the website-builder COW fork
       hazard.
    """
    for website in env["website"].search([]):
        current = website.robots_txt or ""
        if _ROBOTS_MARKER not in current:
            website.robots_txt = (current + "\n" + _ROBOTS_AI_SECTION).strip() + "\n"

    homepages = env["website.page"].search([("url", "=", "/")])
    for page in homepages:
        if (page.website_meta_description or "").strip() in ("", _PLACEHOLDER_META):
            page.website_meta_description = _META_DESCRIPTION
