/** @odoo-module **/
// =====================================================================
// Southbrook Configurator UX v2 — Phase 2b
//
// OWL Component refactor with live attribute data.
//
// What changed from Phase 1:
//   - Hardcoded OPTIONS / GROUPS / FINISH_COLORS removed.
//   - State hydrated on mount from POST /southbrook/api/configurator/state
//     (Phase 2a endpoint).
//   - Vanilla class -> OWL Component with useState, useRef, onWillStart,
//     onMounted. All reactive — picks trigger re-render automatically;
//     no more manual document.getElementById + innerHTML.
//   - Single component owns the entire reactive UI: left preview + summary
//     + action bar, right chip grid, top progress bar, optional bulk-tools
//     bar.
//
// Phase 2c additions on top:
//   - After every chip / select pick the component POSTs to the new
//     /southbrook/api/configurator/select endpoint with the complete
//     pick set. The server returns selected_value_ids, server-resolved
//     price + weight, and disabled_value_ids from the OCA rule engine.
//     The component reconciles its state from the response (server is
//     authoritative; client picks are optimistic).
//   - isValueDisabled() now returns state.disabledValueIds.includes(id);
//     the hardcoded Box-Material/Series rules are GONE.
//   - onAddToQuote POSTs to /southbrook/api/configurator/commit.
//     On success: navigate to redirect URL (the customer's Order
//     Builder). On login_required: navigate to login_url with a
//     return-to-here query string.
//
// What did NOT change:
//   - Cabinet preview render still uses the prototype's CSS-box drawing.
//   - Bulk template / import overlay logic is preserved (no Odoo server
//     wiring yet — Phase 4).
//   - SCSS unchanged — all DOM class names match Phase 1.
//
// Mount-point contract:
//   The QWeb template ships:
//     <section id="sb_cfg_v2_root" data-product-tmpl-id="<int>">
//       <div id="sb_cfg_v2_main_mount" data-internal-user="0|1">
//         (no-JS fallback "Loading…" text)
//       </div>
//     </section>
//   This bundle on DOMContentLoaded:
//     1. Finds #sb_cfg_v2_root; bails out (silent no-op) if absent.
//     2. Reads productTmplId from the data attribute.
//     3. Mounts <ConfiguratorV2> into #sb_cfg_v2_main_mount.
//   The static fallback inside the mount div is replaced when OWL mounts.
// =====================================================================

import {
    Component, mount, markup, onMounted, onWillStart, useRef, useState, xml,
} from "@odoo/owl";


// ---------- RPC helper (raw fetch — public /shop page, no Odoo service) ----------

async function rpcJsonCall(url, params = {}) {
    const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", method: "call", params }),
        credentials: "same-origin",
    });
    const json = await res.json();
    if (json.error) {
        throw new Error(json.error.data?.message || json.error.message || "RPC error");
    }
    return json.result;
}


// ---------- Phase-2b/c constants ----------

// Mapping of finish / box-material display names to a representative
// colour swatch for the CSS cabinet preview. Phase 3+ will source these
// from product.template.attribute.value.html_color (which the /state
// endpoint already surfaces as val.html_color but only for "color"
// display_type attributes today).
const FINISH_COLORS = {
    "White":          "#f3f0ea",
    "Maple Stain":    "#d9a566",
    "Cherry Stain":   "#8a3b2a",
    "Walnut Stain":   "#5a3b28",
    "Custom":         "#b9a07a",
    "Maple":          "#caa06a",
    "White Melamine": "#eceae4",
};

// Attribute names we plumb into the SKU composer + the spec line. The
// component looks these up by NAME in the live state.attributes map; if
// a name isn't on the template the slot is silently skipped.
const SKU_ATTR_NAMES = ["Width", "Series", "Finish"];
const SPEC_ATTR_NAMES = ["Width", "Series", "Finish", "Hinge Side", "Handle"];

// =====================================================================
// ConfiguratorV2 — single OWL component owning the entire reactive UI
// =====================================================================

class ConfiguratorV2 extends Component {
    static template = xml`
<div class="sb_cfg_v2_main">
  <t t-if="state.loading">
    <div class="sb_cfg_titlebar">
      <div class="sb_cfg_titlebar_l">
        <h1 class="sb_cfg_h1">Loading…</h1>
        <p class="sb_cfg_sub">Fetching configurator state</p>
      </div>
    </div>
  </t>
  <t t-elif="state.loadError">
    <div class="sb_cfg_titlebar">
      <div class="sb_cfg_titlebar_l">
        <h1 class="sb_cfg_h1">Couldn't load this configurator</h1>
        <p class="sb_cfg_sub" t-esc="state.loadError"/>
      </div>
    </div>
  </t>
  <t t-else="">
    <!-- TITLE BAR + BULK TOOLS ROW -->
    <div class="sb_cfg_titlebar">
      <div class="sb_cfg_titlebar_l">
        <h1 class="sb_cfg_h1" t-esc="state.product.name"/>
        <p class="sb_cfg_sub">
          Build a made-to-spec cabinet · live pricing ·
          SKU auto-generates as you configure
        </p>
      </div>
      <div t-if="props.isInternalUser"
           class="sb_cfg_bulkbar"
           aria-label="Bulk product tooling">
        <span class="sb_cfg_bulkbar_lbl">Bulk tools</span>
        <button type="button"
                class="sb_cfg_btn sb_cfg_btn_tpl"
                t-on-click="onDownloadTemplate">
          ⬇ Template Layout
        </button>
        <button type="button"
                class="sb_cfg_btn sb_cfg_btn_imp"
                t-on-click="onOpenImport">
          ⤒ Import Product
        </button>
      </div>
    </div>

    <!-- TWO-PANE GRID -->
    <div class="sb_cfg_grid">

      <!-- LEFT: preview + summary + action bar -->
      <aside class="sb_cfg_panel sb_cfg_left">

        <div class="sb_cfg_viewer" t-ref="viewer">
          <div class="sb_cfg_badge" t-esc="state.previewBadge"/>
          <div class="sb_cfg_cab" t-out="cabinetMarkup"/>
          <button type="button"
                  class="sb_cfg_editimg"
                  t-on-click="onReplacePhoto"
                  aria-label="Replace cabinet photo">
            📷 Replace photo
          </button>
        </div>
        <input type="file"
               t-ref="imgInput"
               accept="image/*"
               style="display:none"
               t-on-change="onPhotoFileSelected"/>

        <div class="sb_cfg_summary">
          <div class="sb_cfg_sumrow">
            <span class="sb_cfg_k">
              Price <span class="sb_cfg_livetag">LIVE</span>
            </span>
            <span class="sb_cfg_price">
              <t t-esc="formattedPrice"/>
            </span>
          </div>
          <div class="sb_cfg_sumrow">
            <span class="sb_cfg_k">Est. Weight</span>
            <span class="sb_cfg_weight" t-esc="weightText"/>
          </div>
          <div class="sb_cfg_sumrow">
            <span class="sb_cfg_k">Auto SKU</span>
            <span class="sb_cfg_sku" t-esc="autoSku"/>
          </div>
          <div class="sb_cfg_specline">
            <b>Your build:</b>
            <span t-esc="specLine"/>
          </div>
          <div class="sb_cfg_completion">
            <div class="sb_cfg_ring"
                 t-attf-style="--p:{{completionPct}}">
              <i><t t-esc="completionPct"/>%</i>
            </div>
            <span t-esc="completionText"/>
          </div>
        </div>

        <div class="sb_cfg_actionbar">
          <span t-att-class="validationClass"
                role="status" aria-live="polite"
                t-out="validationText"/>
          <button type="button"
                  class="sb_cfg_btn sb_cfg_btn_primary"
                  t-att-disabled="state.adding ? 'disabled' : null"
                  t-on-click="onAddToQuote">
            <t t-if="state.adding">Adding…</t>
            <t t-else="">Add to Quote ➞</t>
          </button>
        </div>

      </aside>

      <!-- RIGHT: chip-selector configurator. Data-driven from state.groups. -->
      <section class="sb_cfg_panel sb_cfg_right"
               aria-label="Cabinet configuration options">
        <t t-foreach="state.groups" t-as="group" t-key="group.title">
          <div class="sb_cfg_group"
               t-att-class="state.closedGroups[group.title] ? 'sb_cfg_closed' : ''">
            <div class="sb_cfg_ghead"
                 role="button"
                 tabindex="0"
                 t-att-aria-expanded="state.closedGroups[group.title] ? 'false' : 'true'"
                 t-on-click="() => this.toggleGroup(group.title)"
                 t-on-keydown="(ev) => this.onGroupKeydown(ev, group.title)">
              <span class="sb_cfg_gt">
                <span class="sb_cfg_check"
                      t-att-class="groupComplete(group) ? 'sb_cfg_check_done' : ''">
                  <t t-if="groupComplete(group)">✓</t>
                  <t t-else=""><t t-esc="group_index + 1"/></t>
                </span>
                <t t-esc="group.title"/>
              </span>
              <span class="sb_cfg_gnum">
                <span t-esc="groupPickCount(group)"/>/<t t-esc="group.attribute_ids.length"/>
                &#160;
                <span class="sb_cfg_chev">❮</span>
              </span>
            </div>
            <div class="sb_cfg_gbody">
              <t t-foreach="group.attribute_ids"
                 t-as="attrId" t-key="attrId">
                <t t-set="attr" t-value="state.attributes[attrId]"/>
                <t t-if="attr">
                  <div t-att-class="fieldClass(attr, group)">
                    <label>
                      <t t-esc="attr.name"/>
                      <span class="sb_cfg_pd"
                            t-esc="attrPriceDelta(attrId)"/>
                    </label>
                    <t t-if="attr.display_type === 'select'">
                      <select t-on-change="(ev) => this.onSelectChange(attrId, ev)"
                              t-att-aria-label="attr.name">
                        <option value="">Select <t t-esc="attr.name"/>…</option>
                        <t t-foreach="attr.values" t-as="val" t-key="val.id">
                          <option t-att-value="val.id"
                                  t-att-selected="state.picked[attrId] === val.id"
                                  t-att-disabled="isValueDisabled(attr, val) ? 'disabled' : null"
                                  t-esc="val.name"/>
                        </t>
                      </select>
                    </t>
                    <t t-else="">
                      <div class="sb_cfg_chips"
                           role="radiogroup"
                           t-att-aria-label="attr.name">
                        <t t-foreach="attr.values" t-as="val" t-key="val.id">
                          <div t-att-class="chipClass(attrId, val)"
                               role="radio"
                               t-att-tabindex="isValueDisabled(attr, val) ? '-1' : '0'"
                               t-att-aria-checked="state.picked[attrId] === val.id ? 'true' : 'false'"
                               t-on-click="() => this.onChipClick(attrId, val)"
                               t-on-keydown="(ev) => this.onChipKeydown(ev, attrId, val)"
                               t-esc="val.name"/>
                        </t>
                      </div>
                    </t>
                  </div>
                </t>
              </t>
            </div>
          </div>
        </t>
      </section>

    </div>
  </t>
</div>
    `;
    static props = {
        productTmplId: { type: Number },
        isInternalUser: { type: Boolean, optional: true },
    };

    setup() {
        this.state = useState({
            // RPC + load state
            loading: true,
            loadError: null,
            // Server-resolved fields
            product: null,                  // {tmpl_id, sku, name, list_price, currency}
            currency: null,
            sessionId: null,
            basePrice: 0,
            groups: [],
            attributes: {},                 // {<id>: {name, display_type, sequence, required, values: [...]}}
            // Picks: {<attribute_id>: <selected_value_id> | null}
            picked: {},
            // 2c: server-resolved fields after each /select.
            serverPrice: null,              // null until first /select responds
            serverWeight: null,
            disabledValueIds: [],           // value_ids forbidden by OCA rule engine
            selecting: false,               // /select RPC in flight
            // 2c: /commit state.
            adding: false,                  // /commit RPC in flight
            commitMessage: null,            // surfaced if /commit fails
            // UI flags
            closedGroups: {},               // {<title>: true}  — collapsed groups
            userPhoto: null,                // dataURL or null
            previewBadge: "LIVE PREVIEW",
            // Bulk tools — Phase 4: full server-side preview/commit
            // pipeline. importReport caches the entire /preview or
            // /commit response so the commit step doesn't need to
            // re-request; importRows is the flattened per-row view
            // used by the preview table + error CSV.
            importRows: [],
            importReport: null,
        });

        // Refs for DOM-attached interactions (file inputs + drop zones).
        this.viewerRef = useRef("viewer");
        this.imgInputRef = useRef("imgInput");

        // Fetch the configurator state from the Phase-2a endpoint before
        // the first render so the user never sees a flash of empty UI.
        onWillStart(async () => {
            try {
                const r = await rpcJsonCall(
                    "/southbrook/api/configurator/state",
                    { product_tmpl_id: this.props.productTmplId },
                );
                if (!r || !r.ok) {
                    this.state.loadError = (r && r.message)
                        || "The server didn't return a configurator state.";
                    return;
                }
                this._hydrateFromState(r);
            } catch (err) {
                this.state.loadError = err.message || String(err);
            } finally {
                this.state.loading = false;
            }
        });

        // After mount, fire one /select with the current pick set so
        // the disabled_value_ids + server_price + server_weight land
        // BEFORE the user makes their first pick. This gives the rule
        // engine a chance to disable invalid initial combinations
        // (e.g. session restored from a partial earlier visit).
        onMounted(() => {
            this._serverReconcile();
        });

        // Drag-drop on the viewer for the photo replace, and a sync of
        // the imported import-overlay handlers (the modal lives outside
        // the OWL tree at body level).
        onMounted(() => {
            this._wireViewerDragDrop();
            this._wireImportOverlay();
        });
    }

    // ------------------------------------------------------------------
    // State hydration from /state response
    // ------------------------------------------------------------------

    _hydrateFromState(r) {
        this.state.product = r.product;
        this.state.currency = r.product.currency;
        this.state.sessionId = r.session_id;
        this.state.basePrice = r.base_price;
        this.state.groups = r.groups;
        this.state.attributes = r.attributes;
        // Initialise picked: null for every attribute; honour any
        // server-persisted selections from the session.
        const picked = {};
        for (const attrId of Object.keys(r.attributes)) {
            picked[attrId] = null;
        }
        // Resolve server-side selected_value_ids back to {attr_id: val_id}.
        for (const valId of (r.selected_value_ids || [])) {
            for (const [attrId, attr] of Object.entries(r.attributes)) {
                if (attr.values.some((v) => v.id === valId)) {
                    picked[attrId] = valId;
                    break;
                }
            }
        }
        this.state.picked = picked;
        // All groups start expanded.
        for (const g of r.groups) {
            this.state.closedGroups[g.title] = false;
        }
    }

    // ------------------------------------------------------------------
    // Reactive computed getters — driven by useState changes
    // ------------------------------------------------------------------

    get totalPrice() {
        let p = this.state.basePrice || 0;
        for (const [attrId, valId] of Object.entries(this.state.picked)) {
            if (valId === null) continue;
            const attr = this.state.attributes[attrId];
            if (!attr) continue;
            const val = attr.values.find((v) => v.id === valId);
            if (val) p += val.price_extra || 0;
        }
        return p;
    }

    get formattedPrice() {
        const cur = this.state.currency || { symbol: "$", position: "before" };
        // Prefer the server-resolved price (authoritative — reflects
        // OCA's full price computation including any rule effects).
        // Fall back to the client-side sum during the brief moment
        // between mount and first /select response.
        const raw = this.state.serverPrice !== null
            ? this.state.serverPrice
            : this.totalPrice;
        const amt = Math.round(raw).toLocaleString();
        return cur.position === "after"
            ? `${amt}${cur.symbol}`
            : `${cur.symbol}${amt}`;
    }

    get weightText() {
        // Server-resolved weight from /select response. Shows "—" until
        // the first pick triggers /select (no point estimating client-
        // side when the server is one round-trip away).
        if (this.state.serverWeight === null) return "—";
        return `${this.state.serverWeight.toFixed(1)} kg`;
    }

    get autoSku() {
        // SKU_ATTR_NAMES = [Width, Series, Finish]. Compose
        // SB-<width3>-<series3>-<finish3>. Falls back to "—" when no
        // width is picked yet.
        const parts = SKU_ATTR_NAMES.map((name) => this._abbrPickedByName(name));
        if (parts[0] === "XXX") return "—";
        return `SB-${parts.join("-")}`;
    }

    _abbrPickedByName(attrName) {
        const attrId = Object.keys(this.state.attributes)
            .find((id) => this.state.attributes[id].name === attrName);
        if (!attrId) return "XXX";
        const valId = this.state.picked[attrId];
        if (valId === null) return "XXX";
        const attr = this.state.attributes[attrId];
        const val = attr.values.find((v) => v.id === valId);
        if (!val) return "XXX";
        return val.name.replace(/[^A-Za-z0-9]/g, "").substring(0, 3).toUpperCase();
    }

    get specLine() {
        const parts = [];
        for (const name of SPEC_ATTR_NAMES) {
            const attrId = Object.keys(this.state.attributes)
                .find((id) => this.state.attributes[id].name === name);
            if (!attrId) continue;
            const valId = this.state.picked[attrId];
            if (valId === null) continue;
            const val = this.state.attributes[attrId].values
                .find((v) => v.id === valId);
            if (val) parts.push(val.name);
        }
        return parts.length ? parts.join("  ·  ") : "nothing selected yet";
    }

    get completionPct() {
        const total = Object.keys(this.state.attributes).length;
        if (!total) return 0;
        const done = Object.values(this.state.picked)
            .filter((v) => v !== null).length;
        return Math.round((done / total) * 100);
    }

    get completionText() {
        const total = Object.keys(this.state.attributes).length;
        const done = Object.values(this.state.picked)
            .filter((v) => v !== null).length;
        return done === total
            ? "All set — ready to add to quote"
            : `${done} of ${total} options chosen`;
    }

    get validationClass() {
        return this.completionPct === 100
            ? "sb_cfg_note sb_cfg_note_ok"
            : "sb_cfg_note sb_cfg_note_bad";
    }

    get validationText() {
        const total = Object.keys(this.state.attributes).length;
        const done = Object.values(this.state.picked)
            .filter((v) => v !== null).length;
        return this.completionPct === 100
            ? markup("✓ All options valid · ready")
            : markup(`${total - done} option(s) still needed`);
    }

    // ------------------------------------------------------------------
    // Per-group / per-attribute helpers used by the template
    // ------------------------------------------------------------------

    groupPickCount(group) {
        return group.attribute_ids
            .filter((id) => this.state.picked[String(id)] !== null
                         || this.state.picked[id] !== null)
            .length;
    }

    groupComplete(group) {
        return this.groupPickCount(group) === group.attribute_ids.length;
    }

    attrPriceDelta(attrId) {
        const valId = this.state.picked[attrId];
        if (valId === null) return "";
        const attr = this.state.attributes[attrId];
        if (!attr) return "";
        const val = attr.values.find((v) => v.id === valId);
        if (!val || !val.price_extra) return "";
        return val.price_extra > 0
            ? `+$${val.price_extra}`
            : `-$${Math.abs(val.price_extra)}`;
    }

    fieldClass(attr, group) {
        // The prototype used "full" width for Finish + for the last
        // odd-position field in a group. We preserve the same visual
        // weighting.
        if (attr.name === "Finish") {
            return "sb_cfg_field sb_cfg_field_full";
        }
        // Mark the last field as full if the group has an odd number
        // of fields (so the trailing odd one spans both columns).
        const isLast = group.attribute_ids[group.attribute_ids.length - 1]
                       === Number(Object.keys(this.state.attributes)
                                  .find((id) => this.state.attributes[id] === attr));
        if (isLast && (group.attribute_ids.length % 2) !== 0) {
            return "sb_cfg_field sb_cfg_field_full";
        }
        return "sb_cfg_field";
    }

    chipClass(attrId, val) {
        const sel = this.state.picked[attrId] === val.id;
        const attr = this.state.attributes[attrId];
        const dis = this.isValueDisabled(attr, val);
        return "sb_cfg_chip"
            + (sel ? " sb_cfg_chip_sel" : "")
            + (dis ? " sb_cfg_chip_disabled" : "");
    }

    // ------------------------------------------------------------------
    // Disable check — sourced from the server's /select response.
    //
    // Phase 2b shipped a hardcoded ruleset that mirrored the prototype.
    // Phase 2c replaces it with state.disabledValueIds, which the
    // /select endpoint populates from OCA's product.config.line rule
    // engine. Server is authoritative; the client just renders the set.
    // ------------------------------------------------------------------
    isValueDisabled(attr, val) {
        return this.state.disabledValueIds.includes(val.id);
    }

    // ------------------------------------------------------------------
    // Event handlers — chip / select / group toggle / quote
    // ------------------------------------------------------------------

    onChipClick(attrId, val) {
        const attr = this.state.attributes[attrId];
        if (this.isValueDisabled(attr, val)) return;
        this._pick(attrId, val.id);
    }

    onChipKeydown(ev, attrId, val) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.onChipClick(attrId, val);
        }
    }

    onSelectChange(attrId, ev) {
        const v = ev.target.value;
        this._pick(attrId, v === "" ? null : parseInt(v, 10));
    }

    toggleGroup(title) {
        this.state.closedGroups[title] = !this.state.closedGroups[title];
    }

    onGroupKeydown(ev, title) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.toggleGroup(title);
        }
    }

    async _pick(attrId, valId) {
        // Optimistic client update — the chip flips selected immediately
        // so the UI feels responsive even before /select returns.
        this.state.picked[attrId] = valId;
        await this._serverReconcile();
    }

    async _serverReconcile() {
        // POST the COMPLETE current pick set; the server resolves what
        // changed against the session and applies the rule engine.
        //
        // RACE GUARD: rapid clicks fire multiple overlapping /select
        // RPCs. Each later request includes a SUPERSET of the picks
        // the earlier ones sent. If an earlier response arrives after
        // a later one, naive reconciliation overwrites
        // state.picked with the older snapshot — eating the user's
        // newer clicks. Stamp each call with a monotonic sequence
        // number and bail at every await boundary if a newer call has
        // started.
        if (this.state.sessionId === null) return;
        if (this._reconcileSeq === undefined) this._reconcileSeq = 0;
        const mySeq = ++this._reconcileSeq;

        const valueIds = Object.values(this.state.picked)
            .filter((v) => v !== null);
        this.state.selecting = true;
        try {
            const r = await rpcJsonCall(
                "/southbrook/api/configurator/select",
                {
                    session_id: this.state.sessionId,
                    value_ids: valueIds,
                },
            );
            // Stale-response guard. If another reconcile fired during
            // the await, drop this response — the newer one (with the
            // user's later clicks) is what should win.
            if (mySeq !== this._reconcileSeq) return;

            if (r && r.ok) {
                this.state.disabledValueIds = r.disabled_value_ids || [];
                this.state.serverPrice = r.price;
                this.state.serverWeight = r.weight;
                // The server may have cleared picks the rule engine
                // marks as invalid — reconcile our local picked map
                // back to what the server actually kept.
                this._reconcilePicksFromServer(r.selected_value_ids || []);
            } else if (r && r.error === "rule_blocked") {
                this._toast(`Rule: ${r.message || "selection forbidden"}`);
            } else if (r && r.error === "session_locked") {
                this._toast(
                    "This session was already committed. Reload the page "
                    + "to start a new configuration."
                );
            }
        } catch (err) {
            // Network blip — keep the optimistic state and surface a
            // muted toast so the customer knows pricing may be stale.
            // Don't surface stale-response errors either.
            if (mySeq !== this._reconcileSeq) return;
            console.warn("select RPC failed:", err);
            this._toast("Couldn't sync with server — pricing may be stale.");
        } finally {
            // Only flip selecting back off when WE were the most
            // recent call. Otherwise a still-pending newer call is
            // doing the work.
            if (mySeq === this._reconcileSeq) {
                this.state.selecting = false;
            }
        }
    }

    _reconcilePicksFromServer(serverValueIds) {
        // Snapshot the previous pick set so we can diff against the
        // server's response and surface any picks the rule engine
        // cleared (e.g. switching Series to Signature invalidates a
        // previously-picked White Melamine, so OCA's update_config
        // drops it from session.value_ids). Without this notice the
        // completion counter just silently drops 9/12 → 8/12 and the
        // customer doesn't know which option vanished or why.
        const previouslyPickedAttrs = Object.entries(this.state.picked)
            .filter(([_, vid]) => vid !== null)
            .map(([aid, vid]) => {
                const attr = this.state.attributes[aid];
                const val = attr?.values?.find((v) => v.id === vid);
                return {aid, attrName: attr?.name, valName: val?.name};
            });

        const newPicked = {};
        for (const attrId of Object.keys(this.state.attributes)) {
            newPicked[attrId] = null;
        }
        for (const valId of serverValueIds) {
            for (const [attrId, attr] of Object.entries(this.state.attributes)) {
                if (attr.values.some((v) => v.id === valId)) {
                    newPicked[attrId] = valId;
                    break;
                }
            }
        }

        // Diff: any attribute that had a value before but doesn't now
        // was cleared by the server (rule engine drop). Tell the
        // customer by name + by previous value so they can re-pick
        // without a "what just happened" moment.
        const cleared = previouslyPickedAttrs.filter(
            (p) => newPicked[p.aid] === null,
        );
        if (cleared.length) {
            const labels = cleared
                .filter((p) => p.attrName)
                .map((p) => p.valName
                            ? `${p.attrName} (${p.valName})`
                            : p.attrName);
            if (labels.length) {
                this._toast(
                    `Cleared by rule change: ${labels.join(", ")} — `
                    + `please re-pick.`
                );
            }
        }

        this.state.picked = newPicked;
    }

    async onAddToQuote() {
        if (this.state.adding) return;
        const missing = Object.entries(this.state.picked)
            .filter(([_, valId]) => valId === null)
            .map(([aid, _]) => this.state.attributes[aid].name);
        if (missing.length) {
            this._toast(`Please choose: ${missing.join(", ")}`);
            return;
        }
        this.state.adding = true;
        try {
            const r = await rpcJsonCall(
                "/southbrook/api/configurator/commit",
                { session_id: this.state.sessionId },
            );
            if (r && r.ok) {
                this._toast(
                    `Added to quote · ${this.autoSku} · `
                    + `redirecting to your order…`
                );
                if (r.redirect) {
                    window.location.href = r.redirect;
                }
            } else if (r && r.error === "login_required") {
                // Send the visitor to signup with a return URL so they
                // come back to this exact configuration page after.
                const ret = encodeURIComponent(window.location.pathname);
                const login = r.login_url || "/web/signup";
                this._toast("Sign in or create a free account to continue…");
                window.location.href = `${login}?redirect=${ret}`;
            } else if (r && r.error === "validation_failed") {
                this._toast(`Couldn't commit: ${r.message}`);
            } else if (r && r.error === "session_locked") {
                this._toast(
                    "This session was already committed. Reload to start fresh."
                );
            } else {
                this._toast(
                    `Couldn't add to quote: ${(r && (r.message || r.error)) || "unknown error"}`
                );
            }
        } catch (err) {
            this._toast(`Network error: ${err.message || String(err)}`);
        } finally {
            this.state.adding = false;
        }
    }

    // ------------------------------------------------------------------
    // Cabinet preview render — same CSS-box drawing as Phase 1
    // ------------------------------------------------------------------

    get cabinetMarkup() {
        if (this.state.userPhoto) {
            return markup(
                `<img class="sb_cfg_user_photo" src="${this.state.userPhoto}" alt="Custom cabinet photo"/>`
            );
        }
        const pickedNameOf = (attrName, fallback) => {
            const attrId = Object.keys(this.state.attributes)
                .find((id) => this.state.attributes[id].name === attrName);
            if (!attrId) return fallback;
            const valId = this.state.picked[attrId];
            if (valId === null) return fallback;
            const a = this.state.attributes[attrId];
            const v = a.values.find((vv) => vv.id === valId);
            return v ? v.name : fallback;
        };
        const widthName = pickedNameOf("Width", "15 in");
        const wIdx = ["9 in", "12 in", "15 in", "18 in", "21 in", "24 in",
                      "27 in", "30 in", "33 in", "36 in"].indexOf(widthName);
        const wpx = 70 + Math.max(0, wIdx) * 16;
        const finishName = pickedNameOf("Finish",
            pickedNameOf("Box Material", "White"));
        const color = FINISH_COLORS[finishName] || "#dcd3c4";
        const doorCountName = pickedNameOf("Door Count", "1");
        const doors = doorCountName === "2" ? 2 : 1;
        const hinge = pickedNameOf("Hinge Side", "LH (Left Hand)");
        const isLH = hinge.startsWith("LH");
        const handle = pickedNameOf("Handle", "Bar Pull");
        const handleHtml = (handle === "None") ? "" :
            (handle === "Knob"
                ? `<div style="position:absolute;top:50%;${isLH ? "right:8px" : "left:8px"};width:7px;height:7px;border-radius:50%;background:#2f3b52"></div>`
                : `<div style="position:absolute;top:50%;${isLH ? "right:7px" : "left:7px"};width:4px;height:26px;border-radius:3px;background:#2f3b52"></div>`);
        const doorHtml = (doors === 2)
            ? `<div style="position:absolute;inset:6px;display:flex;gap:4px">
                  <div style="flex:1;position:relative;border:1px solid rgba(0,0,0,.12);border-radius:3px;background:rgba(255,255,255,.12)">
                    <div style="position:absolute;top:50%;right:5px;width:3px;height:20px;border-radius:3px;background:#2f3b52"></div>
                  </div>
                  <div style="flex:1;position:relative;border:1px solid rgba(0,0,0,.12);border-radius:3px;background:rgba(255,255,255,.12)">
                    <div style="position:absolute;top:50%;left:5px;width:3px;height:20px;border-radius:3px;background:#2f3b52"></div>
                  </div>
                </div>`
            : `<div style="position:absolute;inset:6px;border:1px solid rgba(0,0,0,.12);border-radius:3px;background:rgba(255,255,255,.1)">${handleHtml}</div>`;
        return markup(
            `<div style="width:${wpx}px;height:150px;background:${color};position:relative;border-top:3px solid rgba(0,0,0,.08);border-radius:4px;box-shadow:0 18px 30px -12px rgba(40,55,80,.4)">${doorHtml}</div>`
        );
    }

    // ------------------------------------------------------------------
    // Photo replace + drag-drop
    // ------------------------------------------------------------------

    onReplacePhoto() {
        if (this.imgInputRef.el) this.imgInputRef.el.click();
    }

    onPhotoFileSelected(ev) {
        const f = ev.target.files[0];
        if (!f) return;
        const r = new FileReader();
        r.onload = (loaded) => {
            this.state.userPhoto = loaded.target.result;
            this.state.previewBadge = "CUSTOM PHOTO";
        };
        r.readAsDataURL(f);
    }

    _wireViewerDragDrop() {
        const el = this.viewerRef.el;
        if (!el) return;
        ["dragover", "dragenter"].forEach((evName) => {
            el.addEventListener(evName, (e) => {
                e.preventDefault();
                el.classList.add("drag");
            });
        });
        ["dragleave", "drop"].forEach((evName) => {
            el.addEventListener(evName, (e) => {
                e.preventDefault();
                el.classList.remove("drag");
            });
        });
        el.addEventListener("drop", (e) => {
            const f = e.dataTransfer.files[0];
            if (f && f.type.indexOf("image") === 0 && this.imgInputRef.el) {
                // Reuse the file-input change handler via a dispatched
                // pseudo-event so the FileReader path stays single-sourced.
                this.onPhotoFileSelected({ target: { files: [f] } });
            }
        });
    }

    // ------------------------------------------------------------------
    // Bulk tools — preserved client-side logic from Phase 1
    // ------------------------------------------------------------------

    // ------------------------------------------------------------------
    // Bulk tools (Phase 4) — server-driven template download +
    // upload + preview + commit pipeline.
    // ------------------------------------------------------------------

    onDownloadTemplate() {
        // Server-side xlsx generation. Navigate to the route as a
        // download — the browser handles the file save automatically.
        // No fetch needed: the Content-Disposition: attachment header
        // triggers the download dialog and the URL gets the user's
        // session cookie via same-origin.
        window.location.href = "/southbrook/api/import/template";
        this._toast("Generating template — your download should start in a moment.");
    }

    onOpenImport() {
        // Clear any stale preview rows from a previous session.
        this.state.importRows = [];
        this.state.importReport = null;
        const body = document.getElementById("sb_cfg_previewBody");
        if (body) body.innerHTML = `
            <tr><td colspan="8" style="text-align:center;color:#6b7488;
                                        padding:20px">
                Drop an xlsx file above (or click to browse) to preview
                what would be imported.
            </td></tr>`;
        const ok = document.getElementById("sb_cfg_okCount");
        const bad = document.getElementById("sb_cfg_badCount");
        const commitBtn = document.getElementById("sb_cfg_commitBtn");
        if (ok) ok.textContent = "0 valid";
        if (bad) bad.textContent = "0 errors";
        if (commitBtn) {
            commitBtn.textContent = "Commit 0 valid rows";
            commitBtn.disabled = true;
        }
        const overlay = document.getElementById("sb_cfg_importOverlay");
        if (overlay) {
            overlay.classList.add("sb_cfg_overlay_show");
            overlay.setAttribute("aria-hidden", "false");
        }
    }

    _wireImportOverlay() {
        // The overlay markup lives outside the OWL tree (body-level
        // position:fixed). Wire its click handlers + drop zone via the
        // imperative DOM API.
        const overlay = document.getElementById("sb_cfg_importOverlay");
        if (!overlay) return;
        overlay.querySelectorAll('[data-action="close-import"]')
            .forEach((b) => b.addEventListener("click", () => this._closeImport()));
        const dl = overlay.querySelector('[data-action="download-errors"]');
        if (dl) dl.addEventListener("click", () => this._downloadImportErrors());
        const commitBtn = overlay.querySelector('[data-action="commit-import"]');
        if (commitBtn) commitBtn.addEventListener("click", () => this._commitImport());

        const drop = document.getElementById("sb_cfg_drop");
        const fileInput = document.getElementById("sb_cfg_fileInput");
        if (drop && fileInput) {
            // xlsx + csv accepted, but the server-side parser is
            // openpyxl which only handles xlsx for v1.
            fileInput.accept = ".xlsx";
            drop.addEventListener("click", () => fileInput.click());
            ["dragover", "dragenter"].forEach((evName) => {
                drop.addEventListener(evName, (e) => {
                    e.preventDefault();
                    drop.classList.add("sb_cfg_drop_drag");
                });
            });
            ["dragleave", "drop"].forEach((evName) => {
                drop.addEventListener(evName, (e) => {
                    e.preventDefault();
                    drop.classList.remove("sb_cfg_drop_drag");
                });
            });
            drop.addEventListener("drop", (e) => {
                const f = e.dataTransfer.files[0];
                if (f) {
                    this._submitImportPreview(f);
                }
            });
            fileInput.onchange = (e) => {
                const f = e.target.files[0];
                if (!f) return;
                this._submitImportPreview(f);
            };
        }
    }

    async _submitImportPreview(file) {
        // POST multipart to /preview. Read-only — no writes hit the DB
        // until the user explicitly clicks Commit.
        this._toast(`Uploading ${file.name}…`);
        const formData = new FormData();
        formData.append("file", file);
        try {
            const res = await fetch("/southbrook/api/import/preview", {
                method: "POST",
                body: formData,
                credentials: "same-origin",
            });
            const body = await res.json();
            this._renderImportReport(body);
            if (body.ok) {
                const summary = body.summary || {};
                this._toast(
                    `Preview: ${summary.valid || 0} valid · `
                    + `${summary.invalid || 0} invalid · `
                    + `${summary.skipped_sheets || 0} sheet(s) deferred`
                );
            } else {
                this._toast(
                    `Preview failed: ${body.message || body.error || "unknown"}`
                );
            }
        } catch (err) {
            this._toast(`Network error: ${err.message || String(err)}`);
        }
    }

    _renderImportReport(report) {
        // Cache for the commit button + error CSV download.
        this.state.importReport = report;
        // Flatten all PRODUCTS rows for display (other sheets get
        // their own summary row so the user can see they were noticed).
        const allRows = [];
        for (const sheet of (report.sheets || [])) {
            if (sheet.sheet === "PRODUCTS") {
                for (const row of (sheet.rows || [])) {
                    allRows.push(row);
                }
            } else if (sheet.status === "deferred") {
                allRows.push({
                    row: "—",
                    default_code: "",
                    status: "deferred",
                    sheet: sheet.sheet,
                    errors: [sheet.message],
                });
            } else if (sheet.status === "unknown") {
                allRows.push({
                    row: "—",
                    default_code: "",
                    status: "unknown",
                    sheet: sheet.sheet,
                    errors: [sheet.message],
                });
            }
        }
        this.state.importRows = allRows;

        const body = document.getElementById("sb_cfg_previewBody");
        if (!body) return;
        const html = allRows.map((row) => {
            const isOk = row.status === "preview_ok"
                       || row.status === "created"
                       || row.status === "updated";
            const isErr = row.status === "invalid"
                        || row.status === "error"
                        || row.status === "skipped";
            const isInfo = row.status === "deferred"
                        || row.status === "unknown";
            const cls = isErr ? "sb_cfg_row_bad" : "";
            const statClass = isOk ? "g" : isErr ? "r" : "g";
            const statText = isOk ? "✓ " + row.status
                          : isErr ? "✕ " + row.status
                          : "ⓘ " + row.status;
            const errCellText = (row.errors || []).join("; ")
                              + (row.sheet ? ` [${row.sheet}]` : "");
            const proposed = row.proposed_vals || {};
            return `
                <tr class="${cls}">
                  <td><span class="sb_cfg_rowstat sb_cfg_rowstat_${statClass}">${statText}</span></td>
                  <td>${row.default_code || ""}</td>
                  <td>${proposed.name || ""}</td>
                  <td>${proposed.list_price !== undefined ? "$" + proposed.list_price : ""}</td>
                  <td>${proposed.southbrook_category || ""}</td>
                  <td>${proposed.southbrook_icon_key || ""}</td>
                  <td>${row.row || ""}</td>
                  <td class="sb_cfg_reason">${errCellText}</td>
                </tr>`;
        }).join("");
        body.innerHTML = html || `
            <tr><td colspan="8" style="text-align:center;color:#6b7488;
                                        padding:20px">
                No rows in the file.
            </td></tr>`;
        const summary = report.summary || {};
        const okEl = document.getElementById("sb_cfg_okCount");
        const badEl = document.getElementById("sb_cfg_badCount");
        const commitBtn = document.getElementById("sb_cfg_commitBtn");
        if (okEl) okEl.textContent = `${summary.valid || 0} valid`;
        if (badEl) badEl.textContent = `${summary.invalid || 0} errors`;
        if (commitBtn) {
            const n = summary.valid || 0;
            commitBtn.textContent = `Commit ${n} valid row${n === 1 ? "" : "s"}`;
            commitBtn.disabled = n === 0;
        }
    }

    async _commitImport() {
        // The commit step uses the file STILL in the file input
        // element (the user's last upload). We require a file because
        // /commit takes the file fresh on each POST — no server-side
        // caching of the preview content (deliberate: prevents stale
        // commits if the user edits and re-uploads).
        const fileInput = document.getElementById("sb_cfg_fileInput");
        const file = fileInput && fileInput.files && fileInput.files[0];
        if (!file) {
            this._toast("Upload a file first, then click Commit.");
            return;
        }
        // Human-confirmation gate at the client: an explicit prompt
        // before we send confirm=true. The server ALSO requires it,
        // so this is the second of two consents.
        const valid = (this.state.importReport
                    && this.state.importReport.summary
                    && this.state.importReport.summary.valid) || 0;
        if (valid === 0) {
            this._toast("No valid rows to commit.");
            return;
        }
        if (!window.confirm(
            `Commit ${valid} valid product${valid === 1 ? "" : "s"} now? `
            + `This will create or update product.template records. `
            + `Invalid rows are skipped.`
        )) {
            return;
        }
        this._toast(`Committing ${valid} row(s)…`);
        const formData = new FormData();
        formData.append("file", file);
        formData.append("confirm", "true");
        try {
            const res = await fetch("/southbrook/api/import/commit", {
                method: "POST",
                body: formData,
                credentials: "same-origin",
            });
            const body = await res.json();
            this._renderImportReport(body);
            if (body.ok) {
                const s = body.summary || {};
                this._toast(
                    `Committed: ${s.created || 0} created · `
                    + `${s.updated || 0} updated · `
                    + `${s.invalid || 0} skipped · `
                    + `${s.errors || 0} errors`
                );
                // Close the overlay after a beat so the user sees the
                // updated row statuses before it vanishes.
                setTimeout(() => this._closeImport(), 2400);
            } else {
                this._toast(
                    `Commit failed: ${body.message || body.error || "unknown"}`
                );
            }
        } catch (err) {
            this._toast(`Network error: ${err.message || String(err)}`);
        }
    }

    _closeImport() {
        const overlay = document.getElementById("sb_cfg_importOverlay");
        if (overlay) {
            overlay.classList.remove("sb_cfg_overlay_show");
            overlay.setAttribute("aria-hidden", "true");
        }
    }

    _downloadImportErrors() {
        // CSV of the rows the server marked as invalid or errored.
        const rows = (this.state.importRows || [])
            .filter((r) => (r.errors || []).length);
        if (!rows.length) {
            this._toast("No errored rows to download.");
            return;
        }
        const csv = "row,sku,sheet,issues\n"
            + rows.map((r) => {
                const sku = (r.default_code || "").replace(/"/g, '""');
                const sheet = (r.sheet || "PRODUCTS").replace(/"/g, '""');
                const issues = (r.errors || []).join("; ").replace(/"/g, '""');
                return `${r.row || ""},"${sku}","${sheet}","${issues}"`;
            }).join("\n");
        const a = document.createElement("a");
        a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
        a.download = "import_errors.csv";
        a.click();
        this._toast("Error report downloaded");
    }

    // ------------------------------------------------------------------
    // Toast — body-level element, hit via document.getElementById
    // ------------------------------------------------------------------

    _toast(msg) {
        const t = document.getElementById("sb_cfg_toast");
        if (!t) return;
        t.textContent = msg;
        t.classList.add("sb_cfg_toast_show");
        clearTimeout(this._toastTimer);
        this._toastTimer = setTimeout(() => {
            t.classList.remove("sb_cfg_toast_show");
        }, 3400);
    }
}


// ---------- Bootstrap: find mount, parse data attrs, mount component ----------
//
// The frontend_lazy bundle (where this file lands) is loaded async/defer,
// often AFTER DOMContentLoaded has already fired. Attaching a DOMContentLoaded
// listener at module-load time misses the event entirely and the component
// never mounts. Pattern: check document.readyState first; if the DOM is
// already past 'loading', call init() synchronously. Otherwise wait.

async function bootstrapConfiguratorV2() {
    const root = document.getElementById("sb_cfg_v2_root");
    if (!root) return;     // bundle no-op on every page without v2

    const productTmplId = parseInt(
        root.getAttribute("data-product-tmpl-id") || "", 10);
    if (!productTmplId) {
        console.warn("sb_cfg_v2_root missing data-product-tmpl-id");
        return;
    }

    const target = document.getElementById("sb_cfg_v2_main_mount");
    if (!target) {
        console.warn("sb_cfg_v2_main_mount not found");
        return;
    }
    const isInternalUser =
        (target.getAttribute("data-internal-user") || "0") === "1";

    // Clear the no-JS "Loading…" fallback before mounting so OWL doesn't
    // duplicate the title bar.
    target.innerHTML = "";

    try {
        await mount(ConfiguratorV2, target, {
            props: { productTmplId, isInternalUser },
        });
    } catch (err) {
        // Last-resort: surface the mount failure in the fallback area
        // so a visitor sees something explicit rather than a blank space.
        target.innerHTML = `
            <div class="sb_cfg_titlebar">
              <div class="sb_cfg_titlebar_l">
                <h1 class="sb_cfg_h1">Couldn't load this configurator</h1>
                <p class="sb_cfg_sub">${(err && err.message) || String(err)}</p>
              </div>
            </div>`;
        throw err;
    }
}

if (document.readyState === "loading") {
    // DOM still parsing — listen for DOMContentLoaded.
    document.addEventListener("DOMContentLoaded", bootstrapConfiguratorV2);
} else {
    // DOM already parsed (the lazy bundle landed after DOMContentLoaded).
    // Run init immediately — but defer one microtask so any other
    // module-load-time side effects on this page complete first.
    Promise.resolve().then(bootstrapConfiguratorV2);
}
