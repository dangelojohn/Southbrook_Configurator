# SPDX-License-Identifier: LGPL-3.0-only
"""A1 — Prodboard cabinet-archetype taxonomy.

A taxonomy layer SEPARATE from the price-bearing southbrook product
templates (those carry locked xml_ids per CLAUDE.md Q8). Archetypes
describe *what kind of cabinet exists* — the body class, the type
suffix (highline / drawerline / multi-drawer / etc.), the width
grid, and the canonical image. The configurator + recommender layers
read this taxonomy when answering "what archetype is this template?"
or "what widths does an MD3DW typically come in?".

Sourced from the Prodboard BetterKitchens catalogue exported into
``data/prodboard_taxonomy_source.json`` — 223 archetypes (160 Classic
Collection + 63 True Handleless).

This is purely additive metadata. It does not replace, mutate, or
shadow the existing southbrook product templates. The seed is
idempotent.
"""
import json
import logging
import os
import re
from urllib.parse import unquote

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


# Body-class derivation from the {body} character right after the
# collection prefix (CC- or TH-). A few archetypes are end-panel /
# filler / appliance shells that don't fit Base/Wall/Tall/Corner/
# Dresser cleanly — those fall through to "other".
_BODY_PREFIXES = {
    "B": "base",
    "W": "wall",
    "T": "tall",
    "C": "corner",
    "D": "dresser",
}

# Two-letter type codes appearing right after the body character.
# Documented in docs/prodboard_lessons_2026-06-18.md (the SKU grammar
# breakdown). Used for the cabinet_type field's display label so a
# new author can read it at a glance without learning the cipher.
_TYPE_LABELS = {
    "HL": "Highline",
    "DL": "Drawerline",
    "MD": "Multi-Drawer",
    "BN": "Bin",
    "BS": "Belfast Sink",
    "HS": "Highline Sink",
    "DS": "Dummy Sink (Drawerless Front)",
    "PO": "Pull-Out",
    "UO": "Under-Oven (Built-Under)",
    "OM": "Oven + Microwave",
    "WO": "Wine Open",
    "WP": "Wine Pull",
    "OP": "Open",
    "OE": "Open End",
    "CV": "Curved",
    "DG": "Dresser Glass",
    "DL": "Dresser Larder",
    "DO": "Dresser Open",
    "DT": "Dresser Tambour",
    "DW": "Dresser Worktop",
    "WC": "Wall Corner",
    "WL": "Wall L-Shape",
    "WD": "Wall Door",
    "WG": "Wall Glass",
    "WS": "Wall Splay",
    "WT": "Wall Top Box",
    "WV": "Wall Vertical",
    "WB": "Wall Bridging",
    "WW": "Wall Wine",
    "WO": "Wall Open Display",
    "TA": "Tall Appliance Housing",
    "TF": "Tall Fridge / Freezer",
    "TL": "Tall Larder",
    "TS": "Tall Swing",
    "TP": "Tall Pull-Out",
    "Ti": "Tall Internal Drawers",
    "TO": "Tall Open",
    "TC": "Tall Corner",
    "TD": "Tall Diagonal",
    "TW": "Tall Wine",
    "CC": "Corner Classic",
    "CH": "Corner Highline",
    "CD": "Corner Drawerline",
    "CL": "Corner L-Shape",
}

# Image-URL pattern: blobs.prodboard.com/betterkitchens/icon/{uuid}/{filename}
# Captures the UUID + filename so we can store them per-archetype and
# reconstruct (or proxy) the URL when needed.
_IMAGE_URL_RE = re.compile(
    r"^https?://blobs\.prodboard\.com/[^/]+/icon/"
    r"(?P<uuid>[0-9a-f-]{36})/"
    r"(?P<filename>.+)$"
)


class SouthbrookCabinetArchetype(models.Model):
    _name = "southbrook.cabinet.archetype"
    _description = "Southbrook cabinet archetype (Prodboard taxonomy)"
    _order = "collection, code"
    _rec_name = "code"

    external_id = fields.Integer(
        string="Source ID",
        index=True,
        copy=False,
        help="The id field from the Prodboard JSON source. Stable across "
             "re-imports — used as the idempotency key.",
    )
    code = fields.Char(
        string="Code",
        required=True,
        index=True,
        copy=False,
        help="Type-encoded cabinet code (e.g. CC-BHL2DR, TH-TPM{S}ST7T). "
             "Curly-brace tokens are template variables ({S} = size, "
             "{H} = height) the configurator resolves at variant time.",
    )
    name = fields.Char(required=True)
    collection = fields.Selection(
        [("classic", "Classic Collection"),
         ("handleless", "True Handleless"),
         ("other", "Other")],
        required=True,
        default="other",
    )
    body_class = fields.Selection(
        [("base", "Base"),
         ("wall", "Wall"),
         ("tall", "Tall"),
         ("corner", "Corner"),
         ("dresser", "Dresser"),
         ("end_panel", "End Panel / Filler"),
         ("other", "Other")],
        required=True,
        default="other",
        index=True,
        help="High-level cabinet body class derived from the code prefix.",
    )
    cabinet_type = fields.Char(
        string="Type",
        help="Short type token from the code (e.g. HL, DL, MD, MC, BCO). "
             "See _TYPE_LABELS in the model module for the full glossary.",
    )
    cabinet_type_label = fields.Char(
        string="Type Label",
        compute="_compute_cabinet_type_label",
        store=True,
        help="Human-readable expansion of cabinet_type.",
    )
    width_default_mm = fields.Integer(string="Default Width (mm)")
    width_available_json = fields.Text(
        string="Available Widths (JSON)",
        help="JSON list of available widths in mm. Empty list when the "
             "archetype has a single fixed width.",
    )
    height_default_mm = fields.Integer(string="Default Height (mm)")
    depth_default_mm = fields.Integer(string="Default Depth (mm)")
    image_uuid = fields.Char(
        string="Image UUID",
        index=True,
        help="UUID portion of the Prodboard CDN URL. The A4 image-proxy "
             "controller can reconstruct the URL from this + image_filename.",
    )
    image_filename = fields.Char()
    image_url = fields.Char(string="Image URL (reference)")
    active = fields.Boolean(default=True)

    _name_uniq = models.Constraint(
        "UNIQUE(external_id)",
        "Each archetype's external_id must be unique within the catalogue.",
    )

    @api.depends("cabinet_type")
    def _compute_cabinet_type_label(self):
        for rec in self:
            rec.cabinet_type_label = (
                _TYPE_LABELS.get(rec.cabinet_type or "", "") or rec.cabinet_type
            )


class SouthbrookProdboardTaxonomy(models.AbstractModel):
    _name = "southbrook.estimating.prodboard_taxonomy"
    _description = (
        "Seed helper for the Prodboard cabinet-archetype taxonomy. "
        "Reads data/prodboard_taxonomy_source.json and upserts "
        "southbrook.cabinet.archetype records idempotently."
    )

    @api.model
    def _json_source_path(self):
        # Resolve the JSON relative to this module's data directory so
        # the seed travels with the addon and survives -u on QNAP.
        return os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data", "prodboard_taxonomy_source.json",
        )

    @api.model
    def seed_from_json(self):
        """Upsert archetype records from the JSON source. Idempotent —
        re-runs after a content change update existing rows; the
        external_id field is the key.

        Returns (created, updated, skipped) counts."""
        path = self._json_source_path()
        if not os.path.isfile(path):
            _logger.warning("Prodboard taxonomy JSON not found at %s", path)
            return (0, 0, 0)

        with open(path, "r") as fh:
            payload = json.load(fh)

        Archetype = self.env["southbrook.cabinet.archetype"]
        created = updated = skipped = 0

        collection_keys = (
            ("classic_collection", "classic"),
            ("true_handleless", "handleless"),
        )
        for json_key, collection_value in collection_keys:
            section = payload.get(json_key) or {}
            for prod in section.get("products") or []:
                vals = self._product_to_vals(prod, collection_value)
                if not vals:
                    skipped += 1
                    continue
                existing = Archetype.search(
                    [("external_id", "=", vals["external_id"])], limit=1)
                if existing:
                    existing.write(vals)
                    updated += 1
                else:
                    Archetype.create(vals)
                    created += 1

        _logger.info(
            "Prodboard taxonomy seed: created=%d, updated=%d, skipped=%d",
            created, updated, skipped,
        )
        return (created, updated, skipped)

    @api.model
    def _product_to_vals(self, prod, collection):
        """Translate one JSON product dict to archetype create vals.
        Returns None when the row is malformed (missing id or code).
        """
        eid = prod.get("id")
        code = (prod.get("code") or "").strip()
        if not eid or not code:
            return None
        widths_avail = prod.get("width_available") or []
        body_class, cabinet_type = self._classify_code(code)
        image_url = prod.get("image_url") or ""
        image_uuid, image_filename = self._parse_image_url(image_url)
        return {
            "external_id": int(eid),
            "code": code,
            "name": prod.get("name") or code,
            "collection": collection,
            "body_class": body_class,
            "cabinet_type": cabinet_type,
            "width_default_mm": int(prod.get("width_default") or 0),
            "width_available_json": json.dumps(widths_avail),
            "height_default_mm": int(prod.get("height_default") or 0),
            "depth_default_mm": int(prod.get("depth_default") or 0),
            "image_uuid": image_uuid,
            "image_filename": image_filename,
            "image_url": image_url,
        }

    @api.model
    def _classify_code(self, code):
        """Derive (body_class, cabinet_type) from the code grammar.

        CC-BHL1DR  → (base, HL)
        TH-TLM{S}FHD  → (tall, TL) — the LM is wrapped around the size
                        variable {S}; we strip braces and surrounding noise.
        BF / TF / WF / SBEP / etc.  → (end_panel, None) — no collection prefix.
        """
        # Strip collection prefix.
        stripped = code
        for prefix in ("CC-", "TH-"):
            if stripped.startswith(prefix):
                stripped = stripped[len(prefix):]
                break
        else:
            # End-panels and fillers have no collection prefix.
            return ("end_panel", None)

        if not stripped:
            return ("other", None)

        body_char = stripped[0]
        body_class = _BODY_PREFIXES.get(body_char, "other")
        # Type token is up to the next non-letter character (a digit, a
        # curly brace, or end-of-string).
        rest = stripped[1:]
        cabinet_type = ""
        for ch in rest:
            if ch.isalpha():
                cabinet_type += ch
            else:
                break
        # Strip the type to two chars if it goes longer (some codes
        # have multi-letter qualifiers like "BUOSM" — we treat the
        # first two as the canonical type code).
        cabinet_type = cabinet_type[:2].upper() or None
        return (body_class, cabinet_type)

    @api.model
    def _parse_image_url(self, image_url):
        if not image_url:
            return (None, None)
        m = _IMAGE_URL_RE.match(image_url)
        if not m:
            return (None, None)
        return (m.group("uuid"), unquote(m.group("filename")))
