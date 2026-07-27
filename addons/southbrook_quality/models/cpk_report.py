# SPDX-License-Identifier: LGPL-3.0-only
"""Rolling Cpk report - SQL-view-backed.

Aggregates SPC samples over a rolling window (default 30 days, configurable
via ir.config_parameter ``southbrook_quality.cpk_window_days``) and computes
the process-capability index Cpk per (dimension_key, workcenter_id) pair.

This is a stat view, not a table - it has no write methods and refreshes
on demand via :meth:`action_refresh_view`.
"""

from odoo import _, fields, models, tools


class SouthbrookCpkReport(models.Model):
    _name = "southbrook.quality.cpk_report"
    _description = "Southbrook Cpk Rolling Report"
    _auto = False
    _order = "cpk asc"

    dimension_key = fields.Char(readonly=True)
    workcenter_id = fields.Many2one("mrp.workcenter", readonly=True)
    sample_count = fields.Integer(readonly=True)
    mean = fields.Float(readonly=True, digits=(16, 6))
    stddev = fields.Float(readonly=True, digits=(16, 6))
    usl = fields.Float(readonly=True, digits=(16, 6))
    lsl = fields.Float(readonly=True, digits=(16, 6))
    cpk = fields.Float(readonly=True, digits=(16, 6))

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        # Rolling window is configurable (documented in the module header).
        # Read it here and bake it into the view DDL; action_refresh_view
        # re-runs init() to pick up a changed value. Cast to int so the
        # interpolation can carry no injection.
        param = self.env["ir.config_parameter"].sudo().get_param(
            "southbrook_quality.cpk_window_days", "30")
        try:
            window_days = int(param)
        except (TypeError, ValueError):
            window_days = 30
        if window_days <= 0:
            window_days = 30
        # We treat (dimension_key, workcenter_id) as the natural key.
        # The synthesised primary id is hashtext(...) of that pair, which is
        # stable across refreshes and lets Odoo's ORM cache the rows.
        # STDDEV_SAMP (Bessel n-1) is the correct SAMPLE estimate of process
        # sigma; STDDEV_POP (n) understates variation and inflates Cpk, making
        # an incapable process look capable. n=1 → SAMP is NULL, and the
        # COALESCE→0.0 + the CASE below already yield a conservative Cpk 0.
        self.env.cr.execute(
            f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                WITH window_samples AS (
                    SELECT
                        s.dimension_key,
                        s.workcenter_id,
                        s.measured_value,
                        s.usl,
                        s.lsl
                    FROM southbrook_quality_spc_sample s
                    WHERE s.taken_at >= (NOW() AT TIME ZONE 'UTC')
                                        - INTERVAL '{window_days} days'
                      AND s.dimension_key IS NOT NULL
                      AND s.workcenter_id IS NOT NULL
                )
                SELECT
                    abs(hashtextextended(
                        coalesce(dimension_key, '') || '|' || workcenter_id::text,
                        0
                    )) AS id,
                    dimension_key,
                    workcenter_id,
                    COUNT(*)                                     AS sample_count,
                    AVG(measured_value)                          AS mean,
                    COALESCE(STDDEV_SAMP(measured_value), 0.0)   AS stddev,
                    MAX(usl)                                     AS usl,
                    MIN(lsl)                                     AS lsl,
                    CASE
                        WHEN COALESCE(STDDEV_SAMP(measured_value), 0.0) = 0.0
                            THEN 0.0
                        ELSE LEAST(
                            (MAX(usl) - AVG(measured_value))
                                / (3.0 * STDDEV_SAMP(measured_value)),
                            (AVG(measured_value) - MIN(lsl))
                                / (3.0 * STDDEV_SAMP(measured_value))
                        )
                    END                                          AS cpk
                FROM window_samples
                GROUP BY dimension_key, workcenter_id
            )
            """
        )

    def action_refresh_view(self):
        """Re-run :meth:`init` to re-create the SQL view definition. Useful
        if the rolling window parameter changed."""
        self.init()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Cpk Report"),
                "message": _("Rolling Cpk view refreshed."),
                "sticky": False,
            },
        }
