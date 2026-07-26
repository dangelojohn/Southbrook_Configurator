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

Task A2 (Materials geometry-writeback plan, 2026-07-24) — this same
hook also stamps the Task A1 geometry fields (`sb_width_mm`,
`sb_height_mm`, `sb_depth_mm`, `sb_panel_family`, `sb_door_count`,
`sb_drawer_count`, `sb_finished_sides`) onto every variant materialised
via the OCA configurator wizard (`create_get_variant` ->
`get_variant_vals`), by calling the existing
`_extract_cabinet_inputs()` resolver (defined on this same
`product.config.session` model in `product_config_line.py`; merged
into one registry class at runtime, so `self._extract_cabinet_inputs()`
is directly callable here — no cross-model relation needed). This is
LIVE: `_extract_cabinet_inputs()` is wrapped in try/except so a
resolver failure on a non-cabinet / malformed template NEVER breaks
variant creation for the rest of the catalogue — it just leaves the
geometry fields at their model defaults (0 / "base" / "none").

Finding I-1 fix (final review, 2026-07-24) — the write is additionally
gated on `geo.get("_geo_resolved")`: `_extract_cabinet_inputs()` always
returns non-zero hard-default dims (it was built for the 3D viewport,
which needs SOMETHING to render), so an ungated `if geo:` fabricated
geometry on templates with no real SKU-table hit and no `attr_width`
pick. Only a resolver-confirmed real geometry signal gets written.
"""
import hashlib
import logging

from odoo import models

_logger = logging.getLogger(__name__)


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

        # Task A2 — geometry writeback. Never let a resolver failure
        # break variant creation for the rest of the catalogue.
        try:
            geo = self._extract_cabinet_inputs()
        except Exception:  # noqa: BLE001
            _logger.exception(
                "sb_geo: _extract_cabinet_inputs() failed for session %s "
                "(template %s) — leaving geometry fields at defaults.",
                self.id, tmpl.id,
            )
            geo = None
        # Finding I-1 fix (2026-07-24): `_extract_cabinet_inputs()` always
        # returns a non-empty dict — it seeds hard-default geometry
        # (609x762x609, family=base) at step 1 before the SKU lookup even
        # runs, so a plain `if geo:` was always truthy and stamped
        # fabricated non-zero dims onto EVERY configured variant,
        # including templates with no real SKU-table hit and no
        # `attr_width` pick. Gate on the resolver's own `_geo_resolved`
        # signal instead — True only when the SKU lookup or a real
        # attr_width pick actually resolved geometry (see that method's
        # docstring). An unresolved template now honestly leaves the
        # variant's sb_* fields at their model defaults (0 / "base" /
        # "none"), matching A3's backfill honesty contract exactly.
        if geo and geo.get("_geo_resolved"):
            vals.update({
                "sb_width_mm": int(geo.get("width_mm") or 0),
                "sb_height_mm": int(geo.get("height_mm") or 0),
                "sb_depth_mm": int(geo.get("depth_mm") or 0),
                "sb_panel_family": geo.get("family") or "base",
                "sb_door_count": int(geo.get("door_count") or 1),
                "sb_drawer_count": int(geo.get("drawer_count") or 0),
                "sb_finished_sides": geo.get("finished_sides") or "none",
            })

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
