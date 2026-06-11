# SPDX-License-Identifier: LGPL-3.0-only
"""Full end-to-end scenario with test data.

A **Sales Manager** provisions a customer's kitchen environment (contact,
portal login, project, three design concepts) and submits it for review.
Then the **customer** completes the whole journey through the Flutter API
exactly as the mobile app would: login -> /me -> list -> detail -> photo
upload -> concepts -> select -> approve.

Run only this scenario (mirrors `make test` flags):

  docker exec sami-odoo odoo -d southbrook -u southbrook_api \
    --test-enable --test-tags=sm_scenario \
    --db_host=db --db_user=odoo --db_password=<pw> \
    --stop-after-init --no-http --http-port=8899 --gevent-port=8902 \
    --workers=0 --max-cron-threads=0
"""
import io
import json

from PIL import Image

from odoo.tests.common import HttpCase, tagged


def _kitchen_photo_bytes():
    """A real, fully-decodable PNG standing in for a kitchen photo. (A
    truncated/1x1 image makes the AI pipeline's PIL decode raise, so use a
    proper raster here.)"""
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), (210, 205, 198)).save(buf, format="PNG")
    return buf.getvalue()


_KITCHEN_PHOTO = _kitchen_photo_bytes()

SCHEMA = "southbrook.flutter.api.v1"


@tagged("post_install", "-at_install", "sm_scenario")
class TestSalesManagerSetupScenario(HttpCase):
    """One ordered narrative: manager sets up -> customer completes."""

    def _api(self, path, key=None, data=None, files=None):
        headers = {}
        if key:
            headers["X-Api-Key"] = key
        if data is not None and files is None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(data)
        return self.url_open(
            path, data=data, files=files, headers=headers,
            allow_redirects=False,
        )

    def test_full_journey(self):
        env = self.env

        # ============================================================
        # ACTOR 1 — SALES MANAGER sets up the customer's environment
        # ============================================================
        mgr_group = env.ref("sales_team.group_sale_manager")
        sales_mgr = env["res.users"].create({
            "name": "Sam Manager",
            "login": "sam.manager@southbrook.test",
            "password": "mgr-strong-pw-1",
            "group_ids": [(4, mgr_group.id)],
        })
        mgr = env(user=sales_mgr.id)

        # 1) Provision the customer contact (as the manager).
        customer = mgr["res.partner"].create({
            "name": "Jane Homeowner",
            "email": "jane.home@example.test",
        })

        # 2) Grant the customer a portal login. Creating res.users is a
        #    privileged step (the real product does it via portal.wizard,
        #    which runs sudo) — so we mirror that with sudo() here.
        portal_group = env.ref("base.group_portal")
        env["res.users"].sudo().create({
            "name": "Jane Homeowner",
            "login": "jane.home@example.test",
            "password": "jane-strong-pw-1",
            "partner_id": customer.id,
            "group_ids": [(6, 0, [portal_group.id])],
        })

        # 3) Create the kitchen project (as the manager). date_target is
        #    left EMPTY on purpose — it exercises Odoo's false-for-empty
        #    serialization, the exact case the Flutter Project.fromJson
        #    coercion handles (review C1 / fix ae4e8d0).
        project = mgr["sb.kitchen.project"].create({
            "name": "Jane's Signature Kitchen",
            "partner_id": customer.id,
            "theme": "signature",
            "salesperson_id": sales_mgr.id,
        })

        # 4) Move into design and seed three concepts.
        project.action_start_designing()
        Option = mgr["sb.kitchen.design.option"]
        opt_a = Option.create({
            "project_id": project.id, "name": "Galley Bright",
            "estimated_price": 11800.0,
            "description": "<p>White slab doors, walnut island.</p>",
        })
        opt_b = Option.create({
            "project_id": project.id, "name": "Shaker Warm",
            "estimated_price": 13950.0,
            "description": "<p>Five-piece maple, brushed-brass pulls.</p>",
        })
        opt_c = Option.create({
            "project_id": project.id, "name": "Modern Matte",
            "estimated_price": 15600.0,
            "description": "<p>Handleless, matte graphite.</p>",
        })
        self.assertEqual(len(project.design_option_ids), 3)

        # 5) Submit to the customer for review.
        project.action_submit_to_customer()
        self.assertEqual(project.state, "awaiting_customer")

        # ============================================================
        # ACTOR 2 — CUSTOMER completes the journey via the Flutter API
        # ============================================================
        # 6) Login -> API key.
        login = self._api("/api/v1/auth/login", data={
            "email": "jane.home@example.test",
            "password": "jane-strong-pw-1",
        })
        self.assertEqual(login.status_code, 200, login.text)
        lbody = login.json()
        self.assertEqual(lbody["schema"], SCHEMA)
        key = lbody["api_key"]
        self.assertTrue(key, "login must return an api_key")

        # 7) /me works with the issued key.
        me = self._api("/api/v1/me", key=key)
        self.assertEqual(me.status_code, 200, me.text)

        # 8) List projects -> only Jane's own.
        plist = self._api("/api/v1/kitchen-projects", key=key)
        self.assertEqual(plist.status_code, 200, plist.text)
        projects = plist.json()["projects"]
        self.assertIn(project.id, [p["id"] for p in projects])
        summary = next(p for p in projects if p["id"] == project.id)
        # CONTRACT CHECK: empty date_target comes back as `false`, NOT null —
        # which is why a raw `as String?` cast on the Flutter side crashes.
        self.assertEqual(summary["date_target"], False)

        # 9) Project detail -> three concepts, nothing selected yet.
        detail = self._api(f"/api/v1/kitchen-projects/{project.id}", key=key)
        self.assertEqual(detail.status_code, 200, detail.text)
        d = detail.json()["project"]
        self.assertEqual(len(d["concept_ids"]), 3)
        self.assertIn(d["selected_design_option_id"], (None, False))

        # 10a) A corrupt/truncated upload (valid mime header, junk bytes)
        #      must be rejected cleanly as 422 invalid_image — not crash the
        #      AI pipeline with a 500.
        bad = self._api(
            f"/api/v1/kitchen-projects/{project.id}/photos", key=key,
            files={"photo": ("broken.png", b"\x89PNG\r\n\x1a\nnotreal", "image/png")},
            data={"prompt_template_code": "default_v1"},
        )
        self.assertEqual(bad.status_code, 422, bad.text)
        self.assertEqual(bad.json()["error"], "invalid_image")

        # 10b) Upload a real kitchen photo. The AI analysis step may be
        #      unconfigured in this environment, so accept either success
        #      (200) or analyze_failed (502) — both prove the upload path
        #      and that the attachment was stored.
        up = self._api(
            f"/api/v1/kitchen-projects/{project.id}/photos", key=key,
            files={"photo": ("kitchen.png", _KITCHEN_PHOTO, "image/png")},
            data={"prompt_template_code": "default_v1"},
        )
        self.assertIn(up.status_code, (200, 502), up.text)
        photo_attachments = env["ir.attachment"].sudo().search([
            ("res_model", "=", "sb.kitchen.project"),
            ("res_id", "=", project.id),
        ])
        self.assertTrue(photo_attachments, "photo attachment should exist")

        # 11) List concepts -> all three, descriptions present.
        clist = self._api(
            f"/api/v1/kitchen-projects/{project.id}/concepts", key=key)
        self.assertEqual(clist.status_code, 200, clist.text)
        concepts = clist.json()["concepts"]
        self.assertEqual(
            {c["name"] for c in concepts},
            {"Galley Bright", "Shaker Warm", "Modern Matte"},
        )
        # description_html is the contract key the Flutter fix now reads.
        self.assertTrue(all("description_html" in c for c in concepts))

        # 12) Select concept B.
        sel = self._api(
            f"/api/v1/kitchen-projects/{project.id}"
            f"/concepts/{opt_b.id}/select",
            key=key, data={},
        )
        self.assertEqual(sel.status_code, 200, sel.text)
        sbody = sel.json()
        self.assertTrue(sbody["ok"])
        self.assertEqual(sbody["selected_id"], opt_b.id)

        # 13) Detail now reflects the selection.
        detail2 = self._api(f"/api/v1/kitchen-projects/{project.id}", key=key)
        self.assertEqual(
            detail2.json()["project"]["selected_design_option_id"], opt_b.id)

        # 14) Approve.
        appr = self._api(
            f"/api/v1/kitchen-projects/{project.id}/approve", key=key,
            data={"notes": "Love the warm shaker — let's build it."},
        )
        self.assertEqual(appr.status_code, 200, appr.text)
        abody = appr.json()
        self.assertTrue(abody["ok"])
        self.assertEqual(abody["project_state"], "approved")

        # ============================================================
        # FINAL STATE — verified on the model side
        # ============================================================
        project.invalidate_recordset(["state"])
        self.assertEqual(project.state, "approved")
        opt_b.invalidate_recordset(["is_selected"])
        self.assertTrue(opt_b.is_selected)
        self.assertFalse(opt_a.is_selected)
        self.assertFalse(opt_c.is_selected)
        approvals = env["sb.kitchen.approval"].search([
            ("project_id", "=", project.id),
            ("approver_type", "=", "customer"),
        ])
        self.assertTrue(approvals, "a customer approval record should exist")
