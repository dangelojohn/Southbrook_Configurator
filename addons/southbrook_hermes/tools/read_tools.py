# SPDX-License-Identifier: LGPL-3.0-only
"""Read tools — list_my_orders, get_order_status, get_order_line, etc."""
import calendar
import datetime

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
    personas=["trade_partner", "sales_rep", "mfg_manager"],
    tier="T0", scope="own_order",
    description=(
        "Return the production status of a specific order, including stage, "
        "MO count, bottleneck work center, top blocker, next best action."),
)
def get_order_status(env, order_id: int):
    order = env["sale.order"].browse(order_id)
    try:
        # v18+ merged check_access_rights + check_access_rule into a single
        # check_access(operation); the old pair is deprecated and spams
        # the test log with multi-frame DeprecationWarning tracebacks
        # (~32 hits across read_tools.py + write_tools.py per R3 log).
        order.check_access("read")
    except Exception:
        raise MissingError("Order not visible to this user.")
    # Both project.task and mrp.production are read WITHOUT sudo so portal
    # record rules apply. If a record rule hides them (e.g., MOs are
    # internal-only), the calls degrade to empty results and the return
    # dict surfaces None — exactly what the spec § 4.4 ACL rule wants.
    kj = env["project.task"].search(
        [("sale_order_id", "=", order.id)], limit=1)
    # The readiness fields live on project.task via southbrook_project_mrp,
    # which is NOT a hermes dependency — and the names carried a wrong
    # `southbrook_` prefix (real fields: current_bottleneck_workcenter_id,
    # top_blocker, next_best_action, readiness_score). The unguarded ones 500'd
    # once a kitchen job was linked. Use the correct names AND getattr-guard all,
    # so the tool degrades to None when southbrook_project_mrp isn't installed.
    bottleneck_wc = getattr(kj, "current_bottleneck_workcenter_id", False) if kj else False
    return {
        "stage": order.state,
        "mos": _count_mos_for_order(env, order),
        "bottleneck": bottleneck_wc.name if bottleneck_wc else None,
        "blocker": getattr(kj, "top_blocker", None) if kj else None,
        "next_action": getattr(kj, "next_best_action", None) if kj else None,
        "install_due": (kj.date_deadline.isoformat()
                        if kj and kj.date_deadline else None),
        "readiness_score": getattr(kj, "readiness_score", None) if kj else None,
        "version": getattr(order, "southbrook_version", 1),
    }


def _count_mos_for_order(env, order):
    # sale_mrp links an MO to the sale.order.line it fulfils via `sale_line_id`
    # (singular). The old `sale_order_line_id` field does not exist on
    # mrp.production in v19 (or anywhere in this stack) → get_order_status
    # raised ValueError("Invalid field mrp.production.sale_order_line_id").
    line_ids = order.order_line.ids
    # v19: mrp.production carries `sale_line_id` (not the legacy
    # `sale_order_line_id` from older sample code). Use the canonical
    # field so the search compiles cleanly under v19's domain validator.
    return env["mrp.production"].search_count(
        [("sale_line_id", "in", line_ids)])


@hermes_tool(
    personas=["trade_partner", "sales_rep", "mfg_manager"],
    tier="T0", scope="own_order",
    description="Return the configured detail of a single order line.",
)
def get_order_line(env, order_id: int, line_id: int):
    order = env["sale.order"].browse(order_id)
    try:
        order.check_access("read")
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
            "option_count": len(p.design_option_ids) if hasattr(p, "design_option_ids") else 0,
            "selected": next(
                (o.name for o in getattr(p, "design_option_ids", [])
                 if getattr(o, "is_selected", False)), None),
        }
        for p in projects
    ]


@hermes_tool(
    personas=["trade_partner", "sales_rep", "mfg_manager"],
    tier="T0", scope="own_order",
    description="Return options + approval status of a kitchen project.",
)
def get_kitchen_project(env, project_id: int):
    Project = env["sb.kitchen.project"] if "sb.kitchen.project" in env else None
    if Project is None:
        raise MissingError("Kitchen projects not available on this instance.")
    project = Project.browse(project_id)
    try:
        project.check_access("read")
    except Exception:
        raise MissingError("Project not visible to this user.")
    return {
        "options": [
            {"name": o.name, "is_selected": getattr(o, "is_selected", False)}
            for o in getattr(project, "design_option_ids", [])
        ],
        "approval_status": getattr(project, "approval_status", None),
        "drawings_url": getattr(project, "drawings_url", None),
    }


@hermes_tool(
    personas=["trade_partner", "sales_rep", "mfg_manager"],
    tier="T0", scope="own_order",
    description="Return install schedule + risk flag for an order.",
)
def get_install_schedule(env, order_id: int):
    order = env["sale.order"].browse(order_id)
    try:
        order.check_access("read")
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
        order.check_access("read")
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


# ----------------------------------------------------------------------
# Shop-wide operations visibility (mfg_manager + sales_rep personas).
#
# Three tools give Hermes a live read on the shop floor without exposing
# raw ORM search:
#   - get_shop_capacity   — rolling-window MO counts + WC load
#   - list_shop_blockers  — active MI blockers/warnings shop-wide
#   - list_work_queue     — next-up WOs for a named shop persona
#
# Design notes:
#   • These are SHOP-wide reads: sudo() is safe because scope="global"
#     matches how catalog / pricelist tools work — internal staff view
#     of the plant floor, not partner-scoped.
#   • Window math is bounded to the current calendar frame (today /
#     this ISO week Mon-Sun / current calendar month) so the LLM does
#     not need to reason about arbitrary datetime arithmetic; the
#     window enum locks the query shape.
#   • Empty state returns a self-explanatory note rather than raising —
#     matches the "empty dict/list on miss" convention set by the T0
#     read tools above.
# ----------------------------------------------------------------------

# Persona -> canonical known-user name. Mirrors hermes_question._answer_users
# so a fabio caller and this tool report matching identities.
_WORK_QUEUE_KNOWN_ROLES = {
    "estimator":  "Alex Estimator",
    "cnc":        "Chris CNC",
    "assembler":  "Sam Assembler",
    "finisher":   "Jordan Finisher",
    "installer":  "Taylor Install",
    "production": "Morgan Production",
}


def _shop_window_bounds(window):
    """Return (start_date, end_date) as date objects for the enum.

    Bounds are inclusive: `date_start >= start` and `date_start < end +
    one day` — the search domain adds the +1 day so we return the calendar
    edges here.

    "this_week" is ISO Monday..Sunday. "this_month" is 1st..last-day.
    Unknown windows fall back to today.
    """
    today = datetime.date.today()
    if window == "today":
        return today, today
    if window == "this_month":
        first = today.replace(day=1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        last = today.replace(day=last_day)
        return first, last
    # Default: this_week (Monday..Sunday of the current ISO week).
    monday = today - datetime.timedelta(days=today.weekday())
    sunday = monday + datetime.timedelta(days=6)
    return monday, sunday


@hermes_tool(
    personas=["sales_rep", "mfg_manager"],
    tier="T0", scope="global",
    description=(
        "Return shop-wide MO capacity for a rolling window. Counts "
        "mrp.production records by state (confirmed/progress/to_close/"
        "done) and reports work-center load. Use to answer 'how many MOs "
        "are open this week' or 'is the shop bottlenecked'."),
    parameters={
        "window": {"type": "string", "required": False,
                    "enum": ["today", "this_week", "this_month"],
                    "default": "this_week"},
    },
)
def get_shop_capacity(env, window="this_week"):
    """Aggregate MO counts + work-center load for the requested window.

    The window is a bounded enum; unknown values fall back to this_week.
    Filters `mrp.production` records by their `date_start` (planned or
    actual start — v19 CE unified field, see mrp/models/mrp_production.py).
    Empty shop returns all zeros + a human-readable note.
    """
    if "mrp.production" not in env:
        return {"error": "mrp_not_installed"}

    start, end = _shop_window_bounds(window)
    # Inclusive-end: search domain uses `< end + 1 day` so anything on
    # `end` at any time-of-day is caught.
    end_exclusive = datetime.datetime.combine(
        end + datetime.timedelta(days=1), datetime.time.min)
    start_dt = datetime.datetime.combine(start, datetime.time.min)

    Production = env["mrp.production"].sudo()
    base_domain = [
        ("date_start", ">=", start_dt),
        ("date_start", "<", end_exclusive),
    ]

    mo_counts = {}
    for state in ("confirmed", "progress", "to_close", "done"):
        mo_counts[state] = Production.search_count(
            base_domain + [("state", "=", state)])
    total = sum(mo_counts.values())

    top_work_centers = []
    if "mrp.workorder" in env:
        Workorder = env["mrp.workorder"].sudo()
        wo_domain = [
            ("date_start", ">=", start_dt),
            ("date_start", "<", end_exclusive),
            # Real Odoo 19 CE WO states; 'blocked' is committed (dependency-
            # waiting) load. 'pending'/'waiting' never existed and hid it.
            ("state", "in", ["blocked", "ready", "progress"]),
        ]
        # read_group aggregates duration_expected per workcenter without
        # loading every WO into memory.
        try:
            grouped = Workorder.read_group(
                wo_domain,
                fields=["workcenter_id", "duration_expected:sum"],
                groupby=["workcenter_id"],
                orderby="duration_expected desc",
                limit=5,
            )
        except Exception:  # noqa: BLE001 — defensive: read_group signature
            grouped = []                    # varies across Odoo minor versions
        for row in grouped:
            wc = row.get("workcenter_id")
            wc_name = wc[1] if wc else "(unassigned)"
            top_work_centers.append({
                "work_center": wc_name,
                "open_workorder_count": int(row.get("workcenter_id_count", 0)),
                "planned_hours": float(
                    (row.get("duration_expected") or 0.0) / 60.0),
            })
        # read_group returns highest planned_hours first via orderby, but
        # defensively re-sort in case the ORM ordered by internal key.
        top_work_centers.sort(
            key=lambda r: r["planned_hours"], reverse=True)

    if total == 0 and not top_work_centers:
        note = "No manufacturing orders in the %s window." % window
    else:
        note = (
            "Window %s: %d MOs total (%d in progress, %d confirmed, "
            "%d to close, %d done). Top WCs by planned load listed."
        ) % (window, total, mo_counts["progress"], mo_counts["confirmed"],
             mo_counts["to_close"], mo_counts["done"])

    return {
        "window": window,
        "window_start_iso": start.isoformat(),
        "window_end_iso": end.isoformat(),
        "mo_counts": mo_counts,
        "top_work_centers": top_work_centers,
        "note": note,
    }


@hermes_tool(
    personas=["sales_rep", "mfg_manager"],
    tier="T0", scope="global",
    description=(
        "Return active shop-wide MI checks — blockers (stop-the-line) "
        "or warnings (needs review). Use to answer 'what's blocking "
        "production today' or 'what warnings should we address'."),
    parameters={
        "severity": {"type": "string", "required": False,
                      "enum": ["blocker", "warning"],
                      "default": "blocker"},
        "limit": {"type": "integer", "required": False, "default": 15},
    },
)
def list_shop_blockers(env, severity="blocker", limit=15):
    """Roll up active MI checks at the given severity for the shop.

    Mirrors the guard pattern in hermes_question._answer_mi_checks:
    returns `{"error": "mi_not_installed"}` when the MI addon isn't
    loaded rather than raising. Empty search returns `count=0, items=[]`
    with a human note.
    """
    if "southbrook.mi.check" not in env:
        return {"error": "mi_not_installed"}

    Check = env["southbrook.mi.check"].sudo()
    checks = Check.search([
        ("active", "=", True),
        ("severity", "=", severity),
    ], order="create_date desc, id desc", limit=limit)

    items = []
    for check in checks:
        target = (
            (check.production_id.display_name if check.production_id else None)
            or (check.production_package_id.display_name
                if check.production_package_id else None)
            or "(unlinked)"
        )
        items.append({
            "id": check.id,
            "name": check.name or "",
            "target": target,
            "category": check.category or "",
            "message": check.message or "",
            "recommendation": (
                check.recommendation or check.message or ""),
        })

    if not items:
        note = "No active %s MI checks." % severity
    else:
        note = "Found %d active %s check(s)." % (len(items), severity)

    return {
        "severity": severity,
        "count": len(items),
        "items": items,
        "note": note,
    }


@hermes_tool(
    personas=["mfg_manager"],
    tier="T0", scope="global",
    description=(
        "Return the next-up work items for a specific shop persona "
        "(estimator, cnc, assembler, finisher, installer, production). "
        "For mfg_manager use to answer 'what's on Chris's plate' or "
        "'who is behind schedule'."),
    parameters={
        "persona": {"type": "string", "required": True,
                     "enum": ["estimator", "cnc", "assembler",
                              "finisher", "installer", "production"]},
        "limit": {"type": "integer", "required": False, "default": 10},
    },
)
def list_work_queue(env, persona, limit=10):
    """Return the ready/progress WOs for the named shop persona.

    Persona -> known user name mapping mirrors hermes_question._answer_users.
    v19 CE mrp.workorder has no per-WO user assignment field (only
    working_user_ids / last_working_user_id historical rows); the
    plate-of-work semantic that closest matches the KNOWN_ROLES table
    is the mrp.production.user_id (responsible for the MO). We match
    that way when native mrp.workorder.user_id is absent.

    Unknown persona -> user match returns count=0, items=[] with a note.
    """
    known_name = _WORK_QUEUE_KNOWN_ROLES.get(persona)
    if not known_name:
        return {
            "persona": persona,
            "user_name": None,
            "user_id": None,
            "count": 0,
            "items": [],
            "note": "No user matched for persona %s." % persona,
        }

    user = env["res.users"].sudo().search([
        ("name", "=", known_name),
        ("active", "=", True),
    ], limit=1)
    if not user:
        return {
            "persona": persona,
            "user_name": None,
            "user_id": None,
            "count": 0,
            "items": [],
            "note": "No user matched for persona %s." % persona,
        }

    if "mrp.workorder" not in env:
        return {
            "persona": persona,
            "user_name": user.name,
            "user_id": user.id,
            "count": 0,
            "items": [],
            "note": (
                "mrp not installed on this deployment; no work-queue "
                "tracking available."),
        }

    Workorder = env["mrp.workorder"].sudo()
    wo_fields = Workorder._fields
    # Prefer a direct WO user_id/assign field if the model exposes one;
    # otherwise fall back to production.user_id (v19 CE default surface).
    if "user_id" in wo_fields:
        domain = [
            ("user_id", "=", user.id),
            ("state", "in", ["ready", "progress"]),
        ]
    else:
        domain = [
            ("production_id.user_id", "=", user.id),
            ("state", "in", ["ready", "progress"]),
        ]

    # date_planned_start doesn't exist on v19 CE mrp.workorder — the
    # canonical planned/actual start column is `date_start`.
    order = "date_start asc, id asc"
    workorders = Workorder.search(domain, order=order, limit=limit)

    items = []
    for wo in workorders:
        items.append({
            "id": wo.id,
            "name": wo.display_name or wo.name or "",
            "production": (
                wo.production_id.name if wo.production_id else ""),
            "state": wo.state,
            "date_start": (
                wo.date_start.isoformat() if wo.date_start else None),
            "duration_expected": float(wo.duration_expected or 0.0),
        })

    if not items:
        note = "No ready or in-progress work orders for %s." % user.name
    else:
        note = "%s has %d ready/in-progress WO(s)." % (user.name, len(items))

    return {
        "persona": persona,
        "user_name": user.name,
        "user_id": user.id,
        "count": len(items),
        "items": items,
        "note": note,
    }
