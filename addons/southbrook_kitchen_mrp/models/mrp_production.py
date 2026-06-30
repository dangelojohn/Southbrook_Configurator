# SPDX-License-Identifier: LGPL-3.0-only
"""mrp.production label extension — cabinet manufacturing label.

Computes the fields the Avery Presta 94215 cabinet label needs:
customer name (resolved through sale.order chain), PO ref, door
name + color, cabinet interior, code (SKU), hinge side, finished
sides; plus a QR PNG that resolves back to this MO on scan.

Read-only: nothing here mutates MO state. The QR points at the
backend record URL so an authenticated operator scans → lands on
the MO form. If/when southbrook_qr_kit is on this branch, swap the
URL builder to use the signed `sb://mo/<id>` pattern.
"""
import base64
import io
import logging

from odoo import _, api, fields, models


_logger = logging.getLogger(__name__)


# Attribute-name candidates per label field — first match wins. Names
# are case-insensitive. Keeps the label resilient to template-author
# variation (e.g. some templates use "Series", others "Door Style").
_ATTR_DOOR_NAME = ["Door Style", "Door Name", "Series"]
_ATTR_DOOR_COLOR = ["Finish", "Door Color", "Color"]
_ATTR_INTERIOR = ["Box Material", "Cabinet Interior", "Interior"]
_ATTR_HINGE = ["Hinge Side", "Hinge"]
_ATTR_FIN = ["Finished Sides", "Fin"]


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    sbk_label_customer_name = fields.Char(
        compute="_compute_sbk_label_customer", store=False)
    sbk_label_po_ref = fields.Char(
        compute="_compute_sbk_label_customer", store=False)
    sbk_label_tag = fields.Char(
        compute="_compute_sbk_label_customer", store=False)

    sbk_label_door_name = fields.Char(
        compute="_compute_sbk_label_attrs", store=False)
    sbk_label_door_color = fields.Char(
        compute="_compute_sbk_label_attrs", store=False)
    sbk_label_interior = fields.Char(
        compute="_compute_sbk_label_attrs", store=False)
    sbk_label_interior_is_white = fields.Boolean(
        compute="_compute_sbk_label_attrs", store=False)
    sbk_label_interior_is_maple = fields.Boolean(
        compute="_compute_sbk_label_attrs", store=False)
    sbk_label_hinge = fields.Char(
        compute="_compute_sbk_label_attrs", store=False)
    sbk_label_fin = fields.Char(
        compute="_compute_sbk_label_attrs", store=False)

    sbk_label_code = fields.Char(
        compute="_compute_sbk_label_code", store=False)
    sbk_label_qr_url = fields.Char(
        compute="_compute_sbk_label_qr", store=False)
    sbk_label_qr_image = fields.Binary(
        compute="_compute_sbk_label_qr", store=False)
    # Company logo as PNG base64 (data: URI ready). Bypasses wkhtmltopdf
    # 0.12.6's flaky WebP rendering AND the `/web/image` URL fetch in
    # PDF render context. PIL transcodes whatever Odoo stores (often
    # WebP) into PNG which wkhtmltopdf renders reliably.
    sbk_company_logo_b64 = fields.Char(
        compute="_compute_sbk_company_logo", store=False)

    # ── Customer / PO / TAG resolution ──────────────────────────────
    @api.depends("sale_line_id", "origin")
    def _compute_sbk_label_customer(self):
        for rec in self:
            so = rec.sale_line_id.order_id
            # When the MO was created without a sale_line_id link (manual
            # MO from confirmed SO via legacy import, etc.), fall back to
            # finding the SO by name == origin. Otherwise customer/PO/TAG
            # all collapse to the bare SO ref string.
            if not so and rec.origin:
                so = rec.env["sale.order"].sudo().search(
                    [("name", "=", rec.origin)], limit=1)
            if so:
                partner = so.partner_id or False
                # Invoices go to the company; the cabinet label
                # should name the contact-or-company per the legacy
                # workflow shown in the user's photo.
                rec.sbk_label_customer_name = (
                    partner.display_name if partner else (rec.origin or "—")
                ).upper()
                rec.sbk_label_po_ref = (
                    so.client_order_ref or so.name or rec.origin or ""
                )
                rec.sbk_label_tag = (
                    partner.display_name if partner else (rec.origin or "")
                ).upper()
            else:
                rec.sbk_label_customer_name = (rec.origin or "—").upper()
                rec.sbk_label_po_ref = rec.origin or ""
                rec.sbk_label_tag = (rec.origin or "").upper()

    # ── Company logo (transcoded to PNG for wkhtmltopdf) ────────────
    @api.depends("company_id")
    def _compute_sbk_company_logo(self):
        """Return company logo as PNG base64 string for inline data: URI.

        Odoo's res.company.logo_web is base64-encoded bytes; the
        underlying format is whatever was uploaded (PNG, JPEG, WebP).
        wkhtmltopdf 0.12.6.x renders PNG + JPEG reliably but breaks on
        WebP. We always transcode through PIL to PNG to be safe.
        """
        try:
            from PIL import Image  # noqa: WPS433 — lazy import is fine
            # PIL's auto-plugin discovery doesn't load WebP on the
            # Debian-bookworm Pillow build; res.company.logo_web in
            # Odoo 19 is WebP, so we register the plugin explicitly.
            # Without this, Image.open() raises UnidentifiedImageError
            # even though features.check("webp") returns True.
            from PIL import WebPImagePlugin  # noqa: F401, WPS433
        except ImportError:
            for rec in self:
                rec.sbk_company_logo_b64 = ""
            return
        for rec in self:
            company = rec.company_id or rec.env.company
            raw_b64 = company.logo_web
            if not raw_b64:
                rec.sbk_company_logo_b64 = ""
                continue
            try:
                # logo_web stores base64-encoded image bytes
                if isinstance(raw_b64, str):
                    src_bytes = base64.b64decode(raw_b64)
                else:
                    src_bytes = base64.b64decode(raw_b64)
                img = Image.open(io.BytesIO(src_bytes))
                # Ensure RGBA → RGB conversion for PNG without alpha
                # issues in wkhtmltopdf
                if img.mode in ("RGBA", "LA"):
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    bg.paste(img, mask=img.split()[-1])
                    img = bg
                elif img.mode != "RGB":
                    img = img.convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="PNG", optimize=True)
                rec.sbk_company_logo_b64 = base64.b64encode(
                    buf.getvalue()).decode("ascii")
            except Exception as exc:  # noqa: BLE001 — log + continue
                _logger.warning(
                    "sbk_company_logo transcode failed for company "
                    "%s: %s", company.id, exc)
                rec.sbk_company_logo_b64 = ""

    # ── Attribute-driven fields ─────────────────────────────────────
    def _sbk_attribute_value(self, attr_name_candidates, default=""):
        """Look up the first matching variant attribute value name.
        ``attr_name_candidates`` is a list of attribute labels to try
        in priority order (case-insensitive)."""
        self.ensure_one()
        if not self.product_id:
            return default
        wanted = {n.lower() for n in attr_name_candidates}
        for ptav in self.product_id.product_template_attribute_value_ids:
            attr_name = (ptav.attribute_id.name or "").lower()
            if attr_name in wanted:
                # ptav.name is "AttrName: ValueName"; prefer the bare
                # value name from product_attribute_value_id.
                return (
                    ptav.product_attribute_value_id.name
                    or ptav.name
                    or default
                )
        return default

    @api.depends("product_id", "product_id.product_template_attribute_value_ids")
    def _compute_sbk_label_attrs(self):
        for rec in self:
            door = rec._sbk_attribute_value(_ATTR_DOOR_NAME, "")
            color = rec._sbk_attribute_value(_ATTR_DOOR_COLOR, "")
            interior = rec._sbk_attribute_value(_ATTR_INTERIOR, "")
            hinge = rec._sbk_attribute_value(_ATTR_HINGE, "")
            fin = rec._sbk_attribute_value(_ATTR_FIN, "")
            rec.sbk_label_door_name = door.upper() if door else ""
            rec.sbk_label_door_color = color.upper() if color else ""
            rec.sbk_label_interior = interior.upper() if interior else ""
            rec.sbk_label_interior_is_white = (
                "white" in interior.lower() or "melamine" in interior.lower()
            ) if interior else False
            rec.sbk_label_interior_is_maple = (
                "maple" in interior.lower()
            ) if interior else False
            # Hinge: shorten "LH (Left Hand)" → "LH"
            if hinge:
                if hinge.startswith("LH"):
                    rec.sbk_label_hinge = "LH"
                elif hinge.startswith("RH"):
                    rec.sbk_label_hinge = "RH"
                else:
                    rec.sbk_label_hinge = hinge[:6].upper()
            else:
                rec.sbk_label_hinge = ""
            rec.sbk_label_fin = fin[:8].upper() if fin else ""

    # ── Code (SKU) — from product default_code ──────────────────────
    @api.depends("product_id", "product_id.default_code")
    def _compute_sbk_label_code(self):
        for rec in self:
            rec.sbk_label_code = (
                rec.product_id.default_code or rec.product_id.name or "—"
            )

    # ── QR — URL targets the MO form via the backend action ─────────
    # depends only on `name` — v19 forbids depending on `id` directly.
    # `name` changes once on create (placeholder → sequence) so the QR
    # is regenerated exactly when it should be.
    #
    # W007 (MFG-REVIEW-R4 W2 / R9 roadmap): when ``pg_revision_code`` is
    # stamped on the MO (PG-112 traceability — populated automatically by
    # the create override at
    # ``product_graph_release/models/mrp_production.py:51-74`` when the
    # source ``mrp.bom`` was written by ``pg.release.action_execute_release``),
    # we append it as a ``?rev=<code>`` query param. Installers scanning
    # the QR at site can read the rev straight out of the URL without
    # authenticating into Odoo. Pre-PG-112 MOs (no stamp) get the
    # original URL — no behaviour change for unstamped records.
    # Note: ``pg_revision_code`` is NOT in @api.depends — it's added by
    # the optional sibling addon ``product_graph_release``, which is not
    # in this addon's manifest depends (this addon is independently
    # installable). The compute reads via ``getattr`` so unstamped MOs
    # render unchanged. Since the field is ``store=False`` it recomputes
    # on every access anyway — no stale-cache risk.
    @api.depends("name")
    def _compute_sbk_label_qr(self):
        """W055 / R1.12 — emit a signed sb://mo/<ident> payload routed
        through /sb/qr/scan?p=... instead of a raw MO id URL.

        Why: when an ECO triggers MO rebuild, the new MO gets a new id.
        Previously printed labels then pointed at a dead id. The signed
        payload encodes the MO's *name* (e.g. WH/MO/00023) when set —
        which the ECO rebuild preserves — and falls back to the raw id
        only for MOs that never got a name.

        Backward compatibility: ALREADY-PRINTED labels carrying the old
        raw `/odoo/action-mrp.mrp_production_action/<id>` URL still
        resolve correctly because the scanner opens the URL directly
        in the browser — Odoo's own MO route renders the MO form. The
        only behavior change is for labels printed FROM NOW ON.
        """
        Param = self.env["ir.config_parameter"].sudo()
        base = (Param.get_param("web.base.url") or "").rstrip("/")
        Payload = (
            self.env["southbrook.qr.payload"]
            if "southbrook.qr.payload" in self.env else None
        )
        for rec in self:
            if not rec.id:
                rec.sbk_label_qr_url = ""
                rec.sbk_label_qr_image = False
                continue
            # Prefer the MO name (WH/MO/00023 style) — it survives ECO
            # MO rebuild via the production_id chain. Falls back to the
            # bare id for MOs without names (legacy/draft state).
            ident = (rec.name or "").strip() or str(rec.id)
            if Payload is not None:
                signed = Payload.build("mo", ident)
                from urllib.parse import quote
                url = (
                    f"{base}/sb/qr/scan?p={quote(signed, safe='')}"
                    if base
                    else f"/sb/qr/scan?p={quote(signed, safe='')}"
                )
            else:
                # Defensive — qr_kit is a hard depend in __manifest__,
                # but keep the legacy raw-URL path so a partial registry
                # never produces a blank label.
                url = (
                    f"{base}/odoo/action-mrp.mrp_production_action/{rec.id}"
                    if base
                    else f"/odoo/action-mrp.mrp_production_action/{rec.id}"
                )
            # W007 — embed engineering revision code in the QR payload
            # when present. Appended as an extra query param so the
            # signed sb:// payload is untouched.
            rev = (getattr(rec, "pg_revision_code", "") or "").strip()
            if rev:
                from urllib.parse import quote
                sep = "&" if "?" in url else "?"
                url = f"{url}{sep}rev={quote(rev, safe='')}"
            rec.sbk_label_qr_url = url
            try:
                import qrcode  # noqa: WPS433 — optional at compute time
                img = qrcode.make(url, box_size=4, border=2)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                rec.sbk_label_qr_image = base64.b64encode(buf.getvalue())
            except Exception:  # noqa: BLE001
                _logger.exception(
                    "Cabinet-label QR PNG failed for MO %s — using "
                    "URL text only.", rec.name)
                rec.sbk_label_qr_image = False

    # ── Action — open the printed-label report ──────────────────────
    def action_print_cabinet_label(self):
        """Trigger the Avery Presta 94215 cabinet-label PDF for
        each MO in self. Wired to a smart-button + a list-print
        action so a batch of MOs can produce a multi-page label
        PDF in one go."""
        return self.env.ref(
            "southbrook_kitchen_mrp.action_report_cabinet_label"
        ).report_action(self)
