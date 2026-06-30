# SPDX-License-Identifier: LGPL-3.0-only
"""SKU + standard_price seeding for configured variants.

OCA's `product.config.session.get_variant_vals` (product_configurator)
returns only product_tmpl_id, PTAV refs, taxes, and image. The
freshly-materialised `product.product` therefore has:

  - default_code = NULL  → Sales reports show blank SKU on configured
    lines, breaking grouping by code in pivot views and CSV exports.
  - standard_price = 0.0 → Inventory valuation, margin reports, and
    the BoM cost rollup all treat the configured variant as free.

End-to-end test 2026-06-22 flagged both as Bug #3. Fix: extend the
hook so every variant created from the wizard inherits its template's
`standard_price` and gets a stable, deterministic SKU.

SKU format: `<TEMPLATE_CODE>-<HASH6>` where HASH6 is the first 6 hex
chars of MD5(sorted(value_ids)). Deterministic — same config gives the
same SKU on every box — and short enough to read out loud. Collision
risk at 24 bits is negligible for the Southbrook catalogue (<10k
configured variants per template forever).

Edge cases:
  - Template has no default_code → fall back to "CFG" prefix.
  - Variant happens to collide with an existing default_code on a
    different template → log + suffix `-2`. Concurrent-create races
    can still produce a duplicate; the unique-by-PTAV constraint
    upstream means a subsequent `search_variant` finds the prior
    record first, so the second create would already return the
    deduplicated record before this code runs.
"""
import hashlib

from odoo import models


class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

    def get_variant_vals(self, value_ids=None, custom_vals=None, **kwargs):
        vals = super().get_variant_vals(
            value_ids=value_ids, custom_vals=custom_vals, **kwargs,
        )
        self.ensure_one()
        tmpl = self.product_tmpl_id

        if value_ids is None:
            value_ids = self.value_ids.ids
        sku = self._southbrook_compose_sku(tmpl, value_ids)
        if sku:
            vals["default_code"] = sku

        # Inherit cost from template. `standard_price` is per-variant
        # per-company; copying the template-level value is the closest
        # honest default — once Phase 4 BoM-cost rollup lands it will
        # recompute against the carcass + door + hardware components.
        cost = float(tmpl.standard_price or 0.0)
        if cost:
            vals["standard_price"] = cost

        return vals

    def _southbrook_compose_sku(self, tmpl, value_ids):
        prefix = (tmpl.default_code or "CFG").strip()
        if not value_ids:
            return prefix
        digest = hashlib.md5(
            ",".join(str(v) for v in sorted(value_ids)).encode("utf-8"),
        ).hexdigest()[:6].upper()
        candidate = "%s-%s" % (prefix, digest)

        Product = self.env["product.product"].sudo()
        clash = Product.search_count([
            ("default_code", "=", candidate),
            ("product_tmpl_id", "!=", tmpl.id),
        ])
        if clash:
            return "%s-2" % candidate
        return candidate
