# SPDX-License-Identifier: LGPL-3.0-only
"""KitchenForge Agent Filesystem — magicpath.ai/files-style virtual FS.

Each *path* is a stable, schema-named view onto Odoo records. Agents list
directories, read YAML/JSON manifests, and write back patches. Every write
goes through a model method (NOT a raw ORM update) so business rules,
constraints, and ECO/PLM gates stay enforced.

Path namespace:

    /templates/                   project.project where is_template
    /templates/<slug>.yaml        single template manifest
    /templates/<slug>/zones/      template zones
    /templates/<slug>/zones/<n>.yaml

    /projects/                    instantiated projects (is_template=False)
    /projects/<ref>.yaml          single project manifest (KF000001)
    /projects/<ref>/zones/<n>.yaml
    /projects/<ref>/quote.yaml    current sale.order state
    /projects/<ref>/bom.yaml      rolled-up BoM tree (read-only)
    /projects/<ref>/tasks/<n>.yaml
    /projects/<ref>/mo/<n>.yaml

    /catalog/cabinets/<tmpl>.yaml configurable product templates
    /catalog/attributes.yaml      attribute schema (the 11 attributes)
    /catalog/rules.yaml           exclusion + price-extra rules
    /catalog/hardware/marathon/   Marathon SKUs (from southbrook_hardware_catalog)

    /shop/workcenters/<n>.yaml
    /shop/schedule.yaml           upcoming MO schedule
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from odoo import _
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError


FS_SCHEMA = "kitchenforge.agent.fs.v1"


class NotFound(Exception):
    """Raised when an agent requests a path that maps to no record."""


class ReadOnly(Exception):
    """Raised when an agent tries to write to a derived/read-only path."""


# ----------------------------------------------------------------------
# Path parsing
# ----------------------------------------------------------------------
_PATH_RE = re.compile(r"^/?(?P<rest>.*?)/?$")


def split_path(path: str) -> List[str]:
    """Normalize and split. Empty path or '/' returns []."""
    m = _PATH_RE.match(path or "")
    rest = (m.group("rest") if m else "") or ""
    return [seg for seg in rest.split("/") if seg]


def slugify(value: str) -> str:
    """File-safe slug. Stable enough for agent path round-trips."""
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "unnamed"


# ----------------------------------------------------------------------
# Resolver registry: maps top-level segment -> dispatcher
# ----------------------------------------------------------------------
def resolve(env, path: str) -> Dict[str, Any]:
    """Return a directory listing OR a file payload for `path`.

    Result shape:
        {"kind": "dir", "path": "/...", "entries": [{name, kind, path, ...}], "schema": ...}
        {"kind": "file", "path": "/...", "content": {...}, "etag": "...", "schema": ...}
    """
    segs = split_path(path)
    if not segs:
        return _list_root(env)

    top = segs[0]
    handler = _RESOLVERS.get(top)
    if not handler:
        raise NotFound(f"unknown namespace: /{top}")
    return handler(env, segs[1:])


def write(env, path: str, content: Dict[str, Any], if_match: Optional[str] = None
          ) -> Dict[str, Any]:
    """Write a YAML/JSON-decoded payload to `path`. Returns the new file
    representation (with new etag)."""
    segs = split_path(path)
    if not segs:
        raise ReadOnly("cannot write to root")
    top = segs[0]
    writer = _WRITERS.get(top)
    if not writer:
        raise ReadOnly(f"namespace /{top} is read-only")
    return writer(env, segs[1:], content, if_match)


# ----------------------------------------------------------------------
# Root listing
# ----------------------------------------------------------------------
def _list_root(env) -> Dict[str, Any]:
    return {
        "kind": "dir",
        "path": "/",
        "schema": FS_SCHEMA,
        "entries": [
            {"name": "templates", "kind": "dir", "path": "/templates",
             "desc": "Reusable project shapes (Full Kitchen, Partial Reno, ...)"},
            {"name": "projects", "kind": "dir", "path": "/projects",
             "desc": "Instantiated kitchen jobs."},
            {"name": "catalog", "kind": "dir", "path": "/catalog",
             "desc": "Cabinet templates, attributes, rules, hardware (Marathon)."},
            {"name": "shop", "kind": "dir", "path": "/shop",
             "desc": "Workcenters and live production schedule."},
        ],
    }


# ----------------------------------------------------------------------
# /templates/...
# ----------------------------------------------------------------------
def _resolve_templates(env, sub: List[str]) -> Dict[str, Any]:
    Project = env["project.project"]
    if not sub:
        templates = Project.search([("is_template", "=", True)], order="name")
        return {
            "kind": "dir",
            "path": "/templates",
            "schema": FS_SCHEMA,
            "entries": [{
                "name": f"{slugify(t.name)}.yaml",
                "kind": "file",
                "path": f"/templates/{slugify(t.name)}.yaml",
                "id": t.id,
                "kf_kind": t.kitchenforge_kind,
                "zones": len(t.default_cabinet_zone_ids),
            } for t in templates],
        }

    # /templates/<slug>.yaml or /templates/<slug>/...
    slug = sub[0]
    if slug.endswith(".yaml"):
        slug = slug[: -len(".yaml")]
    tmpl = _find_template(env, slug)
    if len(sub) == 1 and sub[0].endswith(".yaml"):
        return _template_to_file(tmpl)
    # subpath: /templates/<slug>/zones[/<n>.yaml]
    if len(sub) >= 2 and sub[1] == "zones":
        if len(sub) == 2:
            return _list_template_zones(tmpl)
        zone_name = sub[2]
        return _zone_to_file(tmpl, zone_name)
    raise NotFound(f"unknown template path: /templates/{'/'.join(sub)}")


def _find_template(env, slug: str):
    Project = env["project.project"]
    candidates = Project.search([("is_template", "=", True)])
    for t in candidates:
        if slugify(t.name) == slug:
            return t
    raise NotFound(f"no template matches slug '{slug}'")


def _template_to_file(tmpl) -> Dict[str, Any]:
    content = {
        "schema": FS_SCHEMA,
        "kind": "template",
        "id": tmpl.id,
        "name": tmpl.name,
        "kitchenforge_kind": tmpl.kitchenforge_kind,
        "default_cabinet_zone_count": len(tmpl.default_cabinet_zone_ids),
        "cut_spec": tmpl.cut_spec_id.display_name if tmpl.cut_spec_id else None,
        "bom_version_lock": tmpl.bom_version_lock,
        "tools": [
            {"id": "instantiate",
             "endpoint": "POST /agent/v1/tools/instantiate",
             "args": {"template_id": tmpl.id,
                      "partner_id": "<res.partner id>",
                      "dims": {"room_width_mm": "int",
                               "room_depth_mm": "int",
                               "ceiling_height_mm": "int"}}},
        ],
    }
    return {
        "kind": "file",
        "path": f"/templates/{slugify(tmpl.name)}.yaml",
        "etag": _etag(tmpl),
        "schema": FS_SCHEMA,
        "content": content,
    }


def _list_template_zones(tmpl) -> Dict[str, Any]:
    return {
        "kind": "dir",
        "path": f"/templates/{slugify(tmpl.name)}/zones",
        "schema": FS_SCHEMA,
        "entries": [{
            "name": f"{line.sequence:03d}-{slugify(line.name)}.yaml",
            "kind": "file",
            "path": f"/templates/{slugify(tmpl.name)}/zones/"
                    f"{line.sequence:03d}-{slugify(line.name)}.yaml",
            "id": line.id,
            "product": line.product_tmpl_id.display_name,
        } for line in tmpl.default_cabinet_zone_ids],
    }


def _zone_to_file(tmpl, zone_name: str) -> Dict[str, Any]:
    if zone_name.endswith(".yaml"):
        zone_name = zone_name[: -len(".yaml")]
    for line in tmpl.default_cabinet_zone_ids:
        s = f"{line.sequence:03d}-{slugify(line.name)}"
        if s == zone_name:
            return {
                "kind": "file",
                "path": f"/templates/{slugify(tmpl.name)}/zones/{zone_name}.yaml",
                "etag": _etag(line),
                "schema": FS_SCHEMA,
                "content": {
                    "schema": FS_SCHEMA,
                    "kind": "template.zone",
                    "id": line.id,
                    "sequence": line.sequence,
                    "name": line.name,
                    "product_tmpl_id": line.product_tmpl_id.id,
                    "product_tmpl_name": line.product_tmpl_id.name,
                    "quantity": line.quantity,
                    "dimensions_mm": {
                        "width": line.width_mm,
                        "height": line.height_mm,
                        "depth": line.depth_mm,
                    },
                    "preselected_attribute_values":
                        json.loads(line.preselected_attribute_values_json or "{}"),
                    "notes": line.notes,
                },
            }
    raise NotFound(f"no zone matches '{zone_name}'")


# ----------------------------------------------------------------------
# /projects/...
# ----------------------------------------------------------------------
def _resolve_projects(env, sub: List[str]) -> Dict[str, Any]:
    Project = env["project.project"]
    if not sub:
        projs = Project.search([("is_template", "=", False)], order="id desc", limit=200)
        return {
            "kind": "dir",
            "path": "/projects",
            "schema": FS_SCHEMA,
            "entries": [{
                "name": f"{p.id}.yaml",
                "kind": "file",
                "path": f"/projects/{p.id}.yaml",
                "id": p.id,
                "label": p.name,
                "partner": p.partner_id.name,
                "has_sale_order": bool(p.sale_order_id),
            } for p in projs],
        }
    head = sub[0]
    if head.endswith(".yaml"):
        head = head[: -len(".yaml")]
    proj = _find_project(env, head)
    if len(sub) == 1 and sub[0].endswith(".yaml"):
        return _project_to_file(proj)
    if len(sub) >= 2:
        if sub[1] == "quote.yaml":
            return _quote_to_file(proj)
        if sub[1] == "bom.yaml":
            return _bom_to_file(proj)
        if sub[1] == "zones":
            return _list_project_zones(proj) if len(sub) == 2 else _project_zone(proj, sub[2])
        if sub[1] == "tasks":
            return _list_tasks(proj) if len(sub) == 2 else _task_to_file(proj, sub[2])
        if sub[1] == "mo":
            return _list_mos(proj) if len(sub) == 2 else _mo_to_file(proj, sub[2])
    raise NotFound(f"unknown project path: /projects/{'/'.join(sub)}")


def _find_project(env, ref: str):
    if ref.isdigit():
        proj = env["project.project"].browse(int(ref)).exists()
        if proj:
            return proj
    proj = env["project.project"].search([("name", "=", ref)], limit=1)
    if proj:
        return proj
    raise NotFound(f"no project matches '{ref}'")


def _project_to_file(proj) -> Dict[str, Any]:
    so = proj.sale_order_id
    return {
        "kind": "file",
        "path": f"/projects/{proj.id}.yaml",
        "etag": _etag(proj),
        "schema": FS_SCHEMA,
        "content": {
            "schema": FS_SCHEMA,
            "kind": "project",
            "id": proj.id,
            "name": proj.name,
            "partner": {"id": proj.partner_id.id, "name": proj.partner_id.name},
            "instantiated_from": (
                {"id": proj.instantiated_from_template_id.id,
                 "name": proj.instantiated_from_template_id.name}
                if proj.instantiated_from_template_id else None),
            "sale_order": {"id": so.id, "name": so.name, "state": so.state} if so else None,
            "cut_spec": proj.cut_spec_id.display_name if proj.cut_spec_id else None,
            "task_count": proj.task_count,
            "tools": [
                {"id": "add_zone",
                 "endpoint": "POST /agent/v1/tools/add_zone",
                 "args": {"project_id": proj.id, "zone": {"product_tmpl_id": "int",
                                                          "quantity": "float",
                                                          "width_mm": "int"}}},
                {"id": "confirm_quote",
                 "endpoint": "POST /agent/v1/tools/confirm_quote",
                 "args": {"project_id": proj.id}},
                {"id": "release_mos",
                 "endpoint": "POST /agent/v1/tools/release_mos",
                 "args": {"project_id": proj.id}},
                {"id": "raise_eco",
                 "endpoint": "POST /agent/v1/tools/raise_eco",
                 "args": {"project_id": proj.id, "target_bom_id": "int",
                          "reason": "str"}},
            ],
        },
    }


def _list_project_zones(proj) -> Dict[str, Any]:
    so = proj.sale_order_id
    lines = so.order_line if so else proj.env["sale.order.line"].browse([])
    return {
        "kind": "dir",
        "path": f"/projects/{proj.id}/zones",
        "schema": FS_SCHEMA,
        "entries": [{
            "name": f"{i:03d}-{slugify(line.product_id.display_name)}.yaml",
            "kind": "file",
            "path": f"/projects/{proj.id}/zones/{i:03d}-{slugify(line.product_id.display_name)}.yaml",
            "id": line.id,
            "product": line.product_id.display_name,
            "qty": line.product_uom_qty,
            "subtotal": line.price_subtotal,
        } for i, line in enumerate(lines, start=1)],
    }


def _project_zone(proj, zone_name: str) -> Dict[str, Any]:
    if zone_name.endswith(".yaml"):
        zone_name = zone_name[: -len(".yaml")]
    so = proj.sale_order_id
    if not so:
        raise NotFound("project has no sale order yet")
    for i, line in enumerate(so.order_line, start=1):
        s = f"{i:03d}-{slugify(line.product_id.display_name)}"
        if s == zone_name:
            return {
                "kind": "file",
                "path": f"/projects/{proj.id}/zones/{zone_name}.yaml",
                "etag": _etag(line),
                "schema": FS_SCHEMA,
                "content": {
                    "schema": FS_SCHEMA,
                    "kind": "project.zone",
                    "id": line.id,
                    "product_id": line.product_id.id,
                    "product_name": line.product_id.display_name,
                    "quantity": line.product_uom_qty,
                    "dimensions_mm": {
                        "width": line.kitchenforge_zone_width_mm,
                        "height": line.kitchenforge_zone_height_mm,
                        "depth": line.kitchenforge_zone_depth_mm,
                    },
                    "preselected_attribute_values":
                        json.loads(line.kitchenforge_preselected_attrs_json or "{}"),
                    "price_unit": line.price_unit,
                    "price_subtotal": line.price_subtotal,
                },
            }
    raise NotFound(f"no zone matches '{zone_name}'")


def _quote_to_file(proj) -> Dict[str, Any]:
    so = proj.sale_order_id
    if not so:
        raise NotFound("no sale order on project")
    return {
        "kind": "file",
        "path": f"/projects/{proj.id}/quote.yaml",
        "etag": _etag(so),
        "schema": FS_SCHEMA,
        "content": {
            "schema": FS_SCHEMA,
            "kind": "quote",
            "id": so.id,
            "name": so.name,
            "state": so.state,
            "partner": so.partner_id.name,
            "amount_untaxed": so.amount_untaxed,
            "amount_tax": so.amount_tax,
            "amount_total": so.amount_total,
            "currency": so.currency_id.name,
            "lines": [{
                "id": line.id,
                "product": line.product_id.display_name,
                "qty": line.product_uom_qty,
                "unit_price": line.price_unit,
                "subtotal": line.price_subtotal,
            } for line in so.order_line],
        },
    }


def _bom_to_file(proj) -> Dict[str, Any]:
    so = proj.sale_order_id
    if not so:
        raise NotFound("no sale order on project")
    BoM = proj.env["mrp.bom"]
    rollup = []
    for line in so.order_line:
        # Odoo 19 _bom_find signature: products=recordset, company_id=int,
        # bom_type='normal' -> dict[product, mrp.bom]. See
        # southbrook_mrp_pm/models/sale_order.py:_resolve_bom_for_line for
        # the defensive version that handles older signatures.
        try:
            found = BoM._bom_find(
                products=line.product_id,
                company_id=so.company_id.id,
                bom_type="normal",
            )
            bom = found.get(line.product_id) if isinstance(found, dict) else None
        except TypeError:
            bom = BoM.search([
                ("product_tmpl_id", "=", line.product_id.product_tmpl_id.id),
                ("type", "=", "normal"),
            ], order="sequence", limit=1)
        if not bom:
            continue
        rollup.append({
            "line_id": line.id,
            "product": line.product_id.display_name,
            "bom_id": bom.id,
            "bom_code": bom.code or "",
            "components": [{
                "product_id": comp.product_id.id,
                "name": comp.product_id.display_name,
                "qty": comp.product_qty,
                "uom": comp.product_uom_id.name,
            } for comp in bom.bom_line_ids],
        })
    return {
        "kind": "file",
        "path": f"/projects/{proj.id}/bom.yaml",
        "etag": _etag(so),
        "schema": FS_SCHEMA,
        "content": {
            "schema": FS_SCHEMA,
            "kind": "bom.rollup",
            "project_id": proj.id,
            "sale_order_id": so.id,
            "lines": rollup,
        },
    }


def _list_tasks(proj) -> Dict[str, Any]:
    return {
        "kind": "dir",
        "path": f"/projects/{proj.id}/tasks",
        "schema": FS_SCHEMA,
        "entries": [{
            "name": f"{t.id}.yaml", "kind": "file",
            "path": f"/projects/{proj.id}/tasks/{t.id}.yaml",
            "id": t.id, "label": t.name,
            "stage": t.stage_id.name if t.stage_id else None,
        } for t in proj.task_ids],
    }


def _task_to_file(proj, ref: str) -> Dict[str, Any]:
    if ref.endswith(".yaml"):
        ref = ref[: -len(".yaml")]
    task = proj.env["project.task"].browse(int(ref)).exists() if ref.isdigit() else None
    if not task or task.project_id != proj:
        raise NotFound(f"no task '{ref}'")
    return {
        "kind": "file",
        "path": f"/projects/{proj.id}/tasks/{task.id}.yaml",
        "etag": _etag(task),
        "schema": FS_SCHEMA,
        "content": {
            "schema": FS_SCHEMA,
            "kind": "task",
            "id": task.id,
            "name": task.name,
            "stage": task.stage_id.name if task.stage_id else None,
            "deadline": str(task.date_deadline) if task.date_deadline else None,
            "mo_count": len(task.production_ids) if hasattr(task, "production_ids") else 0,
        },
    }


def _list_mos(proj) -> Dict[str, Any]:
    MO = proj.env["mrp.production"]
    mos = MO.search([
        ("sale_line_id.order_id", "=", proj.sale_order_id.id if proj.sale_order_id else 0)])
    return {
        "kind": "dir",
        "path": f"/projects/{proj.id}/mo",
        "schema": FS_SCHEMA,
        "entries": [{
            "name": f"{m.id}.yaml", "kind": "file",
            "path": f"/projects/{proj.id}/mo/{m.id}.yaml",
            "id": m.id, "name": m.name, "state": m.state,
            "product": m.product_id.display_name,
            "qty": m.product_qty,
        } for m in mos],
    }


def _mo_to_file(proj, ref: str) -> Dict[str, Any]:
    if ref.endswith(".yaml"):
        ref = ref[: -len(".yaml")]
    mo = proj.env["mrp.production"].browse(int(ref)).exists() if ref.isdigit() else None
    if not mo:
        raise NotFound(f"no MO '{ref}'")
    return {
        "kind": "file",
        "path": f"/projects/{proj.id}/mo/{mo.id}.yaml",
        "etag": _etag(mo),
        "schema": FS_SCHEMA,
        "content": {
            "schema": FS_SCHEMA,
            "kind": "mo",
            "id": mo.id,
            "name": mo.name,
            "state": mo.state,
            "product": mo.product_id.display_name,
            "qty": mo.product_qty,
            "bom_id": mo.bom_id.id if mo.bom_id else None,
            "date_planned_start": str(mo.date_start) if mo.date_start else None,
        },
    }


# ----------------------------------------------------------------------
# /catalog/...
# ----------------------------------------------------------------------
def _resolve_catalog(env, sub: List[str]) -> Dict[str, Any]:
    if not sub:
        return {
            "kind": "dir",
            "path": "/catalog",
            "schema": FS_SCHEMA,
            "entries": [
                {"name": "cabinets", "kind": "dir", "path": "/catalog/cabinets"},
                {"name": "attributes.yaml", "kind": "file",
                 "path": "/catalog/attributes.yaml"},
                {"name": "rules.yaml", "kind": "file", "path": "/catalog/rules.yaml"},
                {"name": "hardware", "kind": "dir", "path": "/catalog/hardware"},
            ],
        }
    if sub[0] == "cabinets":
        return _list_cabinets(env) if len(sub) == 1 else _cabinet_to_file(env, sub[1])
    if sub[0] == "attributes.yaml":
        return _attributes_file(env)
    if sub[0] == "rules.yaml":
        return _rules_file(env)
    if sub[0] == "hardware":
        if len(sub) == 1:
            return _list_hardware_brands(env)
        if sub[1] == "marathon":
            return _list_marathon(env) if len(sub) == 2 else _marathon_sku(env, sub[2])
    raise NotFound(f"unknown catalog path: /catalog/{'/'.join(sub)}")


def _list_cabinets(env) -> Dict[str, Any]:
    Tmpl = env["product.template"]
    tmpls = Tmpl.search([("config_ok", "=", True)], limit=400)
    return {
        "kind": "dir",
        "path": "/catalog/cabinets",
        "schema": FS_SCHEMA,
        "entries": [{
            "name": f"{t.id}.yaml", "kind": "file",
            "path": f"/catalog/cabinets/{t.id}.yaml",
            "id": t.id, "label": t.name,
        } for t in tmpls],
    }


def _cabinet_to_file(env, ref: str) -> Dict[str, Any]:
    if ref.endswith(".yaml"):
        ref = ref[: -len(".yaml")]
    tmpl = env["product.template"].browse(int(ref)).exists() if ref.isdigit() else None
    if not tmpl:
        raise NotFound(f"no cabinet template '{ref}'")
    attr_lines = tmpl.attribute_line_ids if hasattr(tmpl, "attribute_line_ids") else []
    return {
        "kind": "file",
        "path": f"/catalog/cabinets/{tmpl.id}.yaml",
        "etag": _etag(tmpl),
        "schema": FS_SCHEMA,
        "content": {
            "schema": FS_SCHEMA,
            "kind": "catalog.cabinet",
            "id": tmpl.id,
            "name": tmpl.name,
            "config_ok": tmpl.config_ok,
            "list_price": tmpl.list_price,
            "attributes": [{
                "id": al.attribute_id.id,
                "name": al.attribute_id.name,
                "values": [{"id": v.id, "name": v.name}
                           for v in al.value_ids],
            } for al in attr_lines],
        },
    }


def _attributes_file(env) -> Dict[str, Any]:
    Attr = env["product.attribute"]
    attrs = Attr.search([], limit=200)
    return {
        "kind": "file",
        "path": "/catalog/attributes.yaml",
        "etag": "attrs-" + str(len(attrs)),
        "schema": FS_SCHEMA,
        "content": {
            "schema": FS_SCHEMA,
            "kind": "catalog.attributes",
            "attributes": [{
                "id": a.id, "name": a.name,
                "values": [{"id": v.id, "name": v.name} for v in a.value_ids],
            } for a in attrs],
        },
    }


def _rules_file(env) -> Dict[str, Any]:
    """Surface exclusion rules. Tries the OCA configurator model; degrades
    gracefully if a host doesn't ship it."""
    Rule = env.get("product.config.line")
    rules = Rule.search([], limit=500) if Rule is not None else []
    return {
        "kind": "file",
        "path": "/catalog/rules.yaml",
        "etag": "rules-" + str(len(rules) if rules else 0),
        "schema": FS_SCHEMA,
        "content": {
            "schema": FS_SCHEMA,
            "kind": "catalog.rules",
            "rule_count": len(rules) if rules else 0,
            "note": "Detailed rule expansion is host-specific; see "
                    "product_configurator addon for the source of truth.",
        },
    }


def _list_hardware_brands(env) -> Dict[str, Any]:
    Brand = env.get("southbrook.hardware.brand")
    brands = Brand.search([]) if Brand is not None else []
    return {
        "kind": "dir",
        "path": "/catalog/hardware",
        "schema": FS_SCHEMA,
        "entries": [{
            "name": slugify(b.name), "kind": "dir",
            "path": f"/catalog/hardware/{slugify(b.name)}",
            "id": b.id, "label": b.name,
        } for b in brands],
    }


def _list_marathon(env) -> Dict[str, Any]:
    """Marathon catalog SKUs — drives the channel-partner play."""
    Cat = env.get("southbrook.hardware.catalog")
    Brand = env.get("southbrook.hardware.brand")
    brand_ids = []
    if Brand is not None:
        brand = Brand.search([("name", "ilike", "marathon")], limit=1)
        brand_ids = brand.ids
    skus = []
    if Cat is not None and brand_ids:
        skus = Cat.search([("brand_id", "in", brand_ids)], limit=500)
    elif Cat is not None:
        skus = Cat.search([], limit=500)
    return {
        "kind": "dir",
        "path": "/catalog/hardware/marathon",
        "schema": FS_SCHEMA,
        "entries": [{
            "name": f"{s.id}.yaml", "kind": "file",
            "path": f"/catalog/hardware/marathon/{s.id}.yaml",
            "id": s.id, "label": getattr(s, "display_name", str(s.id)),
        } for s in skus],
    }


def _marathon_sku(env, ref: str) -> Dict[str, Any]:
    if ref.endswith(".yaml"):
        ref = ref[: -len(".yaml")]
    Cat = env.get("southbrook.hardware.catalog")
    sku = Cat.browse(int(ref)).exists() if Cat is not None and ref.isdigit() else None
    if not sku:
        raise NotFound(f"no hardware SKU '{ref}'")
    return {
        "kind": "file",
        "path": f"/catalog/hardware/marathon/{sku.id}.yaml",
        "etag": _etag(sku),
        "schema": FS_SCHEMA,
        "content": {
            "schema": FS_SCHEMA,
            "kind": "catalog.hardware.sku",
            "id": sku.id,
            "label": getattr(sku, "display_name", None),
            "brand": getattr(sku.brand_id, "name", None) if hasattr(sku, "brand_id") else None,
        },
    }


# ----------------------------------------------------------------------
# /shop/...
# ----------------------------------------------------------------------
def _resolve_shop(env, sub: List[str]) -> Dict[str, Any]:
    if not sub:
        return {
            "kind": "dir", "path": "/shop", "schema": FS_SCHEMA,
            "entries": [
                {"name": "workcenters", "kind": "dir", "path": "/shop/workcenters"},
                {"name": "schedule.yaml", "kind": "file", "path": "/shop/schedule.yaml"},
            ],
        }
    if sub[0] == "workcenters":
        wcs = env["mrp.workcenter"].search([])
        if len(sub) == 1:
            return {
                "kind": "dir", "path": "/shop/workcenters", "schema": FS_SCHEMA,
                "entries": [{
                    "name": f"{w.id}.yaml", "kind": "file",
                    "path": f"/shop/workcenters/{w.id}.yaml",
                    "id": w.id, "label": w.name,
                } for w in wcs],
            }
        ref = sub[1][: -len(".yaml")] if sub[1].endswith(".yaml") else sub[1]
        wc = env["mrp.workcenter"].browse(int(ref)).exists() if ref.isdigit() else None
        if not wc:
            raise NotFound(f"no workcenter '{ref}'")
        return {
            "kind": "file", "path": f"/shop/workcenters/{wc.id}.yaml",
            "etag": _etag(wc), "schema": FS_SCHEMA,
            "content": {
                "schema": FS_SCHEMA, "kind": "shop.workcenter",
                "id": wc.id, "name": wc.name,
                "capacity": wc.default_capacity,
                "efficiency": wc.time_efficiency,
            },
        }
    if sub[0] == "schedule.yaml":
        mos = env["mrp.production"].search(
            [("state", "in", ["confirmed", "progress", "to_close"])],
            order="date_start", limit=200)
        return {
            "kind": "file", "path": "/shop/schedule.yaml",
            "etag": "sched-" + str(len(mos)), "schema": FS_SCHEMA,
            "content": {
                "schema": FS_SCHEMA, "kind": "shop.schedule",
                "entries": [{
                    "mo": m.name, "product": m.product_id.display_name,
                    "qty": m.product_qty, "state": m.state,
                    "start": str(m.date_start) if m.date_start else None,
                } for m in mos],
            },
        }
    raise NotFound(f"unknown shop path: /shop/{'/'.join(sub)}")


# ----------------------------------------------------------------------
# Writers — only template zones + project zones are mutable through the fs
# ----------------------------------------------------------------------
def _write_templates(env, sub: List[str], content: Dict[str, Any],
                      if_match: Optional[str]) -> Dict[str, Any]:
    if len(sub) >= 3 and sub[1] == "zones":
        slug = sub[0].removesuffix(".yaml") if sub[0].endswith(".yaml") else sub[0]
        tmpl = _find_template(env, slug)
        return _write_template_zone(env, tmpl, sub[2], content, if_match)
    raise ReadOnly("only /templates/<slug>/zones/<n>.yaml is writable")


def _write_template_zone(env, tmpl, zone_name: str, content: Dict[str, Any],
                          if_match: Optional[str]) -> Dict[str, Any]:
    if zone_name.endswith(".yaml"):
        zone_name = zone_name[: -len(".yaml")]
    Line = env["kitchenforge.template.line"]
    target = None
    for line in tmpl.default_cabinet_zone_ids:
        if f"{line.sequence:03d}-{slugify(line.name)}" == zone_name:
            target = line
            break
    vals = {
        "name": content.get("name"),
        "sequence": content.get("sequence", 10),
        "product_tmpl_id": content.get("product_tmpl_id"),
        "quantity": content.get("quantity", 1.0),
        "width_mm": content.get("dimensions_mm", {}).get("width", 600),
        "height_mm": content.get("dimensions_mm", {}).get("height", 720),
        "depth_mm": content.get("dimensions_mm", {}).get("depth", 580),
        "preselected_attribute_values_json": json.dumps(
            content.get("preselected_attribute_values") or {}),
        "notes": content.get("notes"),
    }
    if target:
        if if_match and if_match != _etag(target):
            raise ValidationError(_("etag mismatch on /templates/.../%s.yaml") % zone_name)
        target.write({k: v for k, v in vals.items() if v is not None})
    else:
        vals["template_project_id"] = tmpl.id
        target = Line.create({k: v for k, v in vals.items() if v is not None})
    return _zone_to_file(tmpl, f"{target.sequence:03d}-{slugify(target.name)}")


def _write_projects(env, sub: List[str], content: Dict[str, Any],
                     if_match: Optional[str]) -> Dict[str, Any]:
    """Allow agents to edit the quote line (zone) attributes."""
    if len(sub) >= 3 and sub[1] == "zones":
        head = sub[0].removesuffix(".yaml") if sub[0].endswith(".yaml") else sub[0]
        proj = _find_project(env, head)
        so = proj.sale_order_id
        if not so:
            raise NotFound("project has no sale order")
        zone_name = sub[2].removesuffix(".yaml") if sub[2].endswith(".yaml") else sub[2]
        for i, line in enumerate(so.order_line, start=1):
            if f"{i:03d}-{slugify(line.product_id.display_name)}" == zone_name:
                if if_match and if_match != _etag(line):
                    raise ValidationError(_("etag mismatch on zone %s") % zone_name)
                upd = {}
                if "quantity" in content:
                    upd["product_uom_qty"] = content["quantity"]
                dims = content.get("dimensions_mm") or {}
                if "width" in dims:
                    upd["kitchenforge_zone_width_mm"] = dims["width"]
                if "height" in dims:
                    upd["kitchenforge_zone_height_mm"] = dims["height"]
                if "depth" in dims:
                    upd["kitchenforge_zone_depth_mm"] = dims["depth"]
                if "preselected_attribute_values" in content:
                    upd["kitchenforge_preselected_attrs_json"] = json.dumps(
                        content["preselected_attribute_values"])
                line.write(upd)
                return _project_zone(proj, zone_name)
        raise NotFound(f"no zone '{zone_name}'")
    raise ReadOnly("only /projects/<ref>/zones/<n>.yaml is writable via fs")


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _etag(record) -> str:
    """Cheap etag from write_date + id. Survives ORM updates; misses raw SQL."""
    wd = getattr(record, "write_date", None)
    return f"{record._name}:{record.id}:{wd.isoformat() if wd else 'na'}"


_RESOLVERS = {
    "templates": _resolve_templates,
    "projects": _resolve_projects,
    "catalog": _resolve_catalog,
    "shop": _resolve_shop,
}

_WRITERS = {
    "templates": _write_templates,
    "projects": _write_projects,
}
