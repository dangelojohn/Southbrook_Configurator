# SPDX-License-Identifier: LGPL-3.0-only
"""GET /sb/qr/defect-sheet — printable defect-type QR wallpaper.

Renders one QR per defect_type in the southbrook.mi.check
DEFECT_TYPES selection. Operator pins to a floor board, scans + a
cabinet/WO QR → NCR drafts with that defect_type pre-filled.

Each QR encodes sb://defect/<defect_type_key>?t=...&s=... — the
'defect' kind handler in qr_kind_handlers.py reads the ident
(via request.qr_parsed_ident) and creates the NCR.

No auth restriction beyond Odoo session — the print page is for
internal use. Operator scans paper, the scan endpoint enforces ACL.
"""
import base64
import io

from odoo import http
from odoo.http import request


class DefectSheetController(http.Controller):

    @http.route("/sb/qr/defect-sheet", type="http", auth="user",
                methods=["GET"], website=False)
    def defect_sheet(self, **kw):
        env = request.env
        Check = env["southbrook.mi.check"]
        try:
            import qrcode
        except ImportError:
            return request.make_response(
                "qrcode python lib not installed on this Odoo container",
                headers=[("Content-Type", "text/plain")])
        Payload = env["southbrook.qr.payload"].sudo()
        try:
            defect_types = dict(Check._fields["x_sbk_defect_type"].selection)
        except Exception:  # noqa: BLE001
            defect_types = {}
        if not defect_types:
            return request.make_response(
                "No defect types found on southbrook.mi.check.x_sbk_defect_type",
                headers=[("Content-Type", "text/plain")])
        cells = []
        for key, label in defect_types.items():
            try:
                payload = Payload.build("defect", key)
                img = qrcode.make(payload, box_size=5, border=2)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                qr_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            except Exception:  # noqa: BLE001
                qr_b64 = ""
            cells.append(
                f'<div style="width:2.5in;height:3in;border:1px solid #ccc;'
                f'page-break-inside:avoid;display:flex;flex-direction:column;'
                f'align-items:center;justify-content:space-between;'
                f'padding:0.1in;margin:0.05in;background:#fff">'
                f'<div style="font-size:9pt;color:#666;text-align:center">'
                f'DEFECT TYPE</div>'
                f'<img src="data:image/png;base64,{qr_b64}" '
                f'style="display:block;max-width:90%;max-height:60%"/>'
                f'<div style="font-size:13pt;font-weight:bold;text-align:center;'
                f'word-break:break-word">{label}</div>'
                f'<div style="font-size:8pt;color:#999;font-family:monospace">'
                f'{key}</div>'
                f'</div>'
            )
        # W085 (R5.11) — mobile viewport for in-browser preview.
        # The print path is unaffected (the @page rule still drives
        # the printed PDF), but on a phone the page now scales to
        # the device width instead of horizontal-scrolling at the
        # fixed letter-paper aspect.
        body = (
            "<html><head><title>Defect QR Sheet</title>"
            "<meta name=\"viewport\" content=\"width=device-width, "
            "initial-scale=1, viewport-fit=cover\">"
            "<style>"
            ".sb-defect-sheet-wrapper { min-width: 320px; }"
            "@media print { @page { size: letter; margin: 0.25in } "
            "  body { margin: 0; } "
            "  .header { display: none } }"
            "</style></head>"
            "<body style='margin:0;padding:0.2in;font-family:system-ui;background:#f6f6f6'>"
            "<div class='sb-defect-sheet-wrapper'>"
            "<div class='header' style='padding:0.2in 0;text-align:center'>"
            "<h2>Defect Type QR Sheet — Southbrook Floor</h2>"
            "<p style='color:#666;margin:0.3em 0'>"
            "Scan one of these + a cabinet/WO QR to draft an NCR. "
            "Pin to the floor board.</p>"
            "<button onclick='window.print()' "
            "style='padding:0.5em 1em;font-size:1em;cursor:pointer'>"
            "Print</button>"
            "</div>"
            "<div style='display:flex;flex-wrap:wrap;justify-content:center'>"
            + "".join(cells) +
            "</div>"
            "</div>"
            "</body></html>"
        )
        return request.make_response(body, headers=[
            ("Content-Type", "text/html; charset=utf-8")])
