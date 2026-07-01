# SPDX-License-Identifier: LGPL-3.0-only
"""Canonical price_extra backfill for product.template.attribute.value.

Supersedes `southbrook_configurator_ux/models/tactical_price_seed.py` (the
demo-grade table shipped with a "REMOVE this file once
southbrook_estimating/data/attribute_values.xml is populated" comment).

Why an AbstractModel + XML pair (and not pure XML): PTAV rows are auto-
materialised by Odoo when a product.template.attribute.line is created,
so they carry no xml_ids. A search-then-write helper is required to
target them declaratively. Runtime edits by the product owner in the
backend UI survive re-runs of the seed via the `noupdate="1"` guard on
the wrapper XML file — the seed only applies on -i or a fresh install.

Blast radius = customer-visible pricing. Do not add speculative rows;
every entry must trace back to Southbrook_Consolidated_Dataset.xlsx
Price Master or to a CLAUDE.md §5 declarative rule.
"""
from odoo import api, models


class SouthbrookPTAVPriceExtraSeed(models.AbstractModel):
    _name = "southbrook.estimating.ptav_price_extra_seed"
    _description = (
        "Backfill price_extra on product.template.attribute.value from a "
        "canonical (product.attribute.value xml_id → per-template price) table."
    )

    @api.model
    def seed_price_extra_for_value(self, value_xml_id, per_template_extras):
        """Write price_extra on every PTAV row for `value_xml_id`.

        :param value_xml_id: an xml_id from southbrook_estimating pointing
            at a product.attribute.value (the master value).
        :param per_template_extras: dict of {template_xml_id: price_extra},
            all xml_ids in the southbrook_estimating namespace.
        :returns: number of PTAV rows updated.

        Idempotent. Silently skips (template, value) pairs where no PTAV
        exists — that happens when the template's attribute_line does not
        include this value (e.g. Signature is not on the vanity template).
        """
        ref = self.env.ref
        value = ref("southbrook_estimating.%s" % value_xml_id,
                    raise_if_not_found=False)
        if not value:
            return 0
        PTAV = self.env["product.template.attribute.value"]
        updated = 0
        for tmpl_xml_id, extra in per_template_extras.items():
            tmpl = ref("southbrook_estimating.%s" % tmpl_xml_id,
                       raise_if_not_found=False)
            if not tmpl:
                continue
            row = PTAV.search([
                ("product_tmpl_id", "=", tmpl.id),
                ("product_attribute_value_id", "=", value.id),
            ], limit=1)
            if row:
                row.write({"price_extra": float(extra)})
                updated += 1
        return updated

    @api.model
    def seed_price_extra_batch(self, batch):
        """Convenience entry point for XML data-file calls.

        :param batch: list of [value_xml_id, per_template_extras_dict] pairs.
        :returns: total PTAV rows updated across the batch.
        """
        total = 0
        for value_xml_id, extras in batch:
            total += self.seed_price_extra_for_value(value_xml_id, extras)
        return total
