# SPDX-License-Identifier: LGPL-3.0-only
"""Wrap the resolve() AbstractModel to emit a spec-event on every call.

Keeps the resolver's logic untouched — we only observe + emit. The Marathon
dashboard reads from `kitchenforge.marathon.spec.event`.
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class HardwareCatalog(models.AbstractModel):
    _inherit = "southbrook.hardware.catalog"

    @api.model
    def resolve(
        self,
        cabinet_family: str,
        door_count: int = 0,
        drawer_count: int = 0,
        shelf_count: int = 0,
        soft_close: bool = True,
        pull_finish: str = None,
        pull_size_mm: int = 128,
        handle_style: str = "pull",
        mount_appliance: bool = False,
    ):
        result = super().resolve(
            cabinet_family=cabinet_family,
            door_count=door_count,
            drawer_count=drawer_count,
            shelf_count=shelf_count,
            soft_close=soft_close,
            pull_finish=pull_finish,
            pull_size_mm=pull_size_mm,
            handle_style=handle_style,
            mount_appliance=mount_appliance,
        )
        # Emit one event per resolved Marathon-branded SKU.
        Brand = self.env["southbrook.hardware.brand"].sudo()
        marathon = Brand.search([("name", "ilike", "marathon")], limit=1)
        marathon_id = marathon.id if marathon else 0
        Event = self.env["kitchenforge.marathon.spec.event"].sudo()
        for product, qty in result or []:
            # Field name is x_hardware_brand_id per southbrook_hardware_catalog.
            brand = getattr(product, "x_hardware_brand_id", False)
            bid = brand.id if hasattr(brand, "id") else brand
            if bid != marathon_id:
                continue
            try:
                Event.emit(
                    product=product, qty=qty,
                    cabinet_family=cabinet_family,
                    pull_finish=pull_finish,
                    pull_size_mm=pull_size_mm,
                    extra={
                        "door_count": door_count,
                        "drawer_count": drawer_count,
                        "shelf_count": shelf_count,
                        "soft_close": soft_close,
                        "handle_style": handle_style,
                    },
                )
            except Exception as exc:
                _logger.warning("spec-event emit failed: %s", exc)
        return result
