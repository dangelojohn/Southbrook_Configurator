# Copyright 2025 — forward-port to 19.0
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _to_markup_data(self, website):
        """Skip schema.org / JSON-LD product markup for configurable
        templates that have not yet been resolved to a variant.

        Odoo 19.0's ``website_sale`` introduced ``_to_markup_data`` on
        ``product.template``, which delegates to
        ``self.product_variant_id._to_markup_data(website)``. That call
        path eventually invokes ``ensure_one()`` on the variant record,
        which raises ``ValueError: Expected singleton: product.product()``
        whenever the template has zero variants.

        Configurable templates (``config_ok=True``) in this module
        intentionally carry zero ``product.product`` rows until a buyer
        completes a configuration session — variant creation is the
        *output* of the configurator, not its precondition. Without
        this override, every ``config_ok`` template's storefront product
        detail page returns HTTP 500 before the configurator widget
        can mount.

        Behaviour:
          * Non-configurable templates → unchanged (call ``super``).
          * Configurable templates that already have at least one
            variant → unchanged (call ``super``).
          * Configurable templates with zero variants → return an
            empty dict (no schema.org product node for this page until
            a configuration produces a variant; this is correct, since
            no canonical product exists to describe yet).

        Note: this guard intentionally checks ``product_variant_id``
        rather than ``product_variant_count``. The OCA
        ``product_configurator`` module overrides
        ``_compute_product_variant_count`` to return ``1`` even when
        zero variants exist (so configurable templates remain visible
        in product-listing UIs). That override would make a count-based
        guard useless. ``product_variant_id`` is the same M2O field
        core's ``_to_markup_data`` resolves and crashes on — checking
        it directly is the canonical test.

        Surfaced by the W1 manual acceptance walk per spec §4.3.
        """
        self.ensure_one()
        if self.config_ok and not self.product_variant_id:
            return {}
        return super()._to_markup_data(website)
