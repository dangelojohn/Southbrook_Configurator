# Feature Flags — Close-the-Loop Audit (P1–P8)

Every behavioral change introduced by the configurator → particle-intelligence
loop audit ships behind a feature flag, defaulting **OFF**. This file is the
canonical index. Per-module README files cite the same flag with the same
key, default, and effect text.

The flag mechanism is `ir.config_parameter` (string-typed); the convention is
`<module>.<flag_name>` and a truthy value is one of `1` / `true` / `yes` / `on`
(case-insensitive). Anything else (or missing) reads as off.

Enable per-environment via Odoo Settings → Technical → System Parameters,
or via shell:

```python
self.env["ir.config_parameter"].sudo().set_param(
    "southbrook_premium_orchestration.auto_emit_cutlist", "True")
```

## Inventory

| # | Key | Default | Effect when ON | Audit task |
|---|-----|---------|----------------|------------|
| 1 | `southbrook_premium_orchestration.auto_emit_cutlist` | `False` | On `sale.order.action_confirm`, after the project.task spine is created, every configurable kitchen-cabinet line whose MO has been resolved gets exactly one `sb.production.package` (cutlist + hardware) auto-emitted via `sb.production.package.build_from_order_line`. Idempotent per `sale.order.line` via the new `sale_order_line_id` back-reference. | P1 |

(P2, P3, P5, P6, P7, P8 add their own entries as they land.)

## Rollback

For each P-task: setting the flag to `False` returns behaviour to the
audited baseline. No destructive migrations, no schema deletions. If the
flag itself is unset, the default is OFF. The per-task commit can also
be `git revert`-ed cleanly because every change is additive.
