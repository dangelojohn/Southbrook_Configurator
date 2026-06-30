# SPDX-License-Identifier: LGPL-3.0-only
"""W042 (MFG-REVIEW-R5.6) — asbuilt.create auto-stamps lot_id from
the source MO's lot_producing_id.

Why: per R5.6 baseline, lot-to-asbuilt warranty trace fails ~95% of
the time today because operators don't manually stamp the produced
lot on the asbuilt record. The fix snapshots it at create() time so
the trace works without operator action.

Behavioural contract:
  1. asbuilt.create with production_id + no lot_id + MO carrying a
     lot_producing_id -> asbuilt.lot_id == MO.lot_producing_id.
  2. asbuilt.create with an explicit lot_id passed -> respected,
     NOT clobbered by the auto-snapshot.
  3. asbuilt.create on an MO with no lot_producing_id -> lot_id
     stays empty, no crash.
"""
from odoo.tests import TransactionCase


class TestW042AsbuiltLotSnapshot(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Asbuilt = self.env["southbrook.asbuilt"]
        self.Production = self.env["mrp.production"]
        self.Lot = self.env["stock.lot"]

    def _make_mo_with_lot(self):
        """Find or build an MO that carries a lot_producing_id."""
        mo = self.Production.search(
            [("lot_producing_id", "!=", False)], limit=1,
        )
        if mo:
            return mo
        # Synthesize: pick any product that tracks by lot/serial, build
        # a lot for it, attach to a fresh MO. Falls back to skip if
        # the demo DB has no tracked products.
        tracked = self.env["product.product"].search(
            [("tracking", "in", ("lot", "serial"))], limit=1,
        )
        if not tracked:
            return self.Production.browse()
        mo = self.Production.search(
            [("product_id", "=", tracked.id)], limit=1,
        )
        if not mo:
            return self.Production.browse()
        lot = self.Lot.create({
            "product_id": tracked.id,
            "name": "W042-TEST-LOT",
            "company_id": self.env.company.id,
        })
        mo.lot_producing_id = lot.id
        return mo

    def test_auto_snapshot_when_unset(self):
        mo = self._make_mo_with_lot()
        if not mo:
            self.skipTest("no MO with lot_producing_id available")
        ab = self.Asbuilt.create({"production_id": mo.id})
        try:
            self.assertEqual(
                ab.lot_id, mo.lot_producing_id,
                "W042: asbuilt.lot_id should auto-stamp from "
                "MO.lot_producing_id",
            )
        finally:
            ab.unlink()

    def test_explicit_lot_id_respected(self):
        """A caller passing lot_id wins over the auto-snapshot — we
        only stamp when the caller hasn't supplied one."""
        mo = self._make_mo_with_lot()
        if not mo:
            self.skipTest("no MO with lot_producing_id available")
        other_lot = self.Lot.create({
            "product_id": mo.product_id.id,
            "name": "W042-OVERRIDE",
            "company_id": self.env.company.id,
        })
        ab = self.Asbuilt.create({
            "production_id": mo.id,
            "lot_id": other_lot.id,
        })
        try:
            self.assertEqual(
                ab.lot_id, other_lot,
                "W042: explicit lot_id must not be clobbered by "
                "the auto-snapshot",
            )
        finally:
            ab.unlink()

    def test_no_lot_no_crash(self):
        mo = self.Production.search(
            [("lot_producing_id", "=", False)], limit=1,
        )
        if not mo:
            self.skipTest("no MO without lot_producing_id available")
        ab = self.Asbuilt.create({"production_id": mo.id})
        try:
            self.assertFalse(
                ab.lot_id,
                "W042: empty lot_producing_id should leave lot_id empty",
            )
        finally:
            ab.unlink()
