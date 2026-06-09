# SPDX-License-Identifier: LGPL-3.0-only
"""G1 — BoM-contents parity gate.

The single most important safety test on the platform. Asserts that the
canonical 7-panel formulas in `shared/southbrook_dims.py` (mounted at
/srv/shared via the docker-compose PYTHONPATH bind) produce byte-identical
geometry to `southbrook_estimating.models.mrp_bom._compute_panel_dimensions`
for a battery of canonical cabinet shapes.

This is the contract the init doc Module 2 GATE — CRITICAL G1 stipulates:
no FreeCAD-bridge deployment until this gate passes.

Why this matters:

* The FreeCAD bridge renders DXF / SVG / STEP from `shared.southbrook_dims`.
* The Odoo BoM math runs from `southbrook_estimating.mrp_bom`.
* If these diverge by even 0.001 mm the customer's 3D preview, the shop
  cut list, and the rendered drawings will silently disagree. That class
  of bug is invisible until manufactured panels don't fit, which is the
  most expensive failure mode this project can have.

The G2 (Peter Tuschak panel-formula sign-off) closed 2026-06-09. From now
on the only way these two sources of truth diverge is by code drift, and
this test is the tripwire.

Tagged `g1` so CI / dev can run just this gate: `--test-tags g1`.
"""
from odoo.tests.common import TransactionCase, tagged

# /srv/shared on PYTHONPATH (set in docker-compose.yml).
from southbrook_dims import (
    BOX_TH as SHARED_BOX_TH,
    BACK_TH as SHARED_BACK_TH,
    RABBET as SHARED_RABBET,
    DOOR_TH as SHARED_DOOR_TH,
    DOOR_REVEAL as SHARED_DOOR_REVEAL,
    SHELF_TOL as SHARED_SHELF_TOL,
    SHELF_VENT_GAP as SHARED_SHELF_VENT_GAP,
    TOEKICK_H as SHARED_TOEKICK_H,
    TOEKICK_FAMILIES as SHARED_TOEKICK_FAMILIES,
    panel_cut_list as shared_panel_cut_list,
)

# southbrook_estimating's authoritative implementation.
from odoo.addons.southbrook_estimating.models.mrp_bom import (
    BOX_TH as EST_BOX_TH,
    BACK_TH as EST_BACK_TH,
    RABBET as EST_RABBET,
    DOOR_TH as EST_DOOR_TH,
    DOOR_REVEAL as EST_DOOR_REVEAL,
    SHELF_TOL as EST_SHELF_TOL,
    SHELF_VENT_GAP as EST_SHELF_VENT_GAP,
    TOEKICK_H as EST_TOEKICK_H,
    TOEKICK_FAMILIES as EST_TOEKICK_FAMILIES,
)


# Canonical cabinet shapes — same set as test_bom_math.py uses, expressed
# in mm directly. Each tuple is (width, height, depth, family, door_count).
CANONICAL_SHAPES = [
    # 12in x 30in x 24in narrow base, 1-door
    (304.8, 762.0, 609.6, "base", 1),
    # 33in x 30in x 24in wide base, 2-door
    (838.2, 762.0, 609.6, "base", 2),
    # 24in x 84in x 24in tall pantry, 2-door, 3 shelves
    (609.6, 2133.6, 609.6, "tall", 2),
    # 30in x 30in x 12in wall, 2-door (depth variation)
    (762.0, 762.0, 304.8, "wall", 2),
    # 600x720x580 default base, 2-door (round metric sanity check)
    (600.0, 720.0, 580.0, "base", 2),
    # 9in x 30in x 24in narrow base, 1-door (small-width boundary)
    (228.6, 762.0, 609.6, "base", 1),
    # 36in x 36in x 24in mid-base, 2-door
    (914.4, 914.4, 609.6, "base", 2),
]


@tagged("post_install", "-at_install", "southbrook", "g1", "bom_contents")
class TestBomContentsG1(TransactionCase):
    """G1 — parity gate between shared/southbrook_dims and southbrook_estimating."""

    # ------------------------------------------------------------------
    # Constants parity
    # ------------------------------------------------------------------
    def test_constants_parity(self):
        """Every geometric constant must agree byte-for-byte."""
        self.assertEqual(SHARED_BOX_TH, EST_BOX_TH, "BOX_TH divergence")
        self.assertEqual(SHARED_BACK_TH, EST_BACK_TH, "BACK_TH divergence")
        self.assertEqual(SHARED_RABBET, EST_RABBET, "RABBET divergence")
        self.assertEqual(SHARED_DOOR_TH, EST_DOOR_TH, "DOOR_TH divergence")
        self.assertEqual(SHARED_DOOR_REVEAL, EST_DOOR_REVEAL, "DOOR_REVEAL divergence")
        self.assertEqual(SHARED_SHELF_TOL, EST_SHELF_TOL, "SHELF_TOL divergence")
        self.assertEqual(
            SHARED_SHELF_VENT_GAP, EST_SHELF_VENT_GAP, "SHELF_VENT_GAP divergence"
        )
        self.assertEqual(SHARED_TOEKICK_H, EST_TOEKICK_H, "TOEKICK_H divergence")
        self.assertEqual(
            SHARED_TOEKICK_FAMILIES, EST_TOEKICK_FAMILIES,
            "TOEKICK_FAMILIES set divergence",
        )

    # ------------------------------------------------------------------
    # Panel-by-panel parity across canonical shapes
    # ------------------------------------------------------------------
    def test_panel_parity_across_canonical_shapes(self):
        """For every canonical shape, every panel in shared.panel_cut_list
        must equal the corresponding output of estimating's
        _compute_panel_dimensions."""
        MrpBom = self.env["mrp.bom"]
        for width, height, depth, family, door_count in CANONICAL_SHAPES:
            shape_id = f"{family}-{int(width)}x{int(height)}x{int(depth)}-{door_count}dr"
            with self.subTest(shape=shape_id):
                shared = shared_panel_cut_list(
                    width, height, depth, family=family, door_count=door_count
                )
                est = MrpBom._compute_panel_dimensions(
                    width_mm=width,
                    height_mm=height,
                    depth_mm=depth,
                    family=family,
                    door_count=door_count,
                )

                # Tuples should match exactly (re-derivation, not approximate).
                for key in ("side_L", "side_R", "top", "bottom", "back", "door"):
                    self.assertEqual(
                        shared[key], est[key],
                        f"{shape_id}: {key} divergence — "
                        f"shared={shared[key]} estimating={est[key]}",
                    )

                # Shelf parity — note key rename: shared uses
                # `adjustable_shelf` while estimating still uses `shelf`.
                # The G1 contract is on the *value*, not the key name.
                self.assertEqual(
                    shared["adjustable_shelf"], est["shelf"],
                    f"{shape_id}: adjustable shelf divergence",
                )
                self.assertEqual(
                    shared["shelf_count"], est["shelf_count"],
                    f"{shape_id}: shelf_count divergence",
                )

                # Door count must round-trip even when door==None.
                self.assertEqual(
                    shared["door_count"], est["door_count"],
                    f"{shape_id}: door_count divergence",
                )

    # ------------------------------------------------------------------
    # Toe-kick: still integrated, never a separate cut
    # ------------------------------------------------------------------
    def test_toe_kick_remains_integrated(self):
        """shared.toe_kick MUST return a metadata descriptor (not a panel cut)
        for any toekick family. If a future refactor turns the toe kick into a
        separate panel cut, this test fails — forcing the manufacturing-flow
        review the change requires."""
        for fam in ("base", "sink", "tall", "vanity"):
            with self.subTest(family=fam):
                shared = shared_panel_cut_list(600, 720, 580, family=fam, door_count=1)
                tk = shared["toe_kick"]
                self.assertIsNotNone(tk, f"toe_kick missing for family={fam}")
                self.assertIsInstance(tk, dict, f"toe_kick must be a metadata dict for {fam}")
                self.assertTrue(
                    tk.get("integrated_into_sides"),
                    f"toe_kick for {fam} must declare integrated_into_sides=True",
                )

        for fam in ("wall", "drawer", "accessory", "worktop"):
            with self.subTest(family=fam):
                shared = shared_panel_cut_list(600, 720, 580, family=fam, door_count=1)
                self.assertIsNone(
                    shared["toe_kick"],
                    f"toe_kick must be None for non-toe-kick family {fam}",
                )

    # ------------------------------------------------------------------
    # Hardware counts are NOT covered by G1
    # ------------------------------------------------------------------
    # By design — the shared dims module is a GEOMETRY contract. Hardware
    # quantities are an estimating concern and stay in mrp_bom.py. If you
    # find yourself adding a hardware-count assertion to this file, it
    # belongs in addons/southbrook_estimating/tests/ instead.
