# SPDX-License-Identifier: LGPL-3.0-only
"""oiq.scheduling.intelligence — the engine service seam.

All signal logic and scoring lives here; the audit model only persists what this
service produces. Step 1 implements ``analyze()`` (the Factory Intelligence Audit
+ Readiness). Later steps add ``shadow_schedule()``, ``simulate()`` and
``estimate_delivery()`` behind this same abstract model.

Read-only invariant: nothing here writes to mrp.production / mrp.workorder /
mrp.workcenter — the audit only reads MRP and writes its own oiq.* records.
"""
import json
import statistics
from datetime import timedelta

from odoo import fields, models

BEHAVIORAL_LOOKBACK_DAYS = 28
MIN_SAMPLES = {
    "B1_DATE_CHURN": 20,
    "B2_ESTIMATE_ACCURACY": 30,
    "B3_OVERRIDE_RATE": 20,
    "B4_ON_TIME": 15,
}
STRUCTURAL_WEIGHTS = {
    "S1_ROUTING_COVERAGE": 15,
    "S2_WC_ASSIGNED": 10,
    "S3_TIME_REALISM": 15,
    "S4_CALENDAR": 10,
    "S5_CAPACITY": 10,
    "S6_DATE_AUTHENTICITY": 20,
    "S7_OVERLOAD": 20,
}
BEHAVIORAL_WEIGHTS = {
    "B1_DATE_CHURN": 20,
    "B2_ESTIMATE_ACCURACY": 35,
    "B3_OVERRIDE_RATE": 20,
    "B4_ON_TIME": 25,
}
STRUCTURAL_CODES = tuple(STRUCTURAL_WEIGHTS)
BEHAVIORAL_CODES = tuple(BEHAVIORAL_WEIGHTS)

BLOCKER_THRESHOLD = 40.0   # a sub-score below this auto-raises a blocker finding
READINESS_NAMES = {
    1: "Blind", 2: "Structured", 3: "Observed", 4: "Calibrated", 5: "Predictive",
}

# --- shadow scheduler (§6) ---
DEFAULT_FALLBACK_MIN = 30.0   # never schedule a zero-duration op
MIN_CALIB_SAMPLE = 5          # blend calibration to 1.0 below this sample count
RISK_CONF_WEIGHT = 20.0       # low calibration confidence widens late_risk
LATE_SCALE_MIN = 480.0        # 8 working hours = one "unit" of lateness
EARLY_SCALE_MIN = 480.0

# --- calibration engine (§7) ---
MIN_SAMPLE_THRESHOLD = 5      # below this, no factor is applied (pass-through)
BLEND_FULL_TRUST_AT = 20      # at/above this, the raw median is used at full weight
SAMPLE_SATURATION = 40        # sample_count that saturates the confidence sample-term
CALIB_WINDOW_DAYS = 120       # rolling window keeps factors responsive to process change
# Coarse operation-category keyword map — keeps scope keys low-cardinality so
# sample size accumulates quickly. Used by BOTH capture and the scheduler so the
# factor a WO is learned under is the factor it is later scheduled with.
OP_KEYWORDS = {
    "paint": "paint", "spray": "paint", "finish": "paint",
    "assembl": "assembly", "cnc": "cnc", "rout": "cnc", "mill": "cnc",
    "sand": "sanding", "edge": "edgeband", "band": "edgeband",
    "drill": "drilling", "bore": "drilling",
    "cut": "cutting", "saw": "cutting", "nest": "cutting",
}


def _clamp(lo, hi, v):
    return max(lo, min(hi, v))


def _weighted_average(subscores, weights):
    """Average sub-scores by weight, over signals that actually produced data
    (subscores keys). Returns 0.0 when nothing had data."""
    active = {k: v for k, v in subscores.items() if v is not None}
    if not active:
        return 0.0
    wsum = sum(weights[k] for k in active)
    if not wsum:
        return 0.0
    return sum(active[k] * weights[k] for k in active) / wsum


class OiqSchedulingIntelligence(models.AbstractModel):
    _name = "oiq.scheduling.intelligence"
    _description = "OdooIQ Scheduling Intelligence Service"

    # ------------------------------------------------------------------ util
    def _model_or_none(self, name):
        return self.env[name] if name in self.env else None

    # ------------------------------------------------------------- public API
    def analyze(self, company):
        """Run a full Factory Intelligence Audit for ``company`` and return the
        complete ``oiq.factory.audit`` record."""
        horizon_days = 14
        audit = self.env["oiq.factory.audit"].create({
            "date": fields.Datetime.now(),
            "company_id": company.id,
            "horizon_days": horizon_days,
            "state": "draft",
        })

        productions = self.env["mrp.production"].search([
            ("company_id", "=", company.id),
            ("state", "not in", ("cancel",)),
        ])

        findings = []

        # ---- Structural pass ----
        structural_evaluators = {
            "S1_ROUTING_COVERAGE": self._eval_s1,
            "S2_WC_ASSIGNED": self._eval_s2,
            "S3_TIME_REALISM": self._eval_s3,
            "S4_CALENDAR": self._eval_s4,
            "S5_CAPACITY": self._eval_s5,
            "S6_DATE_AUTHENTICITY": self._eval_s6,
            "S7_OVERLOAD": self._eval_s7,
        }
        structural_subscores = {}
        for code, fn in structural_evaluators.items():
            sub_score, fnds = fn(company, productions, horizon_days)
            structural_subscores[code] = sub_score  # may be None → N/A
            findings += fnds

        structural_score = _weighted_average(structural_subscores, STRUCTURAL_WEIGHTS)
        has_blocker = any(f["severity"] == "blocker" and f["tier"] == "structural"
                          for f in findings)
        if has_blocker:
            structural_score = min(structural_score, 45.0)
        structural_score = _clamp(0.0, 100.0, structural_score)

        # ---- Behavioral pass (locked until history accrues) ----
        window_start = fields.Datetime.now() - timedelta(days=BEHAVIORAL_LOOKBACK_DAYS)
        behavioral_evaluators = {
            "B1_DATE_CHURN": self._eval_b1,
            "B2_ESTIMATE_ACCURACY": self._eval_b2,
            "B3_OVERRIDE_RATE": self._eval_b3,
            "B4_ON_TIME": self._eval_b4,
        }
        behavioral_subscores, unlocked = {}, []
        for code, fn in behavioral_evaluators.items():
            sub_score, sample_count, fnds = fn(company, window_start)
            if sample_count >= MIN_SAMPLES[code]:
                behavioral_subscores[code] = sub_score
                unlocked.append(code)
                findings += fnds
            else:
                findings.append(self._lock_finding(code, sample_count))

        behavioral_available = bool(unlocked)
        behavioral_score = (
            _weighted_average(behavioral_subscores,
                              {k: BEHAVIORAL_WEIGHTS[k] for k in unlocked})
            if behavioral_available else 0.0
        )

        # ---- Readiness (min of the two gates) ----
        readiness_level = self._readiness_level(
            structural_score, behavioral_score if behavioral_available else False,
            findings, unlocked)

        audit.write({
            "structural_score": structural_score,
            "behavioral_score": behavioral_score,
            "behavioral_score_available": behavioral_available,
            "readiness_level": readiness_level,
            "summary_text": self._render_summary(readiness_level, findings),
            "state": "complete",
            "finding_ids": [(0, 0, f) for f in findings],
        })
        return audit

    # ---------------------------------------------------------- readiness gate
    def _readiness_level(self, structural_score, behavioral_score, findings, unlocked):
        has_blocker = any(f["severity"] == "blocker" and f["tier"] == "structural"
                          for f in findings)
        # structural gate
        if structural_score < 40 or has_blocker:
            g_struct = 1
        elif structural_score < 70:
            g_struct = 2
        else:
            g_struct = 5
        # behavioral gate
        if behavioral_score is False or not unlocked:
            g_behav = 2
        elif "B2_ESTIMATE_ACCURACY" not in unlocked or "B3_OVERRIDE_RATE" not in unlocked:
            g_behav = 3
        else:
            factors = self._model_or_none("oiq.calibration.factor")
            calibrated = factors is not None and bool(factors.search_count([
                ("sample_count", ">=", MIN_SAMPLES["B2_ESTIMATE_ACCURACY"]),
                ("confidence", ">=", 0.5),
            ]))
            if not calibrated:
                g_behav = 3
            elif behavioral_score < 70:
                g_behav = 4
            else:
                g_behav = 5
        return min(g_struct, g_behav)

    # ------------------------------------------------------------- rendering
    def _render_summary(self, level, findings):
        rank_sev = {"blocker": 30, "warn": 20, "info": 10}
        rank_imp = {"high": 30, "med": 20, "low": 10}
        ranked = sorted(
            findings,
            key=lambda f: (rank_sev.get(f["severity"], 0), rank_imp.get(f["expected_improvement"], 0)),
            reverse=True,
        )
        top = [f for f in ranked if f["severity"] != "info"][:3] or ranked[:1]
        parts = [f"Readiness Level {level} ({READINESS_NAMES.get(level, '?')})."]
        for f in top:
            parts.append(
                f"Top fix: {f['title']} ({f['signal_code']}) — "
                f"expected improvement: {f['expected_improvement']}."
            )
        return " ".join(parts)

    def _lock_finding(self, code, sample_count):
        threshold = MIN_SAMPLES[code]
        return {
            "signal_code": code, "tier": "behavioral", "severity": "info",
            "title": f"{code} locked — not enough history yet",
            "detail": f"{sample_count}/{threshold} samples collected.",
            "affected_count": sample_count,
            "recommended_action": (
                f"Keep running production; this signal unlocks at {threshold} samples "
                f"(currently {sample_count})."),
            "expected_improvement": "med",
        }

    def _finding(self, code, tier, severity, title, detail, affected, action, improvement):
        return {
            "signal_code": code, "tier": tier, "severity": severity,
            "title": title, "detail": detail, "affected_count": affected,
            "recommended_action": action, "expected_improvement": improvement,
        }

    def _maybe_blocker(self, code, sub_score, title, detail, affected, action):
        """Emit a structural finding; severity escalates to blocker below threshold."""
        if sub_score < BLOCKER_THRESHOLD:
            sev, imp = "blocker", "high"
        elif sub_score < 75:
            sev, imp = "warn", "high"
        else:
            sev, imp = "info", "med"
        return self._finding(code, "structural", sev, title, detail, affected, action, imp)

    # --------------------------------------------------------- structural S1-S7
    def _eval_s1(self, company, productions, horizon_days):
        code = "S1_ROUTING_COVERAGE"
        total = len(productions)
        if total == 0:
            return None, [self._finding(
                code, "structural", "info", "No manufacturing orders in scope",
                "No MRP data to evaluate — the factory is not yet schedulable.",
                0, "Create manufacturing orders with routings to begin.", "high")]
        uncovered = productions.filtered(
            lambda p: not (p.bom_id and p.bom_id.operation_ids))
        pct = 100.0 * (total - len(uncovered)) / total
        f = self._maybe_blocker(
            code, pct, f"{len(uncovered)} of {total} MOs have no routing operations",
            "A manufacturing order whose BoM has no operations cannot be scheduled "
            "or estimated.", len(uncovered),
            "Add routing operations to the BoMs of the affected products.")
        return pct, ([f] if uncovered else [])

    def _ops_in_scope(self, productions):
        ops = self.env["mrp.routing.workcenter"]
        for p in productions:
            if p.bom_id:
                ops |= p.bom_id.operation_ids
        return ops

    def _eval_s2(self, company, productions, horizon_days):
        code = "S2_WC_ASSIGNED"
        ops = self._ops_in_scope(productions)
        if not ops:
            return None, []
        assigned = ops.filtered(lambda o: o.workcenter_id)
        pct = 100.0 * len(assigned) / len(ops)
        distinct_wc = len(set(assigned.mapped("workcenter_id").ids))
        penalty = 20.0 if (distinct_wc <= 1 and len(ops) > 5) else 0.0
        sub = _clamp(0.0, 100.0, pct - penalty)
        unassigned = len(ops) - len(assigned)
        if sub >= 75 and not penalty:
            return sub, []
        return sub, [self._maybe_blocker(
            code, sub, f"{unassigned} routing operations have no work center",
            "Operations without a work center cannot be capacity-scheduled; a single "
            "work center used for every operation is a rubber-stamp routing.",
            unassigned, "Assign a real work center to each routing operation.")]

    def _eval_s3(self, company, productions, horizon_days):
        code = "S3_TIME_REALISM"
        ops = self._ops_in_scope(productions)
        if not ops:
            return None, []
        placeholders = ops.filtered(
            lambda o: o.time_mode == "manual" and (not o.time_cycle_manual
                                                    or o.time_cycle_manual in (60.0,)))
        pct = 100.0 * (len(ops) - len(placeholders)) / len(ops)
        if pct >= 75:
            return pct, []
        return pct, [self._maybe_blocker(
            code, pct, f"{len(placeholders)} operations use placeholder times",
            "Operation times left at Odoo defaults (0 or 60 min) make every duration "
            "estimate fiction.", len(placeholders),
            "Set realistic cycle times per operation.")]

    def _wcs_for_company(self, company):
        return self.env["mrp.workcenter"].search([("company_id", "=", company.id)])

    def _eval_s4(self, company, productions, horizon_days):
        code = "S4_CALENDAR"
        wcs = self._wcs_for_company(company)
        if not wcs:
            return None, []
        valid = wcs.filtered(
            lambda w: w.resource_calendar_id and w.resource_calendar_id.attendance_ids)
        pct = 100.0 * len(valid) / len(wcs)
        if pct >= 75:
            return pct, []
        return pct, [self._maybe_blocker(
            code, pct, f"{len(wcs) - len(valid)} work centers have no working calendar",
            "Without a calendar with attendances, available capacity cannot be computed.",
            len(wcs) - len(valid), "Assign a working-hours calendar to each work center.")]

    def _eval_s5(self, company, productions, horizon_days):
        code = "S5_CAPACITY"
        wcs = self._wcs_for_company(company)
        if not wcs:
            return None, []
        # v19 mrp.workcenter has no scalar `capacity` (it is per-product
        # `capacity_ids`); time_efficiency is a percentage. Treat a work center as
        # capacity-configured when its efficiency is set to a sane positive value.
        valid = wcs.filtered(lambda w: w.time_efficiency and w.time_efficiency > 0)
        pct = 100.0 * len(valid) / len(wcs)
        if pct >= 75:
            return pct, []
        return pct, [self._maybe_blocker(
            code, pct, f"{len(wcs) - len(valid)} work centers have no efficiency set",
            "Time efficiency drives finite-capacity load; a zero/blank value distorts "
            "utilization.", len(wcs) - len(valid),
            "Set a realistic time efficiency on each work center.")]

    def _eval_s6(self, company, productions, horizon_days):
        code = "S6_DATE_AUTHENTICITY"
        with_deadline = productions.filtered(lambda p: p.date_deadline)
        total = len(productions)
        if total == 0:
            return None, []
        no_deadline_pct = 100.0 * (total - len(with_deadline)) / total
        suspect = self.env["mrp.production"]
        for p in with_deadline:
            routing_min = sum(p.workorder_ids.mapped("duration_expected"))
            naive = p.create_date + timedelta(minutes=routing_min)
            if abs((p.date_deadline - naive).total_seconds()) < 300:
                suspect |= p
        if with_deadline:
            pct_authentic = 100.0 * (len(with_deadline) - len(suspect)) / len(with_deadline)
        else:
            pct_authentic = 100.0
        sub = _clamp(0.0, 100.0, 0.7 * pct_authentic + 0.3 * (100.0 - no_deadline_pct))
        affected = len(suspect) + (total - len(with_deadline))
        if sub >= 75:
            return sub, []
        return sub, [self._maybe_blocker(
            code, sub,
            f"{len(suspect)} MO deadlines are mechanically derived, {total - len(with_deadline)} missing",
            "A deadline equal to create-date plus routing time is a system artifact, not "
            "a real customer commitment — delivery predictions built on it are fiction.",
            affected, "Anchor MO deadlines to real customer/commitment dates.")]

    def _calendar_open_fraction(self, calendar):
        if not calendar or not calendar.attendance_ids:
            return 5.0 / 7.0 * (8.0 / 24.0)  # sane default ~ 40h week
        weekly_hours = sum(max(0.0, a.hour_to - a.hour_from) for a in calendar.attendance_ids)
        return _clamp(0.01, 1.0, weekly_hours / (7.0 * 24.0))

    def _eval_s7(self, company, productions, horizon_days):
        code = "S7_OVERLOAD"
        wcs = self._wcs_for_company(company)
        if not wcs:
            return None, []
        now = fields.Datetime.now()
        horizon_end = now + timedelta(days=horizon_days)
        overloaded = 0
        utils = []
        for wc in wcs:
            wos = self.env["mrp.workorder"].search([
                ("workcenter_id", "=", wc.id),
                ("state", "not in", ("done", "cancel")),
                ("date_start", "<=", horizon_end),
            ])
            demand = sum(wos.mapped("duration_expected"))
            frac = self._calendar_open_fraction(wc.resource_calendar_id)
            eff = (wc.time_efficiency or 100.0) / 100.0   # percentage → multiplier
            available = horizon_days * 24 * 60 * eff * frac
            util = demand / available if available else 2.0
            utils.append(util)
            if util > 1.0:
                overloaded += 1
        pct_overloaded = 100.0 * overloaded / len(wcs)
        avg_util = sum(utils) / len(utils) if utils else 0.0
        sub = _clamp(0.0, 100.0, 100.0 - pct_overloaded - max(0.0, (avg_util - 1.0)) * 50.0)
        if sub >= 75:
            return sub, []
        return sub, [self._maybe_blocker(
            code, sub, f"{overloaded} of {len(wcs)} work centers are over capacity",
            "Scheduled load exceeds available capacity over the planning horizon; "
            "promised dates cannot all be met.", overloaded,
            "Rebalance load, add capacity, or extend the horizon.")]

    # ------------------------------------------------------- behavioral B1-B4
    def _eval_b1(self, company, window_start):
        code = "B1_DATE_CHURN"
        mos = self.env["mrp.production"].search([
            ("company_id", "=", company.id), ("create_date", ">=", window_start)])
        sample_count = len(mos)
        tracking = self._model_or_none("mail.tracking.value")
        if not tracking or not sample_count:
            return 0.0, sample_count, []
        try:
            msgs = tracking.search_count([
                ("mail_message_id.model", "=", "mrp.production"),
                ("mail_message_id.res_id", "in", mos.ids),
            ])
        except Exception:  # tracking not enabled on the fields — treat as no churn signal
            msgs = 0
        avg_churn = msgs / sample_count if sample_count else 0.0
        sub = _clamp(0.0, 100.0, 100.0 - avg_churn * 25.0)
        return sub, sample_count, []

    def _eval_b2(self, company, window_start):
        code = "B2_ESTIMATE_ACCURACY"
        obs_model = self._model_or_none("oiq.completion.observation")
        if obs_model is None:
            return 0.0, 0, []
        obs = obs_model.search([("observed_at", ">=", window_start)])
        if not obs:
            return 0.0, 0, []
        mape = sum(abs((o.ratio or 1.0) - 1.0) for o in obs) / len(obs)
        return _clamp(0.0, 100.0, 100.0 - mape * 100.0), len(obs), []

    def _eval_b3(self, company, window_start):
        code = "B3_OVERRIDE_RATE"
        slot_model = self._model_or_none("oiq.schedule.slot")
        if slot_model is None:
            return 0.0, 0, []
        wos = self.env["mrp.workorder"].search([
            ("company_id", "=", company.id), ("state", "=", "done"),
            ("date_start", ">=", window_start)])
        matched = overridden = 0
        for wo in wos:
            slot = slot_model.search([("workorder_id", "=", wo.id)], order="run_id desc", limit=1)
            if not slot:
                continue
            matched += 1
            if wo.date_start and abs((wo.date_start - slot.planned_start).total_seconds()) > 4 * 3600:
                overridden += 1
        if not matched:
            return 0.0, 0, []
        return _clamp(0.0, 100.0, 100.0 - 100.0 * overridden / matched), matched, []

    def _eval_b4(self, company, window_start):
        code = "B4_ON_TIME"
        mos = self.env["mrp.production"].search([
            ("company_id", "=", company.id), ("state", "=", "done"),
            ("date_finished", ">=", window_start), ("date_deadline", "!=", False)])
        if not mos:
            return 0.0, 0, []
        on_time = len(mos.filtered(lambda m: m.date_finished <= m.date_deadline))
        return 100.0 * on_time / len(mos), len(mos), []

    # ==================================================================
    # Shadow scheduling engine (§6) — read-only vs MRP
    # ==================================================================
    def shadow_schedule(self, company, horizon_days=14):
        """Compute a capacity-aware EDD-greedy shadow schedule and persist it as
        an ``oiq.schedule.run`` with its slots. Never writes to mrp.*."""
        run = self.env["oiq.schedule.run"].create({
            "date": fields.Datetime.now(),
            "company_id": company.id,
            "horizon_days": horizon_days,
            "algorithm": "edd_greedy",
            "state": "computing",
        })
        try:
            mos = self._gather_ready_mos(company, horizon_days)
            cal_map = self._load_calibration_factors(company)
            queue = self._explode_to_workorders(mos, cal_map)
            queue = self._edd_sort(queue)
            slots = self._forward_pass(queue)
            self._persist_slots(run, slots)

            if slots:
                starts = [s["planned_start"] for s in slots]
                finishes = [s["planned_finish"] for s in slots]
                makespan = (max(finishes) - min(starts)).total_seconds() / 60.0
            else:
                makespan = 0.0
            late = sum(1 for s in slots if s["is_final"] and s["deadline"]
                       and s["predicted_complete"] > s["deadline"])
            run.write({"state": "complete", "makespan_min": makespan,
                       "predicted_late_count": late})
        except Exception as e:  # noqa: BLE001 — record failure, then re-raise
            run.write({"state": "failed", "notes": str(e)})
            raise
        return run

    def backfill_actuals(self, company):
        """Fill ``vs_actual_delta_min`` for slots whose workorder has completed.
        Read-only vs MRP (writes only oiq.schedule.slot)."""
        slots = self.env["oiq.schedule.slot"].search([
            ("vs_actual_delta_min", "=", False),
            ("run_id.company_id", "=", company.id),
        ])
        for slot in slots:
            wo = slot.workorder_id
            if wo.state == "done" and wo.date_finished and slot.predicted_complete:
                slot.vs_actual_delta_min = (
                    wo.date_finished - slot.predicted_complete).total_seconds() / 60.0

    # ---- gather ----
    def _gather_ready_mos(self, company, horizon_days):
        from datetime import timedelta as _td
        domain = [
            ("company_id", "=", company.id),
            ("state", "in", ("confirmed", "progress")),
        ]
        cap = fields.Datetime.now() + _td(days=horizon_days)
        mos = self.env["mrp.production"].search(domain)
        result = self.env["mrp.production"]
        for mo in mos:
            # optional horizon cap on deadline (unbounded MOs still included)
            if mo.date_deadline and mo.date_deadline > cap:
                continue
            if self._components_available(mo):
                result |= mo
        return result

    def _components_available(self, mo):
        if "components_availability_state" in mo._fields:
            return mo.components_availability_state in ("available", "assigned", False)
        return True

    # ---- calibration lookup (empty until Step 3 ships the model) ----
    def _load_calibration_factors(self, company):
        model = self._model_or_none("oiq.calibration.factor")
        if model is None:   # empty recordset is falsy — must test identity, not truth
            return {}
        return {(f.scope, f.key): f
                for f in model.search([("company_id", "=", company.id)])}

    def _calibrated_duration(self, wo, cal_map):
        base = wo.duration_expected or self._fallback_duration(wo)
        op_cat = self._operation_category(wo)
        family = self._product_family(wo.production_id.product_id)
        candidates = [
            ("composite", f"{family}::{op_cat}::{wo.workcenter_id.id}"),
            ("operation_category", op_cat),
            ("product_family", family),
            ("workcenter", str(wo.workcenter_id.id)),
        ]
        factor = None
        for key in candidates:
            f = cal_map.get(key)
            if f and f.sample_count >= MIN_CALIB_SAMPLE:
                factor = f
                break
        multiplier = factor.multiplier if factor else 1.0
        confidence = factor.confidence if factor else 0.0
        return base * multiplier, confidence

    def _fallback_duration(self, wo):
        op = wo.operation_id if "operation_id" in wo._fields else None
        if op and getattr(op, "time_cycle_manual", 0):
            return op.time_cycle_manual
        return DEFAULT_FALLBACK_MIN

    def _operation_category(self, wo):
        """Normalized, low-cardinality operation category (shared by capture and
        scheduler so learned and applied keys agree)."""
        op = wo.operation_id if "operation_id" in wo._fields else None
        base = ((op.name if op else "") or wo.name
                or (wo.workcenter_id.name if wo.workcenter_id else "") or "")
        low = base.lower()
        for kw, cat in OP_KEYWORDS.items():
            if kw in low:
                return cat
        return low or "unknown"

    def _product_family(self, product):
        tmpl = product.product_tmpl_id
        if "x_product_family" in tmpl._fields and getattr(product, "x_product_family", False):
            return product.x_product_family
        categ = product.categ_id
        return (categ.complete_name or categ.name) if categ else ""

    def _explode_to_workorders(self, mos, cal_map):
        queue = []
        for mo in mos:
            for seq, wo in enumerate(mo.workorder_ids.sorted(key=lambda w: w.id)):
                cal_min, conf = self._calibrated_duration(wo, cal_map)
                wc = wo.workcenter_id
                eff = (wc.time_efficiency or 100.0) / 100.0 if wc else 1.0
                queue.append({
                    "wo_id": wo.id, "production_id": mo.id,
                    "workcenter_id": wc.id if wc else False,
                    "seq": seq, "cal_min": cal_min, "efficiency": eff or 1.0,
                    "confidence": conf, "deadline": mo.date_deadline,
                    "is_bottleneck": bool(getattr(wc, "x_sbk_is_bottleneck", False)),
                    "priority": self._priority_level(mo),
                })
        return queue

    def _priority_level(self, mo):
        raw = getattr(mo, "x_sbk_priority_level", None)
        mapping = {"urgent": 3, "high": 2, "normal": 1, "low": 0}
        return mapping.get(raw, 0) if isinstance(raw, str) else 0

    # ---- solver ----
    def _edd_sort(self, queue):
        from datetime import datetime as _dt
        far = _dt(2999, 1, 1)
        return sorted(queue, key=lambda i: (
            i["deadline"] or far, -int(i["is_bottleneck"]), -i["priority"],
            i["production_id"], i["seq"]))

    def _forward_pass(self, queue):
        from datetime import timedelta as _td
        now = fields.Datetime.now()
        wc_free = {}       # workcenter_id -> next free datetime (single lane, capacity 1)
        mo_cursor = {}     # production_id -> earliest next-op start (flow-shop precedence)
        slots = []
        for item in queue:
            wc = item["workcenter_id"]
            not_before = max(wc_free.get(wc, now),
                             mo_cursor.get(item["production_id"], now), now)
            eff_min = item["cal_min"] / (item["efficiency"] or 1.0)
            start, finish = self._place_on_calendar(wc, not_before, eff_min)
            slots.append({
                "wo_id": item["wo_id"], "production_id": item["production_id"],
                "workcenter_id": wc, "seq": item["seq"],
                "planned_start": start, "planned_finish": finish,
                "deadline": item["deadline"], "confidence": item["confidence"],
                "is_final": False, "predicted_complete": finish,
            })
            wc_free[wc] = finish
            mo_cursor[item["production_id"]] = finish

        # MO-level completion + final-op flag + late_risk
        by_mo = {}
        for s in slots:
            by_mo.setdefault(s["production_id"], []).append(s)
        for mo_id, mo_slots in by_mo.items():
            final_finish = max(s["planned_finish"] for s in mo_slots)
            last = max(mo_slots, key=lambda s: (s["seq"], s["planned_finish"]))
            avg_conf = sum(s["confidence"] for s in mo_slots) / len(mo_slots)
            for s in mo_slots:
                s["predicted_complete"] = final_finish
                s["late_risk"] = self._late_risk(s["deadline"], final_finish, avg_conf)
            last["is_final"] = True
        return slots

    def _place_on_calendar(self, wc_id, not_before, minutes):
        from datetime import timedelta as _td
        wc = self.env["mrp.workcenter"].browse(wc_id) if wc_id else None
        cal = wc.resource_calendar_id if wc else None
        finish = None
        if cal:
            try:
                finish = cal.plan_hours(minutes / 60.0, not_before, compute_leaves=False)
            except Exception:  # calendar API variance — fall back to wall-clock
                finish = None
        if not finish:
            finish = not_before + _td(minutes=minutes)
        return not_before, finish

    def _late_risk(self, deadline, final_finish, avg_conf):
        if not deadline:
            return 50.0
        slack_min = (deadline - final_finish).total_seconds() / 60.0
        penalty = (1.0 - avg_conf) * RISK_CONF_WEIGHT
        if slack_min <= 0:
            return min(100.0, 70.0 + abs(slack_min) / LATE_SCALE_MIN + penalty)
        return max(0.0, 40.0 - (slack_min / EARLY_SCALE_MIN) + penalty)

    def _persist_slots(self, run, slots):
        SlotModel = self.env["oiq.schedule.slot"]
        for s in slots:
            wo = self.env["mrp.workorder"].browse(s["wo_id"])
            vs_odoo = False
            if wo.date_start:
                vs_odoo = (s["planned_finish"] - (
                    wo.date_finished or wo.date_start)).total_seconds() / 60.0
            vals = {
                "run_id": run.id, "production_id": s["production_id"],
                "workorder_id": s["wo_id"], "workcenter_id": s["workcenter_id"],
                "seq": s["seq"], "planned_start": s["planned_start"],
                "planned_finish": s["planned_finish"],
                "predicted_complete": s["predicted_complete"],
                "late_risk": s["late_risk"],
            }
            if vs_odoo is not False:
                vals["vs_odoo_delta_min"] = vs_odoo
            SlotModel.create(vals)

    # ==================================================================
    # Calibration engine (§7) — the Factory Learning Graph (the moat)
    # ==================================================================
    def _actual_minutes(self, wo):
        if wo.duration:
            return wo.duration
        if wo.date_finished and wo.date_start:
            return (wo.date_finished - wo.date_start).total_seconds() / 60.0
        return 0.0

    def _capture_observation(self, wo):
        """Create one completion observation for a finished work order.
        Idempotent (UNIQUE(workorder_id) + explicit guard). Read-only vs MRP."""
        Obs = self.env["oiq.completion.observation"]
        if Obs.search_count([("workorder_id", "=", wo.id)]):
            return Obs
        estimated = wo.duration_expected or self._fallback_duration(wo)
        actual = self._actual_minutes(wo)
        if estimated <= 0 or actual <= 0:
            return Obs  # cannot learn from a zero — S3_TIME_REALISM flags this structurally
        return Obs.create({
            "workorder_id": wo.id,
            "production_id": wo.production_id.id,
            "product_id": wo.production_id.product_id.id,
            "product_family": self._product_family(wo.production_id.product_id),
            "operation_category": self._operation_category(wo),
            "workcenter_id": wo.workcenter_id.id,
            "estimated_min": estimated,
            "actual_min": actual,
            "context_json": json.dumps(self._observation_context(wo)),
            "observed_at": fields.Datetime.now(),
        })

    def _observation_context(self, wo):
        finished = wo.date_finished or fields.Datetime.now()
        return {"day_of_week": finished.weekday(),
                "workcenter_id": wo.workcenter_id.id}

    def harvest_completions(self, company):
        """Capture observations for any completed work orders not yet observed."""
        done = self.env["mrp.workorder"].search([
            ("production_id.company_id", "=", company.id),
            ("state", "=", "done"),
            ("date_finished", "!=", False),
        ])
        count = 0
        for wo in done:
            obs = self._capture_observation(wo)
            if obs:
                count += 1
        return count

    def recompute_calibration(self, company):
        """Roll observations up into per-scope calibration factors (§7.3.2/§7.4).
        Median-based (outlier robust) with a small-sample blend toward 1.0."""
        window_start = fields.Datetime.now() - timedelta(days=CALIB_WINDOW_DAYS)
        obs = self.env["oiq.completion.observation"].search([
            ("company_id", "=", company.id),
            ("observed_at", ">=", window_start),
            ("ratio", ">", 0),
        ])
        groups = {}   # (scope, key) -> [ratios]
        for o in obs:
            fam = o.product_family or ""
            opc = o.operation_category or ""
            wcid = str(o.workcenter_id.id)
            composite = f"{fam}::{opc}::{wcid}"
            for scope, key in (("composite", composite), ("product_family", fam),
                               ("operation_category", opc), ("workcenter", wcid)):
                if key:
                    groups.setdefault((scope, key), []).append(o.ratio)

        Factor = self.env["oiq.calibration.factor"]
        written = 0
        for (scope, key), ratios in groups.items():
            n = len(ratios)
            if n < MIN_SAMPLE_THRESHOLD:
                continue  # pass-through: no factor emitted below threshold
            med = statistics.median(ratios)
            mad = statistics.median([abs(r - med) for r in ratios]) if n > 1 else 0.0
            norm_var = (mad / med) if med else 0.0
            consistency = 1.0 / (1.0 + norm_var)
            sample_term = min(1.0, n / SAMPLE_SATURATION)
            confidence = round(sample_term * consistency, 3)
            if n < BLEND_FULL_TRUST_AT:
                w = (n - MIN_SAMPLE_THRESHOLD) / (BLEND_FULL_TRUST_AT - MIN_SAMPLE_THRESHOLD)
                multiplier = 1.0 * (1 - w) + med * w
            else:
                multiplier = med
            multiplier = max(multiplier, 0.01)
            vals = {"multiplier": multiplier, "sample_count": n,
                    "confidence": _clamp(0.0, 1.0, confidence),
                    "last_recomputed": fields.Datetime.now()}
            factor = Factor.search([
                ("company_id", "=", company.id), ("scope", "=", scope),
                ("key", "=", key)], limit=1)
            if factor:
                factor.write(vals)
            else:
                Factor.create({**vals, "company_id": company.id,
                               "scope": scope, "key": key})
            written += 1
        return written
