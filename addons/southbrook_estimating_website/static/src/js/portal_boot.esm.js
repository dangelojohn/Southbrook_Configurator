/** @odoo-module **/
/*
 * SPDX-License-Identifier: LGPL-3.0-only
 *
 * Track 2 commit 2 — empty OWL OrderBuilder mount.
 *
 * Bootstraps the OWL component tree on /my/southbrook/order-builder
 * pages. The portal template ships a `<div id="order_builder_root">`
 * with placeholder content (so the page reads correctly without JS).
 * This script:
 *
 *   1. Finds the mount-point div at DOMContentLoaded.
 *   2. Reads the order id + name from its data attributes.
 *   3. Mounts the <OrderBuilder/> OWL component into it, replacing
 *      the placeholder.
 *
 * <OrderBuilder/> in commit 2 is intentionally minimal — a single
 * heading + a click counter — so we can verify:
 *   • The portal asset bundle loaded OWL successfully.
 *   • Reactivity (useState) works on portal routes the same way it
 *     does in the backend.
 *   • The mount-point div is reachable + props are passed through.
 *
 * Commit 3+ replaces this with the real component tree per
 * docs/southbrook_owl_mockup.html.
 */
import { Component, mount, useState, xml } from "@odoo/owl";

// Inline template — Phase 3 polish moves this to an XML asset file
// alongside additional components.
const TEMPLATE = xml`
    <div class="o_southbrook_owl_root">
        <h3 class="o_owl_heading">
            OWL is alive — Order Builder root mounted.
        </h3>
        <p class="o_owl_subhead">
            Order id: <strong t-esc="props.orderId || 'none'"/>
            <t t-if="props.orderName">
                · <strong t-esc="props.orderName"/>
            </t>
        </p>
        <p>
            Reactivity check — click the button.
            <br/>
            <button class="btn btn-outline-primary o_owl_counter_btn"
                    t-on-click="onClick">
                Clicks: <t t-esc="state.count"/>
            </button>
        </p>
        <p class="o_owl_status text-muted">
            Phase 2 Track 2 commit 2 of 14. Next commit adds palette /
            type tokens; commit 5 wires the reactive store to the
            JSON-RPC controller; commits 6-13 build out the
            <code>&lt;HeaderStrip/&gt;</code> →
            <code>&lt;FooterActions/&gt;</code> component tree per the
            mockup.
        </p>
    </div>
`;

class OrderBuilder extends Component {
    static template = TEMPLATE;
    static props = {
        orderId: { type: String, optional: true },
        orderName: { type: String, optional: true },
    };

    setup() {
        this.state = useState({ count: 0 });
    }

    onClick() {
        this.state.count++;
    }
}

/**
 * Mount the OrderBuilder root into its placeholder div.
 *
 * Idempotent — guards against double-mount if the script runs
 * twice (browser bfcache, hot reload).
 */
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
    // Module loaded after DOMContentLoaded — mount immediately.
    queueMicrotask(mountOrderBuilder);
}
