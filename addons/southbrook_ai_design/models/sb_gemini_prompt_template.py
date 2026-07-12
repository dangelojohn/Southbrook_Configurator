# SPDX-License-Identifier: LGPL-3.0-only
"""sb.gemini.prompt.template — versioned prompts stored as records."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SbGeminiPromptTemplate(models.Model):
    _name = "sb.gemini.prompt.template"
    _description = "Southbrook Gemini Prompt Template"
    _order = "code"

    code = fields.Char(
        required=True, index=True, copy=False,
        help="Stable identifier callers reference, e.g. 'default_v1'.",
    )
    body = fields.Text(required=True)
    active = fields.Boolean(default=True)
    model = fields.Char(default="gemini-2.5-pro")
    temperature = fields.Float(default=0.1, digits=(3, 2))
    top_k = fields.Integer(default=16)
    top_p = fields.Float(default=0.7, digits=(3, 2))
    max_output_tokens = fields.Integer(default=4096)
    version_note = fields.Char(
        help="Short changelog for this prompt rev.",
    )

    # Odoo 19: models.Constraint (legacy _sql_constraints silently no-op'd).
    _code_uniq = models.Constraint(
        'unique(code)', "Prompt template code must be unique.",
    )

    @api.model
    def get_by_code(self, code: str):
        """Return the active prompt template with the given code, or raise
        UserError if none is active."""
        template = self.search([
            ("code", "=", code), ("active", "=", True),
        ], limit=1)
        if not template:
            # UserError (not ValueError) so a missing/inactive template surfaces
            # as a clean message on the analyze() path, not an opaque 500.
            raise UserError(_(
                "No active Gemini prompt template with code '%s'. Insert one "
                "or activate an existing record."
            ) % code)
        return template

    def to_generation_config(self) -> dict:
        self.ensure_one()
        return {
            "temperature": self.temperature,
            "topK": self.top_k,
            "topP": self.top_p,
            "maxOutputTokens": self.max_output_tokens,
            "responseMimeType": "application/json",
        }
