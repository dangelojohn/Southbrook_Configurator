# SPDX-License-Identifier: LGPL-3.0-only
"""Phase 1 provider: southbrook_mrp_kitchen_tools data.

This is the ONLY file that knows about x_southbrook_* fields or
southbrook.tool.category. Phase 2's hardware provider is a sibling file.
"""
from odoo import api, models
from odoo.fields import Domain
from odoo.tools import SQL

PROVENANCE = (
    "Read-only view of the tool and consumable master. Specs are optional — "
    "an absent value is shown as a dash, never as zero."
)

GENERIC_COLUMNS = [
    {"key": "name", "label": "Description", "align": "left", "sortable": True},
    {"key": "default_code", "label": "Reference", "align": "left",
     "sortable": True},
]

# Numeric and boolean values are never absence — 0 and False are real data
# for these types and must survive verbatim. Everything else's falsy value
# ("never set") normalizes to None. Shared by _rows (table) and _build_detail
# (spec grid + engineering rail) so there is exactly one absence rule.
VALUE_IS_NEVER_ABSENT = {"float", "integer", "monetary", "boolean"}


def _normalize_value(value, field):
    """Apply the catalog's absence convention to one raw field value.

    Shared by _rows() (table cells) and _detail_value() (spec grid +
    engineering rail) so there is exactly one place that decides both
    what "absent" means AND how a relational value is shaped — the row
    and the detail panel can never disagree (finding F4).

    `value` may be a batched read()'s raw shape: a many2one comes back as
    Odoo's (id, display_name) tuple, which is unwrapped to the display
    name here, before the same field ever reaches its type-aware absence
    check below.

    `field` is the product.template field object (or None if the key isn't
    a real field on the model) — its `.type` decides whether a falsy raw
    value means "never set" (-> None) or is genuine data to keep as-is.
    """
    if isinstance(value, tuple):
        value = value[1] if len(value) > 1 else (value[0] if value else False)
    ftype = field.type if field else None
    if ftype in VALUE_IS_NEVER_ABSENT:
        return value
    return None if not value else value


BADGE_FIELDS = [
    ("x_southbrook_hazardous", "Hazardous"),
    ("x_southbrook_flammable", "Flammable"),
    ("x_southbrook_msds_required", "MSDS required"),
    ("x_southbrook_requires_ventilation", "Ventilation required"),
    ("x_southbrook_expiry_required", "Expiry tracked"),
]

ENGINEERING_FIELDS = [
    ("x_southbrook_preferred_vendor_id", "Preferred vendor"),
    ("x_southbrook_vendor_sku", "Vendor SKU"),
    ("x_southbrook_issue_uom_id", "Issue UoM"),
    ("x_southbrook_min_stock_qty", "Min stock"),
    ("x_southbrook_max_stock_qty", "Max stock"),
    ("x_southbrook_reorder_multiple", "Reorder multiple"),
    ("x_southbrook_estimated_life_qty", "Estimated life"),
    ("x_southbrook_estimated_life_unit", "Life unit"),
    ("x_southbrook_tool_lifecycle_state", "Lifecycle"),
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

        Counts are variant-scoped (product.product), to match the category
        rail and the table's `total` (finding F3) — EXCEPT range facets,
        which carry no per-value count at all, only a min/max. A numeric
        spec lives on product.template and is identical across every
        variant of that template, so a variant-scoped aggregate would
        report the same numbers as a template-scoped one; it is also not
        mechanically available in one query, because _read_group's
        aggregate spec (unlike its groupby spec) must name a field
        declared directly on the queried model — "product_tmpl_id.<field>"
        is rejected for aggregates even though the identical path is
        accepted for groupby. Range facets are left grouped against
        product.template deliberately; nothing here is silently
        inconsistent, there is simply no "count" for this shape to disagree
        about.
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
        Product = self.env["product.product"]
        tmpl_domain = [("x_southbrook_tool_category_id", "child_of", category.id)]
        variant_domain = [("product_tmpl_id.x_southbrook_tool_category_id",
                           "child_of", category.id)]
        out = []
        for dec in by_field.values():
            field = Tmpl._fields.get(dec.field_name)
            if not field:
                continue
            entry = {"key": dec.field_name, "label": dec.name,
                     "type": dec.facet_type, "values": []}
            variant_field = "product_tmpl_id.%s" % dec.field_name
            if dec.facet_type == "range":
                # Aggregate in Postgres — a bare aggregate query (no GROUP
                # BY, since groupby=[]) always returns exactly one row, even
                # when zero records match. Confirmed against this build's
                # _read_group: NULL aggregates postprocess to False, which we
                # normalise to None — the "no data" sentinel must not be
                # confused with a legitimate all-zero dataset.
                #
                # No `!= False` leaf here (finding F1): MIN/MAX skip NULL
                # natively in SQL, so the leaf was never needed for
                # correctness — and on a Float/Integer/Monetary field it
                # actively hurt: falsy_value=0 means the ORM rewrites
                # `!= False` into `NOT IN (0.0)`, which drops a row whose
                # value is a genuine 0 out of the aggregate too, quietly
                # raising the reported minimum.
                grouped = Tmpl._read_group(
                    tmpl_domain,
                    groupby=[],
                    aggregates=["%s:min" % dec.field_name,
                                "%s:max" % dec.field_name],
                )
                raw_min, raw_max = grouped[0] if grouped else (False, False)
                entry["min"] = raw_min if raw_min is not False else None
                entry["max"] = raw_max if raw_max is not False else None
            elif dec.facet_type == "flag":
                entry["values"] = [{"value": True, "label": dec.name,
                                    "count": Product.search_count(
                                        variant_domain +
                                        [(variant_field, "=", True)])}]
            else:
                # Odoo 17+ API: list of (group_value, count) tuples.
                # Grouped over product.product via the product_tmpl_id.*
                # path — one query, variant-scoped counts (finding F3).
                grouped = Product._read_group(
                    variant_domain + [(variant_field, "!=", False)],
                    groupby=[variant_field],
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
                if low is None and high is None:
                    continue
                # F2: on a nullable Float/Integer/Monetary column, Odoo's
                # domain-to-SQL layer ORs in "field IS NULL" for a `<=`/`>=`
                # leaf whenever the field's falsy value (0) itself satisfies
                # the comparison — e.g. `<= 50` matches unset rows too,
                # because 0 <= 50. A leaf whose bound doesn't reject that
                # (max-only, or a min <= 0) leaves the null-acceptance in
                # place for the whole AND'ed domain, so rows with NO value
                # recorded come back alongside genuine matches.
                null_would_match = ((low is None or low <= 0)
                                     and (high is None or high >= 0))
                if not null_would_match:
                    # A plain leaf already excludes NULL outright here (a
                    # positive ">=" fails a NULL column rather than OR-ing
                    # in IS NULL), so the simple leaves are already correct.
                    if low is not None:
                        domain.append((field_name, ">=", low))
                    if high is not None:
                        domain.append((field_name, "<=", high))
                    continue
                # Refuted compromise: the previous fix here used
                # `(field_name, "!=", False)` to force NULL exclusion, but
                # that compiles to `NOT IN (0.0)` (falsy_value=0 on these
                # field types), which also drops a row whose value really
                # is 0 — the same trap as the facet min/max aggregate (see
                # _facets(), finding F1). No plain domain leaf can express
                # "IS NOT NULL, but a genuine 0 still counts", because every
                # leaf gets rewritten by the same per-field falsy-value
                # machinery. Domain.custom(to_sql=...) bypasses that
                # rewriting entirely and emits the SQL directly — nested
                # under a relational "any" so it plugs into an ordinary
                # domain list without special-casing elsewhere (mirrors
                # Odoo core's own use of this pattern for a predicate plain
                # operators can't express: purchase.order._search_is_late,
                # addons/purchase/models/purchase_order.py:372-388).
                # `product_tmpl_id` is the many2one _rows already filters
                # product.product through (it prefixes every plain tuple
                # leaf with "product_tmpl_id.%s" for the same reason: the
                # spec field lives on product.template, not product.product,
                # and _rows's domain is built for the latter). A Domain
                # object is not a tuple, so it skips that prefixing and is
                # appended to _rows's domain as-is (see _rows) — it must
                # therefore name the relation itself. This only resolves
                # correctly against a model that has a product_tmpl_id
                # field (product.product); a direct product.template query
                # would need this same leaf unwrapped one level.
                def _to_sql(model, alias, query, fn=field_name, lo=low, hi=high):
                    sql_field = model._field_to_sql(alias, fn, query)
                    parts = [SQL("%s IS NOT NULL", sql_field)]
                    if lo is not None:
                        parts.append(SQL("%s >= %s", sql_field, lo))
                    if hi is not None:
                        parts.append(SQL("%s <= %s", sql_field, hi))
                    return SQL(" AND ").join(parts)
                domain.append(
                    Domain("product_tmpl_id", "any", Domain.custom(to_sql=_to_sql)))
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

        Absence is type-aware, driven by the field's actual type
        (product.template._fields[key].type):
        - Char/Text/Selection/Html and relational (m2o/m2m/o2m) fields:
          Odoo's False/empty for "never set" is reported as None.
        - Boolean: False is a real value, not absence — kept as-is.
        - Date/Datetime: False means absent — reported as None.
        - Float/Integer/Monetary: kept as-is, never folded to None. LIMIT:
          the ORM returns 0 (or 0.0) for both "never entered" and "entered
          as zero" on a numeric field — those two states are genuinely
          indistinguishable at the ORM level. This catalog shows the zero
          rather than pretending it can tell the difference.

        No category (finding F6): an unscoped call must not fan out across
        every product on the instance. `_columns(None)` and `_facets(None)`
        already degrade safely to "nothing declared yet"; `_rows` mirrors
        that with an empty result rather than a scoped default — there is
        no principled "default" category to fall back to, and picking one
        would silently show a different, arbitrary subset instead of the
        rail's neutral "choose a category" state the frontend already
        renders when `categoryId` is null.
        """
        if not category:
            return [], 0
        Product = self.env["product.product"]
        Tmpl = self.env["product.template"]
        domain = [("product_tmpl_id.x_southbrook_tool_category_id",
                   "child_of", category.id)]
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
                row[key] = _normalize_value(specs.get(key), Tmpl._fields.get(key))
            rows.append(row)
        return rows, total

    @api.model
    def _build_detail(self, product_id):
        """Detail payload for one variant: spec grid, engineering rail,
        safety badges.

        The spec grid reuses the selected category's declared columns
        (same `_columns()` as the table), so the detail panel and the row
        it was opened from never disagree about which specs exist.

        Values share the absence rule with _rows() via _normalize_value —
        one read() batches both the spec keys and the engineering fields
        so a many2one comes back as Odoo's (id, display_name) tuple, from
        which we take the display name: the detail panel must never show
        a raw database id.

        Access (finding F5): get_catalog's scope check is incidental — it
        only happens because _build_payload always calls _categories(),
        which searches southbrook.tool.category (readable only by
        group_tool_operator and friends). _build_detail has no equivalent
        forced touch: _columns(category) short-circuits to the generic
        columns whenever `category` is falsy, so a product with NO
        x_southbrook_tool_category_id set never reaches that model at all,
        and a base.group_user-only account could otherwise call get_detail
        directly and read title/specs/badges/engineering with no gate.
        Enforce the same scope check unconditionally, before any data is
        assembled, rather than relying on it happening to fire.
        """
        self.env["southbrook.tool.category"].browse().check_access("read")
        product = self.env["product.product"].browse(product_id)
        if not product.exists():
            return self._degrade_detail("Unknown product")
        tmpl = product.product_tmpl_id
        category = tmpl.x_southbrook_tool_category_id
        columns = self._columns(category)

        spec_keys = [c["key"] for c in columns
                     if c["key"] not in ("name", "default_code")]
        engineering_keys = [f for f, _label in ENGINEERING_FIELDS
                            if f in tmpl._fields]
        read_keys = list(dict.fromkeys(
            k for k in spec_keys + engineering_keys if k in tmpl._fields))
        data = tmpl.read(read_keys)[0] if read_keys else {}

        specs = [{"label": col["label"],
                  "value": self._detail_value(tmpl, data, col["key"])}
                 for col in columns if col["key"] not in ("name", "default_code")]

        engineering = [{"label": label,
                        "value": self._detail_value(tmpl, data, field_name)}
                       for field_name, label in ENGINEERING_FIELDS
                       if field_name in tmpl._fields]

        badges = [label for field_name, label in BADGE_FIELDS
                  if field_name in tmpl._fields and tmpl[field_name]]

        return {
            "ok": True,
            "reason": None,
            "title": product.display_name,
            "subtitle": category.complete_name if category else "",
            "specs": specs,
            "engineering": engineering,
            "badges": badges,
        }

    @api.model
    def _detail_value(self, tmpl, data, key):
        """One field's value, read()-shaped, normalized, relation-resolved.

        `data` came from a batched tmpl.read(); a many2one there is Odoo's
        (id, display_name) tuple. Tuple-unwrapping and the absence rule
        both live in _normalize_value (finding F4) — the same helper
        _rows() uses for its cells — so a relation column can never render
        differently in the table than in this detail panel.
        """
        field = tmpl._fields.get(key)
        raw = data.get(key) if field else False
        return _normalize_value(raw, field)
