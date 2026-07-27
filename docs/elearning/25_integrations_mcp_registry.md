---
course: 25
chapter: 25.4
title: Integrations Module — MCP Tool Registry
duration: 9
audience: Developer extending the MCP server-side tool registry
prereqs: Lesson 25.1; Hermes tool decorator familiarity (Course 13)
custom_modules: southbrook_integrations
---

# Integrations Module — MCP Tool Registry

## The two registries

Southbrook ships TWO tool registries with similar names but
different purposes:

| Aspect | Hermes registry | MCP registry |
|---|---|---|
| Where | `southbrook_hermes.tools.decorator` | `southbrook_integrations.mcp_tool` |
| How declared | `@hermes_tool(...)` decorator | `ir.model.data` row |
| Where stored | Process-level Python list | Database table |
| Who calls | Hermes sidecar (trade partners) | Self-hosted Qwen LLM (future VPS) |
| Auth | JWT with persona claims | `X-Api-Key` |
| Tier model | T0 / T1 / T2 | All read-only in v1 |
| Args binding | Persona-claim-bound | Caller-supplied (with whitelist) |

The two are deliberately separate — don't conflate.

## MCP tool model

```python
class SouthbrookIntegrationsMcpTool(models.Model):
    _name = "southbrook.integrations.mcp_tool"
    _description = "MCP Server Tool (read-only scoped query)"
```

Fields:

```python
name             = fields.Char(required=True, index=True)
description      = fields.Text()
category         = fields.Selection([("read", "Read"),
                                     ("search", "Search"),
                                     ("write", "Write")],
                                    default="read")
model_id         = fields.Many2one("ir.model", required=True)
model_name       = fields.Char(related="model_id.model", store=True)
domain_json      = fields.Text(default="[]")
read_fields_json = fields.Text(default="[]")
enabled          = fields.Boolean(default=True)
rate_limit_per_min = fields.Integer(default=60)
```

## Tool invocation

```python
def invoke(self, args_json):
    """Execute a sandboxed read against the configured model+domain+fields."""
    self.ensure_one()
    
    if not self.enabled:
        raise AccessError(_("Tool disabled"))
    if self.category == "write":
        raise AccessError(_("Write tools not enabled in v1"))
    
    args = json.loads(args_json) if args_json else {}
    domain = self._parse_domain()
    
    extra_domain = args.get("extra_domain", [])
    if extra_domain:
        domain = domain + list(extra_domain)
    
    field_names = self._parse_fields()
    self._validate_read_fields_exist(field_names)
    
    limit = int(args.get("limit", 50))
    offset = int(args.get("offset", 0))
    
    Target = self.env[self.model_name].sudo()
    records = Target.search(domain, limit=limit, offset=offset)
    rows = records.read(field_names) if field_names else records.read()
    
    return {
        "schema": "southbrook.mcp.invoke.v1",
        "tool": self.name,
        "model": self.model_name,
        "rows": rows,
        "count": len(rows),
    }
```

## HTTP endpoint

```python
@http.route("/mcp/v1/invoke/<string:slug>", type="json",
            auth="api_key", methods=["POST"], csrf=False)
def invoke(self, slug, **payload):
    tool = request.env["southbrook.integrations.mcp_tool"]\
        .sudo().search([("name", "=", slug)], limit=1)
    if not tool:
        raise NotFound()
    
    # Rate limit check
    self._check_rate_limit(tool, request.api_key_id)
    
    args_json = json.dumps(payload.get("args", {}))
    result = tool.invoke(args_json)
    
    # Log
    request.env["southbrook.integrations.mcp_call_log"].sudo().create({
        "tool_id": tool.id,
        "api_key_id": request.api_key_id,
        "args_json": args_json,
        "result_size": result["count"],
    })
    
    return result
```

## Seeding tools via XML

```xml
<record id="mcp_tool_list_open_sos" model="southbrook.integrations.mcp_tool">
    <field name="name">list_open_sales_orders</field>
    <field name="description">List sales orders in draft or sale state</field>
    <field name="category">read</field>
    <field name="model_id" ref="sale.model_sale_order"/>
    <field name="domain_json">[("state", "in", ["draft", "sale"])]</field>
    <field name="read_fields_json">
        ["name", "partner_id", "amount_total", "state"]
    </field>
</record>
```

After install, Qwen can call `POST /mcp/v1/invoke/list_open_sales_orders`
and get JSON rows back.

## Field whitelist validation

```python
def _validate_read_fields_exist(self, field_names):
    if not field_names:
        return
    Target = self.env[self.model_name]
    unknown = [f for f in field_names if f not in Target._fields]
    if unknown:
        raise UserError(
            _("Unknown fields: %s") % ", ".join(unknown))
```

Prevents a typo'd field from returning silent empty results.

## Common mistakes + how to recover

- **"Tool returns empty rows even though data exists"** — domain
  filter too restrictive. Test with empty extra_domain to see all
  records of that type.
- **"Tool returns 'AccessError: Tool disabled'"** — `enabled = False`.
  Enable in the tool record.
- **"Field whitelist error on a valid field"** — field renamed in
  newer Odoo. Update the read_fields_json.

## Quiz

**Q1.** Hermes tool registry vs MCP tool registry — main
distinction?

> Hermes is persona-bound process-level; MCP is data-driven
> read-only. Different consumers, different auth.

**Q2.** v1 MCP supports write category?

> No — `category = "write"` raises AccessError. Reserved for v2
> when ACL story is decided.

**Q3.** Rate limit — per-tool or per-API-key?

> Per-tool (`rate_limit_per_min` field). Per-API-key is enforced
> at the HTTP layer separately.

**Q4.** New MCP tool: list MOs in progress. XML seed?

> Create with `model_id = mrp.model_mrp_production`,
> `domain_json = [("state", "in", ["confirmed", "progress"])]`,
> appropriate `read_fields_json`.

**Q5.** Self-hosted Qwen calls /mcp/v1/invoke/xyz. If xyz doesn't
exist?

> 404 NotFound. Tool slug not in the registry.
