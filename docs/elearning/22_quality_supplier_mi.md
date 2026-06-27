---
course: 22
chapter: 22.6
title: Quality Module — Supplier Defect Rollup and MI Engine Integration
duration: 9
audience: Developer extending supplier scoring or MI engine integration
prereqs: Lessons 22.1, MI engine familiarity
custom_modules: southbrook_quality, southbrook_manufacturing_intelligence
---

# Quality Module — Supplier Defect Rollup and MI Engine Integration

## The supplier_defect model

```python
class SouthbrookQualitySupplierDefect(models.Model):
    _name = "southbrook.quality.supplier_defect"
    _description = "Supplier Defect"
    _inherit = ["mail.thread"]
```

Fields:

```python
supplier_id     = fields.Many2one("res.partner", required=True,
                                   domain="[('supplier_rank', '>', 0)]")
po_id           = fields.Many2one("purchase.order", required=True)
product_id      = fields.Many2one("product.product", required=True)
defect_count    = fields.Integer(default=1)
defect_type     = fields.Selection([...])
severity        = fields.Selection([...])
description     = fields.Text()
linked_ncr_ids  = fields.Many2many("southbrook.ncr")
is_warranty_claim = fields.Boolean(default=False)
detected_at     = fields.Date(default=fields.Date.context_today)
```

## The nightly rollup

Cron `cron_rollup_supplier_scores` runs at 03:30 daily:

```python
@api.model
def _cron_rollup_supplier_scores(self):
    for partner in self.env["res.partner"].search(
        [("supplier_rank", ">", 0)]):
        self._rollup_for_partner(partner)


def _rollup_for_partner(self, partner):
    period_days = 90
    cutoff = fields.Date.context_today() - relativedelta(days=period_days)
    defects = self.env["southbrook.quality.supplier_defect"].search([
        ("supplier_id", "=", partner.id),
        ("detected_at", ">=", cutoff),
    ])
    receipts = self.env["stock.move"].search([
        ("partner_id", "=", partner.id),
        ("state", "=", "done"),
        ("date", ">=", cutoff),
        ("location_dest_id.usage", "=", "internal"),
    ])
    total_defect_count = sum(d.defect_count for d in defects)
    total_received_qty = sum(r.product_uom_qty for r in receipts)
    
    defect_rate = total_defect_count / total_received_qty \
                  if total_received_qty else 0
    
    # on_time_delivery_pct from PO date vs receipt date
    on_time = self._compute_on_time(partner, cutoff)
    
    consolidated = 0.4 * (1 - defect_rate) + 0.4 * on_time + \
                   0.2 * partner.lead_time_consistency
    
    partner.write({
        "defect_rate_pct": defect_rate * 100,
        "on_time_delivery_pct": on_time * 100,
        "consolidated_score": consolidated,
    })
```

## Trend sparkline

The trend uses JSON storage on the partner:

```python
class ResPartner(models.Model):
    _inherit = "res.partner"
    
    score_trend = fields.Json(default=lambda s: [])
    # ... [0.85, 0.82, 0.78, ...]  — last 6 monthly snapshots
```

Sparkline rendered client-side from the JSON.

## MI engine integration

The MI engine surfaces three things from quality:

1. **Critical NCR opened** → recommendation for Plant GM
2. **SPC rule breach** → recommendation for quality manager
3. **Supplier score below threshold** → recommendation for
   purchasing manager

These hooks live in `mi_engine_ext.py`:

```python
class MiEngineExt(models.AbstractModel):
    _inherit = "southbrook.mi.engine"
    
    @api.model
    def _check_quality_signals(self):
        """Called from the MI engine's main loop."""
        # Critical NCRs
        critical_ncrs = self.env["southbrook.ncr"].search([
            ("severity", "=", "critical"),
            ("state", "in", ("open", "quarantine")),
        ])
        for ncr in critical_ncrs:
            self._emit_recommendation(
                subject=f"Critical NCR {ncr.name}",
                body=ncr.description or "",
                affected_records=ncr,
                persona="mfg_manager",
            )
```

## Adding a new MI signal

To surface a new type of quality signal:

1. Add detection logic to `_check_quality_signals()`
2. Use `_emit_recommendation()` with appropriate persona
3. The recommendation lands in `hermes.recommendation` for human
   review (Course 21 lesson 21.4)

## Common mistakes + how to recover

- **"Supplier scorecard doesn't update after I log defects"** —
  nightly cron. Same-day defects don't reflect until tomorrow.
- **"Critical NCR didn't surface to Hermes"** — MI engine cron
  didn't run, OR NCR severity wasn't `critical`, OR
  `_check_quality_signals()` errored mid-loop. Check logs.
- **"Score trend sparkline is empty"** — only populated after 6+
  months of rollups. First 5 months: sparkline blank.
- **"`linked_ncr_ids` empty even though defect was traced to a
  finished-goods NCR"** — auto-link only fires when `defect_type =
  material` AND PO is within 90-day lookback. Manual link
  otherwise.

## Quiz

**Q1.** Supplier received 1,000 units over 90 days; 5 defects
logged. Defect rate?

> 5 / 1,000 = 0.005 = 0.5%.

**Q2.** Same supplier, on-time delivery 92%, lead-time consistency
0.85. Consolidated score?

> 0.4 × (1 - 0.005) + 0.4 × 0.92 + 0.2 × 0.85
> = 0.398 + 0.368 + 0.17
> = **0.936**

**Q3.** Critical NCR opened. MI engine recommendation appears in
queue. Persona?

> `mfg_manager` (Plant GM). Configured in `_check_quality_signals()`.

**Q4.** Two MI cron loops both touch quality. Risk?

> Race condition on recommendation creation — both could emit the
> same rec. Solution: `_emit_recommendation()` should dedupe by
> subject + affected record + day.

**Q5.** You want to surface "supplier score dropped > 10% in one
month" as a recommendation. Where?

> Add a check in `_check_quality_signals()` comparing the new
> rollup to the prior month's score (from `score_trend` JSON).
> If delta < -0.10, emit a recommendation with `persona =
> "purchasing"`.
