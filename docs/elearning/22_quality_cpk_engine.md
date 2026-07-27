---
course: 22
chapter: 22.4
title: Quality Module — Cpk Compute Engine
duration: 8
audience: Developer extending the Cpk computation
prereqs: Lessons 22.1 + 22.3
custom_modules: southbrook_quality
---

# Quality Module — Cpk Compute Engine

## The model

```python
class SouthbrookQualityCpkReport(models.Model):
    _name = "southbrook.quality.cpk_report"
    _description = "Process Capability Report"
```

Fields:

```python
dimension_id   = fields.Many2one(required=True)
period_days    = fields.Integer(default=30)
sample_count   = fields.Integer(readonly=True)
mean           = fields.Float(readonly=True, digits=(12, 4))
stdev          = fields.Float(readonly=True, digits=(12, 4))
cp             = fields.Float(readonly=True, digits=(8, 3))
cpk            = fields.Float(readonly=True, digits=(8, 3))
cpk_lower      = fields.Float(readonly=True, digits=(8, 3))
cpk_upper      = fields.Float(readonly=True, digits=(8, 3))
computed_at    = fields.Datetime(readonly=True)
sample_ids     = fields.Many2many(
    "southbrook.quality.spc_sample",
    compute="_compute_sample_ids", store=False)
```

## The compute

```python
def action_compute(self):
    self.ensure_one()
    domain = [
        ("dimension_id", "=", self.dimension_id.id),
        ("taken_at", ">=", fields.Datetime.now() -
                            relativedelta(days=self.period_days)),
    ]
    samples = self.env["southbrook.quality.spc_sample"].search(domain)
    if len(samples) < 5:
        raise UserError(_("Need at least 5 samples; have %d") % len(samples))
    values = samples.mapped("measured_value")
    n = len(values)
    mean = sum(values) / n
    stdev = (sum((v - mean) ** 2 for v in values) / (n - 1)) ** 0.5
    usl = self.dimension_id.usl
    lsl = self.dimension_id.lsl
    self.write({
        "sample_count": n,
        "mean": mean,
        "stdev": stdev,
        "cp": (usl - lsl) / (6 * stdev) if stdev else 0,
        "cpk_upper": (usl - mean) / (3 * stdev) if stdev else 0,
        "cpk_lower": (mean - lsl) / (3 * stdev) if stdev else 0,
        "cpk": min((usl - mean) / (3 * stdev) if stdev else 0,
                   (mean - lsl) / (3 * stdev) if stdev else 0),
        "computed_at": fields.Datetime.now(),
    })
```

## Notes on the math

### Sample standard deviation, not population
We divide by `(n - 1)`, not `n`. This is the standard estimator
for a finite sample. Using `n` would systematically underestimate
variability.

### Idempotent compute
Calling `action_compute()` twice in a row produces the same result
(deterministic). Useful for re-running after spotting an
adjustment.

### No statistical significance test
Cpk is reported as a point estimate. A confidence interval would
require knowing the sample size's effect on the estimate's
precision. Not implemented; v1.1 candidate.

## Trustworthiness threshold

Cpk on `< 30` samples is statistically noisy. The platform allows
compute at 5+ but the form displays a warning. Don't act on
sub-30-sample Cpk values.

## Common mistakes + how to recover

- **"Cpk = 0"** — `stdev = 0` because all samples were identical.
  Either the operator is measuring the same item repeatedly or
  the gauge has zero precision. Re-sample with calibrated tool.
- **"Cpk negative"** — process mean is outside spec entirely (mean <
  lsl OR mean > usl). Halt + investigate.
- **"Cpk recompute didn't change"** — same period + same samples =
  same result. Either the lookback didn't catch new samples
  (check `period_days`) or no new samples have come in.

## Customisation: add Pp (long-term capability)

Pp uses long-term standard deviation across multiple periods. To
add:

```python
pp = fields.Float(compute="_compute_pp")

def _compute_pp(self):
    # Compute stdev over a longer window (90 days)
    # then Pp = (usl - lsl) / (6 * long_term_stdev)
    ...
```

Pp will be lower than Cp for processes that drift; the
short-vs-long comparison is informative.

## Quiz

**Q1.** USL = 5.2, LSL = 4.8, mean = 5.0, stdev = 0.05, n = 100.
Cpk?

> Cp = (5.2 - 4.8) / (6 × 0.05) = 1.333
> Cpk_upper = (5.2 - 5.0) / (0.15) = 1.333
> Cpk_lower = (5.0 - 4.8) / (0.15) = 1.333
> Cpk = min = **1.333** (capable)

**Q2.** Same except mean = 5.10. Cpk?

> Cpk_upper = (5.2 - 5.1) / (0.15) = 0.667
> Cpk_lower = (5.1 - 4.8) / (0.15) = 2.0
> Cpk = **0.667** (NOT capable, drifted high)

**Q3.** stdev computed using `n` instead of `n-1`. Effect on Cpk?

> Underestimates stdev → overstates Cpk. Process looks more
> capable than it is. Don't do this.

**Q4.** Cpk = 1.5 with sample_count = 8. Action?

> Wait. 8 samples is too few; the 1.5 estimate has huge confidence
> interval. Sample more, recompute at 30+.

**Q5.** USL or LSL missing on dimension. Compute called. What
happens?

> `usl - lsl = None - None = TypeError`. Add a validation in
> `action_compute()` to raise UserError if usl/lsl unset.
