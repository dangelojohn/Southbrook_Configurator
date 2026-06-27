---
course: 22
chapter: 22.7
title: Quality Module — Customisation Patterns
duration: 7
audience: Developer building a Southbrook-specific extension
prereqs: Lessons 22.1-22.6
custom_modules: southbrook_quality
---

# Quality Module — Customisation Patterns

## Who this lesson is for

You need to customise the Quality module for a Southbrook-specific
flow — a new state, a new field, a new dimension type, a new
escalation rule. This lesson covers the safe patterns + the
anti-patterns.

## Recommended customisation paths

### 1. Extend in a NEW addon

Create `southbrook_quality_local` (or whatever name):

```python
# addons/southbrook_quality_local/models/ncr.py
class SouthbrookNcr(models.Model):
    _inherit = "southbrook.ncr"
    
    your_new_field = fields.Char()
    
    def your_new_action(self):
        # custom logic
        pass
```

Why: keeps `southbrook_quality` upgradeable. When the upstream
ships a new version, your customisations live in their own
module + don't conflict.

### 2. Add a field via Studio (for non-critical fields)

For simple Char fields shown on the form but not used in business
logic, Studio is fine. Studio fields are stored in DB but not in
source.

CAVEAT: Studio fields aren't versioned in git. If you uninstall
your tenant, they're lost. Don't use Studio for fields that need
to survive a re-install.

### 3. Override in your own addon (heavy customisation)

```python
class SouthbrookNcr(models.Model):
    _inherit = "southbrook.ncr"
    
    def action_quarantine(self):
        result = super().action_quarantine()
        # your additional logic
        return result
```

Use `super()` to preserve upstream behavior. Don't replace; extend.

## Anti-patterns

### Don't patch upstream files

Editing `addons/southbrook_quality/models/ncr.py` directly:
- Loses changes on `git pull` of the platform
- Confuses other developers
- Makes upgrades break

### Don't bypass the state machine

```python
ncr.state = "scrap"  # BAD — side effects skipped
ncr.action_scrap()   # GOOD — side effects fire
```

### Don't add stored computed fields for transient data

Stored computed fields force recompute on every change. Use a
non-stored compute + cache externally if needed.

## A worked example: add a "defect_owner_id" tracking field

Goal: track who's responsible for fixing the defect (sometimes
different from `assigned_user_id`).

### Step 1: New addon

```
addons/southbrook_quality_extensions/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── __init__.py
│   └── ncr.py
├── views/
│   └── ncr_form_inherit.xml
└── security/
    └── ir.model.access.csv
```

### Step 2: Model extension

```python
# models/ncr.py
class SouthbrookNcr(models.Model):
    _inherit = "southbrook.ncr"
    
    defect_owner_id = fields.Many2one(
        "res.users",
        string="Defect Owner",
        help="Who's responsible for fixing this defect.",
    )
```

### Step 3: Form view extension

```xml
<record id="view_ncr_form_inherit_ext" model="ir.ui.view">
    <field name="name">southbrook.ncr.form.inherit.ext</field>
    <field name="model">southbrook.ncr</field>
    <field name="inherit_id" ref="southbrook_quality.view_southbrook_ncr_form"/>
    <field name="arch" type="xml">
        <xpath expr="//field[@name='reported_by']" position="after">
            <field name="defect_owner_id"/>
        </xpath>
    </field>
</record>
```

### Step 4: Install + verify

```bash
./scripts/deploy_to_qnap.sh southbrook_quality_extensions
```

Verify in UI: open an NCR → form shows the new field.

## Adding a custom state

Goal: add a `pending_supplier_response` state for when supplier
needs to investigate.

### Step 1: Extend the selection

```python
class SouthbrookNcr(models.Model):
    _inherit = "southbrook.ncr"
    
    state = fields.Selection(
        selection_add=[("pending_supplier_response", "Pending Supplier")],
        ondelete={"pending_supplier_response": "set default"},
    )
```

### Step 2: Add the transition method

```python
def action_pending_supplier_response(self):
    self.ensure_one()
    self.state = "pending_supplier_response"
    self.message_post(body=_("Awaiting supplier investigation"))
    # Notify supplier
    ...
```

### Step 3: Form button

```xml
<button name="action_pending_supplier_response"
        string="Pending Supplier"
        invisible="state != 'quarantine'"
        type="object"/>
```

### Step 4: Statusbar update

```xml
<field name="state" widget="statusbar"
       statusbar_visible="draft,quarantine,pending_supplier_response,rework,scrap,accept"/>
```

## Common mistakes + how to recover

- **"Custom field doesn't appear on the form"** — view inherit XPath
  wrong. Test with the view in *Settings → Technical → Views* +
  *Try the Inheritance*.
- **"State extension fires v19 validation"** — `ondelete` clause
  was missing. v19 requires explicit handling.
- **"Override broke upstream behavior"** — forgot `super()`. Always
  call super in overrides.

## Quiz

**Q1.** You want to add a Boolean to NCR. Pure Studio OK?

> Studio fields aren't in source. If the field has business value
> (used in reports, rules, exports), put it in a custom module.
> Studio is for cosmetic fields.

**Q2.** You override `action_scrap()` to skip the
`procurement.group.run()` call. Why is this risky?

> The native scrap → re-MO flow depends on it. Skipping breaks
> fulfilment. Either don't override, or call super first then skip
> the specific bit you want to bypass via a flag on the NCR.

**Q3.** New `defect_type` value needs to be added. Source-control
approach?

> Custom module with `selection_add=[...]` on the field. v19
> requires `ondelete` clause. Don't edit upstream selection list.

**Q4.** Two custom addons both extend `southbrook.ncr.state` with
new values. Conflict?

> No — both load; the resulting state field has both extensions.
> But ordering matters for `ondelete` defaults; check load order
> in module dependencies.

**Q5.** Your override breaks `mail.thread` audit trail. Why?

> You may have replaced `write()` or `create()` without calling
> super. Always `super().write(...)` for the audit to log.
