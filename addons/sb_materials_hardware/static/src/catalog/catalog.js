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
            detail: null,
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        const payload = await this.orm.call(
            "materials.catalog.provider", "get_catalog", [], {
                scope: "tools",
                category_id: this.state.categoryId,
                facets: this.state.selectedFacets,
                search: this.state.search,
            });
        Object.assign(this.state, payload, { loading: false });
        this.state.detail = null;
    }

    get topCategories() {
        return this.state.categories.filter((c) => !c.parent_id);
    }

    childrenOf(categoryId) {
        return this.state.categories.filter((c) => c.parent_id === categoryId);
    }

    isSelected(key, value) {
        const chosen = this.state.selectedFacets[key] || [];
        return chosen.includes(value);
    }

    rangeValue(key, bound) {
        const chosen = this.state.selectedFacets[key];
        return chosen && chosen[bound] !== undefined ? chosen[bound] : "";
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
        this.state.detail = await this.orm.call(
            "materials.catalog.provider", "get_detail", [productId]);
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
