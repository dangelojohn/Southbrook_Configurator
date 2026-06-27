# SPDX-License-Identifier: LGPL-3.0-only
"""W079 (R4.S8) — cut-spec version stamp tests.

JTBD: warranty trace must distinguish two cabinets built under
different cut specs. Version auto-increments on geometric edits
only, NOT on chatter / name / state / active flips.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "plm", "w079")
class TestW079CutSpecVersion(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.CutSpec = cls.env["southbrook.cut.spec"]

    def test_version_field_present(self):
        f = self.CutSpec._fields.get("version")
        self.assertIsNotNone(f, "W079 version field missing")
        self.assertEqual(f.type, "integer")
        self.assertTrue(f.readonly)
        # default=1
        spec = self.CutSpec.create({"name": "W079 baseline"})
        self.assertEqual(spec.version, 1)

    def test_version_bumps_on_geometric_write(self):
        spec = self.CutSpec.create({"name": "W079 bump test"})
        self.assertEqual(spec.version, 1)
        # door_reveal is in CONSTANT_FIELDS — bumps.
        spec.write({"door_reveal": 2.5})
        self.assertEqual(spec.version, 2,
                         "geometric write must bump version")
        spec.write({"box_th": 16.0})
        self.assertEqual(spec.version, 3,
                         "second geometric write must bump again")

    def test_version_does_not_bump_on_bookkeeping_write(self):
        spec = self.CutSpec.create({"name": "W079 no-bump test"})
        v0 = spec.version
        # Non-geometric fields — name, note, active. These are
        # bookkeeping, not geometric truth; must NOT bump.
        spec.write({"name": "Renamed"})
        self.assertEqual(spec.version, v0,
                         "name edit must not bump version")
        spec.write({"note": "added provenance"})
        self.assertEqual(spec.version, v0,
                         "note edit must not bump version")
        spec.write({"active": False})
        self.assertEqual(spec.version, v0,
                         "active flip must not bump version")

    def test_version_idempotent_write(self):
        """Writing the same value to a geometric field is a no-op
        for the version (no bump)."""
        spec = self.CutSpec.create({
            "name": "W079 idempotent",
            "door_reveal": 3.0,
        })
        v0 = spec.version
        spec.write({"door_reveal": 3.0})  # same value
        self.assertEqual(spec.version, v0,
                         "idempotent write must not bump version")
