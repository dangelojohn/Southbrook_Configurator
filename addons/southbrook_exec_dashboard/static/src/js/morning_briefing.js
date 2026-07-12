/** @odoo-module **/
// SPDX-License-Identifier: LGPL-3.0-only

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
// v19 removed the "user" service — it is now a plain import.
import { user } from "@web/core/user";

export class MorningBriefing extends Component {
    static template = "southbrook_exec_dashboard.MorningBriefing";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            error: null,
            snapshot: null,
        });
        onWillStart(async () => {
            await this._load();
        });
    }

    async _load() {
        this.state.loading = true;
        this.state.error = null;
        try {
            // get_or_create_today reuses the day's snapshot instead of
            // inserting a fresh row on every dashboard open / Refresh (which
            // grew the table unbounded).
            const snapshotId = await this.orm.call(
                "southbrook.exec_dashboard.snapshot",
                "get_or_create_today",
                []
            );
            const records = await this.orm.read(
                "southbrook.exec_dashboard.snapshot",
                [snapshotId],
                [
                    "as_of",
                    "label",
                    "yesterday_units_produced",
                    "yesterday_units_target",
                    "yesterday_takt_adherence_pct",
                    "units_planned_today",
                    "fpy_pct_7d",
                    "quality_open_critical_ncr_count",
                    "otd_pct_30d",
                    "wip_value_current",
                    "revenue_last_30d",
                    "cash_position",
                    "top_bottleneck_workcenter",
                    "top_bottleneck_load_pct",
                    "currency_id",
                ]
            );
            this.state.snapshot = records[0];
        } catch (e) {
            this.state.error = e.message || "Failed to load dashboard";
        } finally {
            this.state.loading = false;
        }
    }

    async onRefresh() {
        await this._load();
    }

    get greeting() {
        const hour = new Date().getHours();
        if (hour < 12) {
            return "Good morning";
        }
        if (hour < 18) {
            return "Good afternoon";
        }
        return "Good evening";
    }

    get userName() {
        return user.name || "";
    }

    get asOfDisplay() {
        const s = this.state.snapshot;
        if (!s || !s.as_of) {
            return "";
        }
        return String(s.as_of);
    }

    formatPct(value) {
        if (value === false || value === null || value === undefined) {
            return "n/a";
        }
        return Number(value).toFixed(1) + "%";
    }

    formatInt(value) {
        if (value === false || value === null || value === undefined) {
            return "0";
        }
        return String(Math.round(Number(value)));
    }

    formatMoney(value) {
        if (value === false || value === null || value === undefined) {
            return "$0";
        }
        const n = Number(value);
        if (n >= 1000000) {
            return "$" + (n / 1000000).toFixed(2) + "M";
        }
        if (n >= 1000) {
            return "$" + (n / 1000).toFixed(1) + "K";
        }
        return "$" + n.toFixed(0);
    }

    gaugeClass(pct) {
        const n = Number(pct);
        if (n >= 95) {
            return "sb-gauge sb-gauge-good";
        }
        if (n >= 80) {
            return "sb-gauge sb-gauge-warn";
        }
        return "sb-gauge sb-gauge-bad";
    }

    bottleneckClass(loadPct) {
        const n = Number(loadPct);
        if (n > 100) {
            return "sb-tile-value sb-tile-danger";
        }
        return "sb-tile-value";
    }

    openCriticalNcrs() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "southbrook.ncr",
            name: "Critical NCRs",
            view_mode: "list,form",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            domain: [
                ["state", "in", ["draft", "quarantine", "rework"]],
                ["severity", "=", "critical"],
            ],
            target: "current",
        });
    }
}

registry.category("actions").add(
    "southbrook_exec_dashboard.morning_briefing",
    MorningBriefing
);
