# SPDX-License-Identifier: LGPL-3.0-only
"""Executive Dashboard snapshot — view-backed KPI rollup.

Each open creates a new record at :code:`fields.Datetime.now()` and computes
12 KPIs across MRP / Sales / Stock / Account / Quality / Finance /
Integrations. Downstream models (e.g. :code:`southbrook.mes_mps.bottleneck_*`)
are looked up via :code:`env.get(...)` so a missing Phase-6 install degrades
to "n/a" rather than ImportError.
"""

from datetime import timedelta

from odoo import _, api, fields, models


class ExecDashboardSnapshot(models.Model):
    _name = "southbrook.exec_dashboard.snapshot"
    _description = "Executive Dashboard Snapshot"
    _order = "as_of desc"

    as_of = fields.Datetime(
        string="As of",
        default=fields.Datetime.now,
        required=True,
        index=True,
    )
    label = fields.Char(default="Morning Briefing", required=True)

    # ---- Production ----
    yesterday_units_produced = fields.Integer(
        compute="_compute_kpis", store=False
    )
    yesterday_units_target = fields.Integer(compute="_compute_kpis", store=False)
    yesterday_takt_adherence_pct = fields.Float(
        compute="_compute_kpis", store=False
    )
    units_planned_today = fields.Integer(compute="_compute_kpis", store=False)

    # ---- Quality ----
    fpy_pct_7d = fields.Float(compute="_compute_kpis", store=False)
    quality_open_critical_ncr_count = fields.Integer(
        compute="_compute_kpis", store=False
    )

    # ---- Logistics ----
    otd_pct_30d = fields.Float(compute="_compute_kpis", store=False)

    # ---- Finance ----
    wip_value_current = fields.Monetary(
        compute="_compute_kpis",
        store=False,
        currency_field="currency_id",
    )
    revenue_last_30d = fields.Monetary(
        compute="_compute_kpis",
        store=False,
        currency_field="currency_id",
    )
    cash_position = fields.Monetary(
        compute="_compute_kpis",
        store=False,
        currency_field="currency_id",
    )

    # ---- MES (soft dependency) ----
    top_bottleneck_workcenter = fields.Char(compute="_compute_kpis", store=False)
    top_bottleneck_load_pct = fields.Float(compute="_compute_kpis", store=False)

    currency_id = fields.Many2one(
        related="company_id.currency_id",
        store=False,
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )

    # ------------------------------------------------------------------
    # KPI computation
    # ------------------------------------------------------------------
    @api.depends("as_of", "company_id")
    def _compute_kpis(self):
        for rec in self:
            data = rec._compute_kpi_payload()
            rec.yesterday_units_produced = data["yesterday_units_produced"]
            rec.yesterday_units_target = data["yesterday_units_target"]
            rec.yesterday_takt_adherence_pct = data["yesterday_takt_adherence_pct"]
            rec.units_planned_today = data["units_planned_today"]
            rec.fpy_pct_7d = data["fpy_pct_7d"]
            rec.quality_open_critical_ncr_count = data[
                "quality_open_critical_ncr_count"
            ]
            rec.otd_pct_30d = data["otd_pct_30d"]
            rec.wip_value_current = data["wip_value_current"]
            rec.revenue_last_30d = data["revenue_last_30d"]
            rec.cash_position = data["cash_position"]
            rec.top_bottleneck_workcenter = data["top_bottleneck_workcenter"]
            rec.top_bottleneck_load_pct = data["top_bottleneck_load_pct"]

    def _compute_kpi_payload(self):
        """Return a dict of all 12 KPI values. Pure data — used by both
        the compute method and the JSON controller."""
        self.ensure_one()
        env = self.env
        now = fields.Datetime.now()
        today = fields.Date.context_today(self)
        yesterday = today - timedelta(days=1)
        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)

        company_id = self.company_id.id or env.company.id

        # ---- Production: yesterday ----
        mo_done_yesterday = env["mrp.production"].search([
            ("company_id", "=", company_id),
            ("state", "=", "done"),
            ("date_finished", ">=", fields.Datetime.to_string(
                fields.Datetime.to_datetime(yesterday)
            )),
            ("date_finished", "<", fields.Datetime.to_string(
                fields.Datetime.to_datetime(today)
            )),
        ])
        units_produced = int(sum(mo_done_yesterday.mapped("product_qty") or [0]))

        mo_scheduled_yesterday = env["mrp.production"].search([
            ("company_id", "=", company_id),
            ("date_start", ">=", fields.Datetime.to_string(
                fields.Datetime.to_datetime(yesterday)
            )),
            ("date_start", "<", fields.Datetime.to_string(
                fields.Datetime.to_datetime(today)
            )),
        ])
        units_target = int(sum(mo_scheduled_yesterday.mapped("product_qty") or [0]))

        takt_pct = 0.0
        if units_target:
            takt_pct = (float(units_produced) / float(units_target)) * 100.0

        # ---- Production: today planned ----
        mo_today = env["mrp.production"].search([
            ("company_id", "=", company_id),
            ("date_start", ">=", fields.Datetime.to_string(
                fields.Datetime.to_datetime(today)
            )),
            ("date_start", "<", fields.Datetime.to_string(
                fields.Datetime.to_datetime(today + timedelta(days=1))
            )),
        ])
        units_planned_today = int(sum(mo_today.mapped("product_qty") or [0]))

        # ---- Quality: FPY 7d ----
        mo_count_7d = env["mrp.production"].search_count([
            ("company_id", "=", company_id),
            ("date_finished", ">=", seven_days_ago),
        ])
        ncr_model = env.get("southbrook.ncr")
        ncr_count_7d = 0
        critical_open = 0
        if ncr_model is not None:
            ncr_count_7d = ncr_model.sudo().search_count([
                ("create_date", ">=", seven_days_ago),
            ])
            crit_domain = [("state", "in", ("open", "new", "in_progress"))]
            # Only filter on severity if the field exists
            if "severity" in ncr_model._fields:
                crit_domain.append(("severity", "=", "critical"))
            critical_open = ncr_model.sudo().search_count(crit_domain)
        fpy = 100.0
        if mo_count_7d:
            fpy = (1.0 - (float(ncr_count_7d) / float(mo_count_7d))) * 100.0
            if fpy < 0.0:
                fpy = 0.0

        # ---- Logistics: OTD 30d ----
        pickings_30d = env["stock.picking"].search([
            ("company_id", "=", company_id),
            ("state", "=", "done"),
            ("date_done", ">=", thirty_days_ago),
            ("picking_type_code", "=", "outgoing"),
        ])
        otd = 100.0
        if pickings_30d:
            on_time = 0
            for p in pickings_30d:
                sched = p.scheduled_date or p.date_done
                if p.date_done and sched and p.date_done <= sched:
                    on_time += 1
            otd = (float(on_time) / float(len(pickings_30d))) * 100.0

        # ---- Finance: WIP ----
        wip_value = 0.0
        wip_model = env.get("southbrook.finance.wip_report")
        if wip_model is not None:
            wip_rec = wip_model.sudo().search(
                [("company_id", "=", company_id)],
                order="create_date desc",
                limit=1,
            )
            if wip_rec:
                # Try common field names, fall back to 0.0
                for fname in ("wip_value", "total_value", "value", "amount"):
                    if fname in wip_rec._fields:
                        wip_value = float(wip_rec[fname] or 0.0)
                        break

        # ---- Finance: revenue 30d ----
        invoices_30d = env["account.move"].search([
            ("company_id", "=", company_id),
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("invoice_date", ">=", thirty_days_ago.date()),
        ])
        revenue_30d = float(sum(invoices_30d.mapped("amount_untaxed") or [0.0]))

        # ---- Finance: cash position ----
        bank_journals = env["account.journal"].search([
            ("company_id", "=", company_id),
            ("type", "in", ("bank", "cash")),
        ])
        cash_position = 0.0
        for journal in bank_journals:
            accounts = journal.default_account_id
            if not accounts:
                continue
            self.env.cr.execute(
                """
                SELECT COALESCE(SUM(balance), 0.0)
                FROM account_move_line aml
                JOIN account_move am ON am.id = aml.move_id
                WHERE aml.account_id = %s
                  AND am.state = 'posted'
                  AND aml.company_id = %s
                """,
                (accounts.id, company_id),
            )
            row = self.env.cr.fetchone()
            if row and row[0]:
                cash_position += float(row[0])

        # ---- MES: bottleneck (soft dep) ----
        bottleneck_wc = "n/a"
        bottleneck_load = 0.0
        bn_model = env.get("southbrook.mes_mps.bottleneck_line")
        if bn_model is None:
            bn_model = env.get("southbrook.mes_mps.bottleneck_report")
        if bn_model is not None:
            bn = bn_model.sudo().search(
                [("company_id", "=", company_id)] if "company_id" in bn_model._fields else [],
                order="create_date desc",
                limit=1,
            )
            if bn:
                # Try a few plausible field shapes
                for wc_f in ("workcenter_id", "work_center_id", "resource_id"):
                    if wc_f in bn._fields and bn[wc_f]:
                        bottleneck_wc = bn[wc_f].display_name or bn[wc_f].name
                        break
                else:
                    if "name" in bn._fields:
                        bottleneck_wc = bn.name or "n/a"
                for load_f in ("load_pct", "load_percent", "load", "utilization"):
                    if load_f in bn._fields:
                        bottleneck_load = float(bn[load_f] or 0.0)
                        break

        return {
            "yesterday_units_produced": units_produced,
            "yesterday_units_target": units_target,
            "yesterday_takt_adherence_pct": takt_pct,
            "units_planned_today": units_planned_today,
            "fpy_pct_7d": fpy,
            "quality_open_critical_ncr_count": critical_open,
            "otd_pct_30d": otd,
            "wip_value_current": wip_value,
            "revenue_last_30d": revenue_30d,
            "cash_position": cash_position,
            "top_bottleneck_workcenter": bottleneck_wc,
            "top_bottleneck_load_pct": bottleneck_load,
        }

    def action_refresh(self):
        """Bump as_of so the compute re-runs, then re-open the same record."""
        self.ensure_one()
        self.write({"as_of": fields.Datetime.now()})
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    @api.model
    def get_or_create_today(self):
        """Return the latest snapshot for the active company (creating if
        no snapshot exists in the last 5 minutes)."""
        company = self.env.company
        recent_cutoff = fields.Datetime.now() - timedelta(minutes=5)
        existing = self.search(
            [
                ("company_id", "=", company.id),
                ("as_of", ">=", recent_cutoff),
            ],
            order="as_of desc",
            limit=1,
        )
        if existing:
            return existing
        return self.create({"company_id": company.id})
