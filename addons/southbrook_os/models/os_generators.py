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
    # Attributes
    # ------------------------------------------------------------------
    @api.model
    def generate_attributes(self):
        body = self._render_attributes_md()
        return self._upsert_generated(
            "03_attributes.generated", "Attributes (live)", body)

    def _render_attributes_md(self):
        Attr = self.env["product.attribute"]
        attrs = Attr.search([], order="sequence, name")
        lines = [
            "---",
            "slug: 03_attributes.generated",
            "title: Attributes (live)",
            "source: generated",
            "---",
            "",
            "# Attributes (live)",
            "",
            "Rebuilt from `product.attribute` and `product.attribute.value`.",
            "",
        ]
        for a in attrs:
            lines.append(f"## {a.name}")
            lines.append("")
            for v in a.value_ids.sorted("sequence"):
                lines.append(f"- {v.name}")
            lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Cut Specification
    # ------------------------------------------------------------------
    @api.model
    def generate_cut_spec(self):
        body = self._render_cut_spec_md()
        return self._upsert_generated(
            "06_cut_spec.generated", "Cut Specification (active)", body)

    def _render_cut_spec_md(self):
        CutSpec = self.env.get("southbrook.cut.spec")
        if CutSpec is None:
            # southbrook_plm not installed yet — emit a stub
            body = (
                "---\nslug: 06_cut_spec.generated\n"
                "title: Cut Specification (active)\nsource: generated\n---\n\n"
                "# Cut Specification (active)\n\n"
                "*Cut spec source not available on this instance.*\n"
            )
            return body
        spec = CutSpec.search([("active", "=", True)], limit=1, order="id desc")
        if not spec:
            body = (
                "---\nslug: 06_cut_spec.generated\n"
                "title: Cut Specification (active)\nsource: generated\n---\n\n"
                "# Cut Specification (active)\n\n"
                "*No active cut spec defined.*\n"
            )
            return body
        # Render the active spec — field names match southbrook_plm's
        # CONSTANT_FIELDS tuple in addons/southbrook_plm/models/
        # southbrook_cut_spec.py (box_th, back_th, rabbet, door_th,
        # door_reveal, shelf_tol, shelf_vent_gap, toekick_h). Earlier
        # `*_mm`-suffixed names didn't exist on the model so getattr
        # returned None and every row was silently skipped.
        fields_to_emit = [
            ("box_th", "Box / Carcass Thickness", "mm"),
            ("back_th", "Back-Panel Thickness", "mm"),
            ("rabbet", "Rabbet Depth", "mm"),
            ("door_th", "Door Thickness", "mm"),
            ("door_reveal", "Door Reveal", "mm"),
            ("shelf_tol", "Shelf Tolerance", "mm"),
            ("shelf_vent_gap", "Shelf Ventilation Gap", "mm"),
            ("toekick_h", "Toe-Kick Height", "mm"),
        ]
        lines = [
            "---", "slug: 06_cut_spec.generated",
            "title: Cut Specification (active)", "source: generated", "---", "",
            f"# Cut Specification (active) — {spec.display_name}", "",
            "| Parameter | Value | Unit |", "|---|---|---|",
        ]
        for fname, label, unit in fields_to_emit:
            val = getattr(spec, fname, None)
            if val is not None:
                lines.append(f"| {label} | {val} | {unit} |")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Work Centers
    # ------------------------------------------------------------------
    @api.model
    def generate_work_centers(self):
        body = self._render_work_centers_md()
        return self._upsert_generated(
            "08_work_centers.generated", "Work Centers (live)", body)

    def _render_work_centers_md(self):
        WC = self.env["mrp.workcenter"]
        centers = WC.search([("active", "=", True)], order="sequence, name")
        lines = [
            "---", "slug: 08_work_centers.generated",
            "title: Work Centers (live)", "source: generated", "---", "",
            "# Work Centers (live)", "",
            "Rebuilt from `mrp.workcenter`.", "",
            "| Work Center | OEE Target | Capacity |", "|---|---|---|",
        ]
        for c in centers:
            oee = getattr(c, "oee_target", "—")
            capacity = getattr(c, "default_capacity", "—")
            lines.append(f"| {c.name} | {oee} | {capacity} |")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Generate all (convenience for the cron + manual button)
    # ------------------------------------------------------------------
    @api.model
    def generate_all(self):
        results = []
        for fn in ("generate_catalog", "generate_attributes",
                   "generate_cut_spec", "generate_work_centers"):
            results.append(getattr(self, fn)())
        return results

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
