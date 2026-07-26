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
        """Return one catalog payload. Never raises."""
        try:
            provider_name = SCOPES.get(scope)
            if not provider_name or provider_name not in self.env:
                return self._degrade("Unknown catalog scope: %s" % scope, scope)
            provider = self.env[provider_name]
            return provider._build_payload(
                scope=scope, category_id=category_id, facets=facets or {},
                search=search or "", offset=offset, limit=limit)
        except Exception as exc:  # noqa: BLE001 — degrade, never 500
            _logger.exception("Catalog payload build failed")
            return self._degrade(str(exc)[:200], scope)

    @api.model
    def _degrade(self, reason, scope):
        return {
            "ok": False, "reason": reason, "scope": scope,
            "categories": [], "facets": [], "columns": [], "rows": [],
            "detail": {}, "total": 0,
            "provenance": "Catalog unavailable.",
        }

    @api.model
    def get_detail(self, product_id, scope="tools"):
        """Return one detail payload. Never raises.

        Degrades the same way get_catalog() does: {"ok": False, "reason":
        ...} with every contract key still present, so the frontend never
        has to special-case a missing key.
        """
        try:
            provider_name = SCOPES.get(scope)
            if not provider_name or provider_name not in self.env:
                return self._degrade_detail("Unknown scope")
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
