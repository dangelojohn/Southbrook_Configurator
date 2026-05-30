/** @odoo-module **/
/*
 * SPDX-License-Identifier: LGPL-3.0-only
 *
 * Track 2 commit 5 (2026-05-30) — reactive store wired to JSON-RPC.
 *
 * Replaces the commit-2 click-counter OrderBuilder with a real
 * reactive store. On mount, fires a JSON-RPC call to
 * /southbrook/api/order/<id> (T2C4 controller) and exposes the
 * normalised payload (order header, lines, zones) on state.
 *
 * Commit 6 reads state.order to render the HeaderStrip (5 cells).
 * Commits 7-12 add the remaining components from the mockup. Each
 * later component will read its slice from the same reactive
 * state — no extra RPC.
 *
 * State shape mirrors the T2C4 payload + a couple of UI flags:
 *
 *   state = {
 *     loading: bool,                 // RPC in flight
 *     error:   string | null,        // human-readable failure message
 *     order:   {id, name, channel, ...} | null,
 *     lines:   [...],
 *     zones:   [...],
 *     ui: {
 *       current_tab: "lines",        // commit 8 wires the tab bar
 *       selected_line_id: null,      // commit 9 wires selection
 *     },
 *   };
 */
import { Component, mount, onMounted, useState, xml } from "@odoo/owl";

// ----------------------------------------------------------------------
// JSON-RPC fetch helper. Pure fetch — no Odoo service dependency so
// the script works on the public portal context where the backend
// service registry isn't available.
// ----------------------------------------------------------------------

async function rpcJsonCall(url, params = {}) {
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
    if (!res.ok) {
        throw new Error(`HTTP ${res.status} ${res.statusText}`);
    }
    const json = await res.json();
    if (json.error) {
        const msg = json.error.data?.message
            || json.error.message
            || "RPC error";
        throw new Error(msg);
    }
    return json.result;
}

// ----------------------------------------------------------------------
// Inline template. Phase 3 polish splits each section into its own
// component file under static/src/js/components/.
// ----------------------------------------------------------------------

const TEMPLATE = xml`
    <div class="o_southbrook_owl_root">

        <!-- Loading -->
        <div t-if="state.loading" class="o_owl_loading_card">
            <p class="o_owl_status">Loading order…</p>
        </div>

        <!-- Error -->
        <div t-elif="state.error" class="o_owl_error_card">
            <strong>Couldn't load this order.</strong>
            <p t-esc="state.error"/>
            <button class="btn btn-outline-secondary o_owl_retry_btn"
                    t-on-click="_onRetry">
                Retry
            </button>
        </div>

        <!-- Empty / no id -->
        <div t-elif="!state.order" class="o_owl_empty_card">
            <strong>No order selected.</strong>
            <p>
                Append an order id to the URL — for example
                <code>/my/southbrook/order-builder/234</code>.
            </p>
        </div>

        <!-- Loaded -->
        <div t-else="" class="o_owl_loaded">
            <h3 class="o_owl_heading">
                <t t-esc="state.order.name"/>
                <span class="o_owl_partner_inline">
                    · <t t-esc="state.order.partner_name"/>
                    <span t-if="state.order.via" class="o_owl_via">
                        (<t t-esc="state.order.via"/>)
                    </span>
                </span>
            </h3>

            <div class="o_owl_channel_badge"
                 t-att-class="'o_owl_channel_' + state.order.channel_css">
                <t t-esc="state.order.channel_label"/>
            </div>

            <!-- Store probe — commit 6 replaces with the proper
                 HeaderStrip 5-cell component. -->
            <div class="o_owl_store_probe">
                <div class="o_owl_probe_row">
                    <span class="o_owl_probe_label">Retail subtotal</span>
                    <span class="o_owl_probe_value mono"
                          t-esc="_fmtUsd(state.order.retail_subtotal)"/>
                </div>
                <div class="o_owl_probe_row">
                    <span class="o_owl_probe_label">Channel total</span>
                    <span class="o_owl_probe_value mono"
                          t-esc="_fmtUsd(state.order.channel_total)"/>
                </div>
                <div class="o_owl_probe_row">
                    <span class="o_owl_probe_label">Savings</span>
                    <span class="o_owl_probe_value mono o_owl_savings"
                          t-esc="_fmtUsd(state.order.savings)"/>
                </div>
                <div class="o_owl_probe_row">
                    <span class="o_owl_probe_label">Lines · Zones</span>
                    <span class="o_owl_probe_value mono">
                        <t t-esc="state.order.line_count"/>
                        ·
                        <t t-esc="state.zones.length"/>
                    </span>
                </div>
            </div>

            <p class="o_owl_status">
                Reactive store wired (T2C5). Commit 6 turns this probe
                into the proper <code>&lt;HeaderStrip/&gt;</code> 5-cell
                component reading the same store slice.
            </p>
        </div>
    </div>
`;

class OrderBuilder extends Component {
    static template = TEMPLATE;
    static props = {
        orderId: { type: String, optional: true },
        orderName: { type: String, optional: true },
    };

    setup() {
        this.state = useState({
            loading: false,
            error: null,
            order: null,
            lines: [],
            zones: [],
            ui: {
                current_tab: "lines",
                selected_line_id: null,
            },
        });
        onMounted(() => this._loadOrder());
    }

    async _loadOrder() {
        const orderId = this.props.orderId;
        if (!orderId) {
            // No id in URL → render the empty-state card. Not an error.
            this.state.loading = false;
            return;
        }
        this.state.loading = true;
        this.state.error = null;
        try {
            const payload = await rpcJsonCall(
                `/southbrook/api/order/${encodeURIComponent(orderId)}`,
            );
            if (payload && payload.error) {
                this.state.error = (
                    payload.error === "forbidden"
                        ? "Access denied. This order is not visible to your account."
                        : payload.error === "not_found"
                        ? "Order not found."
                        : payload.error
                );
                return;
            }
            this.state.order = payload.order;
            this.state.lines = payload.lines || [];
            this.state.zones = payload.zones || [];
        } catch (e) {
            this.state.error = e?.message || String(e);
        } finally {
            this.state.loading = false;
        }
    }

    async _onRetry() {
        await this._loadOrder();
    }

    /**
     * USD currency formatter used by the probe block. Phase 3 polish
     * moves currency awareness into the payload (multi-currency support)
     * — for commit 5 the dollar sign is hardcoded and matches the mockup.
     */
    _fmtUsd(value) {
        if (typeof value !== "number") return "—";
        return "$" + value.toLocaleString(undefined, {
            minimumFractionDigits: 0,
            maximumFractionDigits: 0,
        });
    }
}

// ----------------------------------------------------------------------
// Bootstrap — finds the mount-point div on portal pages and mounts
// the OrderBuilder root. Idempotent against double-mount.
// ----------------------------------------------------------------------

async function mountOrderBuilder() {
    const root = document.getElementById("order_builder_root");
    if (!root || root.dataset.owlMounted === "1") return;
    root.dataset.owlMounted = "1";

    const orderId = root.dataset.orderId || "";
    const orderName = root.dataset.orderName || "";

    // Clear the placeholder so it doesn't flash beneath the OWL render.
    root.innerHTML = "";

    try {
        await mount(OrderBuilder, root, {
            props: { orderId, orderName },
        });
    } catch (err) {
        // Surface mount failures in the DOM so they're discoverable
        // without DevTools — important during scaffold verification.
        root.innerHTML =
            "<div class='alert alert-danger'>" +
            "OWL mount failed: " +
            String(err?.message || err) +
            "</div>";
        // eslint-disable-next-line no-console
        console.error("[southbrook_estimating_website] OWL mount failed:", err);
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mountOrderBuilder);
} else {
    queueMicrotask(mountOrderBuilder);
}
