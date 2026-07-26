/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class MaterialsHardwareCatalog extends Component {
    static template = "sb_materials_hardware.Catalog";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            ok: true,
            reason: "",
            categories: [],
            facets: [],
            columns: [],
            rows: [],
            total: 0,
            provenance: "",
            categoryId: null,
            selectedFacets: {},
            search: "",
            selectedProductId: null,
            detail: this._emptyDetail(),
        });
        onWillStart(() => this.load());
    }

    _emptyDetail() {
        return {
            ok: false,
            reason: null,
            title: "—",
            subtitle: "",
            specs: [],
            engineering: [],
            badges: [],
        };
    }

    async load() {
        this.state.loading = true;
        const previousSelected = this.state.selectedProductId;
        const payload = await this.orm.call(
            "materials.catalog.provider", "get_catalog", [], {
                scope: "tools",
                category_id: this.state.categoryId,
                facets: this.state.selectedFacets,
                search: this.state.search,
            });
        Object.assign(this.state, payload, { loading: false });

        if (!this.state.ok) {
            this.state.selectedProductId = null;
            this.state.detail = this._emptyDetail();
            return;
        }

        const rows = this.state.rows || [];
        const stillPresent = previousSelected !== null &&
            rows.some((row) => row.product_id === previousSelected);
        if (stillPresent) {
            // Keep the current selection and its detail panel showing —
            // the panel stays put across facet/search changes that don't
            // drop the currently open row (finding U8).
            return;
        }
        if (rows.length) {
            await this.selectRow(rows[0].product_id);
        } else {
            this.state.selectedProductId = null;
            this.state.detail = this._emptyDetail();
        }
    }

    get topCategories() {
        return this.state.categories.filter((c) => !c.parent_id);
    }

    childrenOf(categoryId) {
        return this.state.categories.filter((c) => c.parent_id === categoryId);
    }

    // Catalog › Category › Subcategory — built from the category tree the
    // payload already carries, no extra server call (finding U12).
    get breadcrumb() {
        const categoryId = this.state.categoryId;
        if (!categoryId) {
            return null;
        }
        const current = this.state.categories.find((c) => c.id === categoryId);
        if (!current) {
            return null;
        }
        if (current.parent_id) {
            const parent = this.state.categories.find((c) => c.id === current.parent_id);
            return { top: parent ? parent.name : "—", sub: current.name };
        }
        return { top: current.name, sub: null };
    }

    // Echoes the active facet selections and search term in the results
    // bar, from state already on the client — no new data (finding U11).
    get filterEcho() {
        const bits = [];
        for (const facet of this.state.facets) {
            const chosen = this.state.selectedFacets[facet.key];
            if (!chosen) {
                continue;
            }
            if (facet.type === "range") {
                const min = chosen.min !== undefined ? chosen.min : "";
                const max = chosen.max !== undefined ? chosen.max : "";
                if (min !== "" || max !== "") {
                    bits.push(facet.label + " " + min + "–" + max);
                }
            } else if (chosen.length) {
                const labels = chosen.map((v) => {
                    const found = facet.values.find((val) => val.value === v);
                    return found ? found.label : v;
                });
                bits.push(facet.label + ": " + labels.join(", "));
            }
        }
        if (this.state.search) {
            bits.push('"' + this.state.search + '"');
        }
        return bits.length ? "· " + bits.join(" · ") : "";
    }

    isSelected(key, value) {
        const chosen = this.state.selectedFacets[key] || [];
        return chosen.includes(value);
    }

    isRowSelected(productId) {
        return this.state.selectedProductId === productId;
    }

    rangeValue(key, bound) {
        const chosen = this.state.selectedFacets[key];
        return chosen && chosen[bound] !== undefined ? chosen[bound] : "";
    }

    // Column class helper shared by header and body cells: alignment plus
    // a monospace treatment for reference-style code/numeric columns
    // (finding U6).
    cellClass(col) {
        const classes = [];
        if (col.align === "right") {
            classes.push("o_right");
        }
        if (col.key === "default_code") {
            classes.push("o_mono");
        }
        return classes.join(" ");
    }

    async selectCategory(categoryId) {
        this.state.categoryId = categoryId;
        this.state.selectedFacets = {};
        await this.load();
    }

    async toggleFacet(key, value) {
        const chosen = this.state.selectedFacets[key] || [];
        const next = chosen.includes(value)
            ? chosen.filter((v) => v !== value)
            : chosen.concat([value]);
        if (next.length) {
            this.state.selectedFacets[key] = next;
        } else {
            delete this.state.selectedFacets[key];
        }
        await this.load();
    }

    async setRangeBound(key, bound, ev) {
        const raw = ev.target.value;
        const current = Object.assign({}, this.state.selectedFacets[key]);
        if (raw === "") {
            delete current[bound];
        } else {
            current[bound] = Number(raw);
        }
        if (current.min === undefined && current.max === undefined) {
            delete this.state.selectedFacets[key];
        } else {
            this.state.selectedFacets[key] = current;
        }
        await this.load();
    }

    async clearFilters() {
        this.state.selectedFacets = {};
        this.state.search = "";
        await this.load();
    }

    async onSearchInput(ev) {
        this.state.search = ev.target.value;
        await this.load();
    }

    async selectRow(productId) {
        this.state.selectedProductId = productId;
        const detail = await this.orm.call(
            "materials.catalog.provider", "get_detail", [productId]);
        detail.title = detail.title || "—";
        this.state.detail = detail;
    }

    cell(row, key) {
        const value = row[key];
        return value === null || value === undefined
            ? "—"
            : value;
    }
}

registry.category("actions").add(
    "sb_materials_hardware.catalog", MaterialsHardwareCatalog);
