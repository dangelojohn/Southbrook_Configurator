---
course: 28
chapter: 28.3
title: Exec Dashboard Module — OWL View and Mobile-First Layout
duration: 7
audience: Frontend developer working on the OWL component
prereqs: Lesson 28.1, basic OWL framework familiarity
custom_modules: southbrook_exec_dashboard
---

# Exec Dashboard Module — OWL View and Mobile-First Layout

## The OWL component

```javascript
/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class ExecDashboard extends Component {
    static template = "southbrook_exec_dashboard.ExecDashboardView";
    
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ tiles: [], loading: true });
        
        onWillStart(async () => {
            await this.loadTiles();
        });
    }
    
    async loadTiles() {
        const data = await this.orm.call(
            "southbrook.exec_dashboard.tile",
            "get_dashboard_data",
            [],
        );
        this.state.tiles = data;
        this.state.loading = false;
    }
    
    async onTileClick(tile) {
        if (!tile.drill_action) return;
        this.action.doAction(tile.drill_action, {
            additionalContext: {
                search_default_filters: tile.drill_domain || [],
            },
        });
    }
}

registry.category("actions").add(
    "southbrook_exec_dashboard.exec_dashboard_view",
    ExecDashboard,
);
```

## The OWL template

```xml
<templates xml:space="preserve">
    <t t-name="southbrook_exec_dashboard.ExecDashboardView">
        <div class="o_exec_dashboard">
            <div t-if="state.loading" class="text-center">
                <i class="fa fa-spinner fa-spin"/> Loading...
            </div>
            <div t-else="" class="o_exec_dashboard_grid">
                <t t-foreach="state.tiles" t-as="tile" t-key="tile.id">
                    <div class="o_exec_tile"
                         t-attf-class="o_exec_tile_{{tile.color}}"
                         t-on-click="() =&gt; this.onTileClick(tile)">
                        <div class="o_exec_tile_title">
                            <t t-esc="tile.title"/>
                        </div>
                        <div class="o_exec_tile_value">
                            <t t-esc="tile.value"/>
                        </div>
                        <div t-if="tile.subtitle" class="o_exec_tile_subtitle">
                            <t t-esc="tile.subtitle"/>
                        </div>
                        <div t-if="tile.trend" class="o_exec_tile_sparkline">
                            <!-- sparkline component -->
                        </div>
                    </div>
                </t>
            </div>
        </div>
    </t>
</templates>
```

## Mobile-first CSS

```scss
.o_exec_dashboard {
    padding: 1rem;
    max-width: 100vw;
    
    .o_exec_dashboard_grid {
        display: grid;
        grid-template-columns: 1fr;  // single column on mobile
        gap: 1rem;
    }
    
    .o_exec_tile {
        background: var(--card-bg);
        border-radius: 8px;
        padding: 1.5rem;
        cursor: pointer;
        transition: transform 0.1s;
        
        &:hover {
            transform: translateY(-2px);
        }
        
        &.o_exec_tile_green { border-left: 4px solid #4caf50; }
        &.o_exec_tile_amber { border-left: 4px solid #ff9800; }
        &.o_exec_tile_red { border-left: 4px solid #f44336; }
        &.o_exec_tile_grey { border-left: 4px solid #9e9e9e; }
    }
    
    // Tablet
    @media (min-width: 768px) {
        .o_exec_dashboard_grid {
            grid-template-columns: 1fr 1fr;
        }
    }
    
    // Desktop
    @media (min-width: 1200px) {
        .o_exec_dashboard_grid {
            grid-template-columns: 1fr 1fr 1fr 1fr;
        }
    }
}
```

## Why mobile-first

- Owner reads it on phone over coffee
- Plant GM reads on tablet on the floor
- Desktop is the "deep dive" case, not the primary use

Designing for the smallest viewport first ensures all info is
visible everywhere.

## OWL hot reload

During development:

```bash
# Run odoo with assets in dev mode
docker exec southbrook-odoo bash -c 'odoo --dev=qweb,assets'
```

Changes to `.js`, `.xml`, `.scss` reload without full restart.

## Common mistakes + how to recover

- **"OWL template not found"** — `static.assets_backend` doesn't
  include the file. Check manifest.
- **"State not updating on click"** — OWL state must be from
  `useState`; raw object modifications don't trigger re-render.
- **"Mobile breakpoints not working"** — caching. Hard refresh.

## Quiz

**Q1.** OWL component registration — what's the category?

> `actions` (for full-page views). Registry: `registry.category("actions").add(...)`.

**Q2.** `useState` vs plain object?

> `useState` is reactive — changes trigger re-render. Plain
> object changes don't.

**Q3.** Mobile-first means CSS designed for smallest viewport
first. Why?

> Easier to scale up than down. Smartphone constraints force
> simplification; if the dashboard works on phone, desktop will
> work.

**Q4.** Click handler is `() => this.onTileClick(tile)`. Why
arrow function?

> Preserves `this` binding to the component. Without arrow,
> `this` would be undefined in the OWL event context.

**Q5.** OWL hot reload — what command?

> `--dev=qweb,assets`. Changes to assets reload without restart.
