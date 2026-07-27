# SPDX-License-Identifier: LGPL-3.0-only
"""Defect C9 (confirmed by live repro, 2026-07-26) — the first cabinet
dropped on a brand-new wall must trigger corner resolution exactly like any
later cabinet on that wall, not be exempted from it.

Prior bug (introduced by the 2026-07-12 "Task 3" gate, commit 5f15786):
southbrook_api_design_3d_add() captured `wall_had_cabinets` BEFORE creating
the new line and gated the walls_used>=2 -> action_auto_arrange() branch on
it, so the FIRST cabinet placed on a brand-new wall was never eligible for
resolution on the same call. Consequence: the bare engine laid that first
cabinet down at the start of its wall's run, physically interpenetrating the
adjacent wall's cabinets in the shared corner cell, and no corner cabinet was
substituted until a SECOND cabinet landed on the same wall.

The gate existed only to dodge a "vanishing cabinet" UX bug: resolving AND
still returning the plain `item` shape meant the client rendered nothing,
because resolution can archive the very line the response claimed to
describe. The real fix (applied in controllers/main.py) is to always return
the RE-LAID payload whenever resolution runs — design_tab already replaces
the whole scene on `res.relaid` + `res.payload`, so the user simply sees
their cabinet become/join the corner arrangement; nothing "vanishes".

These tests now lock the CORRECT behavior: resolution runs (and the relaid
payload comes back) on the very first cabinet added to a second wall, the
canonical cabinets it supersedes are archived (never deleted), and no active
cabinet's world footprint physically overlaps another's afterward.
"""
from contextlib import contextmanager
from unittest.mock import MagicMock

from odoo.tests import TransactionCase, tagged

from odoo.addons.southbrook_estimating.models import kitchen_layout_engine
from odoo.addons.southbrook_estimating_website.controllers import main as ctrl_main


@contextmanager
def stubbed_request(env, user=None):
    saved = ctrl_main.request
    mock = MagicMock()
    mock.env = env if user is None else env(user=user.id)
    mock.session = {}
    mock.params = {}
    mock.httprequest.args = {}
    ctrl_main.request = mock
    try:
        yield mock
    finally:
        ctrl_main.request = saved


# COORDINATE_CONTRACT.md (southbrook_estimating/models/) — the engine's raw
# placements use a CENTRED along-wall convention (`footprint_mm`); what gets
# persisted to southbrook.kitchen.design.line uses the back-left-bottom
# ANCHOR convention, validated by `footprint_from_anchor_mm`. A concurrent
# workstream is migrating the ORM write boundary to always convert via
# `anchor_pose_mm` before persisting (the contract already mandates it).
# Resolve the validator defensively so this test passes whichever convention
# is actually landed on disk when it runs: prefer the anchor-side helper,
# fall back to the engine-internal one if it isn't present yet.
_FOOTPRINT_FN = getattr(
    kitchen_layout_engine, "footprint_from_anchor_mm", None,
) or kitchen_layout_engine.footprint_mm

_MM_PER_IN = 25.4


def _footprint_3d_in(line):
    """(x0, x1, y0, y1, z0, z1) world AABB of a persisted design line, in
    inches, combining the pure engine's horizontal footprint helper with the
    line's own vertical (y) extent."""
    cab = {
        "width_mm": (line.width_in or 0.0) * _MM_PER_IN,
        "depth_mm": (line.depth_in or 0.0) * _MM_PER_IN,
    }
    place = {
        "x": (line.x_position_in or 0.0) * _MM_PER_IN,
        "z": (line.z_position_in or 0.0) * _MM_PER_IN,
        "rotation_deg": line.rotation_deg or 0.0,
    }
    x0, x1, z0, z1 = _FOOTPRINT_FN(cab, place)
    y0 = line.y_position_in or 0.0
    y1 = y0 + (line.height_in or 0.0)
    return (x0 / _MM_PER_IN, x1 / _MM_PER_IN, y0, y1,
            z0 / _MM_PER_IN, z1 / _MM_PER_IN)


def _aabb_overlap(a, b, eps=0.05):
    """True if two (x0,x1,y0,y1,z0,z1) inch boxes physically interpenetrate
    (overlap on all three axes) — i.e. a real, non-coincident collision, not
    two cabinets merely sharing a wall/floor. `eps` (inches) tolerates
    touching-but-not-overlapping edges (adjacent cabinets in a run)."""
    ax0, ax1, ay0, ay1, az0, az1 = a
    bx0, bx1, by0, by1, bz0, bz1 = b
    return (ax0 < bx1 - eps and bx0 < ax1 - eps
            and ay0 < by1 - eps and by0 < ay1 - eps
            and az0 < bz1 - eps and bz0 < az1 - eps)


def _assert_no_active_overlaps(test, lines):
    """Pairwise 3D AABB check across every active line with a real
    footprint (width/depth both set). Catches defect C9's actual symptom —
    a newly-placed cabinet interpenetrating the adjacent wall's run in the
    shared corner cell — without assuming which vertical "layer" a
    cabinet_type=='corner' derived line belongs to (base-height and
    wall-height corners share the same cabinet_type, so bucketing by type
    would be wrong; a real 3D box check is not)."""
    footed = [l for l in lines if l.width_in and l.depth_in]
    boxes = [_footprint_3d_in(l) for l in footed]
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            test.assertFalse(
                _aabb_overlap(boxes[i], boxes[j]),
                "active cabinets physically overlap: "
                f"{footed[i].display_name} (id={footed[i].id}) {boxes[i]} "
                f"vs {footed[j].display_name} (id={footed[j].id}) {boxes[j]}")


@tagged("post_install", "-at_install", "southbrook", "southbrook_design_3d")
class TestDesign3dAddNewWall(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Design = cls.env["southbrook.kitchen.design"]
        cls.controller = ctrl_main.SouthbrookOrderBuilderPortal()

        cls.partner = cls.env["res.partner"].create({
            "name": "Design3D NewWall Customer",
            "email": "design3d.newwall@southbrook.test",
        })
        portal_group = cls.env.ref("base.group_portal")
        cls.user = cls.env["res.users"].create({
            "name": "Design3D NewWall Customer",
            "login": "design3d.newwall@southbrook.test",
            "partner_id": cls.partner.id,
            "group_ids": [(6, 0, [portal_group.id])],
        })

        # Fresh, catalog-conforming cabinet template — do NOT rely on
        # demo/live-DB product refs (see test_track_b_end_to_end.py's
        # _make_cabinet_template: a shared dev DB's demo product variants
        # are not a stable fixture to build unit tests against).
        # default_code MUST match a key in product_config_line._SKU_DEFAULTS
        # — the order-seed route (_southbrook_seed_design_lines) looks the
        # product up by SKU prefix and silently skips non-matching lines.
        base_tmpl = cls.env["product.template"].create({
            "name":         "Task3 Test Base Cabinet",
            "default_code": "SB-BASE-1DR",
            "type":         "consu",
            "sale_ok":      True,
            "list_price":   500.0,
        })
        base_tmpl.write({
            "southbrook_is_cabinet":   True,
            "southbrook_cabinet_type": "base",
            "southbrook_width_in":     24.0,
            "southbrook_height_in":    34.5,
            "southbrook_depth_in":     24.0,
        })
        cls.base_product = base_tmpl.product_variant_id

        # One back-wall configurator cabinet already on the order — seeded
        # via the design get-or-create route so it lands as a "back" line,
        # exactly like a real session that already has a back run.
        cls.order = cls.env["sale.order"].create({
            "partner_id": cls.partner.id,
            "order_line": [
                (0, 0, {"product_id": cls.base_product.id,
                        "product_uom_qty": 1,
                        "name": cls.base_product.display_name,
                        "zone": "base_run"}),
            ],
        })
        with stubbed_request(cls.env, user=cls.user):
            cls.controller.southbrook_api_design_3d(cls.order.id)
        cls.design = cls.Design.search(
            [("sale_order_id", "=", cls.order.id)], limit=1)
        # Sanity: the seed produced exactly one configurator cabinet, on back.
        back_lines = cls.design.cabinet_line_ids.filtered(
            lambda l: l.origin == "configurator")
        assert len(back_lines) == 1
        assert (back_lines.wall or "back") == "back"

    # ------------------------------------------------------------------
    def test_first_cabinet_on_new_wall_triggers_resolution(self):
        """First LEFT cabinet, back cabinet already present: the design now
        spans 2 walls, so this add must resolve the corner and come back
        RELAID (never the plain-item shape that used to leave the new
        cabinet interpenetrating the back run in the shared corner cell)."""
        canonical_before = len(
            self.design.with_context(active_test=False).cabinet_line_ids
            .filtered(lambda l: l.layout_role != "derived"))

        with stubbed_request(self.env, user=self.user):
            res = self.controller.southbrook_api_design_3d_add(
                self.order.id, product_id=self.base_product.id, wall="left")

        self.assertNotIn("error", res, f"unexpected error: {res}")
        self.assertTrue(res.get("relaid"), f"expected relaid response: {res}")
        self.assertIn("payload", res, res)

        self.design.invalidate_recordset()
        all_lines = self.design.with_context(active_test=False).cabinet_line_ids

        # A derived corner cabinet now exists.
        corner_lines = all_lines.filtered(
            lambda l: l.layout_role == "derived" or l.cabinet_type == "corner")
        self.assertTrue(
            corner_lines,
            "resolving a design that now spans 2 walls must insert a "
            "derived corner cabinet")

        # The canonical cabinets corner resolution superseded are ARCHIVED,
        # never deleted — the canonical row count only grows by the one new
        # (left) cabinet this call created; nothing canonical is unlinked.
        canonical_after = all_lines.filtered(lambda l: l.layout_role != "derived")
        self.assertEqual(
            len(canonical_after), canonical_before + 1,
            "canonical lines must never be deleted by resolution — only "
            "archived (active=False) or repositioned")
        archived_canonical = canonical_after.filtered(lambda l: not l.active)
        self.assertTrue(
            archived_canonical,
            "at least one canonical cabinet (superseded by the new corner) "
            "must be archived, not left both active and overlapping")

        # No ACTIVE cabinet's world footprint physically overlaps another's.
        _assert_no_active_overlaps(self, self.design.cabinet_line_ids)

    def test_second_cabinet_on_occupied_wall_can_trigger_resolution(self):
        """A second LEFT cabinet, added right after the first LEFT cabinet
        (which already resolves the design into a corner — see the test
        above), is allowed to reach the relaid/auto-arrange path again and
        must not error. TransactionCase rolls back between tests, so this
        test's own setup (seeded once in setUpClass: one back cabinet) is
        independent of the other test's outcome."""
        with stubbed_request(self.env, user=self.user):
            first = self.controller.southbrook_api_design_3d_add(
                self.order.id, product_id=self.base_product.id, wall="left")
            self.assertNotIn("error", first, first)

            second = self.controller.southbrook_api_design_3d_add(
                self.order.id, product_id=self.base_product.id, wall="left")

        self.assertNotIn("error", second, f"unexpected error: {second}")
        # Either shape is acceptable here (resolution is now ALLOWED, not
        # mandatory in every case), but if it took the relaid path it must
        # not have errored and must return a payload.
        if second.get("relaid"):
            self.assertIn("payload", second)
        else:
            self.assertIn("item", second)
