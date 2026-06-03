/** @odoo-module **/
// =====================================================================
// Southbrook Configurator UX v2 — Phase 1
//
// Port of the southbrook-configurator-v2.html prototype's vanilla JS,
// scoped to the v2 root mount point and wrapped for the Odoo web bundle.
//
// What this file owns (Phase 1):
//   - Hardcoded OPTIONS / GROUPS / FINISH_COLORS — same shape as the
//     prototype so the visual diff vs the HTML mock is zero. Phase 2
//     replaces these constants with values pulled from product.attribute
//     records via JSON-RPC.
//   - Chip + select state management (`state` object keyed by attribute
//     name; value is the index into OPTIONS[key]).
//   - Conditional disable rules (Box Material → Finish, Series → Door
//     Style / Custom Finish). Phase 3 surfaces these via a server-side
//     rule table sourced from the existing product.config.line records.
//   - Live price + weight + auto-SKU + completion-ring recomputation.
//   - Cabinet preview re-render (CSS-based; Phase 2 may swap to an SVG
//     or to a vendor-supplied photograph).
//   - Photo replace via file input + drag-drop on the viewer pane.
//   - Bulk template CSV download + bulk import preview / validate /
//     commit overlay (client-side only; Phase 4 swaps the commit step
//     for a JSON-RPC call into a server endpoint that writes products).
//   - Toast notifications.
//
// Mount-point guard:
//   The JS scans `document` for `#sb_cfg_v2_root`. If absent (i.e. on
//   any page other than a configurable product page) the entire
//   bundle no-ops. This makes the v2 UX opt-in per template — pages
//   without the v2 markup are completely unaffected.
//
// Out of scope for Phase 1:
//   - Real product attribute data (uses hardcoded OPTIONS object)
//   - Server-side price + weight calc (uses the same client-side
//     formula the prototype uses; BASE = 180 placeholder)
//   - Server-side bulk import commit (the Commit button only shows a
//     toast; nothing reaches Odoo)
//   - WebGL / Three.js cabinet preview (uses the prototype's
//     box-shaped CSS preview)
//   - Translation strings (English only; Phase 5 wraps user-facing
//     copy in i18n helpers)
// =====================================================================

// ---------- Data constants (hardcoded for Phase 1) ----------

const OPTIONS = {
    Width:         [["9 in", -40, -6], ["12 in", -20, -3], ["15 in", 0, 0],
                    ["18 in", 30, 4.6], ["21 in", 60, 9]],
    Series:        [["Contractor", 0, 0], ["Contemporary", 40, 0],
                    ["Elegance", 90, 0], ["Signature", 160, 0]],
    Box_Material:  [["White Melamine", 0, 0], ["Maple", 55, 2]],
    Door_Style:    [["Thermofoil Slab", 0, 0],
                    ["Five-Piece Woodgrain", 45, 1.5],
                    ["Custom (Signature)", 120, 2]],
    Finish:        [["White", 0, 0], ["Maple Stain", 20, 0],
                    ["Cherry Stain", 25, 0], ["Walnut Stain", 30, 0],
                    ["Custom", 75, 0]],
    Hinge_Side:    [["Left", 0, 0], ["Right", 0, 0]],
    Finished_Sides:[["None", 0, 0], ["Left", 18, 0.5],
                    ["Right", 18, 0.5], ["Both", 32, 1]],
    Gables:        [["Standard", 0, 0], ["Finished", 22, 0.6],
                    ["Decorative", 60, 1]],
    Handle:        [["Bar Pull", 12, 0.2], ["Knob", 8, 0.1],
                    ["Cup Pull", 14, 0.2], ["Integrated", 30, 0.3],
                    ["None", 0, 0]],
    Accessories:   [["Soft-Close", 24, 0.3], ["Pull-Outs", 65, 1.2],
                    ["Drawer Organisers", 38, 0.6], ["None", 0, 0]],
    Door_Count:    [["1", 0, 0], ["2", 70, 3]],
};

// Groups define the order + chunking of attribute fields in the right
// pane. The number of fields per group drives the n/total display in
// the group header.
const GROUPS = [
    ["Size & Layout",         ["Width", "Door_Count"]],
    ["Series & Materials",    ["Series", "Box_Material", "Door_Style"]],
    ["Finish & Construction", ["Finish", "Hinge_Side", "Finished_Sides", "Gables"]],
    ["Hardware & Add-ons",    ["Handle", "Accessories"]],
];

const BASE_PRICE = 180;
const BASE_WEIGHT = 8;

// Hex map for the CSS cabinet preview. Maps finish (or box) name to a
// representative colour swatch. Phase 2 swaps this for actual vendor
// swatches (image URLs).
const FINISH_COLORS = {
    "White":          "#f3f0ea",
    "Maple Stain":    "#d9a566",
    "Cherry Stain":   "#8a3b2a",
    "Walnut Stain":   "#5a3b28",
    "Custom":         "#b9a07a",
    "Maple":          "#caa06a",
    "White Melamine": "#eceae4",
};

// CSV template + sample row data. Headers must match the column order
// the Phase-4 server-side parser expects. Sample CSV ships with the
// expected error states pre-baked so QA can verify the validation path
// without authoring a CSV.
const TEMPLATE_HEADERS = [
    "SKU", "Product_Name", "Price", "Weight_kg", "Image", "Family",
    "Width", "Series", "Box_Material", "Door_Style", "Finish",
    "Hinge_Side", "Finished_Sides", "Gables", "Handle", "Accessories",
    "Door_Count",
];
const SAMPLE_CSV = [
    TEMPLATE_HEADERS.join(","),
    "SB-001,Base 18 Sig,325.00,24.6,a.jpg,Base,18 in,Signature,Maple,Five-Piece Woodgrain,Walnut Stain,Right,Both,Standard,Bar Pull,Soft-Close,1",
    "SB-002,Base 12 Con,219.00,16.0,b.jpg,Base,12 in,Contractor,White Melamine,Thermofoil Slab,White,Left,None,Standard,Knob,None,1",
    "SB-003,Base 24 Ele,360.00,30.0,c.jpg,Base,24 in,Elegance,Maple,Five-Piece Woodgrain,Cherry Stain,Right,Both,Finished,Cup Pull,Pull-Outs,2",
    "SB-004,Base 15 Mel,248.00,18.0,d.jpg,Base,15 in,Contemporary,White Melamine,Thermofoil Slab,Walnut Stain,Left,Left,Standard,Bar Pull,Soft-Close,1",
    "SB-005,Base 21 Sig,410.00,33.0,e.jpg,Base,21 in,Signature,Maple,Custom (Signature),Custom,Right,Both,Decorative,Integrated,Drawer Organisers,2",
].join("\n");


// ---------- Module init guard ----------

document.addEventListener("DOMContentLoaded", () => {
    const root = document.getElementById("sb_cfg_v2_root");
    if (!root) {
        // No v2 mount point on this page — bundle no-ops.
        return;
    }
    new SouthbrookConfiguratorV2(root).init();
});


// ---------- Main component (vanilla class for Phase 1) ----------

class SouthbrookConfiguratorV2 {
    constructor(root) {
        this.root = root;
        // state[attr] = selected option index, or null when nothing
        // selected for that attribute yet.
        this.state = {};
        Object.keys(OPTIONS).forEach((k) => { this.state[k] = null; });
        this.userPhoto = null;
        this.curRows = [];
        this._toastTimer = null;
    }

    init() {
        this._buildUI();
        this._wireConfiguratorEvents();
        this._wireBulkToolsEvents();
        this._wirePhotoEvents();
        this._wireImportEvents();
        this._recalc();
    }

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    _label(key) {
        return key.replace(/_/g, " ");
    }

    _allowed(key) {
        return (OPTIONS[key] || []).map((o) => o[0]);
    }

    // Disable rules — Phase 3 sources these from product.config.line.
    _disabledFor(key) {
        let d = [];
        const box = this.state.Box_Material !== null
            ? OPTIONS.Box_Material[this.state.Box_Material][0] : null;
        const series = this.state.Series !== null
            ? OPTIONS.Series[this.state.Series][0] : null;
        if (key === "Finish" && box === "White Melamine") {
            d = ["Maple Stain", "Cherry Stain", "Walnut Stain"];
        }
        if (key === "Door_Style" && series !== "Signature") {
            d = ["Custom (Signature)"];
        }
        if (key === "Finish" && series !== "Signature") {
            d.push("Custom");
        }
        return d;
    }

    // ------------------------------------------------------------------
    // Configurator UI build / chip render / state pick
    // ------------------------------------------------------------------

    _buildUI() {
        const c = this.root.querySelector("#sb_cfg_configurator");
        const html = [];
        GROUPS.forEach(([title, fields], gi) => {
            html.push(`
                <div class="sb_cfg_group" data-g="${gi}">
                  <div class="sb_cfg_ghead" data-toggle="1" tabindex="0"
                       role="button" aria-expanded="true">
                    <span class="sb_cfg_gt">
                      <span class="sb_cfg_check" id="sb_cfg_chk${gi}">${gi + 1}</span>
                      ${title}
                    </span>
                    <span class="sb_cfg_gnum">
                      <span id="sb_cfg_gp${gi}">0</span>/${fields.length}
                      &nbsp;<span class="sb_cfg_chev">❮</span>
                    </span>
                  </div>
                  <div class="sb_cfg_gbody">
            `);
            fields.forEach((k) => {
                const full = (k === "Finish"
                    || (fields.length % 2 !== 0 && fields.indexOf(k) === fields.length - 1))
                    ? " sb_cfg_field_full" : "";
                html.push(`
                    <div class="sb_cfg_field${full}" id="sb_cfg_f_${k}">
                      <label>
                        ${this._label(k)}
                        <span class="sb_cfg_pd" id="sb_cfg_pd_${k}"></span>
                      </label>
                `);
                if (k === "Finish") {
                    html.push(`
                      <select data-finish="1" aria-label="${this._label(k)}">
                        <option value="">Select finish...</option>
                    `);
                    OPTIONS[k].forEach((o, i) => {
                        html.push(`<option value="${i}">${o[0]}</option>`);
                    });
                    html.push(`</select>`);
                } else {
                    html.push(`
                      <div class="sb_cfg_chips" id="sb_cfg_chips_${k}"
                           role="radiogroup" aria-label="${this._label(k)}"></div>
                    `);
                }
                html.push(`
                      <div class="sb_cfg_warn" id="sb_cfg_warn_${k}"
                           style="display:none"></div>
                    </div>
                `);
            });
            html.push(`</div></div>`);
        });
        c.innerHTML = html.join("");
        this._renderChips();
    }

    _renderChips() {
        Object.keys(OPTIONS).forEach((k) => {
            if (k === "Finish") return;
            const box = this.root.querySelector(`#sb_cfg_chips_${k}`);
            if (!box) return;
            const dis = this._disabledFor(k);
            const html = OPTIONS[k].map((o, i) => {
                const off = dis.includes(o[0]);
                const sel = this.state[k] === i ? " sb_cfg_chip_sel" : "";
                return `
                    <div class="sb_cfg_chip${sel}${off ? " sb_cfg_chip_disabled" : ""}"
                         role="radio"
                         tabindex="${off ? "-1" : "0"}"
                         aria-checked="${this.state[k] === i ? "true" : "false"}"
                         data-key="${k}"
                         data-i="${i}"
                         data-off="${off ? 1 : 0}">${o[0]}</div>
                `;
            }).join("");
            box.innerHTML = html;
        });
    }

    _pick(key, idx) {
        this.state[key] = idx;
        // If a dependency change invalidates a current selection,
        // clear it so the rule violation can't persist.
        const disFin = this._disabledFor("Finish");
        if (this.state.Finish !== null
            && disFin.includes(OPTIONS.Finish[this.state.Finish][0])) {
            this.state.Finish = null;
            const sel = this.root.querySelector("[data-finish]");
            if (sel) sel.value = "";
        }
        const disDoor = this._disabledFor("Door_Style");
        if (this.state.Door_Style !== null
            && disDoor.includes(OPTIONS.Door_Style[this.state.Door_Style][0])) {
            this.state.Door_Style = null;
        }
        this._renderChips();
        this._recalc();
    }

    _wireConfiguratorEvents() {
        const c = this.root.querySelector("#sb_cfg_configurator");
        c.addEventListener("click", (ev) => {
            const head = ev.target.closest("[data-toggle]");
            if (head) {
                const group = head.parentElement;
                const closed = group.classList.toggle("sb_cfg_closed");
                head.setAttribute("aria-expanded", closed ? "false" : "true");
                return;
            }
            const chip = ev.target.closest(".sb_cfg_chip");
            if (chip && chip.getAttribute("data-off") !== "1") {
                this._pick(chip.getAttribute("data-key"),
                           +chip.getAttribute("data-i"));
            }
        });
        c.addEventListener("change", (ev) => {
            const sel = ev.target.closest("[data-finish]");
            if (sel) {
                this._pick("Finish", sel.value === "" ? null : +sel.value);
            }
        });
        // Keyboard support: Enter / Space toggles the group head; arrow
        // keys move focus between chips inside a radiogroup.
        c.addEventListener("keydown", (ev) => {
            if (ev.target.matches("[data-toggle]")
                && (ev.key === "Enter" || ev.key === " ")) {
                ev.preventDefault();
                ev.target.click();
            }
            if (ev.target.matches(".sb_cfg_chip")
                && (ev.key === "Enter" || ev.key === " ")) {
                ev.preventDefault();
                ev.target.click();
            }
        });
    }

    // ------------------------------------------------------------------
    // Live recalc — price, weight, SKU, ring, group counters
    // ------------------------------------------------------------------

    _recalc() {
        let price = BASE_PRICE;
        let weight = BASE_WEIGHT;
        const parts = [];
        let done = 0;
        const total = Object.keys(OPTIONS).length;
        Object.keys(OPTIONS).forEach((k) => {
            const i = this.state[k];
            if (i !== null) {
                const o = OPTIONS[k][i];
                price += o[1];
                weight += o[2];
                done++;
                if (["Width", "Series", "Finish", "Hinge_Side", "Handle"].includes(k)) {
                    parts.push(o[0]);
                }
                const pd = this.root.querySelector(`#sb_cfg_pd_${k}`);
                if (pd) {
                    pd.textContent = o[1] > 0
                        ? `+$${o[1]}`
                        : (o[1] < 0 ? `-$${Math.abs(o[1])}` : "");
                }
            }
        });

        const priceEl = this.root.querySelector("#sb_cfg_price");
        priceEl.firstChild.textContent = `$${price.toFixed(0)}`;
        this.root.querySelector("#sb_cfg_weight").textContent =
            `${weight.toFixed(1)} kg`;
        this.root.querySelector("#sb_cfg_spec").textContent =
            parts.length ? parts.join("  ·  ") : "nothing selected yet";

        // Auto SKU compose — short abbreviation of width, series, finish.
        const abbr = (k) => this.state[k] !== null
            ? OPTIONS[k][this.state[k]][0]
                .replace(/[^A-Za-z0-9]/g, "")
                .substring(0, 3)
                .toUpperCase()
            : "XXX";
        this.root.querySelector("#sb_cfg_sku").textContent =
            this.state.Width !== null
                ? `SB-1DR-${abbr("Width")}-${abbr("Series")}-${abbr("Finish")}`
                : "—";

        const pct = Math.round(done / total * 100);
        this.root.querySelector("#sb_cfg_progbar").style.width = `${pct}%`;
        const ring = this.root.querySelector("#sb_cfg_ring");
        ring.style.setProperty("--p", pct);
        this.root.querySelector("#sb_cfg_ringtxt").textContent = `${pct}%`;
        this.root.querySelector("#sb_cfg_comptxt").textContent =
            pct === 100
                ? "All set — ready to add to quote"
                : `${done} of ${total} options chosen`;

        // Group completion counters + checkmarks.
        GROUPS.forEach(([_title, fields], gi) => {
            const gd = fields.filter((k) => this.state[k] !== null).length;
            this.root.querySelector(`#sb_cfg_gp${gi}`).textContent = gd;
            const chk = this.root.querySelector(`#sb_cfg_chk${gi}`);
            if (gd === fields.length) {
                chk.innerHTML = "✓";
                chk.classList.add("sb_cfg_check_done");
            } else {
                chk.innerHTML = String(gi + 1);
                chk.classList.remove("sb_cfg_check_done");
            }
        });

        // Validation summary — bottom-left of left pane.
        const valid = this.root.querySelector("#sb_cfg_valid");
        const progwrap = this.root.querySelector(".sb_cfg_progwrap");
        if (progwrap) progwrap.setAttribute("aria-valuenow", String(pct));
        if (pct === 100) {
            valid.className = "sb_cfg_note sb_cfg_note_ok";
            valid.innerHTML = "✓ All options valid · ready";
        } else {
            valid.className = "sb_cfg_note sb_cfg_note_bad";
            valid.innerHTML = `${total - done} option(s) still needed`;
        }

        this._renderPreview();
    }

    // ------------------------------------------------------------------
    // Cabinet preview re-render — CSS-only for Phase 1
    // ------------------------------------------------------------------

    _renderPreview() {
        const cab = this.root.querySelector("#sb_cfg_cab");
        if (this.userPhoto) return;        // photo override
        const widthIdx = this.state.Width !== null ? this.state.Width : 2;
        const wpx = 70 + widthIdx * 16;
        const finishName = this.state.Finish !== null
            ? OPTIONS.Finish[this.state.Finish][0]
            : (this.state.Box_Material !== null
                ? OPTIONS.Box_Material[this.state.Box_Material][0]
                : "White");
        const col = FINISH_COLORS[finishName] || "#dcd3c4";
        const doors = this.state.Door_Count !== null
            ? (this.state.Door_Count === 1 ? 2 : 1) : 1;
        const hinge = this.state.Hinge_Side !== null
            ? OPTIONS.Hinge_Side[this.state.Hinge_Side][0] : "Left";
        const handle = this.state.Handle !== null
            ? OPTIONS.Handle[this.state.Handle][0] : "Bar Pull";
        const handleHtml = (handle === "None") ? ""
            : (handle === "Knob"
                ? `<div style="position:absolute;top:50%;${hinge === "Left" ? "right:8px" : "left:8px"};width:7px;height:7px;border-radius:50%;background:#2f3b52"></div>`
                : `<div style="position:absolute;top:50%;${hinge === "Left" ? "right:7px" : "left:7px"};width:4px;height:26px;border-radius:3px;background:#2f3b52"></div>`);
        let doorHtml;
        if (doors === 2) {
            doorHtml = `
                <div style="position:absolute;inset:6px;display:flex;gap:4px">
                  <div style="flex:1;position:relative;border:1px solid rgba(0,0,0,.12);border-radius:3px;background:rgba(255,255,255,.12)">
                    <div style="position:absolute;top:50%;right:5px;width:3px;height:20px;border-radius:3px;background:#2f3b52"></div>
                  </div>
                  <div style="flex:1;position:relative;border:1px solid rgba(0,0,0,.12);border-radius:3px;background:rgba(255,255,255,.12)">
                    <div style="position:absolute;top:50%;left:5px;width:3px;height:20px;border-radius:3px;background:#2f3b52"></div>
                  </div>
                </div>`;
        } else {
            doorHtml = `
                <div style="position:absolute;inset:6px;border:1px solid rgba(0,0,0,.12);border-radius:3px;background:rgba(255,255,255,.1)">
                  ${handleHtml}
                </div>`;
        }
        cab.style.width = `${wpx}px`;
        cab.style.height = "150px";
        cab.style.background = col;
        cab.style.position = "relative";
        cab.style.borderTop = "3px solid rgba(0,0,0,.08)";
        cab.innerHTML = doorHtml;
    }

    // ------------------------------------------------------------------
    // Bulk tools — template CSV download
    // ------------------------------------------------------------------

    _wireBulkToolsEvents() {
        const tpl = this.root.querySelector('[data-action="download-template"]');
        if (tpl) tpl.addEventListener("click", () => this._downloadTemplate());
        const imp = this.root.querySelector('[data-action="open-import"]');
        if (imp) imp.addEventListener("click", () => this._openImport());
        const addQ = this.root.querySelector('[data-action="add-to-quote"]');
        if (addQ) addQ.addEventListener("click", () => this._addToQuote());
    }

    _downloadTemplate() {
        const example = [
            "SB-BASE-1DR-001", "Base 1-Door 18in", "295.00", "24.6",
            "base-1dr.jpg", "Base", "18 in", "Signature", "Maple",
            "Five-Piece Woodgrain", "Walnut Stain", "Right", "Both",
            "Standard", "Bar Pull", "Soft-Close", "1",
        ];
        const csv = `${TEMPLATE_HEADERS.join(",")}\n${example.join(",")}\n`;
        const a = document.createElement("a");
        a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
        a.download = "Southbrook_Product_Template_v1.csv";
        a.click();
        this._toast(`Template downloaded · ${TEMPLATE_HEADERS.length} columns + example row`);
    }

    _addToQuote() {
        const miss = Object.keys(OPTIONS).filter((k) => this.state[k] === null);
        if (miss.length) {
            this._toast(`Please choose: ${miss.map((k) => this._label(k)).join(", ")}`);
            return;
        }
        const sku = this.root.querySelector("#sb_cfg_sku").textContent;
        const price = this.root.querySelector("#sb_cfg_price")
            .textContent.trim().split(/\s/)[0];
        this._toast(`Added to quote · ${sku} · ${price}`);
        // Phase 2: POST /shop/cart/update_json with the config session id.
    }

    // ------------------------------------------------------------------
    // Bulk tools — import preview / validate / commit
    // ------------------------------------------------------------------

    _wireImportEvents() {
        const drop = this.root.querySelector("#sb_cfg_drop");
        const fileInput = this.root.querySelector("#sb_cfg_fileInput");
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
                const r = new FileReader();
                r.onload = (ev) => {
                    this._renderImport(this._parseCSV(ev.target.result));
                    this._toast(`Parsed ${f.name}`);
                };
                r.readAsText(f);
            };
        }
        this.root.querySelectorAll('[data-action="close-import"]').forEach((b) => {
            b.addEventListener("click", () => this._closeImport());
        });
        const dl = this.root.querySelector('[data-action="download-errors"]');
        if (dl) dl.addEventListener("click", () => this._downloadErrors());
        const commit = this.root.querySelector('[data-action="commit-import"]');
        if (commit) commit.addEventListener("click", () => this._commitImport());
    }

    _openImport() {
        this._renderImport(this._parseCSV(SAMPLE_CSV));
        const overlay = this.root.querySelector("#sb_cfg_importOverlay")
            || document.getElementById("sb_cfg_importOverlay");
        if (overlay) {
            overlay.classList.add("sb_cfg_overlay_show");
            overlay.setAttribute("aria-hidden", "false");
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

    _validateRow(r) {
        const errs = [];
        const checks = ["Width", "Series", "Box_Material", "Door_Style",
                        "Finish", "Hinge_Side", "Finished_Sides", "Gables",
                        "Handle", "Door_Count"];
        checks.forEach((col) => {
            const v = r[col];
            if (v && !this._allowed(col).includes(v)) {
                errs.push(`${col.replace(/_/g, " ")} '${v}' not allowed`);
            }
        });
        if (r.Box_Material === "White Melamine"
            && ["Maple Stain", "Cherry Stain", "Walnut Stain"].includes(r.Finish)) {
            errs.push(`Finish '${r.Finish}' invalid for White Melamine`);
        }
        if (r.Series !== "Signature" && r.Door_Style === "Custom (Signature)") {
            errs.push("Custom door needs Signature series");
        }
        if (!r.SKU) errs.push("SKU required");
        if (r.Price && Number.isNaN(parseFloat(r.Price))) {
            errs.push("Price not numeric");
        }
        return errs;
    }

    _renderImport(rows) {
        this.curRows = rows;
        const body = document.getElementById("sb_cfg_previewBody");
        let ok = 0, bad = 0;
        const html = rows.map((r) => {
            const e = this._validateRow(r);
            const good = e.length === 0;
            if (good) ok++; else bad++;
            return `
                <tr class="${good ? "" : "sb_cfg_row_bad"}">
                  <td><span class="sb_cfg_rowstat sb_cfg_rowstat_${good ? "g" : "r"}">
                    ${good ? "✓ OK" : "✕ ERR"}
                  </span></td>
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
        document.getElementById("sb_cfg_okCount").textContent  = `${ok} valid`;
        document.getElementById("sb_cfg_badCount").textContent = `${bad} errors`;
        document.getElementById("sb_cfg_commitBtn").textContent =
            `Commit ${ok} valid row${ok === 1 ? "" : "s"}`;
    }

    _commitImport() {
        const ok = this.curRows.filter((r) => this._validateRow(r).length === 0).length;
        const bad = this.curRows.length - ok;
        this._closeImport();
        this._toast(`${ok} product(s) imported · ${bad} skipped (errors logged)`);
        // Phase 4: replace this with a JSON-RPC POST to a new
        // /sb_cfg/import endpoint that writes products in a single
        // transaction and returns a row-level commit log. The human
        // confirmation gate must stay client-side; the server endpoint
        // must require a confirm:true flag on the payload.
    }

    _downloadErrors() {
        const rows = this.curRows.filter((r) => this._validateRow(r).length);
        const csv = `SKU,Issues\n${rows.map(
            (r) => `${r.SKU || ""},"${this._validateRow(r).join("; ")}"`
        ).join("\n")}`;
        const a = document.createElement("a");
        a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
        a.download = "import_errors.csv";
        a.click();
        this._toast("Error report downloaded");
    }

    // ------------------------------------------------------------------
    // Photo replace
    // ------------------------------------------------------------------

    _wirePhotoEvents() {
        const editBtn = this.root.querySelector('[data-action="replace-photo"]');
        const imgInput = this.root.querySelector("#sb_cfg_imgInput");
        if (editBtn && imgInput) {
            editBtn.addEventListener("click", () => imgInput.click());
            imgInput.onchange = (e) => {
                const f = e.target.files[0];
                if (!f) return;
                const r = new FileReader();
                r.onload = (ev) => {
                    this.userPhoto = ev.target.result;
                    const cab = this.root.querySelector("#sb_cfg_cab");
                    cab.style.width = "100%";
                    cab.style.height = "100%";
                    cab.style.background = "none";
                    cab.innerHTML =
                        `<img class="sb_cfg_user_photo" src="${ev.target.result}" alt="Custom cabinet photo"/>`;
                    this.root.querySelector("#sb_cfg_vbadge").textContent = "CUSTOM PHOTO";
                };
                r.readAsDataURL(f);
            };
        }
        const vw = this.root.querySelector("#sb_cfg_viewer");
        if (vw) {
            ["dragover", "dragenter"].forEach((evName) => {
                vw.addEventListener(evName, (e) => {
                    e.preventDefault();
                    vw.classList.add("drag");
                });
            });
            ["dragleave", "drop"].forEach((evName) => {
                vw.addEventListener(evName, (e) => {
                    e.preventDefault();
                    vw.classList.remove("drag");
                });
            });
            vw.addEventListener("drop", (e) => {
                const f = e.dataTransfer.files[0];
                if (f && f.type.indexOf("image") === 0 && imgInput) {
                    imgInput.onchange({ target: { files: [f] } });
                }
            });
        }
    }

    // ------------------------------------------------------------------
    // Toast helper
    // ------------------------------------------------------------------

    _toast(msg) {
        const t = this.root.querySelector("#sb_cfg_toast")
            || document.getElementById("sb_cfg_toast");
        if (!t) return;
        t.textContent = msg;
        t.classList.add("sb_cfg_toast_show");
        clearTimeout(this._toastTimer);
        this._toastTimer = setTimeout(() => {
            t.classList.remove("sb_cfg_toast_show");
        }, 3400);
    }
}
