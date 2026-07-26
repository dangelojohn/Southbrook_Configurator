# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo.exceptions import AccessError
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
        with self.assertRaises(AccessError):
            self.env["production.media"].with_user(user).upload_media(
                "mrp.production", mo.id, "x.jpg", "eA==", "image/jpeg"
            )

    def test_portal_and_public_denied_direct_model_access(self):
        """Task C10: CONFIRMED leak (task-C10-security-verify.md) -- upstream
        `dms` grants base.group_portal/base.group_public model-level
        perm_read=1 on dms.file/dms.directory, and an Odoo-19 regression in
        dms.security.mixin._get_permission_domain() makes the record-level
        ir.rule contribute NO restriction for ANY caller, so a portal or
        public user could previously read production media directly via
        search()/browse().read(), bypassing the production.media RPC layer
        entirely. This module's security/ir.model.access.csv overrides the
        four upstream ACL rows (dms.access_dms_file_portal/_public,
        dms.access_dms_directory_portal/_public) down to perm_read=0. That
        is a plain group-membership ACL check with no computed fields and
        no ir.rule domain evaluation, so it is immune to the upstream bug
        and denies access before the broken ir.rule is ever reached.

        A denied model-level read raises AccessError immediately from
        search()/read() (ir.model.access.check) -- there is no "empty
        result" case once perm_read=0 applies to every group the user
        belongs to, so this asserts AccessError for both search and read,
        on both models, for both portal and public.
        """
        portal = self.env.ref("base.group_portal")
        public = self.env.ref("base.group_public")
        portal_user = self.env["res.users"].create(
            {"name": "Portal Leak Check", "login": "c10_portal", "group_ids": [(6, 0, [portal.id])]}
        )
        public_user = self.env["res.users"].create(
            {"name": "Public Leak Check", "login": "c10_public", "group_ids": [(6, 0, [public.id])]}
        )
        mo, f = self._make_file()
        directory = f.directory_id

        for user in (portal_user, public_user):
            file_env = self.env["dms.file"].with_user(user)
            dir_env = self.env["dms.directory"].with_user(user)
            with self.assertRaises(AccessError, msg="%s must not search dms.file" % user.login):
                file_env.search([])
            with self.assertRaises(AccessError, msg="%s must not read dms.file content" % user.login):
                file_env.browse(f.id).read(["name", "content"])
            with self.assertRaises(AccessError, msg="%s must not search dms.directory" % user.login):
                dir_env.search([])
            with self.assertRaises(AccessError, msg="%s must not read dms.directory" % user.login):
                dir_env.browse(directory.id).read(["name"])

    def test_normal_internal_user_can_annotate_and_qc_own_accessible_media(self):
        """Task C10 (decided access-scope change): a normal internal user
        -- plain manufacturing "User" (``mrp.group_mrp_user``), i.e. someone
        who can write to the MO but is NEITHER a ``group_dms_user`` NOR a
        ``group_media_manager`` / DMS manager -- must be able to
        set_qc_status/save_annotation on media anchored to a business
        record (mrp.production) they can write to. (``mrp.group_mrp_user``
        is the minimal real-world group that actually grants write access
        to ``mrp.production`` -- see mrp/security/ir.model.access.csv;
        ``base.group_user`` alone has no ACL row on that model at all, so a
        bare-``base.group_user`` account could never reach this code path
        for an MO regardless of this fix.)

        dms.file's own upstream ACL denies perm_write to plain
        base.group_user (only group_dms_user/group_dms_manager get
        perm_write=1), so this only works because
        dms_file.py::_sb_scoped_metadata_write() gates on the *anchored
        record*'s write access (mirroring production.media.upload_media())
        and then writes the metadata field under sudo() -- never touching
        the binary `content` field.

        NOTE: this intentionally does not test cross-record isolation
        between two different internal users on two different MOs -- see
        the KNOWN LIMITATION docstring on _sb_scoped_metadata_write() and
        task-C10-security-verify.md: the upstream dms record-rule bug means
        that isolation does not hold today for internal users in general,
        independent of this change, and fixing it is out of scope here.
        """
        mo, f = self._make_file()
        internal_user = self.env["res.users"].create(
            {
                "name": "Plain Manufacturing User",
                "login": "c10_internal",
                "group_ids": [
                    (6, 0, [self.env.ref("base.group_user").id, self.env.ref("mrp.group_mrp_user").id])
                ],
            }
        )
        before = len(mo.message_ids)
        f.with_user(internal_user).action_set_qc_status("pass")
        self.assertEqual(f.qc_status, "pass")
        f.with_user(internal_user).action_save_annotation('{"strokes": [1]}')
        self.assertEqual(f.annotation_data, '{"strokes": [1]}')
        self.assertGreater(
            len(mo.message_ids), before, "should post chatter audit notes for the internal user's actions"
        )
