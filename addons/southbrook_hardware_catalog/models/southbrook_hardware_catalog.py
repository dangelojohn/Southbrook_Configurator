# SPDX-License-Identifier: LGPL-3.0-only
"""Hardware-resolution service.

Given a configured carcass (family + door/drawer/shelf counts + soft-close
preference), returns the list of hardware SKUs the cabinet needs and the
quantity of each. The FreeCAD bridge calls this post-render to append
hardware lines to the BoM; the configurator can use it to preview the
pick list in the UX.

Loading strategy: the mapping rules live in ``data/hardware_map.json`` —
shipped inside the addon and read on first use. Keeping the rules as data
(per the init-doc anti-pattern list) means a brand swap or a new rule
doesn't require a code change.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple

from odoo import api, models

_logger = logging.getLogger(__name__)


def _load_hardware_map() -> dict:
    """Load and return the hardware_map.json shipped inside this addon."""
    path = Path(__file__).resolve().parent.parent / "data" / "hardware_map.json"
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


class SouthbrookHardwareCatalog(models.AbstractModel):
    """Resolution service — exposed as an env.['southbrook.hardware.catalog']
    handle so callers do `env['southbrook.hardware.catalog'].resolve(...)`.
    """
    _name = "southbrook.hardware.catalog"
    _description = "Southbrook Hardware Resolution Service"

    @api.model
    def _hardware_map(self) -> dict:
        # Cached on the registry so we don't re-read the file every call.
        if not hasattr(self.pool, "_southbrook_hardware_map"):
            self.pool._southbrook_hardware_map = _load_hardware_map()
        return self.pool._southbrook_hardware_map

    @api.model
    def resolve(
        self,
        cabinet_family: str,
        door_count: int = 0,
        drawer_count: int = 0,
        shelf_count: int = 0,
        soft_close: bool = True,
    ) -> List[Tuple]:
        """Return a list of (product.product, qty) tuples for the configured carcass.

        Mapping rules — see ``data/hardware_map.json``:

        * ``per_door`` × door_count for hinges + door bumpers + handle.
        * ``per_drawer`` × drawer_count for slides + drawer-front handles.
        * ``per_shelf`` × shelf_count for adjustable-shelf pins.
        * ``per_cabinet`` for cabinet-mounting screws, levelers,
          and the cam-lock kit if applicable.

        ``soft_close=False`` swaps the hinge SKU to the non-soft-close
        variant. Bi-fold corner cabinets pass soft_close=False per the
        configurator's Rule 4 (family → soft-close).

        Any rule whose SKU is missing from the installed seed is skipped
        with a logger warning — the resolution survives partial catalogs
        so the addon installs cleanly with the 20-row seed and grows
        seamlessly once the 179-row import lands.
        """
        m = self._hardware_map()
        Product = self.env["product.product"]

        # Pick the per-door hinge depending on soft-close preference.
        per_door_section = "per_door_soft_close" if soft_close else "per_door"
        rules: List[Tuple[str, str, int]] = []  # (source, sku, qty)

        for sku, qty_per in (m.get(per_door_section) or {}).items():
            rules.append(("per_door", sku, qty_per * door_count))
        for sku, qty_per in (m.get("per_drawer") or {}).items():
            rules.append(("per_drawer", sku, qty_per * drawer_count))
        for sku, qty_per in (m.get("per_shelf") or {}).items():
            rules.append(("per_shelf", sku, qty_per * shelf_count))
        for sku, qty in (m.get("per_cabinet") or {}).items():
            rules.append(("per_cabinet", sku, qty))

        # Family-specific overrides — e.g. tall pantry gets extra levelers.
        family_extra = (m.get("per_family") or {}).get(cabinet_family) or {}
        for sku, qty in family_extra.items():
            rules.append((f"per_family[{cabinet_family}]", sku, qty))

        # Aggregate per-SKU before resolving — so per_cabinet + per_family
        # contributions to the same SKU (e.g. extra levelers on a tall
        # pantry) sum instead of producing duplicate BoM lines.
        totals: Dict[str, int] = {}
        for _source, sku, qty in rules:
            if qty <= 0:
                continue
            totals[sku] = totals.get(sku, 0) + qty

        result: List[Tuple] = []
        for sku, qty in totals.items():
            product = Product.search([("x_marathon_sku", "=", sku)], limit=1)
            if not product:
                _logger.warning(
                    "hardware_map references SKU '%s' not present in the "
                    "catalog — skipped. Add the SKU to the seed or run "
                    "the Marathon-catalog import.",
                    sku,
                )
                continue
            result.append((product, qty))
        return result
