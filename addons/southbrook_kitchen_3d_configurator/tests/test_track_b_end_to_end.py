# SPDX-License-Identifier: LGPL-3.0-only
"""Track B end-to-end regression tests.

Locks in the fixes landed across kitchen_3d_configurator 5.6.3 -> 5.6.7:

  * P0 * mrp.bom.note field removal (5.6.3)
        `note` column was dropped from `mrp.bom` in Odoo v19 CE. The
        earlier autoseed shipped a `note` value and crashed on the
        first quote. Regression pin: no `note` write, BOM lands cleanly.

  * P0 * autoseed BEFORE production-ready gate (5.6.4)
        `_check_production_ready` flags MISSING_BOM as blocking.
        Autoseed used to run AFTER the gate, so every design whose
        template had no BOM was rejected. Regression pin: autoseed
        the design's templates first, THEN validate.

  * P0 * Manufacture route defense-in-depth (5.6.5)
        Runtime-created templates missed the noupdate=1 canonical
        route seed. Without the Manufacture route, procurement.group
        only spawned Delivery -- mrp.production was never created.
        Regression pin: `_ensure_kitchen_bom` attaches the route on
        every call, not just when creating a new BOM.

  * P0 * savepoint action_confirm (5.6.6)
        Confirming the SO inline (context={'confirm_immediately': True})
        used to roll the WHOLE request when the production-approval
        gate raised UserError -- taking the autoseeded BOMs, SO, and
        design state="quoted" down with it. Regression pin: only the
        confirm attempt reverts; upstream persists.

  * UX * customer autofill, walk-in partner, active field (5.6.7)
        - `default_get` fills partner_id from context or portal user.
        - Walk-in partner is a singleton created lazily.
        - `active` field enables the archive/unarchive UX.
        - Unlink guard on state in ('quoted', 'ordered').
        - Recent-partners picker feed returns rich dicts.

If a future refactor regresses ANY of these, one of these tests must
fail. Style follows the sibling `test_save_design_acl.py` (2026-07-01)
and `southbrook_estimating/tests/test_bom_math.py`.
"""
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook",
        "southbrook_kitchen_3d_configurator", "track_b")
class TestTrackBEndToEnd(TransactionCase):
    """Regression pins for the Track B fixes shipped 2026-07-01/02."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.Design = cls.env["southbrook.kitchen.design"]
        cls.Line = cls.env["southbrook.kitchen.design.line"]
        cls.Template = cls.env["product.template"]
        cls.Bom = cls.env["mrp.bom"]
        cls.Partner = cls.env["res.partner"]
        cls.SaleOrder = cls.env["sale.order"]

        # Resolve the Manufacture route once; several tests need it and
        # the route is provided by the mrp module (hard dep of this
        # addon, so it will always be present in a normal install).
        cls.mfg_route = cls.env.ref(
            "mrp.route_warehouse0_manufacture", raise_if_not_found=False,
        )

        # Fresh test partner -- do NOT rely on demo / live prod partners.
        cls.partner = cls.Partner.create({
            "name": "Track-B Test Customer",
            "email": "trackb.customer@southbrook.test",
        })

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------
    def _make_cabinet_template(self, name, w=24.0, h=34.5, d=24.0,
                               cabinet_type="base"):
        """Fresh, catalog-conforming cabinet template with NO BOM and
        NO manufacture route. Every autoseed test starts from this
        blank slate so we can prove autoseed did the work."""
        tmpl = self.Template.create({
            "name":       name,
            "type":       "consu",
            "sale_ok":    True,
            "list_price": 500.0,
        })
        tmpl.write({
            "southbrook_is_cabinet":   True,
            "southbrook_cabinet_type": cabinet_type,
            "southbrook_width_in":     w,
            "southbrook_height_in":    h,
            "southbrook_depth_in":     d,
        })
        # Strip any route the base product create() might have picked
        # up so test_02 has a clean starting point.
        if tmpl.route_ids:
            tmpl.write({"route_ids": [(5, 0, 0)]})
        return tmpl

    def _make_design(self, name="Track-B Test Design",
                     with_lines=False, templates=None):
        """Fresh design; optionally with one line per supplied template."""
        design = self.Design.create({
            "name":          name,
            "partner_id":    self.partner.id,
            "room_width_in": 120,
            "room_depth_in": 96,
            "room_height_in": 96,
        })
        if with_lines and templates:
            for i, tmpl in enumerate(templates):
                variant = tmpl.product_variant_id
                self.Line.create({
                    "design_id":     design.id,
                    "product_id":    variant.id,
                    "quantity":      1,
                    "price_unit":    tmpl.list_price,
                    "cabinet_type":  tmpl.southbrook_cabinet_type or "base",
                    "width_in":      tmpl.southbrook_width_in or 24.0,
                    "height_in":     tmpl.southbrook_height_in or 34.5,
                    "depth_in":      tmpl.southbrook_depth_in or 24.0,
                    "x_position_in": i * 30,
                    "y_position_in": 0,
                    "z_position_in": 0,
                })
        return design

    # ==================================================================
    # 5.6.3 * mrp.bom.note removal + autoseed persistence
    # ==================================================================
    def test_01_autoseed_bom_persists_after_transaction(self):
        """5.6.3 regression pin -- autoseed creates a normal-type BOM
        with no `note` write and it survives a savepoint flush.

        Before 5.6.3 the autoseed passed `note=<json blob>` to
        `mrp.bom.create()`. `note` was removed from mrp.bom in v19 CE,
        so Bom.create() raised ValueError on the very first autoseed
        and no BOM ever landed. This test proves:
          - the create() call now succeeds;
          - a normal-type BOM row exists on the template after flush;
          - product_qty=1.0 and the code starts with 'KitchenAutoSeed-'.
        """
        tmpl = self._make_cabinet_template("Track-B autoseed persist")
        design = self._make_design()
        # Sanity: no BOM on this fresh template.
        self.assertFalse(
            tmpl.with_context(active_test=False).bom_ids,
            "fresh template should start with zero BOMs",
        )
        with self.env.cr.savepoint():
            bom = design._ensure_kitchen_bom(tmpl)
            self.env.flush_all()
        self.assertTrue(bom, "autoseed must return the created BOM")
        self.assertEqual(bom.product_tmpl_id, tmpl)
        self.assertEqual(bom.type, "normal")
        self.assertEqual(bom.product_qty, 1.0)
        self.assertTrue(
            (bom.code or "").startswith("KitchenAutoSeed-"),
            "expected code prefix 'KitchenAutoSeed-', got %r" % bom.code,
        )
        # Post-flush the BOM is still on the template.
        boms = tmpl.bom_ids.filtered(lambda b: b.type == "normal")
        self.assertEqual(
            len(boms), 1,
            "exactly one normal BOM expected on template after autoseed",
        )

    # ==================================================================
    # 5.6.5 * Manufacture route defense-in-depth
    # ==================================================================
    def test_02_autoseed_writes_manufacture_route(self):
        """5.6.5 regression pin -- autoseed attaches the Manufacture
        route on every call.

        Runtime-created templates miss the noupdate=1 canonical
        `canonical_catalog_routes.xml` seed. Without the route,
        procurement.group only spawns Delivery on SO confirm and
        mrp.production is never created -- the shop floor never sees
        the order. This test creates a fresh template with NO routes
        and asserts autoseed adds Manufacture.
        """
        if not self.mfg_route:
            self.skipTest(
                "mrp.route_warehouse0_manufacture not available -- "
                "mrp not fully installed in this test DB"
            )
        tmpl = self._make_cabinet_template("Track-B route seeder")
        self.assertNotIn(
            self.mfg_route.id, tmpl.route_ids.ids,
            "test precondition: fresh template must have no routes",
        )
        design = self._make_design()
        design._ensure_kitchen_bom(tmpl)
        self.assertIn(
            self.mfg_route.id, tmpl.route_ids.ids,
            "autoseed must attach the Manufacture route so downstream "
            "procurement.group creates mrp.production, not just Delivery",
        )

    # ==================================================================
    # Idempotence guards (5.6.3 fast-path + 5.6.3 P1 archived-BOM guard)
    # ==================================================================
    def test_03_autoseed_idempotent_on_active_bom(self):
        """Fast-path check -- second call must NOT create a duplicate BOM."""
        tmpl = self._make_cabinet_template("Track-B idempotent active")
        design = self._make_design()
        first = design._ensure_kitchen_bom(tmpl)
        second = design._ensure_kitchen_bom(tmpl)
        self.assertEqual(
            first, second,
            "repeat autoseed on an active-BOM template must return the "
            "same record (fast-path), not create a duplicate",
        )
        normals = tmpl.bom_ids.filtered(lambda b: b.type == "normal")
        self.assertEqual(
            len(normals), 1,
            "exactly one normal-type BOM expected on the template",
        )

    def test_04_autoseed_idempotent_on_archived_bom(self):
        """5.6.3 P1 regression pin -- an ARCHIVED normal BOM must still
        block a new autoseed.

        The 5.6.3 fix added `.with_context(active_test=False)` to the
        fast-path guard specifically so we don't stack a fresh autoseed
        on top of an archived-but-existing normal BOM (v19 One2many
        default filters archived records; without the context bypass,
        `tmpl.bom_ids` would look empty and we'd seed a duplicate).
        """
        tmpl = self._make_cabinet_template("Track-B idempotent archived")
        design = self._make_design()
        # Create a normal BOM and archive it.
        seed = self.Bom.sudo().create({
            "product_tmpl_id": tmpl.id,
            "type":            "normal",
            "product_qty":     1.0,
            "code":            "PreExisting-Archived",
        })
        seed.active = False
        # Precondition: default One2many hides the archived row.
        self.assertFalse(
            tmpl.bom_ids,
            "default context should filter the archived BOM out",
        )
        design._ensure_kitchen_bom(tmpl)
        all_normals = self.Bom.sudo().with_context(active_test=False).search([
            ("product_tmpl_id", "=", tmpl.id),
            ("type", "=", "normal"),
        ])
        self.assertEqual(
            len(all_normals), 1,
            "autoseed must NOT create a duplicate on top of an "
            "archived normal BOM (active_test=False guard)",
        )
        self.assertEqual(all_normals, seed)

    # ==================================================================
    # 5.6.4 * autoseed BEFORE production-ready gate
    # ==================================================================
    def test_05_autoseed_runs_before_production_ready_check(self):
        """5.6.4 regression pin -- autoseed fires BEFORE the D12 gate.

        Before 5.6.4, the autoseed loop ran AFTER the SO create call,
        so `_check_production_ready` flagged every design whose template
        had no BOM as MISSING_BOM (blocking) and refused the quote --
        defeating the whole point of autoseed. This test:
          1. builds a design with 2 cabinet lines on fresh templates
             that have NO BOM;
          2. asserts precondition (no BOM before quote);
          3. calls `action_create_quotation`;
          4. asserts the SO was created (no UserError raised);
          5. asserts each template now carries a normal-type BOM.
        """
        tmpl_a = self._make_cabinet_template(
            "Track-B pre-gate base", w=24.0, cabinet_type="base",
        )
        tmpl_b = self._make_cabinet_template(
            "Track-B pre-gate wall", w=24.0, cabinet_type="wall",
        )
        for t in (tmpl_a, tmpl_b):
            self.assertFalse(
                t.with_context(active_test=False).bom_ids,
                "test precondition: %s must start with no BOM" % t.name,
            )
        design = self._make_design(with_lines=True,
                                   templates=[tmpl_a, tmpl_b])
        # Should NOT raise -- autoseed heals MISSING_BOM before the gate.
        design.action_create_quotation()
        self.assertTrue(
            design.sale_order_id,
            "action_create_quotation must have produced a sale.order "
            "(the D12 MISSING_BOM gate should not fire when autoseed "
            "runs first)",
        )
        for t in (tmpl_a, tmpl_b):
            normals = t.bom_ids.filtered(lambda b: b.type == "normal")
            self.assertEqual(
                len(normals), 1,
                "template %s should have one normal-type BOM after "
                "autoseed via action_create_quotation" % t.name,
            )

    # ==================================================================
    # 5.6.6 * savepoint wraps action_confirm
    # ==================================================================
    def test_06_savepoint_wraps_action_confirm(self):
        """5.6.6 regression pin -- when Sale.action_confirm raises, the
        SO + autoseeded BOMs + design.state='quoted' must persist.

        We monkey-patch `sale.order.action_confirm` at the class level
        to raise a UserError, mirroring the natural failure mode where
        the Production Approval gate raises. Then we drive the flow
        via `action_create_quotation` with the `confirm_immediately`
        context flag set and assert every upstream side effect survives.
        """
        tmpl = self._make_cabinet_template("Track-B savepoint",
                                           cabinet_type="base")
        design = self._make_design(with_lines=True, templates=[tmpl])
        sale_cls = type(self.SaleOrder)

        def _raise_gate(self, *args, **kwargs):
            raise UserError("Auto-confirm blocked test-simulated gate")

        with patch.object(sale_cls, "action_confirm", _raise_gate):
            # The controller/method must swallow the UserError and
            # return the SO form act_window fallback -- not re-raise.
            result = design.with_context(
                confirm_immediately=True,
            ).action_create_quotation()

        self.assertTrue(
            design.sale_order_id,
            "SO must still exist after the confirm attempt was rolled "
            "back by the savepoint",
        )
        order = design.sale_order_id
        self.assertEqual(
            order.state, "draft",
            "SO must still be in draft -- confirm was rolled back",
        )
        # Autoseeded BOM must still exist.
        normals = tmpl.bom_ids.filtered(lambda b: b.type == "normal")
        self.assertEqual(
            len(normals), 1,
            "autoseeded BOM must survive the savepoint rollback",
        )
        # Design state advanced to 'quoted' BEFORE the confirm attempt.
        self.assertEqual(
            design.state, "quoted",
            "design.state should still be 'quoted' after gate failure",
        )
        # A chatter message documenting the failure was posted.
        blocked = order.message_ids.filtered(
            lambda m: "Auto-confirm blocked" in (m.body or "")
        )
        self.assertTrue(
            blocked,
            "expected an 'Auto-confirm blocked' chatter message on the SO",
        )
        # And the fallback action points at the SO form.
        self.assertEqual(result.get("res_model"), "sale.order")
        self.assertEqual(result.get("res_id"), order.id)

    # ==================================================================
    # 5.6.7 * default_get portal partner autofill
    # ==================================================================
    def test_07_default_get_portal_partner_autofill(self):
        """5.6.7 regression pin -- portal users (share=True) get their
        own partner auto-filled on new design creation."""
        portal_group = self.env.ref("base.group_portal")
        portal_partner = self.Partner.create({
            "name": "Track-B Portal Partner",
            "email": "trackb.portal@southbrook.test",
        })
        portal_user = self.env["res.users"].create({
            "name":       "Track-B Portal User",
            "login":      "trackb.portal@southbrook.test",
            "partner_id": portal_partner.id,
            # Odoo 19 renamed groups_id -> group_ids.
            "group_ids":  [(6, 0, [portal_group.id])],
        })
        self.assertTrue(portal_user.share,
                        "portal-group users must have share=True")
        vals = self.Design.with_user(portal_user).default_get(["partner_id"])
        self.assertEqual(
            vals.get("partner_id"), portal_partner.id,
            "portal user's own partner must be auto-filled by default_get",
        )

    def test_08_default_get_context_partner_priority(self):
        """5.6.7 regression pin -- `context={'default_partner_id': X}`
        wins over the portal-user branch, so partner-form 'Create Kitchen
        Design' still routes to the intended partner."""
        ctx_partner = self.Partner.create({
            "name": "Track-B Context Partner",
        })
        vals = self.Design.with_context(
            default_partner_id=ctx_partner.id,
        ).default_get(["partner_id"])
        self.assertEqual(
            vals.get("partner_id"), ctx_partner.id,
            "context.default_partner_id must win over any implicit "
            "portal-user default",
        )

    # ==================================================================
    # 5.6.7 * unlink guard
    # ==================================================================
    def test_09_unlink_guard_on_quoted_state(self):
        """Regression pin -- designs in state='quoted' or 'ordered'
        cannot be deleted; the audit trail from sale.order / mrp.production
        would otherwise dangle. Users must archive instead."""
        design = self._make_design(name="Track-B unlink guard")
        design.state = "quoted"
        with self.assertRaises(UserError):
            design.unlink()

    # ==================================================================
    # 5.6.7 * walk-in partner singleton
    # ==================================================================
    def test_10_get_or_create_walkin_partner_is_singleton(self):
        """Regression pin -- Walk-in Customer is lazily created ONCE
        and every subsequent call returns the same id. Powers the
        anonymous-quote path from the 3D canvas customer picker."""
        first_id = self.Design.get_or_create_walkin_partner()
        second_id = self.Design.get_or_create_walkin_partner()
        self.assertEqual(
            first_id, second_id,
            "get_or_create_walkin_partner must return the same id on "
            "repeat calls",
        )
        matches = self.Partner.search([
            ("name", "=", "Walk-in Customer"),
            ("is_company", "=", True),
        ])
        self.assertEqual(
            len(matches), 1,
            "exactly one 'Walk-in Customer' company partner must exist",
        )

    # ==================================================================
    # 5.6.7 * recent-partners picker feed
    # ==================================================================
    def test_11_get_recent_partners_returns_dicts(self):
        """Regression pin -- the picker feed returns
        `[{id, name, channel}, ...]` for the current user's recent
        designs. Powers Agent C's 3D canvas 'Recently used' section."""
        partners = []
        for i in range(3):
            p = self.Partner.create({
                "name":  "Track-B Recent Partner %d" % i,
                "email": "trackb.recent%d@southbrook.test" % i,
            })
            partners.append(p)
            self.Design.create({
                "name":           "Track-B Recent Design %d" % i,
                "partner_id":     p.id,
                "room_width_in":  120,
                "room_depth_in":  96,
                "room_height_in": 96,
            })
        feed = self.Design.get_recent_partners_for_picker(limit=10)
        self.assertIsInstance(feed, list)
        self.assertTrue(feed, "feed must not be empty")
        for row in feed:
            self.assertIsInstance(row, dict)
            self.assertIn("id", row)
            self.assertIn("name", row)
            self.assertIn("channel", row)
        returned_ids = {row["id"] for row in feed}
        for p in partners:
            self.assertIn(
                p.id, returned_ids,
                "expected partner %s in recent-partners feed" % p.name,
            )

    # ==================================================================
    # 5.6.7 * active field default
    # ==================================================================
    def test_12_active_field_defaults_true(self):
        """Regression pin -- `active=True` by default on new designs so
        the archive/unarchive UX + list default filter behave correctly."""
        design = self._make_design(name="Track-B active default")
        self.assertTrue(
            design.active,
            "new designs must default to active=True so they show up "
            "in the list without needing an explicit filter",
        )

    # ==================================================================
    # 5.6.11 * cancellation sync sale.order -> kitchen.design
    # ==================================================================
    def test_cancellation_reverts_linked_design(self):
        """5.6.11 regression pin -- cancelling a sale.order tied to a
        kitchen.design reverts the design to state='configured', clears
        sale_order_id, and drops a chatter note on the design.

        Reverse of the ordered->SO transition. Without this sync a rep
        who cancels the SO from its own surface leaves an orphan
        "quoted"/"ordered" design pointing at a cancelled quotation --
        stuck out of the re-quote flow until manually reset via
        action_reset_quote_link.
        """
        tmpl = self._make_cabinet_template(
            "Track-B cancel sync", cabinet_type="base",
        )
        design = self._make_design(
            name="Track-B cancel sync design",
            with_lines=True, templates=[tmpl],
        )
        design.action_create_quotation()
        so = design.sale_order_id
        self.assertTrue(so, "precondition: action_create_quotation must "
                            "have produced a linked SO")
        self.assertEqual(design.state, "quoted",
                         "precondition: design must be in state='quoted' "
                         "before the cancel event")
        so_name = so.name

        so.action_cancel()

        self.assertEqual(
            design.state, "configured",
            "design must revert to 'configured' when its linked SO is "
            "cancelled so the rep can re-quote it",
        )
        self.assertFalse(
            design.sale_order_id,
            "sale_order_id must be cleared so the design is no longer "
            "pinned to the cancelled SO",
        )
        cancel_notes = design.message_ids.filtered(
            lambda m: "was cancelled" in (m.body or "")
        )
        self.assertTrue(
            cancel_notes,
            "expected a chatter note on the design mentioning 'was "
            "cancelled'",
        )
        self.assertTrue(
            any(so_name in (m.body or "") for m in cancel_notes),
            "chatter note must name the cancelled SO (%s) so the "
            "audit trail links back" % so_name,
        )
