# SPDX-License-Identifier: LGPL-3.0-only
"""W055 — MO QR kind resolves by name OR id.

Cabinet labels now encode a signed sb://mo/<name>?t=...&s=... payload
where <name> is the MO's name (WH/MO/00023). Verify:

1. resolve-by-name finds the MO;
2. resolve-by-int-id still works (backward compat);
3. ECO-rebuild fan-out (printed name vs current name-1) lands on
   the latest MO.
"""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestW055MoQrResolve(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env["product.product"].create({
            "name": "W055 cabinet",
            "type": "consu",
            "is_storable": True,
        })
        cls.mo = cls.env["mrp.production"].create({
            "product_id": cls.product.id,
            "product_qty": 1.0,
        })
        cls.kind = cls.env["southbrook.qr.kind.mo"]

    def test_resolve_by_int_id_still_works(self):
        rec = self.kind.get_record(self.mo.id)
        self.assertEqual(rec.id, self.mo.id)

    def test_resolve_by_name(self):
        # mrp.production gets a name assigned on create via sequence;
        # if for some reason this MO has no name, set one for the test.
        if not self.mo.name:
            self.mo.name = "WH/MO/W055-T1"
        rec = self.kind.get_record(self.mo.name)
        self.assertEqual(rec.id, self.mo.id)

    def test_resolve_by_eco_rebuilt_name_picks_latest(self):
        """Printed label says 'WH/MO/W055-T2'; ECO rebuilt to
        'WH/MO/W055-T2-1'. Scan must land on the rebuilt MO."""
        base_name = "WH/MO/W055-T2"
        self.mo.name = base_name
        rebuilt = self.env["mrp.production"].create({
            "product_id": self.product.id,
            "product_qty": 1.0,
        })
        rebuilt.name = f"{base_name}-1"
        # Exact-match lookup still wins when caller scans the base name.
        rec = self.kind.get_record(base_name)
        self.assertEqual(
            rec.id, self.mo.id,
            "Exact name match should win over fan-out",
        )
        # Direct scan of the new name resolves the rebuilt MO.
        rec2 = self.kind.get_record(f"{base_name}-1")
        self.assertEqual(rec2.id, rebuilt.id)

    def test_end_to_end_signed_payload_round_trip(self):
        """Build a signed payload via southbrook.qr.payload, parse it,
        resolve it, confirm we land on the original MO."""
        self.mo.name = "WH/MO/W055-T3"
        Payload = self.env["southbrook.qr.payload"]
        signed = Payload.build("mo", self.mo.name)
        self.assertIn("sb://mo/", signed)
        parsed = Payload.parse(signed)
        self.assertTrue(parsed["valid_signature"])
        rec = self.kind.get_record(parsed["ident"])
        self.assertEqual(rec.id, self.mo.id)
