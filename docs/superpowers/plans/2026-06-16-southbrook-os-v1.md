# Southbrook OS v1.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `southbrook_os` Odoo 19 CE addon — the canonical, governed, version-controlled knowledge layer of the platform — with hand-curated canonical markdown, Odoo-generated dynamic sections, OSRO governance, dated publications, a public JSON endpoint, and a RAG-corpus export so Hermes (Plan B) can ground itself in it.

**Architecture:** A new Odoo addon under `addons/southbrook_os/` with three model classes (`southbrook.os.section`, `southbrook.os.publication`, `southbrook.os.revision`), four generators that mirror live Odoo state to markdown, a JSON endpoint (`/southbrook/os.json`), and a corpus exporter that produces the Hermes RAG bundle. Canonical content is seeded from `2026-06-16-southbrook-os-v1-canonical-seed.md` (sibling file). HTML and PDF viewers + the OSRO UI ship in v1.1 — v1.0 ships the model + the API surface.

**Tech Stack:** Odoo 19 CE (`models.Model`, `models.Constraint` for SQL, QWeb, controllers, `ir.cron`), Python 3.12, `markdown` library for body_html computation, YAML frontmatter parsing (`PyYAML`), TransactionCase/HttpCase tests.

**Reference:** `docs/superpowers/specs/2026-06-16-southbrook-os-and-hermes-platform-design.md` (the design spec). `2026-06-16-southbrook-os-v1-canonical-seed.md` (the markdown content for Task 5).

---

## Tasks

### Task 1: Scaffold the addon skeleton

**Files:**
- Create: `addons/southbrook_os/__manifest__.py`
- Create: `addons/southbrook_os/__init__.py`
- Create: `addons/southbrook_os/models/__init__.py`
- Create: `addons/southbrook_os/controllers/__init__.py`
- Create: `addons/southbrook_os/exports/__init__.py`
- Create: `addons/southbrook_os/security/ir.model.access.csv`
- Create: `addons/southbrook_os/canonical/.gitkeep`
- Create: `addons/southbrook_os/generated/.gitkeep`
- Create: `addons/southbrook_os/tests/__init__.py`
- Create: `addons/southbrook_os/README.md`

- [ ] **Step 1: Create the manifest.**

```python
# addons/southbrook_os/__manifest__.py
# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook OS",
    "summary": "Canonical, governed knowledge layer of the Southbrook platform.",
    "description": """
Southbrook OS
=============

The version-controlled description of how Southbrook works as a business.
Hand-curated canonical markdown + Odoo-generated dynamic sections, governed
through OS Revision Orders (OSROs) and published as dated snapshots.

Consumers: Hermes (RAG grounding), public viewer (v1.1), Overseer (v1.x).
""",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry / OdooIQ",
    "website": "https://southbrookcabinetry.space",
    "category": "Productivity",
    "depends": [
        "base",
        "mail",
        "product",
        "mrp",
        "southbrook_estimating",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/os_section_seed.xml",
        "data/ir_cron.xml",
    ],
    "external_dependencies": {
        "python": ["markdown", "yaml"],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
```

- [ ] **Step 2: Create empty `__init__.py` files.**

```python
# addons/southbrook_os/__init__.py
from . import models
from . import controllers
from . import exports
```

```python
# addons/southbrook_os/models/__init__.py
# (empty for now — populated as models land)
```

```python
# addons/southbrook_os/controllers/__init__.py
# (empty for now)
```

```python
# addons/southbrook_os/exports/__init__.py
# (empty for now)
```

```python
# addons/southbrook_os/tests/__init__.py
# (empty for now)
```

- [ ] **Step 3: Create ACL file (will populate as models land).**

```csv
# addons/southbrook_os/security/ir.model.access.csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
```

- [ ] **Step 4: Create README.**

```markdown
# Southbrook OS

The canonical, version-controlled, governed knowledge layer of the
Southbrook platform. See `docs/superpowers/specs/2026-06-16-southbrook-os-and-hermes-platform-design.md`
for the design and `docs/superpowers/plans/2026-06-16-southbrook-os-v1.md`
for the v1.0 build plan.

Hand-curated content lives under `canonical/`. Odoo-generated content lives
under `generated/`. Governance happens through `southbrook.os.revision`
records (OSROs); dated snapshots live in `southbrook.os.publication`.

Public read endpoint: `GET /southbrook/os.json`.
```

- [ ] **Step 5: Create `.gitkeep` files for empty content directories.**

```bash
touch addons/southbrook_os/canonical/.gitkeep
touch addons/southbrook_os/generated/.gitkeep
```

- [ ] **Step 6: Verify the addon is discoverable by Odoo.**

Run: `ls addons/southbrook_os/`

Expected: shows `__init__.py`, `__manifest__.py`, `models/`, `controllers/`, `exports/`, `security/`, `canonical/`, `generated/`, `tests/`, `README.md`.

- [ ] **Step 7: Commit.**

```bash
git add addons/southbrook_os/
git commit -m "feat(os): scaffold southbrook_os addon skeleton (v19.0.1.0.0)"
```

---

### Task 2: `southbrook.os.section` model + ACL

**Files:**
- Create: `addons/southbrook_os/models/os_section.py`
- Modify: `addons/southbrook_os/models/__init__.py`
- Modify: `addons/southbrook_os/security/ir.model.access.csv`
- Create: `addons/southbrook_os/tests/test_os_section.py`

- [ ] **Step 1: Write the failing test.**

```python
# addons/southbrook_os/tests/test_os_section.py
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "southbrook_os")
class TestOsSection(TransactionCase):
    def test_section_created_with_required_fields(self):
        section = self.env["southbrook.os.section"].create({
            "slug": "test_section",
            "name": "Test Section",
            "source": "canonical",
            "body": "# Test\n\nHello.",
        })
        self.assertEqual(section.version, 1)
        self.assertEqual(section.source, "canonical")
        self.assertIn("<h1>", section.body_html)
        self.assertIn("Hello", section.body_html)

    def test_slug_is_unique(self):
        self.env["southbrook.os.section"].create({
            "slug": "dup", "name": "First", "source": "canonical", "body": "a",
        })
        with self.assertRaises(Exception):
            self.env["southbrook.os.section"].create({
                "slug": "dup", "name": "Second", "source": "canonical", "body": "b",
            })

    def test_version_bump_method(self):
        section = self.env["southbrook.os.section"].create({
            "slug": "bumpable", "name": "X", "source": "canonical", "body": "v1",
        })
        section.bump_version(body="v2")
        self.assertEqual(section.version, 2)
        self.assertEqual(section.body, "v2")
        self.assertEqual(section.last_updated_by, self.env.user)
```

- [ ] **Step 2: Run the test to verify it fails.**

```bash
DEPLOY_VIA=tunnel QNAP_TUNNEL_HOST=admin@ssh.odooiq.com \
ssh -o ProxyCommand="cloudflared access ssh --hostname %h" admin@ssh.odooiq.com \
  '/share/CACHEDEV3_DATA/.qpkg/container-station/bin/system-docker exec southbrook-odoo \
  odoo --test-enable --test-tags=southbrook_os -i southbrook_os -d southbrook --stop-after-init --no-http'
```

Expected: FAIL — model `southbrook.os.section` does not exist.

- [ ] **Step 3: Implement the model.**

```python
# addons/southbrook_os/models/os_section.py
# SPDX-License-Identifier: LGPL-3.0-only
import markdown

from odoo import _, api, fields, models


class OsSection(models.Model):
    _name = "southbrook.os.section"
    _description = "Southbrook OS — Canonical or Generated Section"
    _order = "slug"

    slug = fields.Char(required=True, index=True)
    name = fields.Char(required=True, translate=True)
    source = fields.Selection(
        [("canonical", "Canonical (hand-curated)"),
         ("generated", "Generated (from Odoo)")],
        required=True,
    )
    body = fields.Text(required=True)
    body_html = fields.Html(compute="_compute_body_html", sanitize=False, store=True)
    version = fields.Integer(default=1, required=True)
    last_updated_at = fields.Datetime(default=fields.Datetime.now)
    last_updated_by = fields.Many2one("res.users", default=lambda self: self.env.user)
    audience_tags = fields.Char(help="Comma-separated audience hints from frontmatter.")

    _slug_uniq = models.Constraint("UNIQUE(slug)", "Section slug must be unique.")

    @api.depends("body")
    def _compute_body_html(self):
        for rec in self:
            rec.body_html = markdown.markdown(
                rec.body or "",
                extensions=["fenced_code", "tables", "toc"],
            )

    def bump_version(self, body=None):
        """Apply a new version of this section. Used by OSRO apply + generators."""
        self.ensure_one()
        vals = {
            "version": self.version + 1,
            "last_updated_at": fields.Datetime.now(),
            "last_updated_by": self.env.user.id,
        }
        if body is not None:
            vals["body"] = body
        self.write(vals)
```

- [ ] **Step 4: Register model in `__init__.py`.**

```python
# addons/southbrook_os/models/__init__.py
from . import os_section
```

- [ ] **Step 5: Add ACL entry.**

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_os_section_user,os section read all,model_southbrook_os_section,base.group_user,1,0,0,0
access_os_section_admin,os section admin,model_southbrook_os_section,base.group_system,1,1,1,1
```

- [ ] **Step 6: Re-run the test.**

Expected: PASS — 3 tests.

- [ ] **Step 7: Commit.**

```bash
git add addons/southbrook_os/
git commit -m "feat(os): southbrook.os.section model with version + html computation"
```

---

### Task 3: `southbrook.os.publication` model

**Files:**
- Create: `addons/southbrook_os/models/os_publication.py`
- Modify: `addons/southbrook_os/models/__init__.py`
- Modify: `addons/southbrook_os/security/ir.model.access.csv`
- Create: `addons/southbrook_os/tests/test_os_publication.py`

- [ ] **Step 1: Write the failing test.**

```python
# addons/southbrook_os/tests/test_os_publication.py
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "southbrook_os")
class TestOsPublication(TransactionCase):
    def setUp(self):
        super().setUp()
        Section = self.env["southbrook.os.section"]
        self.s1 = Section.create({
            "slug": "00_charter", "name": "Charter",
            "source": "canonical", "body": "v1 body",
        })
        self.s2 = Section.create({
            "slug": "02_catalog", "name": "Catalog",
            "source": "canonical", "body": "v1 body",
        })

    def test_publish_creates_snapshot_of_every_section(self):
        pub = self.env["southbrook.os.publication"].publish("2026-06")
        self.assertEqual(pub.calendar_key, "2026-06")
        self.assertTrue(pub.build_hash)
        self.assertEqual(len(pub.section_snapshot_ids), 2)
        for snap in pub.section_snapshot_ids:
            self.assertEqual(snap.section_version, 1)

    def test_publish_with_same_content_returns_existing_pub(self):
        first = self.env["southbrook.os.publication"].publish("2026-06")
        second = self.env["southbrook.os.publication"].publish("2026-06")
        self.assertEqual(first.id, second.id)

    def test_publish_after_section_change_makes_new_pub(self):
        self.env["southbrook.os.publication"].publish("2026-06")
        self.s1.bump_version(body="v2 body")
        new_pub = self.env["southbrook.os.publication"].publish("2026-06")
        # Same calendar_key but new build_hash
        self.assertEqual(new_pub.calendar_key, "2026-06")
        # Snapshot of s1 should be at version 2
        s1_snap = new_pub.section_snapshot_ids.filtered(
            lambda s: s.slug == "00_charter")
        self.assertEqual(s1_snap.section_version, 2)
```

- [ ] **Step 2: Run the test to verify it fails.**

Expected: FAIL — model does not exist.

- [ ] **Step 3: Implement the publication + snapshot models.**

```python
# addons/southbrook_os/models/os_publication.py
# SPDX-License-Identifier: LGPL-3.0-only
import hashlib

from odoo import api, fields, models


class OsPublication(models.Model):
    _name = "southbrook.os.publication"
    _description = "Southbrook OS — Dated Publication Snapshot"
    _order = "calendar_key desc, build_hash"

    calendar_key = fields.Char(required=True, index=True,
        help="Calendar tag like '2026-06'.")
    build_hash = fields.Char(required=True, index=True,
        help="SHA-256 of concatenated (slug, version) tuples — content fingerprint.")
    built_at = fields.Datetime(default=fields.Datetime.now)
    section_snapshot_ids = fields.One2many(
        "southbrook.os.publication.section", "publication_id")

    _key_hash_uniq = models.Constraint(
        "UNIQUE(calendar_key, build_hash)",
        "A publication with this (calendar_key, build_hash) already exists.",
    )

    @api.model
    def publish(self, calendar_key):
        """Build (or reuse) a publication for the current section state."""
        sections = self.env["southbrook.os.section"].search([], order="slug")
        fingerprint = "|".join(f"{s.slug}@{s.version}" for s in sections)
        build_hash = hashlib.sha256(fingerprint.encode()).hexdigest()[:16]
        existing = self.search([
            ("calendar_key", "=", calendar_key),
            ("build_hash", "=", build_hash),
        ], limit=1)
        if existing:
            return existing
        pub = self.create({"calendar_key": calendar_key, "build_hash": build_hash})
        SnapModel = self.env["southbrook.os.publication.section"]
        for s in sections:
            SnapModel.create({
                "publication_id": pub.id,
                "slug": s.slug,
                "name": s.name,
                "body": s.body,
                "section_version": s.version,
                "source": s.source,
            })
        return pub


class OsPublicationSection(models.Model):
    _name = "southbrook.os.publication.section"
    _description = "Southbrook OS — Frozen Section in a Publication"
    _order = "slug"

    publication_id = fields.Many2one(
        "southbrook.os.publication", required=True, ondelete="cascade")
    slug = fields.Char(required=True)
    name = fields.Char(required=True)
    body = fields.Text(required=True)
    section_version = fields.Integer(required=True)
    source = fields.Selection(
        [("canonical", "Canonical"), ("generated", "Generated")], required=True)
```

- [ ] **Step 4: Register model.**

```python
# addons/southbrook_os/models/__init__.py
from . import os_section
from . import os_publication
```

- [ ] **Step 5: Add ACL entries.**

```csv
access_os_publication_user,os publication read,model_southbrook_os_publication,base.group_user,1,0,0,0
access_os_publication_admin,os publication admin,model_southbrook_os_publication,base.group_system,1,1,1,1
access_os_publication_section_user,os pub section read,model_southbrook_os_publication_section,base.group_user,1,0,0,0
access_os_publication_section_admin,os pub section admin,model_southbrook_os_publication_section,base.group_system,1,1,1,1
```

- [ ] **Step 6: Re-run the test.**

Expected: PASS — 3 tests.

- [ ] **Step 7: Commit.**

```bash
git add addons/southbrook_os/
git commit -m "feat(os): southbrook.os.publication + frozen section snapshots"
```

---

### Task 4: `southbrook.os.revision` (OSRO) state machine

**Files:**
- Create: `addons/southbrook_os/models/os_revision_order.py`
- Modify: `addons/southbrook_os/models/__init__.py`
- Modify: `addons/southbrook_os/security/ir.model.access.csv`
- Create: `addons/southbrook_os/tests/test_os_revision.py`

- [ ] **Step 1: Write the failing test.**

```python
# addons/southbrook_os/tests/test_os_revision.py
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "southbrook_os")
class TestOsRevision(TransactionCase):
    def setUp(self):
        super().setUp()
        self.section = self.env["southbrook.os.section"].create({
            "slug": "04_lifecycle", "name": "Lifecycle",
            "source": "canonical", "body": "v1 body",
        })

    def test_full_state_machine_draft_to_applied(self):
        Rev = self.env["southbrook.os.revision"]
        rev = Rev.create({
            "target_slug": "04_lifecycle",
            "change_summary": "Add Tier 4 partner pricing note",
            "proposed_body": "v2 body",
        })
        self.assertEqual(rev.state, "draft")
        rev.action_submit_for_review()
        self.assertEqual(rev.state, "review")
        rev.action_approve()
        self.assertEqual(rev.state, "approved")
        rev.action_apply()
        self.assertEqual(rev.state, "applied")
        # The section now carries the new body at version 2
        self.section.invalidate_recordset()
        self.assertEqual(self.section.body, "v2 body")
        self.assertEqual(self.section.version, 2)

    def test_cannot_apply_unapproved_osro(self):
        rev = self.env["southbrook.os.revision"].create({
            "target_slug": "04_lifecycle",
            "change_summary": "X",
            "proposed_body": "X",
        })
        with self.assertRaises(UserError):
            rev.action_apply()

    def test_cannot_target_missing_slug(self):
        rev = self.env["southbrook.os.revision"].create({
            "target_slug": "no_such_slug",
            "change_summary": "X",
            "proposed_body": "X",
        })
        rev.action_submit_for_review()
        rev.action_approve()
        with self.assertRaises(UserError):
            rev.action_apply()

    def test_reject_from_review(self):
        rev = self.env["southbrook.os.revision"].create({
            "target_slug": "04_lifecycle",
            "change_summary": "Bad idea",
            "proposed_body": "X",
        })
        rev.action_submit_for_review()
        rev.action_reject()
        self.assertEqual(rev.state, "rejected")
```

- [ ] **Step 2: Run the test to verify it fails.**

Expected: FAIL — model does not exist.

- [ ] **Step 3: Implement the model.**

```python
# addons/southbrook_os/models/os_revision_order.py
# SPDX-License-Identifier: LGPL-3.0-only
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class OsRevision(models.Model):
    _name = "southbrook.os.revision"
    _description = "Southbrook OS — Revision Order (OSRO)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(default=lambda self: _("New"), tracking=True)
    target_slug = fields.Char(required=True, tracking=True)
    change_summary = fields.Char(required=True, tracking=True)
    proposed_body = fields.Text(required=True)
    state = fields.Selection(
        [("draft", "Draft"),
         ("review", "Under Review"),
         ("approved", "Approved"),
         ("applied", "Applied"),
         ("rejected", "Rejected")],
        default="draft", required=True, tracking=True,
    )
    reviewer_ids = fields.Many2many("res.users")
    applied_at = fields.Datetime(readonly=True)
    applied_by = fields.Many2one("res.users", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "southbrook.os.revision") or _("OSRO/draft")
        return super().create(vals_list)

    def action_submit_for_review(self):
        for rev in self:
            if rev.state != "draft":
                raise UserError(_("Only draft OSROs can be submitted for review."))
            rev.state = "review"

    def action_approve(self):
        for rev in self:
            if rev.state != "review":
                raise UserError(_("Only OSROs under review can be approved."))
            rev.state = "approved"

    def action_reject(self):
        for rev in self:
            if rev.state not in ("review", "draft"):
                raise UserError(_("Cannot reject from %s.") % rev.state)
            rev.state = "rejected"

    def action_apply(self):
        for rev in self:
            if rev.state != "approved":
                raise UserError(
                    _("Only approved OSROs can be applied. Current state: %s.")
                    % rev.state)
            section = self.env["southbrook.os.section"].search(
                [("slug", "=", rev.target_slug)], limit=1)
            if not section:
                raise UserError(
                    _("No OS section with slug '%s' exists to apply this OSRO against.")
                    % rev.target_slug)
            section.bump_version(body=rev.proposed_body)
            rev.write({
                "state": "applied",
                "applied_at": fields.Datetime.now(),
                "applied_by": self.env.user.id,
            })
```

- [ ] **Step 4: Register model + ir.sequence.**

```python
# addons/southbrook_os/models/__init__.py
from . import os_section
from . import os_publication
from . import os_revision_order
```

- [ ] **Step 5: Add ACL + sequence to seed XML (we'll create the seed file in Task 5; for now add the sequence inline).**

Append to `security/ir.model.access.csv`:

```csv
access_os_revision_user,os revision read,model_southbrook_os_revision,base.group_user,1,0,0,0
access_os_revision_admin,os revision admin,model_southbrook_os_revision,base.group_system,1,1,1,1
```

Create `addons/southbrook_os/data/ir_sequence.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
  <data noupdate="1">
    <record id="seq_os_revision" model="ir.sequence">
      <field name="name">Southbrook OS Revision Order</field>
      <field name="code">southbrook.os.revision</field>
      <field name="prefix">OSRO/%(year)s/</field>
      <field name="padding">4</field>
      <field name="number_next">1</field>
      <field name="number_increment">1</field>
    </record>
  </data>
</odoo>
```

Add `"data/ir_sequence.xml"` to the manifest's `data` list (before `os_section_seed.xml`).

- [ ] **Step 6: Re-run the test.**

Expected: PASS — 4 tests.

- [ ] **Step 7: Commit.**

```bash
git add addons/southbrook_os/
git commit -m "feat(os): southbrook.os.revision OSRO state machine + apply handler"
```

---

### Task 5: Seed canonical markdown + loader

**Files:**
- Create: `addons/southbrook_os/canonical/00_charter.md`
- Create: `addons/southbrook_os/canonical/01_company.md`
- Create: `addons/southbrook_os/canonical/02_catalog.md`
- Create: `addons/southbrook_os/canonical/03_attributes.md`
- Create: `addons/southbrook_os/canonical/04_lifecycle.md`
- Create: `addons/southbrook_os/canonical/05_production.md`
- Create: `addons/southbrook_os/canonical/06_plm.md`
- Create: `addons/southbrook_os/canonical/07_partner_faq.md`
- Create: `addons/southbrook_os/canonical/20_systems_topology.md`
- Create: `addons/southbrook_os/canonical/99_glossary.md`
- Create: `addons/southbrook_os/models/os_loader.py`
- Create: `addons/southbrook_os/data/os_section_seed.xml`
- Modify: `addons/southbrook_os/models/__init__.py`
- Create: `addons/southbrook_os/tests/test_loader.py`

- [ ] **Step 1: Copy the ten canonical files.**

Use the verbatim content from `docs/superpowers/plans/2026-06-16-southbrook-os-v1-canonical-seed.md`. There are ten markdown blocks in that file (one per filename). Copy each one as-is into `addons/southbrook_os/canonical/<filename>`. Do not edit; the OSRO process is how that content evolves.

- [ ] **Step 2: Write the failing test.**

```python
# addons/southbrook_os/tests/test_loader.py
import os

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "southbrook_os")
class TestOsLoader(TransactionCase):
    def test_canonical_files_loaded_as_sections(self):
        # After install (this is post_install), every canonical/*.md should
        # exist as a southbrook.os.section record with source=canonical.
        Section = self.env["southbrook.os.section"]
        for fname in os.listdir("/mnt/extra-addons/southbrook_os/canonical"):
            if not fname.endswith(".md"):
                continue
            slug = fname[:-3]  # strip .md
            section = Section.search([("slug", "=", slug)], limit=1)
            self.assertTrue(
                section, f"Expected southbrook.os.section with slug='{slug}'")
            self.assertEqual(section.source, "canonical")
            self.assertTrue(section.body, f"Section {slug} has empty body")

    def test_partner_faq_loaded_with_content(self):
        section = self.env["southbrook.os.section"].search(
            [("slug", "=", "07_partner_faq")], limit=1)
        self.assertTrue(section)
        self.assertIn("Where is my kitchen?", section.body)
```

- [ ] **Step 3: Run the test to verify it fails.**

Expected: FAIL — sections don't exist.

- [ ] **Step 4: Implement the loader.**

```python
# addons/southbrook_os/models/os_loader.py
# SPDX-License-Identifier: LGPL-3.0-only
import os
import re

import yaml

from odoo import api, models

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


class OsLoader(models.AbstractModel):
    _name = "southbrook.os.loader"
    _description = "Loads canonical/*.md files into southbrook.os.section."

    @api.model
    def load_canonical_directory(self, directory_path):
        """Idempotently load every *.md in `directory_path` into a section."""
        Section = self.env["southbrook.os.section"]
        loaded = []
        for fname in sorted(os.listdir(directory_path)):
            if not fname.endswith(".md") or fname.startswith("."):
                continue
            slug = fname[:-3]
            path = os.path.join(directory_path, fname)
            with open(path, encoding="utf-8") as f:
                raw = f.read()
            meta, body = self._split_frontmatter(raw)
            vals = {
                "slug": slug,
                "name": meta.get("title", slug),
                "source": meta.get("source", "canonical"),
                "body": body,
                "audience_tags": ",".join(meta.get("audience") or []),
            }
            existing = Section.search([("slug", "=", slug)], limit=1)
            if existing:
                existing.write({"body": body, "name": vals["name"]})
                loaded.append(existing)
            else:
                loaded.append(Section.create(vals))
        return loaded

    def _split_frontmatter(self, raw):
        match = _FRONTMATTER_RE.match(raw)
        if not match:
            return {}, raw
        try:
            meta = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            meta = {}
        return meta, match.group(2)
```

- [ ] **Step 5: Register the loader.**

```python
# addons/southbrook_os/models/__init__.py
from . import os_section
from . import os_publication
from . import os_revision_order
from . import os_loader
```

- [ ] **Step 6: Wire it to fire on install + upgrade via post_init_hook.**

Add to `__manifest__.py`:

```python
"post_init_hook": "_post_init_load_canonical",
```

Create the hook in `addons/southbrook_os/__init__.py`:

```python
# addons/southbrook_os/__init__.py
import os

from . import models
from . import controllers
from . import exports


def _post_init_load_canonical(env):
    addon_dir = os.path.dirname(__file__)
    canonical_dir = os.path.join(addon_dir, "canonical")
    env["southbrook.os.loader"].load_canonical_directory(canonical_dir)
```

- [ ] **Step 7: Re-run the test.**

Expected: PASS — 2 tests, all 10 canonical slugs found, partner_faq content verified.

- [ ] **Step 8: Commit.**

```bash
git add addons/southbrook_os/
git commit -m "feat(os): seed canonical markdown + frontmatter-aware loader hook"
```

---

### Task 6: Catalog generator

**Files:**
- Create: `addons/southbrook_os/models/os_generators.py`
- Modify: `addons/southbrook_os/models/__init__.py`
- Create: `addons/southbrook_os/tests/test_generators.py`

- [ ] **Step 1: Write the failing test.**

```python
# addons/southbrook_os/tests/test_generators.py
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "southbrook_os")
class TestCatalogGenerator(TransactionCase):
    def test_catalog_generator_produces_section(self):
        result = self.env["southbrook.os.generators"].generate_catalog()
        section = self.env["southbrook.os.section"].search(
            [("slug", "=", "02_catalog.generated")], limit=1)
        self.assertTrue(section)
        self.assertEqual(section.source, "generated")
        self.assertIn("#", section.body)  # has at least one header
        # Should mention at least one real product family
        self.assertTrue(any(
            family in section.body
            for family in ["Base", "Wall", "Tall", "Vanity"]
        ))
        self.assertEqual(result["status"], "ok")

    def test_catalog_generator_is_idempotent(self):
        first = self.env["southbrook.os.generators"].generate_catalog()
        second = self.env["southbrook.os.generators"].generate_catalog()
        section = self.env["southbrook.os.section"].search(
            [("slug", "=", "02_catalog.generated")], limit=1)
        # Unchanged content should not bump version twice
        self.assertEqual(section.version, first["new_version"])
        self.assertEqual(section.version, second["new_version"])
```

- [ ] **Step 2: Run the test to verify it fails.**

Expected: FAIL — `southbrook.os.generators` does not exist.

- [ ] **Step 3: Implement the generator.**

```python
# addons/southbrook_os/models/os_generators.py
# SPDX-License-Identifier: LGPL-3.0-only
import hashlib

from odoo import api, fields, models


class OsGenerators(models.AbstractModel):
    _name = "southbrook.os.generators"
    _description = "Generators that mirror live Odoo state into OS sections."

    # ------------------------------------------------------------------
    # Catalog
    # ------------------------------------------------------------------
    @api.model
    def generate_catalog(self):
        body = self._render_catalog_md()
        return self._upsert_generated("02_catalog.generated", "Catalog (live)", body)

    def _render_catalog_md(self):
        Template = self.env["product.template"]
        templates = Template.search([
            ("active", "=", True),
            ("default_code", "like", "SB-%"),
        ], order="default_code")
        lines = [
            "---",
            "slug: 02_catalog.generated",
            "title: Catalog (live)",
            "source: generated",
            "---",
            "",
            "# Catalog (live)",
            "",
            "Rebuilt from `product.template` records on Odoo. The live SKU list, "
            "current variant counts, and any retired templates appear here.",
            "",
            f"Total active SB-* templates: **{len(templates)}**",
            "",
            "| SKU | Name | Variants |",
            "|---|---|---|",
        ]
        for t in templates:
            variant_count = len(t.product_variant_ids)
            lines.append(f"| `{t.default_code}` | {t.name} | {variant_count} |")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Shared upsert with hash-based no-op detection
    # ------------------------------------------------------------------
    def _upsert_generated(self, slug, name, body):
        body_hash = hashlib.sha256(body.encode()).hexdigest()
        Section = self.env["southbrook.os.section"]
        section = Section.search([("slug", "=", slug)], limit=1)
        if section:
            existing_hash = hashlib.sha256(
                (section.body or "").encode()).hexdigest()
            if existing_hash == body_hash:
                return {"status": "ok", "slug": slug, "changed": False,
                        "new_version": section.version}
            section.bump_version(body=body)
            return {"status": "ok", "slug": slug, "changed": True,
                    "new_version": section.version}
        section = Section.create({
            "slug": slug, "name": name, "source": "generated", "body": body,
        })
        return {"status": "ok", "slug": slug, "changed": True,
                "new_version": section.version}
```

- [ ] **Step 4: Register the generator.**

```python
# addons/southbrook_os/models/__init__.py
from . import os_section
from . import os_publication
from . import os_revision_order
from . import os_loader
from . import os_generators
```

- [ ] **Step 5: Re-run the test.**

Expected: PASS — 2 tests.

- [ ] **Step 6: Commit.**

```bash
git add addons/southbrook_os/
git commit -m "feat(os): catalog generator + hash-based idempotent upsert"
```

---

### Task 7: Attribute generator

**Files:**
- Modify: `addons/southbrook_os/models/os_generators.py`
- Modify: `addons/southbrook_os/tests/test_generators.py`

- [ ] **Step 1: Add the failing test.**

Append to `test_generators.py`:

```python
class TestAttributeGenerator(TransactionCase):
    def test_attribute_generator_lists_attributes(self):
        result = self.env["southbrook.os.generators"].generate_attributes()
        section = self.env["southbrook.os.section"].search(
            [("slug", "=", "03_attributes.generated")], limit=1)
        self.assertTrue(section)
        self.assertIn("attribute", section.body.lower())
        self.assertEqual(result["status"], "ok")
```

(Decorate the new class with the same `@tagged(...)`.)

- [ ] **Step 2: Run the test to verify it fails.**

Expected: FAIL — method `generate_attributes` does not exist.

- [ ] **Step 3: Implement the generator.**

Add to `os_generators.py` inside the `OsGenerators` class:

```python
    @api.model
    def generate_attributes(self):
        body = self._render_attributes_md()
        return self._upsert_generated(
            "03_attributes.generated", "Attributes (live)", body)

    def _render_attributes_md(self):
        Attr = self.env["product.attribute"]
        attrs = Attr.search([], order="sequence, name")
        lines = [
            "---",
            "slug: 03_attributes.generated",
            "title: Attributes (live)",
            "source: generated",
            "---",
            "",
            "# Attributes (live)",
            "",
            "Rebuilt from `product.attribute` and `product.attribute.value`.",
            "",
        ]
        for a in attrs:
            lines.append(f"## {a.name}")
            lines.append("")
            for v in a.value_ids.sorted("sequence"):
                lines.append(f"- {v.name}")
            lines.append("")
        return "\n".join(lines)
```

- [ ] **Step 4: Re-run the test.**

Expected: PASS — 3 tests now in `test_generators.py`.

- [ ] **Step 5: Commit.**

```bash
git add addons/southbrook_os/
git commit -m "feat(os): attribute generator from product.attribute"
```

---

### Task 8: Cut-spec generator

**Files:**
- Modify: `addons/southbrook_os/models/os_generators.py`
- Modify: `addons/southbrook_os/tests/test_generators.py`

- [ ] **Step 1: Add the failing test.**

```python
class TestCutSpecGenerator(TransactionCase):
    def test_cut_spec_generator_emits_active_values(self):
        result = self.env["southbrook.os.generators"].generate_cut_spec()
        section = self.env["southbrook.os.section"].search(
            [("slug", "=", "06_cut_spec.generated")], limit=1)
        self.assertTrue(section)
        # Body should mention thickness or reveal terminology
        text = section.body.lower()
        self.assertTrue("thickness" in text or "reveal" in text)
        self.assertEqual(result["status"], "ok")
```

- [ ] **Step 2: Run the test to verify it fails.**

Expected: FAIL.

- [ ] **Step 3: Implement the generator.**

Add to `os_generators.py`:

```python
    @api.model
    def generate_cut_spec(self):
        body = self._render_cut_spec_md()
        return self._upsert_generated(
            "06_cut_spec.generated", "Cut Specification (active)", body)

    def _render_cut_spec_md(self):
        CutSpec = self.env.get("southbrook.cut.spec")
        if CutSpec is None:
            # southbrook_plm not installed yet — emit a stub
            body = (
                "---\nslug: 06_cut_spec.generated\n"
                "title: Cut Specification (active)\nsource: generated\n---\n\n"
                "# Cut Specification (active)\n\n"
                "*Cut spec source not available on this instance.*\n"
            )
            return body
        spec = CutSpec.search([("active", "=", True)], limit=1, order="id desc")
        if not spec:
            body = (
                "---\nslug: 06_cut_spec.generated\n"
                "title: Cut Specification (active)\nsource: generated\n---\n\n"
                "# Cut Specification (active)\n\n"
                "*No active cut spec defined.*\n"
            )
            return body
        # Render the active spec — field names match southbrook_plm conventions.
        fields_to_emit = [
            ("box_thickness_mm", "Box / Carcass Thickness", "mm"),
            ("back_thickness_mm", "Back-Panel Thickness", "mm"),
            ("rabbet_depth_mm", "Rabbet Depth", "mm"),
            ("door_thickness_mm", "Door Thickness", "mm"),
            ("door_reveal_mm", "Door Reveal", "mm"),
            ("shelf_tolerance_mm", "Shelf Tolerance", "mm"),
            ("shelf_vent_gap_mm", "Shelf Ventilation Gap", "mm"),
            ("toe_kick_height_mm", "Toe-Kick Height", "mm"),
        ]
        lines = [
            "---", "slug: 06_cut_spec.generated",
            "title: Cut Specification (active)", "source: generated", "---", "",
            f"# Cut Specification (active) — {spec.display_name}", "",
            "| Parameter | Value | Unit |", "|---|---|---|",
        ]
        for fname, label, unit in fields_to_emit:
            val = getattr(spec, fname, None)
            if val is not None:
                lines.append(f"| {label} | {val} | {unit} |")
        return "\n".join(lines)
```

- [ ] **Step 4: Re-run the test.**

Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add addons/southbrook_os/
git commit -m "feat(os): cut-spec generator with graceful PLM-absent fallback"
```

---

### Task 9: Work-center generator

**Files:**
- Modify: `addons/southbrook_os/models/os_generators.py`
- Modify: `addons/southbrook_os/tests/test_generators.py`

- [ ] **Step 1: Add the failing test.**

```python
class TestWorkCenterGenerator(TransactionCase):
    def test_work_center_generator(self):
        result = self.env["southbrook.os.generators"].generate_work_centers()
        section = self.env["southbrook.os.section"].search(
            [("slug", "=", "08_work_centers.generated")], limit=1)
        self.assertTrue(section)
        self.assertIn("Work Center", section.body)
        self.assertEqual(result["status"], "ok")
```

- [ ] **Step 2: Run the test to verify it fails.**

Expected: FAIL.

- [ ] **Step 3: Implement.**

Add to `os_generators.py`:

```python
    @api.model
    def generate_work_centers(self):
        body = self._render_work_centers_md()
        return self._upsert_generated(
            "08_work_centers.generated", "Work Centers (live)", body)

    def _render_work_centers_md(self):
        WC = self.env["mrp.workcenter"]
        centers = WC.search([("active", "=", True)], order="sequence, name")
        lines = [
            "---", "slug: 08_work_centers.generated",
            "title: Work Centers (live)", "source: generated", "---", "",
            "# Work Centers (live)", "",
            "Rebuilt from `mrp.workcenter`.", "",
            "| Work Center | OEE Target | Capacity |", "|---|---|---|",
        ]
        for c in centers:
            oee = getattr(c, "oee_target", "—")
            capacity = getattr(c, "default_capacity", "—")
            lines.append(f"| {c.name} | {oee} | {capacity} |")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Generate all (convenience for the cron + manual button)
    # ------------------------------------------------------------------
    @api.model
    def generate_all(self):
        results = []
        for fn in ("generate_catalog", "generate_attributes",
                   "generate_cut_spec", "generate_work_centers"):
            results.append(getattr(self, fn)())
        return results
```

- [ ] **Step 4: Re-run the test.**

Expected: PASS — 5 tests total in `test_generators.py`.

- [ ] **Step 5: Commit.**

```bash
git add addons/southbrook_os/
git commit -m "feat(os): work-center generator + generate_all entrypoint"
```

---

### Task 10: Nightly cron + manual trigger

**Files:**
- Create: `addons/southbrook_os/data/ir_cron.xml`
- Create: `addons/southbrook_os/tests/test_cron.py`

- [ ] **Step 1: Write the failing test.**

```python
# addons/southbrook_os/tests/test_cron.py
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "southbrook_os")
class TestOsCron(TransactionCase):
    def test_cron_record_exists(self):
        cron = self.env.ref(
            "southbrook_os.cron_regenerate_os_sections",
            raise_if_not_found=False,
        )
        self.assertTrue(cron, "Expected southbrook_os.cron_regenerate_os_sections")
        self.assertEqual(cron.interval_type, "days")
        self.assertEqual(cron.interval_number, 1)
        self.assertTrue(cron.active)

    def test_cron_method_runs_without_error(self):
        # Should not raise even if some sources are missing
        self.env["southbrook.os.generators"].generate_all()
```

- [ ] **Step 2: Run the test to verify it fails.**

Expected: FAIL — cron record does not exist.

- [ ] **Step 3: Create the cron XML.**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
  <data noupdate="1">
    <record id="cron_regenerate_os_sections" model="ir.cron">
      <field name="name">Southbrook OS — regenerate sections</field>
      <field name="model_id" ref="model_southbrook_os_generators"/>
      <field name="state">code</field>
      <field name="code">model.generate_all()</field>
      <field name="interval_number">1</field>
      <field name="interval_type">days</field>
      <field name="numbercall">-1</field>
      <field name="active" eval="True"/>
    </record>
  </data>
</odoo>
```

(`ir_cron.xml` is already declared in the manifest's `data` list from Task 1.)

- [ ] **Step 4: Re-run the test.**

Expected: PASS — 2 tests.

- [ ] **Step 5: Commit.**

```bash
git add addons/southbrook_os/
git commit -m "feat(os): nightly ir.cron for generate_all"
```

---

### Task 11: Public `/southbrook/os.json` endpoint

**Files:**
- Create: `addons/southbrook_os/controllers/os_public.py`
- Modify: `addons/southbrook_os/controllers/__init__.py`
- Create: `addons/southbrook_os/tests/test_public_endpoint.py`

- [ ] **Step 1: Write the failing test.**

```python
# addons/southbrook_os/tests/test_public_endpoint.py
import json

from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install", "southbrook", "southbrook_os", "-standard")
class TestOsPublicEndpoint(HttpCase):
    def test_os_json_returns_sections(self):
        resp = self.url_open("/southbrook/os.json")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("sections", data)
        self.assertIn("publication", data)
        self.assertGreaterEqual(len(data["sections"]), 5)
        # At least the charter should be present
        slugs = {s["slug"] for s in data["sections"]}
        self.assertIn("00_charter", slugs)

    def test_section_payload_shape(self):
        resp = self.url_open("/southbrook/os.json")
        data = resp.json()
        section = data["sections"][0]
        for key in ("slug", "name", "version", "source", "body", "last_updated_at"):
            self.assertIn(key, section)
```

- [ ] **Step 2: Run the test to verify it fails.**

Expected: FAIL — 404 on `/southbrook/os.json`.

- [ ] **Step 3: Implement the controller.**

```python
# addons/southbrook_os/controllers/os_public.py
# SPDX-License-Identifier: LGPL-3.0-only
import datetime

from odoo import http
from odoo.http import request


class OsPublicController(http.Controller):

    @http.route("/southbrook/os.json", type="http", auth="public",
                website=False, methods=["GET"], csrf=False)
    def os_json(self, **kw):
        sections = request.env["southbrook.os.section"].sudo().search(
            [], order="slug")
        Pub = request.env["southbrook.os.publication"].sudo()
        calendar_key = datetime.date.today().strftime("%Y-%m")
        publication = Pub.publish(calendar_key)
        payload = {
            "tenant": "southbrook",
            "publication": {
                "calendar_key": publication.calendar_key,
                "build_hash": publication.build_hash,
                "built_at": publication.built_at.isoformat(),
            },
            "sections": [
                {
                    "slug": s.slug,
                    "name": s.name,
                    "version": s.version,
                    "source": s.source,
                    "audience_tags": s.audience_tags or "",
                    "body": s.body,
                    "last_updated_at": s.last_updated_at.isoformat()
                        if s.last_updated_at else None,
                }
                for s in sections
            ],
        }
        return request.make_response(
            request.env["ir.json"].dumps(payload) if hasattr(request.env, "ir.json")
                else __import__("json").dumps(payload),
            headers=[
                ("Content-Type", "application/json"),
                ("Cache-Control", "public, max-age=300"),
            ],
        )
```

- [ ] **Step 4: Register the controller.**

```python
# addons/southbrook_os/controllers/__init__.py
from . import os_public
```

- [ ] **Step 5: Re-run the test.**

Expected: PASS — 2 tests.

- [ ] **Step 6: Commit.**

```bash
git add addons/southbrook_os/
git commit -m "feat(os): GET /southbrook/os.json public endpoint"
```

---

### Task 12: RAG corpus export

**Files:**
- Create: `addons/southbrook_os/exports/rag_corpus_export.py`
- Modify: `addons/southbrook_os/exports/__init__.py`
- Create: `addons/southbrook_os/tests/test_rag_export.py`

- [ ] **Step 1: Write the failing test.**

```python
# addons/southbrook_os/tests/test_rag_export.py
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "southbrook_os")
class TestRagExport(TransactionCase):
    def test_export_emits_one_entry_per_section(self):
        bundle = self.env["southbrook.os.rag.export"].build_bundle(
            tenant="southbrook")
        self.assertEqual(bundle["tenant"], "southbrook")
        self.assertIn("documents", bundle)
        slugs = {d["slug"] for d in bundle["documents"]}
        self.assertIn("00_charter", slugs)

    def test_export_includes_metadata_per_document(self):
        bundle = self.env["southbrook.os.rag.export"].build_bundle(
            tenant="southbrook")
        doc = bundle["documents"][0]
        for key in ("slug", "name", "version", "source", "text", "audience"):
            self.assertIn(key, doc)
```

- [ ] **Step 2: Run the test to verify it fails.**

Expected: FAIL — model does not exist.

- [ ] **Step 3: Implement the exporter.**

```python
# addons/southbrook_os/exports/rag_corpus_export.py
# SPDX-License-Identifier: LGPL-3.0-only
import datetime
import hashlib

from odoo import api, models


class RagCorpusExport(models.AbstractModel):
    _name = "southbrook.os.rag.export"
    _description = "Build the RAG-grounding bundle for the Hermes sidecar."

    @api.model
    def build_bundle(self, tenant):
        sections = self.env["southbrook.os.section"].search([], order="slug")
        body_concat = "".join(s.body or "" for s in sections)
        build_hash = hashlib.sha256(body_concat.encode()).hexdigest()[:16]
        return {
            "tenant": tenant,
            "build_hash": build_hash,
            "built_at": datetime.datetime.utcnow().isoformat() + "Z",
            "documents": [
                {
                    "slug": s.slug,
                    "name": s.name,
                    "version": s.version,
                    "source": s.source,
                    "audience": (s.audience_tags or "").split(",") if s.audience_tags else [],
                    "text": s.body or "",
                }
                for s in sections
            ],
        }
```

- [ ] **Step 4: Register the export.**

```python
# addons/southbrook_os/exports/__init__.py
from . import rag_corpus_export
```

- [ ] **Step 5: Re-run the test.**

Expected: PASS — 2 tests.

- [ ] **Step 6: Commit.**

```bash
git add addons/southbrook_os/
git commit -m "feat(os): RAG corpus export for Hermes sidecar consumption"
```

---

### Task 13: OS coverage test for the partner FAQ

**Files:**
- Create: `addons/southbrook_os/tests/test_os_coverage.py`

- [ ] **Step 1: Write the test.**

```python
# addons/southbrook_os/tests/test_os_coverage.py
from odoo.tests.common import TransactionCase, tagged


_REQUIRED_SLUGS = [
    "00_charter",
    "01_company",
    "02_catalog",
    "03_attributes",
    "04_lifecycle",
    "05_production",
    "06_plm",
    "07_partner_faq",
    "20_systems_topology",
    "99_glossary",
]


@tagged("post_install", "-at_install", "southbrook", "southbrook_os")
class TestOsCoverage(TransactionCase):
    def test_all_required_canonical_sections_exist(self):
        Section = self.env["southbrook.os.section"]
        existing = {s.slug for s in Section.search([("source", "=", "canonical")])}
        missing = [slug for slug in _REQUIRED_SLUGS if slug not in existing]
        self.assertFalse(missing, f"Missing required canonical sections: {missing}")

    def test_partner_faq_contains_anchor_questions(self):
        """The 'where is my kitchen?' question must always be answerable from
        the FAQ — it is the headline Hermes use case."""
        section = self.env["southbrook.os.section"].search(
            [("slug", "=", "07_partner_faq")], limit=1)
        self.assertTrue(section)
        anchor_questions = [
            "Where is my kitchen?",
            "What's blocking my install?",
            "When will my install be ready?",
        ]
        for q in anchor_questions:
            self.assertIn(q, section.body,
                f"FAQ section missing anchor question: {q!r}")
```

- [ ] **Step 2: Run the test.**

Expected: PASS (assuming Task 5 loaded the canonical files correctly).

- [ ] **Step 3: Commit.**

```bash
git add addons/southbrook_os/
git commit -m "test(os): OS coverage — required sections + FAQ anchor questions"
```

---

### Task 14: Deploy + smoke test

**Files:**
- No new files. Uses existing `scripts/deploy_to_qnap.sh`.

- [ ] **Step 1: Run the full test suite locally (against the live container if no local DB is set up).**

```bash
ssh -o ProxyCommand="cloudflared access ssh --hostname %h" admin@ssh.odooiq.com \
  '/share/CACHEDEV3_DATA/.qpkg/container-station/bin/system-docker exec southbrook-odoo \
  odoo --test-enable --test-tags=southbrook_os -i southbrook_os -d southbrook --stop-after-init --no-http'
```

Expected: every test in the `southbrook_os` tag passes; final summary shows `Modules loaded.` + `Registry loaded`.

- [ ] **Step 2: Deploy via the tunnel.**

```bash
DEPLOY_VIA=tunnel QNAP_TUNNEL_HOST=admin@ssh.odooiq.com RESTART=1 \
  ./scripts/deploy_to_qnap.sh southbrook_os
```

Expected: `[deploy] live /web/login → 200`, post-deploy version `southbrook_os 19.0.1.0.0`.

- [ ] **Step 3: Smoke test the public endpoint.**

```bash
curl -s -o /dev/null -w "status=%{http_code} ct=%{content_type}\n" \
  https://southbrookcabinetry.space/southbrook/os.json
```

Expected: `status=200 ct=application/json`.

- [ ] **Step 4: Spot-check the JSON content.**

```bash
curl -s https://southbrookcabinetry.space/southbrook/os.json | \
  python3 -c "import sys, json; \
d = json.load(sys.stdin); \
print('tenant:', d['tenant']); \
print('publication:', d['publication']['calendar_key'], d['publication']['build_hash']); \
print('section count:', len(d['sections'])); \
print('slugs:', [s['slug'] for s in d['sections']])"
```

Expected: `tenant: southbrook`, publication key like `2026-06`, section count ≥ 10, slugs include `00_charter` through `99_glossary`.

- [ ] **Step 5: Verify generators run via cron manually.**

```bash
ssh -o ProxyCommand="cloudflared access ssh --hostname %h" admin@ssh.odooiq.com \
  '/share/CACHEDEV3_DATA/.qpkg/container-station/bin/system-docker exec southbrook-odoo \
  odoo shell -d southbrook --no-http <<EOF
result = env["southbrook.os.generators"].generate_all()
print(result)
env.cr.commit()
EOF'
```

Expected: list of four `{"status": "ok", ...}` dicts. After this, `/southbrook/os.json` should show four additional `*.generated` sections.

- [ ] **Step 6: Re-verify the endpoint reflects generated sections.**

```bash
curl -s https://southbrookcabinetry.space/southbrook/os.json | \
  python3 -c "import sys, json; \
d = json.load(sys.stdin); \
generated = [s['slug'] for s in d['sections'] if s['source'] == 'generated']; \
print('generated sections:', generated)"
```

Expected: includes `02_catalog.generated`, `03_attributes.generated`, `06_cut_spec.generated`, `08_work_centers.generated`.

- [ ] **Step 7: Commit + tag the v1.0 release.**

```bash
git tag -a southbrook_os-v1.0.0 -m "southbrook_os v1.0 — OS layer with canonical + generators + public endpoint"
git push --tags  # if origin is set up
```

---

## Self-review

**Spec coverage check:**
- §2.1 OS addon structure: Tasks 1-12 cover manifest, models, controllers, exports, data, security, canonical content.
- §5.1 `southbrook.os.section`: Task 2 ✓
- §5.2 OSRO state machine: Task 4 ✓
- §5.3 publications: Task 3 ✓
- §5.4 generators: Tasks 6-9 ✓
- §5.5 public endpoints: Task 11 ships `/southbrook/os.json`. **`/southbrook/os` HTML and `/southbrook/os.pdf` are explicitly deferred to v1.1 per the spec § 8 phase table** — they are not in this plan and that is correct.
- §5.6 coverage tests: Task 13 ✓
- §7 RAG corpus export: Task 12 ✓
- §8 v1.0 acceptance: Task 14 smoke-tests `/southbrook/os.json` end-to-end ✓

**Multi-tenant hooks:** The spec §8 v1.0 row calls out three multi-tenant hooks (JWT carries tenant claim, sidecar paths namespace by tenant, tool dispatch reads tenant→Odoo from registry). Those hooks live in **Plan B (Hermes + sidecar)**, not this plan. The OS addon doesn't need them because the OS addon is per-tenant by construction (each tenant installs their own copy). Confirmed not a gap.

**Placeholder scan:** clean — no TBD / TODO / placeholder content. Canonical markdown is delegated to the sibling seed file with explicit "copy verbatim" instruction.

**Type consistency:** model name `southbrook.os.section` used in all tasks; `southbrook.os.publication` and `southbrook.os.publication.section` consistently used; OSRO is `southbrook.os.revision` everywhere; generators use `southbrook.os.generators` everywhere; RAG export is `southbrook.os.rag.export` everywhere.

**Scope:** focused on the OS addon v1.0 only; Hermes extensions and the Vercel sidecar are out of scope (Plan B).

---

## Out of scope for this plan (covered by future plans)

- **Plan B (next):** `southbrook_hermes` tool package, JWT proxy controller, OWL chat panel, Vercel sidecar with RAG indexing and AI Gateway integration.
- **v1.1:** OSRO Kanban/form views, `/southbrook/os` HTML viewer, `/southbrook/os.pdf` renderer.
- **v1.2:** Sales-rep backend chat panel + sales-rep tool set.
- **v1.3:** Manufacturing-manager Kitchen Ops widget.
- **v1.x:** Overseer + meta-OS for the fleet.
