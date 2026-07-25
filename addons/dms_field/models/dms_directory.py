# Copyright 2020 Creu Blanca
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import SQL, Query


class DmsDirectory(models.Model):
    _inherit = "dms.directory"

    parent_id = fields.Many2one(default=lambda self: self._default_parent())

    @api.model
    def _default_parent(self):
        return self.env.context.get("default_parent_directory_id", False)

    @api.constrains("res_id", "is_root_directory", "storage_id", "res_model")
    def _check_resource(self):
        for directory in self:
            if directory.storage_id.save_type == "attachment":
                continue
            if (
                directory.is_root_directory
                and directory.storage_id.model_ids
                and not directory.res_id
            ):
                raise ValidationError(
                    _("Directories of this storage must be related to a record")
                )
            if not directory.res_id:
                continue
            if self.search(
                [
                    ("storage_id", "=", directory.storage_id.id),
                    ("id", "!=", directory.id),
                    ("res_id", "=", directory.res_id),
                    ("res_model", "=", directory.res_model),
                ],
                limit=1,
            ):
                raise ValidationError(
                    _("This record is already related in this storage")
                )

    @api.model
    def _build_documents_view_directory(self, directory):
        return {
            "id": f"directory_{directory.id}",
            "text": directory.name,
            "icon": "fa fa-folder-o",
            "type": "directory",
            "data": {"odoo_id": directory.id, "odoo_model": "dms.directory"},
            "children": directory.count_elements > 0,
        }

    @api.model
    def _check_parent_field(self):
        if self._parent_name not in self._fields:
            raise TypeError(f"The parent ({self._parent_name}) field does not exist.")

    @api.model
    def search_read_parents(
        self, domain=False, fields=None, offset=0, limit=None, order=None
    ):
        """This method finds the top level elements of the hierarchy
        for a given search query.

        :param domain: a search domain <reference/orm/domains> (default: empty list)
        :param fields: a list of fields to read (default: all fields of the model)
        :param offset: the number of results to ignore (default: none)
        :param limit: maximum number of records to return (default: all)
        :param order: a string to define the sort order of the query
             (default: none)
        :returns: the top level elements for the given search query
        """
        if not domain:
            domain = []
        records = self.search_parents(
            domain=domain, offset=offset, limit=limit, order=order
        )
        if not records:
            return []
        if fields and fields == ["id"]:
            return [{"id": record.id} for record in records]
        result = records.read(fields)
        if len(result) <= 1:
            return result
        index = {vals["id"]: vals for vals in result}
        return [index[record.id] for record in records if record.id in index]

    @api.model
    def search_parents(
        self, domain=False, offset=0, limit=None, order=None, count=False
    ):
        """This method finds the top level elements of the
        hierarchy for a given search query.

        :param domain: a search domain <reference/orm/domains> (default: empty list)
        :param offset: the number of results to ignore (default: none)
        :param limit: maximum number of records to return (default: all)
        :param order: a string to define the sort order of the query
             (default: none)
        :param count: counts and returns the number of matching records
             (default: False)
        :returns: the top level elements for the given search query
        """
        if not domain:
            domain = []
        res = self._search_parents(
            domain=domain, offset=offset, limit=limit, order=order, count=count
        )
        return res if count else self.browse(res)

    @api.model
    def _search_parents(
        self, domain=False, offset=0, limit=None, order=None, count=False
    ):
        """Find the top level elements of the hierarchy for a given search
        query: records matching ``domain`` (and readable by the current
        user) whose parent is either unset, or itself not part of that
        readable/matching set.

        .. note::
           Odoo 19 removed the private ``_where_calc()`` /
           ``_apply_ir_rules()`` combo this method used to hand-roll raw SQL
           against (they no longer exist on ``models.BaseModel``: record
           rules are now folded straight into ``_search()``'s returned
           :class:`~odoo.tools.Query`, and ``Query.from_clause`` /
           ``Query.where_clause`` return composable
           :class:`~odoo.tools.SQL` objects instead of ``(code, params)``
           tuples). This rebuilds the same two-query shape (an inner
           "readable & matching" subquery used both to test the parent link
           and, combined with the parent test, as the outer query) on top of
           the current, supported APIs.
        """
        if not domain:
            domain = []
        self._check_parent_field()
        self.check_access("read")

        # `_search()` returns an (unexecuted) Query with `domain` already
        # combined with the active ir.rule record rules and active_test
        # filtering - the direct v19 replacement for the old
        # `_where_calc(domain)` + `_apply_ir_rules(query, "read")` pair.
        query = self._search(domain)
        from_clause = query.from_clause
        where_clause = query.where_clause

        table_id = SQL.identifier(self._table, "id")
        parent_query = SQL(
            "SELECT %s FROM %s%s",
            table_id,
            from_clause,
            SQL(" WHERE %s", where_clause) if where_clause else SQL(),
        )
        parent_column = SQL.identifier(self._table, self._parent_name)
        parent_clause = SQL(
            "(%s IS NULL OR %s NOT IN (%s))",
            parent_column,
            parent_column,
            parent_query,
        )
        final_where = (
            SQL("%s AND %s", where_clause, parent_clause)
            if where_clause
            else parent_clause
        )

        if count:
            count_sql = SQL(
                "SELECT count(1) FROM %s WHERE %s", from_clause, final_where
            )
            self.env.cr.execute(count_sql.code, count_sql.params)
            return self.env.cr.fetchone()[0]

        # Compute ORDER BY against a fresh, domain-less query for the table,
        # matching the historical behaviour of not leaking any join added
        # for the ordering into the FROM clause captured above.
        order_query = Query(self.env, self._table, self._table_sql)
        order_by = self._order_to_sql(order, order_query)
        select_sql = SQL(
            "SELECT %s FROM %s WHERE %s%s%s%s",
            table_id,
            from_clause,
            final_where,
            SQL(" ORDER BY %s", order_by) if order_by else SQL(),
            SQL(" LIMIT %s", limit) if limit else SQL(),
            SQL(" OFFSET %s", offset) if offset else SQL(),
        )
        self.env.cr.execute(select_sql.code, select_sql.params)
        return list({x[0] for x in self.env.cr.fetchall()})
