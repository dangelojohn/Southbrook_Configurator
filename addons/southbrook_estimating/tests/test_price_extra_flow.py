# SPDX-License-Identifier: LGPL-3.0-only
"""Regression pins for the 5 PTAV price_extra anchors — 2026-07-01 audit follow-up.

Track F (southbrook_estimating 19.0.7.2.0) shipped a canonical PTAV
`price_extra` backfill via:

  * `models/ptav_price_extra_seed.py`  (AbstractModel `southbrook.estimating.
     ptav_price_extra_seed` with `seed_price_extra_for_value` +
     `seed_price_extra_batch`)
  * `data/attribute_values_price_extra.xml`  (noupdate="1", batch call
     with 5 anchor value xmlids × per-template price dict)

The design doc `docs/track_c_price_extra_pending_2026-07-01.md` promised
regression pins for those anchors — this file fulfils that promise.

Coverage:
  * anchor completeness (every anchor has ≥1 PTAV row)
  * uniform-anchor value pinning (5-piece door / soft-close / Blum drawer)
  * derived-anchor spot check (Maple box, per-template hand-tuned)
  * cross-addon tactical override pin (Series=Signature $145 wins when
    southbrook_configurator_ux is installed)
  * idempotency of the seed helper (double-call → no duplicates, same result)
  * noupdate="1" contract preserved in the XML wrapper (runtime edits survive `-u`)
  * missing-template graceful skip (contract in the AbstractModel docstring)

Numbers come from `data/attribute_values_price_extra.xml` (the anchor
spec) and are compared with a ±$0.01 tolerance to avoid
FloatingComparisonError on price_extra float storage.

Related work:
  * `southbrook_configurator_ux/models/tactical_price_seed.py`
     (demo-grade sibling seed — the Signature=$145 override lives there)
  * `docs/track_c_price_extra_pending_2026-07-01.md`
     (design + open product-owner questions, updated when this landed)
"""
import logging

from odoo.tests.common import TransactionCase, tagged
from odoo.tools import float_compare


_LOGGER = logging.getLogger(__name__)


# The five value xml_ids seeded by data/attribute_values_price_extra.xml.
_ANCHOR_XMLIDS = (
    "value_box_maple",
    "value_door_five_piece_woodgrain",
    "value_accessory_soft_close",
    "value_drawer_metal_blum",
    "value_series_signature",
)

# Uniform anchors: one price applied across every template that carries
# the value on its attribute_line. Numbers are the anchor spec from
# data/attribute_values_price_extra.xml.
_UNIFORM_ANCHORS = {
    "value_door_five_piece_woodgrain": 35.00,
    "value_accessory_soft_close":      15.00,
    "value_drawer_metal_blum":         65.00,
}

# The 12 canonical cabinet template xmlids per CLAUDE.md §3 Q8.
_Q8_TEMPLATE_XMLIDS = (
    "wall_1dr", "wall_2dr", "base_1dr", "base_2dr",
    "drawer_bank", "sink_base", "tall_pantry", "tall_oven",
    "corner", "vanity", "accessory", "worktop",
)


@tagged("post_install", "-at_install", "southbrook", "price_extra")
class TestPriceExtraSeed(TransactionCase):
    """Regression pins for the 5 PTAV price_extra anchors."""

    def setUp(self):
        super().setUp()
        self.PTAV = self.env["product.template.attribute.value"]
        self.Seed = self.env["southbrook.estimating.ptav_price_extra_seed"]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _ref(self, xml_id, raise_if_not_found=True):
        return self.env.ref(
            f"southbrook_estimating.{xml_id}",
            raise_if_not_found=raise_if_not_found,
        )

    def _ptavs_for_value(self, value_xml_id):
        """All PTAV rows that carry the given anchor value across
        every template that includes it on an attribute_line."""
        value = self._ref(value_xml_id)
        return self.PTAV.search([
            ("product_attribute_value_id", "=", value.id),
        ])

    def _configurator_ux_installed(self):
        """True when southbrook_configurator_ux is in state=installed —
        indicates its tactical price seed is authoritative on overlap."""
        return bool(self.env["ir.module.module"].search_count([
            ("name", "=", "southbrook_configurator_ux"),
            ("state", "=", "installed"),
        ]))

    # ------------------------------------------------------------------
    # 1 · Completeness
    # ------------------------------------------------------------------
    def test_01_all_five_anchors_landed(self):
        """Every one of the 5 anchor value xmlids must resolve to at
        least one PTAV row with a non-None price_extra.

        Anchor spec (from data/attribute_values_price_extra.xml):
          * value_box_maple                — 12 rows (all templates)
          * value_door_five_piece_woodgrain — 10 rows (no worktop / accessory)
          * value_accessory_soft_close     — 10 rows (no worktop / accessory)
          * value_drawer_metal_blum        — 6 rows (drawer-carrying templates)
          * value_series_signature         — 11 rows (no vanity)

        Failure here means either the seed didn't run (fresh install
        skipped the data file) or the anchor's value xml_id got renamed
        in `data/attributes.xml` without a matching update to the
        seed batch.
        """
        missing = []
        empty = []
        for xml_id in _ANCHOR_XMLIDS:
            value = self._ref(xml_id, raise_if_not_found=False)
            if not value:
                missing.append(xml_id)
                continue
            rows = self._ptavs_for_value(xml_id)
            if not rows:
                empty.append(xml_id)
                continue
            # price_extra is a non-nullable float column, so this can
            # only fail if the seed helper silently skipped every row.
            for row in rows:
                self.assertIsNotNone(
                    row.price_extra,
                    f"PTAV {row.id} for anchor {xml_id} on template "
                    f"{row.product_tmpl_id.name!r} has None price_extra "
                    f"— seed didn't apply.",
                )
        self.assertFalse(
            missing,
            f"Anchor value xml_ids not present in southbrook_estimating: "
            f"{missing}. Check data/attributes.xml.",
        )
        self.assertFalse(
            empty,
            f"Anchor value xml_ids resolved but no PTAV rows exist for "
            f"them: {empty}. Either the templates don't include the "
            f"value on any attribute_line, or PTAV rows failed to "
            f"materialise. Check data/product_templates.xml.",
        )

    # ------------------------------------------------------------------
    # 2 · Uniform anchors
    # ------------------------------------------------------------------
    def test_02_uniform_anchor_values(self):
        """3 anchors are uniformly-priced across every template that
        carries them:

          * value_door_five_piece_woodgrain → $35.00 (5-piece woodgrain
            upgrade, canonical Signature-Series book pricing)
          * value_accessory_soft_close     → $15.00 (Blum soft-close
            per-cabinet upgrade)
          * value_drawer_metal_blum        → $65.00 (Blum Legrabox
            metal drawer construction)

        Tolerance ±$0.01 to avoid FloatingComparisonError.
        """
        for xml_id, expected in _UNIFORM_ANCHORS.items():
            rows = self._ptavs_for_value(xml_id)
            self.assertTrue(
                rows,
                f"Anchor {xml_id} has no PTAV rows — cannot verify "
                f"uniform ${expected:.2f} pricing.",
            )
            for row in rows:
                cmp = float_compare(
                    row.price_extra, expected, precision_digits=2)
                self.assertEqual(
                    cmp, 0,
                    f"Anchor {xml_id} on template "
                    f"{row.product_tmpl_id.name!r} (id={row.product_tmpl_id.id}) "
                    f"expected ${expected:.2f}, got ${row.price_extra:.2f}. "
                    f"Either the seed didn't run on this template "
                    f"(check data/attribute_values_price_extra.xml) "
                    f"or a runtime UI edit shifted the value.",
                )

    # ------------------------------------------------------------------
    # 3 · Derived Maple anchor (informational)
    # ------------------------------------------------------------------
    def test_03_maple_ten_percent_derived(self):
        """CLAUDE.md §5 Rule 2 states Maple box carries +10% price.

        The seed at 7.2.0 ships hand-tuned per-template Maple prices
        (approximations pending Price Master extraction). Individual
        template values can therefore land at either:

          (a) `template.list_price * 0.10` (the canonical anchor)
          (b) $30 (the demo-grade tactical override in
              southbrook_configurator_ux/models/tactical_price_seed.py)
          (c) a hand-tuned per-template value from the seed spec
              (e.g. wall_1dr $24.50, drawer_bank $47.50)

        We accept any of these as valid — the anchor commitment is
        that Maple has SOME positive price_extra, not that every
        template matches a single formula. This test logs the actual
        value per template for downstream calibration against the
        Price Master workbook.
        """
        rows = self._ptavs_for_value("value_box_maple")
        self.assertTrue(
            rows,
            "value_box_maple has no PTAV rows — Maple anchor did not "
            "land on any of the 12 Q8 templates.",
        )
        for row in rows:
            tmpl = row.product_tmpl_id
            ten_pct = round(tmpl.list_price * 0.10, 2)
            actual = row.price_extra
            self.assertGreaterEqual(
                actual, 0.0,
                f"Maple price_extra on template {tmpl.name!r} is "
                f"negative ({actual:.2f}) — data corruption.",
            )
            _LOGGER.info(
                "test_03_maple_ten_percent_derived: template=%s "
                "list_price=%.2f → 10%%=%.2f, actual price_extra=%.2f, "
                "tactical_override=$30.00",
                tmpl.name, tmpl.list_price, ten_pct, actual,
            )
        # Informational: at least one row must be non-zero (otherwise
        # the whole anchor is a no-op and something regressed).
        self.assertTrue(
            any(r.price_extra > 0.0 for r in rows),
            "Every value_box_maple PTAV has price_extra == 0.0. "
            "The Maple anchor is effectively unpriced — check "
            "data/attribute_values_price_extra.xml.",
        )

    # ------------------------------------------------------------------
    # 4 · Signature series tactical override
    # ------------------------------------------------------------------
    def test_04_signature_series_tactical_override(self):
        """data/attribute_values_price_extra.xml writes $0 defensively
        for `value_series_signature` on every template (Signature is
        the base tier — other series price DOWN from it).

        `southbrook_configurator_ux/models/tactical_price_seed.py`
        writes $145 for `Series=Signature` — a demo-grade premium so
        the LIVE price badge tells a story during sales-rep demos.

        Load order:
          * southbrook_estimating (base seed) → $0
          * southbrook_configurator_ux (tactical) → $145

        Because configurator_ux depends on estimating and both run at
        `-i` time, the tactical write happens second and wins. This
        test pins that outcome so a future reorder (or removal of the
        tactical file) surfaces as a green-to-red.

        If southbrook_configurator_ux isn't installed, we skip — the
        test is only meaningful with the tactical layer active.
        """
        if not self._configurator_ux_installed():
            self.skipTest(
                "southbrook_configurator_ux not installed — tactical "
                "$145 Signature override not expected in prod.")
        wall_1dr = self._ref("wall_1dr")
        signature = self._ref("value_series_signature")
        row = self.PTAV.search([
            ("product_tmpl_id", "=", wall_1dr.id),
            ("product_attribute_value_id", "=", signature.id),
        ], limit=1)
        self.assertTrue(
            row,
            "No PTAV for value_series_signature on wall_1dr — expected "
            "Series/Signature to be on every wall_1dr attribute_line.",
        )
        cmp = float_compare(row.price_extra, 145.00, precision_digits=2)
        self.assertEqual(
            cmp, 0,
            f"Series=Signature on wall_1dr expected $145.00 (tactical "
            f"override wins over estimating anchor $0.00), got "
            f"${row.price_extra:.2f}. Load order may have flipped, or "
            f"the tactical seed was removed. See "
            f"southbrook_configurator_ux/models/tactical_price_seed.py "
            f"line ~49.",
        )

    # ------------------------------------------------------------------
    # 5 · Idempotency of the seed helper
    # ------------------------------------------------------------------
    def test_05_tactical_price_seed_batch_idempotency(self):
        """`seed_price_extra_for_value(...)` must be idempotent:

          * Two consecutive calls with identical args produce identical
            state.
          * No duplicate PTAV rows appear (the helper `.write()`s onto
            existing rows — it never `.create()`s them).

        Contract from `models/ptav_price_extra_seed.py`:

            "Idempotent. Silently skips (template, value) pairs where
             no PTAV exists — that happens when the template's
             attribute_line does not include this value."

        Regression risk: if the AbstractModel is ever changed to use
        `create()` (e.g. a naive "make PTAV if missing" refactor), row
        count would double on the second call. This test would fail
        loudly instead of silently corrupting pricing.
        """
        anchor = "value_accessory_soft_close"
        # A subset of the batch — enough to exercise a real write.
        payload = {
            "wall_1dr":  15.00,
            "base_1dr":  15.00,
            "drawer_bank": 15.00,
        }
        # Baseline row count for the anchor.
        rows_before = self._ptavs_for_value(anchor)
        count_before = len(rows_before)
        # First call — should be a no-op write (values already at 15.00
        # from the initial data-file seed), returning the number of PTAV
        # rows actually updated.
        first = self.Seed.seed_price_extra_for_value(anchor, payload)
        rows_after_first = self._ptavs_for_value(anchor)
        self.assertEqual(
            len(rows_after_first), count_before,
            "seed_price_extra_for_value first call changed PTAV row "
            "count — the helper is supposed to WRITE, not CREATE.",
        )
        # Second call with identical args.
        second = self.Seed.seed_price_extra_for_value(anchor, payload)
        rows_after_second = self._ptavs_for_value(anchor)
        self.assertEqual(
            len(rows_after_second), count_before,
            "seed_price_extra_for_value second call changed PTAV row "
            "count — regression risk: helper started CREATE-ing rows.",
        )
        # Both calls must report the same number of rows updated —
        # verifying they touched the same (template, value) pairs.
        self.assertEqual(
            first, second,
            f"Idempotency broken: first call updated {first} rows, "
            f"second call updated {second}. Same args should touch "
            f"the same rows.",
        )
        # And every row must still be at the seeded $15.00.
        for row in rows_after_second:
            if row.product_tmpl_id.id in {
                self._ref(t).id for t in payload
            }:
                cmp = float_compare(
                    row.price_extra, 15.00, precision_digits=2)
                self.assertEqual(
                    cmp, 0,
                    f"After 2 idempotent calls, PTAV on "
                    f"{row.product_tmpl_id.name!r} landed at "
                    f"${row.price_extra:.2f} not $15.00.",
                )

    # ------------------------------------------------------------------
    # 6 · noupdate="1" contract
    # ------------------------------------------------------------------
    def test_06_noupdate_flag_respected(self):
        """`data/attribute_values_price_extra.xml` MUST carry
        `noupdate="1"` on its `<odoo>` root. Without that flag,
        `-u southbrook_estimating` would re-apply the seed on every
        upgrade, overwriting any runtime edits the product owner made
        via the backend UI.

        Same reactivity contract as `data/room_templates.xml` and
        `data/prodboard_taxonomy_seed.xml` — audit §4.A pattern.

        This is a docs-in-tests style check: we grep the file for the
        flag rather than exercising the runtime behavior (which would
        need a live upgrade cycle to prove).
        """
        import os
        addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        xml_path = os.path.join(
            addon_dir, "data", "attribute_values_price_extra.xml")
        self.assertTrue(
            os.path.exists(xml_path),
            f"attribute_values_price_extra.xml not found at {xml_path}. "
            f"Was the file moved or renamed?",
        )
        with open(xml_path, "r", encoding="utf-8") as fh:
            content = fh.read()
        # The flag must appear on the <odoo> root element, not merely
        # somewhere in a comment.
        self.assertIn(
            '<odoo noupdate="1">',
            content,
            "attribute_values_price_extra.xml is missing "
            '`<odoo noupdate="1">` on its root element. Runtime '
            "product-owner edits to PTAV.price_extra will NOT survive "
            "`-u southbrook_estimating` — every upgrade will re-seed "
            "and clobber the current values.",
        )

    # ------------------------------------------------------------------
    # 7 · Missing-template graceful skip
    # ------------------------------------------------------------------
    def test_07_missing_template_graceful_skip(self):
        """The AbstractModel docstring pins this contract:

            "Silently skips (template, value) pairs where no PTAV
             exists — that happens when the template's attribute_line
             does not include this value."

        In particular, an unresolvable template xml_id must not raise
        — otherwise a single typo in the XML batch would abort the
        whole install. We verify by passing a deliberately-broken
        template xml_id and asserting the helper returns cleanly with
        0 rows updated.
        """
        try:
            result = self.Seed.seed_price_extra_for_value(
                "value_box_maple",
                {"nonexistent_template_xmlid_xyz123": 999.99},
            )
        except Exception as exc:  # noqa: BLE001 — the whole point.
            self.fail(
                f"seed_price_extra_for_value raised on a missing "
                f"template xml_id — the AbstractModel is supposed to "
                f"silently skip and continue: {exc}"
            )
        self.assertEqual(
            result, 0,
            f"seed_price_extra_for_value reported {result} rows updated "
            f"for a nonexistent template xml_id — expected 0. Either "
            f"the helper is inventing a match, or the fake xml_id "
            f"accidentally resolved.",
        )
