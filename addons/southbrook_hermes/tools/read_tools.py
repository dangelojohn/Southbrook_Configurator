# SPDX-License-Identifier: LGPL-3.0-only
"""Read tools — list_my_orders, get_order_status, get_order_line, etc."""
from odoo.exceptions import MissingError, UserError

from .decorator import hermes_tool


@hermes_tool(
    personas=["trade_partner", "sales_rep"],
    tier="T0", scope="own",
    description="List the orders visible to the current partner.",
)
def list_my_orders(env, partner_id: int):
    orders = env["sale.order"].search(
        [("partner_id", "=", partner_id)], order="date_order desc", limit=50)
    return [
        {
            "ref": o.name,
            "stage": o.state,
            "partner_name": o.partner_id.name,
            "install_due": (o.commitment_date.isoformat()
                            if o.commitment_date else None),
        }
        for o in orders
    ]


@hermes_tool(
    personas=["trade_partner", "sales_rep"],
    tier="T0", scope="own_order",
    description=(
        "Return the production status of a specific order, including stage, "
        "MO count, bottleneck work center, top blocker, next best action."),
)
def get_order_status(env, order_id: int):
    order = env["sale.order"].browse(order_id)
    try:
        order.check_access_rights("read")
        order.check_access_rule("read")
    except Exception:
        raise MissingError("Order not visible to this user.")
    kj = env["project.task"].sudo().search(
        [("sale_order_id", "=", order.id)], limit=1)
    return {
        "stage": order.state,
        "mos": _count_mos_for_order(env, order),
        "bottleneck": (kj.southbrook_current_bottleneck_wc.name
                       if kj and getattr(kj, "southbrook_current_bottleneck_wc", False)
                       else None),
        "blocker": (kj.southbrook_top_blocker if kj else None),
        "next_action": (kj.southbrook_next_best_action if kj else None),
        "install_due": (kj.date_deadline.isoformat()
                        if kj and kj.date_deadline else None),
        "readiness_score": (kj.southbrook_readiness_score if kj else None),
        "version": getattr(order, "southbrook_version", 1),
    }


def _count_mos_for_order(env, order):
    line_ids = order.order_line.ids
    return env["mrp.production"].sudo().search_count(
        [("sale_order_line_id", "in", line_ids)])


@hermes_tool(
    personas=["trade_partner", "sales_rep"],
    tier="T0", scope="own_order",
    description="Return the configured detail of a single order line.",
)
def get_order_line(env, order_id: int, line_id: int):
    order = env["sale.order"].browse(order_id)
    try:
        order.check_access_rights("read")
        order.check_access_rule("read")
    except Exception:
        raise MissingError("Order not visible to this user.")
    line = order.order_line.filtered(lambda l: l.id == line_id)
    if not line:
        raise UserError(
            f"Line {line_id} does not belong to order {order.name} "
            f"or is not visible to this user.")
    return {
        "sku": line.product_id.default_code or "",
        "variant_name": line.product_id.name,
        "qty": line.product_uom_qty,
        "attributes": {
            v.attribute_id.name: v.name
            for v in line.product_id.product_template_attribute_value_ids
        },
        "retail": line.price_unit,
        "channel": line.price_subtotal,
        "flags": [],
    }
