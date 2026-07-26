# SPDX-License-Identifier: LGPL-3.0-only
"""Catalog contract: one shell, many providers.

The frontend calls get_catalog() and renders whatever comes back. It knows
nothing about hardware, tooling or sheet goods. A provider maps one data
domain onto the payload contract.

CONTRACT — the frontend reads exactly these keys:
    ok, reason, scope, categories, facets, columns, rows, detail, total,
    provenance
Rows are keyed on `product_id`. Renaming that key makes rows silently
unselectable in the UI.

Any failure degrades to {"ok": False, "reason": ...}. The catalog never
returns a 500 to the client action.
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

SCOPES = {
    "tools": "tools.catalog.provider",
}


class MaterialsCatalogProvider(models.AbstractModel):
    _name = "materials.catalog.provider"
    _description = "Materials catalog provider contract"

    @api.model
    def get_catalog(self, scope="tools", category_id=None, facets=None,
                    search="", offset=0, limit=80):
        """Return one catalog payload. Never raises.

        `limit` follows plain Odoo search() semantics: 0 means "no limit",
        not "zero rows" — a page size of 0 returns every matching row. This
        is Odoo's own convention, kept deliberately rather than special-cased,
        so it matches every other search() call in the codebase; a caller
        that wants an empty page must ask for it some other way (e.g. by not
        calling get_catalog at all).

        The risky part of building a payload (`provider._build_payload`)
        runs inside a savepoint, not the caller's own transaction. A
        Postgres-level error (e.g. a negative offset) leaves the cursor
        "aborted" until something rolls back — bare `cr.rollback()` would
        discard the caller's own uncommitted work too, since get_catalog
        runs inside whatever transaction the caller already opened. A
        savepoint scopes the rollback to exactly the failed payload build,
        so the very next call on the same cursor still works.
        """
        provider_name = SCOPES.get(scope)
        try:
            if not provider_name or provider_name not in self.env:
                return self._degrade("Unknown catalog scope: %s" % scope, scope)
            provider = self.env[provider_name]
            with self.env.cr.savepoint():
                return provider._build_payload(
                    scope=scope, category_id=category_id, facets=facets or {},
                    search=search or "", offset=offset, limit=limit)
        except Exception as exc:  # noqa: BLE001 — degrade, never 500
            _logger.exception("Catalog payload build failed")
            # The savepoint above has already unwound the failed build, so
            # the cursor is healthy again here — safe to ask the provider
            # for a best-effort category rail. A selection-scoped failure
            # (a bad facet, a bad column) should degrade in place and leave
            # the rail the user was navigating intact; only a failure in the
            # rail itself (or the provider lookup) should degrade to the
            # empty rail this hook returns by default.
            categories = []
            if provider_name and provider_name in self.env:
                categories = self.env[provider_name]._categories_best_effort()
            return self._degrade(str(exc)[:200], scope, categories=categories)

    @api.model
    def _degrade(self, reason, scope, categories=None):
        return {
            "ok": False, "reason": reason, "scope": scope,
            "categories": categories or [], "facets": [], "columns": [],
            "rows": [], "detail": {}, "total": 0,
            "provenance": "Catalog unavailable.",
        }

    @api.model
    def _categories_best_effort(self):
        """Best-effort category rail to accompany a degraded payload.

        Called only after get_catalog's savepoint has already rolled back
        the failed build, so this runs on a healthy cursor. Returns []
        by default; a provider with an actual rail concept overrides this
        to recompute it, so a degraded *selection* still shows the rail the
        user was navigating. If recomputing the rail itself fails, that is
        the "the category tree is what's broken" case, and [] is correct.
        """
        return []

    @api.model
    def get_detail(self, product_id, scope="tools"):
        """Return one detail payload. Never raises.

        Degrades the same way get_catalog() does: {"ok": False, "reason":
        ...} with every contract key still present, so the frontend never
        has to special-case a missing key. Same savepoint reasoning as
        get_catalog: a Postgres-level error inside `_build_detail` must not
        leave the caller's transaction aborted for whatever call comes next.
        """
        try:
            provider_name = SCOPES.get(scope)
            if not provider_name or provider_name not in self.env:
                return self._degrade_detail("Unknown scope")
            with self.env.cr.savepoint():
                return self.env[provider_name]._build_detail(product_id)
        except Exception as exc:  # noqa: BLE001 — degrade, never 500
            _logger.exception("Catalog detail build failed")
            return self._degrade_detail(str(exc)[:200])

    @api.model
    def _degrade_detail(self, reason):
        return {
            "ok": False, "reason": reason, "title": "", "subtitle": "",
            "specs": [], "engineering": [], "badges": [],
        }

    # ---- to be implemented by each provider -------------------------
    @api.model
    def _build_payload(self, scope, category_id, facets, search, offset, limit):
        raise NotImplementedError(
            "%s must implement _build_payload" % self._name)

    @api.model
    def _build_detail(self, product_id):
        raise NotImplementedError(
            "%s must implement _build_detail" % self._name)

    @api.model
    def _numeric_prefix(self, value):
        """Leading number in a string, or None.

        Grit '120' must sort before '220' and after '80'. Values that carry
        no leading number ('assorted', 'coarse') return None, sort LAST, and
        keep their label — a chip that silently vanishes is worse than one
        that sorts oddly.
        """
        if value is None or value is False:
            return None
        text = str(value).strip()
        digits = ""
        for ch in text:
            if ch.isdigit() or (ch == "." and "." not in digits):
                digits += ch
            else:
                break
        if not digits or digits == ".":
            return None
        try:
            return float(digits)
        except ValueError:
            return None
