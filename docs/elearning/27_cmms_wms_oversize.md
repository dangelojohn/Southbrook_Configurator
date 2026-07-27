---
course: 27
chapter: 27.5
title: CMMS + WMS Module — Oversize Permit and Landed Cost Templates
duration: 7
audience: Developer working on WMS-side features
prereqs: Lesson 27.1, native Odoo stock + landed costs
custom_modules: southbrook_cmms_wms
---

# CMMS + WMS Module — Oversize Permit and Landed Cost Templates

## The two WMS features

1. **Oversize permit** — tracks the permits required for shipping
   oversize cabinets (over 12' or 8' wide depending on jurisdiction)
2. **Landed cost templates** — recurring freight/duty cost rules
   that auto-apply to receipts

## Oversize permit model

```python
class SouthbrookWmsOversizePermit(models.Model):
    _name = "southbrook.wms.oversize_permit"
    _description = "Oversize Vehicle Permit"
```

Fields:

```python
name             = fields.Char()
jurisdiction_id  = fields.Many2one("res.country.state")
permit_number    = fields.Char()
issue_date       = fields.Date()
expiry_date      = fields.Date()
max_length_in    = fields.Float()
max_width_in     = fields.Float()
max_height_in    = fields.Float()
max_weight_lb    = fields.Float()

linked_picking_ids = fields.Many2many("stock.picking")

state = fields.Selection([
    ("draft", "Draft"),
    ("active", "Active"),
    ("used", "Used"),
    ("expired", "Expired"),
])
```

## Linking to shipments

When a picking has oversize content:

```python
class StockPicking(models.Model):
    _inherit = "stock.picking"
    
    requires_oversize_permit = fields.Boolean(
        compute="_compute_oversize_required", store=True)
    oversize_permit_id = fields.Many2one(
        "southbrook.wms.oversize_permit")


@api.depends("move_ids.product_id.product_length",
             "move_ids.product_id.product_width",
             "move_ids.product_id.product_height")
def _compute_oversize_required(self):
    for p in self:
        # If any product exceeds standard dimensions
        max_dim = max(
            move.product_id.product_length or 0
            for move in p.move_ids
        )
        p.requires_oversize_permit = max_dim > 96  # 8'
```

## Landed cost templates

For recurring freight/duty patterns:

```python
class SouthbrookWmsLandedCostTemplate(models.Model):
    _name = "southbrook.wms.landed_cost_template"
```

Fields:

```python
name           = fields.Char()
vendor_id      = fields.Many2one("res.partner")
country_id     = fields.Many2one("res.country")
cost_type      = fields.Selection([
    ("freight", "Freight"),
    ("duty", "Customs Duty"),
    ("brokerage", "Brokerage Fee"),
])
cost_formula   = fields.Char()
# Examples: "100", "weight_lb * 0.5", "value * 0.05"
account_id     = fields.Many2one("account.account")
```

When a vendor bill matches the template:

```python
def auto_apply_landed_cost(self, vendor_bill):
    """Find matching templates + create landed cost adjustments."""
    templates = self.search([
        ("vendor_id", "=", vendor_bill.partner_id.id),
    ])
    for template in templates:
        amount = self._evaluate_formula(template, vendor_bill)
        if amount > 0:
            self.env["stock.landed.cost"].create({
                "picking_ids": [(6, 0, vendor_bill.picking_ids.ids)],
                "cost_lines": [(0, 0, {
                    "product_id": template.product_id.id,
                    "price_unit": amount,
                    "account_id": template.account_id.id,
                })],
            })
```

## Common mistakes + how to recover

- **"Shipment requires permit but field is False"** — product
  dimensions missing on master. Set length/width/height on
  product.product.
- **"Permit expired, used field still active"** — check the
  daily expiry cron. Manual: bulk-update state.
- **"Landed cost not applied"** — template formula evaluation
  failed. Check logs.

## Quiz

**Q1.** Permit applies to one shipment. Re-use possible?

> m2m on `linked_picking_ids`. One permit can cover multiple
> shipments within its validity window.

**Q2.** Picking has a product 100" long. `requires_oversize_permit`?

> True (100 > 96 = 8 feet threshold).

**Q3.** Landed cost template uses formula `weight_lb * 0.5`.
What weight?

> Total weight of the bill's products. Computed from
> `product.weight × qty`.

**Q4.** Two templates match same vendor bill. Effect?

> Both apply. Stack additively. Verify this is intended (could be
> double-counting).

**Q5.** Add a new permit jurisdiction (e.g. Manitoba). Effort?

> No code change — just create a new permit record with
> `jurisdiction_id = Manitoba`. Permit thresholds may differ;
> adjust max_* values per jurisdiction.
