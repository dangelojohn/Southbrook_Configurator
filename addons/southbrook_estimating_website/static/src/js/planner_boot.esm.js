/** @odoo-module **/
//
// Phase 2 commit 3 (2026-05-31) — /kitchen-planner OWL three-pane shell.
//
// P2C2 mounted a tiny placeholder inside the viewport pane. P2C3
// expands the OWL component to own the entire three-pane layout
// (rail + catalog + viewport), renders real catalog tiles from the
// /southbrook/api/kitchen-planner/state payload, and wires tile-click
// to a selection state.
//
// What this commit ships:
//   - <KitchenPlanner/> renders the full three-pane layout from state.
//   - Catalog pane: 12 real tiles from state.payload.catalog
//     (sorted by family then SKU for predictable order), each with
//     SKU + name + family + retail price + 80x80 placeholder thumb.
//   - Tile click → state.ui.selected_id (highlighted via
//     .o_kp_tile_selected class). Viewport pane shows the selected
//     cabinet's details (name, family, price). Click same tile to
//     deselect; click another to switch.
//   - Search input filters tiles by name/SKU/family substring.
//   - Loading / error states styled consistently with the rest.
//
// What this commit does NOT yet ship:
//   - Tile click → create product.config.session (P2C4 — wires the
//     OCA configurator session flow).
//   - Attribute drawer below the viewport for picking series / door /
//     hinge / etc. — P2C4.
//   - Live pricing as attributes change — P2C5.
//   - 2D-isometric SVG cabinet renders in the viewport — P2C4 or P2C5.
//   - 'Request a Price' CTA → sale.order.draft — P2C6.

import {
    Component,
    mount,
    onMounted,
    useState,
    xml,
} from "@odoo/owl";

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
// Currency formatter — derived from payload.currency.
// ---------------------------------------------------------------------
function fmtCurrency(value, currency) {
    if (value === null || value === undefined) return "—";
    const sym = (currency && currency.symbol) || "$";
    const dp = (currency && currency.decimal_places) ?? 2;
    const formatted = Number(value).toLocaleString("en-US", {
        minimumFractionDigits: dp,
        maximumFractionDigits: dp,
    });
    return (currency && currency.position === "after")
        ? `${formatted} ${sym}`
        : `${sym}${formatted}`;
}

// ---------------------------------------------------------------------
// Stable family display order — base, drawer, wall, tall, sink, corner,
// vanity, accessory, worktop. Matches Q21 zone order for first 4.
// ---------------------------------------------------------------------
const FAMILY_ORDER = [
    "base", "drawer", "wall", "tall",
    "sink", "corner", "vanity", "accessory", "worktop",
];

function sortCatalog(catalog) {
    return [...catalog].sort((a, b) => {
        const fa = FAMILY_ORDER.indexOf(a.family);
        const fb = FAMILY_ORDER.indexOf(b.family);
        if (fa !== fb) {
            return (fa === -1 ? 99 : fa) - (fb === -1 ? 99 : fb);
        }
        return (a.sku || "").localeCompare(b.sku || "");
    });
}

// ---------------------------------------------------------------------
// KitchenPlanner — root OWL component (P2C3: owns the 3-pane layout).
// ---------------------------------------------------------------------
class KitchenPlanner extends Component {
    static template = xml`
        <div class="o_kp_root">

            <!-- LEFT TOOL RAIL -->
            <aside class="o_kp_rail">
                <div class="o_kp_rail_logo">SB</div>
                <ul class="o_kp_rail_actions">
                    <li class="o_kp_rail_action" title="Select / Pan">
                        <span class="o_kp_rail_glyph">▤</span>
                    </li>
                    <li class="o_kp_rail_action" title="Add cabinet">
                        <span class="o_kp_rail_glyph">＋</span>
                    </li>
                    <li class="o_kp_rail_action" title="Dimensions">
                        <span class="o_kp_rail_glyph">↕</span>
                    </li>
                    <li class="o_kp_rail_action" title="Solid / Blueline">
                        <span class="o_kp_rail_glyph">▦</span>
                    </li>
                </ul>
            </aside>

            <!-- CENTRE CATALOG PANE -->
            <section class="o_kp_catalog">
                <header class="o_kp_catalog_header">
                    <h2 class="o_kp_catalog_title">Cabinets</h2>
                    <input class="o_kp_catalog_search"
                           type="search"
                           placeholder="Search cabinets…"
                           t-att-value="state.ui.search"
                           t-on-input="(ev) => state.ui.search = ev.target.value.toLowerCase()"/>
                </header>

                <div t-if="state.loading"
                     class="o_kp_state o_kp_loading">
                    Loading planner…
                </div>
                <div t-elif="state.error"
                     class="o_kp_state o_kp_error">
                    <strong>Could not load planner.</strong>
                    <div class="o_kp_error_msg" t-esc="state.error"/>
                    <button class="o_kp_retry" t-on-click="_retry">Retry</button>
                </div>
                <ul t-else=""
                    class="o_kp_catalog_tiles">
                    <li t-foreach="filteredCatalog" t-as="cab" t-key="cab.id"
                        t-att-class="{
                            'o_kp_tile': true,
                            'o_kp_tile_selected': cab.id === state.ui.selected_id,
                        }"
                        t-on-click="() => this._onTileClick(cab.id)">
                        <div class="o_kp_tile_thumb"
                             t-att-data-family="cab.family"/>
                        <div class="o_kp_tile_body">
                            <div class="o_kp_tile_name" t-esc="cab.name"/>
                            <div class="o_kp_tile_meta">
                                <t t-esc="cab.sku"/> ·
                                <t t-esc="_fmt(cab.list_price)"/>
                            </div>
                        </div>
                    </li>
                    <li t-if="filteredCatalog.length === 0"
                        class="o_kp_tile_none">
                        No cabinets match "<t t-esc="state.ui.search"/>".
                    </li>
                </ul>

                <footer class="o_kp_catalog_foot"
                        t-if="!state.loading and !state.error">
                    <t t-esc="filteredCatalog.length"/> of
                    <t t-esc="state.payload.catalog.length"/> cabinets ·
                    Phase 2 commit 3
                </footer>
            </section>

            <!-- RIGHT VIEWPORT -->
            <main class="o_kp_viewport">
                <div t-if="state.loading or state.error"
                     class="o_kp_placeholder">
                    <h1 class="o_kp_placeholder_title">Design Your Kitchen</h1>
                </div>
                <div t-elif="selectedCabinet"
                     class="o_kp_selection">
                    <div class="o_kp_selection_thumb"
                         t-att-data-family="selectedCabinet.family"/>
                    <h1 class="o_kp_selection_name"
                        t-esc="selectedCabinet.name"/>
                    <dl class="o_kp_selection_meta">
                        <dt>SKU</dt><dd t-esc="selectedCabinet.sku"/>
                        <dt>Family</dt><dd t-esc="selectedCabinet.family"/>
                        <dt>Retail</dt>
                        <dd t-esc="_fmt(selectedCabinet.list_price)"/>
                    </dl>
                    <p class="o_kp_selection_foot">
                        Attribute picker + add-to-kitchen lands in
                        Phase 2 commit 4.
                    </p>
                </div>
                <div t-else="" class="o_kp_placeholder">
                    <h1 class="o_kp_placeholder_title">Design Your Kitchen</h1>
                    <p class="o_kp_placeholder_body">
                        Hello,
                        <t t-esc="state.payload.user.partner_name"/>. Pick
                        a cabinet from the catalog on the left to start.
                    </p>
                    <p class="o_kp_placeholder_meta">
                        <t t-esc="state.payload.catalog.length"/> cabinets ·
                        <t t-esc="state.payload.user.channel"/> ·
                        <t t-esc="state.payload.currency.name"/>
                    </p>
                </div>
            </main>
        </div>
    `;

    static props = {};

    setup() {
        this.state = useState({
            loading: true,
            error: null,
            payload: null,
            ui: {
                search: "",
                selected_id: null,
            },
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

    _retry = () => { this._load(); };

    _onTileClick = (id) => {
        if (this.state.ui.selected_id === id) {
            this.state.ui.selected_id = null;
        } else {
            this.state.ui.selected_id = id;
        }
    };

    _fmt(value) {
        return fmtCurrency(value, this.state.payload?.currency);
    }

    get filteredCatalog() {
        if (!this.state.payload) return [];
        const sorted = sortCatalog(this.state.payload.catalog);
        const q = (this.state.ui.search || "").trim();
        if (!q) return sorted;
        return sorted.filter((c) =>
            (c.name || "").toLowerCase().includes(q)
            || (c.sku || "").toLowerCase().includes(q)
            || (c.family || "").toLowerCase().includes(q)
        );
    }

    get selectedCabinet() {
        if (!this.state.payload || this.state.ui.selected_id === null) {
            return null;
        }
        return this.state.payload.catalog.find(
            (c) => c.id === this.state.ui.selected_id
        ) || null;
    }
}

// ---------------------------------------------------------------------
// mountKitchenPlanner — idempotent boot.
// ---------------------------------------------------------------------
async function mountKitchenPlanner() {
    const root = document.getElementById("kitchen_planner_root");
    if (!root || root.dataset.owlMounted === "1") return;
    root.dataset.owlMounted = "1";

    // Clear the P2C1 placeholder (rail + catalog + viewport
    // skeletons) before mounting.
    root.innerHTML = "";

    try {
        await mount(KitchenPlanner, root, {
            props: {},
            dev: false,
        });
    } catch (err) {
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
