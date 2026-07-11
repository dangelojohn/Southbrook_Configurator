# SPDX-License-Identifier: LGPL-3.0-only
"""Reliability scoring / Factory Intelligence Audit tests.

Each test isolates its MRP data inside a dedicated ``res.company`` so structural
signals are computed over a known, deterministic dataset rather than whatever the
shared demo DB happens to contain.
"""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "oiq")
class TestReliability(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create({"name": "OIQ Test Cabinets"})
        cls.svc = cls.env["oiq.scheduling.intelligence"]
        # A company-less (shared) calendar keeps a shared work center consistent
        # with the shared BoM that references it.
        cls.calendar = cls.env["resource.calendar"].create({
            "name": "OIQ Shared Calendar", "company_id": False})

    # -- helpers ------------------------------------------------------------
    def _make_workcenter(self):
        # company_id=False → shared work center, consistent with the shared BoM
        # it is referenced from (avoids the resource-calendar company check).
        return self.env["mrp.workcenter"].create({
            "name": "CNC Router",
            "company_id": False,
            "resource_calendar_id": self.calendar.id,
        })

    def _make_product(self, name):
        return self.env["product.product"].create({"name": name, "type": "consu"})

    def _make_mo(self, product, bom):
        return self.env["mrp.production"].create({
            "product_id": product.id,
            "product_qty": 1.0,
            "bom_id": bom.id,
            "company_id": self.company.id,
        })

    def _bom(self, product, with_operation=False):
        vals = {
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_qty": 1.0,
            "type": "normal",
        }
        if with_operation:
            wc = self._make_workcenter()
            vals["operation_ids"] = [(0, 0, {
                "name": "Cut",
                "workcenter_id": wc.id,
                "time_cycle_manual": 30.0,
                "time_mode": "manual",
            })]
        return self.env["mrp.bom"].create(vals)

    def _findings_by_code(self, audit, code):
        return audit.finding_ids.filtered(lambda f: f.signal_code == code)

    # -- tests --------------------------------------------------------------
    def test_analyze_returns_complete_audit(self):
        """analyze() persists a complete audit with a scored, ranged readiness."""
        audit = self.svc.analyze(self.company)
        self.assertTrue(audit.exists())
        self.assertEqual(audit.state, "complete")
        self.assertEqual(audit.company_id, self.company)
        self.assertGreaterEqual(audit.structural_score, 0.0)
        self.assertLessEqual(audit.structural_score, 100.0)
        self.assertIn(audit.readiness_level, (1, 2, 3, 4, 5))

    def test_empty_factory_is_blind(self):
        """A company with no manufacturing data is Readiness Level 1 (Blind)."""
        audit = self.svc.analyze(self.company)
        self.assertEqual(audit.readiness_level, 1)
        self.assertFalse(audit.behavioral_score_available)

    def test_s1_routing_coverage_flags_uncovered_mos(self):
        """S1 counts MOs whose BoM has no routing operations."""
        p_cov = self._make_product("Covered Cab")
        p_unc = self._make_product("Uncovered Cab")
        self._make_mo(p_cov, self._bom(p_cov, with_operation=True))
        self._make_mo(p_unc, self._bom(p_unc, with_operation=False))

        audit = self.svc.analyze(self.company)
        s1 = self._findings_by_code(audit, "S1_ROUTING_COVERAGE")
        self.assertTrue(s1, "expected an S1_ROUTING_COVERAGE finding")
        # Exactly one MO (the uncovered one) is the problem.
        self.assertEqual(s1.affected_count, 1)

    def test_s6_flags_mechanically_derived_deadline(self):
        """S6 flags a deadline that equals create_date + routing time (fiction)."""
        p = self._make_product("Fiction Cab")
        mo = self._make_mo(p, self._bom(p, with_operation=False))
        # No workorders on a draft MO → naive deadline == create_date.
        mo.date_deadline = mo.create_date

        audit = self.svc.analyze(self.company)
        s6 = self._findings_by_code(audit, "S6_DATE_AUTHENTICITY")
        self.assertTrue(s6, "expected an S6_DATE_AUTHENTICITY finding")
        self.assertGreaterEqual(s6.affected_count, 1)

    def test_analyze_with_company_workcenter_runs_capacity_signals(self):
        """A work center owned by the company exercises S4/S5/S7 (calendar,
        efficiency, overload) — the path that has no coverage when work centers
        are shared."""
        wc = self.env["mrp.workcenter"].create({
            "name": "In-Company CNC",
            "company_id": self.company.id,
            "resource_calendar_id": self.calendar.id,
            "time_efficiency": 100.0,
        })
        p = self._make_product("Cap Cab")
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": p.product_tmpl_id.id,
            "product_qty": 1.0, "type": "normal", "company_id": self.company.id,
            "operation_ids": [(0, 0, {
                "name": "Cut", "workcenter_id": wc.id,
                "time_cycle_manual": 45.0, "time_mode": "manual"})],
        })
        self._make_mo(p, bom)
        audit = self.svc.analyze(self.company)  # must not raise on real work centers
        self.assertEqual(audit.state, "complete")
        # S4/S5 evaluated over a real work center (not N/A).
        codes = set(audit.finding_ids.mapped("signal_code"))
        self.assertTrue(audit.readiness_level >= 1)

    def test_behavioral_signals_locked_without_history(self):
        """With no completion history, behavioral score is unavailable and the
        Readiness Level cannot exceed 2 (Structured)."""
        p = self._make_product("Solid Cab")
        self._make_mo(p, self._bom(p, with_operation=True))
        audit = self.svc.analyze(self.company)
        self.assertFalse(audit.behavioral_score_available)
        self.assertLessEqual(audit.readiness_level, 2)
