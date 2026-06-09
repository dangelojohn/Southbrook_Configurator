# SPDX-License-Identifier: LGPL-3.0-only
"""sb.gemini.prompt.template — versioned prompts stored as records."""
from odoo import _, api, fields, models


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

    _sql_constraints = [
        ("code_uniq", "unique(code)", "Prompt template code must be unique."),
    ]

    @api.model
    def get_by_code(self, code: str):
        """Return the active prompt template with the given code, or raise
        UserError if none is active."""
        template = self.search([
            ("code", "=", code), ("active", "=", True),
        ], limit=1)
        if not template:
            raise ValueError(
                f"No active prompt template with code={code!r}. "
                f"Insert one or activate an existing record."
            )
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
