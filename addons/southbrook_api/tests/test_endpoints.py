# SPDX-License-Identifier: LGPL-3.0-only
"""All G6 endpoints except /auth/login (which has its own auth tests)."""
import json

from odoo.tests.common import HttpCase, tagged


SCHEMA = "southbrook.flutter.api.v1"


@tagged("post_install", "-at_install", "southbrook", "api", "endpoints")
class TestApiEndpoints(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        portal_group = cls.env.ref("base.group_portal")
        cls.alice_partner = cls.env["res.partner"].create({
            "name": "Alice", "email": "alice.api@example.com",
        })
        cls.alice = cls.env["res.users"].create({
            "login": "alice.api@example.com",
            "password": "alice-strong-pw-123",
            "partner_id": cls.alice_partner.id,
            "group_ids": [(6, 0, [portal_group.id])],
        })
        cls.bob_partner = cls.env["res.partner"].create({
            "name": "Bob", "email": "bob.api@example.com",
        })
        cls.bob = cls.env["res.users"].create({
            "login": "bob.api@example.com",
            "password": "bob-strong-pw-123",
            "partner_id": cls.bob_partner.id,
            "group_ids": [(6, 0, [portal_group.id])],
        })

        Project = cls.env["sb.kitchen.project"]
        cls.alice_project = Project.create({
            "name": "Alice's Kitchen",
            "partner_id": cls.alice_partner.id, "theme": "signature",
        })
        cls.bob_project = Project.create({
            "name": "Bob's Kitchen",
            "partner_id": cls.bob_partner.id, "theme": "contractor",
        })
        # Two design options on Alice's project.
        DesignOption = cls.env["sb.kitchen.design.option"]
        cls.opt_a = DesignOption.create({
            "project_id": cls.alice_project.id, "name": "Option A",
            "estimated_price": 12000,
        })
        cls.opt_b = DesignOption.create({
            "project_id": cls.alice_project.id, "name": "Option B",
            "estimated_price": 14000,
        })

    def _api_key_for(self, email, password):
        resp = self.url_open(
            "/api/v1/auth/login",
            data=json.dumps({"email": email, "password": password}),
            headers={"Content-Type": "application/json"},
        )
        return resp.json()["api_key"]

    # ------------------------------------------------------------------
    # /kitchen-projects (list + detail)
    # ------------------------------------------------------------------
    def test_list_projects_returns_only_own(self):
        key = self._api_key_for("alice.api@example.com", "alice-strong-pw-123")
        resp = self.url_open(
            "/api/v1/kitchen-projects",
            headers={"X-Api-Key": key},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["schema"], SCHEMA)
        names = [p["name"] for p in body["projects"]]
        self.assertIn("Alice's Kitchen", names)
        self.assertNotIn("Bob's Kitchen", names)

    def test_project_detail_own_works(self):
        key = self._api_key_for("alice.api@example.com", "alice-strong-pw-123")
        resp = self.url_open(
            f"/api/v1/kitchen-projects/{self.alice_project.id}",
            headers={"X-Api-Key": key},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["project"]["name"], "Alice's Kitchen")

    def test_project_detail_other_user_returns_404(self):
        """Alice asking for Bob's project must see 404 (not 403) —
        no existence leak."""
        key = self._api_key_for("alice.api@example.com", "alice-strong-pw-123")
        resp = self.url_open(
            f"/api/v1/kitchen-projects/{self.bob_project.id}",
            headers={"X-Api-Key": key},
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["error"], "project_not_found")

    def test_project_detail_nonexistent_returns_404(self):
        key = self._api_key_for("alice.api@example.com", "alice-strong-pw-123")
        resp = self.url_open(
            "/api/v1/kitchen-projects/99999",
            headers={"X-Api-Key": key},
        )
        self.assertEqual(resp.status_code, 404)

    # ------------------------------------------------------------------
    # /concepts (list + select)
    # ------------------------------------------------------------------
    def test_list_concepts_returns_both(self):
        key = self._api_key_for("alice.api@example.com", "alice-strong-pw-123")
        resp = self.url_open(
            f"/api/v1/kitchen-projects/{self.alice_project.id}/concepts",
            headers={"X-Api-Key": key},
        )
        self.assertEqual(resp.status_code, 200)
        concepts = resp.json()["concepts"]
        names = {c["name"] for c in concepts}
        self.assertEqual(names, {"Option A", "Option B"})

    def test_select_concept_flips_isolation(self):
        key = self._api_key_for("alice.api@example.com", "alice-strong-pw-123")
        resp = self.url_open(
            f"/api/v1/kitchen-projects/{self.alice_project.id}"
            f"/concepts/{self.opt_b.id}/select",
            data="{}",
            headers={"X-Api-Key": key, "Content-Type": "application/json"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["selected_id"], self.opt_b.id)
        # Verify model side.
        self.opt_a.invalidate_recordset(["is_selected"])
        self.opt_b.invalidate_recordset(["is_selected"])
        self.assertFalse(self.opt_a.is_selected)
        self.assertTrue(self.opt_b.is_selected)

    def test_select_concept_from_other_project_returns_404(self):
        """Alice tries to select an option on Bob's project."""
        Bob = self.env["sb.kitchen.design.option"].create({
            "project_id": self.bob_project.id, "name": "Bob Option",
        })
        key = self._api_key_for("alice.api@example.com", "alice-strong-pw-123")
        # alice's path + bob's option id → project_not_found
        resp = self.url_open(
            f"/api/v1/kitchen-projects/{self.bob_project.id}"
            f"/concepts/{Bob.id}/select",
            data="{}",
            headers={"X-Api-Key": key, "Content-Type": "application/json"},
        )
        self.assertEqual(resp.status_code, 404)

    # ------------------------------------------------------------------
    # /approve
    # ------------------------------------------------------------------
    def test_approve_advances_state(self):
        # Move the project into awaiting_customer first.
        self.alice_project.action_start_designing()
        self.alice_project.action_submit_to_customer()
        self.opt_b.write({"is_selected": True})
        key = self._api_key_for("alice.api@example.com", "alice-strong-pw-123")

        resp = self.url_open(
            f"/api/v1/kitchen-projects/{self.alice_project.id}/approve",
            data=json.dumps({"notes": "I love it"}),
            headers={"X-Api-Key": key, "Content-Type": "application/json"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["project_state"], "approved")

    def test_approve_without_selection_409(self):
        # Move to awaiting_customer but DO NOT select.
        # Use a fresh project.
        new_proj = self.env["sb.kitchen.project"].create({
            "name": "No selection yet", "partner_id": self.alice_partner.id,
            "theme": "signature",
        })
        self.env["sb.kitchen.design.option"].create({
            "project_id": new_proj.id, "name": "Sole option",
        })
        new_proj.action_start_designing()
        new_proj.action_submit_to_customer()
        # Reset is_selected (the option may auto-select via the design
        # workflow — make sure it's off for this test).
        new_proj.design_option_ids.write({"is_selected": False})
        key = self._api_key_for("alice.api@example.com", "alice-strong-pw-123")
        resp = self.url_open(
            f"/api/v1/kitchen-projects/{new_proj.id}/approve",
            data="{}",
            headers={"X-Api-Key": key, "Content-Type": "application/json"},
        )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["error"], "no_concept_selected")

    def test_approve_wrong_state_409(self):
        # state=draft is not approvable.
        key = self._api_key_for("alice.api@example.com", "alice-strong-pw-123")
        # alice_project starts in draft
        self.opt_a.write({"is_selected": True})
        resp = self.url_open(
            f"/api/v1/kitchen-projects/{self.alice_project.id}/approve",
            data="{}",
            headers={"X-Api-Key": key, "Content-Type": "application/json"},
        )
        # state=draft → 409 invalid_state
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["error"], "invalid_state")
