# Southbrook Configurator — End-to-End Map

**Updated 2026-06-03 (Step 0 of the post-walkthrough triage).**
Read-only orientation doc; no behaviour was changed in this pass.

The three JSON-RPC endpoints behind the customer-facing OWL configurator
on `/shop/<slug>` are all defined on
[`addons/southbrook_configurator_ux/controllers/main.py`](../addons/southbrook_configurator_ux/controllers/main.py).
They share one `auth='public'` mode, all return JSON dicts via Odoo's
`type='json'` JSON-RPC envelope, and all operate against a single
`product.config.session` per (user, template) which the OCA
`product_configurator` module owns.

## 1 · Route → method → model

| Route (POST) | Controller method | Underlying calls | Notes |
|---|---|---|---|
| `/southbrook/api/configurator/state` | `SouthbrookConfiguratorAPI.configurator_state` (main.py:140) | `product.template.attribute_line_ids` traversal; `_get_or_create_session()` calls `product.config.session.search` / `.create` | Read-only. Builds the entire OWL component's initial payload (product card, attribute groups, value chips, existing picks). |
| `/southbrook/api/configurator/select` | `SouthbrookConfiguratorAPI.configurator_select` (main.py:339) | `product.config.session.update_config(attr_val_dict)`; `product.config.session.values_available(check_val_ids=…)`; reads `session.price`, `session.weight` | Stateful. Sends the COMPLETE current pick set on every call; the controller fills in `attribute_id: []` for any attribute the client omitted so OCA `update_config` clears the old value. |
| `/southbrook/api/configurator/commit` | `SouthbrookConfiguratorAPI.configurator_commit` (main.py:459) | `product.config.session.create_get_variant()` → returns `product.product`; `sale.order.search`/`create` → `sale.order.line.create` → `line.product_id_change()`; `product.config.session.action_confirm(product_id=variant)` | Writes. Public users get `login_required` before any side-effect. Session must be `state='draft'` — second commit returns `session_locked`. Successful commit returns `redirect: /my/southbrook/order-builder/<order_id>`. |

### Model touchpoints

- **`product.config.session`** (OCA `product_configurator/models/product_config.py`) — central state. Methods used: `update_config`, `values_available`, `create_get_variant`, `action_confirm`. Stored fields read: `price`, `weight`, `value_ids`, `state`, `product_tmpl_id`, `user_id`. The session is created in `_get_or_create_session()` (main.py:304) using the request user (or `base.public_user` for anonymous visitors).
- **`product.config.line`** (OCA) — the rule engine the `select` endpoint queries via `values_available`. Box Material + Door Style rules live in `southbrook_configurator_ux/models/rule_completion.py` (one config.line per template × value with a per-value "Series allows V" domain). Width → Door Count + Family Subtype → Soft-Close rules live statically in `southbrook_estimating/data/config_rules.xml`.
- **`southbrook.cut.spec`** (`southbrook_plm/models/southbrook_cut_spec.py`) — engineering snapshot. The active spec at `sale.order.action_confirm()` is captured onto each line via `sale.order.line._capture_southbrook_version_snapshots()` (southbrook_plm/models/sale_order_line.py:113). **NOT called from the configurator commit path**; only fires when the customer confirms the whole order. See P4 gap #2 below.
- **`sale.order.line`** — extended in two addons:
  - `website_product_configurator/models/sale_order.py` adds `config_session_id` (Many2one to `product.config.session`). Wired automatically when adding via the OCA cart route (`_cart_update_order_line` reads it from kwargs). **NOT written by the Southbrook commit controller** — see P4 gap #1.
  - `southbrook_plm/models/sale_order_line.py` adds `southbrook_cut_spec_version_id` (Many2one) and `southbrook_bom_version` (Integer). Both readonly + populated by `_capture_southbrook_version_snapshots()`.

## 2 · How `state` builds its response

Sequence in `configurator_state` (main.py:140–298):

1. **Validate input** — `product_tmpl_id` must be a positive int that resolves to an existing `product.template` with `config_ok=True`. Returns `{ok: false, error: <code>}` otherwise.
2. **Resolve session** — `_get_or_create_session(tmpl)` searches for the user's most-recent `draft` session for this template, or sudo-creates one. Anonymous visitors land sessions under `base.public_user`; OCA's cleanup cron sweeps stale public sessions on a TTL.
3. **Build `attributes` map** — iterates `tmpl.attribute_line_ids` in attribute sequence. For each attribute_line, iterates `line.value_ids` (the per-template subset, not the global value pool), reading `product.template.attribute.value` rows for `price_extra` + `html_color` overrides. Output shape:
   ```
   {"<attribute_id>": {
       name, display_type, sequence, required,
       values: [{id, name, sequence, price_extra, html_color, disabled: false}, ...]
   }}
   ```
   Note: `disabled` is always emitted as `false` here — the live disable state comes from `select`'s `disabled_value_ids`, not `state`.
4. **Build `groups` array** — maps the hardcoded `ATTRIBUTE_GROUPS` list (main.py:119–124) to live attribute IDs. Any attribute on the template that isn't named in the groups list goes into a trailing `"Other"` group so it stays visible. Current groups: `Size & Layout` / `Series & Materials` / `Finish & Construction` / `Hardware & Add-ons`.
5. **Read existing selections** — `session.value_ids.ids` — lets a returning customer pick up where they left off.
6. **Compute display SKU** — walks `tmpl.product_variant_ids.sorted("id")` for the first variant with a `default_code`; falls back to `tmpl.default_code`. With `create_variant='dynamic'` on the Southbrook attributes, variants are spawned on demand, so this can be empty until a configuration is committed.
7. **Resolve currency** — `request.env['website'].get_current_website().currency_id`, fallback to `request.env.company.currency_id`.

**Response shape** (success path):
```
{
  ok: true,
  product: {tmpl_id, sku, name, list_price, currency:{symbol,position,decimal_places,name}},
  session_id: int,
  base_price: float,
  groups: [{title, attribute_ids:[int]}, ...],
  attributes: {"<aid>": {name, display_type, sequence, required, values:[...]}, ...},
  selected_value_ids: [int]
}
```

## 3 · How `select` computes `disabled_value_ids` and `price`

Sequence in `configurator_select` (main.py:339–447):

1. **Validate input** — `session_id` int, `value_ids` array of ints. Reject with `bad_session_id` or `value_ids_must_be_list` otherwise.
2. **Authorize session** — `_authorize_session()` (main.py:598) sudo-browses by id, ensures `session.user_id.id == request.env.user.id`. Returns error dict on mismatch.
3. **Check session state** — `session.state != 'draft'` → `session_locked` error.
4. **Build attribute → value dict** — flat `value_ids` list becomes `{attribute_id: value_id}` by browsing each value to read its attribute. Unknown values silently skipped. Attributes on the template that aren't in the new picks get `attribute_id: []` so OCA's `update_config` clears the old value rather than carrying it forward (main.py:402–408).
5. **Apply picks** — `session.sudo().update_config(attr_val_dict)`. Wrapped in try/except for `UserError` / `ValidationError` → returns `{ok: false, error: 'rule_blocked', message: …}`. This is where the OCA rule engine raises if the picks violate a `product.config.line` rule the engine can't auto-clear.
6. **Compute disabled set**:
   - `all_val_ids` = every value any attribute_line on this template exposes.
   - `available_ids` = `session.sudo().values_available(check_val_ids=all_val_ids)` — OCA's per-value evaluation against the active config.lines for this template (see [OCA `values_available` source](../addons/product_configurator/models/product_config.py) line 1377).
   - `disabled_ids = all_val_ids - available_ids`, returned sorted.
   - Try/except: if `values_available` raises (rare; usually a malformed rule), falls back to `available_ids = all_val_ids` so nothing appears disabled rather than blowing up the whole pick.
7. **Read price + weight** — `session.price` (OCA stored field, summed from base + price_extras), `session.weight` (where present — defaults to `0.0`).

**Response shape** (success):
```
{
  ok: true,
  selected_value_ids: [int],     # session.value_ids.ids after update_config
  price: float,
  weight: float,
  disabled_value_ids: [int],
  warnings: []                    # reserved
}
```

## 4 · What `commit` writes — field by field

Sequence in `configurator_commit` (main.py:459–593):

1. **Public-user gate** — `request.env.user._is_public()` → `{ok: false, error: 'login_required', login_url: '/web/signup'}`. The OWL component renders a sign-in CTA in response.
2. **Validate session_id + authorize** — same `_authorize_session` as `select`.
3. **Session state check** — `state != 'draft'` → `session_locked`.
4. **Materialise variant** — `variant = session.sudo().create_get_variant()` (OCA method on `product.config.session`). Internally calls `validate_configuration` first — raises `ValidationError` on missing required attribute or rule violation. The controller wraps that as `{ok: false, error: 'validation_failed', message: …}`. **Server-side gate** that prevents committing without Box Material etc. — see P4 gap #4.
5. **Resolve target sale.order**:
   - If `order_id` provided: browse, verify `partner_id` matches the user's partner, verify `state in (draft, sent)`. Errors: `bad_order_id` / `order_not_found` / `order_forbidden` / `order_locked`.
   - If not: `sale.order.search([('partner_id','=',user.partner_id.id),('state','=','draft')])` — newest first. If none, `SaleOrder.create({"partner_id": user.partner_id.id})`.
6. **Create the line** — `sale.order.line.create({...})` with these fields **only**:

   | Field on `sale.order.line` | Value written | Notes |
   |---|---|---|
   | `order_id` | `order.id` | Always set. |
   | `product_id` | `variant.id` | The just-materialised `product.product`. |
   | `product_uom_qty` | `1` | Customer changes qty in Order Builder. |
   | `config_session_id` | **❌ NOT WRITTEN** | Field exists (from `website_product_configurator`); committer should set it = `session.id`. **P4 gap #1.** |
   | `southbrook_cut_spec_version_id` | **❌ NOT WRITTEN** | Captured by `_capture_southbrook_version_snapshots()` from `sale.order.action_confirm()`, never from configurator-commit. **P4 gap #2.** |
   | `southbrook_bom_version` | **❌ NOT WRITTEN** | Same as cut-spec version. **P4 gap #2.** |

7. **Hydrate the line** — `line.product_id_change()` is called if the method exists (it does on Southbrook's v19 stack). Populates `name`, `price_unit`, `product_uom` from the variant.
8. **Lock the session** — `session.sudo().action_confirm(product_id=variant)`. Sets `state='done'` + `product_id` link. **Non-fatal**: action_confirm failure is logged at WARNING but doesn't roll back the variant + line. (The cleanup cron handles abandoned sessions.)
9. **Return redirect** — `{ok: true, variant_id, order_id, order_line_id, redirect: '/my/southbrook/order-builder/<order_id>'}`.

### Variant-side write check

`create_get_variant()` materialises a `product.product` whose `default_code` is computed by OCA's `_get_config_name()` from the template + selected values. In practice this is often left **empty** on the variant row (P4 gap #3), because OCA's `_get_config_name` on a freshly-created variant only writes the variant's `name`, not its `default_code`. The Southbrook configurator UI auto-generates a display SKU client-side from `SKU_ATTR_NAMES = ["Width", "Series", "Finish"]` — that client SKU is never written back to the variant.

## 5 · Persistence gaps confirmed against staging trace

Verified against the trace the user supplied (template 38, config values `[389,395,403,407,415,417,420,425,428,433,440]`, resulting in order S00501 / line 310 / variant 232 / price 370):

| Gap | Observation on the live record | Fix shape (Priority 4) |
|---|---|---|
| #1 | `sale.order.line.config_session_id` = `False` | Set `config_session_id=session.id` in the `create()` payload at main.py:565. |
| #2 | `southbrook_cut_spec_version_id` = `False`, `southbrook_bom_version` = `0` | Call `line._capture_southbrook_version_snapshots()` after creating the line, OR thread the cut-spec snapshot directly into the create payload. |
| #3 | `product.product.default_code` = `False` on variant 232 | Compute the client-side SKU server-side post-`create_get_variant`, then `variant.default_code = sku`. |
| #4 | Front-end disables required attribute (Box Material) chips while still demanding the field — UI dead-end; server happily accepts the pick when posted directly | Two-part: (a) front-end disable-logic fix (P1), and (b) keep `create_get_variant`'s `validate_configuration` as a backstop so any future client bypass still rejects an incomplete config. |

The third part of the commit gap (variant `default_code`) is the same "default_code blanks on multi-variant template" v19 gotcha that the `state` endpoint works around via its `for variant in tmpl.product_variant_ids.sorted("id")` fallback (main.py:265). The commit endpoint should similarly write the computed SKU explicitly so the variant row carries it from the moment of creation.

## 6 · Things the commit endpoint already gets right (must preserve)

- **Public user gate**: anonymous visitors get `login_required` with a `/web/signup?redirect=<current_path>` URL before any write attempt.
- **Session ownership check**: `_authorize_session` rejects cross-user session access (main.py:611).
- **Session locking**: a second commit on the same session returns `session_locked` (main.py:517–520) — verified anti-replay guard.
- **Order locking**: an attempt to commit to a confirmed/cancelled order returns `order_locked` with the state surfaced.
- **Order Builder redirect**: success response carries `redirect: /my/southbrook/order-builder/<order_id>` per the Phase-2 cart-target decision (Q-locked: "A — Order Builder, not website_sale cart").

## 7 · Files referenced

- `addons/southbrook_configurator_ux/controllers/main.py` — the three configurator routes (`SouthbrookConfiguratorAPI`) + the four import routes (`SouthbrookImportAPI`, out of scope here).
- `addons/southbrook_configurator_ux/models/rule_completion.py` — current Box Material + Door Style rule generator.
- `addons/southbrook_configurator_ux/models/catalog_expansion.py` — the 40 common-category templates that share the rules.
- `addons/southbrook_estimating/data/config_rules.xml` — Width → Door Count + Family-Subtype → Soft-Close rules (static).
- `addons/product_configurator/models/product_config.py` — OCA `product.config.session` model: `values_available` at line 1377; `compute_domain` at line 34; `validate_domains_against_sels` at line 1340.
- `addons/website_product_configurator/models/sale_order.py` — adds `config_session_id` field + cart-add wiring.
- `addons/southbrook_plm/models/sale_order_line.py` — adds `southbrook_cut_spec_version_id` + `southbrook_bom_version` + `_capture_southbrook_version_snapshots()`.
- `addons/southbrook_plm/models/southbrook_cut_spec.py` — the cut-spec model + `_get_active()` resolver.
