---
course: 25
chapter: 25.3
title: Integrations Module — 3PL ASN (Inbound and Outbound)
duration: 8
audience: Developer working on 3PL Advance Shipment Notice flows
prereqs: Lesson 25.1, native Odoo Inventory + Purchase familiarity
custom_modules: southbrook_integrations
---

# Integrations Module — 3PL ASN (Inbound and Outbound)

## What ASN means

Advance Shipment Notice — the digital pre-arrival message a 3PL
sends about incoming inventory, OR a shipment dispatching out.
Driven by EDI in big retail; HTTP/JSON for newer 3PLs.

## The two flows

### Inbound ASN (3PL → Southbrook)

3PL receiver / handler sends notification "we received X SKUs;
they'll arrive at your dock at Y date." Southbrook receives,
creates stock.picking, plans put-away.

### Outbound ASN (Southbrook → 3PL)

Southbrook ships finished goods to 3PL warehouse. Notifies them
"X SKUs leaving by Y date; expected arrival Z." 3PL prepares
receiving.

## Models

```python
class SouthbrookIntegrationsAsnInbound(models.Model):
    _name = "southbrook.integrations.asn_inbound"
    _description = "Inbound ASN from 3PL"
    _inherit = ["mail.thread"]
```

```python
class SouthbrookIntegrationsAsnOutbound(models.Model):
    _name = "southbrook.integrations.asn_outbound"
    _description = "Outbound ASN to 3PL"
    _inherit = ["mail.thread"]
```

Both share fields:

```python
asn_number       = fields.Char(required=True, index=True)
partner_id       = fields.Many2one("res.partner")  # 3PL
expected_date    = fields.Datetime()
actual_date      = fields.Datetime()
state            = fields.Selection([
    ("draft", "Draft"),
    ("pending", "Pending"),
    ("received", "Received"),  # or "shipped" for outbound
    ("error", "Error"),
])
line_ids         = fields.One2many("...asn_line", "asn_id")
linked_picking_id = fields.Many2one("stock.picking")
```

## Inbound webhook receiver

```python
class SouthbrookIntegrationsAsnApi(http.Controller):
    
    @http.route("/asn/inbound", type="json", auth="api_key",
                methods=["POST"], csrf=False)
    def receive_inbound_asn(self, **payload):
        """Receive ASN from 3PL system."""
        # Validate API key (via auth='api_key' decorator)
        asn = request.env["southbrook.integrations.asn_inbound"]\
            .sudo().create({
                "asn_number": payload["asn_number"],
                "partner_id": self._resolve_partner(payload["sender_id"]),
                "expected_date": payload["expected_date"],
                "state": "pending",
            })
        
        # Create lines
        for line in payload.get("lines", []):
            asn.env["southbrook.integrations.asn_inbound.line"].create({
                "asn_id": asn.id,
                "product_id": self._resolve_product(line["sku"]),
                "qty_expected": line["qty"],
            })
        
        return {"status": "received", "asn_id": asn.id}
```

## Outbound ASN send

```python
def action_send_outbound_asn(self):
    self.ensure_one()
    payload = {
        "asn_number": self.asn_number,
        "sender_id": self.env.company.partner_id.ref,
        "expected_date": self.expected_date.isoformat(),
        "lines": [
            {"sku": l.product_id.default_code, "qty": l.qty}
            for l in self.line_ids
        ],
    }
    response = requests.post(
        self.partner_id.asn_endpoint,
        json=payload,
        headers={"Authorization": f"Bearer {self.partner_id.asn_api_key}"},
    )
    if response.status_code == 200:
        self.state = "shipped"
    else:
        self.state = "error"
        self.message_post(body=f"3PL rejected: {response.text}")
```

## Stock picking link

When inbound ASN reaches state `received`:

```python
def action_confirm_received(self):
    self.ensure_one()
    picking = self.env["stock.picking"].create({
        "picking_type_id": self.env.ref(
            "stock.picking_type_in").id,
        "partner_id": self.partner_id.id,
        "origin": f"ASN/{self.asn_number}",
    })
    for line in self.line_ids:
        self.env["stock.move"].create({
            "picking_id": picking.id,
            "product_id": line.product_id.id,
            "product_uom_qty": line.qty_actual,
            # ... 
        })
    self.linked_picking_id = picking.id
    self.state = "received"
```

## EDI gateway (deferred)

The webhook above handles JSON. EDI (EDIFACT, X12) needs a
gateway service that translates EDI ↔ JSON. Listed as v1.x
candidate; current 3PLs all support JSON.

## Common mistakes + how to recover

- **"Webhook fires but no ASN created"** — auth failed or
  payload validation rejected. Check `mail_log` for the request +
  controller error.
- **"Stock picking didn't link"** — `action_confirm_received` not
  called. Manual button OR auto-trigger via state machine.
- **"ASN line product unrecognized"** — SKU mapping table empty
  for that 3PL. Maintain in `res.partner.sku_mapping_ids` m2m
  field.

## Quiz

**Q1.** Inbound vs outbound — direction of stock movement?

> Inbound = 3PL → Southbrook. Outbound = Southbrook → 3PL.

**Q2.** What auth method on the webhook?

> `auth='api_key'`. Per-partner API key configured on `res.partner`.

**Q3.** Receiving ASN — what happens automatically?

> ASN record created. Stock picking IS NOT auto-created until
> `action_confirm_received` is called. Allows admin review before
> committing the receipt.

**Q4.** EDI support — present?

> Not at v1. JSON only. v1.x candidate for EDI gateway.

**Q5.** Outbound ASN endpoint config — where?

> `res.partner.asn_endpoint` field. Per-3PL configuration.
