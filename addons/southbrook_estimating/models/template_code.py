# SPDX-License-Identifier: LGPL-3.0-only
"""A5 — Type-encoded default_code on product.template archetypes.

The Prodboard catalogue uses type-encoded codes on the cabinet TYPE
(e.g. CC-BHL2DR for a Classic Collection Double Highline Base). Today
Southbrook's SKU lives on product.product.default_code (computed by the
P5 grammar from configurator picks). That config-encoded code can't
answer "what KIND of cabinet is this?" without parsing.

A5 adds a parallel TYPE-encoded code on product.template.default_code
using the Southbrook SB- prefix and the Prodboard cipher (B=Base, W=Wall,
T=Tall, C=Corner, D=Dresser; HL=Highline, DL=Drawerline, MD=Multi-
Drawer, etc). E.g.:

  southbrook.base_2dr     -> SB-BHL2DR
  southbrook.drawer_bank  -> SB-BMD3DW
  southbrook.tall_pantry  -> SB-TFHD
  southbrook.corner       -> SB-CHL

The product.product.default_code (P5 grammar) is untouched — it
continues to encode the customer-specific configuration. The two codes
coexist: the template default_code says WHAT, the variant default_code
says HOW IT'S BUILT.

Idempotent: assign_codes() never overwrites a non-empty default_code on
product.template. Existing manual codes survive untouched.
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


# Southbrook -> Prodboard type-code mapping. Keyed by xml_id slug
# (without the southbrook. namespace). Templates not in this table are
# skipped — no auto-coding of unknowns.
SOUTHBROOK_TEMPLATE_CODES = {
    # ---------- Base cabinets ----------
    "base_1dr":       "BHL1DR",   # Base Highline 1-Door
    "base_2dr":       "BHL2DR",   # Base Highline 2-Door
    "drawer_bank":    "BMD3DW",   # Base Multi-Drawer 3-Drawer
    "sink_base":      "BHS1DR",   # Base Highline Sink 1-Door
    # ---------- Wall cabinets ----------
    "wall_1dr":       "WD1DR",    # Wall Door 1-Door
    "wall_2dr":       "WD2DR",    # Wall Door 2-Door
    # ---------- Tall cabinets ----------
    "tall_pantry":    "TFHD",     # Tall Full-Height Door (larder)
    "tall_oven":      "TASODRS",  # Tall Single Oven Housing with Doors
    # ---------- Corner cabinets ----------
    "corner":         "CHL",      # Corner Highline (base)
    # ---------- Other (no direct Prodboard analogue) ----------
    "vanity":         "BVAN",     # Custom: Base Vanity (NA-specific term)
    "accessory":      "ACC",      # Composite — accessories live elsewhere
    "worktop":        "WTP",      # Composite — worktops are linear-foot
}


class SouthbrookTemplateCode(models.AbstractModel):
    _name = "southbrook.estimating.template_code"
    _description = (
        "A5 helper — assigns type-encoded SB-* default_codes to the "
        "Southbrook Q8 cabinet templates. Idempotent: writes only when "
        "default_code is empty."
    )

    @api.model
    def assign_codes(self):
        """Walk SOUTHBROOK_TEMPLATE_CODES, look up the corresponding
        product.template by xml_id, and write SB-<code> to default_code
        if (and only if) default_code is currently empty.

        Returns (written, skipped, missing) counts."""
        written = skipped = missing = 0
        for slug, type_code in SOUTHBROOK_TEMPLATE_CODES.items():
            xml_id = "southbrook_estimating." + slug
            tmpl = self.env.ref(xml_id, raise_if_not_found=False)
            if not tmpl:
                # Some Southbrook templates may live under a different
                # xml_id namespace per the migrations history. Try the
                # bare "southbrook." namespace as a fallback.
                tmpl = self.env.ref("southbrook." + slug,
                                    raise_if_not_found=False)
            if not tmpl:
                missing += 1
                _logger.info("A5: template '%s' not found, skipped", slug)
                continue
            new_code = "SB-" + type_code
            if tmpl.default_code:
                if tmpl.default_code == new_code:
                    skipped += 1
                else:
                    # Existing code is a manual choice — never overwrite.
                    skipped += 1
                continue
            tmpl.default_code = new_code
            written += 1
        _logger.info(
            "A5 template-code assignment: written=%d, skipped=%d, missing=%d",
            written, skipped, missing,
        )
        return (written, skipped, missing)
