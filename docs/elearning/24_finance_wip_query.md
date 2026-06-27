---
course: 24
chapter: 24.3
title: Finance Pack — WIP Report Query and GL Reconciliation
duration: 8
audience: Developer working on the WIP report or reconciliation logic
prereqs: Lesson 24.1, native Odoo MRP + Stock Valuation familiarity
custom_modules: southbrook_finance_pack
---

# Finance Pack — WIP Report Query and GL Reconciliation

## The model (read-only view)

```python
class SouthbrookFinanceWipReport(models.Model):
    _name = "southbrook.finance.wip_report"
    _description = "Work in Progress Report"
    _auto = False  # No table; backed by SQL view
    _rec_name = "mo_ref"
```

Fields are derived from the SQL view:

```python
mo_ref           = fields.Char(readonly=True)
product_id       = fields.Many2one("product.product", readonly=True)
responsible_team = fields.Char(readonly=True)
cost_so_far      = fields.Float(readonly=True)
cost_to_complete = fields.Float(readonly=True)
wip_value        = fields.Float(readonly=True)
```

## The SQL view

```sql
CREATE OR REPLACE VIEW southbrook_finance_wip_report AS
SELECT
    mp.id AS id,
    mp.name AS mo_ref,
    mp.product_id,
    rt.name AS responsible_team,
    COALESCE(SUM(sv.value), 0) AS cost_so_far,
    mp.product_qty * mp.product_id.standard_price - 
        COALESCE(SUM(sv.value), 0) AS cost_to_complete,
    COALESCE(SUM(sv.value), 0) AS wip_value
FROM mrp_production mp
LEFT JOIN mrp_workcenter wc ON wc.id = mp.workcenter_id
LEFT JOIN res_users ru ON ru.id = mp.user_id
LEFT JOIN res_partner rp ON rp.id = ru.partner_id
LEFT JOIN stock_move sm ON sm.raw_material_production_id = mp.id
    AND sm.state = 'done'
LEFT JOIN stock_valuation_layer sv ON sv.stock_move_id = sm.id
WHERE mp.state IN ('confirmed', 'progress')
GROUP BY mp.id, mp.name, mp.product_id, rt.name, mp.product_qty,
         mp.product_id.standard_price;
```

(Simplified — actual query joins more tables for full data.)

## Cron-cached snapshot

Live query is slow at scale. The cron snapshots into a stored
materialized table:

```python
@api.model
def _cron_snapshot_wip(self):
    self.env.cr.execute("""
        DELETE FROM southbrook_finance_wip_snapshot;
        INSERT INTO southbrook_finance_wip_snapshot
        SELECT * FROM southbrook_finance_wip_report;
    """)
```

Runs at 03:00 daily. The list view reads from snapshot during
business hours.

## GL reconciliation

The reconciliation is in the controller's head (lesson 20.2), but
the SQL helper produces the comparison:

```python
def gl_balance_query(self, company_id, period_end):
    """Return GL WIP account balance at period_end."""
    wip_account = self.env.company.wip_account_id.id
    self.env.cr.execute("""
        SELECT COALESCE(SUM(debit - credit), 0)
        FROM account_move_line
        WHERE account_id = %s
          AND date <= %s
          AND parent_state = 'posted'
    """, (wip_account, period_end))
    return self.env.cr.fetchone()[0]


def report_balance(self):
    return sum(self.search([]).mapped("wip_value"))


def reconciliation_variance(self, period_end):
    return self.report_balance() - self.gl_balance_query(
        self.env.company.id, period_end)
```

## Common mistakes + how to recover

- **"SQL view not refreshing"** — Postgres caches the view
  definition. Re-create on -u via `CREATE OR REPLACE VIEW` in the
  install hook.
- **"Snapshot empty"** — cron didn't run; snapshot is empty so
  list view shows nothing. Check `ir.cron` for the snapshot job.
- **"Variance always growing"** — likely backdated stock moves not
  reflected in the snapshot. Either rerun the snapshot manually
  or accept the staleness.

## Extension: per-team WIP target

To track WIP target vs actual:

```python
class SouthbrookFinanceWipTarget(models.Model):
    _name = "southbrook.finance.wip_target"
    
    responsible_team = fields.Char()
    target_amount = fields.Float()


# Then enhance the view to include the target.
```

## Quiz

**Q1.** Why a SQL view instead of a regular model?

> The data is fully derived from `mrp.production` + 
> `stock_valuation_layer`. No business reason for a separate
> table. View prevents stale Python-cached data.

**Q2.** Snapshot vs live query — when does which fire?

> List view → snapshot. Form view (drill-through) → live. Form
> needs current data; list can be a few hours stale.

**Q3.** WIP variance $0.50. Source?

> Standard cost rounding. Accept; document in close memo.

**Q4.** WIP variance grows by $100/day. Cause?

> An MO is closing without consumption posting, OR an MO has
> stock moves being added retroactively. Investigate via
> mrp.production audit log.

**Q5.** Add a WIP report column for "days_in_progress." Where?

> Add to the SQL view: `EXTRACT(EPOCH FROM (NOW() -
> mp.create_date)) / 86400 AS days_in_progress`. Then expose
> the field in the Python model.
