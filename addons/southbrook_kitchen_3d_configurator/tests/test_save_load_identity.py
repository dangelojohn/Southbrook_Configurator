# SPDX-License-Identifier: LGPL-3.0-only
"""Save -> Load is identity — the canonical-model regression pin.

The tech lead's contract for the backend 3D configurator's persistence
API:

    save_design(items) -> load_design_lines() -> save_design(loaded
    items) -> canonical model is IDENTICAL.

This is NOT a renderer test and NOT a geometry-math test. It only
proves that a design the user has already saved survives being
re-opened (load_design_lines) and re-saved (save_design) without the
client touching anything — the exact "open a saved design and hit
Save" path a rep hits every time they revisit a quote.

Design: exercise the controller methods directly with a stubbed
`request`, same pattern as the sibling `test_wall_persistence.py` /
`test_save_design_acl.py` (itself copied from
`southbrook_estimating_website`'s `test_design_3d_add_new_wall.py`).
"""
from contextlib import contextmanager
from unittest.mock import MagicMock

from odoo.tests import TransactionCase, tagged

from odoo.addons.southbrook_kitchen_3d_configurator.controllers import (
    main as ctrl_main,
)


@contextmanager
def stubbed_request(env, user=None):
    saved = ctrl_main.request
    mock = MagicMock()
    mock.env = env if user is None else env(user=user.id)
    mock.session = {}
    mock.params = {}
    ctrl_main.request = mock
    try:
        yield mock
    finally:
        ctrl_main.request = saved


# Canonical-model snapshot fields — the identity contract is defined
# over exactly these. Sequence/id/name are deliberately excluded: `id`
# is checked separately (stability, not equality-with-a-value) and
# `sequence` is a save-order bookkeeping field, not part of the
# canonical selection the customer made.
_SNAPSHOT_FIELDS = (
    "layout_key", "product_id", "cabinet_type", "wall", "run_seq",
    "x_position_in", "y_position_in", "z_position_in", "rotation_deg",
    "pinned", "width_in", "height_in", "depth_in", "quantity",
    "price_unit",
)


@tagged("post_install", "-at_install", "southbrook",
        "southbrook_kitchen_3d_configurator", "save_load_identity")
class TestSaveLoadIdentity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner = cls.env["res.partner"].create({
            "name": "Save-Load Identity Test Customer",
            "email": "kitchen3d.identity@southbrook.test",
        })
        cls.design = cls.env["southbrook.kitchen.design"].create({
            "name": "Save-load identity test",
            "partner_id": cls.partner.id,
            "room_width_in": 144,
            "room_depth_in": 96,
            "room_height_in": 96,
        })

        # Two catalog-conforming cabinets — one base, one wall — same
        # creation recipe as test_wall_persistence.py / test_save_design_acl.py.
        cls.tmpl_base = cls.env["product.template"].create({
            "name": "Identity Test Base Cabinet",
            "type": "consu",
            "sale_ok": True,
            "list_price": 500.0,
        })
        cls.tmpl_base.southbrook_is_cabinet = True
        cls.tmpl_base.southbrook_cabinet_type = "base"
        cls.product_base = cls.tmpl_base.product_variant_id
        assert cls.product_base, "expected auto-created variant"

        cls.tmpl_wall = cls.env["product.template"].create({
            "name": "Identity Test Wall Cabinet",
            "type": "consu",
            "sale_ok": True,
            "list_price": 350.0,
        })
        cls.tmpl_wall.southbrook_is_cabinet = True
        cls.tmpl_wall.southbrook_cabinet_type = "wall"
        cls.product_wall = cls.tmpl_wall.product_variant_id
        assert cls.product_wall, "expected auto-created variant"

    def _controller(self):
        return ctrl_main.SouthbrookKitchenConfiguratorController()

    def _save(self, items):
        """Call save_design against cls.design and return (result, lines)."""
        controller = self._controller()
        with stubbed_request(self.env):
            result = controller.save_design(
                name=self.design.name,
                room={"width_in": 144, "depth_in": 96, "height_in": 96},
                items=items,
                partner_id=self.partner.id,
                design_id=self.design.id,
            )
        lines = self.env["southbrook.kitchen.design.line"].search([
            ("design_id", "=", self.design.id),
            ("origin", "=", "configurator"),
        ])
        return result, lines

    def _load(self):
        controller = self._controller()
        with stubbed_request(self.env):
            return controller.load_design_lines(design_id=self.design.id)

    def _snapshot(self, lines):
        """Sorted-by-layout_key list of canonical-field tuples — order
        can never flake the comparison."""
        rows = []
        for line in lines:
            rows.append(tuple(
                (line.product_id.id if f == "product_id" else getattr(line, f))
                for f in _SNAPSHOT_FIELDS
            ))
        return sorted(rows, key=lambda row: row[_SNAPSHOT_FIELDS.index("layout_key")])

    def _initial_items(self):
        """>= 3 items covering variety: base + wall cabinet_types,
        distinct walls, a pinned item with nonzero rotation, distinct
        layout_keys/positions/dimensions."""
        return [
            {
                "product_id":    self.product_base.id,
                "layout_key":    "identity-base-1",
                "wall":          "back",
                "x_position_in": 0,
                "y_position_in": 0,
                "z_position_in": 0,
                "rotation_deg":  0,
                "pinned":        False,
                "width_in":      24.0,
                "height_in":     34.5,
                "depth_in":      24.0,
                "price":         500.0,
            },
            {
                "product_id":    self.product_wall.id,
                "layout_key":    "identity-wall-1",
                "wall":          "left",
                "x_position_in": 10,
                "y_position_in": 0,
                "z_position_in": 54,
                "rotation_deg":  0,
                "pinned":        False,
                "width_in":      18.0,
                "height_in":     30.0,
                "depth_in":      12.0,
                "price":         350.0,
            },
            {
                # Second base cabinet, PINNED with a nonzero rotation —
                # the smart-pinning path (v19.0.4.20.0) round-trips
                # through the same save/load cycle and must survive it
                # too.
                "product_id":    self.product_base.id,
                "layout_key":    "identity-base-2",
                "wall":          "right",
                "x_position_in": 42,
                "y_position_in": 0,
                "z_position_in": 0,
                "rotation_deg":  90,
                "pinned":        True,
                "width_in":      30.0,
                "height_in":     34.5,
                "depth_in":      24.0,
                "price":         520.0,
            },
        ]

    # ------------------------------------------------------------------
    def test_save_load_save_is_identity(self):
        """save_design -> load_design_lines -> save_design(loaded) must
        reproduce the exact same canonical model: same line count, same
        layout_keys, field-for-field equality, and stable line ids (no
        unnecessary unlink/recreate)."""
        result1, lines1 = self._save(self._initial_items())
        self.assertNotIn("error", result1, f"unexpected error: {result1}")
        self.assertEqual(len(lines1), 3)
        snapshot1 = self._snapshot(lines1)
        ids1 = set(lines1.ids)

        loaded = self._load()
        self.assertEqual(len(loaded["lines"]), 3)

        # Simulate a user opening the hydrated design and hitting Save
        # without touching anything: feed the loaded line dicts straight
        # back in as `items`.
        result2, lines2 = self._save(loaded["lines"])
        self.assertNotIn("error", result2, f"unexpected error: {result2}")
        self.assertEqual(len(lines2), 3)
        snapshot2 = self._snapshot(lines2)
        ids2 = set(lines2.ids)

        self.assertEqual(
            snapshot2, snapshot1,
            "save -> load -> save must reproduce an IDENTICAL canonical "
            "model (field-for-field, sorted by layout_key)",
        )
        self.assertEqual(
            ids2, ids1,
            "save_design writes existing configurator lines by "
            "layout_key — re-saving a hydrated design must update the "
            "SAME line ids, never unlink+recreate them",
        )

        # Third round for good measure — the cycle must be a fixed
        # point, not just stable for one extra hop.
        loaded_again = self._load()
        result3, lines3 = self._save(loaded_again["lines"])
        self.assertNotIn("error", result3, f"unexpected error: {result3}")
        self.assertEqual(self._snapshot(lines3), snapshot1)
        self.assertEqual(set(lines3.ids), ids1)

    # ------------------------------------------------------------------
    # PR3.0 — y/z field-semantics migration. Save/load identity is a
    # field-preserving contract regardless of which field a value lives
    # in, but this pins it explicitly for the CANONICAL post-migration
    # shape: a wall-type upper carrying its mount height in
    # y_position_in (nonzero) with z_position_in flush at 0 — the
    # opposite of the pre-PR3.0 fixture above (which used the legacy
    # z-as-height shape, itself still a valid round-trip case since
    # save/load never interprets these fields, only persists them).
    def test_save_load_save_is_identity_with_canonical_wall_mount_height(self):
        items = [
            {
                "product_id":    self.product_wall.id,
                "layout_key":    "identity-wall-canonical-1",
                "wall":          "back",
                "x_position_in": 12,
                "y_position_in": 66,   # canonical: mount height lives in y
                "z_position_in": 0,    # canonical: flush to the back wall
                "rotation_deg":  0,
                "pinned":        False,
                "width_in":      18.0,
                "height_in":     30.0,
                "depth_in":      12.0,
                "price":         350.0,
            },
        ]
        result1, lines1 = self._save(items)
        self.assertNotIn("error", result1, f"unexpected error: {result1}")
        self.assertEqual(len(lines1), 1)
        self.assertEqual(lines1[0].y_position_in, 66)
        self.assertEqual(lines1[0].z_position_in, 0)
        snapshot1 = self._snapshot(lines1)
        ids1 = set(lines1.ids)

        loaded = self._load()
        self.assertEqual(len(loaded["lines"]), 1)
        self.assertEqual(loaded["lines"][0]["y_position_in"], 66)
        self.assertEqual(loaded["lines"][0]["z_position_in"], 0)

        result2, lines2 = self._save(loaded["lines"])
        self.assertNotIn("error", result2, f"unexpected error: {result2}")
        self.assertEqual(self._snapshot(lines2), snapshot1)
        self.assertEqual(set(lines2.ids), ids1)
