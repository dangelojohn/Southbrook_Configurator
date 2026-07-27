# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook Floor Traveler",
    "summary": (
        "P8 — Per-production-package PDF traveler with QR code, "
        "workcenter scan endpoint, and scan-driven tool-consumption "
        "telemetry. Closes the shop-floor scan loop without "
        "duplicating the existing mrp.workorder.button_finish path."
    ),
    "description": """
Southbrook Floor Traveler (audit P8)
====================================

Adds three pieces:

  1. **QWeb PDF traveler** (``ir.actions.report``) per
     ``sb.production.package`` with a QR code encoding the package id.
     Operators print one per shop-floor job.
  2. **Scan endpoint** ``/southbrook/api/floor-traveler/scan`` that
     advances the next ``mrp.workorder`` and calls the *existing*
     ``button_finish`` so the tool-consumption debit fires exactly
     once (no duplicate telemetry). The audit's load-bearing
     acceptance criterion.
  3. **Scan-log JSON field** on ``sb.production.package`` storing
     ordered scan events; surfaced as durations on the MI dashboard
     via the existing view extension points.

External dependencies:
  - ``qrcode`` (Python) for QR generation. Pure-Python; falls back
    to a tiny stub if the library isn't available so the addon
    still installs and the report renders without the QR image.
""",
    "author": "Southbrook Cabinetry / OdooIQ",
    "license": "LGPL-3",
    "category": "Manufacturing",
    "version": "19.0.2.0.0",
    "depends": [
        "mrp",
        "sale",
        "southbrook_kitchen_mrp",
        "southbrook_premium_orchestration",
        "southbrook_mrp_pm",
    ],
    # qrcode is a soft dependency. The QR computation gracefully falls
    # back to an empty image when the lib is missing (the traveler PDF
    # still renders with a "QR unavailable" placeholder). Declaring it
    # under external_dependencies would block installs on environments
    # without the lib — we'd rather degrade gracefully.
    "data": [
        # No security/ir.model.access.csv: this addon extends an existing
        # model (sb.production.package) via _inherit; existing ACLs apply.
        # P0 hard rule #2 explicitly bars widening existing permissions.
        "reports/floor_traveler_report.xml",
        "reports/floor_traveler_report_action.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
