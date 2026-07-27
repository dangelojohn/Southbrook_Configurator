# Fabio Agent Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a real Odoo contact identity named Fabio and show it as the avatar-capable agent/source on Fabio recommendations.

**Architecture:** Add a stable `res.partner` data record and a `Many2one` field on `southbrook.hermes.recommendation`. The field defaults to the Fabio contact and is displayed in list/form views with avatar rendering, while technical HERMES names stay stable.

**Tech Stack:** Odoo 19 addon data XML, Odoo model fields/defaults, HTTP controller tests, TransactionCase tests.

---

### Task 1: Fabio Identity Tests

**Files:**
- Create: `addons/southbrook_hermes/tests/test_fabio_identity.py`
- Modify: `addons/southbrook_hermes/tests/__init__.py`

- [ ] **Step 1: Write failing tests**

The tests assert:

- `southbrook_hermes.partner_fabio_agent` exists and is a contact named `Fabio`.
- New recommendations default `agent_partner_id` to that contact.
- API-created recommendations default `agent_partner_id` to that contact.
- The recommendation list/form views include `agent_partner_id` with avatar-capable widgets.

- [ ] **Step 2: Run focused test**

```bash
docker exec sami-odoo odoo -d southbrook -u southbrook_hermes --test-enable --test-tags=fabio_identity --db_host=db --db_user=odoo --db_password='change-me-strong-password' --stop-after-init --no-http --http-port=8899 --gevent-port=8902 --workers=0 --max-cron-threads=0
```

Expected: FAIL because the partner record and field do not exist yet.

### Task 2: Fabio Contact And Field

**Files:**
- Create: `addons/southbrook_hermes/data/fabio_partner.xml`
- Modify: `addons/southbrook_hermes/__manifest__.py`
- Modify: `addons/southbrook_hermes/models/hermes_recommendation.py`

- [ ] **Step 1: Add partner data**

Create a no-login contact:

```xml
<record id="partner_fabio_agent" model="res.partner">
    <field name="name">Fabio</field>
    <field name="email">fabio.agent@southbrookcabinetry.space</field>
    <field name="company_type">person</field>
    <field name="comment">Fabio agent identity for human-approved recommendations.</field>
</record>
```

- [ ] **Step 2: Add recommendation field**

Add:

```python
agent_partner_id = fields.Many2one(
    "res.partner",
    default=lambda self: self.env.ref(
        "southbrook_hermes.partner_fabio_agent",
        raise_if_not_found=False,
    ),
    readonly=True,
    copy=False,
)
```

### Task 3: API And Views

**Files:**
- Modify: `addons/southbrook_hermes/controllers/main.py`
- Modify: `addons/southbrook_hermes/views/hermes_recommendation_views.xml`

- [ ] **Step 1: Preserve API default**

No caller-provided agent field is required in v1. The controller should rely on
the model default when creating records.

- [ ] **Step 2: Show Fabio identity in views**

Add `agent_partner_id` to list and form views. Use `many2one_avatar` where
supported and keep `reviewer_id` as the human reviewer avatar.

### Task 4: Verify

- [ ] **Step 1: Run focused Fabio identity tests**

Expected: 0 failures.

- [ ] **Step 2: Run HERMES/Fabio module tests**

```bash
docker exec sami-odoo odoo -d southbrook -u southbrook_hermes --test-enable --test-tags=hermes --db_host=db --db_user=odoo --db_password='change-me-strong-password' --stop-after-init --no-http --http-port=8899 --gevent-port=8902 --workers=0 --max-cron-threads=0
```

Expected: 0 failures.

- [ ] **Step 3: Run full quick suite**

```bash
make test-quick DB=southbrook
```

Expected: 0 failures.
