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
// USD currency formatter — shared between OrderBuilder (probe) + the
// HeaderStrip (T2C6) + subsequent commits. Phase 3 polish moves this
// to a util module + adds multi-currency awareness based on payload.
// ----------------------------------------------------------------------

function fmtUsd(value) {
    if (typeof value !== "number") return "—";
    return "$" + value.toLocaleString(undefined, {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    });
}

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
// IllustrativeBanner — T2C7.
//
// The yellow strip that marks demo / seed numbers as not-production
// data (per OQ2 acked + commit-9 ask in southbrook_estimating Build
// Spec §9.3). Renders only when props.show is truthy.
//
// Phase 3 polish reads ir.config_parameter southbrook.seed_mode
// (already declared by southbrook_estimating data/config_parameters.xml)
// and toggles render. T2C7 hardcodes show=true so the banner is
// visible during portal scaffold review.
// ----------------------------------------------------------------------

class IllustrativeBanner extends Component {
    static template = xml`
        <div t-if="props.show" class="o_owl_illus_banner">
            <span class="o_owl_illus_pill">ILLUSTRATIVE SEED</span>
            <span class="o_owl_illus_text">
                Demo numbers — not production data. See
                <code>PUNCHLIST.md</code> OQ2 + Build Spec §9.3.
            </span>
        </div>
    `;
    static props = {
        show: { type: Boolean, optional: true },
    };
}

// ----------------------------------------------------------------------
// OrderTitlebar — T2C7.
//
// Two-column row above the StagePipeline + HeaderStrip:
//   • Left:  ← Back link + h1 title (partner name + order purpose).
//   • Right: SO ref · version · state — mono, dim. The "reference"
//            block in the mockup that anchors the order's identity.
//
// The back link target is "/my/southbrook/order-builder" (the
// no-id form which Phase 3 commit 4 turns into a dealer-orders
// list).
// ----------------------------------------------------------------------

class OrderTitlebar extends Component {
    static template = xml`
        <div class="o_owl_titlebar">
            <div class="o_owl_titlebar_lhs">
                <div class="o_owl_titlebar_crumb">
                    <a href="/my/southbrook/order-builder"
                       class="o_owl_back_link">← Back to Order Builder</a>
                </div>
                <h1 class="o_owl_titlebar_heading">
                    <t t-esc="props.order.partner_name"/>
                    <span class="o_owl_titlebar_sub">
                        · Kitchen Order
                    </span>
                </h1>
            </div>
            <div class="o_owl_titlebar_ref">
                <t t-esc="props.order.name"/>
                <t t-if="props.order.version">
                    · v<t t-esc="props.order.version"/>
                </t>
                <t t-if="props.order.state">
                    · <t t-esc="_stateLabel(props.order.state)"/>
                </t>
            </div>
        </div>
    `;
    static props = {
        order: Object,
    };

    _stateLabel(state) {
        const labels = {
            draft:  "Draft",
            sent:   "Estimating",
            sale:   "Confirmed",
            done:   "In Production",
            cancel: "Cancelled",
        };
        return labels[state] || state;
    }
}

// ----------------------------------------------------------------------
// StagePipeline — T2C7.
//
// 5 stages with clip-path arrow shapes, mapping order.state to the
// "current" position. Stages BEFORE current render as .done; the
// current stage renders as .current (walnut bg, linen text); stages
// AFTER current render as default (paper bg, dim text).
//
// Stage list lifts from Build Spec §2.2:
//   Draft → Estimating → Approval → Confirmed → In Production
//
// State → stage index mapping is heuristic until Phase 3 wires the
// real Southbrook stage field (which adds Approval as a distinct
// state). Today:
//   draft  → 0 Draft
//   sent   → 1 Estimating
//   sale   → 3 Confirmed (skips Approval — Phase 3 closes the gap)
//   done   → 4 In Production
//   cancel → -1 (renders all stages dim)
// ----------------------------------------------------------------------

class StagePipeline extends Component {
    static template = xml`
        <div class="o_owl_stages">
            <t t-foreach="STAGES" t-as="stage" t-key="stage_index">
                <div class="o_owl_stage"
                     t-att-class="{
                         'o_owl_stage_done':    stage_index &lt; currentIdx,
                         'o_owl_stage_current': stage_index === currentIdx,
                     }">
                    <t t-esc="stage"/>
                </div>
            </t>
        </div>
    `;
    static props = {
        order: Object,
    };

    STAGES = ["Draft", "Estimating", "Approval", "Confirmed", "In Production"];

    get currentIdx() {
        const map = {
            draft: 0,
            sent: 1,
            sale: 3,
            done: 4,
            cancel: -1,
        };
        const idx = map[this.props.order?.state];
        return idx === undefined ? 0 : idx;
    }
}

// ----------------------------------------------------------------------
// HeaderStrip — T2C6.
//
// The 5-cell row at the top of the OrderBuilder (per mockup §HeaderStrip):
//   1. Customer  — sky-tinted; partner name + via text + pricelist badge
//   2. Retail Subtotal
//   3. Channel Total
//   4. Savings (green accent)
//   5. Lead Time (weeks + maple offset if applicable)
//
// Reads props.order. No state of its own — pure presentation.
// ----------------------------------------------------------------------

class HeaderStrip extends Component {
    static template = xml`
        <div class="o_owl_header_strip">
            <div class="o_owl_hs_cell o_owl_hs_customer">
                <div class="o_owl_hs_label">Customer</div>
                <div class="o_owl_hs_value">
                    <t t-esc="props.order.partner_name"/>
                    <span t-if="props.order.via" class="o_owl_hs_sub">
                        (<t t-esc="props.order.via"/>)
                    </span>
                </div>
                <span class="o_owl_channel_badge"
                      t-att-class="'o_owl_channel_' + props.order.channel_css">
                    <t t-esc="props.order.channel_label"/>
                </span>
            </div>
            <div class="o_owl_hs_cell">
                <div class="o_owl_hs_label">Retail Subtotal</div>
                <div class="o_owl_hs_value mono"
                     t-esc="fmtUsd(props.order.retail_subtotal)"/>
            </div>
            <div class="o_owl_hs_cell">
                <div class="o_owl_hs_label">Channel Total</div>
                <div class="o_owl_hs_value mono"
                     t-esc="fmtUsd(props.order.channel_total)"/>
            </div>
            <div class="o_owl_hs_cell o_owl_hs_savings">
                <div class="o_owl_hs_label">Savings</div>
                <div class="o_owl_hs_value mono"
                     t-esc="fmtUsd(props.order.savings)"/>
            </div>
            <div class="o_owl_hs_cell">
                <div class="o_owl_hs_label">Lead Time</div>
                <div class="o_owl_hs_value">
                    <t t-if="props.order.lead_time_days > 0">
                        <t t-esc="Math.round(props.order.lead_time_days / 7)"/>
                        wks
                    </t>
                    <t t-else="">—</t>
                </div>
            </div>
        </div>
    `;
    static props = {
        order: Object,
    };

    // Expose the shared formatter on the component instance so the
    // template can call it via t-esc="fmtUsd(...)". OWL templates
    // resolve identifiers against `this`, so a named arrow assignment
    // works without import shenanigans.
    fmtUsd = fmtUsd;
}

// ----------------------------------------------------------------------
// OrderBuilder root template. Phase 3 polish splits each section into
// its own component file under static/src/js/components/.
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
            <!-- Chrome (T2C7) — banner + titlebar + stages. -->
            <IllustrativeBanner show="true"/>
            <OrderTitlebar order="state.order"/>
            <StagePipeline order="state.order"/>

            <!-- HeaderStrip (T2C6) — reads order header from state. -->
            <HeaderStrip order="state.order"/>

            <p class="o_owl_status">
                Chrome + HeaderStrip wired (T2C6 + T2C7). Next: TabBar
                (T2C8) and the multi-zone line grid (T2C9).
                <br/>
                Lines loaded: <strong t-esc="state.lines.length"/>
                across <strong t-esc="state.zones.length"/> zones.
            </p>
        </div>
    </div>
`;

class OrderBuilder extends Component {
    static template = TEMPLATE;
    static components = {
        IllustrativeBanner,
        OrderTitlebar,
        StagePipeline,
        HeaderStrip,
    };
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
