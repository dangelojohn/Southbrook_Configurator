# SPDX-License-Identifier: LGPL-3.0-only
"""sb.production.package — bundles a cutlist + a hardware package + state
machine for the shop-floor handoff. The orchestrator the rest of the
platform calls when an MO needs its complete manufacturing recipe."""
import logging
from typing import Optional

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# /srv/shared on PYTHONPATH — same canonical formula source the bridge
# uses for /validate and the G1 test asserts byte-for-byte parity against.
from southbrook_dims import panel_cut_list

_logger = logging.getLogger(__name__)


PRODUCTION_PACKAGE_STATES = [
    ("draft", "Draft"),
    ("ready", "Ready for Shop Floor"),
    ("released", "Released to Production"),
    ("done", "Done"),
]


class SbProductionPackage(models.Model):
    _name = "sb.production.package"
    _description = "Southbrook Production Package"
    _order = "id desc"

    name = fields.Char(required=True, default=lambda self: _("New"))
    mo_id = fields.Many2one(
        comodel_name="mrp.production",
        string="Manufacturing Order",
        ondelete="cascade",
        required=True,
        index=True,
    )
    state = fields.Selection(
        PRODUCTION_PACKAGE_STATES, default="draft", tracking=True, required=True,
    )
    cutlist_id = fields.Many2one(
        comodel_name="sb.cutlist", string="Cut List", ondelete="restrict",
    )
    hardware_package_id = fields.Many2one(
        comodel_name="sb.hardware.package",
        string="Hardware Package",
        ondelete="restrict",
    )
    has_pricing_pending = fields.Boolean(
        related="hardware_package_id.has_pricing_pending", store=True,
    )

    @api.constrains("mo_id")
    def _check_unique_mo(self):
        """One production package per MO — enforced at Python level so
        the constraint survives the Odoo-19 _sql_constraints deprecation.
        """
        for record in self:
            if not record.mo_id:
                continue
            dup = self.search_count([
                ("mo_id", "=", record.mo_id.id),
                ("id", "!=", record.id),
            ])
            if dup:
                raise ValidationError(_(
                    "A production package already exists for this "
                    "manufacturing order. Use generate_from_mo() to "
                    "replace it instead of creating a duplicate."
                ))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "sb.production.package"
                ) or _("New")
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Orchestration: an MO -> a complete cutlist + hardware package
    # ------------------------------------------------------------------
    @api.model
    def generate_from_mo(
        self,
        mo,
        width_mm: float,
        height_mm: float,
        depth_mm: float,
        cabinet_family: str = "base",
        door_count: int = 1,
        drawer_count: int = 0,
        soft_close: bool = True,
    ):
        """Build (or rebuild) the complete production package for an MO.

        Idempotent — calling twice replaces the prior cutlist + hardware
        package on the same MO rather than creating duplicates. The init
        doc Module 4 DoD ("an MO produces a complete cutlist + hardware
        package") is met by a single call to this method.

        Geometry comes from shared.southbrook_dims.panel_cut_list — same
        module the bridge and the G1 gate use, so cutlist geometry is
        guaranteed identical to rendered geometry.

        Hardware comes from southbrook.hardware.catalog.resolve — same
        path the bridge will use post-render.

        Returns the production-package record.
        """
        if not mo:
            raise UserError(_("generate_from_mo requires an mrp.production record."))

        # Idempotency — replace any existing package on this MO.
        # Deletion order matters: production package holds m2o references
        # to cutlist and hardware_package with ondelete='restrict', so we
        # delete the package FIRST, then the things it referenced.
        existing = self.search([("mo_id", "=", mo.id)])
        if existing:
            cutlists = existing.mapped("cutlist_id")
            hardware_packages = existing.mapped("hardware_package_id")
            existing.unlink()
            (cutlists.mapped("line_ids")).unlink()
            cutlists.unlink()
            (hardware_packages.mapped("line_ids")).unlink()
            hardware_packages.unlink()

        Cutlist = self.env["sb.cutlist"]
        HardwarePackage = self.env["sb.hardware.package"]
        Catalog = self.env["southbrook.hardware.catalog"]

        # 1. Geometry — call shared.southbrook_dims and emit cutlist lines.
        panel_dict = panel_cut_list(
            width_mm, height_mm, depth_mm,
            family=cabinet_family, door_count=door_count,
        )
        cutlist = Cutlist.create({"mo_id": mo.id})
        Cutlist.generate_lines_from_panel_dict(cutlist, panel_dict)

        # 2. Hardware — resolve picks and build the package.
        shelf_count = int(panel_dict.get("shelf_count") or 0)
        picks = Catalog.resolve(
            cabinet_family=cabinet_family,
            door_count=door_count,
            drawer_count=drawer_count,
            shelf_count=shelf_count,
            soft_close=soft_close,
        )
        hardware_package = HardwarePackage.create({"mo_id": mo.id})
        HardwarePackage.generate_lines_from_resolution(hardware_package, picks)

        # 3. The wrap.
        package = self.create({
            "mo_id": mo.id,
            "cutlist_id": cutlist.id,
            "hardware_package_id": hardware_package.id,
            "state": "ready",
        })
        return package
