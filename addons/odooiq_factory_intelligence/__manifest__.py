# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "OdooIQ Factory Intelligence",
    "version": "19.0.1.0.0",
    "summary": "Manufacturing intelligence layer for Odoo: data-health audit, "
               "shadow scheduling, calibration and delivery confidence.",
    "description": """
OdooIQ Factory Intelligence
===========================
A machine-agnostic manufacturing intelligence layer that turns any shop's
standard Odoo MRP data into a delivery-confidence, explanation and data-health
product.

Step 1 (this build): the read-only Factory Intelligence Audit + Readiness engine
— the acquisition wedge. Observes MRP data, never mutates it.
    """,
    "author": "OdooIQ",
    "website": "https://odooiq.com",
    "license": "LGPL-3",
    "category": "Manufacturing",
    "depends": ["mrp"],
    "data": [
        "security/oiq_security.xml",
        "security/ir.model.access.csv",
        "views/oiq_factory_audit_views.xml",
        "data/ir_cron.xml",
    ],
    "application": True,
    "installable": True,
}
