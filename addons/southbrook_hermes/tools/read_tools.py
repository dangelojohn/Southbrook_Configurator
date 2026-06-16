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


@hermes_tool(
    personas=["trade_partner", "sales_rep"],
    tier="T0", scope="own",
    description="List kitchen projects visible to this partner.",
)
def list_my_kitchen_projects(env, partner_id: int):
    Project = env["sb.kitchen.project"] if "sb.kitchen.project" in env else None
    if Project is None:
        return []
    projects = Project.sudo().search(
        [("partner_id", "=", partner_id)], order="create_date desc")
    return [
        {
            "ref": p.name,
            "stage": getattr(p, "state", None),
            "option_count": len(p.option_ids) if hasattr(p, "option_ids") else 0,
            "selected": next(
                (o.name for o in getattr(p, "option_ids", [])
                 if getattr(o, "is_selected", False)), None),
        }
        for p in projects
    ]


@hermes_tool(
    personas=["trade_partner", "sales_rep"],
    tier="T0", scope="own_order",
    description="Return options + approval status of a kitchen project.",
)
def get_kitchen_project(env, project_id: int):
    Project = env["sb.kitchen.project"] if "sb.kitchen.project" in env else None
    if Project is None:
        raise MissingError("Kitchen projects not available on this instance.")
    project = Project.browse(project_id)
    try:
        project.check_access_rights("read")
        project.check_access_rule("read")
    except Exception:
        raise MissingError("Project not visible to this user.")
    return {
        "options": [
            {"name": o.name, "is_selected": getattr(o, "is_selected", False)}
            for o in getattr(project, "option_ids", [])
        ],
        "approval_status": getattr(project, "approval_status", None),
        "drawings_url": getattr(project, "drawings_url", None),
    }


@hermes_tool(
    personas=["trade_partner", "sales_rep"],
    tier="T0", scope="own_order",
    description="Return install schedule + risk flag for an order.",
)
def get_install_schedule(env, order_id: int):
    order = env["sale.order"].browse(order_id)
    try:
        order.check_access_rights("read")
    except Exception:
        raise MissingError("Order not visible to this user.")
    return {
        "date": (order.commitment_date.isoformat()
                 if order.commitment_date else None),
        "dispatch": getattr(order, "delivery_status", None),
        "risk_flag": "unknown",
        "risk_reason": None,
    }


@hermes_tool(
    personas=["trade_partner", "sales_rep"],
    tier="T0", scope="own_order",
    description="Return the quote PDF URL + expiry for an order.",
)
def get_quote_pdf_url(env, order_id: int):
    order = env["sale.order"].browse(order_id)
    try:
        order.check_access_rights("read")
    except Exception:
        raise MissingError("Order not visible to this user.")
    base_url = env["ir.config_parameter"].sudo().get_param("web.base.url", "")
    return {
        "pdf_url": (f"{base_url}/my/orders/{order.id}?report_type=pdf"
                    if base_url else None),
        "valid_until": (order.validity_date.isoformat()
                        if order.validity_date else None),
    }


@hermes_tool(
    personas=["trade_partner", "sales_rep"],
    tier="T0", scope="own",
    description="List Hermes recommendations awaiting this partner's approval.",
)
def list_my_recommendations(env, partner_id: int):
    # Partner attribution on southbrook.hermes.recommendation uses the
    # generic (source_model, source_res_id) pair — see
    # addons/southbrook_hermes/models/hermes_recommendation.py:43-44.
    Rec = env["southbrook.hermes.recommendation"] if (
        "southbrook.hermes.recommendation" in env) else None
    if Rec is None:
        return []
    recs = Rec.sudo().search([
        ("source_model", "=", "res.partner"),
        ("source_res_id", "=", partner_id),
        ("state", "in", ("draft", "ready")),
    ], order="create_date desc")
    return [
        {
            "rec_id": r.id,
            "type": r.recommendation_type,
            "summary": r.summary or "",
            "state": r.state,
        }
        for r in recs
    ]


@hermes_tool(
    personas=["trade_partner", "sales_rep", "mfg_manager"],
    tier="T0", scope="global",
    description=(
        "Return the body and current version of a named OS section "
        "(e.g., '02_catalog', '07_partner_faq')."),
)
def get_os_section(env, slug: str):
    Section = env["southbrook.os.section"].sudo()
    section = Section.search([("slug", "=", slug)], limit=1)
    if not section:
        raise MissingError(f"OS section '{slug}' not found.")
    return {
        "slug": section.slug,
        "name": section.name,
        "version": section.version,
        "source": section.source,
        "body": section.body,
    }
