# SPDX-License-Identifier: LGPL-3.0-only
"""Phase 1 provider: southbrook_mrp_kitchen_tools data.

This is the ONLY file that knows about x_southbrook_* fields or
southbrook.tool.category. Phase 2's hardware provider is a sibling file.
"""
from odoo import api, models

PROVENANCE = (
    "Read-only view of the tool and consumable master. Specs are optional — "
    "an absent value is shown as a dash, never as zero."
)

GENERIC_COLUMNS = [
    {"key": "name", "label": "Description", "align": "left", "sortable": True},
    {"key": "default_code", "label": "Reference", "align": "left",
     "sortable": True},
]


class ToolsCatalogProvider(models.AbstractModel):
    _name = "tools.catalog.provider"
    _inherit = "materials.catalog.provider"
    _description = "Tools and consumables catalog provider"

    @api.model
    def _build_payload(self, scope, category_id, facets, search, offset, limit):
        category = self.env["southbrook.tool.category"].browse(
            category_id) if category_id else None
        if category is not None and not category.exists():
            return self._degrade("Unknown category: %s" % category_id, scope)
        columns = self._columns(category)
        rows, total = self._rows(category, facets, search, offset, limit,
                                  columns)
        return {
            "ok": True,
            "reason": None,
            "scope": scope,
            "categories": self._categories(),
            "facets": self._facets(category),
            "columns": columns,
            "rows": rows,
            "detail": {},
            "total": total,
            "provenance": PROVENANCE,
        }

    @api.model
    def _categories(self):
        """Rail tree with descendant-inclusive product counts.

        Counts are computed with TWO efficient queries:
        - one _read_group over product.product grouped by product_tmpl_id
        - one batched read of templates to map category, joined in Python
        This counts variants (not templates) so the rail matches table rows,
        and stays O(1) queries instead of O(categories).
        """
        Category = self.env["southbrook.tool.category"]
        cats = Category.search([])
        if not cats:
            return []

        # Odoo 17+ grouping API: _read_group returns a list of tuples,
        # (group_value, *aggregates). The old public read_group is gone.
        # Count product.product (variants) grouped by template.
        variant_grouped = self.env["product.product"]._read_group(
            [("product_tmpl_id.x_southbrook_tool_category_id", "in", cats.ids)],
            groupby=["product_tmpl_id"],
            aggregates=["__count"],
        )
        # variant_grouped is list of (product.template, count) tuples.
        # Map each template to its variant count.
        tmpl_to_variant_count = {tmpl.id: count for tmpl, count in variant_grouped if tmpl}

        # Batch-read all templates once and map variant counts to categories.
        tmpl_ids = list(tmpl_to_variant_count.keys())
        templates = self.env["product.template"].browse(tmpl_ids) if tmpl_ids else []
        direct = {}
        for tmpl in templates:
            cat_id = tmpl.x_southbrook_tool_category_id.id if tmpl.x_southbrook_tool_category_id else None
            if cat_id:
                direct[cat_id] = direct.get(cat_id, 0) + tmpl_to_variant_count[tmpl.id]

        # Roll direct counts up through parent_path, so an ancestor reports
        # everything beneath it.
        rollup = dict.fromkeys(cats.ids, 0)
        for cat in cats:
            n = direct.get(cat.id, 0)
            if not n:
                continue
            for raw in (cat.parent_path or "").strip("/").split("/"):
                if raw and int(raw) in rollup:
                    rollup[int(raw)] += n

        child_ids = {c.parent_id.id for c in cats if c.parent_id}
        return [{
            "id": c.id,
            "name": c.name,
            "parent_id": c.parent_id.id or False,
            "count": rollup.get(c.id, 0),
            "has_children": c.id in child_ids,
        } for c in cats.sorted(lambda r: (r.complete_name or ""))]

    @api.model
    def _ancestor_ids(self, category):
        """Category's own id plus every ancestor id, nearest LAST.

        parent_path is '/1/7/33/' — root first, self last.
        """
        if not category:
            return []
        return [int(x) for x in (category.parent_path or "").strip("/").split("/") if x]

    @api.model
    def _columns(self, category):
        """Columns for the category, generics first, then declared ones.

        Declarations from the selected category and all its ancestors apply.
        When the same field_name is declared at two levels, the nearest
        declaration wins — a child's label overrides its ancestor's.
        """
        cols = list(GENERIC_COLUMNS)
        if not category:
            return cols
        ids = self._ancestor_ids(category)
        if not ids:
            return cols
        declared = self.env["materials.catalog.column"].search(
            [("category_id", "in", ids)])
        # Nearest declaration wins: order by depth of its category in `ids`.
        depth = {cat_id: i for i, cat_id in enumerate(ids)}
        by_field = {}
        for dec in declared.sorted(
                lambda d: (depth.get(d.category_id.id, -1), d.sequence, d.id)):
            by_field[dec.field_name] = {
                "key": dec.field_name,
                "label": dec.name,
                "align": dec.align,
                "sortable": dec.sortable,
            }
        return cols + list(by_field.values())

    @api.model
    def _facets(self, category):
        """Facet chips for the category, declared via materials.catalog.facet.

        Declarations from the selected category and all its ancestors apply,
        same rule as _columns — INCLUDING the nearest-wins dedupe: the same
        field_name can legitimately be declared as a facet on both an
        ancestor and the selected category (the uniqueness constraint is
        scoped per category_id), and the frontend keys chips on "key", so
        only the nearest declaration may reach the payload.

        Each facet's values are built with ONE grouped query (or one
        aggregate query for range), never a query per value.
        """
        if not category:
            return []
        ids = self._ancestor_ids(category)
        declared = self.env["materials.catalog.facet"].search(
            [("category_id", "in", ids)])
        if not declared:
            return []

        # Nearest declaration wins: order by depth of its category in `ids`,
        # then collapse into a dict keyed on field_name (mirrors _columns).
        depth = {cat_id: i for i, cat_id in enumerate(ids)}
        by_field = {}
        for dec in declared.sorted(
                lambda d: (depth.get(d.category_id.id, -1), d.sequence, d.id)):
            by_field[dec.field_name] = dec

        Tmpl = self.env["product.template"]
        tmpl_domain = [("x_southbrook_tool_category_id", "child_of", category.id)]
        out = []
        for dec in by_field.values():
            field = Tmpl._fields.get(dec.field_name)
            if not field:
                continue
            entry = {"key": dec.field_name, "label": dec.name,
                     "type": dec.facet_type, "values": []}
            if dec.facet_type == "range":
                # Aggregate in Postgres — a bare aggregate query (no GROUP
                # BY, since groupby=[]) always returns exactly one row, even
                # when zero records match. Confirmed against this build's
                # _read_group: NULL aggregates postprocess to False, which we
                # normalise to None — the "no data" sentinel must not be
                # confused with a legitimate all-zero dataset.
                grouped = Tmpl._read_group(
                    tmpl_domain + [(dec.field_name, "!=", False)],
                    groupby=[],
                    aggregates=["%s:min" % dec.field_name,
                                "%s:max" % dec.field_name],
                )
                raw_min, raw_max = grouped[0] if grouped else (False, False)
                entry["min"] = raw_min if raw_min is not False else None
                entry["max"] = raw_max if raw_max is not False else None
            elif dec.facet_type == "flag":
                entry["values"] = [{"value": True, "label": dec.name,
                                    "count": Tmpl.search_count(
                                        tmpl_domain + [(dec.field_name, "=", True)])}]
            else:
                # Odoo 17+ API: list of (group_value, count) tuples.
                grouped = Tmpl._read_group(
                    tmpl_domain + [(dec.field_name, "!=", False)],
                    groupby=[dec.field_name],
                    aggregates=["__count"],
                )
                raw = []
                for val, count in grouped:
                    if val is False or val is None:
                        continue
                    if hasattr(val, "id"):                 # m2o / m2m recordset
                        raw.append({"value": val.id, "label": val.display_name,
                                    "count": count})
                    else:
                        label = val
                        if field.type == "selection":
                            label = dict(
                                field._description_selection(self.env)
                            ).get(val, val)
                        raw.append({"value": val, "label": label,
                                    "count": count})
                # Relation-valued facets ("value" is a database id) must
                # sort alphabetically by label, never numerically — an id
                # is always numeric-parseable, so the numeric-aware ordering
                # would otherwise sort chips by arbitrary internal id order.
                entry["values"] = self._order_values(
                    raw, alpha=(dec.facet_type == "m2m"))
            out.append(entry)
        return out

    @api.model
    def _order_values(self, raw, alpha=False):
        """Order facet values for display.

        Numeric-aware by default: unparseable values keep their label and
        sort last (see _numeric_prefix). Pass alpha=True for relation-valued
        facets (m2m) — their "value" is a database id, which would otherwise
        parse as a number and sort by arbitrary internal id order instead of
        by label.
        """
        if alpha:
            return sorted(raw, key=lambda item: str(item["label"]))
        numbered, unnumbered = [], []
        for item in raw:
            n = self._numeric_prefix(item["value"])
            (numbered if n is not None else unnumbered).append((n, item))
        numbered.sort(key=lambda pair: pair[0])
        unnumbered.sort(key=lambda pair: str(pair[1]["label"]))
        return [item for _n, item in numbered] + [item for _n, item in unnumbered]

    @api.model
    def _facet_domain(self, facets):
        """Domain fragment for the selected facet values.

        Within one facet, selected values are OR'ed. Across facets, the
        fragments are AND'ed (Odoo domains are implicitly AND).
        """
        domain = []
        for field_name, selection in (facets or {}).items():
            if field_name not in self.env["product.template"]._fields:
                continue
            if isinstance(selection, dict):          # range
                low, high = selection.get("min"), selection.get("max")
                if low is not None:
                    domain.append((field_name, ">=", low))
                if high is not None:
                    domain.append((field_name, "<=", high))
                continue
            values = [v for v in (selection or []) if v not in (None, "")]
            if not values:
                continue
            if len(values) == 1:
                domain.append((field_name, "=", values[0]))
            else:
                domain += ["|"] * (len(values) - 1)
                domain += [(field_name, "=", v) for v in values]
        return domain

    @api.model
    def _rows(self, category, facets, search, offset, limit, columns):
        """One row per variant.

        Spec fields live on product.template, so templates are read ONCE in
        a batch and joined in Python — never one read per row.
        """
        Product = self.env["product.product"]
        domain = [("product_tmpl_id.x_southbrook_tool_category_id",
                   "child_of", category.id)] if category else []
        for leaf in self._facet_domain(facets):
            domain.append(("product_tmpl_id.%s" % leaf[0], leaf[1], leaf[2])
                          if isinstance(leaf, tuple) else leaf)
        if search:
            domain += ["|", ("name", "ilike", search),
                       ("default_code", "ilike", search)]

        total = Product.search_count(domain)
        products = Product.search(domain, offset=offset, limit=limit,
                                  order="default_code, name")
        if not products:
            return [], total

        spec_keys = [c["key"] for c in columns
                     if c["key"] not in ("name", "default_code")]
        tmpl_data = {}
        if spec_keys:
            for rec in products.mapped("product_tmpl_id").read(spec_keys):
                tmpl_data[rec["id"]] = rec

        rows = []
        for product in products:
            row = {
                "product_id": product.id,
                "name": product.name,
                "default_code": product.default_code or False,
            }
            specs = tmpl_data.get(product.product_tmpl_id.id, {})
            for key in spec_keys:
                value = specs.get(key)
                # False from an unset Char/Float is "absent", not zero.
                row[key] = None if value in (False, None, "") else value
            rows.append(row)
        return rows, total
