# Fabio Odoo Labels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the user-facing Odoo HERMES labels to Fabio while keeping technical module, model, and API names stable.

**Architecture:** This is a presentation-only rename. XML-visible Odoo strings and tests change; Python class names, model names, route paths, environment variables, and sidecar package names remain unchanged to avoid breaking integrations.

**Tech Stack:** Odoo 19 addon XML, Odoo TransactionCase tests, existing `southbrook_hermes` module.

---

### Task 1: Add UI Label Regression Test

**Files:**
- Create: `addons/southbrook_hermes/tests/test_fabio_labels.py`
- Modify: `addons/southbrook_hermes/tests/__init__.py`

- [ ] **Step 1: Write the failing test**

Add assertions that the Odoo-facing menu, action, group, and confirmation/help strings use Fabio:

```python
menu = self.env.ref("southbrook_hermes.menu_hermes_root")
self.assertEqual(menu.name, "Fabio")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
docker exec sami-odoo odoo -d southbrook -u southbrook_hermes --test-enable --test-tags=fabio_labels --db_host=db --db_user=odoo --db_password='change-me-strong-password' --stop-after-init --no-http --http-port=8899 --gevent-port=8902 --workers=0 --max-cron-threads=0
```

Expected: FAIL because the current XML still says HERMES.

### Task 2: Rename Odoo-Facing XML Strings

**Files:**
- Modify: `addons/southbrook_hermes/__manifest__.py`
- Modify: `addons/southbrook_hermes/security/hermes_security.xml`
- Modify: `addons/southbrook_hermes/views/hermes_menus.xml`
- Modify: `addons/southbrook_hermes/views/hermes_recommendation_views.xml`

- [ ] **Step 1: Update visible strings**

Change only display text:

- `Southbrook HERMES` -> `Southbrook Fabio`
- `HERMES Reviewer` -> `Fabio Reviewer`
- `HERMES` menu -> `Fabio`
- `HERMES Recommendations` -> `Fabio Recommendations`
- Confirmation/help/chatter-facing XML text -> Fabio wording

- [ ] **Step 2: Keep technical names stable**

Do not rename:

- `southbrook_hermes`
- `southbrook.hermes.recommendation`
- `/hermes/api/v1/recommendations`
- Python class names
- sidecar package names

### Task 3: Verify

**Files:**
- Test: `addons/southbrook_hermes/tests/test_fabio_labels.py`

- [ ] **Step 1: Run focused Fabio test**

Run the same `fabio_labels` command and expect 0 failures.

- [ ] **Step 2: Run sidecar tests**

```bash
python3 -m unittest discover -s services/hermes_agent/tests
```

Expected: 3 tests pass.

- [ ] **Step 3: Run HERMES/Fabio Odoo tests**

```bash
docker exec sami-odoo odoo -d southbrook -u southbrook_hermes --test-enable --test-tags=hermes --db_host=db --db_user=odoo --db_password='change-me-strong-password' --stop-after-init --no-http --http-port=8899 --gevent-port=8902 --workers=0 --max-cron-threads=0
```

Expected: 0 failures.
