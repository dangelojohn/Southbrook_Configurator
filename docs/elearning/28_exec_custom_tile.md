---
course: 28
chapter: 28.5
title: Exec Dashboard Module — Adding a Custom Tile
duration: 8
audience: Developer building a new exec tile
prereqs: Lessons 28.1-28.4
custom_modules: southbrook_exec_dashboard
---

# Exec Dashboard Module — Adding a Custom Tile

## The 4-step pattern

1. Write the compute method
2. Register the tile via XML
3. Test the compute output
4. Verify in the UI

## A worked example: "Top 3 Customers by Revenue (Last 30 Days)"

### Step 1: Compute method

In a custom addon (e.g. `southbrook_exec_dashboard_custom`):

```python
class SouthbrookMiEngine(models.AbstractModel):
    _inherit = "southbrook.mi.engine"
    
    @api.model
    def get_top3_customers_tile(self):
        thirty_days_ago = fields.Date.today() - relativedelta(days=30)
        
        # Aggregate revenue by customer
        self.env.cr.execute("""
            SELECT partner_id, SUM(amount_total) AS revenue
            FROM account_move
            WHERE move_type = 'out_invoice'
              AND date >= %s
              AND state = 'posted'
            GROUP BY partner_id
            ORDER BY revenue DESC
            LIMIT 3
        """, (thirty_days_ago,))
        
        rows = self.env.cr.fetchall()
        partner_dict = {
            p.id: p.name
            for p in self.env["res.partner"].browse([r[0] for r in rows])
        }
        
        top3 = [{
            "partner_id": r[0],
            "name": partner_dict.get(r[0], f"Partner {r[0]}"),
            "revenue": r[1],
        } for r in rows]
        
        total = sum(t["revenue"] for t in top3)
        
        return {
            "title": "Top 3 Customers (30d)",
            "value": f"${total:,.0f}",
            "subtitle": ", ".join(t["name"] for t in top3),
            "color": "green",  # Always positive signal
            "list": top3,
            "drill_action": "sale.action_orders",
            "drill_domain": [
                ("partner_id", "in", [t["partner_id"] for t in top3]),
            ],
        }
```

### Step 2: Tile XML

```xml
<record id="tile_top3_customers" model="southbrook.exec_dashboard.tile">
    <field name="name">Top 3 Customers (30d)</field>
    <field name="tile_code">top3_customers</field>
    <field name="tile_type">list</field>
    <field name="sequence">25</field>
    <field name="compute_method">southbrook.mi.engine.get_top3_customers_tile</field>
    <field name="refresh_interval_min">60</field>
    <field name="visible_to_group_ids" eval="[(4, ref('exec_dashboard_user'))]"/>
</record>
```

### Step 3: Test the compute

```python
# In odoo shell
env["southbrook.mi.engine"].get_top3_customers_tile()
# Should return the dict
```

### Step 4: Refresh the dashboard

```bash
docker exec southbrook-odoo kill -HUP 1  # if new public routes
```

Visit /exec/morning; the new tile should appear.

## Tile sequence ordering

Tiles render in `sequence` ascending. Standard sequence ranges:

| Range | Purpose |
|---|---|
| 1-9 | Top row (cash flow / revenue / today plan) |
| 10-29 | Operational health |
| 30-49 | Risk surface |
| 50-79 | Hermes-flagged + executive actions |
| 80+ | Custom tiles |

Pick a sequence that places your tile correctly.

## Visibility

`visible_to_group_ids` controls who sees the tile:
- Empty m2m = visible to all dashboard users
- One or more groups = visible only to members

Useful for:
- Finance tiles → visible only to finance group
- Quality tiles → visible to QC + Plant GM only
- HR tiles → visible to HR group

## Refresh interval choice

| Interval | Use case |
|---|---|
| 5 min | Real-time operational tiles (NCRs, breakdowns) |
| 15-30 min | Hourly trend tiles |
| 60 min | Daily-relevant tiles (top customers, AR) |
| 24h | Strategic tiles (week-over-week trends) |

Longer intervals reduce server load; shorter intervals trade
freshness for cost.

## Common mistakes + how to recover

- **"Tile doesn't appear after install"** — visibility group
  doesn't include your user. Check group membership.
- **"Compute method returns nothing"** — method may have raised
  exception silently caught. Test in odoo shell.
- **"drill_action XML id wrong"** — typo. Use `Settings →
  Technical → Actions` to find correct id.
- **"Tile not refreshing"** — cron skipping due to recent
  compute. Force refresh via cog → Refresh.

## Quiz

**Q1.** Tile shows on /exec/morning but says "no data." Diagnose?

> Compute method may be failing silently. Run from odoo shell;
> if error, fix the method.

**Q2.** New tile at sequence 5 — placement?

> Top row. Among the cash/revenue tiles.

**Q3.** Visible_to_group_ids m2m empty. Who sees it?

> All users with dashboard access.

**Q4.** Tile refresh_interval = 1440. How often computes?

> Once per day. Cron runs every 5 min but only computes when
> `last_computed_at < now - 1440 min`.

**Q5.** Tile XML loads but tile_code conflicts with existing.
Effect?

> XML id collision (use unique id). `tile_code` is just a string;
> can be duplicate (would be a logic bug but not error).
