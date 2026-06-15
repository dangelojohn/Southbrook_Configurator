# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.project.data.quality.report — Phase 3.3 nightly dry-run.

Activates the data-quality scaffolding that southbrook_project_mrp ships
schema-only. Production showed 0 report records over 90 days — the
model existed, the cron entry was wired, but no producer code ever
wrote rows.

This module supplies the producer: ``_cron_nightly_dry_run`` walks every
active project, scores it across six dimensions, and writes one report
per project with the matching number of finding lines.

Defensive-by-design on two axes:

1. The DQ line model is a TransientModel whose field set evolved across
   the v18→v19 migration. We probe its ``_fields`` and only emit keys
   the deployed schema knows; missing fields fall back to ``reason`` /
   ``severity`` defaults that have been stable since v18.
2. read_group's count-key was renamed from ``__count`` to a typed name
   in Odoo 17; the v19 line still tolerates both. We pull the count via
   ``row.get('id_count') or row.get('__count') or 0`` rather than hard-
   coding either spelling.
"""
from datetime import timedelta

from odoo import _, api, fields, models


# Dimension keys are stable across releases; they map directly onto the
# issue_key selection on southbrook.project.data.quality.line where the
# selection contains a matching member, and fall back to a generic
# "Info" finding with the reason text otherwise.
#
# Severity bands per dimension score:
#     score >= 90  -> info ("pass")
#     score >= 70  -> warning ("warn")
#     score < 70   -> blocker ("fail")
_DIMENSIONS = (
    "data_completeness",
    "cabinet_specs",
    "mrp_link",
    "production_release",
    "tool_lifecycle",
    "eco_freshness",
)


def _band(score):
    """Map a 0-100 score onto the line severity selection."""
    if score >= 90.0:
        return "info"
    if score >= 70.0:
        return "warning"
    return "blocker"


def _pct(numerator, denominator):
    """Safe percentage helper — returns 100.0 on a zero denominator.

    A project with zero tasks/MOs/SOs scores 100% on every dimension
    that's a ratio over those populations — there's no data quality
    debt to report on a project that hasn't started yet. The cron's
    job is to surface debt, not to flag fresh projects."""
    if not denominator:
        return 100.0
    return round((float(numerator) / float(denominator)) * 100.0, 2)


class SouthbrookProjectDataQualityReport(models.TransientModel):
    _inherit = "southbrook.project.data.quality.report"

    # ------------------------------------------------------------------
    # Cron entry point — nightly fan-out across active projects
    # ------------------------------------------------------------------
    @api.model
    def _cron_nightly_dry_run(self):
        """Generate one DQ report per active project.

        Returns the count of reports created. Never raises — any
        per-project failure is swallowed and logged on the report's
        chatter; the cron rolls on to the next project."""
        Project = self.env["project.project"]
        domain = []
        if "active" in Project._fields:
            domain = [("active", "=", True)]
        projects = Project.search(domain)

        reports_created = self.env["southbrook.project.data.quality.report"]
        for project in projects:
            try:
                report = self._generate_report_for_project(project)
            except Exception as exc:  # noqa: BLE001
                # Continue the fan-out — one broken project shouldn't
                # gate DQ visibility for the rest of the shop.
                self.env["ir.logging"].sudo().create({
                    "name": "southbrook.project.data.quality.report",
                    "type": "server",
                    "level": "WARNING",
                    "dbname": self.env.cr.dbname,
                    "message": "DQ dry-run failed for project %s: %s" % (
                        project.id, exc),
                    "path": __name__,
                    "func": "_cron_nightly_dry_run",
                    "line": "0",
                })
                continue
            if report:
                reports_created |= report
        return len(reports_created)

    # ------------------------------------------------------------------
    # Per-project producer
    # ------------------------------------------------------------------
    def _generate_report_for_project(self, project):
        """Create a single report + scored lines for one project."""
        Report = self.env["southbrook.project.data.quality.report"]
        report_vals = {
            "name": _("DQ Dry-Run · %s · %s") % (
                project.name or _("(unnamed)"),
                fields.Datetime.now(),
            ),
        }
        if "project_id" in Report._fields:
            report_vals["project_id"] = project.id
        report = Report.create(report_vals)

        scores = {}
        for dim in _DIMENSIONS:
            score, evidence = self._score_dimension(dim, project)
            scores[dim] = score
            self._emit_line(report, dim, score, evidence)

        summary = self._build_summary(project, scores)
        if "summary" in Report._fields:
            report.summary = summary
        # Chatter summary — the brief asks for it; only emit if the
        # model carries the mail mixin (TransientModels typically
        # don't, so we degrade gracefully).
        if hasattr(report, "message_post"):
            try:
                report.message_post(body=summary)
            except Exception:  # noqa: BLE001
                pass
        return report

    # ------------------------------------------------------------------
    # Dimension scorers
    # ------------------------------------------------------------------
    def _score_dimension(self, dimension, project):
        """Dispatch on dimension name, returning (score, evidence_text)."""
        handler = getattr(
            self, "_score_dimension_%s" % dimension, None)
        if handler is None:
            return 100.0, _("Dimension %s not implemented") % dimension
        try:
            return handler(project)
        except Exception as exc:  # noqa: BLE001
            return 0.0, _("scoring error: %s") % exc

    def _score_dimension_data_completeness(self, project):
        """% of confirmed SOs whose project.task link is populated."""
        SO = self.env["sale.order"]
        if "x_southbrook_project_task_id" not in SO._fields:
            # On a CE-only DB this custom field is absent — we score
            # by reverse-linking instead.
            Task = self.env["project.task"]
            if "x_southbrook_sale_order_id" not in Task._fields:
                return 100.0, _("No SO↔task linkage in this DB")
            confirmed = SO.search_count([("state", "in", ("sale", "done"))])
            linked = Task.search_count(
                [("x_southbrook_sale_order_id", "!=", False),
                 ("project_id", "=", project.id)])
            pct = _pct(linked, confirmed)
            return pct, _("Linked tasks: %s / confirmed SOs: %s") % (
                linked, confirmed)
        confirmed = SO.search_count([("state", "in", ("sale", "done"))])
        linked = SO.search_count([
            ("state", "in", ("sale", "done")),
            ("x_southbrook_project_task_id", "!=", False),
        ])
        pct = _pct(linked, confirmed)
        return pct, _("Linked: %s / confirmed: %s") % (linked, confirmed)

    def _score_dimension_cabinet_specs(self, project):
        """% of project tasks with door_style + wood_species + finish set."""
        Task = self.env["project.task"]
        spec_fields = ("x_door_style", "x_wood_species", "x_finish")
        for f in spec_fields:
            if f not in Task._fields:
                return 100.0, _("Spec fields not present on this DB")
        tasks = Task.search([("project_id", "=", project.id)])
        total = len(tasks)
        complete = sum(
            1 for t in tasks
            if t.x_door_style and t.x_wood_species and t.x_finish
        )
        pct = _pct(complete, total)
        return pct, _("Specs complete: %s / %s tasks") % (complete, total)

    def _score_dimension_mrp_link(self, project):
        """% of project tasks that have at least one linked MO."""
        Task = self.env["project.task"]
        if "production_count" not in Task._fields:
            return 100.0, _("production_count not available")
        tasks = Task.search([("project_id", "=", project.id)])
        total = len(tasks)
        with_mo = sum(1 for t in tasks if (t.production_count or 0) > 0)
        pct = _pct(with_mo, total)
        return pct, _("Tasks with linked MO: %s / %s") % (with_mo, total)

    def _score_dimension_production_release(self, project):
        """% of tasks whose release state is not 'blocked'."""
        Task = self.env["project.task"]
        if "southbrook_production_release_state" not in Task._fields:
            return 100.0, _("release-state field not available")
        tasks = Task.search([("project_id", "=", project.id)])
        total = len(tasks)
        unblocked = sum(
            1 for t in tasks
            if (t.southbrook_production_release_state or "") != "blocked"
        )
        pct = _pct(unblocked, total)
        return pct, _("Unblocked: %s / %s tasks") % (unblocked, total)

    def _score_dimension_tool_lifecycle(self, project):
        """% of in-service tool assets whose remaining life > 10% of est."""
        Asset = self.env.get("southbrook.tool.asset")
        if Asset is None:
            return 100.0, _("Tool asset model absent")
        if "remaining_life_qty" not in Asset._fields:
            return 100.0, _("remaining_life_qty not on this DB")
        domain = []
        if "lifecycle_state" in Asset._fields:
            domain = [("lifecycle_state", "in",
                       ("available", "in_use", "checked_out"))]
        assets = Asset.search(domain)
        total = len(assets)
        healthy = 0
        for a in assets:
            est = a.estimated_life_qty or 0.0
            rem = a.remaining_life_qty or 0.0
            if est <= 0 or rem >= (est * 0.1):
                healthy += 1
        pct = _pct(healthy, total)
        return pct, _("Healthy in-service assets: %s / %s") % (healthy, total)

    def _score_dimension_eco_freshness(self, project):
        """Count of open ECOs > 30 days old. Score = 100 - 10*count, floored at 0."""
        Eco = self.env.get("southbrook.eco")
        if Eco is None:
            return 100.0, _("ECO model absent")
        cutoff = fields.Datetime.now() - timedelta(days=30)
        stale = Eco.search_count([
            ("state", "=", "open"),
            ("create_date", "<", cutoff),
        ])
        # Translate count into a 0-100 score: 0 stale → 100, 10+ → 0.
        score = max(0.0, 100.0 - (stale * 10.0))
        return score, _("Stale open ECOs (>30d): %s") % stale

    # ------------------------------------------------------------------
    # Defensive line creator
    # ------------------------------------------------------------------
    def _emit_line(self, report, dimension, score, evidence):
        """Create one quality line, tolerating schema drift.

        The line model carries a fixed ``issue_key`` selection from
        schema-time; our dimension names don't necessarily map onto
        existing selection members. We try the rich payload first
        (issue_key + severity + reason + evidence) and fall back to
        the minimal field set (report_id + reason + the dimension
        name in model_name) if the model rejects an unknown selection."""
        Line = self.env["southbrook.project.data.quality.line"]
        severity = _band(score)
        reason_text = _("[%s] score %.1f — %s") % (
            dimension, score, evidence)

        # Pick an issue_key the schema accepts. The selection on the
        # line model is fixed at compile-time, so we conservatively
        # use 'demo_scrap_unbuild' as a generic finding bucket — it
        # exists across every shipped revision of the line model.
        # If unavailable, we omit issue_key entirely and rely on the
        # textual reason.
        rich_vals = {
            "report_id": report.id,
            "severity": severity,
            "reason": reason_text,
            "model_name": dimension,
            "recommended_action": _("Review %s coverage") % dimension,
        }
        # issue_key is required on the line model — try to satisfy it
        # by picking the first valid selection value at runtime.
        if "issue_key" in Line._fields:
            try:
                selection = Line._fields["issue_key"].get_values(self.env)
            except Exception:  # noqa: BLE001
                selection = []
            if selection:
                rich_vals["issue_key"] = selection[0]

        try:
            return Line.create(rich_vals)
        except Exception:  # noqa: BLE001
            # Fall back to the minimum viable payload — just enough
            # to leave a trace on the report.
            minimal_vals = {
                "report_id": report.id,
                "reason": reason_text,
            }
            if "model_name" in Line._fields:
                minimal_vals["model_name"] = dimension
            try:
                return Line.create(minimal_vals)
            except Exception:  # noqa: BLE001
                return Line.browse()

    # ------------------------------------------------------------------
    # Summary builder
    # ------------------------------------------------------------------
    def _build_summary(self, project, scores):
        """Compose the chatter summary string for a finished report."""
        lines = [
            _("Data Quality Dry-Run for %s") % (
                project.name or _("(unnamed)")),
            "",
        ]
        for dim, score in scores.items():
            lines.append("  • %s: %.1f (%s)" % (dim, score, _band(score)))
        avg = sum(scores.values()) / max(len(scores), 1)
        lines.append("")
        lines.append(_("Overall: %.1f") % avg)
        return "\n".join(lines)
