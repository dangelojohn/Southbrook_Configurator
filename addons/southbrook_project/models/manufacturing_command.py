# SPDX-License-Identifier: LGPL-3.0-only
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError


READINESS_STATES = [
    ("ready", "Ready"),
    ("at_risk", "At Risk"),
    ("blocked", "Blocked"),
]

GATE_STATES = [
    ("not_started", "Not Started"),
    ("ready", "Ready"),
    ("warning", "Warning"),
    ("blocked", "Blocked"),
    ("waived", "Waived"),
]

GATE_SEQUENCE = [
    "estimate",
    "engineering",
    "bom_cutlist",
    "purchasing",
    "materials",
    "tooling",
    "labor",
    "equipment",
    "schedule",
    "delivery",
    "install",
]

GATE_LABELS = {
    "estimate": "Estimate",
    "engineering": "Engineering",
    "bom_cutlist": "BOM / Cutlist",
    "purchasing": "Purchasing",
    "materials": "Materials",
    "tooling": "Tooling",
    "labor": "Labor",
    "equipment": "Equipment",
    "schedule": "Production Schedule",
    "delivery": "Delivery",
    "install": "Install",
}

GATE_WEIGHTS = {
    "estimate": 4,
    "engineering": 10,
    "bom_cutlist": 12,
    "purchasing": 9,
    "materials": 9,
    "tooling": 12,
    "labor": 10,
    "equipment": 10,
    "schedule": 12,
    "delivery": 6,
    "install": 6,
}


class ProjectTask(models.Model):
    _inherit = "project.task"

    x_southbrook_readiness_score = fields.Integer(
        string="MRP Readiness Score",
        compute="_compute_southbrook_mrp_readiness",
        store=False,
    )
    x_southbrook_readiness_state = fields.Selection(
        READINESS_STATES,
        string="MRP Readiness",
        compute="_compute_southbrook_mrp_readiness",
        store=False,
    )
    x_southbrook_blocking_gate = fields.Selection(
        [(key, label) for key, label in GATE_LABELS.items()],
        string="Blocking Gate",
        compute="_compute_southbrook_mrp_readiness",
        store=False,
    )
    x_southbrook_blocker_summary = fields.Text(
        string="Blocker Summary",
        compute="_compute_southbrook_mrp_readiness",
        store=False,
    )
    x_southbrook_next_action = fields.Text(
        string="Next Action",
        compute="_compute_southbrook_mrp_readiness",
        store=False,
    )
    x_southbrook_gate_json = fields.Text(
        string="MRP Gate Detail",
        compute="_compute_southbrook_mrp_readiness",
        store=False,
    )

    @api.depends(
        "x_southbrook_sale_order_id",
        "x_southbrook_sale_order_id.state",
    )
    def _compute_southbrook_mrp_readiness(self):
        for task in self:
            gates = task._southbrook_collect_readiness_gates()
            score, state, blocked_gate, summary, next_action = (
                task._southbrook_score_from_gates(gates)
            )
            task.x_southbrook_readiness_score = score
            task.x_southbrook_readiness_state = state
            task.x_southbrook_blocking_gate = blocked_gate
            task.x_southbrook_blocker_summary = summary
            task.x_southbrook_next_action = next_action
            task.x_southbrook_gate_json = json.dumps(
                task._southbrook_gate_rows(gates),
                sort_keys=True,
            )

    def _southbrook_default_gate(self, gate, state="ready", message=False,
                                 action=False, blocking=False):
        return {
            "gate": gate,
            "label": GATE_LABELS[gate],
            "state": state,
            "message": message or _("%s ready.") % GATE_LABELS[gate],
            "action": action or False,
            "blocking": bool(blocking),
        }

    def _southbrook_gate_rows(self, gates):
        rows = []
        for gate in GATE_SEQUENCE:
            value = dict(gates.get(gate) or self._southbrook_default_gate(gate))
            value.setdefault("gate", gate)
            value.setdefault("label", GATE_LABELS[gate])
            rows.append(value)
        return rows

    def _southbrook_score_from_gates(self, gates):
        rows = self._southbrook_gate_rows(gates)
        total_weight = sum(GATE_WEIGHTS.values())
        earned = 0
        blockers = []
        warnings = []
        for row in rows:
            gate = row["gate"]
            state = row.get("state") or "not_started"
            weight = GATE_WEIGHTS[gate]
            if state in ("ready", "waived"):
                earned += weight
            elif state == "warning":
                earned += int(weight * 0.5)
                warnings.append(row)
            elif state == "blocked":
                blockers.append(row)
        score = int(round((earned / float(total_weight)) * 100.0))
        if blockers:
            score = min(score, 69)
            first = blockers[0]
            summary = "; ".join(
                (row.get("message") or GATE_LABELS[row["gate"]])
                for row in blockers[:3]
            )
            return (
                score,
                "blocked",
                first["gate"],
                summary,
                first.get("action") or first.get("message") or False,
            )
        if warnings:
            score = min(score, 89)
            first = warnings[0]
            summary = "; ".join(
                (row.get("message") or GATE_LABELS[row["gate"]])
                for row in warnings[:3]
            )
            return (
                score,
                "at_risk",
                False,
                summary,
                first.get("action") or first.get("message") or False,
            )
        return score, "ready", False, _("All release gates are ready."), False

    def _southbrook_collect_readiness_gates(self):
        self.ensure_one()
        return {
            gate: self._southbrook_default_gate(gate)
            for gate in GATE_SEQUENCE
        }
