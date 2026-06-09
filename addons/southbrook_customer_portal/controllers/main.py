# SPDX-License-Identifier: LGPL-3.0-only
"""Customer-facing /my/kitchen-projects portal."""
import logging

from odoo import _, http
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request

_logger = logging.getLogger(__name__)


class KitchenPortal(http.Controller):

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------
    @http.route(
        ["/my/kitchen-projects"], type="http", auth="user",
        website=True, methods=["GET"],
    )
    def kitchen_projects_list(self, **kw):
        Project = request.env["sb.kitchen.project"]
        partner = request.env.user.partner_id
        projects = Project.sudo().search(
            [("partner_id", "=", partner.id)],
            order="date_created desc",
        )
        return request.render(
            "southbrook_customer_portal.portal_kitchen_projects_list",
            {"projects": projects, "page_name": "kitchen_projects"},
        )

    # ------------------------------------------------------------------
    # Detail (concept review)
    # ------------------------------------------------------------------
    @http.route(
        ["/my/kitchen-project/<int:project_id>"], type="http", auth="user",
        website=True, methods=["GET"],
    )
    def kitchen_project_detail(self, project_id, **kw):
        project = self._fetch_project_for_user(project_id)
        return request.render(
            "southbrook_customer_portal.portal_kitchen_project_detail",
            {
                "project": project,
                "options": project.design_option_ids,
                "page_name": "kitchen_project",
            },
        )

    # ------------------------------------------------------------------
    # Select option (POST)
    # ------------------------------------------------------------------
    @http.route(
        ["/my/kitchen-project/<int:project_id>/select/<int:option_id>"],
        type="http", auth="user", website=True, methods=["POST"], csrf=True,
    )
    def kitchen_project_select_option(self, project_id, option_id, **kw):
        project = self._fetch_project_for_user(project_id)
        option = project.design_option_ids.filtered(lambda o: o.id == option_id)
        if not option:
            raise MissingError(_("Design option does not belong to this project."))
        option.sudo().write({"is_selected": True})
        return request.redirect(f"/my/kitchen-project/{project_id}")

    # ------------------------------------------------------------------
    # Approve (POST)
    # ------------------------------------------------------------------
    @http.route(
        ["/my/kitchen-project/<int:project_id>/approve"],
        type="http", auth="user", website=True, methods=["POST"], csrf=True,
    )
    def kitchen_project_approve(self, project_id, **kw):
        project = self._fetch_project_for_user(project_id)
        if not project.selected_design_option_id:
            raise UserError(_(
                "Pick a design option first, then approve."
            ))
        if project.state != "awaiting_customer":
            raise UserError(_(
                "Project state is %s; cannot record customer approval."
            ) % project.state)
        # Create an approval record + advance state.
        request.env["sb.kitchen.approval"].sudo().create({
            "project_id": project.id,
            "approval_type": "design",
            "approver_id": request.env.user.id,
            "approver_type": "customer",
            "state": "approved",
            "date_decided": http.fields.Datetime.now() if hasattr(http, "fields") else None,
        })
        project.sudo().action_customer_approves()
        return request.redirect(f"/my/kitchen-project/{project_id}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _fetch_project_for_user(self, project_id):
        """Return the project IFF the current portal user owns it.
        Raises MissingError on either no-such-project or wrong-customer
        (we deliberately give the same response to avoid leaking
        existence of other customers' projects)."""
        Project = request.env["sb.kitchen.project"].sudo()
        project = Project.browse(project_id).exists()
        if not project:
            raise MissingError(_("Project not found."))
        partner = request.env.user.partner_id
        if project.partner_id != partner:
            _logger.warning(
                "Portal ACL: user %s (partner %s) attempted to access "
                "project %s owned by partner %s — denied.",
                request.env.user.id, partner.id, project.id,
                project.partner_id.id,
            )
            raise MissingError(_("Project not found."))
        return project
