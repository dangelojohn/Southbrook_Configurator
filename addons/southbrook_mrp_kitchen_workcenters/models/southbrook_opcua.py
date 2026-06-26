# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.opcua.* — OPC-UA gateway prototype (SAMI PRD #17 / IOT-02).

The factory's Homag iX cells expose state (running / idle / fault /
changeover) and counters (parts produced, cycle time, spindle hours)
over OPC-UA. The PRD asks for an Odoo-side connector that polls these
tags and drives mrp.workorder + mrp.workcenter state.

Per the production plan #17, this commit ships the **framework + stub
mode**, NOT a real OPC-UA polling client:

  - A Python OPC-UA library (asyncua / opcua-asyncio) would have to
    be added to the Odoo container Dockerfile + a pinned version
    locked. That dependency conversation belongs with John / IT.
  - We don't have a Homag iX in front of us — any client we wrote
    would be untested against the live security policy + node
    structure.

What this commit DOES ship:

  southbrook.opcua.endpoint    — connection record (URL, security,
                                  credentials, polling cadence)
  southbrook.opcua.tag.mapping — one row per OPC-UA node we care
                                  about; declares the target Odoo
                                  model + field + transformation
  southbrook.opcua.log         — append-only poll log (timestamp,
                                  endpoint, mapping, raw value,
                                  applied value, error)

  Plus a `action_simulate_poll` button on the endpoint form that
  walks every mapping, reads its `stub_value` field, runs the
  transformation, and writes the target — proving the wiring end-
  to-end without a real OPC-UA roundtrip.

PROD ACTIVATION (Phase 4):

  1. Add `asyncua==X.Y.Z` to services/odoo/Dockerfile
  2. Replace `_poll_endpoint_stub` with the real client using
     `from asyncua import Client`
  3. Endpoint.security_policy + credentials feed the Client config
  4. ir.cron entry replaces the manual button trigger

The model + mapping shape is the load-bearing part — once Phase 4
plugs the real polling in, no view / cron / data changes needed.
"""
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


SECURITY_POLICIES = [
    ("none", "None"),
    ("basic128rsa15", "Basic128Rsa15"),
    ("basic256", "Basic256"),
    ("basic256sha256", "Basic256Sha256"),
]


TARGET_MODELS = [
    ("mrp.workcenter", "mrp.workcenter"),
    ("mrp.workorder", "mrp.workorder"),
    ("southbrook.kitchen.workcenter.downtime",
     "southbrook.kitchen.workcenter.downtime"),
]


VALUE_TRANSFORMS = [
    ("identity", "Identity (pass through)"),
    ("bool_to_state", "Bool → state (true=ready, false=blocked)"),
    ("int_to_qty", "Int → qty (truncated)"),
    ("float_to_minutes", "Float seconds → minutes"),
    ("json_extract", "JSON extract (uses json_path)"),
]


POLL_STATES = [
    ("ok", "OK"),
    ("error", "Error"),
    ("skipped", "Skipped"),
]


class SouthbrookOpcuaEndpoint(models.Model):
    _name = "southbrook.opcua.endpoint"
    _description = "Southbrook OPC-UA Endpoint"
    _inherit = ["mail.thread", "southbrook.qr.mixin"]
    _order = "name"
    _qr_kind = "opcua"

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    workcenter_id = fields.Many2one(
        "mrp.workcenter",
        string="Default Workcenter",
        help="Workcenter most tags on this endpoint relate to. "
             "Per-mapping target may override.",
    )
    url = fields.Char(
        string="OPC-UA URL",
        required=True, tracking=True,
        help="e.g. opc.tcp://homag-cell-1.shop.local:4840",
    )
    security_policy = fields.Selection(
        SECURITY_POLICIES, default="none", required=True, tracking=True,
    )
    username = fields.Char(tracking=True)
    password = fields.Char(
        help="Stored in plaintext for the prototype. Production must "
             "swap to ir.config_parameter or an external secret store.",
    )
    polling_seconds = fields.Integer(
        default=30,
        help="Seconds between polls for the real client. Stub mode "
             "ignores this — manual button only.",
    )
    last_poll_at = fields.Datetime(readonly=True)
    mapping_ids = fields.One2many(
        "southbrook.opcua.tag.mapping",
        "endpoint_id", string="Tag Mappings",
    )
    log_ids = fields.One2many(
        "southbrook.opcua.log", "endpoint_id", string="Poll Log",
    )
    mapping_count = fields.Integer(
        compute="_compute_counts", store=False)
    log_count = fields.Integer(
        compute="_compute_counts", store=False)

    @api.depends("mapping_ids", "log_ids")
    def _compute_counts(self):
        for rec in self:
            rec.mapping_count = len(rec.mapping_ids)
            rec.log_count = len(rec.log_ids)

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------
    def action_simulate_poll(self):
        """Walk every mapping, read stub_value, apply transformation,
        write target field, log the result."""
        self.ensure_one()
        if not self.mapping_ids:
            raise UserError(_(
                "No tag mappings on this endpoint to simulate."))
        Log = self.env["southbrook.opcua.log"]
        applied = 0
        errored = 0
        for mapping in self.mapping_ids.filtered("active"):
            try:
                raw = mapping.stub_value
                transformed = mapping._apply_transform(raw)
                target = mapping._resolve_target()
                if target and mapping.target_field:
                    target.write({mapping.target_field: transformed})
                Log.create({
                    "endpoint_id": self.id,
                    "mapping_id": mapping.id,
                    "node_id": mapping.node_id,
                    "raw_value": str(raw),
                    "applied_value": str(transformed),
                    "state": "ok",
                })
                applied += 1
            except Exception as exc:  # noqa: BLE001
                Log.create({
                    "endpoint_id": self.id,
                    "mapping_id": mapping.id,
                    "node_id": mapping.node_id,
                    "raw_value": str(getattr(mapping, "stub_value", "")),
                    "applied_value": "",
                    "state": "error",
                    "error_message": str(exc)[:500],
                })
                errored += 1
        self.last_poll_at = fields.Datetime.now()
        self.message_post(
            body=_("Simulated poll: applied %(a)d, errored %(e)d "
                   "mapping(s).") % {"a": applied, "e": errored},
        )
        return True

    def _poll_endpoint_real(self):
        """Stub for the real OPC-UA client. Phase 4 replaces this
        with an asyncua-based implementation. Raises so calling
        code surfaces the gap clearly.
        """
        raise NotImplementedError(_(
            "Real OPC-UA polling not implemented in this stub. "
            "Phase 4: add `from asyncua import Client` + the polling "
            "loop, gated on the asyncua dependency being installed."))


class SouthbrookOpcuaTagMapping(models.Model):
    _name = "southbrook.opcua.tag.mapping"
    _description = "Southbrook OPC-UA Tag Mapping"
    _order = "endpoint_id, sequence, id"

    endpoint_id = fields.Many2one(
        "southbrook.opcua.endpoint",
        required=True, ondelete="cascade", index=True,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    name = fields.Char(required=True,
                       help="Descriptive label, e.g. 'CNC2 spindle state'")
    node_id = fields.Char(
        required=True,
        help="OPC-UA node identifier, e.g. 'ns=2;s=Channel1.Spindle.State'",
    )
    target_model = fields.Selection(
        TARGET_MODELS, required=True,
    )
    target_record_id = fields.Many2one(
        "ir.model.fields", string="Target Field (raw)",
        compute=False, store=False,
        help="Reserved for future field-picker UX. For now use "
             "target_field as a Char.",
    )
    target_field = fields.Char(
        required=True,
        help="Field name on the target model. Example: 'state' on "
             "mrp.workorder; 'reason' on the downtime model.",
    )
    target_workcenter_id = fields.Many2one(
        "mrp.workcenter",
        help="When target_model is mrp.workcenter, the specific cell "
             "this tag writes to. For mrp.workorder, the active WO at "
             "that workcenter is resolved at poll time.",
    )
    transform = fields.Selection(
        VALUE_TRANSFORMS, default="identity", required=True,
    )
    json_path = fields.Char(
        help="When transform='json_extract', dotted path into the "
             "value, e.g. 'spindle.rpm'.",
    )
    stub_value = fields.Char(
        help="The fake value action_simulate_poll reads instead of "
             "calling out to the real endpoint. Use for end-to-end "
             "wiring tests.",
    )
    last_applied_value = fields.Char(readonly=True)
    last_applied_at = fields.Datetime(readonly=True)

    def _apply_transform(self, raw):
        """Translate raw OPC-UA value into an Odoo-writable value."""
        self.ensure_one()
        if self.transform == "identity":
            return raw
        if self.transform == "bool_to_state":
            truthy = str(raw).strip().lower() in ("true", "1", "yes")
            return "ready" if truthy else "blocked"
        if self.transform == "int_to_qty":
            try:
                return int(float(str(raw)))
            except (TypeError, ValueError):
                return 0
        if self.transform == "float_to_minutes":
            try:
                return float(str(raw)) / 60.0
            except (TypeError, ValueError):
                return 0.0
        if self.transform == "json_extract":
            if not self.json_path:
                raise UserError(_(
                    "transform='json_extract' requires json_path."))
            try:
                doc = json.loads(str(raw))
            except json.JSONDecodeError as exc:
                raise UserError(_(
                    "Invalid JSON in raw value: %s") % exc)
            for key in self.json_path.split("."):
                if not isinstance(doc, dict) or key not in doc:
                    return None
                doc = doc[key]
            return doc
        return raw

    def _resolve_target(self):
        """Return the recordset to write transformed value into.
        Returns False when nothing resolves — caller logs an error."""
        self.ensure_one()
        Model = self.env[self.target_model]
        if self.target_model == "mrp.workcenter":
            wc = self.target_workcenter_id or self.endpoint_id.workcenter_id
            return wc or False
        if self.target_model == "mrp.workorder":
            wc = self.target_workcenter_id or self.endpoint_id.workcenter_id
            if not wc:
                return False
            return Model.search([
                ("workcenter_id", "=", wc.id),
                ("state", "in", ["ready", "progress", "pending"]),
            ], limit=1, order="date_start asc")
        if self.target_model == "southbrook.kitchen.workcenter.downtime":
            wc = self.target_workcenter_id or self.endpoint_id.workcenter_id
            if not wc:
                return False
            return Model.search([
                ("workcenter_id", "=", wc.id),
                ("state", "=", "active"),
            ], limit=1, order="date_start desc")
        return False


class SouthbrookOpcuaLog(models.Model):
    _name = "southbrook.opcua.log"
    _description = "Southbrook OPC-UA Poll Log"
    _order = "create_date desc, id desc"

    endpoint_id = fields.Many2one(
        "southbrook.opcua.endpoint",
        required=True, ondelete="cascade", index=True,
    )
    mapping_id = fields.Many2one(
        "southbrook.opcua.tag.mapping",
        ondelete="set null", index=True,
    )
    node_id = fields.Char(string="Node ID")
    raw_value = fields.Char(string="Raw")
    applied_value = fields.Char(string="Applied")
    state = fields.Selection(
        POLL_STATES, default="ok", required=True, index=True)
    error_message = fields.Char()
