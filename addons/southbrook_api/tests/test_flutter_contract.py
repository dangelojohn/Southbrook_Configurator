# SPDX-License-Identifier: LGPL-3.0-only
"""Contract guard: the Flutter client reads specific keys out of the
'southbrook.flutter.api.v1' responses. If the backend ever renames or drops
one of those keys, the app silently breaks (this is exactly the 'No projects
yet' / stuck-step incident: the Dart models read keys the API wasn't sending).

These tests assert every key the Dart models depend on is present in the live
API response. Each required key is mapped to the Dart field that reads it, so a
failure tells you precisely which client field would break.

Keep in sync with flutter_app/lib/models/{project,concept}.dart and
addons/southbrook_api/controllers/main.py (_project_summary / _project_detail
/ _concept_dict).
"""
import json

from odoo.tests.common import HttpCase, tagged

SCHEMA = "southbrook.flutter.api.v1"

# key in API response  ->  Dart field that reads it (for the failure message)
PROJECT_SUMMARY_CONTRACT = {
    "id": "Project.id",
    "code": "Project.code",
    "name": "Project.name",
    "state": "Project.state",
    "theme": "Project.theme",
    "date_target": "Project.dateTarget",
    "concept_count": "Project.designOptionCount (count('concept_count','concept_ids'))",
}
PROJECT_DETAIL_CONTRACT = {
    "id": "Project.id",
    "code": "Project.code",
    "name": "Project.name",
    "state": "Project.state",
    "theme": "Project.theme",
    "selected_design_option_id": "Project.selectedOptionId (gates canApprove)",
    "concept_ids": "Project.designOptionCount (gates canReviewConcepts)",
    "ai_ready": "Project.hasAiAnalysis",
    "photo_attachment_ids": "Project.photoCount",
}
CONCEPT_CONTRACT = {
    "id": "Concept.id",
    "name": "Concept.name",
    "description_html": "Concept.description",
    "estimated_price": "Concept.estimatedPrice",
    "is_selected": "Concept.isSelected",
    "preview_attachment_id": "Concept.previewAttachmentId",
}


@tagged("post_install", "-at_install", "flutter_contract")
class TestFlutterContract(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        portal = cls.env.ref("base.group_portal")
        cls.partner = cls.env["res.partner"].create({
            "name": "Contract Customer", "email": "contract@example.test",
        })
        cls.env["res.users"].sudo().create({
            "name": "Contract Customer", "login": "contract@example.test",
            "password": "contract-strong-pw-1", "partner_id": cls.partner.id,
            "group_ids": [(6, 0, [portal.id])],
        })
        cls.project = cls.env["sb.kitchen.project"].create({
            "name": "Contract Kitchen", "partner_id": cls.partner.id,
            "theme": "signature",
        })
        cls.project.action_start_designing()
        cls.env["sb.kitchen.design.option"].create({
            "project_id": cls.project.id, "name": "Opt A",
            "estimated_price": 10000, "description": "<p>desc</p>",
        })
        cls.project.action_submit_to_customer()

    def _key(self):
        resp = self.url_open(
            "/api/v1/auth/login",
            data=json.dumps({"email": "contract@example.test",
                             "password": "contract-strong-pw-1"}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp.json()["api_key"]

    def _assert_contract(self, payload, contract, where):
        missing = [k for k in contract if k not in payload]
        if missing:
            details = "; ".join(f"'{k}' (read by {contract[k]})" for k in missing)
            self.fail(
                f"{where}: response is missing contract key(s) the Flutter "
                f"client depends on: {details}. Present keys: "
                f"{sorted(payload.keys())}")

    def test_project_summary_contract(self):
        key = self._key()
        resp = self.url_open("/api/v1/kitchen-projects",
                             headers={"X-Api-Key": key})
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["schema"], SCHEMA)
        summary = next(p for p in body["projects"] if p["id"] == self.project.id)
        self._assert_contract(summary, PROJECT_SUMMARY_CONTRACT,
                              "GET /kitchen-projects[]")

    def test_project_detail_contract(self):
        key = self._key()
        resp = self.url_open(f"/api/v1/kitchen-projects/{self.project.id}",
                             headers={"X-Api-Key": key})
        self.assertEqual(resp.status_code, 200, resp.text)
        self._assert_contract(resp.json()["project"], PROJECT_DETAIL_CONTRACT,
                              "GET /kitchen-projects/<id>")

    def test_concept_contract(self):
        key = self._key()
        resp = self.url_open(
            f"/api/v1/kitchen-projects/{self.project.id}/concepts",
            headers={"X-Api-Key": key})
        self.assertEqual(resp.status_code, 200, resp.text)
        concepts = resp.json()["concepts"]
        self.assertTrue(concepts, "expected at least one concept")
        for c in concepts:
            self._assert_contract(c, CONCEPT_CONTRACT,
                                  "GET /kitchen-projects/<id>/concepts[]")
