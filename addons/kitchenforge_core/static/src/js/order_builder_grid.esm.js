/** @odoo-module **/
/* KitchenForge multi-cabinet Order Builder grid — Phase-2 stub.

   Replaces the per-line OCA configurator wizard with a single OWL grid
   where each row is a cabinet zone and the salesperson tweaks attributes
   inline. This is the surface the SAMI brief (~/southbrook-v19cr/CLAUDE.md
   §2.2) names `order_builder.esm.js`.

   This stub registers the component and a minimal mount point; the actual
   grid is being shipped in southbrook_configurator_ux phase 2. Keeping it
   here as a thin client lets kitchenforge_core declare the asset
   dependency now and swap implementations without breaking views.
*/

import { Component, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";

class KitchenForgeOrderBuilderGrid extends Component {
    static template = xml`
        <div class="o_kitchenforge_grid_stub p-3 text-muted">
            <h5>KitchenForge Order Builder</h5>
            <p>Multi-cabinet inline grid (Phase 2). Edit zones directly on the
               sale order line list below until this surface ships.</p>
        </div>
    `;
    static props = {};
}

registry.category("actions").add(
    "kitchenforge_order_builder",
    KitchenForgeOrderBuilderGrid,
);
