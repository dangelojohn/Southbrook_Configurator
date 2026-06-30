# SPDX-License-Identifier: LGPL-3.0-only
"""Map the 12 locked Southbrook templates to cloned catalogue archetypes.

This deliberately avoids cloning the full UK catalogue into sellable
product.template rows. The 12 Q8 templates remain authoritative for
pricing, rules, BoMs, and configurator UX; this helper adds reference
taxonomy through `x_prodboard_archetype_id`.
"""
import logging
import base64
import struct
import uuid
import zlib

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

SOUTHBROOK_TEMPLATE_PLACEHOLDERS = {
    "wall_1dr": ("Wall 1 Door", "wall", 1),
    "wall_2dr": ("Wall 2 Door", "wall", 2),
    "base_1dr": ("Base 1 Door", "base", 1),
    "base_2dr": ("Base 2 Door", "base", 2),
    "drawer_bank": ("Drawer Bank", "drawer", 3),
    "sink_base": ("Sink Base", "sink", 2),
    "tall_pantry": ("Tall Pantry", "tall", 2),
    "tall_oven": ("Tall Oven", "oven", 2),
    "corner": ("Corner", "corner", 2),
    "vanity": ("Vanity", "vanity", 2),
    "accessory": ("Accessory", "accessory", 1),
    "worktop": ("Worktop", "worktop", 1),
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

    @api.model
    def assign_placeholder_images(self, force=False):
        """Assign Southbrook-owned generated PNG placeholders.

        The generated image content is deliberately local and schematic. It
        does not render Prodboard artwork. By default, existing product images
        are preserved; `force=True` regenerates them.

        Returns (written, skipped, missing) counts.
        """
        written = skipped = missing = 0
        for slug, spec in SOUTHBROOK_TEMPLATE_PLACEHOLDERS.items():
            tmpl = self.env.ref(
                "southbrook_estimating." + slug,
                raise_if_not_found=False,
            )
            if not tmpl:
                tmpl = self.env.ref("southbrook." + slug,
                                    raise_if_not_found=False)
            if not tmpl:
                missing += 1
                _logger.info(
                    "Template placeholder image: template '%s' missing",
                    slug,
                )
                continue

            values = {
                "x_image_uuid": self._placeholder_uuid(slug),
                "x_image_filename": "southbrook-%s.png" % slug,
            }
            if force or not tmpl.image_1920:
                values["image_1920"] = base64.b64encode(
                    self._render_placeholder_png(slug, spec),
                ).decode("ascii")
                written += 1
            else:
                skipped += 1
            tmpl.write(values)

        _logger.info(
            "Template placeholder images: written=%d, skipped=%d, missing=%d",
            written, skipped, missing,
        )
        return (written, skipped, missing)

    @api.model
    def _placeholder_uuid(self, slug):
        return str(uuid.uuid5(
            uuid.NAMESPACE_URL,
            "https://southbrookcabinetry.space/catalog-placeholder/%s/v1"
            % slug,
        ))

    @api.model
    def _render_placeholder_png(self, slug, spec):
        _label, kind, count = spec
        width, height = 640, 480
        bg = (246, 244, 238)
        ink = (73, 64, 54)
        shadow = (194, 172, 142)
        gold = (200, 155, 90)
        blue = (63, 88, 126)
        green = (88, 125, 96)
        pixels = bytearray(bg * width * height)

        def set_px(x, y, color):
            if 0 <= x < width and 0 <= y < height:
                i = (y * width + x) * 3
                pixels[i:i + 3] = bytes(color)

        def rect(x1, y1, x2, y2, color, fill=True):
            x1, x2 = sorted((max(0, x1), min(width - 1, x2)))
            y1, y2 = sorted((max(0, y1), min(height - 1, y2)))
            if fill:
                for y in range(y1, y2 + 1):
                    start = (y * width + x1) * 3
                    pixels[start:start + (x2 - x1 + 1) * 3] = (
                        bytes(color) * (x2 - x1 + 1)
                    )
            else:
                for x in range(x1, x2 + 1):
                    set_px(x, y1, color)
                    set_px(x, y2, color)
                for y in range(y1, y2 + 1):
                    set_px(x1, y, color)
                    set_px(x2, y, color)

        def line(x1, y1, x2, y2, color):
            dx = abs(x2 - x1)
            dy = -abs(y2 - y1)
            sx = 1 if x1 < x2 else -1
            sy = 1 if y1 < y2 else -1
            err = dx + dy
            while True:
                set_px(x1, y1, color)
                if x1 == x2 and y1 == y2:
                    break
                e2 = 2 * err
                if e2 >= dy:
                    err += dy
                    x1 += sx
                if e2 <= dx:
                    err += dx
                    y1 += sy

        # Framing and shop-floor neutral background.
        rect(56, 58, 584, 422, (255, 255, 252), True)
        rect(56, 58, 584, 422, shadow, False)
        rect(84, 84, 556, 394, (238, 235, 226), True)

        if kind == "wall":
            x1, y1, x2, y2 = 175, 100, 465, 285
        elif kind == "tall":
            x1, y1, x2, y2 = 210, 76, 430, 382
        elif kind == "worktop":
            x1, y1, x2, y2 = 120, 202, 520, 260
        elif kind == "accessory":
            x1, y1, x2, y2 = 190, 160, 450, 318
        else:
            x1, y1, x2, y2 = 170, 132, 470, 354

        rect(x1 + 16, y2 + 18, x2 + 18, y2 + 36, shadow, True)
        rect(x1, y1, x2, y2, (230, 224, 211), True)
        rect(x1, y1, x2, y2, ink, False)
        rect(x1 + 14, y1 + 14, x2 - 14, y2 - 14, (247, 245, 239), True)
        rect(x1 + 14, y1 + 14, x2 - 14, y2 - 14, ink, False)

        if kind == "drawer":
            step = max(32, (y2 - y1 - 38) // count)
            for i in range(count):
                yy = y1 + 20 + i * step
                rect(x1 + 28, yy, x2 - 28, yy + step - 12,
                     (250, 249, 245), True)
                rect(x1 + 28, yy, x2 - 28, yy + step - 12, ink, False)
                rect((x1 + x2) // 2 - 32, yy + 12,
                     (x1 + x2) // 2 + 32, yy + 18, gold, True)
        elif kind == "sink":
            line(x1 + 36, y1 + 38, x2 - 36, y1 + 38, blue)
            rect((x1 + x2) // 2 - 56, y1 + 52,
                 (x1 + x2) // 2 + 56, y1 + 96, (214, 224, 226), True)
            rect((x1 + x2) // 2 - 56, y1 + 52,
                 (x1 + x2) // 2 + 56, y1 + 96, blue, False)
            line((x1 + x2) // 2, y1 + 30, (x1 + x2) // 2, y1 + 52, blue)
        elif kind == "oven":
            rect(x1 + 38, y1 + 74, x2 - 38, y1 + 168, (63, 68, 75), True)
            rect(x1 + 52, y1 + 88, x2 - 52, y1 + 154, (132, 150, 162), True)
            rect(x1 + 38, y1 + 188, x2 - 38, y2 - 34,
                 (247, 245, 239), True)
            rect(x1 + 38, y1 + 188, x2 - 38, y2 - 34, ink, False)
        elif kind == "corner":
            line(x1, y1, x2 - 64, y1 + 56, ink)
            line(x2, y1, x2 - 64, y1 + 56, ink)
            line(x2 - 64, y1 + 56, x2 - 64, y2, ink)
        elif kind == "accessory":
            for i in range(4):
                yy = y1 + 26 + i * 30
                line(x1 + 42, yy, x2 - 42, yy, green)
                rect(x1 + 34, yy - 5, x1 + 44, yy + 5, gold, True)
        elif kind == "worktop":
            rect(x1, y1, x2, y2, gold, True)
            rect(x1, y1, x2, y2, ink, False)
            line(x1 + 24, y1 + 16, x2 - 24, y2 - 16, (238, 216, 183))
        else:
            if count == 2:
                mid = (x1 + x2) // 2
                line(mid, y1 + 14, mid, y2 - 14, ink)
                rect(mid - 20, (y1 + y2) // 2 - 4,
                     mid - 10, (y1 + y2) // 2 + 4, gold, True)
                rect(mid + 10, (y1 + y2) // 2 - 4,
                     mid + 20, (y1 + y2) // 2 + 4, gold, True)
            else:
                rect(x2 - 46, (y1 + y2) // 2 - 5,
                     x2 - 34, (y1 + y2) // 2 + 5, gold, True)

        # Deterministic corner mark by slug, avoiding embedded text/fonts.
        mark = sum(ord(c) for c in slug) % 9
        for i in range(mark + 1):
            rect(102 + i * 16, 368, 112 + i * 16, 378, gold, True)

        raw = b"".join(
            b"\x00" + bytes(pixels[y * width * 3:(y + 1) * width * 3])
            for y in range(height)
        )
        return self._png_from_raw_rgb(width, height, raw)

    @api.model
    def _png_from_raw_rgb(self, width, height, raw):
        def chunk(tag, data):
            return (
                struct.pack(">I", len(data))
                + tag
                + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
            )

        return (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB",
                                         width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b"")
        )
