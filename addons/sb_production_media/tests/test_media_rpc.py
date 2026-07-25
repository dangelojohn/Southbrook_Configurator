# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sb_media")
class TestMediaRpc(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # dms_field's create() gates its auto-directory creation off during
        # --test-enable runs unless this context flag is set. See
        # dms_field/models/dms_field_mixin.py and sb_production_media's
        # tests/test_bridge.py for the same setup.
        cls.env = cls.env(context=dict(cls.env.context, test_dms_field=True))

    def _make_file(self):
        mo = self.env["mrp.production"].create(
            {"product_id": self.env["product.product"].create({"name": "X"}).id}
        )
        mo.invalidate_recordset(["dms_directory_ids"])
        d = mo.dms_directory_ids[:1]
        return mo, self.env["dms.file"].create(
            {"name": "shot.jpg", "directory_id": d.id, "content": "eA=="}
        )

    def test_qc_status_and_audit(self):
        mo, f = self._make_file()
        before = len(mo.message_ids)
        f.action_set_qc_status("flag")
        self.assertEqual(f.qc_status, "flag")
        self.assertGreater(len(mo.message_ids), before, "should post a chatter audit note")

    def test_save_annotation_is_non_destructive(self):
        """Annotation is stored alongside the file without altering content."""
        mo, f = self._make_file()
        original_content = f.content
        before = len(mo.message_ids)
        f.action_save_annotation('{"strokes": []}')
        self.assertEqual(f.annotation_data, '{"strokes": []}')
        self.assertEqual(f.content, original_content)
        self.assertGreater(len(mo.message_ids), before, "should post a chatter audit note")

    def test_rpc_roundtrip(self):
        """Task C9: the narrow production.media RPC surface used by the
        Process Explorer QC panel -- upload, list, and set QC status,
        without any kitchen-specific logic (generic res_model/res_id)."""
        p = self.env["product.product"].create({"name": "Z"})
        mo = self.env["mrp.production"].create({"product_id": p.id})
        pm = self.env["production.media"]
        fid = pm.upload_media("mrp.production", mo.id, "a.jpg", "eA==", "image/jpeg")
        data = pm.get_node_media("mrp.production", mo.id)
        self.assertTrue(any(f["id"] == fid for f in data["files"]))
        self.assertTrue(pm.set_qc_status(fid, "pass"))

    def test_no_anchor_skips_chatter_gracefully(self):
        """A file whose directory has no res_model/res_id anchor (e.g. a
        structural subfolder) must not crash when QC status is set."""
        mo, f = self._make_file()
        structural_dir = self.env["dms.directory"].create(
            {
                "name": "Structural",
                "parent_id": f.directory_id.id,
                "storage_id": f.directory_id.storage_id.id,
            }
        )
        f2 = self.env["dms.file"].create(
            {"name": "shot2.jpg", "directory_id": structural_dir.id, "content": "eA=="}
        )
        f2.action_set_qc_status("pass")
        self.assertEqual(f2.qc_status, "pass")

    def test_internal_only(self):
        """Task C10: a PORTAL user must never be able to upload production
        media -- ``upload_media`` checks write access on the *anchored*
        business record (mrp.production here) before doing anything else,
        and portal has no access to mrp.production, so this must raise
        AccessError. This is a regression guard: C9's ``record.check_access
        ("write")`` call already enforced this before the C10 security
        files existed; C10 additionally makes the module's own access
        model explicit (Production Media Manager group + ACL rows)."""
        portal = self.env.ref("base.group_portal")
        user = self.env["res.users"].create(
            {"name": "P", "login": "p_media", "group_ids": [(6, 0, [portal.id])]}
        )
        p = self.env["product.product"].create({"name": "Q"})
        mo = self.env["mrp.production"].create({"product_id": p.id})
        from odoo.exceptions import AccessError

        with self.assertRaises(AccessError):
            self.env["production.media"].with_user(user).upload_media(
                "mrp.production", mo.id, "x.jpg", "eA==", "image/jpeg"
            )
