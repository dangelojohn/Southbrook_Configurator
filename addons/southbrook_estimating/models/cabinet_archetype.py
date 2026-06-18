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
import base64
import hashlib
import mimetypes
import os
import re
from urllib.parse import unquote
from urllib.request import Request, urlopen

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
    prodboard_source_package = fields.Char(
        string="Source Package",
        default="betterkitchens",
        help="Internal source package key for the cloned catalogue metadata. "
             "Not rendered in the public UI.",
    )
    prodboard_source_collection_key = fields.Char(
        string="Source Collection Key",
        help="JSON section key from the source catalogue, e.g. "
             "classic_collection or true_handleless.",
    )
    prodboard_asset_attachment_id = fields.Many2one(
        "ir.attachment",
        string="Imported Asset Attachment",
        copy=False,
        ondelete="set null",
        help="Private Odoo attachment containing the licensed source image "
             "binary for this archetype. Public pages do not serve this "
             "attachment directly.",
    )
    prodboard_asset_status = fields.Selection(
        [("not_imported", "Not Imported"),
         ("imported", "Imported"),
         ("missing_source", "Missing Source"),
         ("failed", "Failed")],
        string="Asset Import Status",
        default="not_imported",
        copy=False,
        index=True,
    )
    prodboard_asset_sha256 = fields.Char(
        string="Asset SHA-256",
        copy=False,
        index=True,
    )
    prodboard_asset_mimetype = fields.Char(
        string="Asset MIME Type",
        copy=False,
    )
    prodboard_asset_bytes = fields.Integer(
        string="Asset Bytes",
        copy=False,
    )
    prodboard_asset_imported_at = fields.Datetime(
        string="Asset Imported At",
        copy=False,
    )
    prodboard_asset_error = fields.Text(
        string="Asset Import Error",
        copy=False,
    )
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
            "prodboard_source_package": "betterkitchens",
            "prodboard_source_collection_key": (
                "classic_collection"
                if collection == "classic"
                else "true_handleless"
                if collection == "handleless"
                else collection
            ),
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


class SouthbrookProdboardAssetImporter(models.AbstractModel):
    _name = "southbrook.estimating.prodboard_asset_importer"
    _description = (
        "Importer for licensed Prodboard image binaries. Assets are cached "
        "as private ir.attachment rows linked to cabinet archetypes; public "
        "UI routes continue serving Southbrook-owned product.template images."
    )

    @api.model
    def import_assets(self, limit=None, offline_dir=None, allow_network=False):
        """Import image assets for seeded archetypes.

        Network access is disabled by default. In production, pass
        allow_network=True only when the deployment environment is allowed to
        fetch the licensed source images. For locked-down environments, place
        files in offline_dir named by image_uuid (for example
        {uuid}.png) or by image_filename.

        Returns a summary dict with imported/missing/failed counts.
        """
        domain = [("image_uuid", "!=", False), ("image_url", "!=", False)]
        archetypes = self.env["southbrook.cabinet.archetype"].search(
            domain,
            limit=limit or None,
        )
        summary = {"imported": 0, "missing_source": 0, "failed": 0}
        for archetype in archetypes:
            ok = self._import_one(
                archetype,
                offline_dir=offline_dir,
                allow_network=allow_network,
            )
            archetype.flush_recordset()
            if ok:
                summary["imported"] += 1
            elif archetype.prodboard_asset_status == "missing_source":
                summary["missing_source"] += 1
            else:
                summary["failed"] += 1
        return summary

    @api.model
    def _import_one(self, archetype, offline_dir=None, allow_network=False,
                    fetcher=None):
        """Import one archetype image.

        `fetcher` is a test seam accepting the source URL and returning either
        bytes or `(bytes, mimetype)`. It avoids live network calls in tests.
        """
        archetype.ensure_one()
        if not archetype.image_uuid or not archetype.image_url:
            self._write_asset_failure(
                archetype,
                "missing_source",
                "Missing image UUID or image URL",
            )
            return False

        try:
            payload = self._read_offline_asset(archetype, offline_dir)
            if payload is None and fetcher:
                payload = fetcher(archetype.image_url)
            if payload is None and allow_network:
                payload = self._fetch_url(archetype.image_url)
            if payload is None:
                self._write_asset_failure(
                    archetype,
                    "missing_source",
                    "No offline asset found and network disabled",
                )
                return False

            content, mimetype = self._normalise_payload(
                payload,
                filename=archetype.image_filename,
            )
            if not content:
                self._write_asset_failure(
                    archetype,
                    "failed",
                    "Imported asset was empty",
                )
                return False
            attachment = self._upsert_attachment(
                archetype,
                content,
                mimetype,
            )
            archetype.write({
                "prodboard_asset_attachment_id": attachment.id,
                "prodboard_asset_status": "imported",
                "prodboard_asset_sha256": hashlib.sha256(content).hexdigest(),
                "prodboard_asset_mimetype": mimetype,
                "prodboard_asset_bytes": len(content),
                "prodboard_asset_imported_at": fields.Datetime.now(),
                "prodboard_asset_error": False,
            })
            return True
        except Exception as exc:  # pragma: no cover - exercised by Odoo env
            _logger.exception(
                "Prodboard asset import failed for archetype %s",
                archetype.display_name,
            )
            self._write_asset_failure(archetype, "failed", str(exc))
            return False

    @api.model
    def _read_offline_asset(self, archetype, offline_dir):
        if not offline_dir or not os.path.isdir(offline_dir):
            return None
        candidates = []
        if archetype.image_filename:
            candidates.append(os.path.basename(archetype.image_filename))
            ext = os.path.splitext(archetype.image_filename)[1]
            if ext:
                candidates.append(archetype.image_uuid + ext)
        candidates.extend([
            archetype.image_uuid + ".png",
            archetype.image_uuid + ".jpg",
            archetype.image_uuid + ".jpeg",
            archetype.image_uuid + ".webp",
            archetype.image_uuid,
        ])
        seen = set()
        for name in candidates:
            if not name or name in seen:
                continue
            seen.add(name)
            path = os.path.join(offline_dir, name)
            if not os.path.isfile(path):
                continue
            with open(path, "rb") as fh:
                content = fh.read()
            return (
                content,
                self._guess_mimetype(path, content),
            )
        return None

    @api.model
    def _fetch_url(self, url):
        request = Request(
            url,
            headers={"User-Agent": "Southbrook-Odoo-Prodboard-Importer/1.0"},
        )
        with urlopen(request, timeout=20) as response:
            content = response.read()
            mimetype = response.headers.get_content_type() or None
        return (content, mimetype)

    @api.model
    def _normalise_payload(self, payload, filename=None):
        if isinstance(payload, tuple):
            content, mimetype = payload
        else:
            content, mimetype = payload, None
        if isinstance(content, str):
            content = content.encode("utf-8")
        mimetype = mimetype or self._guess_mimetype(filename, content)
        return (content, mimetype)

    @api.model
    def _guess_mimetype(self, filename=None, content=None):
        if content and content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if content and content.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if content and content.startswith(b"RIFF") and b"WEBP" in content[:16]:
            return "image/webp"
        guessed = mimetypes.guess_type(filename or "")[0]
        return guessed or "application/octet-stream"

    @api.model
    def _upsert_attachment(self, archetype, content, mimetype):
        Attachment = self.env["ir.attachment"].sudo()
        attachment = archetype.prodboard_asset_attachment_id.sudo()
        if not attachment:
            attachment = Attachment.search([
                ("res_model", "=", "southbrook.cabinet.archetype"),
                ("res_id", "=", archetype.id),
                ("name", "=", archetype.image_filename or archetype.code),
            ], limit=1)
        vals = {
            "name": archetype.image_filename or archetype.code,
            "type": "binary",
            "datas": base64.b64encode(content).decode("ascii"),
            "mimetype": mimetype,
            "res_model": "southbrook.cabinet.archetype",
            "res_id": archetype.id,
            "public": False,
        }
        if attachment:
            attachment.write(vals)
        else:
            attachment = Attachment.create(vals)
        return attachment

    @api.model
    def _write_asset_failure(self, archetype, status, error):
        archetype.write({
            "prodboard_asset_status": status,
            "prodboard_asset_error": error,
            "prodboard_asset_imported_at": False,
        })
