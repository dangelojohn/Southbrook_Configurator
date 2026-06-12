# SPDX-License-Identifier: LGPL-3.0-only
import json

from odoo import _, fields, models
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
        default=0,
        copy=False,
    )
    x_southbrook_readiness_state = fields.Selection(
        READINESS_STATES,
        string="MRP Readiness",
        default="at_risk",
        index=True,
        copy=False,
    )
    x_southbrook_blocking_gate = fields.Selection(
        [(key, label) for key, label in GATE_LABELS.items()],
        string="Blocking Gate",
        index=True,
        copy=False,
    )
    x_southbrook_blocker_summary = fields.Text(
        string="Blocker Summary",
        copy=False,
    )
    x_southbrook_next_action = fields.Text(
        string="Next Action",
        copy=False,
    )
    x_southbrook_gate_json = fields.Text(
        string="MRP Gate Detail",
        copy=False,
    )

    def action_southbrook_refresh_mrp_readiness_snapshot(self):
        for task in self:
            gates = task._southbrook_collect_readiness_gates()
            score, state, blocked_gate, summary, next_action = (
                task._southbrook_score_from_gates(gates)
            )
            task.write({
                "x_southbrook_readiness_score": score,
                "x_southbrook_readiness_state": state,
                "x_southbrook_blocking_gate": blocked_gate,
                "x_southbrook_blocker_summary": summary,
                "x_southbrook_next_action": next_action,
                "x_southbrook_gate_json": json.dumps(
                    task._southbrook_gate_rows(gates),
                    sort_keys=True,
                ),
            })
        return True

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

    def _southbrook_release_sale_order(self):
        self.ensure_one()
        return self.x_southbrook_sale_order_id

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

    def _southbrook_release_records(self, records, operation="write"):
        if not records:
            return records
        user_records = self.env[records._name].browse(records.ids).exists()
        user_records.check_access_rights(operation)
        user_records.check_access_rule(operation)
        return user_records

    def _southbrook_check_release_permissions(self, sale):
        sale.check_access_rights("read")
        sale.check_access_rule("read")
        sale.check_access_rights("write")
        sale.check_access_rule("write")
        Production = self.env["mrp.production"]
        Production.check_access_rights("create")
        Production.check_access_rights("write")

    def _southbrook_check_mi_recompute_permissions(self):
        Check = self.env["southbrook.mi.check"]
        for operation in ("read", "write", "create", "unlink"):
            Check.check_access_rights(operation)

    def _southbrook_notification_action(self, message=False):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Ready for Production"),
                "message": message or _(
                    "No production release action is available for this task."
                ),
                "type": "success",
                "sticky": False,
            },
        }

    def _southbrook_mo_action(self, productions):
        if isinstance(productions, dict):
            return self._southbrook_notification_action(_(
                "Production release completed, but no safe manufacturing "
                "order action is available."
            ))
        if not productions:
            return self._southbrook_notification_action()
        if productions._name != "mrp.production":
            return self._southbrook_notification_action(_(
                "Production release completed, but no safe manufacturing "
                "order action is available."
            ))
        productions = self._southbrook_release_records(productions, "read")
        if not productions:
            return self._southbrook_notification_action()
        action = {
            "type": "ir.actions.act_window",
            "name": _("Manufacturing Orders"),
            "res_model": "mrp.production",
        }
        if len(productions) == 1:
            action.update({
                "view_mode": "form",
                "res_id": productions.id,
            })
        else:
            action.update({
                "view_mode": "list,form",
                "domain": [("id", "in", productions.ids)],
            })
        return action

    def action_southbrook_recompute_mrp_readiness(self):
        for task in self:
            related_productions = task._southbrook_related_productions()
            productions = task._southbrook_release_records(related_productions)
            for production in productions:
                if hasattr(production, "action_recompute_manufacturing_intelligence"):
                    task._southbrook_check_mi_recompute_permissions()
                    production.action_recompute_manufacturing_intelligence()
            related_packages = task._southbrook_related_packages(related_productions)
            packages = task._southbrook_release_records(related_packages)
            for package in packages:
                if hasattr(package, "action_recompute_manufacturing_intelligence"):
                    task._southbrook_check_mi_recompute_permissions()
                    package.action_recompute_manufacturing_intelligence()
            related_workorders = task._southbrook_related_workorders(
                related_productions
            )
            workorders = task._southbrook_release_records(related_workorders)
            for workorder in workorders:
                if hasattr(workorder, "action_check_tool_readiness"):
                    workorder.action_check_tool_readiness()
        self.action_southbrook_refresh_mrp_readiness_snapshot()
        return True

    def action_southbrook_release_to_production(self):
        self.ensure_one()
        self.action_southbrook_recompute_mrp_readiness()
        if self.x_southbrook_readiness_state == "blocked":
            raise UserError(_(
                "Cannot release %(job)s. %(summary)s"
            ) % {
                "job": self.display_name,
                "summary": self.x_southbrook_blocker_summary,
            })
        sale = self._southbrook_release_sale_order()
        if sale and hasattr(sale, "action_send_to_production"):
            self._southbrook_check_release_permissions(sale)
            productions = sale.action_send_to_production()
            return self._southbrook_mo_action(productions)
        return self._southbrook_notification_action()

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
