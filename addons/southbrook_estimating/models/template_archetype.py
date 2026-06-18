# SPDX-License-Identifier: LGPL-3.0-only
"""Map the 12 locked Southbrook templates to cloned catalogue archetypes.

This deliberately avoids cloning the full UK catalogue into sellable
product.template rows. The 12 Q8 templates remain authoritative for
pricing, rules, BoMs, and configurator UX; this helper adds reference
taxonomy through `x_prodboard_archetype_id`.
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


SOUTHBROOK_TEMPLATE_ARCHETYPE_CODES = {
    # ---------- Base cabinets ----------
    "base_1dr": "CC-BHL1DR",
    "base_2dr": "CC-BHL2DR",
    "drawer_bank": "CC-BMD3DW",
    "sink_base": "CC-BHS1DR",
    # ---------- Wall cabinets ----------
    "wall_1dr": "CC-WD{H}1DR",
    "wall_2dr": "CC-WD{H}2DR",
    # ---------- Tall cabinets ----------
    "tall_pantry": "CC-TL{H}{h}T",
    "tall_oven": "CC-TA{H}SODRS",
    # ---------- Corner cabinets ----------
    "corner": "CC-CHL{S}",
    # ---------- Southbrook-only placeholders ----------
    # vanity/accessory/worktop have no clean BetterKitchens cabinet
    # archetype in the supplied JSON. Leave them unmapped rather than
    # forcing a misleading UK reference.
}


class SouthbrookTemplateArchetype(models.AbstractModel):
    _name = "southbrook.estimating.template_archetype"
    _description = (
        "Assigns cloned Prodboard catalogue archetypes to the locked "
        "Southbrook Q8 product templates. Idempotent."
    )

    @api.model
    def assign_archetypes(self):
        """Assign `x_prodboard_archetype_id` on mapped Q8 templates.

        Returns (written, skipped, missing_template, missing_archetype).
        """
        TemplateArchetype = self.env["southbrook.cabinet.archetype"]
        written = skipped = missing_template = missing_archetype = 0
        for slug, archetype_code in SOUTHBROOK_TEMPLATE_ARCHETYPE_CODES.items():
            tmpl = self.env.ref(
                "southbrook_estimating." + slug,
                raise_if_not_found=False,
            )
            if not tmpl:
                tmpl = self.env.ref("southbrook." + slug,
                                    raise_if_not_found=False)
            if not tmpl:
                missing_template += 1
                _logger.info(
                    "Template-archetype mapping: template '%s' missing",
                    slug,
                )
                continue

            archetype = TemplateArchetype.search(
                [("code", "=", archetype_code)],
                limit=1,
            )
            if not archetype:
                missing_archetype += 1
                _logger.info(
                    "Template-archetype mapping: archetype '%s' missing",
                    archetype_code,
                )
                continue

            if tmpl.x_prodboard_archetype_id == archetype:
                skipped += 1
                continue
            tmpl.x_prodboard_archetype_id = archetype.id
            written += 1

        _logger.info(
            "Template-archetype mapping: written=%d, skipped=%d, "
            "missing_template=%d, missing_archetype=%d",
            written, skipped, missing_template, missing_archetype,
        )
        return (written, skipped, missing_template, missing_archetype)
