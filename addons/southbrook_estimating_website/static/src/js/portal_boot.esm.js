/** @odoo-module **/
// Bundle hash bump 2026-06-22 — UX bugfix pass: poll no longer wipes
// transient UI state ("Loading order…" only on initial load + payload
// hash + modal-open pause); CatalogPicker defaults to Base; Add button
// gets a synchronous lock + a confirmation toast (single-add only).
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
import { Component, mount, markup, onMounted, onWillUnmount, useState, xml } from "@odoo/owl";
import { KitchenViewport } from "@southbrook_estimating_website/js/kitchen_viewport.esm";
import { RoomSetupWizard } from "@southbrook_estimating_website/js/room_setup_wizard.esm";
import { RoomLayoutTab, AssignToWallModal, GapRecommendModal } from "@southbrook_estimating_website/js/room_layout.esm";

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

export async function rpcJsonCall(url, params = {}) {
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
                <span t-if="props.mode === 'customer'"
                      class="o_owl_mode_badge">
                    CUSTOMER VIEW
                </span>
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
        mode: { type: String, optional: true },
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
            <t t-foreach="_stages" t-as="stage" t-key="stage_index">
                <div class="o_owl_stage"
                     t-att-class="{
                         'o_owl_stage_done':    stage_index &lt; currentIdx,
                         'o_owl_stage_current': stage_index === currentIdx,
                     }">
                    <span class="o_owl_stage_label" t-esc="stage.label"/>
                    <span t-if="stage.date"
                          class="o_owl_stage_date"
                          t-esc="_fmtDate(stage.date)"/>
                </div>
            </t>
        </div>
    `;
    static props = {
        order: Object,
        // G14 — mode='customer' tweaks labels to customer-friendly copy
        // (Designing / Submitted / Quoted / Confirmed / In Production)
        // instead of the dealer-side names (Draft / Estimating /
        // Approval / Confirmed / In Production).
        mode: { type: String, optional: true },
    };

    // G17 — labels per mode, plus the date field on order payload
    // (when populated by the backend). Indexes match currentIdx.
    get _stages() {
        const o = this.props.order || {};
        const dealer = ["Draft", "Estimating", "Approval", "Confirmed", "In Production"];
        const customer = ["Designing", "Submitted", "Quoted", "Confirmed", "In Production"];
        const labels = this.props.mode === "customer" ? customer : dealer;
        const dates = [
            o.created_date,      // 0 Draft / Designing
            o.submitted_date,    // 1 Estimating / Submitted
            null,                // 2 Approval / Quoted (Phase-3 polish stamps this)
            o.confirmed_date,    // 3 Confirmed
            null,                // 4 In Production (Phase-3 polish: MO create date)
        ];
        return labels.map((label, i) => ({ label, date: dates[i] || null }));
    }

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

    _fmtDate(isoStr) {
        if (!isoStr) return "";
        const d = new Date(isoStr);
        if (Number.isNaN(d.getTime())) return "";
        // Compact display: "Jun 1" — short month + day, no year unless
        // it differs from today.
        const opts = { month: "short", day: "numeric" };
        return d.toLocaleDateString(undefined, opts);
    }
}

// ----------------------------------------------------------------------
// FooterActions — T2C12.
//
// Bottom action row with the four primary actions (Customer Print /
// Duplicate / Confirm) and the grand total summary. Each button
// invokes props.onAction(code); the parent OrderBuilder handles the
// async RPC + post-action navigation/refresh.
//
// Confirm is disabled when order.state is outside (draft, sent).
// Print + Duplicate are always enabled (Phase 3 may gate based on
// order state — e.g. only allow Print after pricing has settled).
// ----------------------------------------------------------------------

class FooterActions extends Component {
    static template = xml`
        <div class="o_owl_footer">
            <div class="o_owl_footer_actions">
                <button class="o_owl_btn o_owl_btn_secondary"
                        t-on-click="() => props.onAction('print')"
                        t-att-disabled="props.busy">
                    <t t-if="props.mode === 'customer'">
                        Print Spec Sheet (PDF)
                    </t>
                    <t t-else="">Customer Print (PDF)</t>
                </button>

                <!-- Phase 4 Sprint 7 — Dealer-only: Print Door Order
                     (per-order door schedule, used by the door
                     supplier directly). -->
                <button t-if="props.mode !== 'customer'"
                        class="o_owl_btn o_owl_btn_secondary"
                        t-on-click="() => props.onAction('print_door_order')"
                        t-att-disabled="props.busy">
                    Print Door Order
                </button>

                <!-- Phase 4 Sprint 7 — Dealer-only: Print Shop Copy.
                     Surfaces only when an MO exists for this order
                     (after Send-to-Manufacturing fires). The server
                     returns no_mo when no MO is tied, and the OWL
                     component shows the message inline. -->
                <button t-if="props.mode !== 'customer' and props.order?.state === 'sale'"
                        class="o_owl_btn o_owl_btn_secondary"
                        t-on-click="() => props.onAction('print_shop_copy')"
                        t-att-disabled="props.busy">
                    Print Shop Copy
                </button>

                <!-- Dealer-only: Duplicate as Draft. Customers don't
                     duplicate their own orders — that's a sales-rep
                     iteration tool (NF6 Image Floor pattern). -->
                <button t-if="props.mode !== 'customer'"
                        class="o_owl_btn o_owl_btn_secondary"
                        t-on-click="() => props.onAction('duplicate')"
                        t-att-disabled="props.busy">
                    Duplicate as Draft
                </button>

                <!-- Phase 3 Sprint C4 — Cancel order. State-guarded
                     server-side: only draft/sent are cancelable from
                     the portal. The button hides itself once the
                     salesperson has confirmed (post-confirmation
                     cancellation goes through the backend). -->
                <button t-if="_canCancel()"
                        class="o_owl_btn o_owl_btn_secondary o_owl_btn_danger"
                        t-on-click="_onCancelClick"
                        t-att-disabled="props.busy">
                    Cancel Order
                </button>

                <!-- Phase 4 Sprint 2 — Send to Manufacturing.
                     Only visible once the order is in 'sale' state
                     (i.e. Confirmed). Dealer-only — customers don't
                     fire MOs. Click triggers a confirm() prompt
                     because creating MOs is hard to undo. -->
                <button t-if="_canSendToMfg()"
                        class="o_owl_btn o_owl_btn_primary"
                        t-on-click="_onSendToMfgClick"
                        t-att-disabled="props.busy">
                    Send to Manufacturing
                </button>

                <!-- Confirm vs Request a Price.
                     Step 5 (2026-06-01): dealer mode now opens a
                     confirmation modal before firing the irreversible
                     action_confirm. Customer mode still single-clicks
                     (the customer just asks for a price; nothing
                     manufacturing-ish has happened yet). -->
                <button class="o_owl_btn o_owl_btn_primary"
                        t-on-click="_onConfirmClick"
                        t-att-disabled="props.busy or !_canConfirm()">
                    <t t-if="!_canConfirm()">
                        <t t-if="props.mode === 'customer'">
                            Submitted (<t t-esc="props.order.state"/>)
                        </t>
                        <t t-else="">
                            Confirmed (<t t-esc="props.order.state"/>)
                        </t>
                    </t>
                    <t t-elif="props.mode === 'customer'">
                        Request a Price
                    </t>
                    <t t-else="">Send to Production</t>
                </button>
            </div>
            <div class="o_owl_footer_total">
                <div class="o_owl_footer_total_label">
                    <t t-if="props.mode === 'customer'">
                        Estimated Total
                    </t>
                    <t t-else="">Grand Total</t>
                </div>
                <div class="o_owl_footer_total_value mono"
                     t-esc="fmtUsd(props.order.channel_total)"/>
                <div class="o_owl_footer_total_sub">
                    <t t-esc="props.order.line_count"/> lines ·
                    <span t-att-class="'o_owl_channel_badge o_owl_channel_'
                                       + props.order.channel_css">
                        <t t-esc="props.order.channel_label"/>
                    </span>
                </div>
            </div>

            <!-- Step 5 (2026-06-01): Send-to-Production confirmation
                 modal. Renders inline as an overlay; closed via
                 state.confirming = false. Once PR #1 merges the PLM
                 variant-BoM snapshot fields, this modal will also
                 show the cut spec + BoM versions per line. For now
                 it shows what's already in the payload. -->
            <div t-if="state.confirming" class="o_owl_modal_backdrop"
                 t-on-click="_onCancelConfirm">
                <div class="o_owl_modal"
                     t-on-click="(ev) => ev.stopPropagation()">
                    <header class="o_owl_modal_head">
                        <h2 class="o_owl_modal_title">Send to Production?</h2>
                        <p class="o_owl_modal_sub">
                            This commits the order to manufacturing.
                            Once sent, the panel cut list locks
                            against the current cut spec. To change
                            anything after this point, an Engineering
                            Change Order (ECO) is required.
                        </p>
                    </header>
                    <dl class="o_owl_modal_review">
                        <dt>Order</dt>
                        <dd t-esc="props.order.name"/>
                        <dt>Customer</dt>
                        <dd t-esc="props.order.partner_name"/>
                        <dt>Channel</dt>
                        <dd>
                            <span t-att-class="'o_owl_channel_badge o_owl_channel_'
                                               + props.order.channel_css"
                                  t-esc="props.order.channel_label"/>
                        </dd>
                        <dt>Lines</dt>
                        <dd><t t-esc="props.order.line_count"/> cabinets</dd>
                        <dt>Retail</dt>
                        <dd class="mono"
                            t-esc="fmtUsd(props.order.retail_subtotal)"/>
                        <dt>Channel total</dt>
                        <dd class="mono o_owl_modal_grand"
                            t-esc="fmtUsd(props.order.channel_total)"/>
                    </dl>
                    <footer class="o_owl_modal_foot">
                        <button class="o_owl_btn o_owl_btn_secondary"
                                t-on-click="_onCancelConfirm"
                                t-att-disabled="props.busy">
                            Cancel
                        </button>
                        <button class="o_owl_btn o_owl_btn_primary"
                                t-on-click="_onApproveConfirm"
                                t-att-disabled="props.busy">
                            Send to Production
                        </button>
                    </footer>
                </div>
            </div>
        </div>
    `;
    static props = {
        order: Object,
        onAction: Function,
        busy: { type: Boolean, optional: true },
        mode: { type: String, optional: true },
    };

    setup() {
        this.state = useState({
            // Step 5 — Send-to-Production confirmation modal.
            // Toggled true when dealer clicks the primary action;
            // toggled false on Cancel, on Confirm-Send, or on
            // backdrop click. Customer mode never opens this modal.
            confirming: false,
        });
    }

    fmtUsd = fmtUsd;

    _canConfirm() {
        const s = this.props.order?.state;
        return s === "draft" || s === "sent";
    }

    // Phase 3 Sprint C4 — Cancel order availability.
    // Same gate as _canConfirm: only draft/sent are cancelable from
    // the portal. Server enforces the same rule; this check is purely
    // for hiding the button at rest.
    _canCancel() {
        const s = this.props.order?.state;
        return s === "draft" || s === "sent";
    }

    _onCancelClick = () => {
        if (!this._canCancel()) return;
        const msg = "Cancel this order? This cannot be undone from " +
                    "the portal — you would have to contact your dealer " +
                    "to reopen it.";
        if (typeof window !== "undefined" && window.confirm
            && !window.confirm(msg)) {
            return;
        }
        this.props.onAction("cancel");
    };

    // Phase 4 Sprint 2 — Send to Manufacturing availability.
    // Only post-confirm + dealer mode (customers don't fire MOs).
    // Server enforces the same gate; this hides the button at rest.
    _canSendToMfg() {
        if (this.props.mode === "customer") return false;
        return this.props.order?.state === "sale";
    }

    _onSendToMfgClick = () => {
        if (!this._canSendToMfg()) return;
        const msg = "Send all cabinets in this order to manufacturing? "
                  + "This creates an MO for every cabinet line with a "
                  + "BoM. Existing MOs (e.g. from a prior Send) are "
                  + "reused — nothing is duplicated.";
        if (typeof window !== "undefined" && window.confirm
            && !window.confirm(msg)) {
            return;
        }
        this.props.onAction("send_to_manufacturing");
    };

    _confirmAction() {
        return this.props.mode === "customer" ? "request_price" : "confirm";
    }

    /** Dealer click → open modal. Customer click → fire immediately. */
    _onConfirmClick = () => {
        if (!this._canConfirm()) return;
        if (this.props.mode === "customer") {
            // Customer Request-a-Price is a soft commit — no
            // manufacturing-irreversible action. Send directly.
            this.props.onAction(this._confirmAction());
            return;
        }
        // Dealer Send-to-Production → confirm first.
        this.state.confirming = true;
    };

    _onCancelConfirm = () => {
        this.state.confirming = false;
    };

    _onApproveConfirm = () => {
        this.state.confirming = false;
        this.props.onAction(this._confirmAction());
    };
}

// ----------------------------------------------------------------------
// BoMPreview — T2C11.
//
// Read-only panel showing the order's BoM rollup: total cabinets,
// per-panel-type counts (sides / top / bottom / back / shelf / door /
// drawer_front), hardware counts (hinges / handles / drawer slides),
// and total edge-banding length.
//
// Reads props.rollup (sourced from state.order... no — actually from
// the top-level payload's bom_rollup). T2C11 OrderBuilder reads
// state.bom_rollup which we add to the store in this commit.
// ----------------------------------------------------------------------

class BoMPreview extends Component {
    static template = xml`
        <div class="o_owl_bom">
            <div class="o_owl_bom_summary">
                <div class="o_owl_bom_summary_cell">
                    <div class="o_owl_bom_label">Cabinets</div>
                    <div class="o_owl_bom_value mono"
                         t-esc="props.rollup.cabinet_count"/>
                </div>
                <div class="o_owl_bom_summary_cell">
                    <div class="o_owl_bom_label">Total Panels</div>
                    <div class="o_owl_bom_value mono"
                         t-esc="_totalPanels()"/>
                </div>
                <div class="o_owl_bom_summary_cell">
                    <div class="o_owl_bom_label">Edge Banding</div>
                    <div class="o_owl_bom_value mono">
                        <t t-esc="_fmtMeters(props.rollup.edge_banding_mm)"/>
                        m
                    </div>
                </div>
            </div>

            <h4 class="o_owl_bom_section">Panel Cut List</h4>
            <table class="o_owl_bom_table">
                <thead>
                    <tr>
                        <th>Panel</th>
                        <th class="o_owl_th_right">Qty</th>
                    </tr>
                </thead>
                <tbody>
                    <t t-foreach="_panelRows()" t-as="row" t-key="row.key">
                        <tr t-if="row.qty > 0">
                            <td t-esc="row.label"/>
                            <td class="mono o_owl_th_right" t-esc="row.qty"/>
                        </tr>
                    </t>
                </tbody>
            </table>

            <h4 class="o_owl_bom_section">Hardware</h4>
            <table class="o_owl_bom_table">
                <thead>
                    <tr>
                        <th>Item</th>
                        <th class="o_owl_th_right">Qty</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Hinge pairs</td>
                        <td class="mono o_owl_th_right"
                            t-esc="props.rollup.hardware.hinge_pair_count"/>
                    </tr>
                    <tr>
                        <td>Handles</td>
                        <td class="mono o_owl_th_right"
                            t-esc="props.rollup.hardware.handle_count"/>
                    </tr>
                    <tr>
                        <td>Drawer slide pairs</td>
                        <td class="mono o_owl_th_right"
                            t-esc="props.rollup.hardware.drawer_slide_pair_count"/>
                    </tr>
                </tbody>
            </table>

            <!-- Phase 4 Sprint 3 — per-line BoM breakdown.
                 Each line gets its decomposition: width, panel count,
                 door count. Reads the B2 sb_panel_count / sb_door_count /
                 sb_width_mm fields surfaced into the line payload. -->
            <h4 t-if="(props.lines || []).length"
                class="o_owl_bom_section">
                Per Line
            </h4>
            <table t-if="(props.lines || []).length"
                   class="o_owl_bom_table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Cabinet</th>
                        <th class="o_owl_th_right">Width</th>
                        <th class="o_owl_th_right">Panels</th>
                        <th class="o_owl_th_right">Doors</th>
                    </tr>
                </thead>
                <tbody>
                    <tr t-foreach="props.lines || []" t-as="line"
                        t-key="line.id">
                        <td class="mono"
                            t-esc="line.sequence || line_index + 1"/>
                        <td t-esc="line.product_name || line.product_sku || 'Line'"/>
                        <td class="mono o_owl_th_right">
                            <t t-if="line.sb_width_mm">
                                <t t-esc="_fmtMm(line.sb_width_mm)"/>
                            </t>
                            <t t-else="">—</t>
                        </td>
                        <td class="mono o_owl_th_right"
                            t-esc="line.sb_panel_count || '—'"/>
                        <td class="mono o_owl_th_right"
                            t-esc="line.sb_door_count || '—'"/>
                    </tr>
                </tbody>
            </table>

            <p class="o_owl_bom_foot">
                Panel counts derive from variant attribute values when
                a configurator session is wired; otherwise they parse
                from the line name (B2 live-compute fallback).
            </p>
        </div>
    `;
    static props = {
        rollup: Object,
        // Phase 4 Sprint 3 — per-line array. Default empty so the
        // panel still renders cleanly on demo orders that haven't
        // been re-loaded since B2 shipped.
        lines: { type: Array, optional: true },
    };

    _totalPanels() {
        const p = this.props.rollup.panels || {};
        return Object.values(p).reduce((a, b) => a + b, 0);
    }

    _panelRows() {
        const p = this.props.rollup.panels || {};
        return [
            { key: "side",         label: "Side panels",          qty: p.side || 0 },
            { key: "top",          label: "Top panels",           qty: p.top || 0 },
            { key: "bottom",       label: "Bottom panels",        qty: p.bottom || 0 },
            { key: "back",         label: "Back panels",          qty: p.back || 0 },
            { key: "shelf",        label: "Shelves",              qty: p.shelf || 0 },
            { key: "door",         label: "Doors",                qty: p.door || 0 },
            { key: "drawer_front", label: "Drawer fronts",        qty: p.drawer_front || 0 },
        ];
    }

    _fmtMeters(mm) {
        if (!mm) return "0";
        return (mm / 1000).toFixed(2);
    }

    // Phase 4 Sprint 3 — format width as inches OR mm based on
    // size. Cabinet widths are quoted in inches in North America;
    // mm in Europe. Below 100 the value is in inches; above, mm.
    // Heuristic — 100mm < any cabinet < 100" is the safe zone.
    _fmtMm(mm) {
        if (!mm) return "—";
        if (mm < 100) {
            // Already in inches (parsed from 24" pattern).
            return `${mm.toFixed(0)}"`;
        }
        const inches = mm / 25.4;
        if (Math.abs(inches - Math.round(inches)) < 0.05) {
            return `${Math.round(inches)}" (${mm.toFixed(0)} mm)`;
        }
        return `${mm.toFixed(0)} mm`;
    }
}

// ----------------------------------------------------------------------
// ValidationStrip — T2C11.
//
// Lists hard-rule + soft-suggestion issues from the rule engine.
// Phase 1 ships an empty-state card; Phase 3 polish backports the
// real rule output (the OCA validate_configuration runner already
// produces this shape — needs wiring into the order-level payload).
// ----------------------------------------------------------------------

class ValidationStrip extends Component {
    static template = xml`
        <div class="o_owl_validation">
            <t t-if="props.issues.length === 0">
                <div class="o_owl_validation_ok">
                    <strong>✓ No rule issues.</strong>
                    <p class="o_owl_validation_foot">
                        Phase 3 polish wires the OCA rule engine output
                        per line. Today this panel shows the empty-state
                        whenever the rules pass (or aren't run).
                    </p>
                </div>
            </t>
            <t t-else="">
                <ul class="o_owl_validation_list">
                    <t t-foreach="props.issues" t-as="issue" t-key="issue_index">
                        <li class="o_owl_validation_item"
                            t-att-class="'o_owl_validation_' + issue.severity">
                            <span class="o_owl_validation_sev mono">
                                <t t-esc="issue.severity.toUpperCase()"/>
                            </span>
                            <span class="o_owl_validation_msg"
                                  t-esc="issue.message"/>
                            <span t-if="issue.line_id"
                                  class="o_owl_validation_ref mono">
                                Line <t t-esc="issue.line_id"/>
                            </span>
                        </li>
                    </t>
                </ul>
            </t>
        </div>
    `;
    static props = {
        issues: Array,
    };
}

// ----------------------------------------------------------------------
// ConfigDrawer — T2C10.
//
// Inline editable drawer that expands below the selected OrderLine,
// spanning all 8 columns of the zone grid. Shows the line's read-
// only spec + an editable Qty field with autosave.
//
// Autosave: on each Qty change (debounced 300ms), POSTs to
// /southbrook/api/line/<id>/update. On success calls props.onSaved
// which the parent OrderBuilder uses to refetch the order payload
// (so prices, line subtotals, zone subtotals, and header totals
// all refresh from the same source of truth).
//
// Phase 3 polish extends the editable surface to attribute pickers
// (Family, Width, Series, Door Style, Finish, Hinge Side, Finished
// Sides, Accessories) — the full mockup ConfigDrawer. Commit 10's
// Qty-only surface proves the autosave pattern end-to-end so the
// later attribute-picker additions are mechanical.
// ----------------------------------------------------------------------

class ConfigDrawer extends Component {
    static template = xml`
        <div class="o_owl_drawer" style="grid-column: 1 / -1;">
            <div class="o_owl_drawer_head">
                <span class="o_owl_drawer_title">
                    Line <t t-esc="props.line.sequence"/> · Configuration
                </span>
                <span class="o_owl_drawer_pill"
                      t-att-class="{
                          'o_owl_drawer_pill_saving': state.saving,
                          'o_owl_drawer_pill_error':  state.error,
                      }">
                    <t t-if="state.saving">SAVING…</t>
                    <t t-elif="state.error">ERROR · <t t-esc="state.error"/></t>
                    <t t-elif="state.savedAt">SAVED · <t t-esc="state.savedAt"/></t>
                    <t t-else="">LIVE EDIT · AUTOSAVE</t>
                </span>
            </div>

            <div class="o_owl_drawer_grid">

                <!-- Read-only spec block. -->
                <div class="o_owl_attr">
                    <label>Template</label>
                    <div class="o_owl_attr_value">
                        <t t-esc="props.line.product_name"/>
                        <span class="o_owl_attr_sku mono"
                              t-if="props.line.product_sku"
                              t-esc="props.line.product_sku"/>
                    </div>
                </div>
                <div class="o_owl_attr">
                    <label>Family</label>
                    <div class="o_owl_attr_value mono"
                         t-esc="props.line.family || '—'"/>
                </div>
                <div class="o_owl_attr">
                    <label>Zone</label>
                    <div class="o_owl_attr_value">
                        <t t-esc="_zoneLabel(props.line.zone)"/>
                    </div>
                </div>
                <div class="o_owl_attr">
                    <label>Width</label>
                    <div class="o_owl_attr_value mono">
                        <t t-if="props.line.width_inches">
                            <t t-esc="props.line.width_inches"/>″
                            (<t t-esc="props.line.width_mm"/> mm)
                        </t>
                        <t t-else="">—</t>
                    </div>
                </div>

                <!-- Spec text — what the user picked in the wizard. -->
                <div class="o_owl_attr o_owl_attr_wide">
                    <label>Spec</label>
                    <div class="o_owl_attr_value">
                        <t t-esc="props.line.spec_summary || '—'"/>
                        <span t-if="props.line.is_maple"
                              class="o_owl_badge o_owl_badge_maple">
                            MAPLE
                        </span>
                    </div>
                </div>

                <!-- Editable: Qty + autosave. -->
                <div class="o_owl_attr">
                    <label for="qty_field">Quantity</label>
                    <input id="qty_field"
                           type="number"
                           min="1"
                           step="1"
                           class="o_owl_qty_input mono"
                           t-att-value="state.qtyDraft"
                           t-on-input="_onQtyInput"
                           t-att-disabled="state.saving"/>
                </div>

                <!-- Read-only prices. -->
                <div class="o_owl_attr">
                    <label>Retail</label>
                    <div class="o_owl_attr_value mono o_owl_drawer_retail"
                         t-esc="fmtUsd(props.line.retail_price)"/>
                </div>
                <div class="o_owl_attr">
                    <label>Channel</label>
                    <div class="o_owl_attr_value mono"
                         t-esc="fmtUsd(props.line.channel_price)"/>
                </div>
            </div>

            <!-- G15 — attribute picker grid. Loads on drawer open from
                 /api/line/<id>/attributes; each attribute renders as a
                 select. Changing a value fires /set-attribute which
                 swaps the line's product variant and re-prices. -->
            <div class="o_owl_attr_picker"
                 t-if="state.attributes.length || state.attrsLoading">
                <div class="o_owl_attr_picker_head">
                    <span class="o_owl_attr_picker_title">
                        Configure this cabinet
                    </span>
                    <span t-if="state.attrsLoading"
                          class="o_owl_attr_picker_pill">
                        Loading options…
                    </span>
                    <span t-elif="state.attrSaving"
                          class="o_owl_attr_picker_pill o_owl_attr_picker_saving">
                        Updating…
                    </span>
                </div>
                <div class="o_owl_attr_picker_grid">
                    <div t-foreach="state.attributes"
                         t-as="attr"
                         t-key="attr.attribute_id"
                         class="o_owl_attr o_owl_attr_picker_field">
                        <label t-attf-for="attr_field_{{attr.attribute_id}}">
                            <t t-esc="attr.name"/>
                        </label>
                        <select t-attf-id="attr_field_{{attr.attribute_id}}"
                                class="o_owl_attr_select"
                                t-att-disabled="state.attrSaving"
                                t-on-change="(ev) => this._onAttrChange(attr.attribute_id, ev.target.value)">
                            <option value="">— pick —</option>
                            <option t-foreach="attr.values"
                                    t-as="v"
                                    t-key="v.value_id"
                                    t-att-value="v.value_id"
                                    t-att-selected="v.current ? 'selected' : null"
                                    t-esc="v.name"/>
                        </select>
                    </div>
                </div>
                <p t-if="state.attrError"
                   class="o_owl_attr_picker_error"
                   t-esc="state.attrError"/>
            </div>

            <!-- Phase 3 Sprint C2 — line-scoped validation hints.
                 Lists any hard/soft/info validation issues tied to
                 this line so the dealer can see at-a-glance which
                 combinations are flagged before clicking through
                 the picker. Issues are produced by B1's rule
                 inspector and passed in as the lineIssues prop. -->
            <div t-if="(props.lineIssues || []).length"
                 class="o_owl_drawer_validation">
                <div class="o_owl_drawer_validation_head">
                    Rule notes for this line
                </div>
                <ul class="o_owl_drawer_validation_list">
                    <li t-foreach="props.lineIssues || []"
                        t-as="iss" t-key="iss_index"
                        t-att-class="'o_owl_drawer_validation_item o_owl_dv_' + iss.severity">
                        <span class="o_owl_dv_sev mono"
                              t-esc="iss.severity.toUpperCase()"/>
                        <span class="o_owl_dv_msg" t-esc="iss.message"/>
                    </li>
                </ul>
            </div>

            <p class="o_owl_drawer_foot">
                The picker above swaps the line's variant on each
                change and re-prices it. Hard-rule violations surface
                inline as a Rule Notes block above; soft suggestions
                stay there as recommendations.
            </p>
        </div>
    `;
    static props = {
        line: Object,
        onSaved: Function,
        // Phase 3 Sprint C2 — per-line validation issues forwarded
        // from the OrderBuilder's state.validation array, filtered
        // to those tied to this line.id. Default empty.
        lineIssues: { type: Array, optional: true },
    };

    setup() {
        this.state = useState({
            qtyDraft: this.props.line.qty,
            saving: false,
            error: null,
            savedAt: null,
            // G15 — attribute picker state.
            attributes: [],
            attrsLoading: false,
            attrSaving: false,
            attrError: null,
        });
        this._debounceTimer = null;
        onMounted(() => this._loadAttributes());
    }

    fmtUsd = fmtUsd;

    // ------------------------------------------------------------------
    // G15 — attribute picker.
    // ------------------------------------------------------------------

    async _loadAttributes() {
        this.state.attrsLoading = true;
        this.state.attrError = null;
        try {
            const r = await rpcJsonCall(
                `/southbrook/api/line/${this.props.line.id}/attributes`,
                {},
            );
            if (r && r.ok) {
                this.state.attributes = r.attributes || [];
            } else {
                this.state.attrError = r?.error || "Could not load options.";
            }
        } catch (e) {
            this.state.attrError = e?.message || String(e);
        } finally {
            this.state.attrsLoading = false;
        }
    }

    async _onAttrChange(attributeId, valueId) {
        if (!valueId) return;
        this.state.attrSaving = true;
        this.state.attrError = null;
        try {
            const r = await rpcJsonCall(
                `/southbrook/api/line/${this.props.line.id}/set-attribute`,
                {
                    attribute_id: parseInt(attributeId, 10),
                    value_id: parseInt(valueId, 10),
                },
            );
            if (r && r.ok) {
                // Re-fetch attributes (current selection updates) AND
                // trigger the parent to refresh the order so the line
                // tile re-renders with the new price/spec.
                await Promise.all([
                    this._loadAttributes(),
                    this.props.onSaved(),
                ]);
            } else {
                this.state.attrError = (
                    r?.error === "order_locked"
                    ? `Cannot edit — order is ${r.state}.`
                    : r?.error || "Could not update the cabinet."
                );
            }
        } catch (e) {
            this.state.attrError = e?.message || String(e);
        } finally {
            this.state.attrSaving = false;
        }
    }

    _zoneLabel(zone) {
        const labels = {
            base_run: "Base Run",
            wall: "Wall",
            tall: "Tall",
            island: "Island",
            accessory: "Accessory",
            other: "Other",
        };
        return labels[zone] || zone;
    }

    _onQtyInput = (event) => {
        const newVal = event.target.value;
        this.state.qtyDraft = newVal;
        if (this._debounceTimer) clearTimeout(this._debounceTimer);
        // 300ms debounce so rapid arrow-key / typing doesn't fire 10
        // RPCs. The pill flashes SAVING then SAVED after the burst.
        this._debounceTimer = setTimeout(() => this._save(newVal), 300);
    };

    async _save(qty) {
        const qtyNum = parseFloat(qty);
        if (!Number.isFinite(qtyNum) || qtyNum <= 0) {
            this.state.error = "Qty must be > 0";
            return;
        }
        this.state.saving = true;
        this.state.error = null;
        try {
            const res = await rpcJsonCall(
                `/southbrook/api/line/${this.props.line.id}/update`,
                { qty: qtyNum },
            );
            if (res && res.error) {
                this.state.error = res.error;
                return;
            }
            this.state.savedAt = new Date().toLocaleTimeString();
            // Tell parent to refresh — order subtotals + savings depend
            // on this line's price, which is qty-dependent in Odoo.
            await this.props.onSaved();
        } catch (e) {
            this.state.error = e?.message || String(e);
        } finally {
            this.state.saving = false;
        }
    }
}

// ----------------------------------------------------------------------
// OrderLine — T2C9.
//
// One row in the zone grid. 8-column layout matching the mockup:
//   [#] [Template + SKU] [Width] [Spec + badges] [Qty]
//   [Retail strike] [Channel] [⋯ menu]
//
// Click anywhere on the row → parent OrderBuilder's selected_line_id
// updates and the row gets .o_owl_line_selected (yellow highlight).
// ----------------------------------------------------------------------

class OrderLine extends Component {
    static template = xml`
        <div class="o_owl_line"
             t-att-class="{ 'o_owl_line_selected': props.isSelected }"
             t-on-click="() => props.onSelect(props.line.id)">
            <div class="o_owl_lineno" t-esc="props.line.sequence"/>
            <div class="o_owl_line_tpl">
                <t t-esc="props.line.product_name"/>
                <span t-if="props.line.product_sku"
                      class="o_owl_line_xmlid"
                      t-esc="props.line.product_sku"/>
            </div>
            <div class="o_owl_line_dim mono">
                <t t-if="props.line.width_inches">
                    <t t-esc="props.line.width_inches"/>″
                </t>
                <t t-else="">—</t>
            </div>
            <div class="o_owl_line_spec">
                <t t-esc="props.line.spec_summary"/>
                <span t-if="props.line.is_maple"
                      class="o_owl_badge o_owl_badge_maple">
                    MAPLE
                </span>
                <span t-if="props.line.rule_blocked"
                      class="o_owl_badge o_owl_badge_rule">
                    RULE
                </span>
            </div>
            <div class="o_owl_line_qty mono" t-esc="props.line.qty"/>
            <div class="o_owl_line_price o_owl_line_retail mono"
                 t-esc="fmtUsd(props.line.retail_price)"/>
            <div class="o_owl_line_price mono"
                 t-esc="fmtUsd(props.line.channel_price)"/>
            <div class="o_owl_line_menu">⋯</div>
        </div>
    `;
    static props = {
        line: Object,
        isSelected: { type: Boolean, optional: true },
        onSelect: Function,
    };
    fmtUsd = fmtUsd;
}

// ----------------------------------------------------------------------
// ZoneGroup — T2C9.
//
// Collapsible group of OrderLine rows under a zone header. Header
// shows chevron + name + line count + (retail strike) channel subtotal.
// Click the header → toggles collapsed state (lives on the
// ZoneGroup, not the parent OrderBuilder — each zone collapses
// independently).
// ----------------------------------------------------------------------

class ZoneGroup extends Component {
    static template = xml`
        <div class="o_owl_zone"
             t-att-class="{ 'o_owl_zone_collapsed': state.collapsed }">
            <div class="o_owl_zone_header" t-on-click="_toggle">
                <span class="o_owl_zone_chevron">▾</span>
                <span class="o_owl_zone_name" t-esc="props.zone.label"/>
                <span class="o_owl_zone_count">
                    <t t-esc="props.zone.line_count"/>
                    <t t-if="props.zone.line_count === 1">line</t>
                    <t t-else="">lines</t>
                </span>
                <span class="o_owl_zone_subtotal">
                    <span class="o_owl_zone_retail mono"
                          t-esc="fmtUsd(props.zone.subtotal)"/>
                    <span class="o_owl_zone_channel mono"
                          t-esc="fmtUsd(props.zone.channel_subtotal)"/>
                </span>
            </div>
            <div class="o_owl_lines" t-if="!state.collapsed">
                <div class="o_owl_line_head">
                    <div/>
                    <div>Template</div>
                    <div>Width</div>
                    <div>Spec</div>
                    <div class="o_owl_th_center">Qty</div>
                    <div class="o_owl_th_right">Retail</div>
                    <div class="o_owl_th_right">Channel</div>
                    <div/>
                </div>
                <t t-foreach="props.lines" t-as="line" t-key="line.id">
                    <!-- Phase 3.D — per-line status chip. Hidden when no
                         room is configured (chipStatus returns null). The
                         OrderLine row hosts its own grid; the chip sits
                         to its left as a sibling so click targets stay
                         clean. -->
                    <t t-set="chipStatus" t-value="_lineStatus(line)"/>
                    <small t-if="chipStatus"
                           class="sb-room-chip-status"
                           t-att-class="'sb-room-chip-status--' + chipStatus"
                           t-att-title="_chipTitle(chipStatus)"
                           t-esc="_chipDot(chipStatus)"/>
                    <OrderLine line="line"
                               isSelected="line.id === props.selectedLineId"
                               onSelect="props.onSelectLine"/>
                    <!-- T2C10 — ConfigDrawer expands below the selected line,
                         spanning all 8 columns of the parent grid. -->
                    <ConfigDrawer t-if="line.id === props.selectedLineId"
                                  line="line"
                                  lineIssues="props.issuesForLine(line.id)"
                                  onSaved="props.onLineSaved"/>
                </t>
                <!-- Phase 3 Sprint C1 — per-zone inline add-line.
                     Click opens the catalog modal with the picker pre-
                     filtered to the zone's family. Lets dealers grow a
                     specific zone without scrolling back to the top
                     "Add Another Cabinet" button. -->
                <div class="o_owl_zone_add"
                     t-on-click.stop="() => props.onAddToZone(props.zone.code)">
                    <button class="o_owl_zone_add_btn"
                            t-att-aria-label="'Add cabinet to ' + props.zone.label">
                        + Add to <t t-esc="props.zone.label"/>
                    </button>
                </div>
                <!-- Phase 3.D — per-zone wall-summary footer. Only
                     renders when every line in the zone points at the
                     same wall (single-wall zone); otherwise stays
                     silent so multi-wall zones aren't misrepresented.
                     Phase 4 — length labels flip through _humanLen so
                     they honour the room's unit_preference toggle. -->
                <t t-set="wallSummary" t-value="_singleWallSummary()"/>
                <div t-if="wallSummary"
                     class="sb-room-zone-wall-summary">
                    <span class="sb-room-zone-wall-name">
                        Wall: <t t-esc="wallSummary.name"/>
                    </span>
                    <span class="sb-room-zone-wall-cap mono">
                        <t t-esc="_humanLen(wallSummary.used_mm)"/> / <t t-esc="_humanLen(wallSummary.length_mm)"/> used
                    </span>
                    <span class="sb-room-zone-wall-rem mono"
                          t-att-class="wallSummary.remaining_mm &lt; 0 ? 'sb-room-zone-wall-rem--over' : ''">
                        <t t-esc="_humanLen(wallSummary.remaining_mm)"/> left
                    </span>
                </div>
            </div>
        </div>
    `;
    static components = { OrderLine, ConfigDrawer };
    static props = {
        zone: Object,
        lines: Array,
        selectedLineId: { type: [Number, { value: null }], optional: true },
        onSelectLine: Function,
        onLineSaved: Function,
        onAddToZone: Function,
        // Phase 3 Sprint C2 — issuesForLine(line_id) -> Array of
        // validation issues filtered to the given line.
        issuesForLine: Function,
        // Phase 3.D — the order's room payload (mirror of state.room on
        // the parent OrderBuilder). Null when no room is configured;
        // in that case _lineStatus returns null and chips don't render
        // and the wall-summary footer stays silent.
        room: { type: [Object, { value: null }], optional: true },
        // Phase 4 — unit preference forwarded from OrderBuilder so the
        // wall-summary footer renders mm or ft/in consistently with the
        // rest of the Room Setup surface. Mirrored locally on the
        // ZoneGroup so _humanLen here doesn't have to reach back into a
        // parent reference. Defaults to "mm".
        unitPreference: { type: String, optional: true },
    };

    setup() {
        this.state = useState({ collapsed: false });
    }

    _toggle = () => {
        this.state.collapsed = !this.state.collapsed;
    };

    // Phase 4 — mm → ft/in conversion mirror of OrderBuilder._imperialFromMm.
    // Kept identical (small + pure) so the wall-summary footer can call it
    // without a prop-method round-trip. Reads unitPreference from props so
    // the parent can flip the toggle and OWL re-renders this group.
    _imperialFromMm(mm) {
        const inches = Math.round((Number(mm) || 0) / 25.4);
        const feet = Math.floor(inches / 12);
        const remIn = inches - feet * 12;
        if (feet === 0) return `${remIn}"`;
        if (remIn === 0) return `${feet}'`;
        return `${feet}' ${remIn}"`;
    }

    _humanLen(mm) {
        if (!mm && mm !== 0) return "—";
        const pref = this.props.unitPreference || "mm";
        if (pref === "imperial") return this._imperialFromMm(mm);
        return `${Math.round(Number(mm) || 0)} mm`;
    }

    // Phase 3.D — derive the chip status for one line. Pure function
    // of (line, props.room); no new state, recomputes per render so
    // OWL handles reactivity naturally.
    _lineStatus(line) {
        if (!this.props.room) return null;
        if (!line.wall_id) return "unplaced";
        const walls = this.props.room.walls || [];
        const wall = walls.find((w) => w.id === line.wall_id);
        if (wall && wall.has_conflicts) return "conflict";
        return "placed";
    }

    _chipDot(status) {
        // U+25CF (BLACK CIRCLE) — accessible to screen readers via the
        // title attribute; visual colour is handled by the SCSS variant.
        return "●";
    }

    _chipTitle(status) {
        return {
            placed:   "Placed on a wall",
            unplaced: "Not yet placed on a wall",
            conflict: "Wall has a placement conflict",
        }[status] || "";
    }

    // Phase 3.D — collapse-to-summary when every line in the zone
    // points at the same wall. Returns the wall dict or null.
    _singleWallSummary() {
        if (!this.props.room) return null;
        const lines = this.props.lines || [];
        if (!lines.length) return null;
        const firstId = lines[0].wall_id;
        if (!firstId) return null;
        for (const l of lines) {
            if (l.wall_id !== firstId) return null;
        }
        const walls = this.props.room.walls || [];
        return walls.find((w) => w.id === firstId) || null;
    }

    fmtUsd = fmtUsd;
}

// ----------------------------------------------------------------------
// TabBar — T2C8.
//
// 5 tabs from the mockup (Order Lines / BoM Preview / Validation /
// History / Customer Print) with count badges. State lives on the
// parent OrderBuilder (state.ui.current_tab) so child panels can
// switch panels without re-rendering the whole frame.
//
// Each tab is `{code, label, count}`. count may be a number, a string
// ("v1"), or null (no badge for the print tab).
// ----------------------------------------------------------------------

class TabBar extends Component {
    // Phase 3 Sprint D1 — Tab/Tablist role pattern from the WAI-ARIA
    // Authoring Practices. Arrow keys cycle between tabs; Home/End
    // jump to ends; Tab key moves focus OUT of the tablist into the
    // panel content (browser default — no JS needed).
    static template = xml`
        <div class="o_owl_tabs" role="tablist"
             aria-label="Order builder sections"
             t-on-keydown="_onKeydown">
            <t t-foreach="props.tabs" t-as="tab" t-key="tab.code">
                <button class="o_owl_tab"
                        role="tab"
                        t-att-class="{
                            'o_owl_tab_active': tab.code === props.activeTab,
                        }"
                        t-att-aria-selected="tab.code === props.activeTab ? 'true' : 'false'"
                        t-att-tabindex="tab.code === props.activeTab ? '0' : '-1'"
                        t-att-data-tab-code="tab.code"
                        t-att-id="'o_owl_tab_' + tab.code"
                        t-on-click.stop="() => props.onTabChange(tab.code)">
                    <t t-esc="tab.label"/>
                    <span t-if="tab.count !== null and tab.count !== undefined"
                          class="o_owl_tab_count"
                          t-esc="tab.count"/>
                </button>
            </t>
        </div>
    `;
    static props = {
        tabs: Array,
        activeTab: String,
        onTabChange: Function,
    };

    _onKeydown(event) {
        // Roving-tabindex Left/Right cycling; Home/End jump to ends.
        const codes = this.props.tabs.map((t) => t.code);
        const cur = codes.indexOf(this.props.activeTab);
        if (cur < 0) return;
        let next = cur;
        switch (event.key) {
            case "ArrowRight":
            case "ArrowDown":
                next = (cur + 1) % codes.length;
                break;
            case "ArrowLeft":
            case "ArrowUp":
                next = (cur - 1 + codes.length) % codes.length;
                break;
            case "Home":
                next = 0;
                break;
            case "End":
                next = codes.length - 1;
                break;
            default:
                return;
        }
        event.preventDefault();
        this.props.onTabChange(codes[next]);
        // Focus the newly-active tab so arrow nav continues.
        const root = event.currentTarget;
        const target = root && root.querySelector(
            `[data-tab-code="${codes[next]}"]`,
        );
        if (target && target.focus) target.focus();
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
                <div class="o_owl_hs_value"
                     t-att-title="props.order.partner_name">
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
// Cabinet icon set (2026-06-02 redesign).
//
// Stroke-only 48×48 line drawings, one per icon key. Inherit colour
// via stroke="currentColor" so they tint to whatever colour the
// surrounding card uses (walnut on hover, ink-dim by default).
//
// Keys match the `icon` field stamped by SouthbrookKitchenPlannerSPA
// ._CATALOG_METADATA in the controller. cabinetIcon() resolves a
// key to a markup() wrapper so OWL's t-out renders it as HTML; an
// unknown key falls back to the 'extra' icon.
// ----------------------------------------------------------------------

const CABINET_ICONS = {
    wall1: `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <rect x="12" y="6" width="24" height="36" rx="2"/>
        <rect x="15" y="9" width="18" height="30" rx="1"/>
        <circle cx="30" cy="24" r="1" fill="currentColor"/>
    </svg>`,
    wall2: `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <rect x="4" y="8" width="40" height="32" rx="2"/>
        <rect x="7" y="11" width="16" height="26" rx="1"/>
        <rect x="25" y="11" width="16" height="26" rx="1"/>
        <circle cx="20" cy="24" r="1" fill="currentColor"/>
        <circle cx="28" cy="24" r="1" fill="currentColor"/>
    </svg>`,
    base1: `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <rect x="8" y="6" width="32" height="32" rx="2"/>
        <rect x="11" y="9" width="26" height="26" rx="1"/>
        <circle cx="34" cy="22" r="1" fill="currentColor"/>
        <line x1="8" y1="38" x2="40" y2="38"/>
        <line x1="10" y1="42" x2="38" y2="42"/>
    </svg>`,
    base2: `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <rect x="4" y="6" width="40" height="32" rx="2"/>
        <rect x="7" y="9" width="16" height="26" rx="1"/>
        <rect x="25" y="9" width="16" height="26" rx="1"/>
        <circle cx="20" cy="22" r="1" fill="currentColor"/>
        <circle cx="28" cy="22" r="1" fill="currentColor"/>
        <line x1="6" y1="38" x2="42" y2="38"/>
        <line x1="8" y1="42" x2="40" y2="42"/>
    </svg>`,
    drawer: `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <rect x="8" y="6" width="32" height="32" rx="2"/>
        <rect x="11" y="9" width="26" height="7" rx="1"/>
        <rect x="11" y="18.5" width="26" height="7" rx="1"/>
        <rect x="11" y="28" width="26" height="7" rx="1"/>
        <line x1="20" y1="12.5" x2="28" y2="12.5"/>
        <line x1="20" y1="22" x2="28" y2="22"/>
        <line x1="20" y1="31.5" x2="28" y2="31.5"/>
        <line x1="8" y1="42" x2="40" y2="42"/>
    </svg>`,
    sink: `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <rect x="4" y="6" width="40" height="32" rx="2"/>
        <ellipse cx="24" cy="20" rx="12" ry="6"/>
        <circle cx="24" cy="20" r="1.5"/>
        <line x1="11" y1="30" x2="37" y2="30"/>
        <line x1="6" y1="38" x2="42" y2="38"/>
        <line x1="8" y1="42" x2="40" y2="42"/>
    </svg>`,
    pantry: `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <rect x="14" y="2" width="20" height="44" rx="2"/>
        <line x1="17" y1="12" x2="31" y2="12"/>
        <line x1="17" y1="20" x2="31" y2="20"/>
        <line x1="17" y1="28" x2="31" y2="28"/>
        <line x1="17" y1="36" x2="31" y2="36"/>
        <circle cx="31" cy="24" r="1" fill="currentColor"/>
    </svg>`,
    oven: `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <rect x="12" y="2" width="24" height="44" rx="2"/>
        <rect x="15" y="6" width="18" height="6" rx="1"/>
        <rect x="15" y="14" width="18" height="14" rx="1"/>
        <circle cx="24" cy="21" r="3"/>
        <rect x="15" y="30" width="18" height="14" rx="1"/>
    </svg>`,
    corner: `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M 6 6 L 30 6 L 42 18 L 42 42 L 6 42 Z"/>
        <line x1="30" y1="6" x2="42" y2="18"/>
        <rect x="10" y="11" width="12" height="26" rx="1"/>
        <circle cx="19" cy="24" r="1" fill="currentColor"/>
    </svg>`,
    vanity: `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <ellipse cx="24" cy="10" rx="14" ry="4"/>
        <line x1="20" y1="6" x2="28" y2="6"/>
        <rect x="6" y="14" width="36" height="28" rx="2"/>
        <rect x="9" y="17" width="14" height="22" rx="1"/>
        <rect x="25" y="17" width="14" height="22" rx="1"/>
        <circle cx="21" cy="28" r="1" fill="currentColor"/>
        <circle cx="27" cy="28" r="1" fill="currentColor"/>
    </svg>`,
    extra: `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <rect x="6" y="6" width="14" height="14" rx="1.5"/>
        <rect x="28" y="6" width="14" height="14" rx="1.5"/>
        <rect x="6" y="28" width="14" height="14" rx="1.5"/>
        <rect x="28" y="28" width="14" height="14" rx="1.5"/>
        <line x1="35" y1="32" x2="35" y2="38"/>
        <line x1="32" y1="35" x2="38" y2="35"/>
    </svg>`,
    worktop: `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <rect x="4" y="20" width="40" height="8" rx="1.5"/>
        <line x1="10" y1="20" x2="10" y2="28"/>
        <line x1="38" y1="20" x2="38" y2="28"/>
        <line x1="2" y1="35" x2="46" y2="35" stroke-dasharray="3 3"/>
    </svg>`,
};

function cabinetIcon(key) {
    return markup(CABINET_ICONS[key] || CABINET_ICONS.extra);
}

// ----------------------------------------------------------------------
// CatalogPicker (G11+G12+G13 2026-06-01, redesigned 2026-06-02).
//
// Modal that lists the 12 Q8 cabinet templates as filterable cards.
// 2026-06-02 redesign added: search input, category pills, grid/list
// view toggle, per-card quantity stepper, SVG icon thumbnails,
// hover-lift cards, brand-accent Add button with success state.
//
// The add path is unchanged — addItem(item) calls props.onPick(item.id,
// qty), which is the SAME function path the old tile-click used. No
// duplication, no bypass; the qty arg flows through to the existing
// /southbrook/api/order/<id>/add-line endpoint.
//
// Props:
//   catalog  — array of {id, sku, name, list_price, family, category,
//                        description, dimensions, icon}
//   open     — whether the modal is shown
//   busy     — true while the add-line RPC is in flight
//   onClose  — fired when user dismisses the modal
//   onPick   — fired with (templateId, qty) when an Add button is clicked
// ----------------------------------------------------------------------

class CatalogPicker extends Component {
    static template = xml`
        <div t-if="props.open" class="o_owl_modal_backdrop"
             t-on-click="_onBackdropClick">
            <div class="o_owl_modal_panel o_owl_catalog_panel"
                 t-att-class="state.viewMode === 'list' ? 'o_owl_catalog_panel_list' : ''"
                 t-on-click.stop="">

                <div class="o_owl_modal_header">
                    <h3 class="o_owl_modal_title">
                        Add a cabinet to your order
                    </h3>
                    <!-- P1 / UX 2026-06-22: persistent cart counter in
                         the modal header. Updates live as _onPickCabinet
                         finishes and the parent's _loadOrder mutates
                         state.lines. Singular/plural handled inline. -->
                    <span class="o_owl_modal_cart_count"
                          t-if="props.cartCount !== null">
                        <strong t-esc="props.cartCount"/>
                        <t t-if="props.cartCount === 1"> cabinet</t>
                        <t t-else=""> cabinets</t>
                        on order
                    </span>
                    <button type="button" class="o_owl_modal_close"
                            t-on-click="_onCloseClick"
                            aria-label="Close">×</button>
                </div>

                <div class="o_owl_catalog_toolbar">
                    <!-- 2026-06-02 filter v2 alternative — compact
                         &lt;select&gt; dropdown. Renders only when
                         state.filterMode === 'select' (see setup
                         comment for how to switch). Same setCategory
                         handler the tab bar uses. -->
                    <select t-if="state.filterMode === 'select'"
                            class="o_owl_catalog_filter_select"
                            t-on-change="(ev) => this._setCategory(ev.target.value)"
                            aria-label="Filter by category">
                        <option t-foreach="getCategoryTabs()"
                                t-as="tab"
                                t-key="tab.key"
                                t-att-value="tab.key"
                                t-att-selected="state.activeCategory === tab.key ? 'selected' : ''">
                            <t t-esc="tab.key"/> · <t t-esc="tab.count"/>
                        </option>
                    </select>
                    <div class="o_owl_catalog_search_wrap">
                        <svg class="o_owl_catalog_search_icon"
                             viewBox="0 0 24 24" fill="none"
                             stroke="currentColor" stroke-width="2"
                             stroke-linecap="round"
                             stroke-linejoin="round" aria-hidden="true">
                            <circle cx="11" cy="11" r="7"/>
                            <line x1="20" y1="20" x2="16.5" y2="16.5"/>
                        </svg>
                        <input type="search"
                               class="o_owl_catalog_search"
                               placeholder="Search cabinets by name or SKU…"
                               t-att-value="state.searchQuery"
                               t-on-input="_onSearch"
                               aria-label="Search catalog"/>
                    </div>
                    <div class="o_owl_catalog_view_toggle"
                         role="group" aria-label="View mode">
                        <button type="button"
                                class="o_owl_catalog_view_btn"
                                t-att-class="state.viewMode === 'grid' ? 'o_owl_catalog_view_btn_active' : ''"
                                t-on-click="() => this._setView('grid')"
                                aria-label="Grid view"
                                title="Grid view">
                            <svg viewBox="0 0 24 24" fill="none"
                                 stroke="currentColor" stroke-width="2"
                                 stroke-linecap="round"
                                 stroke-linejoin="round">
                                <rect x="3" y="3" width="7" height="7" rx="1"/>
                                <rect x="14" y="3" width="7" height="7" rx="1"/>
                                <rect x="3" y="14" width="7" height="7" rx="1"/>
                                <rect x="14" y="14" width="7" height="7" rx="1"/>
                            </svg>
                        </button>
                        <button type="button"
                                class="o_owl_catalog_view_btn"
                                t-att-class="state.viewMode === 'list' ? 'o_owl_catalog_view_btn_active' : ''"
                                t-on-click="() => this._setView('list')"
                                aria-label="List view"
                                title="List view">
                            <svg viewBox="0 0 24 24" fill="none"
                                 stroke="currentColor" stroke-width="2"
                                 stroke-linecap="round"
                                 stroke-linejoin="round">
                                <line x1="4" y1="6" x2="20" y2="6"/>
                                <line x1="4" y1="12" x2="20" y2="12"/>
                                <line x1="4" y1="18" x2="20" y2="18"/>
                            </svg>
                        </button>
                    </div>
                </div>

                <nav t-if="state.filterMode === 'tabs'"
                     class="o_owl_catalog_tabs"
                     role="tablist"
                     aria-label="Filter by category">
                    <t t-foreach="getCategoryTabs()" t-as="tab"
                       t-key="tab.key">
                        <button type="button"
                                class="o_owl_catalog_tab"
                                t-att-class="state.activeCategory === tab.key ? 'o_owl_catalog_tab_active' : ''"
                                t-on-click="() => this._setCategory(tab.key)"
                                t-on-keydown="(ev) => this._onTabKeydown(ev, tab.key)"
                                role="tab"
                                t-att-aria-selected="state.activeCategory === tab.key ? 'true' : 'false'"
                                t-att-tabindex="state.activeCategory === tab.key ? '0' : '-1'">
                            <span class="o_owl_catalog_tab_label"
                                  t-esc="tab.key"/>
                            <sup class="o_owl_catalog_tab_count"
                                 t-esc="tab.count"/>
                        </button>
                    </t>
                </nav>

                <div class="o_owl_modal_body o_owl_catalog_body">
                    <p class="o_owl_catalog_count">
                        Showing
                        <strong t-esc="getFilteredItems().length"/>
                        of
                        <strong t-esc="props.catalog.length"/>
                        cabinet families
                    </p>

                    <t t-if="getFilteredItems().length === 0">
                        <div class="o_owl_catalog_empty">
                            <div class="o_owl_catalog_empty_icon"
                                 t-out="searchIcon()"/>
                            <strong>No cabinets match this search.</strong>
                            <p>Try a different keyword or clear the filter.</p>
                            <button type="button"
                                    class="o_owl_catalog_empty_reset"
                                    t-on-click="_resetFilters">
                                Reset filters
                            </button>
                        </div>
                    </t>
                    <t t-else="">
                        <div class="o_owl_catalog_grid"
                             t-att-class="state.viewMode === 'list' ? 'o_owl_catalog_grid_list' : ''">
                            <article t-foreach="getFilteredItems()"
                                     t-as="item"
                                     t-key="item.id"
                                     class="o_owl_catalog_card"
                                     t-att-class="state.lastAddedSku === item.sku ? 'o_owl_catalog_card_added' : ''">
                                <!-- 2026-06-02 card layout v3 — three explicit
                                     regions so list mode can flex-row cleanly:
                                       1) icon          (flex:0 0 auto, fixed)
                                       2) content       (flex:1 1 auto, min-width:0)
                                       3) aside         (flex:0 0 auto, price+actions)
                                     The flexible middle is what stops the
                                     per-character wrap bug in list mode.
                                     Grid mode places these into a 2-col
                                     grid: icon|content on top, aside spans full
                                     width below. -->
                                <div class="o_owl_catalog_card_icon"
                                     t-out="cabinetIcon(item.icon)"/>
                                <div class="o_owl_catalog_card_content">
                                    <div class="o_owl_catalog_card_titles">
                                        <span t-if="item.category"
                                              class="o_owl_catalog_card_badge"
                                              t-esc="item.category"/>
                                        <h4 class="o_owl_catalog_card_name"
                                            t-esc="item.name"/>
                                        <div class="o_owl_catalog_card_sku"
                                             t-esc="item.sku"/>
                                    </div>
                                    <p t-if="item.description"
                                       class="o_owl_catalog_card_desc"
                                       t-esc="item.description"/>
                                    <div t-if="item.dimensions"
                                         class="o_owl_catalog_card_dims">
                                        <svg viewBox="0 0 24 24" fill="none"
                                             stroke="currentColor"
                                             stroke-width="1.5"
                                             stroke-linecap="round"
                                             stroke-linejoin="round"
                                             aria-hidden="true">
                                            <path d="M3 9h18M3 9v6m18-6v6M3 15h18"/>
                                            <line x1="7" y1="9" x2="7" y2="15"/>
                                            <line x1="12" y1="9" x2="12" y2="15"/>
                                            <line x1="17" y1="9" x2="17" y2="15"/>
                                        </svg>
                                        <span t-esc="item.dimensions"/>
                                    </div>
                                </div>
                                <div class="o_owl_catalog_card_aside">
                                    <div class="o_owl_catalog_card_price_row">
                                        <t t-if="hasChannelDiscount(item)">
                                            <span class="o_owl_catalog_card_price_strike"
                                                  t-esc="fmtUsd(item.list_price)"/>
                                            <span class="o_owl_catalog_card_price"
                                                  t-esc="fmtUsd(item.channel_price)"/>
                                            <span class="o_owl_catalog_card_channel_lbl">your price<t t-if="props.channelLabel"> · <t t-esc="channelLabelShort()"/></t></span>
                                        </t>
                                        <t t-else="">
                                            <span class="o_owl_catalog_card_price"
                                                  t-esc="fmtUsd(item.list_price)"/>
                                            <span class="o_owl_catalog_card_price_lbl">list</span>
                                        </t>
                                    </div>
                                    <div class="o_owl_catalog_card_actions">
                                        <div class="o_owl_catalog_qty"
                                             role="group"
                                             aria-label="Quantity">
                                            <button type="button"
                                                    class="o_owl_catalog_qty_btn"
                                                    t-att-disabled="props.busy or getQty(item.sku) &lt;= 1"
                                                    t-on-click="() => this._decQty(item.sku)"
                                                    aria-label="Decrease quantity">−</button>
                                            <input type="number" min="1"
                                                   class="o_owl_catalog_qty_input"
                                                   t-att-value="getQty(item.sku)"
                                                   t-on-input="(ev) => this._setQty(item.sku, ev.target.value)"
                                                   aria-label="Quantity"/>
                                            <button type="button"
                                                    class="o_owl_catalog_qty_btn"
                                                    t-att-disabled="props.busy"
                                                    t-on-click="() => this._incQty(item.sku)"
                                                    aria-label="Increase quantity">+</button>
                                        </div>
                                        <button type="button"
                                                class="o_owl_catalog_add_btn"
                                                t-att-class="state.lastAddedSku === item.sku ? 'o_owl_catalog_add_btn_added' : ''"
                                                t-att-disabled="props.busy || state.addingSku || state.lastAddedSku === item.sku"
                                                t-on-click="() => this._addItem(item)">
                                            <t t-if="state.lastAddedSku === item.sku">
                                                <svg viewBox="0 0 24 24"
                                                     fill="none"
                                                     stroke="currentColor"
                                                     stroke-width="2"
                                                     stroke-linecap="round"
                                                     stroke-linejoin="round"
                                                     aria-hidden="true">
                                                    <path d="M4 12l5 5L20 6"/>
                                                </svg>
                                                Added
                                            </t>
                                            <t t-elif="state.addingSku === item.sku">Adding…</t>
                                            <t t-else="">Add</t>
                                        </button>
                                    </div>
                                </div>
                            </article>
                        </div>
                    </t>

                    <p t-if="props.busy"
                       class="o_owl_catalog_busy"
                       role="status" aria-live="polite">
                        Adding cabinet to your order…
                    </p>
                </div>
            </div>
        </div>
    `;
    static props = {
        catalog: Array,
        open: Boolean,
        busy: Boolean,
        onClose: Function,
        onPick: Function,
        // 2026-06-02 — channel pricelist label for the optional
        // channel-pricing badge. Empty string for retail walk-in.
        channelLabel: { type: String, optional: true },
        // Phase 3 Sprint C1 — when set to a zone code (base_run,
        // wall, tall, etc.) the picker pre-filters to the matching
        // family group on open. null means show everything.
        zoneFilter: {
            type: [String, { value: null }], optional: true,
        },
        // UX 2026-06-22 — live count of cabinets already on the order,
        // surfaced in the modal header so the user knows when their
        // click actually added a line. null hides the chip.
        cartCount: {
            type: [Number, { value: null }], optional: true,
        },
    };

    // Module-level helpers exposed as instance fields so the template
    // can resolve them against `this`.
    fmtUsd = fmtUsd;
    cabinetIcon = cabinetIcon;

    // 2026-06-02 channel-price helpers.
    //
    // hasChannelDiscount(item)  True when item.channel_price differs
    //                           from item.list_price (i.e. the visiting
    //                           partner is on a non-retail pricelist
    //                           AND the cabinet has a resolvable
    //                           channel price). Drives the dual-price
    //                           treatment in the card.
    //
    // channelLabelShort()       Compact label shown next to the
    //                           channel price. Strips the parenthesised
    //                           discount tail of pricelist names so
    //                           "Contractor Tier 3 (-35%)" renders
    //                           as "TIER 3 -35%" in 11px monospace
    //                           on the card. Falls back to the empty
    //                           string when no channel applies.
    hasChannelDiscount(item) {
        if (item.channel_price == null || item.list_price == null) {
            return false;
        }
        // Use a small epsilon for float drift (currency rounding).
        return Math.abs(item.list_price - item.channel_price) > 0.005;
    }

    channelLabelShort() {
        const label = (this.props.channelLabel || "").trim();
        if (!label) return "";
        // Pricelist names look like "Contractor Tier 3 (-35%)" or
        // "Dealer (-50%)". Pull out the discount tail if present;
        // otherwise show the whole label upper-cased.
        const m = label.match(/\(([^)]+)\)/);
        if (m) return m[1].toUpperCase();
        return label.toUpperCase();
    }

    setup() {
        this.state = useState({
            // 2026-06-02 redesign — reactive filter + view state.
            searchQuery: "",
            // UX 2026-06-22: default to "Base" — base cabinets are the
            // most common starting point of a kitchen order, so opening
            // the catalog already on that filter gets the trade user
            // straight to the cards they want. zoneFilter (from a
            // "+ Add to <zone>" entry point) still wins over this in
            // setup() below; the "All" tab remains one click away.
            activeCategory: "Base",
            viewMode: "grid",          // 'grid' | 'list'
            // 2026-06-02 filter v2 — UI variant for the category
            // filter. 'tabs' renders the underlined single-row tab
            // bar (default); 'select' renders a compact <select>
            // dropdown inline in the toolbar instead. Both call
            // _setCategory so the rest of the component doesn't
            // know which is showing. TO SWITCH DEFAULT: change the
            // initial value here to "select".
            filterMode: "tabs",        // 'tabs' | 'select'
            qtyBySku: {},              // sku -> integer qty (default 1)
            // UX bugfix 2026-06-23: track which SKU is mid-add (replaces
            // the old non-reactive this._adding). Reactive so the button
            // can both visually feedback ("Adding…") and be t-att-disabled
            // through the entire click→server→render window — the lag
            // between server response and parent state.lines refresh
            // was tricking users into double-clicking and creating
            // duplicate sale.order.line rows.
            addingSku: null,
            lastAddedSku: null,        // briefly set after successful add
        });
        // Pre-bind handlers passed by plain reference (same pattern as
        // OrderBuilder — OWL 2 in this Odoo build doesn't preserve
        // `this` for non-arrow method props).
        this._onBackdropClick = this._onBackdropClick.bind(this);
        this._onSearch = this._onSearch.bind(this);
        this._resetFilters = this._resetFilters.bind(this);
        // P2 bugfix 2026-06-22: a pre-bound close handler we own (rather
        // than passing `props.onClose` straight to the template's
        // t-on-click) so the click hits a stable function reference
        // across re-renders. Also lets us gate on `props.busy` here
        // before forwarding — that ensures the × never opens-then-
        // -immediately-closes mid-add.
        this._onCloseClick = this._onCloseClick.bind(this);
        this._onKeydown = this._onKeydown.bind(this);

        // Phase 3 Sprint C1 — react to zoneFilter prop changes.
        // When OrderBuilder opens the picker with a zone pre-filter
        // (e.g. user clicked "+ Add to Wall"), pre-select the matching
        // category tab so the first cards the user sees are wall
        // cabinets. Falls back to "Base" (UX 2026-06-22 default) for
        // unknown / null zones.
        const initial = this._zoneToCategory(this.props.zoneFilter);
        if (initial) this.state.activeCategory = initial;

        // P2 bugfix 2026-06-22 — Escape-key handler attached at the
        // document level so it works regardless of which child element
        // currently has focus. Single global listener for the whole
        // lifetime of the component; the `props.open` guard inside
        // _onKeydown makes it a no-op when the modal is closed.
        onMounted(() => {
            document.addEventListener("keydown", this._onKeydown);
        });
        onWillUnmount(() => {
            document.removeEventListener("keydown", this._onKeydown);
        });
    }

    /** Phase 3 Sprint C1 — map a zone code to a CatalogPicker category
     *  name. Returns null when the zone doesn't translate (the
     *  catalog stays unfiltered). The category names match what
     *  catalog items declare as item.category in
     *  kitchen_planner_state's response. */
    _zoneToCategory(zoneCode) {
        if (!zoneCode) return null;
        const map = {
            base_run: "Base",
            wall:     "Wall",
            tall:     "Tall",
            island:   "Base",
            accessory:"Accessory",
        };
        return map[zoneCode] || null;
    }

    // ------------------------------------------------------------------
    // Static module-level icon for the empty state. Returns markup so
    // OWL t-out renders it as inline SVG.
    // ------------------------------------------------------------------
    searchIcon() {
        return markup(`<svg viewBox="0 0 48 48" fill="none"
                            stroke="currentColor" stroke-width="1.5"
                            stroke-linecap="round" stroke-linejoin="round">
            <circle cx="22" cy="22" r="13"/>
            <line x1="40" y1="40" x2="31" y2="31"/>
        </svg>`);
    }

    // ------------------------------------------------------------------
    // Derived selectors — filter pipeline.
    //
    //   buildDomain()        Returns the current filter criteria as a
    //                        plain object {category, searchQuery}.
    //                        Pure function of state — no I/O.
    //
    //   applyFilters()       Filters items by the criteria object.
    //                        Today runs purely client-side over the
    //                        already-loaded 12-record catalog.
    //
    //   getFilteredItems()   Thin wrapper composing build + apply;
    //                        the template only ever calls this.
    //
    // SCALE NOTE: once the catalog grows past a few dozen SKUs,
    // filtering should move into the ORM domain with pagination.
    // The transition is a one-method swap: rewrite buildDomain() to
    // emit a real Odoo polish-notation domain
    // ([['category','=',x],'|',['name','ilike',q],['sku','ilike',q]])
    // and push it as a `domain` arg to /southbrook/api/kitchen-
    // planner/state — the controller evaluates server-side via
    // search_read with limit/offset pagination. applyFilters()
    // becomes a debounced fetch instead of an in-memory filter. The
    // template + caller stay untouched: they only know about
    // getFilteredItems().
    // ------------------------------------------------------------------

    // Logical catalog order for the tab bar. Not alphabetical —
    // it mirrors how a customer thinks about a kitchen: base cabinets
    // first (the dominant family), then walls, talls, drawers,
    // vanity, and Extras last. 'All' is always position 0.
    //
    // Categories that arrive from the controller but aren't in this
    // table (e.g. a future "Worktops" split) fall through to the end
    // alphabetically so the tab row stays deterministic.
    static CATEGORY_ORDER = [
        "All",
        "Base",
        "Wall",
        "Tall",
        "Drawer",
        "Vanity",
        "Extras",
    ];

    getCategoryTabs() {
        const counts = { All: this.props.catalog.length };
        for (const item of this.props.catalog) {
            const c = item.category || "Extras";
            counts[c] = (counts[c] || 0) + 1;
        }
        const ORDER = this.constructor.CATEGORY_ORDER;
        const orderedKeys = Object.keys(counts).sort((a, b) => {
            const ai = ORDER.indexOf(a);
            const bi = ORDER.indexOf(b);
            if (ai !== -1 && bi !== -1) return ai - bi;
            if (ai !== -1) return -1;
            if (bi !== -1) return 1;
            return a.localeCompare(b);
        });
        return orderedKeys.map((k) => ({ key: k, count: counts[k] }));
    }

    buildDomain() {
        // Plain-object criteria. `category` is null when 'All' is
        // active (no category filter). `searchQuery` is the trimmed
        // search input — empty string when none.
        const cat = this.state.activeCategory;
        return {
            category: (cat && cat !== "All") ? cat : null,
            searchQuery: (this.state.searchQuery || "").trim(),
        };
    }

    applyFilters(items, domain) {
        const { category, searchQuery } = domain;
        const q = (searchQuery || "").toLowerCase();
        // Fast path: no criteria → return the list unchanged.
        if (!category && !q) return items;
        return items.filter((item) => {
            // UX bugfix 2026-06-23: when a search query is active,
            // ignore the category filter so users searching "SB-TALL"
            // find tall cabinets even when the Wall tab is selected.
            // Previously search was AND-ed with the category → users
            // hit "No cabinets match" and didn't realize the result
            // was hiding behind a tab they hadn't selected. The
            // category state is preserved; clearing the search returns
            // the user to their category view.
            if (category && !q) {
                const c = item.category || "Extras";
                if (c !== category) return false;
            }
            if (q) {
                const name = (item.name || "").toLowerCase();
                const sku = (item.sku || "").toLowerCase();
                if (!name.includes(q) && !sku.includes(q)) return false;
            }
            return true;
        });
    }

    getFilteredItems() {
        return this.applyFilters(this.props.catalog, this.buildDomain());
    }

    getQty(sku) {
        const q = this.state.qtyBySku[sku];
        return q && q > 0 ? q : 1;
    }

    // ------------------------------------------------------------------
    // Handlers.
    // ------------------------------------------------------------------

    _onBackdropClick() {
        if (!this.props.busy) {
            this.props.onClose();
        }
    }

    // P2 bugfix 2026-06-22: stable × handler. Important: stop event
    // propagation so it doesn't bubble to the backdrop and double-fire
    // (some browsers fire both with overlapping z-stacks), and prevent
    // default so any wrapping form/anchor doesn't navigate.
    _onCloseClick(ev) {
        if (ev) {
            ev.stopPropagation();
            ev.preventDefault();
        }
        if (this.props.busy) return;
        this.props.onClose();
    }

    // P2 bugfix 2026-06-22: Escape key closes the modal. Wired via the
    // global document keydown listener attached only while the modal is
    // open (see onPatched / onMounted below).
    _onKeydown(ev) {
        if (ev.key === "Escape" && this.props.open && !this.props.busy) {
            this.props.onClose();
        }
    }

    _onSearch(ev) {
        this.state.searchQuery = ev.target.value;
    }

    _setCategory(category) {
        this.state.activeCategory = category;
    }

    // Arrow-key navigation between category tabs. Follows the WAI-ARIA
    // tablist pattern: ArrowLeft / ArrowRight cycle through tabs and
    // activate immediately (single-select filter); Home / End jump to
    // the first / last tab. Tab key still moves focus out of the tab
    // bar to the next focusable control, since only the active tab
    // has tabindex=0.
    _onTabKeydown(ev, currentKey) {
        const tabs = this.getCategoryTabs().map((t) => t.key);
        const idx = tabs.indexOf(currentKey);
        if (idx < 0) return;
        let next = null;
        if (ev.key === "ArrowRight") {
            next = tabs[(idx + 1) % tabs.length];
        } else if (ev.key === "ArrowLeft") {
            next = tabs[(idx - 1 + tabs.length) % tabs.length];
        } else if (ev.key === "Home") {
            next = tabs[0];
        } else if (ev.key === "End") {
            next = tabs[tabs.length - 1];
        }
        if (next !== null) {
            ev.preventDefault();
            this._setCategory(next);
        }
    }

    _setView(mode) {
        if (mode === "grid" || mode === "list") {
            this.state.viewMode = mode;
        }
    }

    _resetFilters() {
        this.state.searchQuery = "";
        this.state.activeCategory = "All";
    }

    _setQty(sku, raw) {
        const n = parseInt(raw, 10);
        this.state.qtyBySku[sku] = Number.isFinite(n) && n > 0 ? n : 1;
    }

    _incQty(sku) {
        this.state.qtyBySku[sku] = this.getQty(sku) + 1;
    }

    _decQty(sku) {
        const next = this.getQty(sku) - 1;
        this.state.qtyBySku[sku] = next > 0 ? next : 1;
    }

    async _addItem(item) {
        // UX bugfix 2026-06-23: reactive addingSku replaces the old
        // non-reactive this._adding. The previous guard was reset as
        // soon as props.onPick resolved, but parent state.lines didn't
        // refresh until the next render tick — during that gap, a user
        // who clicked again (because the UI showed no change) hit a
        // re-armed guard. Result: duplicate lines (e.g. two qty=2 lines
        // for the same cabinet, totalling qty 4). Tying the guard to
        // the same 1500ms timeout that clears the "Added" badge means
        // the button stays disabled + showing visual feedback through
        // the parent re-render, eliminating the race.
        if (this.props.busy || this.state.addingSku) return;
        this.state.addingSku = item.sku;
        const qty = this.getQty(item.sku);
        // Reuses the parent's existing add-line path — onPick now
        // accepts (templateId, qty, label). The original 1- and 2-arg
        // call shapes still work because the new args are optional on
        // both sides.
        try {
            await this.props.onPick(item.id, qty, item.name || item.sku);
            this.state.lastAddedSku = item.sku;
            // Clear both the 'Added' indicator AND the in-flight lock
            // after 1.5s — single timer keeps the visual feedback
            // window and the click guard in lockstep.
            setTimeout(() => {
                if (this.state.lastAddedSku === item.sku) {
                    this.state.lastAddedSku = null;
                }
                if (this.state.addingSku === item.sku) {
                    this.state.addingSku = null;
                }
            }, 1500);
        } catch (e) {
            // Reset immediately on error so the user can retry. Parent
            // surfaces the message via state.error + toast.
            this.state.addingSku = null;
        }
    }
}

// ----------------------------------------------------------------------
// OrderBuilder root template. Phase 3 polish splits each section into
// its own component file under static/src/js/components/.
// ----------------------------------------------------------------------

const TEMPLATE = xml`
    <div class="o_southbrook_owl_root">

        <!-- P1 / UX 2026-06-22: toast stack. Lives outside the
             loading/error/loaded t-if chain so a confirmation that fires
             during a background re-render stays mounted. role=status +
             aria-live=polite so screen readers announce each toast
             without stealing focus. -->
        <div class="o_owl_toast_stack" role="status" aria-live="polite"
             t-if="state.toasts.length">
            <div t-foreach="state.toasts" t-as="toast" t-key="toast.id"
                 t-attf-class="o_owl_toast o_owl_toast_{{ toast.kind }}">
                <span class="o_owl_toast_text" t-esc="toast.text"/>
                <button type="button" class="o_owl_toast_close"
                        t-on-click="() => this._dismissToast(toast.id)"
                        aria-label="Dismiss">×</button>
            </div>
        </div>

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
            <!-- G11 + G12 + G13 — CatalogPicker modal. Rendered inside
                 the loaded branch because the catalog action targets
                 state.order. (Originally placed between t-elif and
                 t-else, which broke the QWeb chain — OWL 2 reports
                 'OWL mount failed: t-elif and t-else directives must
                 be preceded by a t-if or t-elif directive' when a
                 sibling sits in the middle. See bug 2026-06-01.)
                 Visibility is driven by state.ui.catalog_open. -->
            <!-- Method props are pre-bound to 'this' in setup() so
                 they can be passed by plain reference without losing
                 context. Neither OWL's .bind directive nor arrow
                 wrappers carry 'this' correctly in this Odoo's OWL
                 version (verified by user devtools 2026-06-01).
                 setup() bind is the working pattern. -->
            <CatalogPicker catalog="state.catalog"
                           open="state.ui.catalog_open"
                           busy="state.catalog_busy"
                           channelLabel="state.channel_label"
                           zoneFilter="state.ui.catalog_zone_filter"
                           cartCount="state.lines.length"
                           onClose="_closeCatalog"
                           onPick="_onPickCabinet"/>

            <!-- Chrome (T2C7) — banner + titlebar + stages. -->
            <IllustrativeBanner show="true"/>
            <OrderTitlebar order="state.order"
                           mode="props.mode || 'dealer'"/>
            <StagePipeline order="state.order"
                           mode="props.mode || 'dealer'"/>

            <!-- HeaderStrip (T2C6) — reads order header from state. -->
            <HeaderStrip order="state.order"/>

            <!-- TabBar (T2C8) — client-side panel switch. -->
            <TabBar tabs="_tabs"
                    activeTab="state.ui.current_tab"
                    onTabChange.bind="_setActiveTab"/>

            <!-- Tab panels. T2C9 fills Lines. T2C10-11 fill the rest.
                 Phase 2.B prepends the Room Setup panel as the chain
                 head; lines/3D/etc are downstream t-elif siblings. -->
            <div t-if="state.ui.current_tab === 'room_setup'"
                 class="o_owl_tab_panel sb-room-setup-panel"
                 role="tabpanel" aria-labelledby="o_owl_tab_room_setup"
                 tabindex="0">
                <t t-if="state.room">
                    <!-- Phase 4 — Room Setup panel header bar. Hosts the
                         persistent unit toggle (mm | ft/in). The toggle
                         POSTs /room/<rid>/update and on success refreshes
                         state.room so every length label re-renders in
                         the new unit. -->
                    <div class="sb-room-panel-header">
                        <div class="sb-room-unit-toggle"
                             role="group"
                             aria-label="Length units">
                            <span class="sb-room-unit-toggle-label">Units:</span>
                            <button type="button"
                                    class="sb-room-unit-toggle-btn"
                                    t-att-class="(state.room.unit_preference || 'mm') === 'mm' ? 'sb-room-unit-toggle-btn--active' : ''"
                                    t-att-aria-pressed="(state.room.unit_preference || 'mm') === 'mm' ? 'true' : 'false'"
                                    t-att-disabled="state.unit_saving"
                                    t-on-click="() => this._onUnitToggle('mm')">
                                mm
                            </button>
                            <button type="button"
                                    class="sb-room-unit-toggle-btn"
                                    t-att-class="(state.room.unit_preference || 'mm') === 'imperial' ? 'sb-room-unit-toggle-btn--active' : ''"
                                    t-att-aria-pressed="(state.room.unit_preference || 'mm') === 'imperial' ? 'true' : 'false'"
                                    t-att-disabled="state.unit_saving"
                                    t-on-click="() => this._onUnitToggle('imperial')">
                                ft/in
                            </button>
                        </div>
                    </div>

                    <!-- Phase 4 — celebratory state when all 5 steps
                         complete. Replaces the checklist so the user has
                         a clear "you can move on" signal. -->
                    <t t-if="_allStepsComplete()">
                        <div class="sb-room-complete-card">
                            <div class="sb-room-complete-icon" aria-hidden="true">✓</div>
                            <div class="sb-room-complete-body">
                                <h3 class="sb-room-complete-title">Room Complete</h3>
                                <p class="sb-room-complete-text">
                                    Your room is fully set up — all
                                    cabinets placed, no conflicts.
                                </p>
                            </div>
                            <button type="button"
                                    class="sb-room-complete-cta"
                                    t-on-click="() => this._setActiveTab('lines')">
                                Continue to Order Lines →
                            </button>
                        </div>
                    </t>
                    <t t-else="">
                        <!-- Phase 4 — 5-step progress checklist. Each
                             step shows ✓ when complete, an empty bubble
                             otherwise, plus a → CTA link on incomplete
                             steps that dispatches via
                             _onProgressStepClick(step.key). -->
                        <ol class="sb-room-progress" aria-label="Room setup progress">
                            <li t-foreach="_progressSteps()"
                                t-as="step"
                                t-key="step.key"
                                class="sb-room-progress-step"
                                t-att-class="step.complete ? 'sb-room-progress-step--done' : (step.optional ? 'sb-room-progress-step--optional' : 'sb-room-progress-step--todo')">
                                <span class="sb-room-progress-bubble" aria-hidden="true">
                                    <t t-if="step.complete">✓</t>
                                    <t t-else=""></t>
                                </span>
                                <span class="sb-room-progress-label" t-esc="step.label"/>
                                <button t-if="!step.complete"
                                        type="button"
                                        class="sb-room-progress-cta"
                                        t-att-aria-label="step.hint"
                                        t-on-click="() => this._onProgressStepClick(step.key)">→</button>
                            </li>
                        </ol>
                    </t>

                    <!-- Summary card + per-wall cards -->
                    <div class="sb-room-summary">
                        <h2 class="sb-room-title">
                            <t t-esc="state.room.name"/>
                        </h2>
                        <div class="sb-room-meta">
                            <span class="sb-room-shape">
                                <t t-esc="_humanShape(state.room.layout_shape)"/>
                            </span>
                            <span class="sb-room-linear">
                                <t t-esc="_humanLen(state.room.total_linear_mm)"/> linear
                            </span>
                            <span class="sb-room-walls">
                                <t t-esc="state.room.walls.length"/> wall(s)
                            </span>
                            <span t-if="state.room.has_plumbing"
                                  class="sb-room-plumbing-flag">Plumbing</span>
                        </div>
                    </div>
                    <div class="sb-room-walls-grid">
                        <t t-foreach="state.room.walls" t-as="wall" t-key="wall.id">
                            <div class="sb-room-wall-card"
                                 t-att-class="wall.has_conflicts ? 'sb-room-wall-card--conflict' : ''">
                                <header>
                                    <strong t-esc="wall.name"/>
                                    <span class="sb-room-wall-len">
                                        <t t-esc="_humanLen(wall.length_mm)"/>
                                    </span>
                                </header>
                                <div class="sb-room-wall-bar"
                                     t-att-title="_humanLen(wall.used_mm) + ' / ' + _humanLen(wall.length_mm) + ' used'">
                                    <div class="sb-room-wall-bar-fill"
                                         t-att-style="'width:' + _capPct(wall) + '%'"></div>
                                </div>
                                <footer class="sb-room-wall-cap">
                                    <span><t t-esc="_humanLen(wall.used_mm)"/> used</span>
                                    <span class="sb-room-wall-rem"
                                          t-att-class="wall.remaining_mm &lt; 0 ? 'sb-room-wall-rem--over' : ''">
                                        <t t-esc="_humanLen(wall.remaining_mm)"/> left
                                    </span>
                                </footer>
                                <ul t-if="wall.constraints.length" class="sb-room-constraint-chips">
                                    <li t-foreach="wall.constraints" t-as="c" t-key="c.id"
                                        class="sb-room-chip"
                                        t-att-data-type="c.constraint_type">
                                        <t t-esc="_humanConstraint(c.constraint_type)"/>
                                        <small>@ <t t-esc="_humanLen(c.distance_from_left_mm)"/></small>
                                    </li>
                                </ul>
                            </div>
                        </t>
                    </div>
                </t>
                <t t-else="">
                    <div class="sb-room-empty">
                        <h2>No room configured yet</h2>
                        <p>
                            Add room dimensions, walls, and constraints to anchor
                            this order to a physical space. Cabinets you add can
                            then be placed against walls with live conflict
                            detection.
                        </p>
                        <button class="o_owl_add_cabinet_btn sb-room-setup-cta"
                                t-on-click="_openRoomSetupWizard">
                            Set Up Room
                        </button>
                        <p class="sb-room-empty-note">
                            <small>You can still add cabinets and design without
                                   setting up a room — it just unlocks the Room
                                   Layout tab in Phase 3.</small>
                        </p>
                    </div>
                </t>
            </div>
            <!-- Phase 3.B — Room Layout tab. Top-down floor plan.
                 Phase 3.C.2a adds three click affordances via the
                 callbacks below; drag (3.C.2b) + elevation (3.C.2c)
                 remain deferred. -->
            <div t-elif="state.ui.current_tab === 'room_layout'"
                 class="o_owl_tab_panel sb-room-plan-panel"
                 role="tabpanel" aria-labelledby="o_owl_tab_room_layout"
                 tabindex="0">
                <RoomLayoutTab room="state.room"
                               lines="state.lines"
                               unitPreference="(state.room &amp;&amp; state.room.unit_preference) || 'mm'"
                               onCabinetClick="_onPlanCabinetClick"
                               onGapClick="_onPlanGapClick"
                               onAssignFromSidebar="_onPlanAssignClick"
                               onCabinetDragEnd="_onPlanCabinetDragEnd"
                               onWallResizeEnd="_onPlanWallResizeEnd"/>
            </div>
            <div t-elif="state.ui.current_tab === 'lines'"
                 class="o_owl_tab_panel o_owl_panel_lines"
                 role="tabpanel" aria-labelledby="o_owl_tab_lines"
                 tabindex="0">
                <!-- T2C9 — multi-zone line grid. G11 empty-state CTA. -->
                <t t-if="state.lines.length === 0">
                    <div class="o_owl_panel_placeholder o_owl_lines_empty">
                        <strong>Your project is empty.</strong>
                        <p>
                            Add cabinets from the catalog to start
                            configuring your kitchen. Pick a family
                            (base, wall, tall, drawer bank…), then
                            refine dimensions, finish, and door style
                            line by line.
                        </p>
                        <button class="o_owl_add_cabinet_btn o_owl_add_cabinet_lg"
                                t-on-click="_openCatalog">
                            + Add Your First Cabinet
                        </button>
                    </div>
                </t>
                <t t-else="">
                    <div class="o_owl_lines_topbar">
                        <button class="o_owl_add_cabinet_btn"
                                t-on-click="_openCatalog">
                            + Add Another Cabinet
                        </button>
                        <span class="o_owl_lines_count">
                            <t t-esc="state.lines.length"/>
                            <t t-if="state.lines.length === 1"> cabinet</t>
                            <t t-else=""> cabinets</t>
                            on this order
                        </span>
                    </div>

                    <!-- Phase 3.D — collapsible warning banner. Renders
                         only when _warnings() returns at least one entry.
                         Headline shows the count; expand/collapse toggles
                         the bullet list. Each bullet stays static text in
                         3.D; 3.C will wire click → zone/wall focus. -->
                    <t t-set="warnings" t-value="_warnings()"/>
                    <div t-if="warnings.length"
                         class="sb-room-warn-banner"
                         t-att-class="state.ui.warnings_expanded ? 'sb-room-warn-banner--open' : ''">
                        <button type="button"
                                class="sb-room-warn-banner-head"
                                t-on-click="_toggleWarnings"
                                t-att-aria-expanded="state.ui.warnings_expanded ? 'true' : 'false'">
                            <span class="sb-room-warn-icon" aria-hidden="true">⚠</span>
                            <span class="sb-room-warn-headline">
                                <t t-esc="warnings.length"/>
                                <t t-if="warnings.length === 1"> issue found</t>
                                <t t-else=""> issues found</t>
                            </span>
                            <span class="sb-room-warn-chevron" aria-hidden="true">
                                <t t-if="state.ui.warnings_expanded">▾</t>
                                <t t-else="">▸</t>
                            </span>
                        </button>
                        <ul t-if="state.ui.warnings_expanded"
                            class="sb-room-warn-list">
                            <li t-foreach="warnings" t-as="w" t-key="w_index"
                                class="sb-room-warn-item"
                                t-esc="w"/>
                        </ul>
                    </div>

                    <!-- onSelectLine / onLineSaved are pre-bound in
                         setup() so plain-reference props carry 'this'
                         correctly. -->
                    <ZoneGroup t-foreach="state.zones"
                               t-as="zone"
                               t-key="zone.code"
                               zone="zone"
                               lines="_linesForZone(zone.code)"
                               selectedLineId="state.ui.selected_line_id"
                               onSelectLine="_setSelectedLine"
                               onLineSaved="_onLineSaved"
                               onAddToZone="_onAddToZone"
                               issuesForLine="_issuesForLine"
                               room="state.room"
                               unitPreference="(state.room &amp;&amp; state.room.unit_preference) || 'mm'"/>
                </t>
            </div>
            <div t-elif="state.ui.current_tab === 'kitchen3d'"
                 class="o_owl_tab_panel o_owl_panel_kitchen3d"
                 role="tabpanel" aria-labelledby="o_owl_tab_kitchen3d"
                 tabindex="0">
                <KitchenViewport orderId="props.orderId"
                                 payloadVersion="state.payload_version"
                                 onLineSelected.bind="_onKitchen3dLineSelected"/>
            </div>
            <div t-elif="state.ui.current_tab === 'bom'"
                 class="o_owl_tab_panel o_owl_panel_bom"
                 role="tabpanel" aria-labelledby="o_owl_tab_bom"
                 tabindex="0">
                <BoMPreview rollup="state.bom_rollup" lines="state.lines"/>
            </div>
            <div t-elif="state.ui.current_tab === 'validation'"
                 class="o_owl_tab_panel o_owl_panel_validation"
                 role="tabpanel" aria-labelledby="o_owl_tab_validation"
                 tabindex="0">
                <ValidationStrip issues="state.validation"/>
            </div>
            <div t-elif="state.ui.current_tab === 'history'"
                 class="o_owl_tab_panel o_owl_panel_history"
                 role="tabpanel" aria-labelledby="o_owl_tab_history"
                 tabindex="0">
                <!-- Phase 3 Sprint C3 — NF6 parent-order chain.
                     state.order.history_chain is newest-first, each
                     entry: {id, name, version, state, amount_total,
                     date_order, is_current}. Empty list for v1
                     orders that were never duplicated. -->
                <t t-if="(state.order.history_chain || []).length &lt;= 1">
                    <p class="o_owl_panel_placeholder">
                        <strong>No prior versions.</strong>
                        This is the first version of this order.
                        If a sales rep duplicates it via the backend
                        ("Duplicate as Draft"), the prior version
                        appears here as v1, this one becomes v2, etc.
                    </p>
                </t>
                <ol t-else="" class="o_owl_history_chain">
                    <li t-foreach="state.order.history_chain || []"
                        t-as="entry" t-key="entry.id"
                        t-att-class="'o_owl_history_entry ' +
                                     (entry.is_current ? 'o_owl_history_current' : '') +
                                     ' o_owl_history_state_' + entry.state">
                        <div class="o_owl_history_version">
                            v<t t-esc="entry.version"/>
                        </div>
                        <div class="o_owl_history_body">
                            <div class="o_owl_history_name">
                                <a t-if="!entry.is_current"
                                   t-attf-href="/my/southbrook/order-builder/#{entry.id}"
                                   t-esc="entry.name"/>
                                <strong t-else="" t-esc="entry.name"/>
                                <span t-if="entry.is_current"
                                      class="o_owl_history_chip">
                                    Current
                                </span>
                            </div>
                            <div class="o_owl_history_meta">
                                <span t-esc="entry.state"/>
                                <span t-if="entry.date_order">
                                    · <t t-esc="entry.date_order.slice(0, 10)"/>
                                </span>
                                <span t-if="entry.amount_total">
                                    · <t t-esc="fmtUsd(entry.amount_total)"/>
                                </span>
                            </div>
                        </div>
                    </li>
                </ol>
            </div>
            <div t-elif="state.ui.current_tab === 'print'"
                 class="o_owl_tab_panel o_owl_panel_print"
                 role="tabpanel" aria-labelledby="o_owl_tab_print"
                 tabindex="0">
                <p class="o_owl_panel_placeholder">
                    <strong>Customer Print panel</strong> — Phase 3
                    polish embeds the Signature Spec Sheet PDF preview
                    (already QWeb-rendered by southbrook_estimating).
                </p>
            </div>

            <!-- T2C12 — FooterActions row -->
            <FooterActions order="state.order"
                           onAction.bind="_onFooterAction"
                           busy="state.action_busy"
                           mode="props.mode || 'dealer'"/>

            <div t-if="state.action_message" class="o_owl_action_msg"
                 t-esc="state.action_message"/>

            <p class="o_owl_status">
                Phase 2 Track 2 — 12 of 14 commits live.
                Commit 13 lands the customer-mode toggle; commit 14
                is the gate review with John.
            </p>

            <!-- Phase 2.C — Room Setup wizard overlay. Renders only
                 when the user clicks the "Set Up Room" CTA on the
                 Room Setup tab. Self-mounts as a fullscreen modal
                 above all OrderBuilder chrome. -->
            <RoomSetupWizard t-if="state.ui.wizard === 'room_setup'"
                             orderId="props.orderId"
                             onClose="_closeRoomSetupWizard"
                             onSubmitted="_onRoomSubmitted"/>

            <!-- Phase 3.C.2a — AssignToWallModal. Opened from the
                 Room Layout sidebar Assign... button. The line lookup
                 returns null when the line is gone (race after a
                 concurrent delete) — the t-if guard then hides the
                 modal cleanly. -->
            <AssignToWallModal t-if="state.ui.assigning &amp;&amp; _lineById(state.ui.assigning) &amp;&amp; state.room"
                               line="_lineById(state.ui.assigning)"
                               room="state.room"
                               unitPreference="(state.room &amp;&amp; state.room.unit_preference) || 'mm'"
                               onAssign="(wallId, posMm) => this._onAssignSubmit(state.ui.assigning, wallId, posMm)"
                               onCancel="_onAssignCancel"/>

            <!-- Phase 6.1 — GapRecommendModal. Opened from a gap-click
                 on the Room Layout floor plan. Shows top-3 cabinet
                 recommendations + a "Browse all" escape to the full
                 catalog. The catalog-fallback path inside
                 _onPlanGapClick covers RPC failures so the user is
                 never stranded if the recommend endpoint misbehaves. -->
            <GapRecommendModal t-if="state.ui.gapRecommend"
                               gapInfo="state.ui.gapRecommend"
                               recommendations="state.ui.gapRecommend.recommendations"
                               onPick="_onGapPickTemplate"
                               onBrowseAll="_onGapBrowseAll"
                               onCancel="_onGapCancel"/>
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
        TabBar,
        ZoneGroup,
        BoMPreview,
        ValidationStrip,
        FooterActions,
        KitchenViewport,
        CatalogPicker,
        RoomSetupWizard,
        RoomLayoutTab,
        // Phase 3.C.2a — fullscreen overlay opened by the Room Layout
        // sidebar's Assign... button. Mounted at OrderBuilder level so
        // it floats above the tab chrome (and survives a tab switch
        // mid-pick).
        AssignToWallModal,
        // Phase 6.1 — fullscreen overlay opened by Room Layout gap-
        // click; replaces the 3.C.2a direct-to-catalog flow with a top-
        // 3 recommendation list + Browse all fallback.
        GapRecommendModal,
    };
    static props = {
        orderId: { type: String, optional: true },
        orderName: { type: String, optional: true },
        // T2C13 — view mode. "dealer" (default) shows the full surface;
        // "customer" hides power-user tabs (BoM Preview, Validation,
        // History) and the dealer-only actions (Duplicate). Same root,
        // different visibility — per charter Q6 + Build Spec §2.3
        // "There must not be two configurators".
        mode: { type: String, optional: true },
    };

    setup() {
        this.state = useState({
            // P0 bugfix 2026-06-22: split "first-page-paint loading" from
            // "background poll loading". `loading` only flips true on the
            // very first _loadOrder(); the 5-second poll updates state in
            // place without ever showing the "Loading order…" card, so
            // CatalogPicker and other children keep their transient UI
            // state (search query, active category, scroll, modal-open).
            loading: false,
            initial_load: true,
            // Stable hash of the order payload — when an unchanged poll
            // response comes back, we skip the state write entirely so
            // OWL doesn't even reconcile (avoids any chance of resetting
            // child reactivity on a no-op).
            payload_hash: "",
            error: null,
            order: null,
            lines: [],
            zones: [],
            // P1 bugfix 2026-06-22: confirmation toasts. Each toast is
            // {id, text, kind: 'success'|'error'}; renders top-right and
            // auto-dismisses after ~3s via setTimeout.
            toasts: [],
            // T2C11 — BoM rollup + validation issues. Both populated
            // by /api/order/<id>. Default rollup matches the empty
            // shape so the BoMPreview component never sees undefined
            // even before the first fetch.
            bom_rollup: {
                cabinet_count: 0,
                panels: { side: 0, top: 0, bottom: 0, back: 0,
                          shelf: 0, door: 0, drawer_front: 0 },
                hardware: { hinge_pair_count: 0, handle_count: 0,
                            drawer_slide_pair_count: 0 },
                edge_banding_mm: 0,
            },
            validation: [],
            // T2C12 — footer-action progress flag. Disables buttons +
            // shows a brief inline message while an RPC is in flight.
            action_busy: false,
            action_message: null,
            // Phase 4 — in-flight flag for the Room Setup unit toggle.
            // Disables both segmented buttons while the POST is pending
            // so a rapid double-click doesn't queue two flips.
            unit_saving: false,
            // P25C4 — monotonically increasing counter bumped on every
            // successful _loadOrder. KitchenViewport watches this to
            // refetch its 3D payload when the order changes underneath
            // (drawer autosave, footer action, etc.). Phase 3 polish:
            // generalise to a publish/subscribe pattern for any
            // component that needs to refresh on order change.
            payload_version: 0,
            // G11+G12 — catalog list (the 12 Q8 cabinets, fetched on
            // mount from the existing kitchen-planner state endpoint
            // so the CatalogPicker has tiles to render).
            catalog: [],
            catalog_busy: false,
            // 2026-06-02 channel pricing — pricelist display name
            // surfaced from kitchen_planner_state.user.channel_label
            // ("Dealer (-50%)", "Contractor Tier 3 (-35%)", etc.).
            // Drives the channel badge on each catalog card.
            channel_label: "",
            // Phase 2.B — Room Setup tab payload. Mirrors the shape
            // returned by /southbrook/api/order/<id>/room/get
            // (Phase 2.A controller). Null until the background fetch
            // resolves; the room_setup tab renders the empty-state CTA
            // while it's null. Non-blocking: initial render does NOT
            // wait on this.
            room: null,
            ui: {
                current_tab: "lines",
                selected_line_id: null,
                // G11 — modal visibility.
                catalog_open: false,
                // Phase 3 Sprint C1 — when the user clicks "+ Add to
                // <zone>", we stash the zone code here so the
                // CatalogPicker can pre-filter to the matching
                // family group. Cleared by the top-level Browse
                // Catalog button so it shows everything.
                catalog_zone_filter: null,
                // Phase 2.C — fullscreen wizard slot. null when no
                // wizard is open; "room_setup" when the Room Setup
                // wizard is mounted. Future wizards (e.g. cabinet
                // bulk-edit) can reuse this slot.
                wizard: null,
                // Phase 3.D — collapsible warning banner above the
                // Order Lines list. Starts collapsed; the headline
                // ("⚠ N issues found") is always visible; bullet
                // list appears only when expanded.
                warnings_expanded: false,
                // Phase 3.C.2a — line id of the cabinet currently
                // being assigned to a wall via the AssignToWallModal.
                // null when the modal is closed. The render block
                // mounts <AssignToWallModal/> when this is non-null.
                assigning: null,
                // Phase 6.1 — gap-click recommendation modal state.
                // null when no recommend modal is open; otherwise:
                //   { gapMm, position, wallId, recommendations: [...] }
                // Set by _onPlanGapClick after the recommend RPC
                // resolves; cleared by _onGapPickTemplate (on success),
                // _onGapBrowseAll (escape to full catalog), or
                // _onGapCancel (× / Cancel).
                gapRecommend: null,
            },
            // Phase 3.C.2a — gap-click stash. When the user taps a gap
            // rect on the Room Layout, we record the wall+position here
            // and open the catalog modal; after the picker creates a
            // new line, _onPickCabinet checks this flag and fires the
            // /place-on-wall RPC to auto-place the new cabinet at the
            // gap. Cleared after the place call (success OR failure)
            // so a subsequent normal Add doesn't accidentally inherit
            // the placement. Kept at the top level (NOT under .ui)
            // because it's a data-flow flag, not a UI visibility flag.
            pendingGapPlacement: null,
        });
        // Pre-bind handler methods to this. OWL's template compiler
        // doesn't preserve 'this' when methods are referenced as
        // props or via arrow wrappers in this Odoo version — the
        // first this.state.* access inside the handler then throws
        // 'Cannot read properties of undefined (reading state)'.
        // Binding here makes the bound functions safe to pass as
        // plain props without losing context. Verified safe pattern
        // by user devtools 2026-06-01 (3 prior fix attempts —
        // .bind directive miscompiled, arrow wrappers didn't carry
        // this — both failed).
        this._closeCatalog = this._closeCatalog.bind(this);
        this._onPickCabinet = this._onPickCabinet.bind(this);
        this._setSelectedLine = this._setSelectedLine.bind(this);
        this._onLineSaved = this._onLineSaved.bind(this);

        // P1 bugfix: synchronous lock prevents double-add on rapid clicks
        // (the reactive `state.catalog_busy` flag flips inside an async
        // function, so OWL's re-render-driven disabled-attribute update
        // arrives after a fast second click. The instance flag is set
        // before the first `await` so re-entry is impossible).
        this._addInFlight = false;
        // Counter for unique toast ids — useState array keys.
        this._toastSeq = 0;

        onMounted(() => {
            this._loadOrder();
            this._loadCatalog();
            // Phase 2.B — fire-and-forget room fetch. The Room Setup tab
            // pre-renders with state.room=null (empty-state CTA) so we
            // do NOT await this; if the fetch fails the tab just shows
            // the empty state, which is the correct fallback.
            this._refreshRoomState();
            this._startRealtimeSync();
        });
        onWillUnmount(() => this._stopRealtimeSync());
    }

    // ------------------------------------------------------------------
    // P1 bugfix 2026-06-22 — toast helpers. _pushToast spawns a transient
    // status banner that disappears after `ttl` ms (default 3s); the
    // template renders them in a fixed-position stack.
    // ------------------------------------------------------------------
    _pushToast(text, kind = "success", ttl = 3000) {
        this._toastSeq += 1;
        const id = this._toastSeq;
        this.state.toasts.push({ id, text, kind });
        setTimeout(() => {
            const idx = this.state.toasts.findIndex((t) => t.id === id);
            if (idx >= 0) this.state.toasts.splice(idx, 1);
        }, ttl);
    }

    _dismissToast(id) {
        const idx = this.state.toasts.findIndex((t) => t.id === id);
        if (idx >= 0) this.state.toasts.splice(idx, 1);
    }

    // ------------------------------------------------------------------
    // Phase 3 Sprint D3 — realtime sync.
    //
    // Two designers / dealers on the same order see each other's
    // edits within ~5s. We poll _loadOrder() on a fixed interval
    // while the tab is visible; document.visibilityState pauses the
    // poll when the tab is in the background (saves server load and
    // mobile battery).
    //
    // Why polling vs the planned bus.bus subscription:
    //   The portal_boot.esm.js bootstrap is a standalone OWL mount
    //   (no service registry), so wiring up @bus/services/bus_service
    //   needs scaffolding that exceeds D3's 0.5d budget. A 5-second
    //   visibility-gated poll achieves the same end-user effect (sub-
    //   5s sync) and degrades gracefully if the network blips. When
    //   the bus_service refactor lands (post-Phase 3), this method
    //   becomes a one-liner that listens on the same channel the
    //   backend already posts to.
    //
    // Per-tab interval; cleared on unmount.
    // ------------------------------------------------------------------
    _startRealtimeSync() {
        const POLL_MS = 5000;
        if (this._realtimeTimer) clearInterval(this._realtimeTimer);
        const tick = () => {
            if (typeof document !== "undefined"
                && document.visibilityState === "hidden") {
                return;
            }
            if (this.state.loading || this.state.action_busy) {
                return;
            }
            // P0 bugfix 2026-06-22: pause the poll while the user is in
            // the middle of an interaction. The catalog modal is the big
            // one (a re-render that wipes filter state mid-browse is the
            // worst UX hit), but also skip during an in-flight add so
            // the optimistic UI doesn't fight an interleaved refresh.
            if (this.state.ui.catalog_open) return;
            if (this._addInFlight) return;
            this._loadOrder();
        };
        this._realtimeTimer = setInterval(tick, POLL_MS);
    }

    _stopRealtimeSync() {
        if (this._realtimeTimer) {
            clearInterval(this._realtimeTimer);
            this._realtimeTimer = null;
        }
    }

    // ------------------------------------------------------------------
    // G11 + G12 — catalog management.
    // ------------------------------------------------------------------

    async _loadCatalog() {
        try {
            const payload = await rpcJsonCall(
                "/southbrook/api/kitchen-planner/state",
                {},
            );
            // The kitchen-planner endpoint returns {catalog: [...], ...}.
            // If the route is missing or the user isn't authed, fall
            // back to an empty array — the UI will show 'No catalog
            // available' inside the picker.
            this.state.catalog = (payload && payload.catalog) || [];
            // 2026-06-02 — capture the pricelist label for the
            // CatalogPicker's channel badge. Empty when the visitor
            // is on the retail walk-in pricelist (no channel badge).
            this.state.channel_label = (
                (payload && payload.user && payload.user.channel_label)
                || ""
            );
        } catch (e) {
            // Quiet failure — the catalog button will still render
            // but the modal will be empty. Phase-2 polish surfaces
            // the error inline.
            this.state.catalog = [];
        }
    }

    _openCatalog() {
        // Clear any zone pre-filter from a previous "+ Add to <zone>"
        // click so a top-level Browse Catalog action sees everything.
        this.state.ui.catalog_zone_filter = null;
        this.state.ui.catalog_open = true;
    }

    // Phase 3 Sprint C1 — per-zone inline add-line entry point.
    // Pre-filters the CatalogPicker to the matching family group when
    // possible (base_run -> base/sink/corner, wall -> wall, tall ->
    // tall/pantry, island -> base/island). Falls back to opening the
    // full catalog when the zone has no clear family mapping.
    _onAddToZone = (zoneCode) => {
        this.state.ui.catalog_zone_filter = zoneCode || null;
        this.state.ui.catalog_open = true;
    };

    _closeCatalog() {
        if (!this.state.catalog_busy) {
            this.state.ui.catalog_open = false;
            // Phase 3.C.2a — drop any stashed gap-placement intent so
            // the NEXT "+ Add Another Cabinet" click doesn't
            // accidentally inherit a placement from a cancelled gap
            // flow. _onPickCabinet success path already clears it on
            // the happy path; this covers the "user closed the modal
            // without picking" case.
            this.state.pendingGapPlacement = null;
        }
    }

    async _onPickCabinet(productTmplId, qty, label) {
        if (!this.state.order) return;
        // P1 bugfix 2026-06-22: synchronous re-entry guard. The reactive
        // `catalog_busy` flag below still drives the visual disabled
        // state on the button, but OWL re-render is async, so a fast
        // second click can sneak through before the DOM attribute
        // updates. Setting `_addInFlight` before the first `await`
        // closes that race window — re-entry returns immediately.
        if (this._addInFlight) return;
        this._addInFlight = true;
        this.state.catalog_busy = true;
        const qtyArg = (typeof qty === "number" && qty > 0)
            ? Math.floor(qty)
            : 1;
        // UX bugfix 2026-06-23: optimistic counter bump. The "N
        // cabinets" counter reads state.order.line_count which is
        // server-side `len(sale.order.line[])` — i.e. count of LINES,
        // not sum of qty. So we bump by 1 per click regardless of qty.
        // With Option B merge enabled (server-side at /add-line), a
        // duplicate-template add merges into the existing line — the
        // optimistic +1 over-shoots by 1 briefly, but _loadOrder()
        // after the server response reconciles to truth. The catch
        // path reverts on failure. Grand total is intentionally NOT
        // optimistic — pricelist/channel discounts make a naive
        // qtyArg * list_price wrong; the toast confirms the add and
        // the total catches up on reload.
        const _optimisticBump = 1;
        if (this.state.order && typeof this.state.order.line_count === "number") {
            this.state.order.line_count += _optimisticBump;
        }
        try {
            const result = await rpcJsonCall(
                `/southbrook/api/order/${encodeURIComponent(this.state.order.id)}/add-line`,
                {
                    product_tmpl_id: productTmplId,
                    // 2026-06-02 catalog redesign — pass qty through.
                    // Endpoint accepts and validates; defaults to 1
                    // when omitted, so old callers stay correct.
                    qty: qtyArg,
                },
            );
            if (result && result.ok) {
                // Force the next _loadOrder to apply (the add changed
                // server state in a way the hash MUST observe).
                this.state.payload_hash = "";
                // Refresh the order so the new line appears + totals
                // re-compute. Bumps payload_version, which makes the
                // KitchenViewport refetch its 3D payload as a bonus.
                //
                // 2026-06-02 redesign: do NOT auto-close the modal.
                // Users browsing the catalog often want to add several
                // cabinets in one session; the CatalogPicker now shows
                // a brief 'Added' state per card and the user closes
                // when done. The error path still surfaces via
                // state.error and skips the success-state pulse.
                await this._loadOrder();
                // Phase 3.C.2a — gap-click auto-place. When the catalog
                // modal was opened by a tap on an empty wall gap (vs the
                // top-level "+ Add Another Cabinet" button), we POST a
                // /place-on-wall RPC against the freshly-created line so
                // it lands at the gap's position. The flag is cleared
                // unconditionally — a placement failure leaves the
                // cabinet on the order but unplaced, which the sidebar
                // surfaces so the user can resolve via Assign...
                const stash = this.state.pendingGapPlacement;
                const newLineId = result.line_id;
                if (stash && newLineId) {
                    try {
                        const placeRes = await rpcJsonCall(
                            "/southbrook/api/order/"
                            + encodeURIComponent(this.state.order.id)
                            + "/line/" + encodeURIComponent(newLineId)
                            + "/place-on-wall",
                            {
                                wall_id: stash.wallId,
                                position_from_left_mm: stash.position,
                            },
                        );
                        if (placeRes && placeRes.ok) {
                            await this._refreshRoomState();
                            this.state.payload_hash = "";
                            await this._loadOrder();
                            this._pushToast("Cabinet placed on wall", "success");
                        } else {
                            // Don't block the catalog flow — the line
                            // was added, just not placed. Surface a
                            // soft warning so the user knows to assign
                            // it via the sidebar.
                            this._pushToast(
                                "Cabinet added but could not auto-place — assign it from the Room Layout sidebar.",
                                "error",
                                5000,
                            );
                        }
                    } catch (placeErr) {
                        this._pushToast(
                            "Cabinet added but auto-place failed: "
                            + (placeErr && placeErr.message ? placeErr.message : String(placeErr)),
                            "error",
                            5000,
                        );
                    } finally {
                        this.state.pendingGapPlacement = null;
                    }
                }
                // P1 bugfix 2026-06-22: visible confirmation toast.
                // Quantity prefix only when qty>1 to keep the common
                // case short. `label` comes from the catalog card so
                // the user sees what they actually picked.
                const qtyPrefix = qtyArg > 1 ? `${qtyArg} × ` : "";
                this._pushToast(
                    `Added ${qtyPrefix}${label || "cabinet"}`,
                    "success",
                );
            } else {
                this.state.error = (
                    result?.error === "order_locked"
                    ? `Cannot add cabinets — this order is ${result.state}.`
                    : result?.error || "Could not add the cabinet."
                );
                this._pushToast(this.state.error, "error", 5000);
                throw new Error(this.state.error);
            }
        } catch (e) {
            // UX bugfix 2026-06-23: revert the optimistic counter bump
            // when the add failed. (_loadOrder did NOT run, so the
            // counter would otherwise stay artificially high until the
            // next refresh.) Floored at 0 in case the optimistic state
            // got further corrupted somehow.
            if (this.state.order && typeof this.state.order.line_count === "number") {
                this.state.order.line_count = Math.max(
                    0, this.state.order.line_count - _optimisticBump,
                );
            }
            // If the error was already set by the !ok branch above,
            // don't overwrite it with a generic message.
            if (!this.state.error) {
                this.state.error = e?.message || String(e);
                this._pushToast(this.state.error, "error", 5000);
            }
            throw e;
        } finally {
            this.state.catalog_busy = false;
            this._addInFlight = false;
        }
    }

    async _loadOrder() {
        const orderId = this.props.orderId;
        if (!orderId) {
            // No id in URL → render the empty-state card. Not an error.
            this.state.loading = false;
            this.state.initial_load = false;
            return;
        }
        const isInitial = this.state.initial_load;
        // P0 bugfix 2026-06-22: only flip the global loading card on the
        // initial paint. Background polls update reactive state in place
        // — OWL reconciles the DOM, child components (CatalogPicker)
        // keep their setup() state, and the "Loading order…" branch
        // (which tears down the entire loaded subtree) never appears.
        if (isInitial) {
            this.state.loading = true;
            this.state.error = null;
        }
        try {
            const payload = await rpcJsonCall(
                `/southbrook/api/order/${encodeURIComponent(orderId)}`,
            );
            if (payload && payload.error) {
                // Only surface a structured error on the initial paint.
                // Background polls swallow it (network blip / 401 from
                // a stale session would otherwise blank the UI mid-edit).
                if (isInitial) {
                    this.state.error = (
                        payload.error === "forbidden"
                            ? "Access denied. This order is not visible to your account."
                            : payload.error === "not_found"
                            ? "Order not found."
                            : payload.error
                    );
                }
                return;
            }
            // P0 bugfix 2026-06-22: compute a stable hash of the payload
            // slice that the UI actually reads, and bail before writing
            // to reactive state when nothing changed. Avoids a no-op OWL
            // reconcile that — in some browser frames — interleaves with
            // an in-flight user gesture and momentarily clears focus or
            // selection. Hash covers everything that drives visible
            // pixels: order header version+state+totals, line count +
            // per-line id/qty/price triplets, validation count.
            const newHash = this._computePayloadHash(payload);
            if (!isInitial && newHash === this.state.payload_hash) {
                return;
            }
            this.state.payload_hash = newHash;
            this.state.order = payload.order;
            this.state.lines = payload.lines || [];
            this.state.zones = payload.zones || [];
            // T2C11 — keep the default shape when the payload omits
            // the key (forward-compat with older backend versions).
            if (payload.bom_rollup) {
                this.state.bom_rollup = payload.bom_rollup;
            }
            this.state.validation = payload.validation || [];
            // P25C4 — bump the version counter so subscribed components
            // (KitchenViewport) re-fetch their slice.
            this.state.payload_version = (this.state.payload_version || 0) + 1;
        } catch (e) {
            // P0 bugfix: only surface the error on the initial paint;
            // background-poll exceptions are silent (a transient network
            // hiccup must not blow away the user's open modal). Errors
            // raised by the user-driven _onPickCabinet / _onFooterAction
            // paths reach state.error / state.action_message via their
            // own try/catch blocks.
            if (isInitial) {
                this.state.error = e?.message || String(e);
            }
        } finally {
            if (isInitial) {
                this.state.loading = false;
                this.state.initial_load = false;
            }
        }
    }

    // P0 bugfix 2026-06-22 — payload hash for the unchanged-poll fast
    // path. JSON.stringify of the load-bearing fields only; the entire
    // payload is too noisy (timestamps drift, derived fields jitter).
    _computePayloadHash(payload) {
        const o = (payload && payload.order) || {};
        const lines = payload && payload.lines ? payload.lines : [];
        // Line fingerprint must mirror the field names emitted by the
        // /southbrook/api/order/<id> controller (main.py around line
        // 1789): id, product_id, qty (NOT product_uom_qty — the
        // controller exposes the user-facing alias), price_unit,
        // price_subtotal. Mismatching the names here would silently
        // produce a constant hash and we'd never refresh the lines
        // grid on qty/price edits.
        const lineFingerprints = lines.map((l) => [
            l.id,
            l.product_id,
            l.qty,
            l.price_unit,
            l.price_subtotal,
        ]);
        return JSON.stringify([
            o.id,
            o.state,
            o.version,
            o.line_count,
            o.channel_total,
            o.retail_subtotal,
            o.savings,
            o.lead_time_days,
            lineFingerprints,
            (payload.validation || []).length,
        ]);
    }

    async _onRetry() {
        await this._loadOrder();
    }

    // ------------------------------------------------------------------
    // T2C8 — TabBar
    // ------------------------------------------------------------------

    /**
     * Five-tab definition for the TabBar. Counts derive live from the
     * store so they update as commits 9-11 wire the underlying data.
     *
     *   lines     → line_count from the payload header
     *   bom       → Phase-1 approximation (panels per cabinet × 10).
     *               T2C11 replaces with the real BoM rollup count.
     *   validation→ placeholder 0. T2C11 wires the rule-engine output.
     *   history   → "v<N>" string from order.version.
     *   print     → null (no badge — print tab is just an action).
     */
    get _tabs() {
        const order = this.state.order || {};
        const all = [
            // Phase 2.B — Room Setup is the first tab. Badge:
            //   ✓ when a room is configured AND layout_complete is true
            //   ⚠ when a room exists but is not yet complete
            //   null when no room (badge hidden)
            // Customer mode includes this tab — room measurement is a
            // customer concern (see customerCodes below).
            {
                code: "room_setup",
                label: "Room Setup",
                count: this.state.room
                    ? (this.state.room.layout_complete ? "✓" : "⚠")
                    : null,
            },
            // Phase 3.B — Room Layout. Position 1 (after Room Setup,
            // before Order Lines). Badge: unplaced cabinet count when
            // a room exists, null otherwise (badge hidden).
            {
                code: "room_layout",
                label: "Room Layout",
                count: this.state.room
                    ? (this.state.lines.filter((l) => !l.wall_id).length || null)
                    : null,
            },
            {
                code: "lines",
                label: "Order Lines",
                count: this.state.lines.length,
            },
            // Phase 2.5 commit 1 — 3D Kitchen tab.
            {
                code: "kitchen3d",
                label: "3D Kitchen",
                count: this.state.lines.length || null,
            },
            {
                code: "bom",
                label: "BoM Preview",
                // T2C11 — total panels + hardware items rolled up.
                count: this._bomBadgeCount(),
            },
            {
                code: "validation",
                label: "Validation",
                count: this.state.validation.length,
            },
            {
                code: "history",
                label: "History",
                count: "v" + (order.version || 1),
            },
            {
                code: "print",
                label: "Customer Print",
                count: null,
            },
        ];
        // T2C13 — customer mode shows only the lines view + print.
        // BoM Preview, Validation, and History are dealer-only
        // surfaces (per Build Spec §2.1/§2.2 + charter Q6). Phase 2.5
        // commit 1 added 3D Kitchen to the customer-visible set —
        // it's a presentation surface, not a power-user tool.
        if (this.props.mode === "customer") {
            // Phase 2.B — "room_setup" is customer-visible (room
            // measurement is a customer concern, not a power-user tool).
            const customerCodes = new Set([
                "room_setup", "room_layout", "lines", "kitchen3d", "print",
            ]);
            return all.filter((t) => customerCodes.has(t.code));
        }
        return all;
    }

    // Class-field arrow so `this` binds to the OrderBuilder when the
    // TabBar invokes the callback. Equivalent to .bind(this) but
    // declarative.
    _setActiveTab = (code) => {
        this.state.ui.current_tab = code;
    };

    // ------------------------------------------------------------------
    // Phase 2.B — Room Setup helpers.
    //
    // _humanShape / _humanConstraint translate the server's enum codes
    // (snake_case selection values from Phase 1 models) into customer-
    // readable labels for the summary card and constraint chips.
    //
    // _capPct returns the wall-utilisation percentage (0-100) for the
    // capacity bar; clamped so an over-used wall renders at 100% with
    // the negative `remaining_mm` surfacing via the `--over` modifier.
    //
    // _openRoomSetupWizard mounts the 3-step wizard component (Phase
    // 2.C) by flipping state.ui.wizard. _closeRoomSetupWizard +
    // _onRoomSubmitted are the lifecycle callbacks the wizard invokes.
    //
    // _refreshRoomState wraps the /room/get endpoint from Phase 2.A.
    // Reuses the module-level rpcJsonCall helper (line 58) — must NOT
    // introduce a parallel fetch path. Failure is swallowed so the
    // tab degrades to the empty-state CTA rather than blocking the
    // initial render.
    // ------------------------------------------------------------------

    _humanShape(code) {
        return {
            straight: "Straight",
            l_shape: "L-Shape",
            u_shape: "U-Shape",
            galley: "Galley",
            g_shape: "G-Shape",
            island: "Island",
            peninsula: "Peninsula",
            custom: "Custom",
        }[code] || code || "—";
    }

    _humanConstraint(code) {
        return {
            window: "Window",
            door: "Door",
            sink: "Sink",
            cooktop: "Cooktop",
            oven: "Oven",
            dishwasher: "Dishwasher",
            rangehood: "Rangehood",
            fridge_space: "Fridge Space",
            power_outlet: "Power Outlet",
            structural_post: "Structural Post",
            other: "Other",
        }[code] || code;
    }

    _capPct(wall) {
        const len = wall.length_mm || 1;
        const used = Math.max(0, wall.used_mm);
        return Math.min(100, Math.round((used / len) * 100));
    }

    // ------------------------------------------------------------------
    // Phase 4 — mm ↔ ft/in conversion helpers.
    //
    // Storage layer is always mm; the toggle on the Room Setup header
    // flips state.room.unit_preference between "mm" and "imperial". Every
    // length label that reads off the room payload calls _humanLen so the
    // re-render flips cleanly without round-tripping to the server.
    //
    // ZoneGroup, RoomLayoutTab, FloorPlanSVG and AssignToWallModal each
    // carry mirror copies of these helpers (they're 5 lines of pure
    // arithmetic) — extracting to a module would just move the import
    // weight without simplifying anything.
    // ------------------------------------------------------------------

    _imperialFromMm(mm) {
        const inches = Math.round((Number(mm) || 0) / 25.4);
        const feet = Math.floor(inches / 12);
        const remIn = inches - feet * 12;
        if (feet === 0) return `${remIn}"`;
        if (remIn === 0) return `${feet}'`;
        return `${feet}' ${remIn}"`;
    }

    _humanLen(mm) {
        if (!mm && mm !== 0) return "—";
        const pref = (this.state.room && this.state.room.unit_preference) || "mm";
        if (pref === "imperial") return this._imperialFromMm(mm);
        return `${Math.round(Number(mm) || 0)} mm`;
    }

    // ------------------------------------------------------------------
    // Phase 4 — Unit toggle handler. POSTs the new preference to the
    // /room/<rid>/update endpoint (Phase 2.A — already supports a
    // partial-update body with unit_preference); on success refreshes
    // state.room so every length label re-renders in the new unit.
    // Failure is non-fatal: we restore the previous preference visually
    // and log to console.
    // ------------------------------------------------------------------

    _onUnitToggle = async (unit) => {
        if (!this.state.room) return;
        const current = this.state.room.unit_preference || "mm";
        if (current === unit) return;
        if (this.state.unit_saving) return;
        this.state.unit_saving = true;
        try {
            const r = await rpcJsonCall(
                "/southbrook/api/order/"
                + encodeURIComponent(this.props.orderId)
                + "/room/"
                + encodeURIComponent(this.state.room.id)
                + "/update",
                { unit_preference: unit },
            );
            if (r && r.ok) {
                await this._refreshRoomState();
            } else {
                console.warn("[OrderBuilder] unit toggle rejected:", r);
            }
        } catch (e) {
            console.warn("[OrderBuilder] unit toggle failed:", e);
        } finally {
            this.state.unit_saving = false;
        }
    };

    // ------------------------------------------------------------------
    // Phase 4 — 5-step progress checklist for the Room Setup panel.
    //
    // _progressSteps() returns an array of {key, label, complete, hint,
    // optional} entries. _allStepsComplete() reads the same list and
    // returns true when every step's complete === true; the panel
    // template swaps to the celebratory card in that case.
    //
    // _onProgressStepClick(key) dispatches the per-step CTA: steps
    // 1-3 reopen the wizard (where the user authored the data),
    // steps 4-5 jump to the Room Layout tab (where placement and
    // conflicts are visualised).
    // ------------------------------------------------------------------

    _progressSteps() {
        const room = this.state.room;
        if (!room) return [];
        const walls = room.walls || [];
        const constraints = room.constraints || [];
        const allWallsHaveLen = walls.length > 0
            && walls.every((w) => (w.length_mm || 0) > 0);
        const lines = this.state.lines || [];
        const allLinesPlaced = lines.length === 0
            || lines.every((l) => !!l.wall_id);
        const noConflicts = walls.every((w) => !w.has_conflicts);
        return [
            {
                key: "room_shape",
                label: "Room type & shape selected",
                complete: !!room.layout_shape,
                hint: "Open Room Setup wizard",
            },
            {
                key: "wall_dimensions",
                label: "Wall dimensions entered",
                complete: allWallsHaveLen,
                hint: "Open Room Setup wizard",
            },
            {
                key: "constraints",
                label: "Fixed constraints mapped (optional)",
                complete: constraints.length > 0,
                hint: "Open Room Setup wizard",
                optional: true,
            },
            {
                key: "cabinets_assigned",
                label: "All cabinets assigned to walls",
                complete: allLinesPlaced,
                hint: "Open Room Layout tab",
            },
            {
                key: "no_conflicts",
                label: "No conflicts detected",
                complete: noConflicts,
                hint: "Open Room Layout tab",
            },
        ];
    }

    _allStepsComplete() {
        const steps = this._progressSteps();
        if (steps.length === 0) return false;
        return steps.every((s) => s.complete === true);
    }

    _onProgressStepClick(stepKey) {
        if (stepKey === "room_shape"
            || stepKey === "wall_dimensions"
            || stepKey === "constraints") {
            this._openRoomSetupWizard();
            return;
        }
        if (stepKey === "cabinets_assigned" || stepKey === "no_conflicts") {
            this._setActiveTab("room_layout");
            return;
        }
    }

    // Phase 2.C — wired. Mounts the RoomSetupWizard overlay; the
    // template renders it conditional on state.ui.wizard === "room_setup".
    _openRoomSetupWizard() {
        this.state.ui.wizard = "room_setup";
    }

    // Phase 2.C — callbacks the RoomSetupWizard fires via its props.
    // _closeRoomSetupWizard is the cancel / × path. _onRoomSubmitted
    // receives the room dict returned by /room/create and caches it on
    // state.room (so the Room Setup tab re-renders without a round-trip)
    // then switches to the room_setup tab so the user lands on the
    // summary card from Phase 2.B.
    _closeRoomSetupWizard = () => {
        this.state.ui.wizard = null;
    };

    _onRoomSubmitted = (room) => {
        if (room) {
            this.state.room = room;
        }
        this.state.ui.wizard = null;
        this.state.ui.current_tab = "room_setup";
    };

    async _refreshRoomState() {
        const orderId = this.props.orderId;
        if (!orderId) {
            return;
        }
        try {
            const r = await rpcJsonCall(
                "/southbrook/api/order/" + encodeURIComponent(orderId) + "/room/get",
                {});
            if (r && r.ok) {
                this.state.room = r.room;
            }
        } catch (e) {
            // Tab still works in empty state — room fetch failure is
            // non-fatal. Log for ops visibility.
            console.warn("[OrderBuilder] room fetch failed:", e);
        }
    }

    // ------------------------------------------------------------------
    // T2C9 — line grouping + selection
    // ------------------------------------------------------------------

    /**
     * Filter the store's lines down to the ones belonging to a zone.
     * Called by the template's t-foreach over zones. Pure derived data
     * — no caching, but OWL only re-renders the affected ZoneGroup
     * when the array reference changes (and ours changes per render
     * call), so this stays correct without memoisation. Phase 3 polish
     * memoises if the list grows past ~50.
     */
    _linesForZone(zoneCode) {
        return this.state.lines.filter((l) => l.zone === zoneCode);
    }

    // Phase 3 Sprint C2 — filter the order's validation issue list
    // down to those tied to a given line.id. Passed into ZoneGroup
    // so each ConfigDrawer can read its own slice without each
    // drawer having to filter the whole array.
    _issuesForLine = (lineId) => {
        return (this.state.validation || [])
            .filter((iss) => iss && iss.line_id === lineId);
    };

    // ------------------------------------------------------------------
    // Phase 3.D — smart inline warnings on the Order Lines tab.
    //
    // _lineStatus / _warnings are the data side of the same UX surface:
    //   • _lineStatus(line)  → "placed" / "unplaced" / "conflict" / null.
    //     Passed by ZoneGroup itself (each ZoneGroup gets state.room as
    //     a prop) — kept on the parent ONLY so dealer-facing scripts /
    //     future test hooks have a single canonical implementation to
    //     reach for. The ZoneGroup template hosts its own _lineStatus
    //     mirror for perf (avoids one prop-callback per row × render).
    //   • _warnings()         → array of human-readable warning strings
    //     used to populate the collapsible banner. Pulls from:
    //       - per-wall: wall.remaining_mm < 0 → over capacity by N mm
    //       - per-wall: wall.has_conflicts    → placement conflict
    //       - per-order: lines with no wall_id when a room exists
    //
    // Returns [] (not null) when there's nothing to warn about so the
    // template's t-if check is a simple .length read.
    // ------------------------------------------------------------------

    _lineStatus(line) {
        const room = this.state.room;
        if (!room) return null;
        if (!line.wall_id) return "unplaced";
        const walls = room.walls || [];
        const wall = walls.find((w) => w.id === line.wall_id);
        if (wall && wall.has_conflicts) return "conflict";
        return "placed";
    }

    _warnings() {
        const out = [];
        const room = this.state.room;
        if (!room) return out;
        const walls = room.walls || [];

        // Over-capacity walls (one bullet each).
        for (const w of walls) {
            if (typeof w.remaining_mm === "number" && w.remaining_mm < 0) {
                const over = -w.remaining_mm;
                out.push(
                    "Wall " + (w.name || "?") + " is over capacity by "
                    + over + "mm",
                );
            }
        }

        // Wall conflicts (one bullet per wall, not per line).
        const conflictWalls = walls.filter((w) => w.has_conflicts);
        if (conflictWalls.length === 1) {
            const w = conflictWalls[0];
            out.push(
                "Wall " + (w.name || "?") + " has a placement conflict",
            );
        } else if (conflictWalls.length > 1) {
            const names = conflictWalls
                .map((w) => w.name || "?")
                .join(", ");
            out.push(
                conflictWalls.length + " walls have placement conflicts ("
                + names + ")",
            );
        }

        // Unplaced cabinets (one rolled-up bullet).
        const unplaced = (this.state.lines || [])
            .filter((l) => !l.wall_id).length;
        if (unplaced > 0) {
            out.push(
                unplaced + " "
                + (unplaced === 1 ? "cabinet has" : "cabinets have")
                + " no wall assigned",
            );
        }

        return out;
    }

    _toggleWarnings = () => {
        this.state.ui.warnings_expanded = !this.state.ui.warnings_expanded;
    };

    _setSelectedLine = (lineId) => {
        // Toggle: clicking the already-selected line clears the
        // selection. Matches the mockup's "click to deselect" UX.
        this.state.ui.selected_line_id =
            this.state.ui.selected_line_id === lineId ? null : lineId;
    };

    // T2C10 — invoked by ConfigDrawer after a successful autosave.
    // Re-fetches the order payload so prices everywhere (line cell,
    // zone subtotal, header strip) refresh from the canonical
    // backend state.
    _onLineSaved = async () => {
        await this._loadOrder();
    };

    // ------------------------------------------------------------------
    // T2C12 — FooterActions handler
    // ------------------------------------------------------------------

    /**
     * Dispatch a footer action via the backend then post-process the
     * result: confirm → re-fetch order to update state; duplicate →
     * navigate to the new order; print → open the PDF URL in a new tab.
     */
    _onFooterAction = async (actionCode) => {
        const orderId = this.props.orderId;
        if (!orderId) return;
        this.state.action_busy = true;
        this.state.action_message = null;
        try {
            const res = await rpcJsonCall(
                `/southbrook/api/order/${encodeURIComponent(orderId)}/action`,
                { action_code: actionCode },
            );
            if (res && res.error) {
                this.state.action_message = (
                    res.message || res.error
                );
                return;
            }
            switch (actionCode) {
                case "confirm":
                    await this._loadOrder();
                    this.state.action_message = "Order confirmed.";
                    break;
                case "send_to_manufacturing":
                    // Phase 4 Sprint 2 — show the dealer how many MOs
                    // were created vs reused, then refresh the order
                    // (chatter post updates the history feed).
                    await this._loadOrder();
                    this.state.action_message = (
                        `Sent to manufacturing — ${res.mo_count || 0} `
                        + `MO(s): ${res.new_count || 0} new, `
                        + `${res.existing_count || 0} existing.`
                    );
                    break;
                case "cancel":
                    await this._loadOrder();
                    this.state.action_message = "Order cancelled.";
                    break;
                case "request_price":
                    await this._loadOrder();
                    this.state.action_message = (
                        res.already_submitted
                        ? "Already submitted for pricing review."
                        : "Submitted for pricing review."
                    );
                    break;
                case "duplicate":
                    if (res.redirect_url) {
                        // Full page nav — destination is the same SPA
                        // mount point with a new order id.
                        window.location.href = res.redirect_url;
                    }
                    break;
                case "print":
                case "print_door_order":
                case "print_shop_copy":
                    if (res.redirect_url) {
                        window.open(res.redirect_url, "_blank");
                    }
                    break;
            }
        } catch (e) {
            this.state.action_message = e?.message || String(e);
        } finally {
            this.state.action_busy = false;
        }
    };

    // P25C3 — invoked when the user clicks a cabinet in the kitchen
    // viewport. Switches to Lines tab and selects the line so the
    // ZoneGroup → ConfigDrawer expansion fires.
    _onKitchen3dLineSelected = (lineId) => {
        this.state.ui.current_tab = "lines";
        this.state.ui.selected_line_id = lineId;
        this._scrollSelectedLineIntoView();
    };

    // After cross-tab line selection (3D Kitchen tap, Room Layout tap),
    // the highlighted row may be below the fold — scroll it into view so
    // the user actually sees the result of their click. Defer past the
    // OWL render tick via requestAnimationFrame so the DOM has the new
    // .o_owl_line_selected class before we query for it.
    _scrollSelectedLineIntoView = () => {
        requestAnimationFrame(() => {
            const el = document.querySelector(".o_owl_line_selected");
            if (el && typeof el.scrollIntoView === "function") {
                el.scrollIntoView({ block: "nearest", behavior: "smooth" });
            }
        });
    };

    // ------------------------------------------------------------------
    // Phase 3.C.2a — Room Layout tap interactivity.
    //
    // Three callbacks threaded into <RoomLayoutTab/>:
    //   _onPlanCabinetClick(lineId)         — placed-cabinet tap
    //   _onPlanGapClick(wallId, gap, posMm) — empty-gap tap (opens
    //                                          catalog + stashes intent)
    //   _onPlanAssignClick(lineId)          — sidebar Assign... button
    //
    // Plus two modal-driven handlers:
    //   _onAssignSubmit(lineId, wallId, posMm) — modal Assign click
    //   _onAssignCancel()                       — modal × / Cancel
    //
    // And one helper for the modal mount:
    //   _lineById(id) — lookup by id, returns null if not found
    //
    // The line-creation auto-place path lives inside _onPickCabinet
    // (search for "pendingGapPlacement" in this file).
    // ------------------------------------------------------------------

    _onPlanCabinetClick = (lineId) => {
        // Mirror _onKitchen3dLineSelected — same UX (jump to Lines tab,
        // select + scroll the row into view).
        this.state.ui.current_tab = "lines";
        this.state.ui.selected_line_id = lineId;
        this._scrollSelectedLineIntoView();
    };

    _onPlanGapClick = async (wallId, gapMm, position) => {
        // Phase 3.C.2a stashed the placement intent and opened the
        // catalog directly. Phase 6.1 inserts a recommend step: fetch
        // top-3 cabinet templates that fit the gap, open the
        // GapRecommendModal with them, and let the user pick (or hit
        // Browse all to fall through to the catalog). Stashing is
        // unchanged — the existing auto-place block at the tail of
        // _onPickCabinet handles placement regardless of which entry
        // point created the line.
        //
        // Fallback: ANY recommend failure (network, endpoint not
        // deployed yet on the live worker pool, malformed response)
        // falls through to the direct-to-catalog path so the user is
        // never blocked. This preserves the 3.C.2a behaviour as a
        // safety net.
        this.state.pendingGapPlacement = {
            wallId: wallId,
            position: position,
            gapMm: gapMm,
        };
        try {
            const r = await rpcJsonCall(
                "/southbrook/api/order/"
                + encodeURIComponent(this.props.orderId)
                + "/room/" + encodeURIComponent((this.state.room && this.state.room.id) || 0)
                + "/wall/" + encodeURIComponent(wallId)
                + "/recommend",
                {
                    gap_mm: gapMm,
                    position_from_left_mm: position,
                },
            );
            if (r && r.ok) {
                this.state.ui.gapRecommend = {
                    gapMm: gapMm,
                    position: position,
                    wallId: wallId,
                    recommendations: r.recommendations || [],
                };
                return;
            }
        } catch (e) {
            // eslint-disable-next-line no-console
            console.warn("[OrderBuilder] recommend fetch failed:", e);
        }
        // Fallback: open the catalog directly (3.C.2a behaviour).
        this._openCatalog();
    };

    // Phase 6.1 — user picked a recommended cabinet from the
    // GapRecommendModal. Close the modal and route through the EXISTING
    // _onPickCabinet pipeline: that fires /add-line, then the auto-
    // place block at the tail of _onPickCabinet sees pendingGapPlacement
    // is still set and POSTs /place-on-wall. We deliberately do NOT add
    // a parallel placement call here — see CLAUDE.md "Critical guard-
    // rails: Don't double-place".
    _onGapPickTemplate = async (templateId) => {
        const rec = (
            this.state.ui.gapRecommend
            && (this.state.ui.gapRecommend.recommendations || []).find(
                (x) => x.template_id === templateId,
            )
        );
        const label = rec ? (rec.name || rec.default_code || "cabinet") : null;
        // Close the recommend modal BEFORE the await so the user sees
        // the catalog-busy state on the order tabs (not on the modal).
        this.state.ui.gapRecommend = null;
        try {
            await this._onPickCabinet(templateId, 1, label);
        } catch (e) {
            // _onPickCabinet already surfaces the error via toast.
            // Swallow here so the modal's await doesn't propagate to
            // an unhandled rejection.
            // eslint-disable-next-line no-console
            console.warn("[OrderBuilder] gap-pick add failed:", e);
        }
    };

    // Phase 6.1 — Browse all fallback. Close the recommend modal,
    // open the full catalog. pendingGapPlacement is preserved so the
    // auto-place tail still fires once a template is picked from the
    // catalog.
    _onGapBrowseAll = () => {
        this.state.ui.gapRecommend = null;
        this._openCatalog();
    };

    // Phase 6.1 — × / Cancel. Drop both the modal state AND the
    // pendingGapPlacement stash so a subsequent normal "+ Add Another
    // Cabinet" doesn't inherit the cancelled gap's placement intent.
    _onGapCancel = () => {
        this.state.ui.gapRecommend = null;
        this.state.pendingGapPlacement = null;
    };

    _onPlanAssignClick = (lineId) => {
        // Guard: the modal needs walls to populate its dropdown — opening
        // it with no walls would let the user submit a no-op assign that
        // the endpoint rejects as a 400. Better to short-circuit with a
        // friendly note pointing at Room Setup.
        const walls = (this.state.room && this.state.room.walls) || [];
        if (walls.length === 0) {
            alert(
                "No walls configured yet — add walls in the Room Setup "
                + "tab before assigning cabinets.",
            );
            return;
        }
        this.state.ui.assigning = lineId;
    };

    _onAssignSubmit = async (lineId, wallId, positionMm) => {
        // Parent owns the RPC so the modal stays presentation-only.
        // On success we refresh state.room (used_mm + remaining_mm on
        // the picked wall) AND _loadOrder so the line's wall_id flows
        // into state.lines (the sidebar's "unplaced" filter reads it).
        try {
            const r = await rpcJsonCall(
                "/southbrook/api/order/" + encodeURIComponent(this.props.orderId)
                + "/line/" + encodeURIComponent(lineId) + "/place-on-wall",
                {
                    wall_id: wallId,
                    position_from_left_mm: positionMm,
                },
            );
            if (r && r.ok) {
                await this._refreshRoomState();
                // Force the next _loadOrder to take (the hash-skip path
                // would otherwise no-op on an unchanged-looking poll).
                this.state.payload_hash = "";
                await this._loadOrder();
                this.state.ui.assigning = null;
            } else {
                const detail = (r && (r.detail || r.error)) || "unknown error";
                // Surface to the user — same channel the other action
                // failures use (alert is intentionally coarse here; the
                // modal's own state.error captures it from the throw).
                throw new Error("Could not assign cabinet: " + detail);
            }
        } catch (e) {
            // Re-throw so the modal's own try/catch picks it up and
            // shows the inline error band (parent doesn't double-toast).
            throw e;
        }
    };

    _onAssignCancel = () => {
        this.state.ui.assigning = null;
    };

    // Phase 3.C.2b — drag-along-wall + touch ± shifter end handler.
    // Fired by FloorPlanSVG with a 25mm-snapped position_from_left_mm
    // for the dragged cabinet. Reuses /place-on-wall (3.A endpoint)
    // since this is just a position update on the SAME wall — cross-
    // wall drag is intentionally out of scope (AssignToWallModal
    // still owns that flow). Mirrors _onAssignSubmit's success path
    // (refresh room + load order + bust payload hash).
    _onPlanCabinetDragEnd = async (lineId, positionMm) => {
        const line = this._lineById(lineId);
        if (!line || !line.wall_id) return;
        try {
            const r = await rpcJsonCall(
                "/southbrook/api/order/" + encodeURIComponent(this.props.orderId)
                + "/line/" + encodeURIComponent(lineId) + "/place-on-wall",
                {
                    wall_id: line.wall_id,
                    position_from_left_mm: positionMm,
                },
            );
            if (r && r.ok) {
                await this._refreshRoomState();
                // Force the next _loadOrder to take (hash-skip path
                // would otherwise no-op on a same-looking poll).
                this.state.payload_hash = "";
                await this._loadOrder();
            } else if (r && r.error === "out_of_bounds") {
                // 25mm snap + JS-side clamp should make this
                // unreachable; defensive surfacing if the server
                // disagrees (e.g. wall length changed mid-drag).
                alert(
                    "Could not move cabinet: "
                    + (r.detail || "position out of bounds"),
                );
            } else {
                const detail = (r && (r.detail || r.error)) || "unknown error";
                alert("Could not move cabinet: " + detail);
            }
        } catch (e) {
            alert(
                "Could not move cabinet: "
                + ((e && e.message) ? e.message : String(e)),
            );
        }
    };

    // Phase 3.C.2d — interactive wall resize end handler. Fired by
    // RoomLayoutTab in two cases:
    //   - SVG handle drag drop on a single-wall topology (straight |
    //     island). Pre-snapped to 25mm, min-clamped to 200mm by the
    //     FloorPlanSVG before reaching us.
    //   - Sidebar ± 100mm button click on any shape (the only resize
    //     affordance multi-wall shapes get in v1 — SVG handles for
    //     l_shape / u_shape / galley / g_shape are deferred).
    //
    // Reuses /room/<rid>/update (Phase 2.A endpoint) — that already
    // accepts `walls: [{id, length_mm}]` for partial wall upserts.
    // Refreshes room + bumps payload_hash so the next _loadOrder()
    // takes (the hash-skip path would otherwise no-op on an
    // unchanged-looking poll). Cabinets that no longer fit surface
    // via the existing Phase 3.D warning banner — no server-side
    // cabinet mutation here.
    _onPlanWallResizeEnd = async (wallId, newLengthMm) => {
        if (!this.state.room) return;
        try {
            const r = await rpcJsonCall(
                "/southbrook/api/order/"
                + encodeURIComponent(this.props.orderId)
                + "/room/"
                + encodeURIComponent(this.state.room.id)
                + "/update",
                { walls: [{ id: wallId, length_mm: newLengthMm }] },
            );
            if (r && r.ok) {
                await this._refreshRoomState();
                this.state.payload_hash = "";
                await this._loadOrder();
            } else {
                const detail = (r && (r.detail || r.error)) || "unknown error";
                alert("Could not resize wall: " + detail);
            }
        } catch (e) {
            alert(
                "Could not resize wall: "
                + ((e && e.message) ? e.message : String(e)),
            );
        }
    };

    _lineById = (id) => {
        if (id === null || id === undefined) return null;
        return (this.state.lines || []).find((l) => l.id === id) || null;
    };

    // T2C11 — total BoM items used as the BoM tab badge count.
    _bomBadgeCount() {
        const r = this.state.bom_rollup || {};
        const p = r.panels || {};
        const h = r.hardware || {};
        return (
            (p.side || 0) + (p.top || 0) + (p.bottom || 0) + (p.back || 0)
            + (p.shelf || 0) + (p.door || 0) + (p.drawer_front || 0)
            + (h.hinge_pair_count || 0) + (h.handle_count || 0)
            + (h.drawer_slide_pair_count || 0)
        );
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

    // T2C13 — view-mode resolution.
    //   1. Explicit URL param ?mode=customer wins (test path + dealer
    //      previewing the customer view).
    //   2. Otherwise the data-mode attribute set by the controller
    //      (Phase 3 polish — backend reads user.share + a partner
    //      preference and emits the default).
    //   3. Fallback "dealer".
    const params = new URLSearchParams(window.location.search);
    const urlMode = params.get("mode");
    const datasetMode = root.dataset.mode || "";
    const mode = (
        urlMode === "customer" || datasetMode === "customer"
            ? "customer"
            : "dealer"
    );

    // Clear the placeholder so it doesn't flash beneath the OWL render.
    root.innerHTML = "";

    try {
        await mount(OrderBuilder, root, {
            props: { orderId, orderName, mode },
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
