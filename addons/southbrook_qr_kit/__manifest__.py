# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook QR Kit",
    "summary": "Shared QR-code foundation: HMAC-signed payloads, scan "
               "controller, scan log, print wizard, kind-registry pattern.",
    "description": """
Southbrook QR Kit
=================

Foundation addon for all QR-driven workflows across Southbrook.
Provides:

- `southbrook.qr.payload` service — HMAC-SHA256 signed payloads of
  the form `sb://<kind>/<id>?t=<unix>&s=<hmac>`. The HMAC secret is
  stored in `ir.config_parameter` `southbrook.qr_kit.hmac_secret`
  (auto-generated on first use; 32 bytes urlsafe).
- `/sb/qr/scan` controller — single entry point for every QR scan.
  Resolves the kind to a registered handler, enforces ACL, logs the
  scan, returns JSON or HTML redirect depending on request.
- `southbrook.qr.scan.log` model — append-only audit of every scan.
- "Print QR Label" wizard — generic per-model QWeb report renderer.
- "Recent Scans" tile pattern for dashboards.

KIND REGISTRY:

  Other addons register their kinds via subclassing `QrKindHandler`:

      class AsbuiltKind(models.AbstractModel):
          _name = "southbrook.qr.kind.asbuilt"
          _inherit = "southbrook.qr.kind"
          _kind_name = "asbuilt"
          _target_model = "southbrook.asbuilt"
          _default_action = "open"

  This file pulls them from the registry — no central kind list.

SECURITY:

  HMAC is the forgery defense, not a permission gate. ACL on the
  target model is still enforced. A malicious actor with a stolen
  secret could still only do what their Odoo user is allowed to do.

  Optional `expires_in_seconds` per kind — handles "one-time use"
  receipts (e.g. ephemeral POD QRs that expire in 24h).
""",
    "version": "19.0.0.1.0",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry",
    "category": "Manufacturing",
    "depends": ["base", "web", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/southbrook_qr_scan_log_views.xml",
        "wizards/southbrook_qr_label_print_wizard_views.xml",
        "data/qr_kit_config_parameters.xml",
    ],
    "external_dependencies": {
        "python": ["qrcode"],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
