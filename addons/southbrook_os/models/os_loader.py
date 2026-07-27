# SPDX-License-Identifier: LGPL-3.0-only
import os
import re

import yaml

from odoo import api, models

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


class OsLoader(models.AbstractModel):
    _name = "southbrook.os.loader"
    _description = "Loads canonical/*.md files into southbrook.os.section."

    @api.model
    def load_canonical_directory(self, directory_path):
        """Idempotently load every *.md in `directory_path` into a section."""
        Section = self.env["southbrook.os.section"]
        loaded = []
        for fname in sorted(os.listdir(directory_path)):
            if not fname.endswith(".md") or fname.startswith("."):
                continue
            slug = fname[:-3]
            path = os.path.join(directory_path, fname)
            with open(path, encoding="utf-8") as f:
                raw = f.read()
            meta, body = self._split_frontmatter(raw)
            vals = {
                "slug": slug,
                "name": meta.get("title", slug),
                "source": meta.get("source", "canonical"),
                "body": body,
                "audience_tags": ",".join(meta.get("audience") or []),
            }
            existing = Section.search([("slug", "=", slug)], limit=1)
            if existing:
                # Refresh ALL frontmatter-derived fields (not just body/name) so
                # an audience:/source: change in a canonical .md actually
                # propagates on -u. Bump the version only when the body really
                # changed, mirroring os_generators._upsert_generated — consumers
                # key revisions off `version`.
                changed = (existing.body or "") != (body or "")
                existing.write({
                    "body": body,
                    "name": vals["name"],
                    "source": vals["source"],
                    "audience_tags": vals["audience_tags"],
                })
                if changed:
                    existing.bump_version()
                loaded.append(existing)
            else:
                loaded.append(Section.create(vals))
        return loaded

    def _split_frontmatter(self, raw):
        match = _FRONTMATTER_RE.match(raw)
        if not match:
            return {}, raw
        try:
            meta = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            meta = {}
        return meta, match.group(2)
