# SPDX-License-Identifier: LGPL-3.0-only
"""Task 1 (Materials Phase-2b Procurement). v19 `uom.uom` has NO
`category`/`category_id` model (grep-verified against the installed core,
addons/uom/models/uom_uom.py) — units relate via `relative_uom_id`, a
_parent_store tree, and `_has_common_reference` walks `parent_path` to
check two units share a root. `_compute_quantity` itself does NOT gate on
that — it blindly multiplies by `factor` ratios regardless of category, so
this helper checks `_has_common_reference` FIRST and never calls
`_compute_quantity` when it's false.
"""
from odoo import models


class UomUom(models.Model):
    _inherit = "uom.uom"

    def sb_convert_demand_qty(self, qty, to_uom):
        """Convert `qty` (expressed in `self`) into `to_uom`.

        Returns (qty, is_exact):
        - is_exact True: a real native conversion applied; `qty` is now in
          `to_uom`.
        - is_exact False: `self`/`to_uom` share no reference (e.g. canonical
          m2 vs. a vendor's non-dimensional "Sheet" pack unit -- that case
          is `uom_yield_qty`'s job, Phase-2a, not this helper's). `qty` is
          returned UNCHANGED -- never fabricated.
        """
        self.ensure_one()
        if not self or not to_uom:
            return qty, False
        to_uom.ensure_one()
        if self == to_uom:
            return qty, True
        if not self._has_common_reference(to_uom):
            return qty, False
        return self._compute_quantity(qty, to_uom, round=False), True
