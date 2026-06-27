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
    "version": "19.0.0.8.0",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry",
    "category": "Manufacturing",
    # W035 (R8.14, 2026-06-27): hr depends added — scan log gains
    # `employee_id` and /sb/qr/identify resolves hr.employee.pin.
    "depends": ["base", "web", "mail", "stock", "hr"],
    "data": [
        "security/ir.model.access.csv",
        "data/qr_kit_config_parameters.xml",
        "data/shipping_unit_seed.xml",
        "data/truck_load_seed.xml",
        "views/southbrook_qr_scan_log_views.xml",
        "views/shipping_unit_views.xml",
        "views/truck_load_views.xml",
        "wizards/southbrook_qr_label_print_wizard_views.xml",
    ],
    "external_dependencies": {
        "python": ["qrcode"],
    },
    # W036 (R8.7, 2026-06-27) — scan-success/fail audio cues for the
    # tablet/handheld scan flow. Loads into web.assets_backend AND
    # web.assets_frontend so both backend OWL clients and any public
    # PWA scan UI emit the same beep. Self-installs by patching the
    # global fetch + XMLHttpRequest layers; default = unmuted.
    # W035 (R8.14, 2026-06-27) — operator PIN modal + top-bar badge
    # also bundled into BOTH backend and frontend so the operator
    # identity follows the kiosk regardless of which Odoo surface
    # the tablet happens to be on.
    # W038 (R8.5, 2026-06-27) — Night-shift dark mode. SCSS + toggle
    # JS bundled into BOTH backend and frontend so kanban, scan modal,
    # POD page, and traveler-print preview all honour the same body
    # class. Default OFF — day-shift users see zero visual change.
    "assets": {
        "web.assets_backend": [
            "southbrook_qr_kit/static/src/js/scan_audio_cue.js",
            "southbrook_qr_kit/static/src/js/operator_pin_modal.js",
            "southbrook_qr_kit/static/src/scss/operator_pin_modal.scss",
            "southbrook_qr_kit/static/src/js/dark_mode_toggle.js",
            "southbrook_qr_kit/static/src/scss/dark_mode.scss",
        ],
        "web.assets_frontend": [
            "southbrook_qr_kit/static/src/js/scan_audio_cue.js",
            "southbrook_qr_kit/static/src/js/operator_pin_modal.js",
            "southbrook_qr_kit/static/src/scss/operator_pin_modal.scss",
            "southbrook_qr_kit/static/src/js/dark_mode_toggle.js",
            "southbrook_qr_kit/static/src/scss/dark_mode.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
