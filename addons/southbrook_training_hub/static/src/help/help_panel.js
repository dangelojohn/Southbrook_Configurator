/** @odoo-module **/
/* SPDX-License-Identifier: LGPL-3.0-only */
/*
 * HelpPanelDialog — the modal opened by the systray button.
 *
 * Shape: a Dialog with a search input + a list of training items.
 * On mount, calls /training/recommended to show a default set. On
 * keystroke, debounces 200ms then calls /training/search.
 *
 * Items open in a new tab — we don't navigate the Odoo SPA away from
 * whatever the user was doing.
 */
import {Component, onWillStart, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {useService} from "@web/core/utils/hooks";

export class HelpPanelDialog extends Component {
    static template = "southbrook_training_hub.HelpPanelDialog";
    static components = {Dialog};
    static props = {
        close: {type: Function, optional: true},
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            query: "",
            items: [],
            loading: true,
            error: "",
        });
        this._debounce = null;

        onWillStart(async () => {
            await this.load();
        });
    }

    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            const result = await this.orm.call(
                "southbrook.training.item",
                "search_for_user",
                [],
                {query: this.state.query || null, limit: 10},
            );
            this.state.items = result || [];
        } catch (err) {
            this.state.error = (err && err.message) || "Search failed.";
            this.state.items = [];
        } finally {
            this.state.loading = false;
        }
    }

    onInput(ev) {
        this.state.query = ev.target.value;
        if (this._debounce) {
            clearTimeout(this._debounce);
        }
        this._debounce = setTimeout(() => this.load(), 200);
    }

    onOpenItem(url) {
        if (!url) return;
        window.open(url, "_blank", "noopener,noreferrer");
    }
}
