# SPDX-License-Identifier: LGPL-3.0-only
"""GAP-02 gate — the engine must refuse to act on unconfirmed inputs."""
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "config_engine", "gap02")
class TestGap02Gate(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Engine = cls.env["southbrook.config.engine"]
        cls.partner = cls.env["res.partner"].create({"name": "Engine test"})

    def _new_project(self):
        return self.env["sb.kitchen.project"].create({
            "name": "Engine gate test",
            "partner_id": self.partner.id,
            "theme": "signature",
        })

    def test_refuses_when_no_analysis(self):
        project = self._new_project()
        with self.assertRaises(UserError):
            self.Engine.place_for_project(project)

    def test_refuses_when_analysis_unconfirmed(self):
        project = self._new_project()
        analysis = self.env["sb.kitchen.ai.analysis"].create({
            "project_id": project.id,
            "raw_response_json": '{"room": {"wall_segments": []}, "appliances": []}',
        })
        project.ai_analysis_id = analysis
        # confirmed_by_human defaults False
        with self.assertRaises(UserError):
            self.Engine.place_for_project(project)

    def test_refuses_when_appliance_unconfirmed(self):
        project = self._new_project()
        analysis = self.env["sb.kitchen.ai.analysis"].create({
            "project_id": project.id,
            "raw_response_json": '{"room": {"wall_segments":[{"id":"wall_n","length_mm_approx":3000}]}, "appliances":[]}',
        })
        project.ai_analysis_id = analysis
        analysis.action_confirm()
        self.env["sb.kitchen.appliance"].create({
            "project_id": project.id,
            "name": "Stove",
            "appliance_type": "stove",
            "width_mm": 762,
            "confirmed_by_human": False,
        })
        with self.assertRaises(UserError):
            self.Engine.place_for_project(project)
