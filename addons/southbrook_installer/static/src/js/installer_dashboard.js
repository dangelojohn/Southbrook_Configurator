/** @odoo-module **/
// SPDX-License-Identifier: LGPL-3.0-only
// Dispatcher live status board.
//
// Subscribes to the `sami_installer` bus channel (the same channel
// southbrook.damage.flag / southbrook.installer.job already post to)
// and merges live updates into the visible rows. A 30s fallback poll
// keeps the board honest if a worker missed a bus event.

import {
    Component,
    onMounted,
    onWillUnmount,
    onWillStart,
    useState,
} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";


// Stage codes mapped to a CSS badge class. Stage codes are the stable
// enums seeded in data/southbrook_installer_stage_data.xml.
const STAGE_CLASS = {
    SCHEDULED: "sbi-stage-scheduled",
    PRE_SITE_CONFIRM: "sbi-stage-confirm",
    DELIVERY_RECEIVED: "sbi-stage-received",
    INSTALLATION_IN_PROGRESS: "sbi-stage-install",
    FINAL_SIGN_OFF: "sbi-stage-signoff",
    CLOSED_OUT: "sbi-stage-closed",
    COMPLETE: "sbi-stage-complete",
    INVOICED: "sbi-stage-invoiced",
};


// Fields fetched once for the board. Reads pull only what the row
// displays — wide reads on hot rows are the OWL-board common bug.
const BOARD_FIELDS = [
    "name",
    "stage_id",
    "completion_pct",
    "lead_installer_id",
    "site_address",
    "unit_number",
    "project_id",
    "scheduled_date",
    "delivery_confirmed",
    "is_blocked",
    "open_damage_count",
    "blocking_damage_count",
    "stage_log_count",
    "stage_log_done_count",
    "stage_is_terminal",
    "tool_loan_open_count",
    "closeout_done",
    "priority",
    "color",
    "write_date",
];


export class InstallerDispatchBoard extends Component {
    static template = "southbrook_installer.DispatchBoard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.busService = useService("bus_service");

        this.state = useState({
            loading: true,
            error: null,
            jobs: [],
            lastRefresh: null,
            filter: "active",
            busConnected: false,
            updateCount: 0,
        });

        // Bus handler — bound once so onMounted/onWillUnmount can
        // hand the SAME reference to subscribe/unsubscribe.
        this._onBusMessage = this._onBusMessage.bind(this);

        onWillStart(async () => {
            await this._loadJobs();
        });

        onMounted(() => {
            this._subscribeBus();
            // 30s fallback poll — covers worker bus-miss scenarios
            // (the v1 spec is explicit about this).
            this._pollTimer = setInterval(() => {
                this._loadJobs(/*silent=*/true);
            }, 30000);
        });

        onWillUnmount(() => {
            this._unsubscribeBus();
            if (this._pollTimer) {
                clearInterval(this._pollTimer);
                this._pollTimer = null;
            }
        });
    }

    // ------------------------------------------------------------------
    // Data
    // ------------------------------------------------------------------
    async _loadJobs(silent) {
        if (!silent) {
            this.state.loading = true;
        }
        this.state.error = null;
        try {
            const domain = this._domainForFilter(this.state.filter);
            // search_read keeps it to ONE round-trip vs search + read.
            const records = await this.orm.searchRead(
                "southbrook.installer.job",
                domain,
                BOARD_FIELDS,
                {
                    order: "is_blocked DESC, priority DESC, scheduled_date ASC, id ASC",
                    limit: 200,
                }
            );
            this.state.jobs = records;
            this.state.lastRefresh = new Date();
        } catch (e) {
            this.state.error = e.message || "Failed to load dispatch board";
        } finally {
            if (!silent) {
                this.state.loading = false;
            }
        }
    }

    _domainForFilter(filter) {
        if (filter === "blocked") {
            return [["is_blocked", "=", true]];
        }
        if (filter === "today") {
            const today = new Date();
            const start = today.toISOString().slice(0, 10) + " 00:00:00";
            const end = today.toISOString().slice(0, 10) + " 23:59:59";
            return [
                ["scheduled_date", ">=", start],
                ["scheduled_date", "<=", end],
            ];
        }
        if (filter === "all") {
            return [];
        }
        // default: active = not in terminal stage
        return [["stage_is_terminal", "=", false]];
    }

    // ------------------------------------------------------------------
    // Bus
    // ------------------------------------------------------------------
    _subscribeBus() {
        try {
            this.busService.addChannel("sami_installer");
            this.busService.subscribe("installer_update", this._onBusMessage);
            this.state.busConnected = true;
        } catch (e) {
            // Bus service unavailable (rare on backend) — fall back
            // to the 30s poll. Surface in the indicator.
            this.state.busConnected = false;
        }
    }

    _unsubscribeBus() {
        try {
            this.busService.unsubscribe("installer_update", this._onBusMessage);
        } catch (e) {
            // Service may have been torn down already; ignore.
        }
    }

    _onBusMessage(payload) {
        // payload shape per damage_flag._notify_dispatcher_bus +
        // installer_job._notify_dispatcher_bus (Phase 2.2 wiring).
        // Common keys: event, job_id, job_ref, stage, completion_pct,
        // open_flags, is_blocked, timestamp.
        if (!payload || !payload.job_id) {
            return;
        }
        this.state.updateCount = this.state.updateCount + 1;
        // Targeted refresh of the affected job, falling back to full
        // reload if we can't find it locally (might be a new job).
        const idx = this.state.jobs.findIndex(
            (j) => j.id === payload.job_id
        );
        if (idx === -1) {
            this._loadJobs(/*silent=*/true);
            return;
        }
        // Re-fetch THIS row so all stored computes (color, counts) are
        // in sync. One ORM call, cheap.
        this.orm.read(
            "southbrook.installer.job",
            [payload.job_id],
            BOARD_FIELDS
        ).then((records) => {
            if (records.length) {
                this.state.jobs[idx] = records[0];
            }
        }).catch(() => {
            // ignore — next poll will reconcile
        });
    }

    // ------------------------------------------------------------------
    // Computed view helpers
    // ------------------------------------------------------------------
    get filteredJobs() {
        return this.state.jobs;
    }

    get summary() {
        const jobs = this.state.jobs;
        return {
            total: jobs.length,
            blocked: jobs.filter((j) => j.is_blocked).length,
            flagged: jobs.filter((j) => !j.is_blocked && j.open_damage_count > 0).length,
            on_track: jobs.filter((j) => !j.is_blocked && j.open_damage_count === 0).length,
            tools_out: jobs.reduce((acc, j) => acc + (j.tool_loan_open_count || 0), 0),
        };
    }

    rowClass(job) {
        const base = "sbi-row";
        if (job.is_blocked) {
            return base + " sbi-row-blocked";
        }
        if (job.open_damage_count > 0) {
            return base + " sbi-row-flagged";
        }
        if (job.stage_is_terminal) {
            return base + " sbi-row-terminal";
        }
        return base + " sbi-row-ok";
    }

    stageBadgeClass(job) {
        const stage = job.stage_id ? job.stage_id[0] : null;
        if (!stage) {
            return "sbi-stage-badge";
        }
        // stage_id is [id, display_name]; we mapped by code so look
        // it up via the display_name suffix the stage's _compute_
        // display_name produced ("Scheduled (SCHEDULED)").
        const label = job.stage_id[1] || "";
        const m = label.match(/\(([A-Z_]+)\)$/);
        const code = m ? m[1] : null;
        const cls = STAGE_CLASS[code] || "sbi-stage-default";
        return "sbi-stage-badge " + cls;
    }

    progressSegments(job) {
        // 11-segment phase bar per v1 spec. We approximate from
        // (done / total) — since the count fields are NOT broken out
        // by phase here, we map completion_pct → filled segments.
        const total = 11;
        const pct = Math.max(0, Math.min(100, job.completion_pct || 0));
        const filled = Math.round((pct / 100) * total);
        const segments = [];
        for (let i = 0; i < total; i++) {
            segments.push(i < filled ? "sbi-seg sbi-seg-filled" : "sbi-seg");
        }
        return segments;
    }

    timeSince(job) {
        // write_date is the last touch — Bus updates trigger writes,
        // so this is a fair "last activity" proxy.
        if (!job.write_date) {
            return "";
        }
        const wrote = new Date(job.write_date.replace(" ", "T") + "Z");
        const seconds = Math.max(0, Math.floor((Date.now() - wrote.getTime()) / 1000));
        if (seconds < 60) {
            return seconds + "s ago";
        }
        if (seconds < 3600) {
            return Math.floor(seconds / 60) + "m ago";
        }
        if (seconds < 86400) {
            return Math.floor(seconds / 3600) + "h ago";
        }
        return Math.floor(seconds / 86400) + "d ago";
    }

    lastRefreshDisplay() {
        if (!this.state.lastRefresh) {
            return "—";
        }
        const d = this.state.lastRefresh;
        return d.toLocaleTimeString();
    }

    // ------------------------------------------------------------------
    // Actions
    // ------------------------------------------------------------------
    openJob(job) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "southbrook.installer.job",
            res_id: job.id,
            name: job.name,
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
        });
    }

    setFilter(filter) {
        this.state.filter = filter;
        this._loadJobs();
    }

    onRefresh() {
        this._loadJobs();
    }
}


registry.category("actions").add(
    "southbrook_installer.dispatch_board",
    InstallerDispatchBoard
);
