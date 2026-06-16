# SPDX-License-Identifier: LGPL-3.0-only
import markdown

from odoo import _, api, fields, models


class OsSection(models.Model):
    _name = "southbrook.os.section"
    _description = "Southbrook OS — Canonical or Generated Section"
    _order = "slug"

    slug = fields.Char(required=True, index=True)
    name = fields.Char(required=True, translate=True)
    source = fields.Selection(
        [("canonical", "Canonical (hand-curated)"),
         ("generated", "Generated (from Odoo)")],
        required=True,
    )
    body = fields.Text(required=True)
    body_html = fields.Html(compute="_compute_body_html", sanitize=False, store=True)
    version = fields.Integer(default=1, required=True)
    last_updated_at = fields.Datetime(default=fields.Datetime.now)
    last_updated_by = fields.Many2one("res.users", default=lambda self: self.env.user)
    audience_tags = fields.Char(help="Comma-separated audience hints from frontmatter.")

    _slug_uniq = models.Constraint("UNIQUE(slug)", "Section slug must be unique.")

    @api.depends("body")
    def _compute_body_html(self):
        for rec in self:
            rec.body_html = markdown.markdown(
                rec.body or "",
                extensions=["fenced_code", "tables", "toc"],
            )

    def bump_version(self, body=None):
        """Apply a new version of this section. Used by OSRO apply + generators."""
        self.ensure_one()
        vals = {
            "version": self.version + 1,
            "last_updated_at": fields.Datetime.now(),
            "last_updated_by": self.env.user.id,
        }
        if body is not None:
            vals["body"] = body
        self.write(vals)
