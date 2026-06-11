# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "project_mrp")
class TestProjectMrpIntegration(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Job Customer"})
        cls.project = cls.env["project.project"].create({"name": "Jobs"})
        # A manufacturable cabinetry-ish product (has a BoM => drives an MO).
        cls.comp = cls.env["product.product"].create(
            {"name": "Panel", "type": "consu", "is_storable": True})
        cls.fp = cls.env["product.product"].create({
            "name": "SB-BASE-1DR", "type": "consu", "is_storable": True})
        cls.bom = cls.env["mrp.bom"].create({
            "product_tmpl_id": cls.fp.product_tmpl_id.id,
            "product_qty": 1.0,
            "bom_line_ids": [(0, 0, {"product_id": cls.comp.id,
                                     "product_qty": 1.0})],
        })

    def _make_mo(self):
        mo = self.env["mrp.production"].create(
            {"product_id": self.fp.id, "product_qty": 1.0, "bom_id": self.bom.id})
        return mo

    # --- T1.1 + T1.2 ---------------------------------------------------------
    def test_link_and_status_rollup(self):
        task = self.env["project.task"].create(
            {"name": "Smith Kitchen", "project_id": self.project.id})
        self.assertEqual(task.production_count, 0)
        self.assertEqual(task.components_available, "none")

        mo1, mo2 = self._make_mo(), self._make_mo()
        (mo1 | mo2).write({"project_task_id": task.id})
        task.invalidate_recordset()

        self.assertEqual(task.production_count, 2)
        self.assertEqual(set(task.production_ids.ids), {mo1.id, mo2.id})
        self.assertIn(mo1.name, task.mo_reference)
        self.assertIn("SB-BASE-1DR", task.mo_product_summary)
        self.assertTrue(task.mo_state_summary)              # non-empty rollup
        self.assertNotEqual(task.components_available, "none")

    # --- T1.3: sale confirm creates + links the job -------------------------
    def test_sale_confirm_creates_job(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "southbrook_project_mrp.job_project_id", str(self.project.id))
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {"product_id": self.fp.id,
                                   "product_uom_qty": 1.0})],
        })
        self.assertFalse(self.env["project.task"].search(
            [("x_southbrook_sale_order_id", "=", so.id)]))

        so.action_confirm()

        job = self.env["project.task"].search(
            [("x_southbrook_sale_order_id", "=", so.id)])
        self.assertEqual(len(job), 1, "confirming a manufacturing sale must "
                                      "create exactly one job task")
        self.assertEqual(job.project_id, self.project)
        # Idempotent: re-confirm path doesn't double-create.
        so._southbrook_ensure_job()
        self.assertEqual(len(self.env["project.task"].search(
            [("x_southbrook_sale_order_id", "=", so.id)])), 1)

    def test_non_manufacturing_sale_makes_no_job(self):
        svc = self.env["product.product"].create(
            {"name": "Consulting", "type": "service"})
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {"product_id": svc.id,
                                   "product_uom_qty": 1.0})],
        })
        so.action_confirm()
        self.assertFalse(self.env["project.task"].search(
            [("x_southbrook_sale_order_id", "=", so.id)]),
            "a sale with no BoM-able product should not create a job")

    # --- MO back-links to an existing job on create -------------------------
    def test_mo_create_backlinks_to_job(self):
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {"product_id": self.fp.id,
                                   "product_uom_qty": 1.0})],
        })
        job = self.env["project.task"].create({
            "name": "Job", "project_id": self.project.id,
            "x_southbrook_sale_order_id": so.id})
        mo = self.env["mrp.production"].create({
            "product_id": self.fp.id, "product_qty": 1.0, "bom_id": self.bom.id,
            "sale_line_id": so.order_line[0].id})
        self.assertEqual(mo.project_task_id, job,
                         "an MO traced to a sale that has a job must back-link")
