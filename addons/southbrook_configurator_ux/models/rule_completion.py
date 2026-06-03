# SPDX-License-Identifier: LGPL-3.0-only
"""Rewrite OCA product.config.line rules into a form the engine
actually handles.

The southbrook_estimating seed shipped per-series rules like:
    "Contractor → box_material allowed = [white_melamine]"
    "Signature  → box_material allowed = [maple]"

That structure relies on the OCA whitelist semantics. The intent was
that Contemporary + Elegance (with no rule) would leave both materials
unrestricted. But OCA's values_available works per-VALUE:

    For each value V, find every config.line that mentions V in its
    value_ids. Combine those config.lines' domains with AND. If the
    combined domain matches current picks, V is available.

So White Melamine (mentioned only in the Contractor rule) is available
ONLY when picks match "Series=Contractor". When Contemporary is
picked, the Contractor rule's domain doesn't match → White Melamine is
disabled. Same for Maple under Elegance. The customer sees BOTH box
materials struck through.

Adding more rules makes it WORSE: each value's combined domain is
ANDed across all its config.lines. A White Melamine line under
{Contractor, Contemporary, Elegance} would require all three picks
simultaneously (impossible).

The fix: ONE config.line per (template × value), with a single domain
expressing the OR-list of series that allow that value. This module:

  1. DELETES every existing config.line for Box Material + Door Style
     on the Q8 templates (idempotently — by tmpl × attribute_line scope).
  2. CREATES "Series allows <Value>" domains as needed.
  3. CREATES exactly one config.line per (template × value) with the
     correct domain.

Per-value allow sets (CLAUDE.md §5 + workbook spec):
    White Melamine: Contractor, Contemporary, Elegance
    Maple:                       Contemporary, Elegance, Signature
    Thermofoil:     Contractor, Contemporary,           Signature
    Five-Piece:                  Contemporary, Elegance, Signature
    Custom:                                              Signature
"""
from odoo import api, models


# Allow lists per value. Keys are attribute_value names; values are the
# series names that permit that value.
_BOX_MATERIAL_ALLOW = {
    "White Melamine": ["Contractor Series", "Contemporary", "Elegance"],
    "Maple":          ["Contemporary", "Elegance", "Signature"],
}
_DOOR_STYLE_ALLOW = {
    "Thermofoil Slab — White":  ["Contractor Series", "Contemporary",
                                  "Signature"],
    "Five-Piece Woodgrain":     ["Contemporary", "Elegance", "Signature"],
    "Custom (Signature)":       ["Signature"],
}


def _domain_name_for(value_name):
    """The human-readable name used to identify the dedicated 'allow' domain
    for this value. Keying by value name keeps the rule table grep-friendly."""
    return f"Series allows {value_name}"


class RuleCompletion(models.AbstractModel):
    _name = "southbrook.configurator_ux.rule_completion"
    _description = "Rewrite Box Material + Door Style rules into unified per-value form"

    @api.model
    def complete_rules(self):
        Domain = self.env["product.config.domain"]
        DomainLine = self.env["product.config.domain.line"]
        ConfigLine = self.env["product.config.line"]
        Attr = self.env["product.attribute"]
        AttrVal = self.env["product.attribute.value"]
        AttrLine = self.env["product.template.attribute.line"]

        series_attr = Attr.search([("name", "=", "Series")], limit=1)
        if not series_attr:
            return {"error": "Series attribute missing"}

        series_value_by_name = {
            v.name: v for v in AttrVal.search(
                [("attribute_id", "=", series_attr.id)])
        }

        box_attr = Attr.search([("name", "=", "Box Material")], limit=1)
        door_attr = Attr.search([("name", "=", "Door Style")], limit=1)
        box_vals = {v.name: v for v in AttrVal.search(
            [("attribute_id", "=", box_attr.id)])} if box_attr else {}
        door_vals = {v.name: v for v in AttrVal.search(
            [("attribute_id", "=", door_attr.id)])} if door_attr else {}

        # Ensure per-value "Series allows V" domains exist.
        def ensure_domain(value_name, allowed_series_names):
            dom_name = _domain_name_for(value_name)
            dom = Domain.search([("name", "=", dom_name)], limit=1)
            allowed_series_ids = [
                series_value_by_name[n].id for n in allowed_series_names
                if n in series_value_by_name
            ]
            if not dom:
                dom = Domain.create({"name": dom_name})
                DomainLine.create({
                    "domain_id": dom.id,
                    "attribute_id": series_attr.id,
                    "condition": "in",
                    "operator": "and",
                    "value_ids": [(6, 0, allowed_series_ids)],
                })
            else:
                # Sync the domain.line's value_ids to match the spec.
                line = dom.domain_line_ids[:1]
                if line and set(line.value_ids.ids) != set(allowed_series_ids):
                    line.write({"value_ids": [(6, 0, allowed_series_ids)]})
            return dom

        domains_by_value_name = {}
        for v_name, allowed in _BOX_MATERIAL_ALLOW.items():
            domains_by_value_name[v_name] = ensure_domain(v_name, allowed)
        for v_name, allowed in _DOOR_STYLE_ALLOW.items():
            domains_by_value_name[v_name] = ensure_domain(v_name, allowed)

        # Scope every product.template that exposes Box Material OR
        # Door Style to its customers — that covers the Q8 locked
        # templates AND the catalog_expansion's 40 common-category
        # templates AND any future template wired through the OCA
        # configurator. Each template gets exactly the rules it needs:
        # templates without Door Style (open shelves, drawer banks,
        # accessories) get only Box Material rules; templates without
        # Box Material (none in current scope, but defensive) get only
        # Door Style rules.
        box_lines = AttrLine.search(
            [("attribute_id", "=", box_attr.id)]) if box_attr else AttrLine
        door_lines = AttrLine.search(
            [("attribute_id", "=", door_attr.id)]) if door_attr else AttrLine
        scoped_tmpl_ids = sorted({
            l.product_tmpl_id.id
            for l in (box_lines | door_lines)
        })

        deleted, created = 0, 0
        for tmpl_id in scoped_tmpl_ids:
            tmpl_lines = AttrLine.search(
                [("product_tmpl_id", "=", tmpl_id)])
            box_line = tmpl_lines.filtered(
                lambda l, a=box_attr: a and l.attribute_id.id == a.id)
            door_line = tmpl_lines.filtered(
                lambda l, a=door_attr: a and l.attribute_id.id == a.id)

            # NUKE existing config.lines on these attribute_lines. The
            # broken Contractor/Signature seeds (and any leftovers from
            # the previous rule_completion attempt) get cleared.
            for line in (box_line | door_line):
                stale = ConfigLine.search([
                    ("product_tmpl_id", "=", tmpl_id),
                    ("attribute_line_id", "=", line.id),
                ])
                deleted += len(stale)
                stale.unlink()

            # CREATE one config.line per (value) pointing to the right
            # per-value domain. OCA constraint: config.line value_ids
            # must be a subset of the attribute_line's value_ids — so
            # only emit a rule for a value that the template ACTUALLY
            # exposes (e.g. SB-WALL-GLASS restricts Door Style to just
            # "Custom (Signature)", so it gets ONE door rule, not three).
            if box_line:
                box_line_value_ids = set(box_line.value_ids.ids)
                for v_name, attr_val in box_vals.items():
                    if v_name not in _BOX_MATERIAL_ALLOW:
                        continue
                    if attr_val.id not in box_line_value_ids:
                        continue
                    ConfigLine.create({
                        "product_tmpl_id": tmpl_id,
                        "attribute_line_id": box_line.id,
                        "domain_id": domains_by_value_name[v_name].id,
                        "value_ids": [(6, 0, [attr_val.id])],
                        "sequence": 20000,
                    })
                    created += 1
            if door_line:
                door_line_value_ids = set(door_line.value_ids.ids)
                for v_name, attr_val in door_vals.items():
                    if v_name not in _DOOR_STYLE_ALLOW:
                        continue
                    if attr_val.id not in door_line_value_ids:
                        continue
                    ConfigLine.create({
                        "product_tmpl_id": tmpl_id,
                        "attribute_line_id": door_line.id,
                        "domain_id": domains_by_value_name[v_name].id,
                        "value_ids": [(6, 0, [attr_val.id])],
                        "sequence": 20010,
                    })
                    created += 1

        self.env["ir.logging"].sudo().create({
            "name": "southbrook.configurator_ux.rule_completion",
            "type": "server",
            "level": "INFO",
            "dbname": self.env.cr.dbname,
            "message": (f"rule rewrite: {deleted} stale lines deleted, "
                        f"{created} fresh lines created"),
            "path": __file__,
            "func": "complete_rules",
            "line": "0",
        })
        return {"deleted": deleted, "created": created}
