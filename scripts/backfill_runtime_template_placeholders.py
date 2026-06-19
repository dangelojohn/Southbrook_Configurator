# SPDX-License-Identifier: LGPL-3.0-only
"""One-shot: backfill x_image_uuid + image_1920 on SB-* templates that
were created at runtime (no xml_id) and therefore aren't covered by
southbrook.estimating.template_archetype.assign_placeholder_images.

Run via:
    docker exec -i southbrook-odoo odoo shell \\
        --no-http --database=southbrook \\
        < scripts/backfill_runtime_template_placeholders.py

Idempotent — only touches templates whose x_image_uuid is blank.
Reuses the existing _placeholder_uuid + _render_placeholder_png helpers
on the template_archetype AbstractModel; doesn't introduce a new
generator. Derives a (slug, spec) pair from the default_code via
the SB-{FAMILY}-{REST} convention.
"""
import base64
import logging
import sys

_logger = logging.getLogger("backfill_runtime_placeholders")

# env is bound by odoo shell at the global scope.
TA = env["southbrook.estimating.template_archetype"].sudo()
Template = env["product.template"].sudo()


def derive_slug_and_spec(default_code):
    """Map an SB-* default_code -> (slug, (label, kind, count)).

    The slug feeds the deterministic _placeholder_uuid hash; the spec
    drives _render_placeholder_png (label is the on-image text, kind
    chooses the schematic style, count is the door/drawer/face count).
    """
    code = (default_code or "").upper().strip()
    if not code.startswith("SB-"):
        return None, None
    rest = code[3:]
    parts = rest.split("-")
    family = parts[0] if parts else ""
    label = " ".join(p.title() for p in parts)
    slug = rest.lower().replace("-", "_")

    if family == "BASE":
        if "3DRW" in rest:
            return slug, (label, "drawer", 3)
        if "4DRW" in rest:
            return slug, (label, "drawer", 4)
        if "COOKTOP" in rest:
            return slug, (label, "cooktop", 1)
        if "DISHWASH" in rest:
            return slug, (label, "appliance", 1)
        if "MICRO" in rest:
            return slug, (label, "appliance", 1)
        if "PO-" in rest or rest.startswith("PO"):
            return slug, (label, "drawer", 2)
        return slug, (label, "base", 1)
    if family == "WALL":
        return slug, (label, "wall", 1 if "1DR" in rest else 2)
    if family == "TALL":
        if "OVEN" in rest:
            return slug, (label, "oven", 2)
        return slug, (label, "tall", 2)
    if family == "ACC":
        if "ENDPANEL" in rest:
            return slug, (label, "accessory", 1)
        if "FILLER" in rest:
            return slug, (label, "accessory", 1)
        return slug, (label, "accessory", 1)
    if family == "WORKTOP":
        return slug, (label, "worktop", 1)
    # Catch-all: generic accessory styling.
    return slug, (label, "extra", 1)


def main():
    written = skipped = 0
    domain = [
        ("default_code", "=like", "SB-%"),
        "|",
        ("x_image_uuid", "=", False),
        ("x_image_uuid", "=", ""),
    ]
    for tmpl in Template.search(domain):
        slug, spec = derive_slug_and_spec(tmpl.default_code)
        if not slug:
            skipped += 1
            continue
        values = {
            "x_image_uuid": TA._placeholder_uuid(slug),
            "x_image_filename": "southbrook-%s.png" % slug,
        }
        if not tmpl.image_1920:
            try:
                png_bytes = TA._render_placeholder_png(slug, spec)
            except Exception as e:  # noqa: BLE001
                _logger.warning(
                    "render failed for %s (%s): %s",
                    tmpl.default_code, slug, e,
                )
                skipped += 1
                continue
            values["image_1920"] = base64.b64encode(png_bytes).decode("ascii")
        tmpl.write(values)
        written += 1
        print("  wrote %s -> uuid=%s, image_set=%s" % (
            tmpl.default_code, values["x_image_uuid"],
            "image_1920" in values,
        ))

    env.cr.commit()
    print("DONE — written=%d, skipped=%d" % (written, skipped))


main()
sys.exit(0)
