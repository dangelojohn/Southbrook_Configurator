/** @odoo-module **/
/*
 * SPDX-License-Identifier: LGPL-3.0-only
 *
 * 2026-07-03 T1/T2 — Order Builder "3D Design" tab.
 *
 * A portal parent that drives the standalone Configurator's KitchenCanvas
 * OWL engine (reused verbatim from southbrook_kitchen_3d_configurator's
 * canvas/* modules, now also loaded into web.assets_frontend) inside the
 * Order Builder portal SPA.
 *
 * Data model: the order's southbrook.kitchen.design (get-or-created +
 * seeded from the order's SB-SKU lines by the portal route
 * /southbrook/api/order/<id>/design-3d). The editor reads and writes its
 * OWN design, so it is self-coherent (unlike the zone-tiled read-only
 * KitchenViewport Preview). Drag-moves persist to
 * kitchen.design.line.x_position_in via .../design-3d/move — in-bounds
 * (never touches sale.order/MO; positions ride the existing design→order
 * reconcile cron).
 *
 * We deliberately do NOT reuse the backend parent kitchen_configurator.js
 * (it uses useService("action"), whose service is absent from
 * web.assets_frontend). This component is that parent's portal-safe twin.
 */
import { Component, onMounted, useState, xml } from "@odoo/owl";
import { KitchenCanvas } from "@southbrook_kitchen_3d_configurator/js/canvas/kitchen_canvas.esm";

// Plain JSON-RPC fetch — no @web service dependency, matching the portal
// context pattern used by kitchen_viewport.esm.js / portal_boot.esm.js.
async function rpcCall(url, params = {}) {
    const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            jsonrpc: "2.0",
            method: "call",
            params: params,
            id: Math.floor(Math.random() * 1e9),
        }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const j = await res.json();
    if (j.error) {
        throw new Error(j.error.data?.message || j.error.message || "RPC error");
    }
    return j.result;
}

export class KitchenDesignTab extends Component {
    static components = { KitchenCanvas };
    static template = xml`
        <div class="o_owl_design3d">
            <div class="o_owl_design3d_toolbar">
                <span class="o_owl_design3d_title">3D Design</span>
                <span class="o_owl_design3d_status"
                      t-if="state.loading">Loading…</span>
                <span class="o_owl_design3d_status text-danger"
                      t-elif="state.error" t-esc="state.error"/>
                <span class="o_owl_design3d_meta" t-else="">
                    <t t-esc="state.items.length"/> cabinets · drag to arrange
                    <t t-if="state.saving"> · saving…</t>
                </span>
            </div>
            <div class="o_owl_design3d_stage">
                <KitchenCanvas items="state.items"
                               room="state.room"
                               view="'iso'"
                               selected="state.selected"
                               onSelectItem.bind="_onSelectItem"
                               onMoveItem.bind="_onMoveItem"/>
            </div>
        </div>
    `;
    static props = {
        orderId: { type: String, optional: true },
        // Bumped by OrderBuilder after autosaves; a change re-fetches so the
        // design reseeds if the order's cabinet set changed (T1: reload).
        payloadVersion: { type: Number, optional: true },
    };

    setup() {
        this.state = useState({
            loading: true,
            error: null,
            saving: false,
            items: [],
            room: { width_in: 12, depth_in: 24, height_in: 96 },
            selected: null,
            designId: null,
        });
        this._lastPayloadVersion = this.props.payloadVersion || 0;
        onMounted(() => this._load());
    }

    async _load() {
        if (!this.props.orderId) {
            this.state.loading = false;
            this.state.error = "No order selected.";
            return;
        }
        this.state.loading = true;
        this.state.error = null;
        try {
            const payload = await rpcCall(
                `/southbrook/api/order/${encodeURIComponent(this.props.orderId)}/design-3d`,
                {},
            );
            if (payload && payload.error) {
                this.state.error = payload.error;
                return;
            }
            this.state.designId = payload.design_id;
            this.state.room = payload.room || this.state.room;
            this.state.items = payload.items || [];
        } catch (e) {
            this.state.error = e?.message || String(e);
        } finally {
            this.state.loading = false;
        }
    }

    // KitchenCanvas → cabinet clicked. Highlight (T1). A parent-level
    // Order-Lines bridge is a later tier.
    _onSelectItem(item) {
        this.state.selected = item || null;
    }

    // KitchenCanvas → cabinet dragged (X-axis). Persist to the design line
    // via the portal move route (T2). Optimistic: KitchenCanvas already
    // moved the mesh; we only persist. On failure, reload to resync.
    async _onMoveItem(payload) {
        const item = payload && payload.item;
        if (!item || !item.layout_key || !this.props.orderId) return;
        this.state.saving = true;
        try {
            const res = await rpcCall(
                `/southbrook/api/order/${encodeURIComponent(this.props.orderId)}/design-3d/move`,
                {
                    layout_key: item.layout_key,
                    x_position_in: payload.x_position_in,
                },
            );
            if (res && res.error) {
                this.state.error = res.error;
                await this._load();   // resync on server rejection
            }
        } catch (e) {
            this.state.error = e?.message || String(e);
            await this._load();
        } finally {
            this.state.saving = false;
        }
    }
}
