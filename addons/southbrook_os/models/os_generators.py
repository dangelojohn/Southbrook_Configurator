# SPDX-License-Identifier: LGPL-3.0-only
import hashlib

from odoo import api, fields, models


class OsGenerators(models.AbstractModel):
    _name = "southbrook.os.generators"
    _description = "Generators that mirror live Odoo state into OS sections."

    # ------------------------------------------------------------------
    # Catalog
    # ------------------------------------------------------------------
    @api.model
    def generate_catalog(self):
        body = self._render_catalog_md()
        return self._upsert_generated("02_catalog.generated", "Catalog (live)", body)

    def _render_catalog_md(self):
        Template = self.env["product.template"]
        templates = Template.search([
            ("active", "=", True),
            ("default_code", "like", "SB-%"),
        ], order="default_code")
        lines = [
            "---",
            "slug: 02_catalog.generated",
            "title: Catalog (live)",
            "source: generated",
            "---",
            "",
            "# Catalog (live)",
            "",
            "Rebuilt from `product.template` records on Odoo. The live SKU list, "
            "current variant counts, and any retired templates appear here.",
            "",
            f"Total active SB-* templates: **{len(templates)}**",
            "",
            "| SKU | Name | Variants |",
            "|---|---|---|",
        ]
        for t in templates:
            variant_count = len(t.product_variant_ids)
            lines.append(f"| `{t.default_code}` | {t.name} | {variant_count} |")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Shared upsert with hash-based no-op detection
    # ------------------------------------------------------------------
    def _upsert_generated(self, slug, name, body):
        body_hash = hashlib.sha256(body.encode()).hexdigest()
        Section = self.env["southbrook.os.section"]
        section = Section.search([("slug", "=", slug)], limit=1)
        if section:
            existing_hash = hashlib.sha256(
                (section.body or "").encode()).hexdigest()
            if existing_hash == body_hash:
                return {"status": "ok", "slug": slug, "changed": False,
                        "new_version": section.version}
            section.bump_version(body=body)
            return {"status": "ok", "slug": slug, "changed": True,
                    "new_version": section.version}
        section = Section.create({
            "slug": slug, "name": name, "source": "generated", "body": body,
        })
        return {"status": "ok", "slug": slug, "changed": True,
                "new_version": section.version}
