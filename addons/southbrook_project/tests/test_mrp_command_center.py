# SPDX-License-Identifier: LGPL-3.0-only
import json

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "mrp_command")
class TestMrpCommandCenter(TransactionCase):

    def _new_task(self, **vals):
        project = self.env["project.project"].create({
            "name": vals.pop("project_name", "MRP Command Test Project"),
        })
        defaults = {
            "name": "SO24091 Kitchen A",
            "project_id": project.id,
        }
        defaults.update(vals)
        return self.env["project.task"].create(defaults)

    def test_ready_task_scores_100(self):
        task = self._new_task()
        gates = {
            "estimate": {
                "state": "ready",
                "message": "Estimate approved",
                "action": False,
                "blocking": False,
            },
            "engineering": {
                "state": "ready",
                "message": "Drawings approved",
                "action": False,
                "blocking": False,
            },
            "bom_cutlist": {
                "state": "ready",
                "message": "BOM and cutlist ready",
                "action": False,
                "blocking": False,
            },
            "purchasing": {
                "state": "ready",
                "message": "Purchasing ready",
                "action": False,
                "blocking": False,
            },
            "materials": {
                "state": "ready",
                "message": "Materials ready",
                "action": False,
                "blocking": False,
            },
            "tooling": {
                "state": "ready",
                "message": "Tooling ready",
                "action": False,
                "blocking": False,
            },
            "labor": {
                "state": "ready",
                "message": "Labor assigned",
                "action": False,
                "blocking": False,
            },
            "equipment": {
                "state": "ready",
                "message": "Equipment ready",
                "action": False,
                "blocking": False,
            },
            "schedule": {
                "state": "ready",
                "message": "Schedule ready",
                "action": False,
                "blocking": False,
            },
            "delivery": {
                "state": "ready",
                "message": "Delivery not due",
                "action": False,
                "blocking": False,
            },
            "install": {
                "state": "ready",
                "message": "Install not due",
                "action": False,
                "blocking": False,
            },
        }
        score, state, blocked_gate, summary, next_action = (
            task._southbrook_score_from_gates(gates)
        )
        self.assertEqual(score, 100)
        self.assertEqual(state, "ready")
        self.assertFalse(blocked_gate)
        self.assertEqual(summary, "All release gates are ready.")
        self.assertFalse(next_action)

    def test_blocked_gate_caps_score_and_summary(self):
        task = self._new_task()
        gates = {
            "bom_cutlist": {
                "state": "blocked",
                "message": "BOM or cutlist missing",
                "action": "Generate the cutlist before release.",
                "blocking": True,
            },
            "tooling": {
                "state": "warning",
                "message": "Tooling has warnings",
                "action": "Review optional tooling.",
                "blocking": False,
            },
        }
        score, state, blocked_gate, summary, next_action = (
            task._southbrook_score_from_gates(gates)
        )
        self.assertLessEqual(score, 69)
        self.assertEqual(state, "blocked")
        self.assertEqual(blocked_gate, "bom_cutlist")
        self.assertIn("BOM or cutlist missing", summary)
        self.assertEqual(next_action, "Generate the cutlist before release.")

    def test_warning_gate_sets_at_risk_state(self):
        task = self._new_task()
        gates = {
            "tooling": {
                "state": "warning",
                "message": "Tooling has warnings",
                "action": "Review optional tooling.",
                "blocking": False,
            },
        }
        score, state, blocked_gate, summary, next_action = (
            task._southbrook_score_from_gates(gates)
        )
        self.assertLessEqual(score, 89)
        self.assertEqual(state, "at_risk")
        self.assertFalse(blocked_gate)
        self.assertIn("Tooling has warnings", summary)
        self.assertEqual(next_action, "Review optional tooling.")

    def test_not_started_gate_sets_at_risk_state(self):
        task = self._new_task()
        gates = {
            "engineering": {
                "state": "not_started",
                "message": "Engineering not started",
                "action": "Start engineering.",
                "blocking": False,
            },
        }
        score, state, blocked_gate, summary, next_action = (
            task._southbrook_score_from_gates(gates)
        )
        self.assertLessEqual(score, 89)
        self.assertEqual(state, "at_risk")
        self.assertFalse(blocked_gate)
        self.assertIn("Engineering not started", summary)
        self.assertEqual(next_action, "Start engineering.")

    def test_partial_gate_without_state_sets_at_risk_state(self):
        task = self._new_task()
        gates = {
            "engineering": {
                "message": "Engineering pending",
            },
        }
        score, state, blocked_gate, summary, next_action = (
            task._southbrook_score_from_gates(gates)
        )
        self.assertLessEqual(score, 89)
        self.assertEqual(state, "at_risk")
        self.assertFalse(blocked_gate)
        self.assertIn("Engineering pending", summary)
        self.assertEqual(next_action, "Engineering pending")

    def test_unknown_gate_state_sets_at_risk_state(self):
        task = self._new_task()
        gates = {
            "schedule": {
                "state": "deferred",
                "message": "Schedule status imported from legacy data",
                "action": False,
                "blocking": False,
            },
        }
        score, state, blocked_gate, summary, next_action = (
            task._southbrook_score_from_gates(gates)
        )
        self.assertLessEqual(score, 89)
        self.assertEqual(state, "at_risk")
        self.assertFalse(blocked_gate)
        self.assertIn("Unknown gate state 'deferred'", summary)
        self.assertIn("Unknown gate state 'deferred'", next_action)

    def test_unlinked_task_computes_at_risk_missing_mrp_context(self):
        task = self._new_task()
        self.assertEqual(task.x_southbrook_readiness_state, "at_risk")
        self.assertFalse(task.x_southbrook_blocking_gate)
        self.assertIn(
            "No originating quote or sales order is linked.",
            task.x_southbrook_blocker_summary,
        )
        self.assertLessEqual(task.x_southbrook_readiness_score, 89)

        rows = json.loads(task.x_southbrook_gate_json)
        self.assertEqual(len(rows), 11)
        self.assertEqual(rows[0]["gate"], "estimate")
        self.assertEqual(rows[0]["label"], "Estimate")
        self.assertEqual(rows[0]["state"], "warning")
        self.assertEqual(rows[8]["gate"], "schedule")
        self.assertEqual(rows[8]["state"], "warning")

    def test_computed_gate_json_has_expected_shape(self):
        task = self._new_task()

        rows = json.loads(task.x_southbrook_gate_json)
        self.assertEqual(len(rows), 11)
        for row in rows:
            self.assertEqual(
                set(row),
                {"gate", "label", "state", "message", "action", "blocking"},
            )

    def _new_mo_for_task(self, task, **vals):
        product = self.env["product.product"].create({
            "name": "MRP Command Cabinet",
            "type": "consu",
            "is_storable": True,
        })
        mo_vals = {
            "product_id": product.id,
            "product_uom_id": product.uom_id.id,
            "product_qty": 1.0,
            "origin": task.x_southbrook_sale_order_id.name
            if task.x_southbrook_sale_order_id else task.name,
        }
        mo_vals.update(vals)
        mo = self.env["mrp.production"].create(mo_vals)
        return mo

    def _new_sale_order_task(self):
        partner = self.env["res.partner"].create({
            "name": "MRP Command Customer",
        })
        sale = self.env["sale.order"].create({"partner_id": partner.id})
        sale.write({"state": "sale"})
        return self._new_task(x_southbrook_sale_order_id=sale.id), sale

    def _new_package_for_mo(self, mo):
        return self.env["sb.production.package"].create({"mo_id": mo.id})

    def test_missing_package_blocks_bom_cutlist_gate(self):
        task, sale = self._new_sale_order_task()
        self._new_mo_for_task(task)
        gates = task._southbrook_collect_readiness_gates()
        self.assertEqual(gates["bom_cutlist"]["state"], "blocked")
        self.assertTrue(gates["bom_cutlist"]["blocking"])
        self.assertIn(
            "production package",
            gates["bom_cutlist"]["message"].lower(),
        )
        score, state, blocked_gate, summary, next_action = (
            task._southbrook_score_from_gates(gates)
        )
        self.assertLessEqual(score, 69)
        self.assertEqual(state, "blocked")
        self.assertEqual(blocked_gate, "bom_cutlist")
        self.assertIn("production package", summary.lower())
        self.assertIn("production package", next_action.lower())

    def test_partial_packages_block_bom_cutlist_gate(self):
        task, sale = self._new_sale_order_task()
        packaged_mo = self._new_mo_for_task(task)
        unpackaged_mo = self._new_mo_for_task(task)
        self._new_package_for_mo(packaged_mo)

        gates = task._southbrook_collect_readiness_gates()

        self.assertEqual(gates["bom_cutlist"]["state"], "blocked")
        self.assertTrue(gates["bom_cutlist"]["blocking"])
        self.assertIn(
            "production package",
            gates["bom_cutlist"]["message"].lower(),
        )
        score, state, blocked_gate, summary, next_action = (
            task._southbrook_score_from_gates(gates)
        )
        self.assertLessEqual(score, 69)
        self.assertEqual(state, "blocked")
        self.assertEqual(blocked_gate, "bom_cutlist")
        self.assertIn("production package", summary.lower())
        self.assertIn("production package", next_action.lower())
        self.assertIn(unpackaged_mo, task._southbrook_related_productions())

    def test_related_productions_are_scoped_to_sale_company(self):
        task, sale = self._new_sale_order_task()
        production_model = self.env["mrp.production"]
        if "company_id" not in production_model._fields:
            self.skipTest("mrp.production has no company_id field")

        sale_company_mo = self._new_mo_for_task(
            task,
            company_id=sale.company_id.id,
        )
        other_company = self.env["res.company"].create({
            "name": "MRP Command Other Company",
        })
        other_company_mo = self._new_mo_for_task(
            task,
            company_id=other_company.id,
        )

        productions = task._southbrook_related_productions()

        self.assertIn(sale_company_mo, productions)
        self.assertNotIn(other_company_mo, productions)

    def test_tool_readiness_blocker_blocks_tooling_gate(self):
        task, sale = self._new_sale_order_task()
        mo = self._new_mo_for_task(task)
        self._new_package_for_mo(mo)
        workcenter = self.env["mrp.workcenter"].create({
            "name": "MRP Command CNC",
            "code": "MCC-CNC",
        })
        workorder = self.env["mrp.workorder"].create({
            "name": "CNC",
            "production_id": mo.id,
            "workcenter_id": workcenter.id,
            "state": "ready",
            "southbrook_tool_readiness_state": "blocked",
            "southbrook_tool_readiness_msg": "Blocked: need compression bit",
        })
        gates = task._southbrook_collect_readiness_gates()
        self.assertEqual(gates["tooling"]["state"], "blocked")
        self.assertIn("compression bit", gates["tooling"]["message"])
        score, state, blocked_gate, summary, next_action = (
            task._southbrook_score_from_gates(gates)
        )
        self.assertLessEqual(score, 69)
        self.assertEqual(state, "blocked")
        self.assertEqual(blocked_gate, "tooling")
        self.assertIn("compression bit", summary)
        self.assertEqual(next_action, "Clear mandatory tool readiness before release.")

    def test_unscheduled_workorder_sets_schedule_warning(self):
        task, sale = self._new_sale_order_task()
        mo = self._new_mo_for_task(task)
        self._new_package_for_mo(mo)
        workcenter = self.env["mrp.workcenter"].create({
            "name": "MRP Command Assembly",
            "code": "MCC-ASM",
        })
        workorder = self.env["mrp.workorder"].create({
            "name": "Assembly",
            "production_id": mo.id,
            "workcenter_id": workcenter.id,
            "state": "ready",
        })
        workorder.write({"date_start": False})
        gates = task._southbrook_collect_readiness_gates()
        self.assertEqual(gates["schedule"]["state"], "warning")
        self.assertIn("not scheduled", gates["schedule"]["message"])
        score, state, blocked_gate, summary, next_action = (
            task._southbrook_score_from_gates(gates)
        )
        self.assertLessEqual(score, 89)
        self.assertEqual(state, "at_risk")
        self.assertFalse(blocked_gate)
        self.assertIn("not scheduled", summary)

    def test_release_to_production_raises_with_blocker_summary(self):
        task, sale = self._new_sale_order_task()
        sale.action_confirm()
        self._new_mo_for_task(task)
        with self.assertRaises(UserError) as err:
            task.action_southbrook_release_to_production()
        self.assertIn("Cannot release", str(err.exception))
        self.assertIn("production package", str(err.exception).lower())

    def test_blocked_release_does_not_call_sale_release_action(self):
        task, sale = self._new_sale_order_task()
        sale.action_confirm()
        self._new_mo_for_task(task)
        calls = []
        Sale = type(sale)
        original = getattr(Sale, "action_send_to_production", None)

        def fake_action_send_to_production(recordset):
            calls.append(recordset)
            return recordset.env["mrp.production"]

        Sale.action_send_to_production = fake_action_send_to_production
        try:
            with self.assertRaises(UserError):
                task.action_southbrook_release_to_production()
        finally:
            if original:
                Sale.action_send_to_production = original
            else:
                delattr(Sale, "action_send_to_production")

        self.assertFalse(calls)

    def test_release_requires_mrp_create_rights_before_sale_action(self):
        task, sale = self._new_sale_order_task()
        calls = []
        Sale = type(sale)
        Production = type(self.env["mrp.production"])
        original_sale_action = getattr(Sale, "action_send_to_production", None)
        original_check_access_rights = Production.check_access_rights

        def fake_action_send_to_production(recordset):
            calls.append(recordset)
            return recordset.env["mrp.production"]

        def fake_check_access_rights(
            recordset, operation, raise_exception=True
        ):
            if operation == "create":
                raise AccessError("No MRP create rights")
            return original_check_access_rights(
                recordset, operation, raise_exception=raise_exception
            )

        Sale.action_send_to_production = fake_action_send_to_production
        Production.check_access_rights = fake_check_access_rights
        try:
            with self.assertRaises(AccessError):
                task.action_southbrook_release_to_production()
        finally:
            Production.check_access_rights = original_check_access_rights
            if original_sale_action:
                Sale.action_send_to_production = original_sale_action
            else:
                delattr(Sale, "action_send_to_production")

        self.assertFalse(calls)

    def test_release_recompute_rebrowses_productions_without_sudo(self):
        task, sale = self._new_sale_order_task()
        mo = self._new_mo_for_task(task)
        Production = type(mo)
        original = getattr(
            Production, "action_recompute_manufacturing_intelligence", None
        )
        recompute_env_su = []

        def fake_recompute(recordset):
            recompute_env_su.append(recordset.env.su)
            return True

        Production.action_recompute_manufacturing_intelligence = fake_recompute
        try:
            task.action_southbrook_recompute_mrp_readiness()
        finally:
            if original:
                Production.action_recompute_manufacturing_intelligence = original
            else:
                delattr(
                    Production,
                    "action_recompute_manufacturing_intelligence",
                )

        self.assertTrue(recompute_env_su)
        self.assertFalse(any(recompute_env_su))

    def test_release_requires_mi_check_rights_before_sale_action(self):
        task, sale = self._new_sale_order_task()
        mo = self._new_mo_for_task(task)
        calls = []
        Sale = type(sale)
        Production = type(mo)
        Check = type(self.env["southbrook.mi.check"])
        original_sale_action = getattr(Sale, "action_send_to_production", None)
        original_recompute = getattr(
            Production, "action_recompute_manufacturing_intelligence", None
        )
        original_check_access_rights = Check.check_access_rights

        def fake_action_send_to_production(recordset):
            calls.append(recordset)
            return recordset.env["mrp.production"]

        def fake_recompute(recordset):
            return True

        def fake_check_access_rights(
            recordset, operation, raise_exception=True
        ):
            if operation == "unlink":
                raise AccessError("No MI unlink rights")
            return original_check_access_rights(
                recordset, operation, raise_exception=raise_exception
            )

        Sale.action_send_to_production = fake_action_send_to_production
        Production.action_recompute_manufacturing_intelligence = fake_recompute
        Check.check_access_rights = fake_check_access_rights
        try:
            with self.assertRaises(AccessError):
                task.action_southbrook_release_to_production()
        finally:
            Check.check_access_rights = original_check_access_rights
            if original_recompute:
                Production.action_recompute_manufacturing_intelligence = (
                    original_recompute
                )
            else:
                delattr(
                    Production,
                    "action_recompute_manufacturing_intelligence",
                )
            if original_sale_action:
                Sale.action_send_to_production = original_sale_action
            else:
                delattr(Sale, "action_send_to_production")

        self.assertFalse(calls)

    def test_successful_release_returns_mo_action_dict(self):
        task, sale = self._new_sale_order_task()
        Sale = type(sale)
        Production = type(self.env["mrp.production"])
        original = getattr(Sale, "action_send_to_production", None)
        original_check_access_rights = Production.check_access_rights
        access_env_su = []

        def fake_action_send_to_production(recordset):
            return self._new_mo_for_task(task).sudo()

        def fake_check_access_rights(
            recordset, operation, raise_exception=True
        ):
            access_env_su.append(recordset.env.su)
            return original_check_access_rights(
                recordset, operation, raise_exception=raise_exception
            )

        Sale.action_send_to_production = fake_action_send_to_production
        Production.check_access_rights = fake_check_access_rights
        try:
            action = task.action_southbrook_release_to_production()
        finally:
            Production.check_access_rights = original_check_access_rights
            if original:
                Sale.action_send_to_production = original
            else:
                delattr(Sale, "action_send_to_production")

        self.assertIsInstance(action, dict)
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "mrp.production")
        self.assertEqual(action["view_mode"], "form")
        self.assertTrue(access_env_su)
        self.assertFalse(any(access_env_su))

    def test_release_dict_result_returns_neutral_notification(self):
        task, sale = self._new_sale_order_task()
        raw_action = {
            "type": "ir.actions.act_window",
            "res_model": "mrp.production",
            "res_id": 999999,
        }
        Sale = type(sale)
        original = getattr(Sale, "action_send_to_production", None)

        def fake_action_send_to_production(recordset):
            return raw_action

        Sale.action_send_to_production = fake_action_send_to_production
        try:
            action = task.action_southbrook_release_to_production()
        finally:
            if original:
                Sale.action_send_to_production = original
            else:
                delattr(Sale, "action_send_to_production")

        self.assertIsInstance(action, dict)
        self.assertNotEqual(action, raw_action)
        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "display_notification")
        self.assertEqual(
            action["params"]["message"],
            "Production release completed, but no safe manufacturing "
            "order action is available.",
        )

    def test_release_without_sale_returns_neutral_notification(self):
        task = self._new_task()

        action = task.action_southbrook_release_to_production()

        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "display_notification")
        self.assertEqual(
            action["params"]["message"],
            "No production release action is available for this task.",
        )
