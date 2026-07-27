---
course: 22
chapter: 22.3
title: Quality Module — SPC Sample Model and Control Limit Math
duration: 10
audience: Developer working on SPC sample logic or chart rendering
prereqs: Lesson 22.1, basic statistics
custom_modules: southbrook_quality
---

# Quality Module — SPC Sample Model and Control Limit Math

## The model

```python
class SouthbrookQualitySpcSample(models.Model):
    _name = "southbrook.quality.spc_sample"
    _description = "SPC Sample"
    _order = "taken_at desc"
```

Fields:

```python
dimension_id   = fields.Many2one("southbrook.quality.dimension",
                                 required=True, index=True)
workcenter_id  = fields.Many2one("mrp.workcenter", required=True)
measured_value = fields.Float(required=True, digits=(12, 4))
sample_size    = fields.Integer(default=5)
operator_id    = fields.Many2one("res.users",
                                 default=lambda s: s.env.user)
taken_at       = fields.Datetime(default=fields.Datetime.now)
is_in_control  = fields.Boolean(compute="_compute_in_control",
                                store=True)
```

`is_in_control` is stored (not lazy) so search filters work.

## Control limit computation

Control limits are recomputed on each sample create. The math:

```python
@api.model
def _compute_control_limits(self, dimension_id, workcenter_id):
    """Return (centre, ucl, lcl) for the dimension+workcenter pair."""
    samples = self.search([
        ("dimension_id", "=", dimension_id),
        ("workcenter_id", "=", workcenter_id),
    ], limit=30, order="taken_at desc")
    if len(samples) < 5:
        # Not enough samples — fall back to dimension spec
        dim = self.env["southbrook.quality.dimension"].browse(dimension_id)
        return dim.nominal, dim.nominal + (dim.usl - dim.nominal) * 0.66, \
               dim.nominal - (dim.nominal - dim.lsl) * 0.66
    values = samples.mapped("measured_value")
    mean = sum(values) / len(values)
    stdev = (sum((v - mean) ** 2 for v in values) / (len(values) - 1)) ** 0.5
    k = 2 if samples[0].dimension_id.is_critical else 3
    return mean, mean + k * stdev, mean - k * stdev
```

Notes:
- 30-sample lookback hard-coded; adjust if you need more
- Critical dimensions use 2σ; normal use 3σ
- Fall-back to dimension spec when < 5 samples avoid divide-by-zero

## Western Electric rules

Rule detection runs in `_check_western_electric_rules()`:

```python
def _check_western_electric_rules(self):
    """Returns list of violated rule numbers (empty if clean)."""
    # Rule 1: one point > 3σ (or > UCL for our control limits)
    # Rule 2: 2 of 3 consecutive points > 2σ same side
    # Rule 3: 4 of 5 consecutive points > 1σ same side
    # Rule 4: 9 consecutive points one side of centre
    violations = []
    # ... rule detection ...
    return violations
```

When violations fire, `is_in_control = False` is set on the sample.
The MI engine subscribes via `mi_engine_ext.py`.

## Chart rendering

The chart is an OWL component (`southbrook_quality.spc_chart_widget`)
reading the last 20 samples via JSON-RPC. Cached 60s in the browser
via SWR pattern; not server-side cached.

## Common mistakes + how to recover

- **"Sample created but is_in_control = False even though value
  looks fine"** — control limits may be very tight if recent
  samples were clustered. Investigate by reading actual
  `_compute_control_limits()` output.
- **"30-sample lookback truncates older context"** — increase the
  limit (be careful — long histories can include obsolete process
  conditions, distorting limits).
- **"Critical dimensions trigger too many false positives"** — 2σ
  limits are by design tighter. If false positives dominate,
  reconsider whether the dimension is truly critical.

## Customisation: alternative control chart types

The default chart is an X-bar (sample mean) chart. To add an R-bar
(range) chart:

```python
def _compute_range(self):
    # Group by dimension+workcenter, return range per period
    ...
```

Add a new view + widget; route via dimension's `chart_type`
selection.

## Quiz

**Q1.** New sample with value 4.95 on a normal dimension (3σ).
Last 30 samples cluster around 5.0 with stdev 0.02. In control?

> Mean ± 3σ = 5.0 ± 0.06 = (4.94, 5.06). 4.95 is inside → in control.

**Q2.** Same dimension marked critical (2σ). Same sample?

> Mean ± 2σ = 5.0 ± 0.04 = (4.96, 5.04). 4.95 is BELOW LCL → out of
> control.

**Q3.** Sample lookback is 30. Process changed significantly 60
days ago. Limits reflect what?

> The last 30 samples — so post-change conditions only. Good IF
> sample density is < 30 samples per 60 days. If denser, limits
> may still reflect old behaviour.

**Q4.** You want to surface rule-4 (9 consecutive points one side)
breaches to Hermes. Where?

> Add a hook in `_check_western_electric_rules()` that posts a
> recommendation via `mi_engine_ext`. Don't compute Hermes calls
> from the chart widget — keep render lean.

**Q5.** Chart cache TTL is 60s. Sample entered now; visible in
chart?

> Within 60s due to client cache. Force refresh = explicit
> `chart_refresh()` action on the widget.
