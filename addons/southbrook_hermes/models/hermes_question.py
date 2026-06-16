# SPDX-License-Identifier: LGPL-3.0-only
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SouthbrookHermesQuestion(models.Model):
    _name = "southbrook.hermes.question"
    _description = "Fabio Question"
    _order = "create_date desc, id desc"

    question = fields.Text(required=True)
    answer = fields.Text(readonly=True)
    state = fields.Selection(
        [("draft", "Draft"), ("answered", "Answered")],
        default="draft",
        required=True,
        readonly=True,
    )
    scope = fields.Selection(
        [("internal", "Internal"), ("customer", "Customer")],
        default="internal",
        required=True,
    )
    asked_by_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        readonly=True,
        copy=False,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        help="Customer scope is limited to this partner's kitchen projects.",
    )
    project_id = fields.Many2one("sb.kitchen.project", string="Kitchen Project")
    recommendation_id = fields.Many2one(
        "southbrook.hermes.recommendation",
        readonly=True,
        copy=False,
    )

    def action_answer(self):
        for question in self:
            if question.scope == "customer":
                answer = question._answer_customer()
            else:
                answer = question._answer_internal()
            question.write({"answer": answer, "state": "answered"})
        return True

    def action_create_recommendation(self):
        for question in self:
            if not question.answer:
                question.action_answer()
            recommendation = self.env["southbrook.hermes.recommendation"].create({
                "name": _("Follow up: %s") % question._short_question(),
                "recommendation_type": "followup",
                "priority": "normal",
                "summary": question.answer,
                "proposed_action": _(
                    "Review Fabio's answer and decide the next human action."
                ),
                "payload_json": "{}",
                "source_model": question._name,
                "source_res_id": question.id,
                "agent_run_id": "fabio-ask-%s" % question.id,
                "model_provider": "odoo",
                "model_name": "fabio-ask-v1",
            })
            question.recommendation_id = recommendation.id
        return True

    @api.model
    def ask_customer(self, partner, question_text, project=None, user=None):
        if not partner:
            raise UserError(_("Customer questions require a partner."))
        values = {
            "question": question_text,
            "scope": "customer",
            "partner_id": partner.id,
            "asked_by_id": (user or self.env.user).id,
        }
        if project:
            if project.partner_id != partner:
                raise UserError(_(
                    "This kitchen project does not belong to the customer."
                ))
            values["project_id"] = project.id
        question = self.sudo().create(values)
        question.action_answer()
        return question

    def _answer_internal(self):
        self.ensure_one()
        text = (self.question or "").lower()
        if self._mentions_any(
            text, ("help", "what can", "what do you", "how do i")
        ):
            return self._answer_help()
        if self._mentions_any(
            text, ("user", "users", "role", "roles", "team", "who")
        ):
            return self._answer_users()
        if self._mentions_any(text, ("block", "blocked", "blocker", "stuck")):
            return self._answer_mi_checks("blocker")
        if self._mentions_any(text, ("warn", "warning", "risk", "issue")):
            return self._answer_mi_checks("warning")
        if self._mentions_any(
            text,
            ("production", "mo", "manufacturing", "shop", "status", "today"),
        ):
            return self._answer_production_summary()
        return "\n\n".join([
            self._answer_production_summary(),
            _(
                "Ask about blockers, warnings, production status, customer "
                "projects, or the Southbrook production users for a more "
                "specific answer."
            ),
        ])

    def _answer_customer(self):
        self.ensure_one()
        partner = self.partner_id
        if not partner:
            return _(
                "I need a customer account before I can answer customer "
                "project questions."
            )
        projects = self._customer_projects(partner)
        if self.project_id:
            projects = projects.filtered(
                lambda project: project.id == self.project_id.id
            )
        if not projects:
            return _(
                "I do not see any kitchen projects for %s yet."
            ) % partner.display_name

        text = (self.question or "").lower()
        if self._mentions_any(text, ("approval", "approve", "approved", "sign")):
            return self._answer_customer_approval(projects)
        if self._mentions_any(
            text, ("production", "manufacturing", "build", "shop")
        ):
            return self._answer_customer_production(projects)
        return self._answer_customer_status(projects)

    def _answer_help(self):
        return _(
            "Fabio can answer questions about production blockers, warnings, "
            "manufacturing status, customer project status, approvals, and "
            "the Southbrook production users. Fabio can also turn an answer "
            "into a draft recommendation for human review."
        )

    def _answer_users(self):
        known_roles = {
            "Alex Estimator": _("estimating and customer requirement review"),
            "Chris CNC": _("CNC and cutting work"),
            "Sam Assembler": _("cabinet assembly"),
            "Jordan Finisher": _("finishing work"),
            "Taylor Install": _("installation planning and closeout"),
            "Morgan Production": _("production management and shop coordination"),
            "ProductGraph MCP Bot": _("tool and product-graph automation"),
        }
        users = self.env["res.users"].sudo().search([
            ("share", "=", False),
            ("active", "=", True),
        ], order="id")
        lines = [_("Current internal users Fabio knows about:")]
        for user in users:
            role = known_roles.get(user.name, _("internal Odoo user"))
            lines.append("- %s: %s." % (user.name, role))
        return "\n".join(lines)

    def _answer_mi_checks(self, severity):
        if "southbrook.mi.check" not in self.env:
            return _(
                "Manufacturing intelligence checks aren't available on this "
                "instance."
            )
        label = dict(
            self.env["southbrook.mi.check"]._fields["severity"].selection
        ).get(severity, severity)
        checks = self.env["southbrook.mi.check"].sudo().search([
            ("active", "=", True),
            ("severity", "=", severity),
        ], limit=8)
        if not checks:
            return _(
                "I do not see active %s manufacturing intelligence checks."
            ) % label.lower()
        lines = [_("Active %s checks:") % label.lower()]
        for check in checks:
            target = (
                check.production_id.display_name
                or check.production_package_id.display_name
                or _("unlinked record")
            )
            action = check.recommendation or check.message
            lines.append("- %s: %s. Next action: %s" % (target, check.name, action))
        return "\n".join(lines)

    def _answer_production_summary(self):
        Production = self.env["mrp.production"].sudo()
        productions = Production.search([], limit=20, order="id desc")
        if "x_mi_status" in Production._fields:
            blocked = Production.search_count([("x_mi_status", "=", "blocked")])
            review = Production.search_count([("x_mi_status", "=", "review")])
        else:
            blocked = 0
            review = 0
        if not productions:
            return _("I do not see manufacturing orders yet.")
        lines = [
            _(
                "Production summary: %(total)s recent manufacturing orders. "
                "%(blocked)s blocked, %(review)s needing review."
            ) % {
                "total": len(productions),
                "blocked": blocked,
                "review": review,
            }
        ]
        for production in productions[:5]:
            next_action = (
                getattr(production, "x_mi_next_action", False)
                or _("No next action recorded.")
            )
            lines.append("- %s: %s" % (production.display_name, next_action))
        return "\n".join(lines)

    def _answer_customer_status(self, projects):
        labels = dict(self.env["sb.kitchen.project"]._fields["state"].selection)
        lines = [_("Here is what I found for your kitchen project:")]
        for project in projects[:5]:
            selected = (
                project.selected_design_option_id.name
                if project.selected_design_option_id
                else _("No design option selected yet")
            )
            target = project.date_target or _("No target date set")
            lines.append("- %s - %s. State: %s. Target: %s. Selected option: %s." % (
                project.code,
                project.name,
                labels.get(project.state, project.state),
                target,
                selected,
            ))
        return "\n".join(lines)

    def _answer_customer_approval(self, projects):
        labels = dict(self.env["sb.kitchen.project"]._fields["state"].selection)
        lines = []
        for project in projects[:5]:
            if project.state == "awaiting_customer":
                if project.selected_design_option_id:
                    lines.append(
                        _(
                            "%s is waiting for your final approval. "
                            "Selected option: %s."
                        ) % (
                            project.display_name,
                            project.selected_design_option_id.name,
                        )
                    )
                else:
                    lines.append(
                        _(
                            "%s is waiting for you to select a design option "
                            "before final approval."
                        ) % project.display_name
                    )
            else:
                lines.append(
                    _(
                        "%s is currently %s, so no customer approval action "
                        "is pending."
                    ) % (
                        project.display_name,
                        labels.get(project.state, project.state),
                    )
                )
        return "\n".join(lines)

    def _answer_customer_production(self, projects):
        sale_orders = projects.mapped("sale_order_id")
        Production = self.env["mrp.production"].sudo()
        productions = Production.browse()
        if sale_orders and "sale_id" in Production._fields:
            productions = Production.search(
                [("sale_id", "in", sale_orders.ids)], limit=8
            )
        if not productions:
            return self._answer_customer_status(projects)
        lines = [_("Production records linked to your project:")]
        for production in productions:
            next_action = (
                getattr(production, "x_mi_next_action", False)
                or _("No next action recorded.")
            )
            lines.append("- %s: %s" % (production.display_name, next_action))
        return "\n".join(lines)

    def _customer_projects(self, partner):
        return self.env["sb.kitchen.project"].sudo().search([
            ("partner_id", "=", partner.id),
        ], order="date_created desc, id desc")

    def _short_question(self):
        self.ensure_one()
        text = (self.question or "").strip()
        return text[:77] + "..." if len(text) > 80 else text

    @staticmethod
    def _mentions_any(text, needles):
        return any(needle in text for needle in needles)
