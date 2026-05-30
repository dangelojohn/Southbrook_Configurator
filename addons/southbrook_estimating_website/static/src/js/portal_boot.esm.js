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
                    Customer Print (PDF)
                </button>
                <button class="o_owl_btn o_owl_btn_secondary"
                        t-on-click="() => props.onAction('duplicate')"
                        t-att-disabled="props.busy">
                    Duplicate as Draft
                </button>
                <button class="o_owl_btn o_owl_btn_primary"
                        t-on-click="() => props.onAction('confirm')"
                        t-att-disabled="props.busy or !_canConfirm()">
                    <t t-if="_canConfirm()">Confirm Order</t>
                    <t t-else="">
                        Confirmed (<t t-esc="props.order.state"/>)
                    </t>
                </button>
            </div>
            <div class="o_owl_footer_total">
                <div class="o_owl_footer_total_label">Grand Total</div>
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
        </div>
    `;
    static props = {
        order: Object,
        onAction: Function,
        busy: { type: Boolean, optional: true },
    };

    fmtUsd = fmtUsd;

    _canConfirm() {
        const s = this.props.order?.state;
        return s === "draft" || s === "sent";
    }
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

            <p class="o_owl_bom_foot">
                Phase 3 polish adds per-line BoM breakdown (collapsible),
                cut diagrams, and the Accucutt nest JSON export.
            </p>
        </div>
    `;
    static props = {
        rollup: Object,
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

            <p class="o_owl_drawer_foot">
                Phase 3 polish opens the full attribute picker (Family /
                Width / Series / Door Style / Finish / Hinge / Finished
                Sides / Accessories). The autosave path proven here
                carries through unchanged — only the editable surface
                widens.
            </p>
        </div>
    `;
    static props = {
        line: Object,
        onSaved: Function,
    };

    setup() {
        this.state = useState({
            qtyDraft: this.props.line.qty,
            saving: false,
            error: null,
            savedAt: null,
        });
        this._debounceTimer = null;
    }

    fmtUsd = fmtUsd;

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
                    <OrderLine line="line"
                               isSelected="line.id === props.selectedLineId"
                               onSelect="props.onSelectLine"/>
                    <!-- T2C10 — ConfigDrawer expands below the selected line,
                         spanning all 8 columns of the parent grid. -->
                    <ConfigDrawer t-if="line.id === props.selectedLineId"
                                  line="line"
                                  onSaved="props.onLineSaved"/>
                </t>
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
    };

    setup() {
        this.state = useState({ collapsed: false });
    }

    _toggle = () => {
        this.state.collapsed = !this.state.collapsed;
    };
}

fmtUsd; // referenced via class field on OrderLine + ZoneGroup helpers.

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
    static template = xml`
        <div class="o_owl_tabs">
            <t t-foreach="props.tabs" t-as="tab" t-key="tab.code">
                <button class="o_owl_tab"
                        t-att-class="{
                            'o_owl_tab_active': tab.code === props.activeTab,
                        }"
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

            <!-- TabBar (T2C8) — client-side panel switch. -->
            <TabBar tabs="_tabs"
                    activeTab="state.ui.current_tab"
                    onTabChange.bind="_setActiveTab"/>

            <!-- Tab panels. T2C9 fills Lines. T2C10-11 fill the rest. -->
            <div t-if="state.ui.current_tab === 'lines'"
                 class="o_owl_tab_panel o_owl_panel_lines">
                <!-- T2C9 — multi-zone line grid. -->
                <t t-if="state.zones.length === 0">
                    <p class="o_owl_panel_placeholder o_owl_lines_empty">
                        <strong>No cabinet lines on this order yet.</strong>
                        <br/>
                        Add lines via the backend Order Builder OR
                        click <em>New</em> below to start the
                        configurator (Phase 3 wires the inline add-line
                        flow into the portal).
                    </p>
                </t>
                <t t-else="">
                    <ZoneGroup t-foreach="state.zones"
                               t-as="zone"
                               t-key="zone.code"
                               zone="zone"
                               lines="_linesForZone(zone.code)"
                               selectedLineId="state.ui.selected_line_id"
                               onSelectLine="_setSelectedLine"
                               onLineSaved="_onLineSaved"/>
                </t>
            </div>
            <div t-elif="state.ui.current_tab === 'bom'"
                 class="o_owl_tab_panel o_owl_panel_bom">
                <BoMPreview rollup="state.bom_rollup"/>
            </div>
            <div t-elif="state.ui.current_tab === 'validation'"
                 class="o_owl_tab_panel o_owl_panel_validation">
                <ValidationStrip issues="state.validation"/>
            </div>
            <div t-elif="state.ui.current_tab === 'history'"
                 class="o_owl_tab_panel o_owl_panel_history">
                <p class="o_owl_panel_placeholder">
                    <strong>History panel</strong> — Phase 3 polish
                    surfaces the NF6 parent-order chain
                    (v1 → v2 → v3 …).
                </p>
            </div>
            <div t-elif="state.ui.current_tab === 'print'"
                 class="o_owl_tab_panel o_owl_panel_print">
                <p class="o_owl_panel_placeholder">
                    <strong>Customer Print panel</strong> — Phase 3
                    polish embeds the Signature Spec Sheet PDF preview
                    (already QWeb-rendered by southbrook_estimating).
                </p>
            </div>

            <!-- T2C12 — FooterActions row -->
            <FooterActions order="state.order"
                           onAction.bind="_onFooterAction"
                           busy="state.action_busy"/>

            <div t-if="state.action_message" class="o_owl_action_msg"
                 t-esc="state.action_message"/>

            <p class="o_owl_status">
                Phase 2 Track 2 — 12 of 14 commits live.
                Commit 13 lands the customer-mode toggle; commit 14
                is the gate review with John.
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
        TabBar,
        ZoneGroup,
        BoMPreview,
        ValidationStrip,
        FooterActions,
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
            // T2C11 — keep the default shape when the payload omits
            // the key (forward-compat with older backend versions).
            if (payload.bom_rollup) {
                this.state.bom_rollup = payload.bom_rollup;
            }
            this.state.validation = payload.validation || [];
        } catch (e) {
            this.state.error = e?.message || String(e);
        } finally {
            this.state.loading = false;
        }
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
        return [
            {
                code: "lines",
                label: "Order Lines",
                count: this.state.lines.length,
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
    }

    // Class-field arrow so `this` binds to the OrderBuilder when the
    // TabBar invokes the callback. Equivalent to .bind(this) but
    // declarative.
    _setActiveTab = (code) => {
        this.state.ui.current_tab = code;
    };

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
                case "duplicate":
                    if (res.redirect_url) {
                        // Full page nav — destination is the same SPA
                        // mount point with a new order id.
                        window.location.href = res.redirect_url;
                    }
                    break;
                case "print":
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
