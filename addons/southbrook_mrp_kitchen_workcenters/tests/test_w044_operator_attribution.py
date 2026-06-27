# SPDX-License-Identifier: LGPL-3.0-only
"""W044 (R5.8) — Operator-attribution on NCR via PIN-gated scan_log.

`southbrook.mi.check.x_sbk_operator_who_caused_defect_id` is a stored
compute that resolves the most recent `southbrook.qr.scan.log` row tied
to the NCR's `x_sbk_workorder_id` whose `employee_id` is set (i.e. a
PIN-gated W035 scan or a form-open by an employee-bound session user).

These tests verify:
  * resolves to the most recent stamped employee
  * empty WO -> empty operator
  * WO with no stamped employee scans -> empty operator
  * rebinding x_sbk_workorder_id re-resolves
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_kitchen", "w044")
class TestW044OperatorAttribution(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Check = cls.env["southbrook.mi.check"]
        cls.Log = cls.env["southbrook.qr.scan.log"]
        cls.Workorder = cls.env["mrp.workorder"]
        cls.Employee = cls.env["hr.employee"]
        cls.emp_a = cls.Employee.create({"name": "W044 Operator A"})
        cls.emp_b = cls.Employee.create({"name": "W044 Operator B"})

    def _make_wo(self):
        wc = self.env["mrp.workcenter"].search([], limit=1)
        if not wc:
            wc = self.env["mrp.workcenter"].create({
                "name": "W044 WC", "code": "W044WC",
            })
        product = self.env["product.product"].search([
            ("type", "=", "consu")], limit=1)
        if not product:
            product = self.env["product.product"].create({
                "name": "W044 product", "type": "consu",
            })
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_qty": 1.0,
        })
        production = self.env["mrp.production"].create({
            "product_id": product.id,
            "product_qty": 1.0,
            "bom_id": bom.id,
        })
        wo = self.Workorder.create({
            "name": "W044 WO",
            "production_id": production.id,
            "workcenter_id": wc.id,
            "product_uom_id": product.uom_id.id,
        })
        return wo

    def _stamp_log(self, wo, employee, action="start"):
        """Create a scan_log row tied to `wo` and credited to
        `employee`. Returns the new row."""
        return self.Log.create({
            "user_id": self.env.user.id,
            "employee_id": employee.id if employee else False,
            "kind": "wo",
            "ident": str(wo.id),
            "action": action,
            "result": "ok",
            "target_model": "mrp.workorder",
            "target_id": wo.id,
        })

    def test_10_resolves_most_recent_employee(self):
        """Two scans, two different operators — the field resolves to
        the most recently stamped one."""
        wo = self._make_wo()
        self._stamp_log(wo, self.emp_a, action="start")
        self._stamp_log(wo, self.emp_b, action="finish")
        check = self.Check.create({
            "name": "W044 NCR-most-recent",
            "severity": "warning",
            "category": "production",
            "message": "Defect at the bench",
            "x_sbk_workorder_id": wo.id,
        })
        self.assertEqual(
            check.x_sbk_operator_who_caused_defect_id, self.emp_b,
            "compute should pick the most-recent employee-stamped scan")

    def test_20_no_wo_yields_empty_operator(self):
        """An NCR without an attached WO has no operator attribution."""
        check = self.Check.create({
            "name": "W044 NCR-no-wo",
            "severity": "info",
            "category": "production",
            "message": "No WO bound",
        })
        self.assertFalse(check.x_sbk_operator_who_caused_defect_id)

    def test_30_no_employee_stamped_scans_yields_empty(self):
        """Scans on the WO with NULL employee_id (pre-W035, or
        unauthenticated POD scans) do not credit the field."""
        wo = self._make_wo()
        self._stamp_log(wo, False, action="start")
        check = self.Check.create({
            "name": "W044 NCR-no-emp",
            "severity": "warning",
            "category": "production",
            "message": "Defect — no operator known",
            "x_sbk_workorder_id": wo.id,
        })
        self.assertFalse(
            check.x_sbk_operator_who_caused_defect_id,
            "scans without employee_id must not credit the field")

    def test_40_rebinding_wo_re_resolves(self):
        """Changing x_sbk_workorder_id re-fires the compute against
        the new WO's scan_log."""
        wo_a = self._make_wo()
        wo_b = self._make_wo()
        self._stamp_log(wo_a, self.emp_a)
        self._stamp_log(wo_b, self.emp_b)
        check = self.Check.create({
            "name": "W044 NCR-rebind",
            "severity": "warning",
            "category": "production",
            "message": "Starts on A",
            "x_sbk_workorder_id": wo_a.id,
        })
        self.assertEqual(
            check.x_sbk_operator_who_caused_defect_id, self.emp_a)
        check.x_sbk_workorder_id = wo_b.id
        self.assertEqual(
            check.x_sbk_operator_who_caused_defect_id, self.emp_b,
            "rebinding the WO must re-resolve the operator field")
