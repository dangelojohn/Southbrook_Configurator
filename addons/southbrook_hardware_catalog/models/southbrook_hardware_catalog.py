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
        pull_finish: str = None,
        pull_size_mm: int = 128,
        handle_style: str = "pull",
        mount_appliance: bool = False,
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

        Audit 2026-06-10 — finish-aware handle selection:

        * ``pull_finish`` — snake-case key matching attr_pull_finish
          values (e.g. ``brushed_nickel``, ``matte_black``). When given,
          the resolver strips legacy default-pull SKUs (per
          ``pull_default_skus``) from the result and substitutes the
          finish-specific SKU from ``by_pull_finish[finish][size]``.
        * ``pull_size_mm`` — pull center-to-center in mm (96, 128, 192).
          Falls back to the finish's ``default`` SKU when unseeded.
        * ``handle_style`` — ``"pull"`` (default) or ``"knob"``. Knob
          swaps go through ``by_knob_finish`` and ``knob_default_skus``.
        * ``mount_appliance`` — when True, an appliance pull is added on
          top of the regular per-door handle (for tall_oven/fridge).

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

        # ---- Finish-aware handle override ----------------------------
        # Apply only when the caller passed pull_finish. Without it,
        # the legacy default (MRH-HDL-PUL128 brushed nickel) flows
        # through unchanged — preserves backward compatibility for
        # callers that haven't been updated for the audit's
        # attr_pull_finish surface yet.
        if pull_finish and handle_style == "pull":
            handle_qty = self._strip_default_handles(
                totals, m.get("pull_default_skus") or [])
            target_sku = self._lookup_pull_sku(
                m, pull_finish, pull_size_mm)
            if target_sku and handle_qty > 0:
                totals[target_sku] = totals.get(target_sku, 0) + handle_qty
        elif pull_finish and handle_style == "knob":
            handle_qty = self._strip_default_handles(
                totals, m.get("knob_default_skus") or [])
            target_sku = (m.get("by_knob_finish") or {}).get(pull_finish)
            if target_sku and handle_qty > 0:
                totals[target_sku] = totals.get(target_sku, 0) + handle_qty

        # ---- Appliance pull addition --------------------------------
        if mount_appliance and pull_finish:
            app_sku = (m.get("appliance_pulls") or {}).get(pull_finish)
            if app_sku:
                # One appliance pull per appliance-door front. door_count
                # on tall_oven / tall_fridge equals appliance-door count.
                totals[app_sku] = totals.get(app_sku, 0) + max(door_count, 1)

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

    @staticmethod
    def _strip_default_handles(totals: Dict[str, int], default_skus: list) -> int:
        """Remove default-handle SKUs from totals; return total stripped qty
        so the caller can re-add the finish-specific SKU with the same
        quantity (preserves the per_door × door_count + per_drawer × drawer_count
        sum that flowed through the legacy aggregation)."""
        stripped = 0
        for sku in default_skus:
            if sku in totals:
                stripped += totals.pop(sku)
        return stripped

    @staticmethod
    def _lookup_pull_sku(
        m: dict, pull_finish: str, pull_size_mm: int,
    ) -> str:
        """Find the right pull SKU for (finish, size). Falls back to the
        finish's ``default`` if the specific size isn't mapped. Returns
        None if the finish itself is unmapped — the caller logs and the
        default would be unable to land, so a downstream warning surfaces
        the gap."""
        finish_map = (m.get("by_pull_finish") or {}).get(pull_finish)
        if not finish_map:
            return None
        size_key = f"{pull_size_mm}mm"
        return finish_map.get(size_key) or finish_map.get("default")
