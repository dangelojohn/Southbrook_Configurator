# SPDX-License-Identifier: LGPL-3.0-only
"""Module 5 tests — project lifecycle, design-option selection, AI
confirmation gate, approvals, and the DoD walk-through."""
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "kitchen_workspace")
class TestKitchenWorkspace(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Project = cls.env["sb.kitchen.project"]
        cls.DesignOption = cls.env["sb.kitchen.design.option"]
        cls.AiAnalysis = cls.env["sb.kitchen.ai.analysis"]
        cls.Appliance = cls.env["sb.kitchen.appliance"]
        cls.Approval = cls.env["sb.kitchen.approval"]
        cls.partner = cls.env["res.partner"].create({
            "name": "Test Customer", "is_company": False,
        })

    def _new_project(self, name="Test Kitchen", theme="signature"):
        return self.Project.create({
            "name": name,
            "partner_id": self.partner.id,
            "theme": theme,
        })

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def test_initial_state_is_draft(self):
        project = self._new_project()
        self.assertEqual(project.state, "draft")
        self.assertTrue(project.code, "code must be sequence-assigned at create")
        self.assertNotEqual(project.code, "New")

    def test_lifecycle_happy_path(self):
        project = self._new_project()
        project.action_start_designing()
        self.assertEqual(project.state, "designing")

        # Need at least one design option to submit to customer.
        self.DesignOption.create({
            "project_id": project.id, "name": "Option A",
        })
        project.action_submit_to_customer()
        self.assertEqual(project.state, "awaiting_customer")

        # Need a selected option to record approval.
        project.design_option_ids.write({"is_selected": True})
        project.action_customer_approves()
        self.assertEqual(project.state, "approved")

        project.action_release_to_production()
        self.assertEqual(project.state, "in_production")
        project.action_done()
        self.assertEqual(project.state, "done")
        self.assertTrue(project.date_completed)

    def test_invalid_state_transition_blocks(self):
        """draft → in_production isn't a valid hop; the state machine
        must reject it."""
        project = self._new_project()
        with self.assertRaises(UserError):
            project.action_set_state("in_production")

    def test_submit_without_options_blocks(self):
        project = self._new_project()
        project.action_start_designing()
        with self.assertRaises(UserError):
            project.action_submit_to_customer()

    def test_customer_approves_without_selection_blocks(self):
        project = self._new_project()
        project.action_start_designing()
        self.DesignOption.create({
            "project_id": project.id, "name": "Option A",
        })
        project.action_submit_to_customer()
        with self.assertRaises(UserError):
            project.action_customer_approves()

    def test_cancel_from_anywhere_works(self):
        for from_state, action_method in [
            ("draft", "action_cancel"),
            ("designing", "action_cancel"),
        ]:
            with self.subTest(from_state=from_state):
                project = self._new_project()
                if from_state == "designing":
                    project.action_start_designing()
                getattr(project, action_method)()
                self.assertEqual(project.state, "cancelled")

    # ------------------------------------------------------------------
    # Design-option one-of-N selection
    # ------------------------------------------------------------------
    def test_design_option_selection_clears_siblings(self):
        project = self._new_project()
        opt_a = self.DesignOption.create({
            "project_id": project.id, "name": "Option A",
        })
        opt_b = self.DesignOption.create({
            "project_id": project.id, "name": "Option B",
        })
        opt_c = self.DesignOption.create({
            "project_id": project.id, "name": "Option C",
        })

        opt_b.write({"is_selected": True})
        self.assertFalse(opt_a.is_selected)
        self.assertTrue(opt_b.is_selected)
        self.assertFalse(opt_c.is_selected)
        # Flip to C — B must clear.
        opt_c.write({"is_selected": True})
        self.assertFalse(opt_b.is_selected)
        self.assertTrue(opt_c.is_selected)
        # The computed selected_design_option_id follows.
        self.assertEqual(project.selected_design_option_id, opt_c)

    # ------------------------------------------------------------------
    # AI-analysis confirmation gate (init-doc GAP-02)
    # ------------------------------------------------------------------
    def test_is_ready_for_config_engine_requires_ai_confirmation(self):
        project = self._new_project()
        self.assertFalse(
            project.is_ready_for_config_engine(),
            "No analysis at all → not ready",
        )

        analysis = self.AiAnalysis.create({"project_id": project.id})
        project.ai_analysis_id = analysis
        self.assertFalse(
            project.is_ready_for_config_engine(),
            "Analysis unconfirmed → not ready",
        )

        analysis.action_confirm()
        self.assertTrue(
            project.is_ready_for_config_engine(),
            "Analysis confirmed + no unconfirmed appliances → ready",
        )

    def test_is_ready_for_config_engine_requires_appliance_confirmation(self):
        project = self._new_project()
        analysis = self.AiAnalysis.create({"project_id": project.id})
        project.ai_analysis_id = analysis
        analysis.action_confirm()

        # One unconfirmed appliance is enough to block.
        self.Appliance.create({
            "project_id": project.id,
            "name": "Stove",
            "appliance_type": "stove",
            "confirmed_by_human": False,
        })
        self.assertFalse(
            project.is_ready_for_config_engine(),
            "Unconfirmed appliance must block readiness",
        )

        project.appliance_ids.write({"confirmed_by_human": True})
        self.assertTrue(
            project.is_ready_for_config_engine(),
            "All appliances confirmed → ready",
        )

    def test_ai_analysis_confirm_stamps_user_and_time(self):
        project = self._new_project()
        analysis = self.AiAnalysis.create({"project_id": project.id})
        self.assertFalse(analysis.confirmed_by_user_id)
        analysis.action_confirm()
        self.assertEqual(analysis.confirmed_by_user_id, self.env.user)
        self.assertTrue(analysis.confirmed_at)

    # ------------------------------------------------------------------
    # Approvals
    # ------------------------------------------------------------------
    def test_approval_record_creation_and_decision(self):
        project = self._new_project()
        approval = self.Approval.create({
            "project_id": project.id,
            "approval_type": "concept",
            "approver_type": "customer",
        })
        self.assertEqual(approval.state, "pending")

        approval.action_approve()
        self.assertEqual(approval.state, "approved")
        self.assertEqual(approval.approver_id, self.env.user)
        self.assertTrue(approval.date_decided)

    def test_approval_double_decision_blocks(self):
        project = self._new_project()
        approval = self.Approval.create({
            "project_id": project.id,
            "approval_type": "design",
            "approver_type": "designer",
        })
        approval.action_approve()
        with self.assertRaises(UserError):
            approval.action_reject()

    # ------------------------------------------------------------------
    # DoD — designer creates a project, attaches photos, selects options
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Lifecycle email notifications
    # ------------------------------------------------------------------
    def test_concepts_ready_email_template_seeded(self):
        template = self.env.ref(
            "southbrook_kitchen_workspace.email_template_concepts_ready",
            raise_if_not_found=False,
        )
        self.assertTrue(template, "Concepts-ready email template must be seeded")
        self.assertEqual(template.model_id.model, "sb.kitchen.project")

    def test_design_approved_email_template_seeded(self):
        template = self.env.ref(
            "southbrook_kitchen_workspace.email_template_design_approved",
            raise_if_not_found=False,
        )
        self.assertTrue(template, "Design-approved email template must be seeded")
        self.assertEqual(template.model_id.model, "sb.kitchen.project")

    def test_submit_to_customer_queues_concepts_ready_email(self):
        project = self._new_project()
        project.action_start_designing()
        self.DesignOption.create({
            "project_id": project.id, "name": "Option A",
        })
        before = self.env["mail.mail"].search_count([])
        project.action_submit_to_customer()
        after = self.env["mail.mail"].search_count([])
        self.assertGreater(
            after, before,
            "action_submit_to_customer must queue an email",
        )

    def test_customer_approves_queues_design_approved_email(self):
        project = self._new_project()
        project.action_start_designing()
        self.DesignOption.create({
            "project_id": project.id, "name": "Option A",
            "is_selected": True,
        })
        project.action_submit_to_customer()
        before = self.env["mail.mail"].search_count([])
        project.action_customer_approves()
        after = self.env["mail.mail"].search_count([])
        self.assertGreater(
            after, before,
            "action_customer_approves must queue an email",
        )

    def test_released_to_production_email_template_seeded(self):
        template = self.env.ref(
            "southbrook_kitchen_workspace.email_template_released_to_production",
            raise_if_not_found=False,
        )
        self.assertTrue(
            template, "Released-to-production email template must be seeded")
        self.assertEqual(template.model_id.model, "sb.kitchen.project")

    def test_project_done_email_template_seeded(self):
        template = self.env.ref(
            "southbrook_kitchen_workspace.email_template_project_done",
            raise_if_not_found=False,
        )
        self.assertTrue(template, "Project-done email template must be seeded")
        self.assertEqual(template.model_id.model, "sb.kitchen.project")

    def test_release_to_production_queues_email(self):
        project = self._new_project()
        project.action_start_designing()
        self.DesignOption.create({
            "project_id": project.id, "name": "Option A",
            "is_selected": True,
        })
        project.action_submit_to_customer()
        project.action_customer_approves()
        before = self.env["mail.mail"].search_count([])
        project.action_release_to_production()
        after = self.env["mail.mail"].search_count([])
        self.assertGreater(
            after, before,
            "action_release_to_production must queue an email",
        )

    def test_action_done_queues_email(self):
        project = self._new_project()
        project.action_start_designing()
        self.DesignOption.create({
            "project_id": project.id, "name": "Option A",
            "is_selected": True,
        })
        project.action_submit_to_customer()
        project.action_customer_approves()
        project.action_release_to_production()
        before = self.env["mail.mail"].search_count([])
        project.action_done()
        after = self.env["mail.mail"].search_count([])
        self.assertGreater(
            after, before,
            "action_done must queue an email",
        )

    def test_action_cancel_queues_no_email(self):
        # Cancellation is out-of-band by design — chatter + operator phone
        # call, never an automated cold-cancel email.
        project = self._new_project()
        before = self.env["mail.mail"].search_count([])
        project.action_cancel()
        after = self.env["mail.mail"].search_count([])
        self.assertEqual(
            after, before,
            "action_cancel must NOT queue an email",
        )

    # ------------------------------------------------------------------
    # DoD — designer creates a project, attaches photos, selects options
    # ------------------------------------------------------------------
    def test_dod_create_attach_select(self):
        project = self._new_project(name="DoD walk-through", theme="signature")

        # Attach a "photo" (any ir.attachment scoped to the project).
        att = self.env["ir.attachment"].create({
            "name": "kitchen_photo.jpg",
            "res_model": "sb.kitchen.project",
            "res_id": project.id,
        })
        self.assertEqual(att.res_id, project.id)

        # Move into designing and create three options.
        project.action_start_designing()
        for letter in ("A", "B", "C"):
            self.DesignOption.create({
                "project_id": project.id, "name": f"Option {letter}",
                "estimated_price": 12000 + ord(letter) * 100,
            })
        self.assertEqual(len(project.design_option_ids), 3)

        # Select one.
        chosen = project.design_option_ids[1]
        chosen.write({"is_selected": True})
        self.assertEqual(project.selected_design_option_id, chosen)
