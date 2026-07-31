# -*- coding: utf-8 -*-
"""Correct SB-EDGE (Edge Bander) from Man to Machine — an approved decision.

The 19.0.1.1.0 backfill deliberately refused to touch this one. `wc_type` was 'H' (Man) on
SB-EDGE, set by a human at some point, and that field decides which GL account absorbs a
work order's direct cost. A migration silently rewriting somebody's explicit entry on a
financial field is not a migration's job, so it logged a warning instead:

    SB-EDGE (Edge Bander) is set to 'H' (Man), so its cost posts to the LABOUR account.
    An edge bander is a machine. This value was set by hand and has NOT been changed —
    confirm with finance whether it should be 'M'.

That confirmation was given on 2026-07-31: change it to 'M'. An edge bander runs a heated
glue pot and a feed motor; its cost is machine time, not labour.

Effect: SB-EDGE work-order direct cost moves from the labour account to the machine-run
account, matching the other four machine stations (panel saw, CNC boring, CNC router,
door shop).

Idempotent, and narrow. It changes SB-EDGE only, only if it is still 'H', so re-running is
a no-op and a later human decision to set something else is not stomped by a redeploy.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    from odoo import SUPERUSER_ID, api
    env = api.Environment(cr, SUPERUSER_ID, {})
    Workcenter = env["mrp.workcenter"].with_context(active_test=False)

    if "wc_type" not in Workcenter._fields:
        return

    edge = Workcenter.search([("code", "=", "SB-EDGE")], limit=1)
    if not edge:
        _logger.info("wc_type: no SB-EDGE work centre on this database; nothing to do")
        return

    if edge.wc_type == "M":
        _logger.info("wc_type: SB-EDGE already 'M'; nothing to do")
        return

    if edge.wc_type != "H":
        # Somebody has set it to something else since. Do not overwrite a live decision.
        _logger.warning(
            "wc_type: SB-EDGE is %r, not the 'H' this correction was approved against. "
            "Left unchanged — re-confirm with finance if it should be 'M'.", edge.wc_type)
        return

    edge.wc_type = "M"
    _logger.warning(
        "wc_type: SB-EDGE (Edge Bander) corrected 'H' -> 'M' per approval 2026-07-31. "
        "Its work-order direct cost now posts to the MACHINE RUN account, not labour.")
