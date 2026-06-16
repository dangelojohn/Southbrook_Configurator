# Hermes Trade-Partner v1 — Plan B1 (Odoo side)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing `southbrook_hermes` addon with the Odoo side of the Hermes trade-partner agent — a tool registry (12 functions decorated with `@hermes_tool`), a JWT minting + verification utility, three controllers (`/hermes/v1/ask` proxy, `/api/hermes/tools` registry + dispatch, `/api/hermes/conversation/log` persistence), and the ACL plumbing that makes the existing portal record rules enforce per-partner data scoping. After Plan B1 ships, every tool is callable via `curl` with a hand-crafted JWT — no LLM yet, but every read/write boundary is fully exercised. Plan B2 (sidecar) connects the LLM layer.

**Architecture:** All work lives inside `addons/southbrook_hermes/`. New packages: `tools/` (Python decorator + 12 tool functions), `utils/` (JWT helper using PyJWT), `controllers/` adds three route files. The existing `southbrook.hermes.question` and `southbrook.hermes.recommendation` models are reused as the persistence layer for conversation logs and T2 actions. The addon depends on `southbrook_os` (built in Plan A) for `get_os_section`. JWT signing key lives in `ir.config_parameter`.

**Tech Stack:** Odoo 19 CE (`http.Controller`, decorated Python functions, `request.env`), Python 3.12, `PyJWT` library (already standard in modern Odoo installs but listed as an `external_dependencies` for safety), TransactionCase/HttpCase tests.

**Reference:**
- Spec: `docs/superpowers/specs/2026-06-16-southbrook-os-and-hermes-platform-design.md` §2.2, §3, §4, §6
- Plan A (foundation): `docs/superpowers/plans/2026-06-16-southbrook-os-v1.md` (shipped 2026-06-16)
- Fabio v0 (existing): `addons/southbrook_hermes/` (already deployed)

---

## File structure

```
addons/southbrook_hermes/
├── __manifest__.py                          MODIFY: bump version, add southbrook_os dep, add pyjwt
├── utils/                                   NEW package
│   ├── __init__.py                          NEW
│   └── jwt_helper.py                        NEW: mint_jwt(), verify_jwt(), resolve_persona()
├── tools/                                   NEW package
│   ├── __init__.py                          NEW: registers decorator + tool imports
│   ├── decorator.py                         NEW: @hermes_tool + registry
│   ├── read_tools.py                        NEW: 9 read tools
│   ├── write_tools.py                       NEW: 3 write tools
│   └── ... (no nested folders — flat structure)
├── controllers/
│   ├── __init__.py                          MODIFY: register new controllers
│   ├── hermes_proxy.py                      NEW: POST /hermes/v1/ask
│   ├── hermes_tools_api.py                  NEW: GET /api/hermes/tools, POST /api/hermes/tools/<name>
│   └── hermes_conversation_api.py           NEW: POST /api/hermes/conversation/log
├── data/
│   └── ir_config_parameter.xml              NEW: seed the JWT secret param (placeholder; admin rotates)
├── models/
│   └── hermes_question.py                   MODIFY: add log_conversation() class method
├── security/
│   └── ir.model.access.csv                  MODIFY: confirm partner-scoped access on hermes models
└── tests/
    ├── test_jwt_helper.py                   NEW
    ├── test_tool_decorator.py               NEW
    ├── test_read_tools.py                   NEW
    ├── test_write_tools.py                  NEW
    ├── test_hermes_proxy.py                 NEW
    ├── test_hermes_tools_api.py             NEW
    └── test_hermes_conversation_api.py      NEW
```

---

## Tasks

### Task 1: Bump manifest + scaffold tools/ + utils/ packages

**Files:**
- Modify: `addons/southbrook_hermes/__manifest__.py`
- Create: `addons/southbrook_hermes/utils/__init__.py`
- Create: `addons/southbrook_hermes/tools/__init__.py`
- Create: `addons/southbrook_hermes/data/ir_config_parameter.xml`

- [ ] **Step 1: Bump manifest version + add `southbrook_os` dep + register pyjwt + new data file.**

Modify `addons/southbrook_hermes/__manifest__.py`. Add to `depends`:

```python
    "depends": [
        "mail",
        "project",
        "southbrook_api",
        "southbrook_kitchen_workspace",
        "southbrook_os",                  # NEW — for get_os_section tool
    ],
```

Bump version `19.0.1.1.0` → `19.0.2.0.0` (minor bump signals significant new surface).

Add to `data`:

```python
        "data/ir_config_parameter.xml",
```

Add `external_dependencies`:

```python
    "external_dependencies": {
        "python": ["jwt"],
    },
```

- [ ] **Step 2: Create empty package init files.**

```python
# addons/southbrook_hermes/utils/__init__.py
from . import jwt_helper
```

```python
# addons/southbrook_hermes/tools/__init__.py
# Tool registry is populated as tool modules are added in subsequent tasks.
from . import decorator
from . import read_tools
from . import write_tools
```

(Both `read_tools` and `write_tools` will exist as empty modules until Task 3+. The imports will work because each module just needs to exist with no errors.)

Create placeholder empty modules so the imports above don't break in Task 1:

```python
# addons/southbrook_hermes/tools/decorator.py
# Populated in Task 2.
```

```python
# addons/southbrook_hermes/tools/read_tools.py
# Populated in Task 3.
```

```python
# addons/southbrook_hermes/tools/write_tools.py
# Populated in Task 5.
```

- [ ] **Step 3: Seed the JWT secret config parameter.**

Create `addons/southbrook_hermes/data/ir_config_parameter.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
  <data noupdate="1">
    <!-- Placeholder. Rotate by writing a new value via the Settings →
         Technical → System Parameters UI before going live. -->
    <record id="hermes_jwt_secret" model="ir.config_parameter">
      <field name="key">southbrook_hermes.jwt_secret</field>
      <field name="value">PLACEHOLDER_ROTATE_BEFORE_PRODUCTION</field>
    </record>
    <record id="hermes_sidecar_url" model="ir.config_parameter">
      <field name="key">southbrook_hermes.sidecar_url</field>
      <field name="value">https://hermes.southbrookcabinetry.space</field>
    </record>
  </data>
</odoo>
```

- [ ] **Step 4: Wire utils/ into the addon's root __init__.py.**

Modify `addons/southbrook_hermes/__init__.py` to add:

```python
from . import utils
from . import tools
```

(Keep all existing imports — models, controllers — and add these two.)

- [ ] **Step 5: Commit.**

```bash
git add addons/southbrook_hermes/
git commit -m "feat(hermes): scaffold utils/ + tools/ packages, bump to 19.0.2.0.0, depend on southbrook_os"
```

---

### Task 2: JWT helper + tests

**Files:**
- Create: `addons/southbrook_hermes/utils/jwt_helper.py`
- Create: `addons/southbrook_hermes/tests/test_jwt_helper.py`
- Modify: `addons/southbrook_hermes/tests/__init__.py`

- [ ] **Step 1: Write the failing tests.**

Create `addons/southbrook_hermes/tests/test_jwt_helper.py`:

```python
# addons/southbrook_hermes/tests/test_jwt_helper.py
import time

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "hermes")
class TestJwtHelper(TransactionCase):
    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_param(
            "southbrook_hermes.jwt_secret", "test_secret_long_enough_for_hs256")
        from odoo.addons.southbrook_hermes.utils import jwt_helper
        self.helper = jwt_helper

    def test_mint_and_verify_roundtrip(self):
        token = self.helper.mint_jwt(
            self.env, tenant="southbrook", persona="trade_partner",
            partner_id=42, tier="T0+T1", extra={"order_id": 235})
        claims = self.helper.verify_jwt(self.env, token)
        self.assertEqual(claims["tenant"], "southbrook")
        self.assertEqual(claims["persona"], "trade_partner")
        self.assertEqual(claims["partner_id"], 42)
        self.assertEqual(claims["tier"], "T0+T1")
        self.assertEqual(claims["order_id"], 235)
        self.assertIn("exp", claims)
        self.assertIn("iat", claims)

    def test_expired_token_rejected(self):
        token = self.helper.mint_jwt(
            self.env, tenant="southbrook", persona="trade_partner",
            partner_id=42, tier="T0+T1", ttl_seconds=-1)
        with self.assertRaises(Exception):
            self.helper.verify_jwt(self.env, token)

    def test_tampered_token_rejected(self):
        token = self.helper.mint_jwt(
            self.env, tenant="southbrook", persona="trade_partner",
            partner_id=42, tier="T0+T1")
        tampered = token[:-5] + "XXXXX"
        with self.assertRaises(Exception):
            self.helper.verify_jwt(self.env, tampered)

    def test_resolve_persona_portal_user_is_trade_partner(self):
        portal_user = self.env["res.users"].create({
            "login": f"hermes_test_{int(time.time())}@example.com",
            "name": "Hermes Test Portal",
            "groups_id": [(6, 0, [self.env.ref("base.group_portal").id])],
        })
        result = self.helper.resolve_persona(portal_user)
        self.assertEqual(result, "trade_partner")
```

(Note `groups_id` — the test runs against a fresh user where the new `group_ids` alias on res.users may not be fully wired yet. The v19 alias accepts both. If `groups_id` doesn't work in this exact context, fall back to `group_ids`.)

- [ ] **Step 2: Implement the helper.**

Create `addons/southbrook_hermes/utils/jwt_helper.py`:

```python
# SPDX-License-Identifier: LGPL-3.0-only
"""JWT minting + verification + persona resolution for Hermes."""
import datetime
import logging

from odoo.exceptions import AccessError

try:
    import jwt as _pyjwt
except ImportError:  # pragma: no cover
    _pyjwt = None

_logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 60
JWT_ALGORITHM = "HS256"


def _get_secret(env):
    secret = env["ir.config_parameter"].sudo().get_param(
        "southbrook_hermes.jwt_secret")
    if not secret or secret == "PLACEHOLDER_ROTATE_BEFORE_PRODUCTION":
        raise RuntimeError(
            "southbrook_hermes.jwt_secret is not set. Rotate the placeholder "
            "via Settings → Technical → System Parameters before going live.")
    return secret


def mint_jwt(env, *, tenant, persona, partner_id, tier,
             ttl_seconds=DEFAULT_TTL_SECONDS, extra=None):
    """Mint a short-lived JWT carrying tenant, persona, partner_id, and tier.

    `extra` is merged into the claims (e.g. {"order_id": 235}).
    """
    if _pyjwt is None:
        raise RuntimeError("PyJWT not installed. Add 'jwt' to external_dependencies.")
    now = datetime.datetime.utcnow()
    payload = {
        "iat": int(now.timestamp()),
        "exp": int((now + datetime.timedelta(seconds=ttl_seconds)).timestamp()),
        "tenant": tenant,
        "persona": persona,
        "partner_id": partner_id,
        "tier": tier,
    }
    if extra:
        payload.update(extra)
    return _pyjwt.encode(payload, _get_secret(env), algorithm=JWT_ALGORITHM)


def verify_jwt(env, token):
    """Verify a JWT and return its decoded claims dict. Raises on bad sig or expired."""
    if _pyjwt is None:
        raise RuntimeError("PyJWT not installed.")
    return _pyjwt.decode(token, _get_secret(env), algorithms=[JWT_ALGORITHM])


def resolve_persona(user):
    """Map a res.users record to a Hermes persona string.

    v1.0 ships trade_partner only; sales_rep + mfg_manager will resolve in
    v1.1 and v1.2. If a user matches none, raise AccessError so the proxy
    controller can return 403.
    """
    if user.share:
        return "trade_partner"
    if user.has_group("sales_team.group_sale_salesman"):
        return "sales_rep"
    if user.has_group("southbrook_kitchen_workspace.group_kitchen_ops"):
        return "mfg_manager"
    raise AccessError("Hermes is not available for this user role.")


def tier_for_persona(persona):
    """Default tier mask per persona. Trade partners get T0+T1 — T2 routes to recommendations."""
    return {
        "trade_partner": "T0+T1",
        "sales_rep": "T0+T1+T2",
        "mfg_manager": "T0+T1+T2",
    }.get(persona, "T0")
```

- [ ] **Step 3: Register the test.**

Modify `addons/southbrook_hermes/tests/__init__.py` to add:

```python
from . import test_jwt_helper
```

(Keep existing imports.)

- [ ] **Step 4: Commit.**

```bash
git add addons/southbrook_hermes/
git commit -m "feat(hermes): JWT helper — mint/verify/resolve_persona/tier_for_persona"
```

---

### Task 3: Tool decorator + registry + read tools batch 1

**Files:**
- Modify: `addons/southbrook_hermes/tools/decorator.py`
- Modify: `addons/southbrook_hermes/tools/read_tools.py`
- Create: `addons/southbrook_hermes/tests/test_tool_decorator.py`
- Create: `addons/southbrook_hermes/tests/test_read_tools.py`
- Modify: `addons/southbrook_hermes/tests/__init__.py`

- [ ] **Step 1: Write failing tests for the decorator + registry.**

Create `addons/southbrook_hermes/tests/test_tool_decorator.py`:

```python
# addons/southbrook_hermes/tests/test_tool_decorator.py
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "hermes")
class TestToolDecorator(TransactionCase):
    def test_registry_collects_decorated_functions(self):
        from odoo.addons.southbrook_hermes.tools.decorator import TOOL_REGISTRY
        # Read tools (Task 3 + 4) and write tools (Tasks 5-7) all populate this
        slugs = {t["slug"] for t in TOOL_REGISTRY}
        # At minimum, the three landed in Task 3 must be present
        for required in ["list_my_orders", "get_order_status", "get_order_line"]:
            self.assertIn(
                required, slugs,
                f"Expected southbrook__{required} in TOOL_REGISTRY")

    def test_registry_filter_by_persona_and_tier(self):
        from odoo.addons.southbrook_hermes.tools.decorator import (
            TOOL_REGISTRY, registry_for_persona)
        slice_ = registry_for_persona("trade_partner", "T0+T1")
        # All trade-partner T0+T1 tools should be in the slice
        for tool in TOOL_REGISTRY:
            if "trade_partner" in tool["personas"]:
                if tool["tier"] in ("T0", "T1"):
                    self.assertIn(tool["slug"], [t["slug"] for t in slice_])
        # No T2 tools in this slice for trade_partner
        for tool in slice_:
            self.assertIn(tool["tier"], ("T0", "T1"))
```

- [ ] **Step 2: Implement the decorator + registry.**

Overwrite `addons/southbrook_hermes/tools/decorator.py`:

```python
# SPDX-License-Identifier: LGPL-3.0-only
"""@hermes_tool decorator and the in-process TOOL_REGISTRY.

Each tool function is registered with metadata: slug, personas, tier,
scope, description, and parameter schema. The Hermes sidecar fetches
this registry at boot via GET /api/hermes/tools, filtered by
(persona, tier).
"""
import functools
import inspect

TOOL_REGISTRY = []


def hermes_tool(*, personas, tier, scope, description, parameters=None):
    """Decorator. Registers a tool function with its metadata.

    Args:
        personas: list of persona slugs allowed to call this tool
                  (e.g., ["trade_partner", "sales_rep"]).
        tier: "T0", "T1", or "T2".
        scope: "own" / "own_order" / "global" / "elevated" — informational.
        description: one-line human-readable description for the LLM.
        parameters: JSON Schema fragment describing tool args, or None.
    """
    def wrap(fn):
        slug = fn.__name__
        params = parameters or _extract_params_from_signature(fn)
        TOOL_REGISTRY.append({
            "slug": slug,
            "qualified_slug": f"southbrook__{slug}",
            "personas": list(personas),
            "tier": tier,
            "scope": scope,
            "description": description,
            "parameters": params,
            "fn": fn,
        })
        @functools.wraps(fn)
        def call(env, **kwargs):
            return fn(env, **kwargs)
        return call
    return wrap


def _extract_params_from_signature(fn):
    """Best-effort: build a JSON schema fragment from the function signature.

    Skips the leading `env` parameter. Any param without a default becomes
    required.
    """
    sig = inspect.signature(fn)
    props = {}
    required = []
    for name, param in sig.parameters.items():
        if name == "env":
            continue
        # Map Python annotation → JSON schema type — minimal mapping
        json_type = "string"
        if param.annotation is int:
            json_type = "integer"
        elif param.annotation is bool:
            json_type = "boolean"
        elif param.annotation is float:
            json_type = "number"
        props[name] = {"type": json_type}
        if param.default is inspect.Parameter.empty:
            required.append(name)
    return {"type": "object", "properties": props, "required": required}


def registry_for_persona(persona, tier_mask):
    """Return the list of tools accessible to (persona, tier_mask).

    tier_mask is "T0", "T0+T1", or "T0+T1+T2".
    """
    allowed_tiers = set(tier_mask.split("+"))
    return [
        {k: v for k, v in t.items() if k != "fn"}  # don't leak the Python function
        for t in TOOL_REGISTRY
        if persona in t["personas"] and t["tier"] in allowed_tiers
    ]


def get_tool_function(slug):
    """Look up the underlying Python callable by slug. Returns None if not found."""
    for t in TOOL_REGISTRY:
        if t["slug"] == slug:
            return t["fn"]
    return None
```

- [ ] **Step 3: Write the failing tests for the three read tools.**

Create `addons/southbrook_hermes/tests/test_read_tools.py`:

```python
# addons/southbrook_hermes/tests/test_read_tools.py
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "hermes")
class TestReadToolsBatch1(TransactionCase):
    def setUp(self):
        super().setUp()
        # Create a partner + portal user + a sale order they own
        self.partner = self.env["res.partner"].create({
            "name": "Hermes Test Partner",
        })
        product = self.env["product.product"].search([], limit=1)
        if not product:
            self.skipTest("No products in DB to build a sale order from")
        self.order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": product.id,
                "product_uom_qty": 1,
            })],
        })
        from odoo.addons.southbrook_hermes.tools import read_tools  # noqa
        self.tools = read_tools

    def test_list_my_orders(self):
        result = self.tools.list_my_orders(self.env, partner_id=self.partner.id)
        self.assertIsInstance(result, list)
        refs = [o["ref"] for o in result]
        self.assertIn(self.order.name, refs)
        for item in result:
            for k in ("ref", "stage", "partner_name"):
                self.assertIn(k, item)

    def test_get_order_status(self):
        status = self.tools.get_order_status(self.env, order_id=self.order.id)
        for k in ("stage", "mos", "bottleneck", "blocker",
                  "next_action", "install_due", "readiness_score", "version"):
            self.assertIn(k, status)

    def test_get_order_line(self):
        line = self.order.order_line[0]
        result = self.tools.get_order_line(
            self.env, order_id=self.order.id, line_id=line.id)
        for k in ("sku", "variant_name", "qty", "attributes", "retail", "channel", "flags"):
            self.assertIn(k, result)
        self.assertEqual(result["qty"], 1)

    def test_get_order_line_rejects_cross_partner_line(self):
        # Make a second partner with their own order
        other = self.env["res.partner"].create({"name": "Other Partner"})
        product = self.env["product.product"].search([], limit=1)
        their_order = self.env["sale.order"].create({
            "partner_id": other.id,
            "order_line": [(0, 0, {
                "product_id": product.id, "product_uom_qty": 1})],
        })
        their_line = their_order.order_line[0]
        # Calling get_order_line with mismatched line_id should error
        with self.assertRaises(Exception):
            self.tools.get_order_line(
                self.env, order_id=self.order.id, line_id=their_line.id)
```

- [ ] **Step 4: Implement the three read tools.**

Overwrite `addons/southbrook_hermes/tools/read_tools.py`:

```python
# SPDX-License-Identifier: LGPL-3.0-only
"""Read tools — list_my_orders, get_order_status, get_order_line, etc.

All read tools rely on Odoo record rules for ACL. The persona context is
provided by the JWT; the controller dispatches with `env(user=portal_user)`
so record rules naturally exclude data the partner shouldn't see.
"""
from odoo.exceptions import MissingError, UserError

from .decorator import hermes_tool


@hermes_tool(
    personas=["trade_partner", "sales_rep"],
    tier="T0", scope="own",
    description="List the orders visible to the current partner.",
)
def list_my_orders(env, partner_id: int):
    orders = env["sale.order"].search(
        [("partner_id", "=", partner_id)], order="date_order desc", limit=50)
    return [
        {
            "ref": o.name,
            "stage": o.state,
            "partner_name": o.partner_id.name,
            "install_due": (o.commitment_date.isoformat()
                            if o.commitment_date else None),
        }
        for o in orders
    ]


@hermes_tool(
    personas=["trade_partner", "sales_rep"],
    tier="T0", scope="own_order",
    description=(
        "Return the production status of a specific order, including stage, "
        "MO count, bottleneck work center, top blocker, next best action."),
)
def get_order_status(env, order_id: int):
    order = env["sale.order"].browse(order_id)
    try:
        order.check_access_rights("read")
        order.check_access_rule("read")
    except Exception:
        raise MissingError("Order not visible to this user.")
    # Kitchen Job lookup is best-effort — older orders may have none yet.
    kj = env["project.task"].sudo().search(
        [("sale_order_id", "=", order.id)], limit=1)
    return {
        "stage": order.state,
        "mos": _count_mos_for_order(env, order),
        "bottleneck": (kj.southbrook_current_bottleneck_wc.name
                       if kj and getattr(kj, "southbrook_current_bottleneck_wc", False)
                       else None),
        "blocker": (kj.southbrook_top_blocker if kj else None),
        "next_action": (kj.southbrook_next_best_action if kj else None),
        "install_due": (kj.date_deadline.isoformat()
                        if kj and kj.date_deadline else None),
        "readiness_score": (kj.southbrook_readiness_score if kj else None),
        "version": getattr(order, "southbrook_version", 1),
    }


def _count_mos_for_order(env, order):
    """Best-effort count of MOs linked to this order's lines."""
    line_ids = order.order_line.ids
    return env["mrp.production"].sudo().search_count(
        [("sale_order_line_id", "in", line_ids)])


@hermes_tool(
    personas=["trade_partner", "sales_rep"],
    tier="T0", scope="own_order",
    description="Return the configured detail of a single order line.",
)
def get_order_line(env, order_id: int, line_id: int):
    order = env["sale.order"].browse(order_id)
    try:
        order.check_access_rights("read")
        order.check_access_rule("read")
    except Exception:
        raise MissingError("Order not visible to this user.")
    line = order.order_line.filtered(lambda l: l.id == line_id)
    if not line:
        raise UserError(
            f"Line {line_id} does not belong to order {order.name} "
            f"or is not visible to this user.")
    return {
        "sku": line.product_id.default_code or "",
        "variant_name": line.product_id.name,
        "qty": line.product_uom_qty,
        "attributes": {
            v.attribute_id.name: v.name
            for v in line.product_id.product_template_attribute_value_ids
        },
        "retail": line.price_unit,
        "channel": line.price_subtotal,
        "flags": [],
    }
```

- [ ] **Step 5: Register the new tests.**

Modify `tests/__init__.py`:

```python
from . import test_tool_decorator
from . import test_read_tools
```

- [ ] **Step 6: Commit.**

```bash
git add addons/southbrook_hermes/
git commit -m "feat(hermes): @hermes_tool decorator + registry + read tools batch 1"
```

---

### Task 4: Read tools batch 2 + get_os_section

**Files:**
- Modify: `addons/southbrook_hermes/tools/read_tools.py` (append)
- Modify: `addons/southbrook_hermes/tests/test_read_tools.py` (append)

- [ ] **Step 1: Append the failing tests.**

Append to `test_read_tools.py`:

```python
@tagged("post_install", "-at_install", "southbrook", "hermes")
class TestReadToolsBatch2(TransactionCase):
    def setUp(self):
        super().setUp()
        from odoo.addons.southbrook_hermes.tools import read_tools  # noqa
        self.tools = read_tools

    def test_get_os_section_returns_charter(self):
        result = self.tools.get_os_section(self.env, slug="00_charter")
        for k in ("slug", "body", "version"):
            self.assertIn(k, result)
        self.assertEqual(result["slug"], "00_charter")

    def test_get_os_section_missing(self):
        with self.assertRaises(Exception):
            self.tools.get_os_section(self.env, slug="no_such_slug_anywhere")

    def test_list_my_kitchen_projects_returns_list(self):
        # Partner with no projects — should return empty list, not raise
        partner = self.env["res.partner"].create({"name": "Empty Partner"})
        result = self.tools.list_my_kitchen_projects(
            self.env, partner_id=partner.id)
        self.assertEqual(result, [])

    def test_list_my_recommendations(self):
        partner = self.env["res.partner"].create({"name": "Rec Partner"})
        result = self.tools.list_my_recommendations(
            self.env, partner_id=partner.id)
        self.assertIsInstance(result, list)
```

- [ ] **Step 2: Append the six tool functions.**

Append to `addons/southbrook_hermes/tools/read_tools.py`:

```python
@hermes_tool(
    personas=["trade_partner", "sales_rep"],
    tier="T0", scope="own",
    description="List kitchen projects visible to this partner.",
)
def list_my_kitchen_projects(env, partner_id: int):
    Project = env["sb.kitchen.project"] if "sb.kitchen.project" in env else None
    if Project is None:
        return []
    projects = Project.sudo().search(
        [("partner_id", "=", partner_id)], order="create_date desc")
    return [
        {
            "ref": p.name,
            "stage": getattr(p, "state", None),
            "option_count": len(p.option_ids) if hasattr(p, "option_ids") else 0,
            "selected": next(
                (o.name for o in getattr(p, "option_ids", [])
                 if getattr(o, "is_selected", False)), None),
        }
        for p in projects
    ]


@hermes_tool(
    personas=["trade_partner", "sales_rep"],
    tier="T0", scope="own_order",
    description="Return options + approval status of a kitchen project.",
)
def get_kitchen_project(env, project_id: int):
    Project = env["sb.kitchen.project"] if "sb.kitchen.project" in env else None
    if Project is None:
        raise MissingError("Kitchen projects not available on this instance.")
    project = Project.browse(project_id)
    try:
        project.check_access_rights("read")
        project.check_access_rule("read")
    except Exception:
        raise MissingError("Project not visible to this user.")
    return {
        "options": [
            {"name": o.name, "is_selected": getattr(o, "is_selected", False)}
            for o in getattr(project, "option_ids", [])
        ],
        "approval_status": getattr(project, "approval_status", None),
        "drawings_url": getattr(project, "drawings_url", None),
    }


@hermes_tool(
    personas=["trade_partner", "sales_rep"],
    tier="T0", scope="own_order",
    description="Return install schedule + risk flag for an order.",
)
def get_install_schedule(env, order_id: int):
    order = env["sale.order"].browse(order_id)
    try:
        order.check_access_rights("read")
    except Exception:
        raise MissingError("Order not visible to this user.")
    return {
        "date": (order.commitment_date.isoformat()
                 if order.commitment_date else None),
        "dispatch": getattr(order, "delivery_status", None),
        "risk_flag": "unknown",
        "risk_reason": None,
    }


@hermes_tool(
    personas=["trade_partner", "sales_rep"],
    tier="T0", scope="own_order",
    description="Return the quote PDF URL + expiry for an order.",
)
def get_quote_pdf_url(env, order_id: int):
    order = env["sale.order"].browse(order_id)
    try:
        order.check_access_rights("read")
    except Exception:
        raise MissingError("Order not visible to this user.")
    base_url = env["ir.config_parameter"].sudo().get_param("web.base.url", "")
    return {
        "pdf_url": (f"{base_url}/my/orders/{order.id}?report_type=pdf"
                    if base_url else None),
        "valid_until": (order.validity_date.isoformat()
                        if order.validity_date else None),
    }


@hermes_tool(
    personas=["trade_partner", "sales_rep"],
    tier="T0", scope="own",
    description="List Hermes recommendations awaiting this partner's approval.",
)
def list_my_recommendations(env, partner_id: int):
    Rec = env.get("southbrook.hermes.recommendation")
    if Rec is None:
        return []
    recs = Rec.sudo().search(
        [("requesting_partner_id", "=", partner_id),
         ("state", "in", ("draft", "ready_for_review"))], order="create_date desc")
    return [
        {
            "rec_id": r.id,
            "type": getattr(r, "recommendation_type", None),
            "summary": getattr(r, "summary", "") or "",
            "state": r.state,
        }
        for r in recs
    ]


@hermes_tool(
    personas=["trade_partner", "sales_rep", "mfg_manager"],
    tier="T0", scope="global",
    description=(
        "Return the body and current version of a named OS section "
        "(e.g., '02_catalog', '07_partner_faq')."),
)
def get_os_section(env, slug: str):
    Section = env["southbrook.os.section"].sudo()
    section = Section.search([("slug", "=", slug)], limit=1)
    if not section:
        raise MissingError(f"OS section '{slug}' not found.")
    return {
        "slug": section.slug,
        "name": section.name,
        "version": section.version,
        "source": section.source,
        "body": section.body,
    }
```

- [ ] **Step 3: Commit.**

```bash
git add addons/southbrook_hermes/
git commit -m "feat(hermes): read tools batch 2 + get_os_section"
```

---

### Task 5: T0 / T1 write tools

**Files:**
- Modify: `addons/southbrook_hermes/tools/write_tools.py`
- Create: `addons/southbrook_hermes/tests/test_write_tools.py`
- Modify: `addons/southbrook_hermes/tests/__init__.py`

- [ ] **Step 1: Write the failing tests.**

Create `addons/southbrook_hermes/tests/test_write_tools.py`:

```python
# addons/southbrook_hermes/tests/test_write_tools.py
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "hermes")
class TestWriteTools(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create({
            "name": "Hermes Write Test Partner",
            "email": "hermes_write@example.com",
        })
        product = self.env["product.product"].search([], limit=1)
        if not product:
            self.skipTest("No products")
        self.order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": product.id, "product_uom_qty": 1,
            })],
        })
        from odoo.addons.southbrook_hermes.tools import write_tools  # noqa
        self.tools = write_tools

    def test_post_internal_note(self):
        result = self.tools.post_internal_note(
            self.env, record_model="sale.order", record_id=self.order.id,
            content="Hermes-posted note from test.")
        self.assertTrue(result["ok"])
        self.assertIn(
            "Hermes-posted note", self.order.message_ids[0].body)

    def test_schedule_followup_activity(self):
        from datetime import date, timedelta
        due = (date.today() + timedelta(days=3)).isoformat()
        result = self.tools.schedule_followup_activity(
            self.env, order_id=self.order.id,
            summary="Confirm delivery window", due_date=due)
        self.assertTrue(result["ok"])
        self.assertTrue(self.order.activity_ids)

    def test_schedule_followup_activity_rejects_past_date(self):
        from datetime import date, timedelta
        past = (date.today() - timedelta(days=1)).isoformat()
        with self.assertRaises(Exception):
            self.tools.schedule_followup_activity(
                self.env, order_id=self.order.id,
                summary="X", due_date=past)
```

(Note: `send_spec_pdf_email` is not unit-tested because it would actually send an email. It's exercised by integration tests in Plan B2.)

- [ ] **Step 2: Implement the write tools.**

Overwrite `addons/southbrook_hermes/tools/write_tools.py`:

```python
# SPDX-License-Identifier: LGPL-3.0-only
"""Write tools — T0 (note posting), T1 (email/activity)."""
import datetime

from odoo.exceptions import UserError

from .decorator import hermes_tool


@hermes_tool(
    personas=["trade_partner", "sales_rep", "mfg_manager"],
    tier="T0", scope="own",
    description=(
        "Post an internal note on a record the caller can access. "
        "Used for 'log my preference' or 'remind me later' use cases."),
)
def post_internal_note(env, record_model: str, record_id: int, content: str):
    allowed_models = ("sale.order", "project.task", "southbrook.hermes.question")
    if record_model not in allowed_models:
        raise UserError(
            f"Hermes can't post notes on '{record_model}'. "
            f"Allowed: {', '.join(allowed_models)}.")
    record = env[record_model].browse(record_id)
    record.check_access_rights("write")
    record.check_access_rule("write")
    msg = record.message_post(body=content, message_type="comment",
                               subtype_xmlid="mail.mt_note")
    return {"ok": True, "message_id": msg.id}


@hermes_tool(
    personas=["trade_partner", "sales_rep"],
    tier="T1", scope="own_order",
    description=(
        "Resend the spec sheet PDF for this order to the requesting partner's "
        "own email address. No customer or third party recipient allowed."),
)
def send_spec_pdf_email(env, order_id: int):
    order = env["sale.order"].browse(order_id)
    order.check_access_rights("read")
    order.check_access_rule("read")
    template = env.ref(
        "sale.email_template_edi_sale", raise_if_not_found=False)
    if not template:
        raise UserError("Standard sale email template not available.")
    template.send_mail(order.id, force_send=False, email_values={
        "email_to": env.user.email or order.partner_id.email,
    })
    return {"ok": True, "sent_to": env.user.email or order.partner_id.email}


@hermes_tool(
    personas=["trade_partner", "sales_rep", "mfg_manager"],
    tier="T1", scope="own",
    description=(
        "Schedule a follow-up activity (to-do) on the caller's user for the "
        "given order. Due date must be today or later."),
)
def schedule_followup_activity(env, order_id: int, summary: str, due_date: str):
    parsed_date = datetime.date.fromisoformat(due_date)
    if parsed_date < datetime.date.today():
        raise UserError("Activity due_date must be today or in the future.")
    order = env["sale.order"].browse(order_id)
    order.check_access_rights("read")
    activity_type = env.ref("mail.mail_activity_data_todo")
    activity = env["mail.activity"].create({
        "res_id": order.id,
        "res_model_id": env["ir.model"]._get("sale.order").id,
        "activity_type_id": activity_type.id,
        "summary": summary,
        "date_deadline": due_date,
        "user_id": env.user.id,
    })
    return {"ok": True, "activity_id": activity.id}
```

- [ ] **Step 3: Register the test.**

Modify `tests/__init__.py`:

```python
from . import test_write_tools
```

- [ ] **Step 4: Commit.**

```bash
git add addons/southbrook_hermes/
git commit -m "feat(hermes): T0 + T1 write tools — note posting, spec email, activity"
```

---

### Task 6: T2 propose_recommendation tool

**Files:**
- Modify: `addons/southbrook_hermes/tools/write_tools.py` (append)
- Modify: `addons/southbrook_hermes/tests/test_write_tools.py` (append)

- [ ] **Step 1: Append the failing test.**

Append to `test_write_tools.py`:

```python
@tagged("post_install", "-at_install", "southbrook", "hermes")
class TestProposeRecommendation(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create({
            "name": "T2 Test Partner",
        })
        from odoo.addons.southbrook_hermes.tools import write_tools  # noqa
        self.tools = write_tools

    def test_propose_recommendation_creates_draft(self):
        Rec = self.env["southbrook.hermes.recommendation"]
        before = Rec.search_count([])
        result = self.tools.propose_recommendation(
            self.env, partner_id=self.partner.id,
            type="request_revision",
            payload={"order_id": 1, "change": "swap door style"},
            summary="Test draft recommendation",
        )
        self.assertTrue(result["ok"])
        after = Rec.search_count([])
        self.assertEqual(after, before + 1)
        rec = Rec.browse(result["rec_id"])
        self.assertEqual(rec.state, "draft")

    def test_propose_recommendation_rejects_disallowed_type_for_trade_partner(self):
        # Trade partners can only request: request_revision,
        # request_install_reschedule, request_clarification.
        with self.assertRaises(Exception):
            self.tools.propose_recommendation(
                self.env, partner_id=self.partner.id,
                type="apply_cut_spec_override",
                payload={}, summary="Trying to force a cut-spec change",
                persona="trade_partner",
            )
```

- [ ] **Step 2: Append the tool function.**

Append to `addons/southbrook_hermes/tools/write_tools.py`:

```python
_TRADE_PARTNER_ALLOWED_TYPES = (
    "request_revision",
    "request_install_reschedule",
    "request_clarification",
)


@hermes_tool(
    personas=["trade_partner", "sales_rep", "mfg_manager"],
    tier="T2", scope="own",
    description=(
        "Create a draft southbrook.hermes.recommendation for human review. "
        "The actual business mutation only happens when an approver clicks "
        "Approve. For trade-partner persona, only request_revision, "
        "request_install_reschedule, and request_clarification types are "
        "allowed."),
)
def propose_recommendation(env, partner_id: int, type: str, payload: dict,
                            summary: str, persona: str = "trade_partner"):
    if persona == "trade_partner" and type not in _TRADE_PARTNER_ALLOWED_TYPES:
        raise UserError(
            f"Trade partners cannot propose '{type}' recommendations. "
            f"Allowed types: {', '.join(_TRADE_PARTNER_ALLOWED_TYPES)}.")
    Rec = env["southbrook.hermes.recommendation"]
    rec = Rec.sudo().create({
        "requesting_partner_id": partner_id,
        "recommendation_type": type,
        "payload_json": payload if isinstance(payload, str) else _to_json(payload),
        "summary": summary,
        "state": "draft",
    })
    return {"ok": True, "rec_id": rec.id, "summary": summary}


def _to_json(obj):
    import json
    return json.dumps(obj, default=str)
```

**Note:** the `southbrook.hermes.recommendation` model already exists (Fabio v0). Some field names — `requesting_partner_id`, `payload_json` — may differ from what's currently shipped. The implementer must verify the field names by reading `addons/southbrook_hermes/models/hermes_recommendation.py` first, and adapt the create dict to match the actual model fields. If field names differ, prefer the existing model's names (don't rename the model).

- [ ] **Step 3: Commit.**

```bash
git add addons/southbrook_hermes/
git commit -m "feat(hermes): T2 propose_recommendation tool with trade-partner type guard"
```

---

### Task 7: Hermes proxy controller — `/hermes/v1/ask`

**Files:**
- Create: `addons/southbrook_hermes/controllers/hermes_proxy.py`
- Modify: `addons/southbrook_hermes/controllers/__init__.py`
- Create: `addons/southbrook_hermes/tests/test_hermes_proxy.py`
- Modify: `addons/southbrook_hermes/tests/__init__.py`

This is the entry point the browser hits. v1.0 of B1 mints the JWT, posts to the sidecar, streams the response back. Because B2 (the sidecar) doesn't exist yet, this controller's POST-to-sidecar step short-circuits to a stub response in B1 — the JWT mint and persona resolution paths are exercised. B2 hooks up the real downstream call.

- [ ] **Step 1: Write failing tests.**

Create `addons/southbrook_hermes/tests/test_hermes_proxy.py`:

```python
# addons/southbrook_hermes/tests/test_hermes_proxy.py
import json

from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install", "southbrook", "hermes", "-standard")
class TestHermesProxy(HttpCase):
    def test_unauthenticated_rejected(self):
        resp = self.url_open("/hermes/v1/ask", data="{}",
                              headers={"Content-Type": "application/json"})
        # auth='user' → portal+ users only. Anonymous is 401/403.
        self.assertIn(resp.status_code, (401, 403, 404))

    def test_authenticated_portal_user_gets_stub_answer(self):
        # Log in as the demo portal user — same one Fabio v0 tests use.
        self.authenticate("portal", "portal")
        resp = self.url_open(
            "/hermes/v1/ask", data=json.dumps({"q": "where is my kitchen?"}),
            headers={"Content-Type": "application/json"})
        # B1: stub response. B2 will replace this with sidecar streaming.
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("stub", data)  # B1 marker — B2 removes this
        self.assertIn("jwt_iat_seen", data)
```

- [ ] **Step 2: Implement the proxy controller.**

Create `addons/southbrook_hermes/controllers/hermes_proxy.py`:

```python
# SPDX-License-Identifier: LGPL-3.0-only
"""POST /hermes/v1/ask — the browser entry point for Hermes."""
import json
import logging

from odoo import http
from odoo.exceptions import AccessError
from odoo.http import request

from ..utils import jwt_helper

_logger = logging.getLogger(__name__)


class HermesProxyController(http.Controller):

    @http.route("/hermes/v1/ask", type="http", auth="user",
                methods=["POST"], csrf=False)
    def ask(self, **kw):
        try:
            body = json.loads(request.httprequest.data or b"{}")
        except json.JSONDecodeError:
            return self._json_response({"error": "invalid_json"}, status=400)

        try:
            persona = jwt_helper.resolve_persona(request.env.user)
        except AccessError as e:
            return self._json_response(
                {"error": "forbidden", "detail": str(e)}, status=403)

        tier = jwt_helper.tier_for_persona(persona)
        partner_id = request.env.user.partner_id.id
        token = jwt_helper.mint_jwt(
            request.env, tenant="southbrook", persona=persona,
            partner_id=partner_id, tier=tier,
            extra={"order_id": body.get("order_id")})
        # B1: stub the downstream call. B2 will POST `token + body` to the
        # sidecar and stream the response.
        claims = jwt_helper.verify_jwt(request.env, token)
        stub_answer = (
            f"(Stub answer — sidecar not yet wired.) Question received: "
            f"'{body.get('q', '')}'.")
        return self._json_response({
            "stub": True,
            "answer": stub_answer,
            "persona": persona,
            "tier": tier,
            "jwt_iat_seen": claims["iat"],
        }, status=200)

    def _json_response(self, payload, status=200):
        return request.make_response(
            json.dumps(payload),
            headers=[("Content-Type", "application/json")],
            status=status,
        )
```

- [ ] **Step 3: Register the controller.**

Modify `addons/southbrook_hermes/controllers/__init__.py`:

```python
from . import hermes_proxy
```

(Append — keep any existing imports.)

- [ ] **Step 4: Register the test.**

Modify `tests/__init__.py`:

```python
from . import test_hermes_proxy
```

- [ ] **Step 5: Commit.**

```bash
git add addons/southbrook_hermes/
git commit -m "feat(hermes): /hermes/v1/ask proxy controller — JWT mint, stub answer"
```

---

### Task 8: Tools API controller — registry pull + dispatch

**Files:**
- Create: `addons/southbrook_hermes/controllers/hermes_tools_api.py`
- Modify: `addons/southbrook_hermes/controllers/__init__.py`
- Create: `addons/southbrook_hermes/tests/test_hermes_tools_api.py`
- Modify: `addons/southbrook_hermes/tests/__init__.py`

The sidecar pulls the tool registry once at boot via `GET /api/hermes/tools`, then calls individual tools via `POST /api/hermes/tools/<slug>`. Both routes verify the same JWT format the proxy mints.

- [ ] **Step 1: Write failing tests.**

Create `addons/southbrook_hermes/tests/test_hermes_tools_api.py`:

```python
# addons/southbrook_hermes/tests/test_hermes_tools_api.py
import json

from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install", "southbrook", "hermes", "-standard")
class TestHermesToolsApi(HttpCase):
    def setUp(self):
        super().setUp()
        # Ensure the JWT secret has a real value (not the placeholder)
        self.env["ir.config_parameter"].sudo().set_param(
            "southbrook_hermes.jwt_secret",
            "test_secret_long_enough_for_hs256",
        )
        from odoo.addons.southbrook_hermes.utils import jwt_helper
        self.token = jwt_helper.mint_jwt(
            self.env, tenant="southbrook", persona="trade_partner",
            partner_id=1, tier="T0+T1")

    def test_registry_unauth_rejected(self):
        resp = self.url_open("/api/hermes/tools")
        self.assertIn(resp.status_code, (400, 401, 403))

    def test_registry_with_jwt_lists_tools(self):
        resp = self.url_open(
            "/api/hermes/tools",
            headers={"Authorization": f"Bearer {self.token}"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("tools", data)
        slugs = [t["slug"] for t in data["tools"]]
        for required in ["list_my_orders", "get_order_status", "get_os_section"]:
            self.assertIn(required, slugs)

    def test_dispatch_get_os_section(self):
        resp = self.url_open(
            "/api/hermes/tools/get_os_section",
            data=json.dumps({"slug": "00_charter"}),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["slug"], "00_charter")

    def test_dispatch_unknown_tool_404(self):
        resp = self.url_open(
            "/api/hermes/tools/no_such_tool",
            data="{}",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            })
        self.assertEqual(resp.status_code, 404)
```

- [ ] **Step 2: Implement the controller.**

Create `addons/southbrook_hermes/controllers/hermes_tools_api.py`:

```python
# SPDX-License-Identifier: LGPL-3.0-only
"""GET /api/hermes/tools + POST /api/hermes/tools/<slug>.

The Hermes sidecar fetches the registry once at startup and dispatches
individual tool calls back through this controller. Every call is JWT-bearer
authenticated; the JWT's `persona` + `tier` claims gate which tools the
caller can see and call.
"""
import json
import logging

from odoo import http
from odoo.http import request

from ..tools import decorator
from ..utils import jwt_helper

_logger = logging.getLogger(__name__)


class HermesToolsApiController(http.Controller):

    @http.route("/api/hermes/tools", type="http", auth="public",
                methods=["GET"], csrf=False)
    def registry(self, **kw):
        claims = self._verify(request)
        if isinstance(claims, http.Response):
            return claims  # error response
        tools = decorator.registry_for_persona(
            claims["persona"], claims["tier"])
        return self._json({"tenant": claims["tenant"], "tools": tools})

    @http.route("/api/hermes/tools/<slug>", type="http", auth="public",
                methods=["POST"], csrf=False)
    def dispatch(self, slug, **kw):
        claims = self._verify(request)
        if isinstance(claims, http.Response):
            return claims
        fn = decorator.get_tool_function(slug)
        if fn is None:
            return self._json({"error": "unknown_tool", "slug": slug}, status=404)
        # Verify the caller's persona is allowed for this tool
        meta = next(
            (t for t in decorator.TOOL_REGISTRY if t["slug"] == slug), None)
        if claims["persona"] not in meta["personas"]:
            return self._json(
                {"error": "not_allowed_for_persona"}, status=403)
        allowed_tiers = set(claims["tier"].split("+"))
        if meta["tier"] not in allowed_tiers:
            return self._json(
                {"error": "tier_required",
                 "required_tier": meta["tier"]}, status=403)
        try:
            args = json.loads(request.httprequest.data or b"{}")
        except json.JSONDecodeError:
            return self._json({"error": "invalid_json"}, status=400)
        # Look up the partner's user record for record-rule scoping
        partner = request.env["res.partner"].sudo().browse(claims["partner_id"])
        user = partner.user_ids[:1] or request.env.user
        env_with_user = request.env(user=user.id)
        try:
            result = fn(env_with_user, **args)
        except Exception as e:
            _logger.exception("Tool %s raised", slug)
            return self._json(
                {"error": "tool_exception", "detail": str(e),
                 "tool": slug}, status=500)
        return self._json(result)

    def _verify(self, req):
        auth = req.httprequest.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return self._json(
                {"error": "missing_bearer_token"}, status=401)
        token = auth[len("Bearer "):].strip()
        try:
            return jwt_helper.verify_jwt(request.env, token)
        except Exception as e:
            return self._json(
                {"error": "invalid_token", "detail": str(e)}, status=401)

    def _json(self, payload, status=200):
        return request.make_response(
            json.dumps(payload, default=str),
            headers=[("Content-Type", "application/json")],
            status=status,
        )
```

- [ ] **Step 3: Register the controller.**

Modify `controllers/__init__.py`:

```python
from . import hermes_proxy
from . import hermes_tools_api
```

- [ ] **Step 4: Register the test.**

Modify `tests/__init__.py`:

```python
from . import test_hermes_tools_api
```

- [ ] **Step 5: Commit.**

```bash
git add addons/southbrook_hermes/
git commit -m "feat(hermes): /api/hermes/tools registry + dispatch with persona ACL"
```

---

### Task 9: Conversation log API — POST `/api/hermes/conversation/log`

**Files:**
- Create: `addons/southbrook_hermes/controllers/hermes_conversation_api.py`
- Modify: `addons/southbrook_hermes/controllers/__init__.py`
- Modify: `addons/southbrook_hermes/models/hermes_question.py` (add class-level `log_conversation` helper)
- Create: `addons/southbrook_hermes/tests/test_hermes_conversation_api.py`
- Modify: `addons/southbrook_hermes/tests/__init__.py`

The sidecar POSTs the completed Q/A pair here after each turn so it persists alongside Fabio v0's existing question records.

- [ ] **Step 1: Write the failing test.**

Create `addons/southbrook_hermes/tests/test_hermes_conversation_api.py`:

```python
# addons/southbrook_hermes/tests/test_hermes_conversation_api.py
import json

from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install", "southbrook", "hermes", "-standard")
class TestHermesConversationApi(HttpCase):
    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_param(
            "southbrook_hermes.jwt_secret",
            "test_secret_long_enough_for_hs256",
        )
        from odoo.addons.southbrook_hermes.utils import jwt_helper
        self.token = jwt_helper.mint_jwt(
            self.env, tenant="southbrook", persona="trade_partner",
            partner_id=1, tier="T0+T1")

    def test_log_persists_question_and_answer(self):
        Q = self.env["southbrook.hermes.question"]
        before = Q.search_count([])
        resp = self.url_open(
            "/api/hermes/conversation/log",
            data=json.dumps({
                "question": "Where is my kitchen?",
                "answer": "Stub answer for test.",
                "scope": "external",
            }),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            })
        self.assertEqual(resp.status_code, 200)
        after = Q.search_count([])
        self.assertEqual(after, before + 1)

    def test_log_rejects_invalid_jwt(self):
        resp = self.url_open(
            "/api/hermes/conversation/log",
            data="{}",
            headers={
                "Authorization": "Bearer not_a_real_jwt",
                "Content-Type": "application/json",
            })
        self.assertEqual(resp.status_code, 401)
```

- [ ] **Step 2: Add a class-level helper on the question model.**

Modify `addons/southbrook_hermes/models/hermes_question.py` to add a class method at the bottom of the `southbrook.hermes.question` class (find the existing class and append):

```python
    @api.model
    def log_conversation(self, *, question, answer, partner_id, scope="external"):
        """Persist a Q+A turn from the sidecar."""
        return self.create({
            "question": question,
            "answer": answer,
            "scope": scope,
            "state": "answered",
            "requesting_partner_id": partner_id,
        })
```

(Note: field names — `question`, `answer`, `scope`, `state`, `requesting_partner_id` — are based on the existing Fabio v0 model. The implementer MUST verify these match the actual model file and adapt if any name differs.)

- [ ] **Step 3: Implement the controller.**

Create `addons/southbrook_hermes/controllers/hermes_conversation_api.py`:

```python
# SPDX-License-Identifier: LGPL-3.0-only
"""POST /api/hermes/conversation/log — sidecar persists Q+A turns."""
import json

from odoo import http
from odoo.http import request

from ..utils import jwt_helper


class HermesConversationApiController(http.Controller):

    @http.route("/api/hermes/conversation/log", type="http", auth="public",
                methods=["POST"], csrf=False)
    def log(self, **kw):
        auth = request.httprequest.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return self._json(
                {"error": "missing_bearer_token"}, status=401)
        try:
            claims = jwt_helper.verify_jwt(request.env, auth[len("Bearer "):].strip())
        except Exception as e:
            return self._json(
                {"error": "invalid_token", "detail": str(e)}, status=401)
        try:
            body = json.loads(request.httprequest.data or b"{}")
        except json.JSONDecodeError:
            return self._json({"error": "invalid_json"}, status=400)
        Q = request.env["southbrook.hermes.question"].sudo()
        rec = Q.log_conversation(
            question=body.get("question", ""),
            answer=body.get("answer", ""),
            partner_id=claims["partner_id"],
            scope=body.get("scope", "external"),
        )
        return self._json({"ok": True, "question_id": rec.id})

    def _json(self, payload, status=200):
        return request.make_response(
            json.dumps(payload, default=str),
            headers=[("Content-Type", "application/json")],
            status=status,
        )
```

- [ ] **Step 4: Register the controller + test.**

Modify `controllers/__init__.py`:

```python
from . import hermes_conversation_api
```

Modify `tests/__init__.py`:

```python
from . import test_hermes_conversation_api
```

- [ ] **Step 5: Commit.**

```bash
git add addons/southbrook_hermes/
git commit -m "feat(hermes): POST /api/hermes/conversation/log persistence endpoint"
```

---

### Task 10: Deploy + smoke test

**Files:** none new.

- [ ] **Step 1: Set the real JWT secret on production via SSH.**

Generate a strong secret and write it via Odoo's CLI:

```bash
SECRET=$(openssl rand -hex 32)
ssh -o ProxyCommand="cloudflared access ssh --hostname %h" admin@ssh.odooiq.com \
  "/share/CACHEDEV3_DATA/.qpkg/container-station/bin/system-docker exec southbrook-odoo \
  bash -c 'echo \"env[\\\"ir.config_parameter\\\"].sudo().set_param(\\\"southbrook_hermes.jwt_secret\\\", \\\"$SECRET\\\"); env.cr.commit()\" | odoo shell -d southbrook --no-http' 2>&1 | tail -5"
echo "Stored secret (first 8 chars): ${SECRET:0:8}…  — save this somewhere safe."
```

(The script keeps the rest of the secret out of any persistent log.)

- [ ] **Step 2: Deploy the addon.**

```bash
./scripts/deploy_to_qnap.sh southbrook_hermes 2>&1 | tail -20
```

Expected: `cold upgrade OK`, `live /web/login → 200`.

If the deploy mode change at script-time means `DEPLOY_VIA=tunnel` isn't available anymore, run it as the script currently expects.

- [ ] **Step 3: Hard-restart the container so the OWL bundle picks up the new code.**

```bash
ssh -o ProxyCommand="cloudflared access ssh --hostname %h" admin@ssh.odooiq.com \
  '/share/CACHEDEV3_DATA/.qpkg/container-station/bin/system-docker restart southbrook-odoo' 2>&1
```

Wait for `/web/login` to return 200.

- [ ] **Step 4: Smoke test the tools API via curl.**

Mint a token by calling `/hermes/v1/ask` with a known portal session, then use the returned JWT to call `/api/hermes/tools` and verify the registry is non-empty.

Alternatively, mint a JWT directly from a brief Odoo shell:

```bash
ssh -o ProxyCommand="cloudflared access ssh --hostname %h" admin@ssh.odooiq.com \
  "/share/CACHEDEV3_DATA/.qpkg/container-station/bin/system-docker exec southbrook-odoo \
  bash -c 'echo \"from odoo.addons.southbrook_hermes.utils import jwt_helper; \
print(jwt_helper.mint_jwt(env, tenant=\\\"southbrook\\\", persona=\\\"trade_partner\\\", \
partner_id=1, tier=\\\"T0+T1\\\", ttl_seconds=120))\" | odoo shell -d southbrook --no-http' 2>&1 | tail -3"
```

Copy the token, then:

```bash
TOKEN=<paste>
curl -s -H "Authorization: Bearer $TOKEN" \
  https://southbrookcabinetry.space/api/hermes/tools | \
  python3 -c "import sys, json; d = json.load(sys.stdin); print('tenant:', d['tenant']); print('tool count:', len(d['tools'])); print('slugs:', sorted(t['slug'] for t in d['tools']))"
```

Expected: tenant=`southbrook`, 12 tools listed, slugs include `list_my_orders`, `get_order_status`, `get_os_section`, `propose_recommendation`.

- [ ] **Step 5: Smoke test the dispatch of `get_os_section` via curl.**

```bash
curl -s -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"slug": "00_charter"}' \
  https://southbrookcabinetry.space/api/hermes/tools/get_os_section
```

Expected: JSON with `slug: 00_charter`, `body: <markdown>`, `version: 1`.

- [ ] **Step 6: Smoke test conversation log.**

```bash
curl -s -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question":"smoke test", "answer":"smoke test answer", "scope":"external"}' \
  https://southbrookcabinetry.space/api/hermes/conversation/log
```

Expected: `{"ok": true, "question_id": <int>}`.

Verify in the DB:

```bash
ssh -o ProxyCommand="cloudflared access ssh --hostname %h" admin@ssh.odooiq.com \
  '/share/CACHEDEV3_DATA/.qpkg/container-station/bin/system-docker exec southbrook-postgres \
  psql -U odoo -d southbrook -c "SELECT id, question, answer FROM southbrook_hermes_question ORDER BY id DESC LIMIT 1;"' 2>&1
```

- [ ] **Step 7: Tag v0.1.0 of the Hermes API surface.**

```bash
git tag -a hermes_api-v0.1.0 -m "hermes API surface — registry + dispatch + log (sidecar pending)"
```

---

## Self-review

**Spec coverage check:**
- §2.2 Hermes addon extensions: Tasks 1-9 cover utils/, tools/, controllers/. The OWL chat panel is deferred to a UI-only task in Plan B2's integration phase (the panel needs the live sidecar to be useful).
- §3 Data flow: Task 7 (proxy mints JWT) + Task 8 (tools API dispatches with JWT + record rules) + Task 9 (conversation log) wire the Odoo half of the flow. The sidecar half is Plan B2.
- §4 Personas/ACL/tiers: Task 2 (`resolve_persona`, `tier_for_persona`) + Task 3 (decorator filters by persona+tier) + Task 8 (controller enforces both).
- §6 Tool catalog v1.0 (12 tools): Tasks 3 + 4 + 5 + 6 ship all 12. Verified slug list:
  - Read (9): `list_my_orders`, `get_order_status`, `get_order_line`, `list_my_kitchen_projects`, `get_kitchen_project`, `get_install_schedule`, `get_quote_pdf_url`, `list_my_recommendations`, `get_os_section`
  - T0 write (1): `post_internal_note`
  - T1 (2): `send_spec_pdf_email`, `schedule_followup_activity`
  - T2 (1): `propose_recommendation`
  - Total: 13 (one more than the spec's 12 — the spec lumped `get_os_section` with read tools as part of the 12; the registry has 13 distinct entries because I split the OS lookup out. Acceptable — extras documented and gated.)

**Placeholder scan:** clean. The two tools (`schedule_followup_activity`, `propose_recommendation`) note that the implementer must verify existing model field names — this is a directive to verify, not a placeholder.

**Type consistency:** model + helper names consistent across tasks. `southbrook.hermes.question.log_conversation` is added in Task 9 and called from the controller in Task 9 same task. `TOOL_REGISTRY` and `registry_for_persona` consistent across decorator + tools API.

**Out of scope (for Plan B2):**
- Vercel sidecar (Next.js routes, RAG indexing, AI Gateway integration, SSE streaming).
- OWL chat panel UI (depends on sidecar for streamed answers).
- End-to-end "where is my kitchen?" smoke test through the browser.
- Real LLM call.

**Multi-tenant readiness:** the JWT already carries a `tenant` claim and the tools API endpoints already namespace by tenant in the response. When Porterly gets its own copy of `southbrook_hermes`, the path will need a rename or a query-param/prefix decision — that's a v1.x concern.

---

## What's next

After Plan B1 ships, Plan B2 (`2026-06-16-hermes-trade-partner-b2-sidecar.md`) will:
1. Scaffold the Vercel sidecar repo (Next.js, TypeScript).
2. Pull and index the RAG corpus from `/southbrook/os.json`.
3. Implement `/api/hermes/ask` with SSE streaming + AI Gateway integration + tool dispatch back through `/api/hermes/tools/<slug>`.
4. Add the OWL chat panel to the Order Builder portal.
5. End-to-end smoke test from a real portal session.
