# SPDX-License-Identifier: LGPL-3.0-only
"""P7 — Single source of truth for material / hardware / qty.

After action_confirm, project.task's three Cabinetry-Specs fields
reflect the configured sale.order — they do not silently diverge.
A manual override boolean opts a task out of the sync.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "project", "p7",
        "specs_sync")
class TestP7SpecsSync(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Attribute = cls.env["product.attribute"]
        cls.AttributeValue = cls.env["product.attribute.value"]
        cls.Tmpl = cls.env["product.template"]
        cls.TmplAttrLine = cls.env["product.template.attribute.line"]
        cls.SaleOrder = cls.env["sale.order"]
        cls.Task = cls.env["project.task"]
        cls.Project = cls.env["project.project"]
        cls.Partner = cls.env["res.partner"].create({"name": "P7 customer"})

    def _attr(self, name, values):
        a = self.Attribute.create({"name": name, "create_variant": "always"})
        return a, [
            self.AttributeValue.create({"name": v, "attribute_id": a.id})
            for v in values
        ]

    def _make_configured_template(self, species_value):
        tmpl = self.Tmpl.create({
            "name": "P7 cabinet", "type": "consu", "is_storable": True,
        })
        width_attr, width_vals = self._attr("Width", ["24 in"])
        species_attr, species_vals = self._attr("Wood Species", [species_value])
        for attr, vals in (
            (width_attr, width_vals),
            (species_attr, species_vals),
        ):
            self.TmplAttrLine.create({
                "product_tmpl_id": tmpl.id,
                "attribute_id": attr.id,
                "value_ids": [(6, 0, [v.id for v in vals])],
            })
        tmpl._create_variant_ids()
        return tmpl, tmpl.product_variant_id

    def _make_so_and_task(self, variant, qty=2):
        so = self.SaleOrder.create({
            "partner_id": self.Partner.id,
            "order_line": [(0, 0, {
                "product_id": variant.id,
                "product_uom_qty": qty,
            })],
        })
        project = self.Project.create({"name": "P7 project"})
        task = self.Task.create({
            "name": "P7 task",
            "project_id": project.id,
            "x_southbrook_sale_order_id": so.id,
        })
        return so, task

    # ------------------------------------------------------------------
    # Acceptance — sync pulls species + unit count from the SO
    # ------------------------------------------------------------------
    def test_sync_pulls_species_and_unit_count(self):
        _, variant = self._make_configured_template("Hard Maple")
        so, task = self._make_so_and_task(variant, qty=3)
        task._southbrook_p7_sync_from_so()
        self.assertEqual(task.x_southbrook_material_species, "maple")
        self.assertEqual(task.x_southbrook_unit_count, 3)

    # ------------------------------------------------------------------
    # Acceptance — override boolean opts the task out
    # ------------------------------------------------------------------
    def test_override_flag_skips_sync(self):
        _, variant = self._make_configured_template("Hard Maple")
        so, task = self._make_so_and_task(variant, qty=3)
        task.x_southbrook_specs_override = True
        task.x_southbrook_material_species = "walnut"  # manual divergence
        task._southbrook_p7_sync_from_so()
        self.assertEqual(
            task.x_southbrook_material_species, "walnut",
            "override=True must keep the manual species (no auto-overwrite)")

    # ------------------------------------------------------------------
    # Acceptance — no SO link, no sync (graceful no-op)
    # ------------------------------------------------------------------
    def test_no_so_is_noop(self):
        task = self.Task.create({
            "name": "P7 unlinked task",
            "x_southbrook_material_species": "cherry",
        })
        task._southbrook_p7_sync_from_so()
        self.assertEqual(task.x_southbrook_material_species, "cherry")
