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
// What did NOT change:
//   - The conditional disable rules are still hardcoded (Box Material =
//     White Melamine forbids wood stains; Series != Signature forbids
//     Custom door/finish). Phase 2c replaces these with disabled_value_ids
//     pulled from the rule engine via /select.
//   - Price recalc is still client-side (sum base_price + price_extra of
//     picked values). Phase 2c adds server reconcile via /select.
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


// ---------- Phase-2b hardcoded constants (Phase 2c replaces) ----------

// Mapping of finish / box-material display names to a representative
// colour swatch for the CSS cabinet preview. Phase 2c will source these
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

// CSV template + sample for the bulk-tools workflow. Headers must match
// the Phase-4 server-side parser's column order.
const TEMPLATE_HEADERS = [
    "SKU", "Product_Name", "Price", "Weight_kg", "Image", "Family",
    "Width", "Series", "Box_Material", "Door_Style", "Finish",
    "Hinge_Side", "Finished_Sides", "Gables", "Handle", "Accessories",
    "Door_Count",
];
const SAMPLE_CSV = [
    TEMPLATE_HEADERS.join(","),
    "SB-001,Base 18 Sig,325.00,24.6,a.jpg,Base,18 in,Signature,Maple,Five-Piece Woodgrain,Walnut Stain,Right,Both,Standard,Bar Pull,Soft-Close,1",
    "SB-002,Base 12 Con,219.00,16.0,b.jpg,Base,12 in,Contractor Series,White Melamine,Thermofoil Slab — White,White,Left,None,Standard,Knob,None,1",
    "SB-003,Base 24 Ele,360.00,30.0,c.jpg,Base,24 in,Elegance,Maple,Five-Piece Woodgrain,Cherry Stain,Right,Both,Finished,Cup Pull,Pull-Outs,2",
    "SB-004,Base 15 Mel,248.00,18.0,d.jpg,Base,15 in,Contemporary,White Melamine,Thermofoil Slab — White,Walnut Stain,Left,Left,Standard,Bar Pull,Soft-Close,1",
    "SB-005,Base 21 Sig,410.00,33.0,e.jpg,Base,21 in,Signature,Maple,Custom (Signature),Custom,Right,Both,Decorative,Integrated,Drawer Organisers,2",
].join("\n");


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
                  t-on-click="onAddToQuote">
            Add to Quote ➞
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
            // UI flags
            closedGroups: {},               // {<title>: true}  — collapsed groups
            userPhoto: null,                // dataURL or null
            previewBadge: "LIVE PREVIEW",
            // Bulk tools (Phase 4 wiring deferred)
            importRows: [],
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
        const amt = Math.round(this.totalPrice).toLocaleString();
        return cur.position === "after"
            ? `${amt}${cur.symbol}`
            : `${cur.symbol}${amt}`;
    }

    get weightText() {
        // Phase 2b shows "—" — Phase 2c will surface the server-resolved
        // weight from the /select response. Showing a placeholder is
        // more honest than the Phase-1 client-side estimate that didn't
        // reflect the real product weight.
        return "—";
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
    // Phase-2b hardcoded disable rules.
    //
    // Phase 2c replaces this whole method with a lookup against a
    // server-provided `disabled_value_ids` set returned by /select.
    // The rules below mirror the southbrook-configurator-v2.html
    // prototype exactly so the visual contract holds.
    // ------------------------------------------------------------------
    isValueDisabled(attr, val) {
        if (!attr) return false;
        // Resolve the canonical picks BY NAME — works regardless of
        // attribute ids, which differ per environment.
        const pickedNameOf = (attrName) => {
            const attrId = Object.keys(this.state.attributes)
                .find((id) => this.state.attributes[id].name === attrName);
            if (!attrId) return null;
            const valId = this.state.picked[attrId];
            if (valId === null) return null;
            const a = this.state.attributes[attrId];
            const v = a.values.find((vv) => vv.id === valId);
            return v ? v.name : null;
        };
        const boxName = pickedNameOf("Box Material");
        const seriesName = pickedNameOf("Series");

        if (attr.name === "Finish" && boxName === "White Melamine"
            && ["Maple Stain", "Cherry Stain", "Walnut Stain"].includes(val.name)) {
            return true;
        }
        if (attr.name === "Door Style" && seriesName !== "Signature"
            && val.name === "Custom (Signature)") {
            return true;
        }
        if (attr.name === "Finish" && seriesName !== "Signature"
            && val.name === "Custom") {
            return true;
        }
        return false;
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

    _pick(attrId, valId) {
        this.state.picked[attrId] = valId;
        // After picking, re-evaluate the disable rules and clear any
        // currently-picked value that the new state makes invalid.
        for (const [aid, attr] of Object.entries(this.state.attributes)) {
            const pickedValId = this.state.picked[aid];
            if (pickedValId === null) continue;
            const pickedVal = attr.values.find((v) => v.id === pickedValId);
            if (pickedVal && this.isValueDisabled(attr, pickedVal)) {
                this.state.picked[aid] = null;
            }
        }
    }

    onAddToQuote() {
        const missing = Object.entries(this.state.picked)
            .filter(([_, valId]) => valId === null)
            .map(([aid, _]) => this.state.attributes[aid].name);
        if (missing.length) {
            this._toast(`Please choose: ${missing.join(", ")}`);
            return;
        }
        this._toast(
            `Added to quote · ${this.autoSku} · ${this.formattedPrice}`
        );
        // Phase 2c: POST /southbrook/api/configurator/commit
        // {session_id, order_id} → materialise variant + add to a draft
        // sale.order for the logged-in portal user (target A per the
        // Phase-2 cart-target decision).
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

    onDownloadTemplate() {
        const example = [
            "SB-BASE-1DR-001", "Base 1-Door 18in", "295.00", "24.6",
            "base-1dr.jpg", "Base", "18 in", "Signature", "Maple",
            "Five-Piece Woodgrain", "Walnut Stain", "RH (Right Hand)", "Both",
            "Standard", "Bar Pull", "Soft-Close", "1",
        ];
        const csv = `${TEMPLATE_HEADERS.join(",")}\n${example.join(",")}\n`;
        const a = document.createElement("a");
        a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
        a.download = "Southbrook_Product_Template_v1.csv";
        a.click();
        this._toast(`Template downloaded · ${TEMPLATE_HEADERS.length} columns + example row`);
    }

    onOpenImport() {
        const rows = this._parseCSV(SAMPLE_CSV);
        this._renderImport(rows);
        const overlay = document.getElementById("sb_cfg_importOverlay");
        if (overlay) {
            overlay.classList.add("sb_cfg_overlay_show");
            overlay.setAttribute("aria-hidden", "false");
        }
    }

    _wireImportOverlay() {
        // The overlay markup lives outside the OWL tree (body-level
        // position:fixed). Wire its click handlers via the imperative
        // DOM API — there's only one of each so this is safe.
        const overlay = document.getElementById("sb_cfg_importOverlay");
        if (!overlay) return;
        overlay.querySelectorAll('[data-action="close-import"]')
            .forEach((b) => b.addEventListener("click", () => this._closeImport()));
        const dl = overlay.querySelector('[data-action="download-errors"]');
        if (dl) dl.addEventListener("click", () => this._downloadImportErrors());
        const commit = overlay.querySelector('[data-action="commit-import"]');
        if (commit) commit.addEventListener("click", () => this._commitImport());

        const drop = document.getElementById("sb_cfg_drop");
        const fileInput = document.getElementById("sb_cfg_fileInput");
        if (drop && fileInput) {
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
                    fileInput.onchange({ target: { files: [f] } });
                }
            });
            fileInput.onchange = (e) => {
                const f = e.target.files[0];
                if (!f) return;
                const reader = new FileReader();
                reader.onload = (ev) => {
                    this._renderImport(this._parseCSV(ev.target.result));
                    this._toast(`Parsed ${f.name}`);
                };
                reader.readAsText(f);
            };
        }
    }

    _closeImport() {
        const overlay = document.getElementById("sb_cfg_importOverlay");
        if (overlay) {
            overlay.classList.remove("sb_cfg_overlay_show");
            overlay.setAttribute("aria-hidden", "true");
        }
    }

    _parseCSV(text) {
        const lines = text.trim().split(/\r?\n/);
        const head = lines[0].split(",").map((s) => s.trim());
        return lines.slice(1).map((ln) => {
            const cells = ln.split(",");
            const o = {};
            head.forEach((hh, i) => {
                o[hh] = (cells[i] || "").trim();
            });
            return o;
        });
    }

    _validateImportRow(r) {
        const errs = [];
        if (!r.SKU) errs.push("SKU required");
        if (r.Price && Number.isNaN(parseFloat(r.Price))) {
            errs.push("Price not numeric");
        }
        if (r.Box_Material === "White Melamine"
            && ["Maple Stain", "Cherry Stain", "Walnut Stain"].includes(r.Finish)) {
            errs.push(`Finish '${r.Finish}' invalid for White Melamine`);
        }
        if (r.Series !== "Signature" && r.Door_Style === "Custom (Signature)") {
            errs.push("Custom door needs Signature series");
        }
        return errs;
    }

    _renderImport(rows) {
        this.state.importRows = rows;
        const body = document.getElementById("sb_cfg_previewBody");
        if (!body) return;
        let ok = 0, bad = 0;
        const html = rows.map((r) => {
            const e = this._validateImportRow(r);
            const good = e.length === 0;
            if (good) ok++; else bad++;
            return `
                <tr class="${good ? "" : "sb_cfg_row_bad"}">
                  <td><span class="sb_cfg_rowstat sb_cfg_rowstat_${good ? "g" : "r"}">${good ? "✓ OK" : "✕ ERR"}</span></td>
                  <td>${r.SKU || ""}</td>
                  <td>${r.Width || ""}</td>
                  <td>${r.Series || ""}</td>
                  <td>${r.Box_Material || ""}</td>
                  <td>${r.Finish || ""}</td>
                  <td>$${r.Price || ""}</td>
                  <td class="sb_cfg_reason">${e.join("; ")}</td>
                </tr>
            `;
        }).join("");
        body.innerHTML = html;
        document.getElementById("sb_cfg_okCount").textContent = `${ok} valid`;
        document.getElementById("sb_cfg_badCount").textContent = `${bad} errors`;
        document.getElementById("sb_cfg_commitBtn").textContent =
            `Commit ${ok} valid row${ok === 1 ? "" : "s"}`;
    }

    _commitImport() {
        const ok = this.state.importRows
            .filter((r) => this._validateImportRow(r).length === 0).length;
        const bad = this.state.importRows.length - ok;
        this._closeImport();
        this._toast(`${ok} product(s) imported · ${bad} skipped (errors logged)`);
        // Phase 4: replace this with a JSON-RPC POST to
        // /southbrook/api/import/commit that requires explicit
        // confirm:true and wraps writes in a single transaction.
    }

    _downloadImportErrors() {
        const rows = this.state.importRows
            .filter((r) => this._validateImportRow(r).length);
        const csv = `SKU,Issues\n${rows.map(
            (r) => `${r.SKU || ""},"${this._validateImportRow(r).join("; ")}"`
        ).join("\n")}`;
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

document.addEventListener("DOMContentLoaded", async () => {
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
});
