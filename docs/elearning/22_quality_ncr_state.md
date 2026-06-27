---
course: 22
chapter: 22.2
title: Quality Module — NCR State Machine Internals
duration: 10
audience: Developer extending or debugging the NCR model
prereqs: Lesson 22.1
custom_modules: southbrook_quality
---

# Quality Module — NCR State Machine Internals

## Who this lesson is for

You're working in `addons/southbrook_quality/models/ncr.py`. This
lesson walks the state machine, the side-effects of each
transition, and the patterns for safe extension.

## The model

```python
class SouthbrookNcr(models.Model):
    _name = "southbrook.ncr"
    _description = "Non-Conformance Record"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"
```

Key fields:

```python
name           = fields.Char(default=lambda s: s._make_seq())
production_id  = fields.Many2one("mrp.production", required=True)
product_id     = fields.Many2one("product.product", required=True)
workorder_id   = fields.Many2one("mrp.workorder")
defect_type    = fields.Selection([...], required=True)
severity       = fields.Selection([
    ("minor", "Minor"),
    ("major", "Major"),
    ("critical", "Critical"),
])
state          = fields.Selection([
    ("draft", "Draft"),
    ("quarantine", "Quarantine"),
    ("rework", "Rework"),
    ("scrap", "Scrap"),
    ("accept", "Accept"),
], default="draft")
description    = fields.Text(required_for=["major", "critical"])
```

## State transitions

```
draft ──[Quarantine]──> quarantine ──[Rework]──> rework
                            │       └──[Scrap]──> scrap
                            │       └──[Accept]──> accept
                            │
                            └── auto-close on MO done
```

### Quarantine

`action_quarantine()`:

1. State → `quarantine`
2. For each downstream `mrp.workorder` not yet `done`:
   - Sets `block_reason = f"NCR/{self.id}"`
   - The MES kanban renders these as red-bordered
3. Posts `mail.activity` to the quality manager group
4. Posts to MO chatter

### Rework

`action_rework()`:

1. State → `rework`
2. Required: `rework_workcenter_id`
3. Creates a `mrp.workorder.duration` adjustment for the rework cost
4. Unblocks downstream WOs (clears `block_reason` from each)
5. Routes the cabinet back to `rework_workcenter_id` first
6. NCR stays open; closes when rework signs off

### Scrap

`action_scrap()`:

1. State → `scrap`
2. Required: `scrap_quantity` (default 1)
3. Creates `stock.scrap` for the product + qty
4. Calls `procurement.group.run()` on the originating SO line to
   trigger re-MO
5. Logs to scrap GL account via native stock valuation
6. NCR auto-closes after journal posts

### Accept

`action_accept()`:

1. State → `accept`
2. Required: `accept_reason` (text)
3. Requires `group_southbrook_quality_manager`
4. Unblocks all downstream WOs
5. NCR auto-closes

## Side effects per transition (the audit table)

| Transition | DB writes | Workorder effect | Chatter |
|---|---|---|---|
| Quarantine | `state`, audit log | `block_reason` set | activity assigned |
| Rework | `state`, `rework_workcenter_id` | `block_reason` cleared | rework start logged |
| Scrap | `state`, `scrap_quantity` | unaffected (already moved on) | scrap link posted |
| Accept | `state`, `accept_reason` | `block_reason` cleared | accept reason logged |

## Extension patterns

### Adding a new state

If you need a `repair` state (e.g. cabinet needs hardware
replacement, not rework):

```python
state = fields.Selection(selection_add=[
    ("repair", "Repair"),
])
```

Then add a transition method + a button in the form view.

### Customising the block-affected logic

`_block_downstream()` is the helper:

```python
def _block_downstream(self):
    self.ensure_one()
    affected = self.production_id.workorder_ids.filtered(
        lambda wo: wo.state in ("ready", "progress"))
    affected.write({"block_reason": f"NCR/{self.id}"})
```

Override this method to add custom blocking logic (e.g. cabinet
family-specific).

### Customising the rework target routing

`_rework_routing()` is the helper that decides where the cabinet
goes:

```python
def _rework_routing(self):
    return self.rework_workcenter_id
```

Override if you need conditional routing (e.g. based on severity).

## Common mistakes + how to recover

- **"State transition allowed but downstream WOs didn't unblock"** —
  `_block_downstream()` was overridden but `_unblock_downstream()`
  wasn't. Make sure both methods exist + handle the same cases.
- **"Scrap state but no re-MO appeared"** — the SO link missing.
  Trace: NCR → production_id → sale_order_id. If missing, the SO
  link wasn't established at MO confirm time.
- **"Accept state set without the reason check"** — `_check_accept()`
  was bypassed (calling state= directly). Don't bypass; use
  `action_accept()`.

## Quiz

**Q1.** You call `record.state = 'rework'` directly. Side effects?

> None of the side effects fire. The `action_rework()` method does
> the side effects; setting state directly bypasses them. Always
> use the action methods.

**Q2.** NCR moves to `scrap`. Cabinet was already in MO progress.
The `stock.scrap` records what stock?

> The `product_id` × `scrap_quantity` from the finished-goods (or
> WIP, depending on workorder state). Native `stock.scrap` handles
> location resolution.

**Q3.** Customise: add a 24h auto-escalate on critical NCRs not
yet quarantined. Approach?

> Add a cron + scheduled action filtering critical drafts older
> than 24h, transitioning to `quarantine` + flagging to a
> manager activity. Don't change the state machine; add a
> background reconciliation.

**Q4.** State → `rework`. Operator marks workcenter complete.
What unblocks the rework state?

> The `action_confirm_rework_done()` method on the NCR (called
> from the form button after rework completes). Sets state →
> `done`. Without this call, the NCR stays open in `rework`.

**Q5.** Where does NCR integrate with the MI engine?

> `mi_engine_ext.py` subscribes to NCR creates with
> `severity = 'critical'` and posts a recommendation to the Hermes
> queue for the Plant GM persona.
