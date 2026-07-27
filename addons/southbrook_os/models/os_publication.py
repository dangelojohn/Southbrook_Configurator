# SPDX-License-Identifier: LGPL-3.0-only
import hashlib

from odoo import api, fields, models


class OsPublication(models.Model):
    _name = "southbrook.os.publication"
    _description = "Southbrook OS — Dated Publication Snapshot"
    _order = "calendar_key desc, build_hash"

    calendar_key = fields.Char(required=True, index=True,
        help="Calendar tag like '2026-06'.")
    build_hash = fields.Char(required=True, index=True,
        help="SHA-256 of concatenated (slug, version) tuples — content fingerprint.")
    built_at = fields.Datetime(default=fields.Datetime.now)
    section_snapshot_ids = fields.One2many(
        "southbrook.os.publication.section", "publication_id")

    _key_hash_uniq = models.Constraint(
        "UNIQUE(calendar_key, build_hash)",
        "A publication with this (calendar_key, build_hash) already exists.",
    )

    @api.model
    def publish(self, calendar_key):
        """Build (or reuse) a publication for the current section state."""
        sections = self.env["southbrook.os.section"].search([], order="slug")
        fingerprint = "|".join(f"{s.slug}@{s.version}" for s in sections)
        build_hash = hashlib.sha256(fingerprint.encode()).hexdigest()[:16]
        existing = self.search([
            ("calendar_key", "=", calendar_key),
            ("build_hash", "=", build_hash),
        ], limit=1)
        if existing:
            return existing
        pub = self.create({"calendar_key": calendar_key, "build_hash": build_hash})
        SnapModel = self.env["southbrook.os.publication.section"]
        for s in sections:
            SnapModel.create({
                "publication_id": pub.id,
                "slug": s.slug,
                "name": s.name,
                "body": s.body,
                "section_version": s.version,
                "source": s.source,
            })
        return pub


class OsPublicationSection(models.Model):
    _name = "southbrook.os.publication.section"
    _description = "Southbrook OS — Frozen Section in a Publication"
    _order = "slug"

    publication_id = fields.Many2one(
        "southbrook.os.publication", required=True, ondelete="cascade",
        index=True)
    slug = fields.Char(required=True)
    name = fields.Char(required=True)
    body = fields.Text(required=True)
    section_version = fields.Integer(required=True)
    source = fields.Selection(
        [("canonical", "Canonical"), ("generated", "Generated")], required=True)
