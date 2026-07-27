# SPDX-License-Identifier: LGPL-3.0-only
"""T4a (kitchen templates) — SB-CORNER catalog data repair.

Ground truth (live prod, 2026-07-27 — .superpowers/sdd/t4a-groundtruth.md):
the Q8 corner template is a 36"x36"x34.5" HIGHLINE corner base
(archetype CC-CHL), but its single live variant carries Width='33 in'
(the outlier — 3 of 4 data points say 36) and only an LH hand, which
blocked every L/U kitchen template from shipping. The Width and Hinge
Side attribute LINES already allow '36 in' and 'RH (Right Hand)' — this
is variant-level data repair, not schema work.

Called from the 19.0.9.1.0 post-migration AND from tests (which first
recreate the known-bad prod state on a bare DB). Idempotent: every step
is guarded to the known-bad state, so a later hand edit is never
clobbered and re-running is a no-op.
"""
import logging

_logger = logging.getLogger(__name__)


def repair_corner_sku(env):
    """Repair SB-CORNER variants. Returns a summary dict.

    1. Any variant whose Width PTAV is '33 in' is relinked to '36 in'.
    2. LH variants with no default_code get 'SB-CORNER' backfilled.
    3. An RH twin (default_code 'SB-CORNER-R') is created when an LH
       variant exists and no RH variant does — enabling right-facing
       L/U layouts (the corner engine picks the variant by the node's
       handedness).
    4. The WALL-layer corner SKU (SB-WALL-CORNER) is seeded if absent —
       the arrange engine substitutes it for junction uppers, and with
       no product it silently ARCHIVES those uppers and inserts nothing
       (catalog blocker #1: "no wall-layer equivalent"). Placeholder
       price flagged for the shop to reprice.
    """
    summary = {"width_fixed": 0, "codes_set": 0, "rh_created": False,
               "wall_corner_created": False}
    Template = env["product.template"]
    if not Template.search(
            [("default_code", "=", "SB-WALL-CORNER")], limit=1):
        vals = {
            "name": "Corner Wall Cabinet",
            "default_code": "SB-WALL-CORNER",
            "type": "consu",
            "list_price": 295.0,
        }
        if "southbrook_cabinet_type" in Template._fields:
            # Classification fields belong to the 3D configurator addon
            # (installed on prod; guarded for estimating-only DBs).
            vals.update({
                "southbrook_cabinet_type": "corner",
                "southbrook_width_in": 24.0,
                "southbrook_height_in": 30.0,
                "southbrook_depth_in": 12.0,
            })
        Template.create(vals)
        summary["wall_corner_created"] = True
    tmpl = env.ref("southbrook_estimating.corner", raise_if_not_found=False)
    if not tmpl:
        return summary
    PTAV = env["product.template.attribute.value"]

    def _ptav(attr_name, prefix):
        return PTAV.search([
            ("product_tmpl_id", "=", tmpl.id),
            ("attribute_id.name", "=", attr_name),
            ("name", "=like", prefix + "%"),
        ], limit=1)

    p33 = _ptav("Width", "33")
    p36 = _ptav("Width", "36")
    lh = _ptav("Hinge Side", "LH")
    rh = _ptav("Hinge Side", "RH")

    if p33 and p36:
        bad = tmpl.product_variant_ids.filtered(
            lambda v: p33 in v.product_template_attribute_value_ids)
        for variant in bad:
            variant.write({"product_template_attribute_value_ids": [
                (3, p33.id), (4, p36.id)]})
            summary["width_fixed"] += 1

    if lh and rh:
        variants = tmpl.product_variant_ids
        lh_variants = variants.filtered(
            lambda v: lh in v.product_template_attribute_value_ids)
        rh_variants = variants.filtered(
            lambda v: rh in v.product_template_attribute_value_ids)
        for variant in lh_variants.filtered(lambda v: not v.default_code):
            variant.default_code = "SB-CORNER"
            summary["codes_set"] += 1
        if lh_variants and not rh_variants:
            combo = (lh_variants[0].product_template_attribute_value_ids
                     - lh) | rh
            env["product.product"].create({
                "product_tmpl_id": tmpl.id,
                "product_template_attribute_value_ids": [(6, 0, combo.ids)],
                "default_code": "SB-CORNER-R",
            })
            summary["rh_created"] = True

    if any(v for v in summary.values()):
        _logger.info("[T4a corner repair] %s", summary)
    return summary
