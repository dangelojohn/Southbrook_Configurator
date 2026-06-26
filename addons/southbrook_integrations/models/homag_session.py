# SPDX-License-Identifier: LGPL-3.0-only
"""Homag iX CAM exchange session.

Q-8 of the SAMI PRD descope notes confirm a Homag iX rig is NOT physically
present at Southbrook; we ship a deterministic simulator counterparty so the
production-count feedback loop and BTL/MPR export envelope can be wired,
tested and demoed without a CNC. A real Homag iX bridge replaces
``action_simulate_homag_count`` with an HTTP/file-drop ingest later.

The simulator is intentionally seeded: deterministic given a ``simulator_seed``
so a smoke test can pin the count and a flaky-CNC scenario can be replayed
without random surprise. ``auto`` falls back to ``random`` for live demos.
"""
import hashlib
import json
import logging
import random

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SouthbrookIntegrationsHomagSession(models.Model):
    _name = "southbrook.integrations.homag_session"
    _description = "Homag iX CAM Exchange Session"
    _order = "create_date desc, id desc"
    _inherit = ["mail.thread"]

    name = fields.Char(
        required=True, copy=False, readonly=True, default=lambda s: _("New"),
        tracking=True,
    )
    production_id = fields.Many2one(
        "mrp.production",
        required=True,
        ondelete="restrict",
        tracking=True,
        help="Manufacturing order whose cabinet panels are routed to Homag.",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("sent_to_homag", "Sent to Homag"),
            ("cutting", "Cutting"),
            ("count_received", "Count Received"),
            ("completed", "Completed"),
            ("error", "Error"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    btl_export_payload = fields.Text(
        help="JSON envelope of the BTL-style panel/operation list that was "
             "(or would be) shipped to Homag iX.",
    )
    count_received = fields.Float(
        digits=(12, 2),
        help="Units actually cut as reported by Homag (simulated by default).",
    )
    scrap_qty = fields.Float(
        digits=(12, 2),
        help="Offcut/defect quantity reported back by Homag.",
    )
    expected_count = fields.Float(
        related="production_id.product_qty",
        store=True,
        readonly=True,
        digits=(12, 2),
    )
    discrepancy_pct = fields.Float(
        compute="_compute_discrepancy_pct",
        store=True,
        digits=(8, 2),
        string="Discrepancy (%)",
    )
    simulator_seed = fields.Char(
        default="auto",
        help="`auto` -> non-deterministic; any other string is hashed into a "
             "deterministic RNG seed (smoke-test pin / replay).",
    )
    error_message = fields.Char(copy=False)

    _name_uniq = models.Constraint(
        'UNIQUE(name)',
        "Homag session sequence numbers must be unique.",
    )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "southbrook.integrations.homag_session"
                ) or _("New")
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends("count_received", "expected_count")
    def _compute_discrepancy_pct(self):
        for rec in self:
            if rec.expected_count:
                rec.discrepancy_pct = (
                    (rec.count_received - rec.expected_count)
                    / rec.expected_count
                ) * 100.0
            else:
                rec.discrepancy_pct = 0.0

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_export_to_homag(self):
        """Materialise a BTL-style JSON envelope from the MO BOM + routing
        and transition to ``sent_to_homag``.

        The shape mirrors a real Homag iX BTL-XML drop in JSON form so the
        future hand-off only needs an XML serialiser, not a re-model.
        """
        for rec in self:
            mo = rec.production_id
            if not mo:
                raise UserError(_("No manufacturing order linked."))
            lines = []
            for move in mo.move_raw_ids:
                lines.append({
                    "sku": move.product_id.default_code or move.product_id.name,
                    "name": move.product_id.display_name,
                    "qty": move.product_uom_qty,
                    "uom": move.product_uom.name if move.product_uom else "",
                })
            envelope = {
                "schema": "southbrook.homag.btl.v1",
                "session": rec.name,
                "mo": mo.name,
                "product": mo.product_id.display_name,
                "qty": mo.product_qty,
                "lines": lines,
                "operations": [
                    {"op": "cut", "machine": "edgeband", "qty": len(lines)},
                ],
            }
            rec.btl_export_payload = json.dumps(envelope, indent=2)
            rec.state = "sent_to_homag"
            rec.message_post(body=_("BTL envelope generated, %s lines.")
                             % len(lines))
        return True

    def _seeded_rng(self):
        """Return a deterministic ``random.Random`` for replayable simulation."""
        self.ensure_one()
        seed = self.simulator_seed or "auto"
        if seed == "auto":
            return random.Random()
        # SHA-256 of the seed gives a stable integer regardless of Python
        # hash randomisation.
        digest = hashlib.sha256(seed.encode("utf-8")).digest()
        return random.Random(int.from_bytes(digest[:8], "big"))

    def action_simulate_homag_count(self, noise_pct=0.5):
        """Fake counterparty: stamp ``count_received`` and ``scrap_qty`` as
        if Homag had reported back; transition to ``count_received``.

        ``noise_pct`` is the +/- proportion of expected used as the random
        spread (default 0.5 = +/-50%, plenty for smoke). With a non-``auto``
        seed the same input always produces the same output.
        """
        for rec in self:
            if rec.state not in ("sent_to_homag", "cutting", "draft"):
                raise UserError(
                    _("Simulator can only run on a draft/sent/cutting session."))
            rng = rec._seeded_rng()
            expected = rec.expected_count or 0.0
            jitter = rng.uniform(-noise_pct, noise_pct)
            rec.count_received = max(0.0, expected * (1.0 + jitter * 0.1))
            # 2-5% scrap of expected.
            rec.scrap_qty = expected * rng.uniform(0.02, 0.05)
            rec.state = "count_received"
            rec.message_post(
                body=_("Simulated Homag report: count=%(c)s scrap=%(s)s")
                     % {"c": rec.count_received, "s": rec.scrap_qty})
        return True

    def action_post_to_mo(self):
        """Push the simulated/real count back into the MO and, if there is
        any scrap, drop a ``stock.scrap`` against the finished product.

        v1 keeps this small on purpose: post the count, post the scrap,
        flip to ``completed``. A real Homag adapter will gate state by
        the BTL job completion event, not by manual click.
        """
        Scrap = self.env["stock.scrap"]
        for rec in self:
            if rec.state != "count_received":
                raise UserError(
                    _("Can only post a session in 'count_received' state."))
            mo = rec.production_id
            if rec.count_received:
                mo.qty_producing = rec.count_received
            if rec.scrap_qty:
                Scrap.create({
                    "product_id": mo.product_id.id,
                    "product_uom_id": mo.product_uom_id.id,
                    "scrap_qty": rec.scrap_qty,
                    "production_id": mo.id,
                    "origin": rec.name,
                })
            rec.state = "completed"
            rec.message_post(body=_("Posted to MO %s.") % mo.name)
        return True
