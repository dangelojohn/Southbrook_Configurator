/** @odoo-module **/
//
// Phase 2 commit 2 (2026-05-31) — /kitchen-planner OWL bootstrap.
//
// Mounts the <KitchenPlanner/> component into the
// `#kitchen_planner_root` div emitted by P2C1's template. Mirrors the
// pattern in portal_boot.esm.js (T2C2 for the Order Builder).
//
// What this commit ships:
//   - rpcCall(url, params) — pure fetch + JSON-RPC envelope (same
//     helper as the Order Builder uses; duplicated to keep the two
//     bundles independent and avoid cross-imports between SPAs).
//   - <KitchenPlanner/> component — loading / error / loaded states.
//     Loaded state shows partner name + catalog item count + currency.
//     Real catalog tile rendering is P2C3; this commit proves the
//     boot loop end-to-end (mount → fetch state → render).
//   - mountKitchenPlanner() — finds the mount-point div, mounts the
//     component, sets data-owl-mounted="1" so the mount is idempotent
//     (DOMContentLoaded + queueMicrotask both fire in some Odoo
//     navigation paths).
//
// What this commit does NOT ship:
//   - Catalog tile click → add to current session (P2C3+)
//   - Attribute drawer (P2C4+)
//   - Live pricing (P2C5)
//   - "Request a Price" CTA (P2C6)
//

import { Component, mount, onMounted, useState, xml } from "@odoo/owl";

// ---------------------------------------------------------------------
// rpcCall — pure fetch + JSON-RPC envelope.
// ---------------------------------------------------------------------
async function rpcCall(url, params = {}) {
    const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            jsonrpc: "2.0",
            method: "call",
            params,
            id: Date.now(),
        }),
        credentials: "same-origin",
    });
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }
    const body = await response.json();
    if (body.error) {
        const msg = body.error.data?.message || body.error.message
            || "RPC error";
        throw new Error(msg);
    }
    return body.result;
}

// ---------------------------------------------------------------------
// KitchenPlanner — root OWL component.
// ---------------------------------------------------------------------
class KitchenPlanner extends Component {
    static template = xml`
        <div class="o_kp_planner">
            <div t-if="state.loading" class="o_kp_state o_kp_loading">
                Loading planner…
            </div>
            <div t-elif="state.error" class="o_kp_state o_kp_error">
                <strong>Could not load planner.</strong>
                <div class="o_kp_error_msg" t-esc="state.error"/>
                <button class="o_kp_retry" t-on-click="_retry">Retry</button>
            </div>
            <div t-else="" class="o_kp_state o_kp_loaded">
                <h1 class="o_kp_loaded_title">
                    Hello, <t t-esc="state.payload.user.partner_name"/>.
                </h1>
                <p class="o_kp_loaded_sub">
                    Your kitchen planner is ready.
                </p>
                <dl class="o_kp_loaded_meta">
                    <dt>Cabinets in catalog</dt>
                    <dd><t t-esc="state.payload.catalog.length"/></dd>
                    <dt>Channel</dt>
                    <dd t-esc="state.payload.user.channel"/>
                    <dt>Currency</dt>
                    <dd>
                        <t t-esc="state.payload.currency.name"/>
                        (<t t-esc="state.payload.currency.symbol"/>)
                    </dd>
                </dl>
                <p class="o_kp_loaded_foot">
                    Phase 2 commit 2 · OWL mount confirmed · 2026-05-31.
                    Tile interaction lands in commit 3+.
                </p>
            </div>
        </div>
    `;

    static props = {};

    setup() {
        this.state = useState({
            loading: true,
            error: null,
            payload: null,
        });
        onMounted(() => this._load());
    }

    async _load() {
        try {
            this.state.loading = true;
            this.state.error = null;
            const result = await rpcCall(
                "/southbrook/api/kitchen-planner/state",
                {},
            );
            this.state.payload = result;
            this.state.loading = false;
        } catch (err) {
            this.state.loading = false;
            this.state.error = err.message || String(err);
        }
    }

    _retry = () => {
        this._load();
    };
}

// ---------------------------------------------------------------------
// mountKitchenPlanner — idempotent boot.
// ---------------------------------------------------------------------
async function mountKitchenPlanner() {
    const root = document.getElementById("kitchen_planner_root");
    if (!root || root.dataset.owlMounted === "1") return;
    root.dataset.owlMounted = "1";

    // Clear the P2C1 placeholder before mounting.
    root.innerHTML = "";

    try {
        await mount(KitchenPlanner, root, {
            props: {},
            dev: false,
        });
    } catch (err) {
        // Reveal mount errors to the user — silent failure on an
        // empty white screen is worse than a visible error block.
        root.innerHTML =
            '<div class="o_kp_state o_kp_error">' +
            '<strong>Planner failed to mount.</strong>' +
            '<div class="o_kp_error_msg">' + (err.message || String(err))
            + '</div></div>';
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mountKitchenPlanner);
} else {
    queueMicrotask(mountKitchenPlanner);
}
