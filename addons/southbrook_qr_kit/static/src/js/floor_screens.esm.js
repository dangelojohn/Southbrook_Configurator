/** @odoo-module **/
// SPDX-License-Identifier: LGPL-3.0-only
//
// W073 (R8.8, 2026-06-27) — Bin-Scan + Load-Unit OWL companion UI.
//
// JTBD: "When I'm at the receiving dock with a barcoded box, I want
// a real UI that scans the box, shows what's inside, and lets me
// confirm or split — not just a JSON endpoint."
//
// Two screens, one bundle:
//   * BinScanScreen     — /southbrook/floor/bin-scan
//   * LoadUnitScreen    — /southbrook/floor/load-unit
//
// The HTML shell at each route mounts the correct screen onto
// #sb_floor_root by reading data-sb-floor-app on that element.
//
// Touch-friendly: ships with the W039 dense class on body by default
// (the controller stamps `class="sb-dense"`).
//
// Audio cues are emitted automatically because the W036
// scan_audio_cue.js asset is in the same bundle (it hooks into the
// global fetch).
//
// Offline queue is automatic too: the W037 Service Worker registered
// by offline_scan_queue.js (also in this bundle) intercepts the
// /sb/qr/* POSTs and queues them when the wifi drops.

import {
    Component,
    mount,
    onMounted,
    useState,
    xml,
} from "@odoo/owl";

// ---------------------------------------------------------------------
// JSON-RPC helper — same wire-protocol Odoo's type=json controllers
// expect. Returns body.result; throws on body.error.
// ---------------------------------------------------------------------
async function rpcCall(url, params = {}) {
    const response = await fetch(url, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            jsonrpc: "2.0",
            method: "call",
            params,
            id: Date.now(),
        }),
        credentials: "same-origin",
    });
    if (!response.ok) {
        throw new Error("HTTP " + response.status);
    }
    const body = await response.json();
    if (body.error) {
        const msg =
            (body.error.data && body.error.data.message) ||
            body.error.message ||
            "RPC error";
        throw new Error(msg);
    }
    return body.result;
}

// ---------------------------------------------------------------------
// BinScanScreen — scan a bin to see what's inside, then scan
// destination + qty to move stock.
//
// Flow:
//   1. Operator scans the source bin QR → bin-inspect → render
//      contents (product, qty, lot, package).
//   2. Operator picks a product row or types qty.
//   3. Operator scans the destination bin QR → contents panel for
//      destination loads on the side.
//   4. Operator presses CONFIRM → POST /sb/qr/inventory/bin-scan.
//   5. Toast result; reset on success.
// ---------------------------------------------------------------------
class BinScanScreen extends Component {
    static template = xml`
        <div class="sb_floor sb_bin_scan">
            <header class="sb_floor_head">
                <h1>Bin Scan</h1>
                <span class="sb_floor_sub">
                    Scan source → scan destination → confirm
                </span>
            </header>

            <section class="sb_floor_step">
                <label for="src_input">1. Source bin QR</label>
                <input id="src_input"
                       t-att-value="state.srcRaw"
                       t-on-input="(e) => state.srcRaw = e.target.value"
                       t-on-keydown="_onSrcKey"
                       autofocus="autofocus"
                       placeholder="sb://loc/...  (scan or paste)"
                       autocomplete="off"
                       spellcheck="false"/>
                <button class="sb_btn sb_btn_secondary"
                        t-on-click="_inspectSrc"
                        t-att-disabled="!state.srcRaw || state.loading">
                    Inspect
                </button>
            </section>

            <div t-if="state.srcLocation" class="sb_floor_card sb_floor_contents">
                <div class="sb_floor_card_head">
                    <strong t-esc="state.srcLocation.complete_name"/>
                    <span class="sb_floor_card_sub"
                          t-esc="state.srcQuants.length + ' product line(s)'"/>
                </div>
                <table t-if="state.srcQuants.length" class="sb_floor_quants">
                    <thead>
                        <tr><th>Product</th><th>Code</th><th>Qty</th>
                            <th>UoM</th><th>Lot</th><th>Pkg</th></tr>
                    </thead>
                    <tbody>
                        <tr t-foreach="state.srcQuants" t-as="q"
                            t-key="q.product_id + ':' + (q.lot_name || '')"
                            t-att-class="{
                                sb_quant_row_selected:
                                    state.selectedProductId === q.product_id
                            }"
                            t-on-click="() => this._selectProduct(q)">
                            <td t-esc="q.product_name"/>
                            <td t-esc="q.product_code"/>
                            <td t-esc="q.qty"/>
                            <td t-esc="q.uom"/>
                            <td t-esc="q.lot_name"/>
                            <td t-esc="q.package_name"/>
                        </tr>
                    </tbody>
                </table>
                <p t-else="" class="sb_floor_empty">Bin is empty.</p>
            </div>

            <section class="sb_floor_step">
                <label for="dst_input">2. Destination bin QR</label>
                <input id="dst_input"
                       t-att-value="state.dstRaw"
                       t-on-input="(e) => state.dstRaw = e.target.value"
                       placeholder="sb://loc/...  (scan or paste)"
                       autocomplete="off"
                       spellcheck="false"/>
            </section>

            <section class="sb_floor_step sb_floor_qty">
                <label for="qty_input">3. Quantity</label>
                <input id="qty_input" type="number" min="0.001" step="0.001"
                       t-att-value="state.qty"
                       t-on-input="(e) => state.qty = parseFloat(e.target.value) || 0"/>
                <span class="sb_floor_qty_hint">
                    <t t-if="state.selectedProductId">
                        Moving
                        <strong t-esc="state.qty"/>
                        of
                        <strong t-esc="_selectedName()"/>
                    </t>
                    <t t-else="">Pick a product row above first.</t>
                </span>
            </section>

            <footer class="sb_floor_foot">
                <button class="sb_btn sb_btn_primary sb_btn_big"
                        t-on-click="_confirm"
                        t-att-disabled="!_canConfirm()">
                    Confirm Move
                </button>
                <button class="sb_btn sb_btn_secondary"
                        t-on-click="_reset">
                    Reset
                </button>
            </footer>

            <div t-if="state.toast" class="sb_floor_toast"
                 t-att-class="'sb_floor_toast sb_toast_' + state.toast.kind"
                 t-esc="state.toast.message"/>
        </div>
    `;

    setup() {
        this.state = useState({
            srcRaw: "",
            dstRaw: "",
            qty: 1,
            srcLocation: null,
            srcQuants: [],
            selectedProductId: null,
            loading: false,
            toast: null,
        });
    }

    _onSrcKey(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this._inspectSrc();
        }
    }

    async _inspectSrc() {
        if (!this.state.srcRaw) return;
        this.state.loading = true;
        try {
            const res = await rpcCall("/sb/qr/inventory/bin-inspect", {
                bin: this.state.srcRaw.trim(),
            });
            if (res && res.ok) {
                this.state.srcLocation = res.location;
                this.state.srcQuants = res.quants || [];
                this.state.selectedProductId = null;
                this._toast("ok", "Source loaded: " + res.location.name);
            } else {
                this.state.srcLocation = null;
                this.state.srcQuants = [];
                this._toast("err", (res && res.error) || "Inspect failed");
            }
        } catch (err) {
            this._toast("err", err.message || String(err));
        } finally {
            this.state.loading = false;
        }
    }

    _selectProduct(q) {
        this.state.selectedProductId = q.product_id;
        // Default qty to whatever's on hand, so a single-tap move
        // works out of the box. Operator can override.
        if (q.qty && q.qty > 0) {
            this.state.qty = q.qty;
        }
    }

    _selectedName() {
        const pid = this.state.selectedProductId;
        const q = this.state.srcQuants.find((x) => x.product_id === pid);
        return q ? q.product_name : "";
    }

    _canConfirm() {
        return (
            !this.state.loading &&
            this.state.srcRaw &&
            this.state.dstRaw &&
            this.state.selectedProductId &&
            this.state.qty > 0
        );
    }

    async _confirm() {
        if (!this._canConfirm()) return;
        this.state.loading = true;
        try {
            const res = await rpcCall("/sb/qr/inventory/bin-scan", {
                src: this.state.srcRaw.trim(),
                dst: this.state.dstRaw.trim(),
                product: this.state.selectedProductId,
                qty: this.state.qty,
            });
            if (res && res.ok) {
                if (res.queued) {
                    this._toast("warn",
                        "Queued offline (will sync when wifi returns)");
                } else if (res.replayed) {
                    this._toast("ok",
                        "Already done (replay): " + (res.message || ""));
                } else {
                    this._toast("ok", res.message || "Move OK");
                }
                // Reset for the next scan.
                setTimeout(() => this._reset(), 1500);
            } else {
                this._toast("err", (res && res.error) || "Move failed");
            }
        } catch (err) {
            this._toast("err", err.message || String(err));
        } finally {
            this.state.loading = false;
        }
    }

    _reset() {
        this.state.srcRaw = "";
        this.state.dstRaw = "";
        this.state.qty = 1;
        this.state.srcLocation = null;
        this.state.srcQuants = [];
        this.state.selectedProductId = null;
        const el = document.getElementById("src_input");
        if (el) el.focus();
    }

    _toast(kind, message) {
        this.state.toast = {kind, message};
        setTimeout(() => {
            if (this.state.toast && this.state.toast.message === message) {
                this.state.toast = null;
            }
        }, 4000);
    }
}

// ---------------------------------------------------------------------
// LoadUnitScreen — scan truck QR, then scan each shipping-unit QR;
// the server tracks loaded vs manifest and tells the UI when each
// scan was EXTRA (not on the BOL) or MISSING (manifested but not yet
// scanned).
// ---------------------------------------------------------------------
class LoadUnitScreen extends Component {
    static template = xml`
        <div class="sb_floor sb_load_unit">
            <header class="sb_floor_head">
                <h1>Load Unit</h1>
                <span class="sb_floor_sub">
                    Scan truck → scan each pallet → roll out
                </span>
            </header>

            <section class="sb_floor_step">
                <label for="truck_input">1. Truck QR</label>
                <input id="truck_input"
                       t-att-value="state.truckRaw"
                       t-on-input="(e) => state.truckRaw = e.target.value"
                       autofocus="autofocus"
                       placeholder="sb://truck/...  (scan or paste)"
                       autocomplete="off"
                       spellcheck="false"/>
            </section>

            <section class="sb_floor_step">
                <label for="unit_input">2. Unit QR</label>
                <input id="unit_input"
                       t-att-value="state.unitRaw"
                       t-on-input="(e) => state.unitRaw = e.target.value"
                       t-on-keydown="_onUnitKey"
                       placeholder="sb://ship/...  (scan or paste)"
                       autocomplete="off"
                       spellcheck="false"/>
                <button class="sb_btn sb_btn_primary"
                        t-on-click="_confirm"
                        t-att-disabled="!_canConfirm()">
                    Load Unit
                </button>
            </section>

            <div t-if="state.lastResult" class="sb_floor_card sb_floor_result">
                <div class="sb_floor_card_head">
                    <strong t-esc="state.lastResult.unit_name"/>
                    <span t-if="state.lastResult.is_extra"
                          class="sb_floor_chip sb_chip_warn">
                        EXTRA — not on manifest
                    </span>
                    <span t-elif="state.lastResult.already_loaded"
                          class="sb_floor_chip sb_chip_info">
                        Already loaded
                    </span>
                    <span t-else="" class="sb_floor_chip sb_chip_ok">
                        Loaded
                    </span>
                </div>
                <dl class="sb_floor_counts">
                    <dt>Manifest</dt>
                    <dd t-esc="state.lastResult.manifest_count"/>
                    <dt>Loaded</dt>
                    <dd t-esc="state.lastResult.loaded_count"/>
                    <dt>Missing</dt>
                    <dd t-esc="state.lastResult.missing_count"/>
                    <dt>Extra</dt>
                    <dd t-esc="state.lastResult.extra_count"/>
                </dl>
            </div>

            <ul t-if="state.history.length" class="sb_floor_history">
                <li t-foreach="state.history" t-as="h" t-key="h.id"
                    t-att-class="'sb_history_item sb_history_' + h.kind">
                    <span class="sb_history_time" t-esc="h.time"/>
                    <span class="sb_history_msg" t-esc="h.message"/>
                </li>
            </ul>

            <div t-if="state.toast"
                 t-att-class="'sb_floor_toast sb_toast_' + state.toast.kind"
                 t-esc="state.toast.message"/>
        </div>
    `;

    setup() {
        this.state = useState({
            truckRaw: "",
            unitRaw: "",
            lastResult: null,
            history: [],
            loading: false,
            toast: null,
        });
        this._historyId = 0;
    }

    _onUnitKey(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this._confirm();
        }
    }

    _canConfirm() {
        return (
            !this.state.loading &&
            this.state.truckRaw &&
            this.state.unitRaw
        );
    }

    async _confirm() {
        if (!this._canConfirm()) return;
        this.state.loading = true;
        try {
            const res = await rpcCall("/sb/qr/shipping/load-unit", {
                truck: this.state.truckRaw.trim(),
                unit: this.state.unitRaw.trim(),
            });
            if (res && res.ok) {
                this.state.lastResult = res;
                if (res.queued) {
                    this._toast("warn", "Queued offline");
                    this._pushHistory("queued", res.unit_name + " (queued)");
                } else if (res.is_extra) {
                    this._toast("warn",
                        res.alert || "Extra unit — not on manifest!");
                    this._pushHistory("warn",
                        res.unit_name + " — EXTRA");
                } else if (res.already_loaded) {
                    this._toast("info",
                        res.unit_name + " was already loaded");
                    this._pushHistory("info",
                        res.unit_name + " (already loaded)");
                } else {
                    this._toast("ok",
                        "Loaded " + res.unit_name);
                    this._pushHistory("ok",
                        res.unit_name + " loaded");
                }
                // Clear only the unit field so the operator can keep
                // beeping pallets onto the same truck.
                this.state.unitRaw = "";
                const el = document.getElementById("unit_input");
                if (el) el.focus();
            } else {
                this._toast("err", (res && res.error) || "Scan failed");
                this._pushHistory("err",
                    (res && res.error) || "scan failed");
            }
        } catch (err) {
            this._toast("err", err.message || String(err));
        } finally {
            this.state.loading = false;
        }
    }

    _pushHistory(kind, message) {
        this._historyId += 1;
        const now = new Date();
        const hh = String(now.getHours()).padStart(2, "0");
        const mm = String(now.getMinutes()).padStart(2, "0");
        const ss = String(now.getSeconds()).padStart(2, "0");
        this.state.history.unshift({
            id: this._historyId,
            kind: kind,
            time: hh + ":" + mm + ":" + ss,
            message: message,
        });
        // Keep the last 20 scans only.
        if (this.state.history.length > 20) {
            this.state.history.length = 20;
        }
    }

    _toast(kind, message) {
        this.state.toast = {kind, message};
        setTimeout(() => {
            if (this.state.toast && this.state.toast.message === message) {
                this.state.toast = null;
            }
        }, 4000);
    }
}

// ---------------------------------------------------------------------
// Boot — dispatch screen based on data-sb-floor-app on the mount.
// ---------------------------------------------------------------------
async function bootFloor() {
    const root = document.getElementById("sb_floor_root");
    if (!root || root.dataset.owlMounted === "1") return;
    root.dataset.owlMounted = "1";
    root.innerHTML = "";
    const app = root.getAttribute("data-sb-floor-app");
    let Cls = null;
    if (app === "bin-scan") {
        Cls = BinScanScreen;
    } else if (app === "load-unit") {
        Cls = LoadUnitScreen;
    } else {
        root.innerHTML =
            "<div class='sb_floor_err'>Unknown floor app: " +
            (app || "(missing)") +
            "</div>";
        return;
    }
    try {
        await mount(Cls, root, {props: {}, dev: false});
    } catch (err) {
        root.innerHTML =
            "<div class='sb_floor_err'>Failed to mount: " +
            (err.message || String(err)) +
            "</div>";
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootFloor);
} else {
    queueMicrotask(bootFloor);
}

// Expose for smoke tests.
window.sbFloorScreens = {BinScanScreen, LoadUnitScreen, bootFloor};
