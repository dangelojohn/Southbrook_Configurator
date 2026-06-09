# SPDX-License-Identifier: LGPL-3.0-only
"""Idempotency-Key replay safety per G6 §5."""
import json
import uuid

from odoo.tests.common import HttpCase, tagged


SCHEMA = "southbrook.flutter.api.v1"


@tagged("post_install", "-at_install", "southbrook", "api", "idempotency")
class TestApiIdempotency(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        portal_group = cls.env.ref("base.group_portal")
        cls.partner = cls.env["res.partner"].create({
            "name": "Idem Test", "email": "idem.api@example.com",
        })
        cls.user = cls.env["res.users"].create({
            "login": "idem.api@example.com",
            "password": "idem-strong-pw-123",
            "partner_id": cls.partner.id,
            "group_ids": [(6, 0, [portal_group.id])],
        })
        cls.project = cls.env["sb.kitchen.project"].create({
            "name": "Idem Kitchen", "partner_id": cls.partner.id,
            "theme": "signature",
        })
        cls.opt = cls.env["sb.kitchen.design.option"].create({
            "project_id": cls.project.id, "name": "Sole option",
        })

    def _api_key(self):
        resp = self.url_open(
            "/api/v1/auth/login",
            data=json.dumps({"email": "idem.api@example.com",
                              "password": "idem-strong-pw-123"}),
            headers={"Content-Type": "application/json"},
        )
        return resp.json()["api_key"]

    def test_replay_returns_same_response(self):
        key = self._api_key()
        idem = str(uuid.uuid4())
        resp1 = self.url_open(
            f"/api/v1/kitchen-projects/{self.project.id}"
            f"/concepts/{self.opt.id}/select",
            data="{}",
            headers={
                "X-Api-Key": key, "Content-Type": "application/json",
                "Idempotency-Key": idem,
            },
        )
        self.assertEqual(resp1.status_code, 200)
        body1 = resp1.json()

        # Replay with same Idempotency-Key.
        resp2 = self.url_open(
            f"/api/v1/kitchen-projects/{self.project.id}"
            f"/concepts/{self.opt.id}/select",
            data="{}",
            headers={
                "X-Api-Key": key, "Content-Type": "application/json",
                "Idempotency-Key": idem,
            },
        )
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json(), body1,
                          "Replay must return byte-identical body")

    def test_different_key_creates_new_record(self):
        key = self._api_key()
        idem_a = str(uuid.uuid4())
        idem_b = str(uuid.uuid4())
        for idem in (idem_a, idem_b):
            resp = self.url_open(
                f"/api/v1/kitchen-projects/{self.project.id}"
                f"/concepts/{self.opt.id}/select",
                data="{}",
                headers={
                    "X-Api-Key": key, "Content-Type": "application/json",
                    "Idempotency-Key": idem,
                },
            )
            self.assertEqual(resp.status_code, 200)
        # Two distinct records in the cache.
        cache = self.env["southbrook.api.idempotency"].sudo().search([
            ("idempotency_key", "in", [idem_a, idem_b]),
        ])
        self.assertEqual(len(cache), 2)

    def test_no_idempotency_key_still_works(self):
        """A POST without Idempotency-Key behaves normally and creates
        no cache record."""
        key = self._api_key()
        resp = self.url_open(
            f"/api/v1/kitchen-projects/{self.project.id}"
            f"/concepts/{self.opt.id}/select",
            data="{}",
            headers={"X-Api-Key": key, "Content-Type": "application/json"},
        )
        self.assertEqual(resp.status_code, 200)
