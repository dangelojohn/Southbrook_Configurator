# Marathon Channel ROI Model — 12 Months

All figures in USD. Model assumes channel SKU live August 2026, exclusivity window through February 2027.

---

## Input variables

| Variable | Conservative | Base | Aggressive |
|---|---:|---:|---:|
| Shops onboarded in Q1 (Aug–Oct) | 25 | 40 | 60 |
| Shops onboarded in Q2 (Nov–Jan) | 55 | 90 | 140 |
| Shops onboarded in Q3 (Feb–Apr) | 90 | 150 | 240 |
| Shops onboarded in Q4 (May–Jul) | 110 | 180 | 290 |
| **Total active shops, end of Y1** | **280** | **460** | **730** |
| ARPU (subscription, $/mo/shop) | $149 | $149 | $149 |
| Avg cabinets / shop / month | 38 | 45 | 55 |
| Rebate paid by Marathon ($/cabinet) | $8 | $8 | $8 |
| Marathon share of subscription (40%) | $59.60 | $59.60 | $59.60 |
| Annual logo churn | 12% | 8% | 5% |

Quarterly cohort math uses mid-quarter activation (shops billed for ~half their first quarter), churn applied at year-end on the cumulative base.

---

## Conservative scenario — 280 shops, 38 cabinets/shop/mo

### Subscription revenue (Marathon's 40% share)

| Quarter | New shops | Active (mid-Q) | Marathon $/mo share | Quarterly Marathon sub revenue |
|---|---:|---:|---:|---:|
| Q1 | 25 | 12 | $715 | $2,145 |
| Q2 | 55 | 52 | $3,099 | $9,298 |
| Q3 | 90 | 125 | $7,450 | $22,350 |
| Q4 | 110 | 225 | $13,410 | $40,230 |
| **Y1 subtotal — Marathon sub share** | | | | **$74,023** |

### Rebate paid out (Marathon pays Southbrook)

Cabinets/year ≈ avg active shops × 12 × cabinets/shop/mo. Avg active = (12+52+125+225)/4 ≈ 104. Cabinets ≈ 104 × 12 × 38 = **47,424**. Rebate cost to Marathon = 47,424 × $8 = **$379,392**.

### Hardware pull-through (the real number)

Assume average Marathon hardware content per cabinet = $42 (drawer slides + hinges + pulls + misc), and pull-through capture rate = 78% (spec'd doesn't always equal ordered — substitutions, out-of-stock).
Pull-through hardware revenue ≈ 47,424 × $42 × 0.78 = **$1,553,617**.

### Net Marathon P&L contribution, Y1 conservative

| Line | Amount |
|---|---:|
| Subscription revenue (40% share) | + $74,023 |
| Hardware pull-through revenue | + $1,553,617 |
| Less: rebate paid to Southbrook | − $379,392 |
| Less: assumed gross-margin haircut on pull-through @ 28% | − $1,118,604 (COGS, est.) |
| **Net Y1 contribution to Marathon** | **≈ $129,644** |

Note: COGS haircut is conservative — Marathon's actual GM on cabinet-hardware mix is reported in the 30–35% range. We are intentionally lowballing.

Southbrook side of conservative case = $149 × 60% × cumulative shop-months ≈ **$111,034** subscription + $379,392 rebate = **~$490K** ARR-equivalent to Southbrook. Channel total ≈ **$1.0M** in combined recognizable revenue.

---

## Base scenario — 460 shops, 45 cabinets/shop/mo

### Subscription revenue (Marathon share)

| Quarter | New | Active (mid-Q) | Marathon quarterly |
|---|---:|---:|---:|
| Q1 | 40 | 20 | $3,576 |
| Q2 | 90 | 85 | $15,198 |
| Q3 | 150 | 205 | $36,654 |
| Q4 | 180 | 370 | $66,162 |
| **Y1 Marathon sub share** | | | **$121,590** |

Avg active ≈ 170. Cabinets ≈ 170 × 12 × 45 = **91,800**. Rebate = $734,400. Pull-through ≈ 91,800 × $42 × 0.80 = **$3,084,480**.

| Line | Amount |
|---|---:|
| Subscription (40%) | + $121,590 |
| Pull-through revenue | + $3,084,480 |
| Less: rebate | − $734,400 |
| Less: 28% COGS on pull-through | − $2,220,826 |
| **Net Y1 contribution** | **≈ $250,844** |

Southbrook side of base case ≈ **~$1.85M** combined channel revenue.

---

## Aggressive scenario — 730 shops, 55 cabinets/shop/mo

### Subscription revenue (Marathon share)

| Quarter | New | Active (mid-Q) | Marathon quarterly |
|---|---:|---:|---:|
| Q1 | 60 | 30 | $5,364 |
| Q2 | 140 | 130 | $23,244 |
| Q3 | 240 | 320 | $57,216 |
| Q4 | 290 | 585 | $104,598 |
| **Y1 Marathon sub share** | | | **$190,422** |

Avg active ≈ 266. Cabinets ≈ 266 × 12 × 55 = **175,560**. Rebate = $1,404,480. Pull-through ≈ 175,560 × $42 × 0.82 = **$6,044,486**.

| Line | Amount |
|---|---:|
| Subscription (40%) | + $190,422 |
| Pull-through revenue | + $6,044,486 |
| Less: rebate | − $1,404,480 |
| Less: 28% COGS on pull-through | − $4,352,030 |
| **Net Y1 contribution** | **≈ $478,398** |

Southbrook side of aggressive case ≈ **~$3.5M** combined channel revenue.

---

## Sensitivity — the variable Marathon should pressure-test

The model is dominated by **pull-through capture rate**. At 78% (conservative), Marathon nets +$129K in Y1. At 90% capture (achievable once auto-RFQ is tuned and stocking-depth alignment is in branch ops), Y1 conservative net climbs to ~$295K — and Y2 compounds against a fully-onboarded base.

The other lever is **avg cabinets/shop/month**. A 20% lift here — entirely plausible once shops realize KitchenForge speeds quoting — drops directly into pull-through revenue.

This is why the rebate is structured per-cabinet rather than per-subscription: it aligns Southbrook's incentive with Marathon's actual revenue driver, which is hardware shipped, not seats sold.
