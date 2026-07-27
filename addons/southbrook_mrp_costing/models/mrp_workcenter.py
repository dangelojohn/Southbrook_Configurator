# SPDX-License-Identifier: LGPL-3.0-only
"""Workcenter cost rates.

``costs_hour`` is native to ``mrp``. ``costs_hour_fixed`` is **not** — in the
system this module replaces it was contributed by ``mrp_product_costing``
(verified against ir_model_fields: owner module ``mrp_product_costing``).

Defining it here matters. Without it, swapping that module out would remove
the field from ``mrp.workcenter`` entirely and every order's fixed routing
cost would silently fall to zero — a capability regression disguised as a
clean migration, and one that would be hard to spot because nothing raises.
"""

from odoo import fields, models


class MrpWorkcenter(models.Model):
    _inherit = "mrp.workcenter"

    costs_hour_fixed = fields.Float(
        "Fixed Hourly Cost", digits="Product Price",
        help="Hourly rate applied to the setup and cleanup allowance "
             "(time_start + time_stop) rather than to run time. Charged once "
             "per operation, not per unit produced.")
