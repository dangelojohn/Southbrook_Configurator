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

    # ── Customer / PO / TAG resolution ──────────────────────────────
    @api.depends("sale_line_id", "origin")
    def _compute_sbk_label_customer(self):
        for rec in self:
            so = rec.sale_line_id.order_id
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
    @api.depends("name")
    def _compute_sbk_label_qr(self):
        Param = self.env["ir.config_parameter"].sudo()
        base = (Param.get_param("web.base.url") or "").rstrip("/")
        for rec in self:
            if not rec.id:
                rec.sbk_label_qr_url = ""
                rec.sbk_label_qr_image = False
                continue
            # Authenticated operator scans → opens MO form. Works
            # without the qr_kit signed-URL infrastructure being on
            # this branch.
            url = (
                f"{base}/odoo/action-mrp.mrp_production_action/{rec.id}"
                if base else f"/odoo/action-mrp.mrp_production_action/{rec.id}"
            )
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
