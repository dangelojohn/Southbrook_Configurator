# SPDX-License-Identifier: LGPL-3.0-only
import json

from odoo import _, api, fields, models


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
GATE_STATE_KEYS = {key for key, _label in GATE_STATES}

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
        gates = gates or {}
        rows = []
        for gate in GATE_SEQUENCE:
            explicit = gate in gates
            supplied = dict(gates.get(gate) or {})
            value = self._southbrook_default_gate(gate)
            value.update(supplied)
            value["gate"] = gate
            value["label"] = GATE_LABELS[gate]
            if explicit and not supplied.get("state"):
                value["state"] = "not_started"
            elif not value.get("state"):
                value["state"] = "ready"
            if value["state"] not in GATE_STATE_KEYS:
                state = value["state"]
                message = _("Unknown gate state '%s' for %s.") % (
                    state,
                    GATE_LABELS[gate],
                )
                value["state"] = "warning"
                value["message"] = message
                value["action"] = value.get("action") or message
            value["message"] = (
                value.get("message") or _("%s ready.") % GATE_LABELS[gate]
            )
            value["action"] = value.get("action") or False
            value["blocking"] = bool(value.get("blocking"))
            rows.append({
                "gate": value["gate"],
                "label": value["label"],
                "state": value["state"],
                "message": value["message"],
                "action": value["action"],
                "blocking": value["blocking"],
            })
        return rows

    def _southbrook_score_from_gates(self, gates):
        rows = self._southbrook_gate_rows(gates)
        total_weight = sum(GATE_WEIGHTS.values())
        earned = 0
        blockers = []
        risks = []
        for row in rows:
            gate = row["gate"]
            state = row.get("state") or "not_started"
            weight = GATE_WEIGHTS[gate]
            if state in ("ready", "waived"):
                earned += weight
            elif state == "warning":
                earned += int(weight * 0.5)
                risks.append(row)
            elif state == "blocked":
                blockers.append(row)
            else:
                risks.append(row)
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
        if risks:
            score = min(score, 89)
            first = risks[0]
            summary = "; ".join(
                (row.get("message") or GATE_LABELS[row["gate"]])
                for row in risks[:3]
            )
            return (
                score,
                "at_risk",
                False,
                summary,
                first.get("action") or first.get("message") or False,
            )
        return score, "ready", False, _("All release gates are ready."), False

    def _southbrook_related_sale_order(self):
        self.ensure_one()
        return self.x_southbrook_sale_order_id.sudo()

    def _southbrook_related_company(self, sale=False):
        self.ensure_one()
        company = False
        if sale and "company_id" in sale._fields:
            company = sale.company_id
        if not company and "company_id" in self._fields:
            company = self.company_id
        if (
            not company
            and self.project_id
            and "company_id" in self.project_id._fields
        ):
            company = self.project_id.company_id
        return company or self.env.company

    def _southbrook_related_productions(self):
        self.ensure_one()
        sale = self._southbrook_related_sale_order()
        Production = self.env["mrp.production"].sudo()
        if sale:
            domain = [("origin", "=", sale.name)]
        else:
            domain = [("origin", "=", self.name)]
        company = self._southbrook_related_company(sale)
        if company and "company_id" in Production._fields:
            domain.append(("company_id", "=", company.id))
        return Production.search(domain)

    def _southbrook_related_packages(self, productions=False):
        productions = productions or self._southbrook_related_productions()
        if not productions:
            return self.env["sb.production.package"]
        return self.env["sb.production.package"].sudo().search([
            ("mo_id", "in", productions.ids),
        ])

    def _southbrook_related_workorders(self, productions=False):
        productions = productions or self._southbrook_related_productions()
        if not productions:
            return self.env["mrp.workorder"]
        return productions.mapped("workorder_ids")

    def _southbrook_related_mi_checks(self, productions=False, packages=False):
        Check = self.env["southbrook.mi.check"].sudo()
        domains = []
        if productions:
            domains.append(("production_id", "in", productions.ids))
        if packages:
            domains.append(("production_package_id", "in", packages.ids))
        if not domains:
            return Check
        if len(domains) == 1:
            checks = Check.search([domains[0]])
        else:
            checks = Check.search(["|", domains[0], domains[1]])
        if "is_gate" in Check._fields:
            checks = checks.filtered(lambda check: check.is_gate)
        return checks

    def _southbrook_gate_from_checks(self, gate, checks, fallback_ready):
        blockers = checks.filtered(lambda check: check.severity == "blocker")
        warnings = checks.filtered(lambda check: check.severity == "warning")
        if blockers:
            first = blockers.sorted(key=lambda c: (c.sequence or 100, c.id))[0]
            return self._southbrook_default_gate(
                gate,
                state="blocked",
                message=first.message or first.name,
                action=first.recommendation or first.message,
                blocking=True,
            )
        if warnings:
            first = warnings.sorted(key=lambda c: (c.sequence or 100, c.id))[0]
            return self._southbrook_default_gate(
                gate,
                state="warning",
                message=first.message or first.name,
                action=first.recommendation or first.message,
                blocking=False,
            )
        return fallback_ready

    def _southbrook_collect_readiness_gates(self):
        self.ensure_one()
        gates = {
            gate: self._southbrook_default_gate(gate)
            for gate in GATE_SEQUENCE
        }
        sale = self._southbrook_related_sale_order()
        productions = self._southbrook_related_productions()
        packages = self._southbrook_related_packages(productions)
        workorders = self._southbrook_related_workorders(productions)
        checks = self._southbrook_related_mi_checks(productions, packages)

        if not sale:
            gates["estimate"] = self._southbrook_default_gate(
                "estimate",
                state="warning",
                message=_("No originating quote or sales order is linked."),
                action=_("Link the project task to its originating sales order."),
            )
        elif sale.state not in ("sale", "done"):
            gates["estimate"] = self._southbrook_default_gate(
                "estimate",
                state="blocked",
                message=_("Sales order is not confirmed."),
                action=_("Confirm the sales order before release."),
                blocking=True,
            )

        if not productions:
            gates["schedule"] = self._southbrook_default_gate(
                "schedule",
                state="warning",
                message=_("No manufacturing orders exist for this job yet."),
                action=_("Release the job to create manufacturing orders."),
            )
        elif not packages:
            gates["bom_cutlist"] = self._southbrook_default_gate(
                "bom_cutlist",
                state="blocked",
                message=_(
                    "No production package is linked to the manufacturing order."
                ),
                action=_("Create or recompute the production package and cutlist."),
                blocking=True,
            )
        else:
            packaged_production_ids = set(packages.mapped("mo_id").ids)
            missing_package_productions = productions.filtered(
                lambda production: production.id not in packaged_production_ids
            )
            if missing_package_productions:
                gates["bom_cutlist"] = self._southbrook_default_gate(
                    "bom_cutlist",
                    state="blocked",
                    message=_(
                        "No production package is linked to one or more "
                        "manufacturing orders."
                    ),
                    action=_("Create or recompute the production package and cutlist."),
                    blocking=True,
                )
            package_blockers = packages.filtered(
                lambda package: package.x_mi_status == "blocked"
            )
            if not missing_package_productions and package_blockers:
                first = package_blockers[0]
                gates["bom_cutlist"] = self._southbrook_default_gate(
                    "bom_cutlist",
                    state="blocked",
                    message=first.x_mi_next_stage_action
                    or first.x_mi_next_action
                    or _("Production package has blockers."),
                    action=first.x_mi_next_stage_action
                    or first.x_mi_next_action
                    or _("Open the production package intelligence checks."),
                    blocking=True,
                )

        tooling_blockers = workorders.filtered(
            lambda wo: getattr(wo, "southbrook_tool_readiness_state", False)
            == "blocked"
        )
        tooling_warnings = workorders.filtered(
            lambda wo: getattr(wo, "southbrook_tool_readiness_state", False)
            == "warning"
        )
        if tooling_blockers:
            first = tooling_blockers[0]
            gates["tooling"] = self._southbrook_default_gate(
                "tooling",
                state="blocked",
                message=first.southbrook_tool_readiness_msg
                or _("A work order is blocked by missing tooling."),
                action=_("Clear mandatory tool readiness before release."),
                blocking=True,
            )
        elif tooling_warnings:
            first = tooling_warnings[0]
            gates["tooling"] = self._southbrook_default_gate(
                "tooling",
                state="warning",
                message=first.southbrook_tool_readiness_msg
                or _("A work order has tooling warnings."),
                action=_("Review optional tooling before release."),
            )

        equipment_checks = checks.filtered(lambda check: check.stage in (
            "cnc", "edgeband", "assembly", "finish_qc"
        ) and check.category in ("production", "assembly"))
        gates["equipment"] = self._southbrook_gate_from_checks(
            "equipment", equipment_checks, gates["equipment"]
        )

        install_checks = checks.filtered(lambda check: check.stage == "install")
        gates["install"] = self._southbrook_gate_from_checks(
            "install", install_checks, gates["install"]
        )

        if workorders and any(not wo.date_start for wo in workorders):
            gates["schedule"] = self._southbrook_default_gate(
                "schedule",
                state="warning",
                message=_("One or more work orders are not scheduled."),
                action=_("Plan work orders before the daily production meeting."),
            )

        return gates
