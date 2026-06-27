---
course: 25
chapter: 25.5
title: Integrations Module — Label Printer Integration
duration: 6
audience: Developer working on shipping label or shop-floor tag generation
prereqs: Lesson 25.1
custom_modules: southbrook_integrations
---

# Integrations Module — Label Printer Integration

## What this integrates

Physical label printers — Zebra ZPL II + DataMax/Honeywell — for:
- Shipping labels (carton, pallet)
- Shop-floor traveller tags (cabinet ID, MO ID, cut spec)
- Inventory bin labels

## Models

```python
class SouthbrookIntegrationsLabelPrinter(models.Model):
    _name = "southbrook.integrations.label_printer"
    _description = "Label Printer Configuration"
```

Fields:

```python
name             = fields.Char(required=True)
ip_address       = fields.Char(required=True)
port             = fields.Integer(default=9100)
language         = fields.Selection([
    ("zpl", "Zebra ZPL"),
    ("dpl", "DataMax DPL"),
], required=True)
dpi              = fields.Selection([
    ("203", "203 dpi"),
    ("300", "300 dpi"),
])
active           = fields.Boolean(default=True)
last_print_at    = fields.Datetime()
last_heartbeat   = fields.Datetime()
status           = fields.Selection([
    ("online", "Online"),
    ("offline", "Offline"),
    ("error", "Error"),
])
```

```python
class SouthbrookIntegrationsLabelLog(models.Model):
    _name = "southbrook.integrations.label_log"
    _order = "printed_at desc"
```

Fields:

```python
printer_id     = fields.Many2one("...label_printer", required=True)
label_data     = fields.Text()  # raw ZPL/DPL
printed_at     = fields.Datetime(default=fields.Datetime.now)
printed_by     = fields.Many2one("res.users")
related_model  = fields.Char()  # e.g. "stock.picking"
related_id     = fields.Integer()
status         = fields.Selection([
    ("queued", "Queued"),
    ("sent", "Sent"),
    ("error", "Error"),
])
```

## Print pipeline

```python
def print_label(self, label_data, related_record=None):
    """Send raw ZPL/DPL to the printer."""
    self.ensure_one()
    
    log = self.env["southbrook.integrations.label_log"].create({
        "printer_id": self.id,
        "label_data": label_data,
        "related_model": related_record._name if related_record else False,
        "related_id": related_record.id if related_record else False,
        "status": "queued",
    })
    
    try:
        socket = SocketIO((self.ip_address, self.port))
        socket.send(label_data.encode("utf-8"))
        socket.close()
        log.status = "sent"
        self.last_print_at = fields.Datetime.now()
    except Exception as e:
        log.status = "error"
        log.message_post(body=str(e))
        raise UserError(_("Print failed: %s") % e)
    
    return log
```

## ZPL template

A shop-floor traveller tag in ZPL:

```python
def render_traveller_zpl(self, mo):
    return f"""
^XA
^FO50,50^A0N,50,50^FD{mo.name}^FS
^FO50,150^A0N,30,30^FDCabinet: {mo.product_id.display_name}^FS
^FO50,200^A0N,30,30^FDQty: {int(mo.product_qty)}^FS
^FO50,250^BCN,100,Y,N,N^FD{mo.name}^FS
^XZ
"""
```

Renders barcode + product info on a 4×6 label.

## Heartbeat

```python
@api.model
def _cron_printer_heartbeat(self):
    for printer in self.search([("active", "=", True)]):
        if self._ping(printer.ip_address, printer.port):
            printer.status = "online"
        else:
            printer.status = "offline"
        printer.last_heartbeat = fields.Datetime.now()
```

Offline printers surface to MI engine as recommendation.

## Common mistakes + how to recover

- **"Print works locally but not from Odoo"** — Odoo container
  network can't reach printer's IP. Check Docker network +
  printer's network segment.
- **"ZPL renders wrong dpi"** — printer's actual dpi differs from
  `dpi` field. Adjust the ZPL coordinates or update the field.
- **"Logs grow unboundedly"** — `cron_label_log_cleanup`
  archives > 90 days. If disabled, runs OOM eventually.

## Quiz

**Q1.** Two printer languages supported?

> ZPL (Zebra) and DPL (DataMax/Honeywell).

**Q2.** ZPL templates produce binary or text?

> Plain text (ZPL is ASCII commands). Sent as bytes over TCP.

**Q3.** Printer offline — what happens?

> Heartbeat marks status `offline`. Print attempt raises
> UserError. MI engine may emit recommendation.

**Q4.** Add a new printer language (e.g. EPL Eltron). Path?

> Add to language Selection, write a render_method for that
> language. Wire into the dispatch.

**Q5.** Label_log relation field empty after print. Effect?

> Log still saves but can't be traced back to source record.
> Always pass `related_record` to `print_label()`.
