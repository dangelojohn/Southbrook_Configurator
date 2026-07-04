# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook Hermes Product Research & BOM Builder",
    "version": "19.0.2.2.0",
    "summary": "AI-powered product research and BOM generation via Hermes agent",
    "description": """
Adds a wizard-driven research path to Configurable Templates and Configured
Variants. From the form, a Hermes Reviewer can dispatch a research job to an
external Hermes endpoint, review proposed enrichment + a derived BOM, and
selectively apply the changes back to the product.template / mrp.bom records.

Sibling module to southbrook_hermes (Fabio recommendation queue). The two
share no models, no security groups, and no ir.config_parameter namespace —
deliberately distinct so either can be installed without the other and so a
later refactor can fold them together cleanly if/when it makes sense.
""",
    "author": "Southbrook Cabinetry",
    "website": "https://southbrookcabinetry.space",
    "category": "Manufacturing",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "mrp",
        "product_configurator",
        "product_configurator_mrp",
    ],
    "data": [
        "security/hermes_security.xml",
        "security/ir.model.access.csv",
        "data/hermes_config_data.xml",
        "data/hermes_cron.xml",
        "views/hermes_research_job_views.xml",
        "views/hermes_wizard_views.xml",
        "views/product_template_views.xml",
        "views/product_product_views.xml",
        "views/hermes_menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "uninstall_hook": "uninstall_hook",
}
