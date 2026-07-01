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
    # Both project.task and mrp.production are read WITHOUT sudo so portal
    # record rules apply. If a record rule hides them (e.g., MOs are
    # internal-only), the calls degrade to empty results and the return
    # dict surfaces None — exactly what the spec § 4.4 ACL rule wants.
    kj = env["project.task"].search(
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
    return env["mrp.production"].search_count(
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
def list_my_kitchen_projects(env, partner_id: int = None):
    # partner_id is informational only — the authoritative scope comes from
    # the caller's env.user (set by the dispatch controller from JWT claims),
    # so an LLM arg can NOT widen the result set to another partner.
    Project = env["sb.kitchen.project"] if "sb.kitchen.project" in env else None
    if Project is None:
        return []
    projects = Project.search(
        [("partner_id", "=", env.user.partner_id.id)], order="create_date desc")
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
        order.check_access_rule("read")
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
        order.check_access_rule("read")
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
def list_my_recommendations(env, partner_id: int = None):
    # partner_id is informational only — the authoritative scope comes from
    # env.user.partner_id (controller-bound from JWT claims). Caller arg
    # can NOT widen the result to another partner.
    Rec = env["southbrook.hermes.recommendation"] if (
        "southbrook.hermes.recommendation" in env) else None
    if Rec is None:
        return []
    recs = Rec.search([
        ("source_model", "=", "res.partner"),
        ("source_res_id", "=", env.user.partner_id.id),
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


# ----------------------------------------------------------------------
# Catalog + pricing tools (Fabio agent — CLAUDE.md §5 rules + §6 channels)
#
# These tools give the Fabio LLM structured access to the Southbrook
# cabinet catalog + the channel-pricelist matrix, without exposing raw
# ORM search. They are:
#   - list_catalog       — enumerate templates, optionally filtered
#   - get_cabinet_price  — priced spec: list_price + PTAV extras + channel
#   - get_pricelist      — channel metadata (label, discount, notes)
#
# Design notes:
#   • Southbrook "cabinet" = product.template with config_ok=True (OCA
#     product_configurator marker). No separate is_cabinet flag exists.
#   • The family attribute is attr_family (display name "Cabinet Style")
#     with 9 canonical values. The tool arg accepts lowercase slugs
#     ("base", "wall", …) which map to xml_ids southbrook_estimating.
#     value_family_<slug>. "drawer" resolves to the "Drawer Bank" value.
#   • price_extra is stored on product.template.attribute.value (PTAV),
#     not on product.attribute.value. Caller passes product.attribute.
#     value ids; the tool resolves each to a PTAV bound to the template
#     and sums price_extra — matching OCA _compute_extra_prices.
#   • Channel percentages mirror southbrook_estimating_website
#     controllers/main.py:_CHANNEL_META (Q1 locked): retail=0, dealer=50,
#     kd=54, bigbox=33, refacing=35, tradesperson tiers 1=25/2=30/3=35.
#   • sudo() is safe here: catalog + pricelist metadata are global read
#     (scope="global" per decorator). No partner-scoped ACL applies.
# ----------------------------------------------------------------------

# Canonical channel metadata — kept local so the tool doesn't depend on
# the website controller module (which isn't guaranteed installed on
# every stack that runs Hermes). Values must stay in sync with
# southbrook_estimating_website/controllers/main.py:_CHANNEL_META and
# CLAUDE.md §6.
_CATALOG_CHANNEL_META = {
    "retail":       {"label": "Retail (List Price)",       "discount_pct": 0.0,
                     "notes": "Retail list price — the base Southbrook Signature Series book price."},
    "dealer":       {"label": "Dealer (-50%)",             "discount_pct": 50.0,
                     "notes": "Dealer -50% flat off retail (Signed Dealer Agreement)."},
    "tradesperson": {"label": "Contractor (Tiered)",       "discount_pct": 0.0,
                     "notes": "Contractor tiered: Tier 1 -25%, Tier 2 -30%, Tier 3 -35% off retail."},
    "kd":           {"label": "Central KD",                "discount_pct": 54.0,
                     "notes": "Central KD ~46% of retail — component pricing only, no assembly."},
    "bigbox":       {"label": "Big-Box Wholesale",         "discount_pct": 33.0,
                     "notes": "Big-Box Wholesale — fixed $65 cost / $98 retail per SKU."},
    "refacing":     {"label": "Refacing (CTHS)",           "discount_pct": 35.0,
                     "notes": "Refacing per-SF door pricing, ~35% target margin."},
}
_CATALOG_TRADESPERSON_TIER_PCT = {"1": 25.0, "2": 30.0, "3": 35.0}

# Family slug -> Cabinet Style value xml_id.
_CATALOG_FAMILY_TO_XMLID = {
    "base":      "southbrook_estimating.value_family_base",
    "wall":      "southbrook_estimating.value_family_wall",
    "tall":      "southbrook_estimating.value_family_tall",
    "drawer":    "southbrook_estimating.value_family_drawer",
    "sink":      "southbrook_estimating.value_family_sink",
    "corner":    "southbrook_estimating.value_family_corner",
    "vanity":    "southbrook_estimating.value_family_vanity",
    "accessory": "southbrook_estimating.value_family_accessory",
    "worktop":   "southbrook_estimating.value_family_worktop",
}


def _catalog_channel_pct(channel, tradesperson_tier=None):
    """Return (discount_pct, label, notes) for a channel.

    Tradesperson dispatches on tier; other channels use flat pct.
    Unknown tradesperson tier falls back to 0 (matches Order Builder
    tradesperson_no_tier warning path — see sale_order._resolve_channel_pricelist).
    """
    meta = _CATALOG_CHANNEL_META.get(channel) or _CATALOG_CHANNEL_META["retail"]
    if channel == "tradesperson" and tradesperson_tier:
        pct = _CATALOG_TRADESPERSON_TIER_PCT.get(str(tradesperson_tier), 0.0)
    else:
        pct = float(meta["discount_pct"])
    return pct, meta["label"], meta["notes"]


def _catalog_template_family(template):
    """Return the lowercase family slug for a template, or None.

    Reads the attr_family value bound to the template's attribute lines.
    Used to populate the family field in list_catalog / get_cabinet_price
    return dicts.
    """
    for line in template.attribute_line_ids:
        if line.attribute_id.name == "Cabinet Style":
            for v in line.value_ids:
                # Map value name back to slug. "Drawer Bank" -> "drawer".
                nm = (v.name or "").strip().lower()
                if nm == "drawer bank":
                    return "drawer"
                if nm.endswith(" series"):
                    nm = nm[:-len(" series")]
                if nm in _CATALOG_FAMILY_TO_XMLID:
                    return nm
    return None


def _catalog_template_series(template):
    """Return the series slug for a template if a single series is bound.

    Templates carry all 4 series as options (contractor/contemporary/
    elegance/signature) so this returns None unless the template is
    scoped to exactly one. Included for symmetry with list_catalog's
    series filter — a template lists as belonging to a series only if
    that series is on its attr_series line."""
    for line in template.attribute_line_ids:
        if line.attribute_id.name == "Series" and len(line.value_ids) == 1:
            return (line.value_ids[0].name or "").strip().lower().replace(" series", "")
    return None


@hermes_tool(
    personas=["trade_partner", "sales_rep", "mfg_manager"],
    tier="T0", scope="global",
    description=(
        "List Southbrook cabinet catalog entries. Filter by family "
        "(base|wall|tall|drawer|sink|corner|vanity|accessory|worktop) "
        "and/or series. Returns id, name, family, series, base list_price "
        "for each matching product.template. Use to answer 'what cabinets "
        "are available' or as a first step before get_cabinet_price."),
    parameters={
        "family": {"type": "string", "required": False,
                    "enum": ["base", "wall", "tall", "drawer", "sink",
                             "corner", "vanity", "accessory", "worktop"]},
        "series": {"type": "string", "required": False},
    },
)
def list_catalog(env, family=None, series=None):
    """Enumerate Southbrook cabinet templates.

    Filter semantics:
      • family: exact match against the attr_family Cabinet Style value
        bound to the template's attribute line.
      • series: case-insensitive match against attr_series values bound
        to the template's attribute line.

    Returns up to 40 entries sorted by family then name. Empty list on
    no match — never raises.
    """
    Template = env["product.template"].sudo()
    domain = [("config_ok", "=", True)]

    if family:
        xml_id = _CATALOG_FAMILY_TO_XMLID.get(family)
        if not xml_id:
            return {"cabinets": []}
        family_value = env.ref(xml_id, raise_if_not_found=False)
        if not family_value:
            return {"cabinets": []}
        domain.append(("attribute_line_ids.value_ids", "in", family_value.id))

    if series:
        series_norm = series.strip().lower().rstrip("s")
        # Try xml_id shortcut first: value_series_contractor / _elegance / etc.
        series_slug = series_norm.replace(" series", "").replace(" ", "_")
        series_value = env.ref(
            f"southbrook_estimating.value_series_{series_slug}",
            raise_if_not_found=False,
        )
        if not series_value:
            AttrValue = env["product.attribute.value"].sudo()
            series_value = AttrValue.search([
                ("attribute_id.name", "=", "Series"),
                ("name", "=ilike", f"{series.strip()}%"),
            ], limit=1)
        if not series_value:
            return {"cabinets": []}
        domain.append(("attribute_line_ids.value_ids", "in", series_value.id))

    templates = Template.search(domain, limit=40)
    entries = []
    for tmpl in templates:
        entries.append({
            "id": tmpl.id,
            "name": tmpl.name,
            "family": _catalog_template_family(tmpl),
            "series": _catalog_template_series(tmpl),
            "list_price": float(tmpl.list_price or 0.0),
        })
    entries.sort(key=lambda e: (e["family"] or "", e["name"] or ""))
    return {"cabinets": entries}


@hermes_tool(
    personas=["trade_partner", "sales_rep", "mfg_manager"],
    tier="T0", scope="global",
    description=(
        "Return the price of a specific cabinet with attribute selections. "
        "Combines list_price + price_extra for chosen attribute values, then "
        "optionally applies a channel pricelist. Use after list_catalog "
        "narrows to a template."),
    parameters={
        "product_tmpl_id": {"type": "integer", "required": True},
        "attribute_value_ids": {"type": "array", "items": {"type": "integer"},
                                 "required": False},
        "channel": {"type": "string", "required": False,
                     "enum": ["retail", "dealer", "tradesperson", "kd",
                              "bigbox", "refacing"]},
        "tradesperson_tier": {"type": "string", "required": False,
                               "enum": ["1", "2", "3"]},
    },
)
def get_cabinet_price(env, product_tmpl_id, attribute_value_ids=None,
                      channel="retail", tradesperson_tier=None):
    """Return the fully-computed retail + channel price for a template.

    Look up procedure:
      1. Browse product.template. If missing or not config_ok, return {}.
      2. For each product.attribute.value id in attribute_value_ids, find
         the sibling product.template.attribute.value bound to the same
         template and sum its price_extra (OCA convention).
      3. retail_total = list_price + sum(extras).
      4. channel_total = retail_total * (1 - discount_pct/100).

    Returns {} if the template is not a Southbrook cabinet.
    """
    Template = env["product.template"].sudo()
    tmpl = Template.browse(int(product_tmpl_id)).exists()
    if not tmpl or not tmpl.config_ok:
        return {}

    list_price = float(tmpl.list_price or 0.0)
    extras = []
    if attribute_value_ids:
        PTAV = env["product.template.attribute.value"].sudo()
        ptavs = PTAV.search([
            ("product_tmpl_id", "=", tmpl.id),
            ("product_attribute_value_id", "in", list(attribute_value_ids)),
        ])
        for ptav in ptavs:
            extras.append({
                "attribute": ptav.attribute_id.name,
                "value": ptav.name,
                "price_extra": float(ptav.price_extra or 0.0),
            })

    retail_total = list_price + sum(e["price_extra"] for e in extras)
    channel_pct, _label, _notes = _catalog_channel_pct(channel, tradesperson_tier)
    channel_total = retail_total * (1.0 - channel_pct / 100.0)

    currency = tmpl.currency_id or env.company.currency_id
    return {
        "product_tmpl_id": tmpl.id,
        "name": tmpl.name,
        "list_price": list_price,
        "attribute_extras": extras,
        "retail_total": retail_total,
        "channel": channel,
        "channel_pct": channel_pct,
        "channel_total": channel_total,
        "currency": {
            "symbol": currency.symbol or "",
            "name": currency.name or "",
            "position": currency.position or "after",
            "decimal_places": int(currency.decimal_places or 2),
        },
    }


@hermes_tool(
    personas=["trade_partner", "sales_rep", "mfg_manager"],
    tier="T0", scope="global",
    description=(
        "Return metadata for a channel pricelist (label, discount %, "
        "example calc). Use to answer 'what's the dealer discount' or "
        "'how does the contractor tier work'."),
    parameters={
        "channel": {"type": "string", "required": True,
                     "enum": ["retail", "dealer", "tradesperson", "kd",
                              "bigbox", "refacing"]},
        "tradesperson_tier": {"type": "string", "required": False,
                               "enum": ["1", "2", "3"]},
    },
)
def get_pricelist(env, channel, tradesperson_tier=None):
    """Return {channel, label, discount_pct, notes} for a channel.

    For channel='tradesperson' with a tier, discount_pct resolves to the
    tier's specific value (25/30/35). Without a tier, discount_pct is
    0 and the notes explain the tier system — matching the Order
    Builder's tradesperson_no_tier warning path.
    """
    if channel not in _CATALOG_CHANNEL_META:
        return {}
    pct, label, notes = _catalog_channel_pct(channel, tradesperson_tier)
    return {
        "channel": channel,
        "label": label,
        "discount_pct": pct,
        "notes": notes,
    }
