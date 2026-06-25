# SPDX-License-Identifier: LGPL-3.0-only
"""Hook MO lifecycle transitions into the Kitchen Ops activity feed.

Proposals §3.4: when an MO is marked done, emit a `mo_done` event so
the manager dashboard's right column shows the completion as it
happens.

DESIGN:
  - Only override `button_mark_done` (the standard mrp.production
    transition to `done`). Don't hook every state write — too noisy.
  - Wrapped in try/except. Activity-feed failures MUST NEVER block
    an MO from completing.
  - Emit `mo_done` AFTER the super() call returns successfully —
    a failed mark_done shouldn't produce a fake "done" event.
"""
from odoo import models


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    def button_mark_done(self):
        result = super().button_mark_done()
        for mo in self:
            try:
                self.env["southbrook.ops.event"].emit(
                    "mo_done",
                    f"MO {mo.name} marked done"
                    + (f" (for {mo.product_id.name})"
                       if mo.product_id else ""),
                    res_model="mrp.production",
                    res_id=mo.id,
                    severity="info",
                )
            except Exception:  # noqa: BLE001
                pass
        return result
