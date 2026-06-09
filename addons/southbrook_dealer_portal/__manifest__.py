# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook Dealer Portal",
    "summary": "Dealer-channel portal surfaces: 50%-off pricing visibility, "
               "KD flat-pack export variant, dealer-order entry.",
    "description": """
Southbrook Dealer Portal (Module 9 — Phase 1)
==============================================

Extends the customer portal with the dealer-channel surface:

* `/my/dealer/orders`              — dealer's sale orders + production packages
* `/my/dealer/order/<so_id>`       — order detail with 50%-off pricing
* `/my/dealer/order/<so_id>/kd`    — KD flat-pack export endpoint

KD (Knock-Down) export — Module-9 first-class capability:
  sb.production.package.export_kd_envelope() emits a JSON payload with
  pre-drilled hardware hole positions per panel (SYN-05) plus a 'shipped
  knocked-down, assembled on site' flag. The Central Kitchens channel
  consumes it. Round-trip stub for now; the consumer-side cabling lands
  when a Central Kitchens dealer is signed.

Dealer pricing surface:
  Uses the existing res.partner.channel = 'dealer' from southbrook_estimating
  + the dealer pricelist (50%-off retail). The portal view exposes
  list/dealer columns side-by-side so the dealer can show the
  customer-facing price + their margin clearly.

Tests as anonymous SECOND dealer per ACL discipline.

Outstanding:
- Installation-drawing PDF (GAP-06) — needs a separate FreeCAD TechDraw
  elevation output; gated on Module 2 G2a + the elevation script.
""",
    "author": "Southbrook Kitchens / OdooIQ",
    "license": "LGPL-3",
    "category": "Manufacturing",
    "version": "19.0.0.1.0",
    "depends": [
        "southbrook_customer_portal",
        "southbrook_kitchen_mrp",
        "sale",
    ],
    "data": [
        "security/dealer_portal_security.xml",
        "security/ir.model.access.csv",
        "views/dealer_portal_templates.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
