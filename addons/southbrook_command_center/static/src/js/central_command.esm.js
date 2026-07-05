/** @odoo-module */
// SPDX-License-Identifier: LGPL-3.0-only
// Central Command — backend OWL client action (DELIVERABLE_4_UI.md).
// Registered as action tag "southbrook_command_center.central_command".
// Read-only against business objects: buttons navigate to the source record
// or call the exception model's own workflow methods; the dashboard never
// writes business state. Live updates ride bus.bus when available and degrade
// to a manual Refresh otherwise (DELIVERABLE_5_DELIVERY.md §5).

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { rpc } from "@web/core/network/rpc";
import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";

const EXCEPTION_FIELDS = [
    "severity", "owner_id", "impact_summary", "recommended_action",
    "why_text", "state", "source_model", "source_res_id", "exception_type",
];

export class CentralCommand extends Component {
    static template = "southbrook_command_center.CentralCommand";
    static props = ["*"];

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.busService = useService("bus_service");

        this.state = useState({
            loading: true,
            error: null,
            role: null,
            busConnected: false,
            factoryHealth: null,
            factoryHealthStale: false,
            healthExpanded: false,
            exceptions: [],
            exceptionsTotal: 0,
            flow: null,
            recommendations: [],
            alerts: [],
        });

        this._onExceptionMsg = this._onExceptionMsg.bind(this);
        this._onAlertMsg = this._onAlertMsg.bind(this);
        this._onHermesMsg = this._onHermesMsg.bind(this);

        onWillStart(async () => {
            await this._resolveRole();
            await this._loadAll();
        });

        onMounted(() => this._subscribeBus());
        onWillUnmount(() => this._unsubscribeBus());
    }

    get companyId() {
        try {
            const ids = user.context && user.context.allowed_company_ids;
            if (ids && ids.length) {
                return ids[0];
            }
        } catch {
            // fall through to default
        }
        return 1;
    }

    async _resolveRole() {
        const G = "southbrook_command_center.";
        try {
            if (await user.hasGroup(G + "group_command_center_owner")) {
                this.state.role = "owner";
            } else if (await user.hasGroup(G + "group_command_center_production_manager")) {
                this.state.role = "production_manager";
            } else if (await user.hasGroup(G + "group_command_center_shop_foreman")) {
                this.state.role = "shop_foreman";
            } else if (await user.hasGroup(G + "group_command_center_purchasing_manager")) {
                this.state.role = "purchasing_manager";
            } else if (await user.hasGroup(G + "group_command_center_warehouse_manager")) {
                this.state.role = "warehouse_manager";
            } else {
                this.state.role = "owner";
            }
        } catch {
            this.state.role = "owner";
        }
    }

    async _loadAll() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const payload = await rpc("/command_center/bootstrap", {
                company_id: this.companyId,
                role: this.state.role,
            });
            this.state.factoryHealth = payload.factory_health;
            this.state.flow = payload.flow;
            this.state.exceptions = payload.exceptions || [];
            this.state.exceptionsTotal = payload.exceptions_total || 0;
            this.state.recommendations = payload.recommendations || [];
            this.state.alerts = payload.alerts || [];
            this.state.factoryHealthStale = false;
        } catch (e) {
            this.state.error = (e && e.message) || "Failed to load Central Command";
        } finally {
            this.state.loading = false;
        }
    }

    onRefresh() {
        this._loadAll();
    }

    toggleHealth() {
        this.state.healthExpanded = !this.state.healthExpanded;
    }

    // -- bus -----------------------------------------------------------
    _subscribeBus() {
        try {
            const cid = this.companyId;
            this.busService.addChannel("sb_cc_exceptions_" + cid);
            this.busService.addChannel("sb_cc_alerts_" + cid);
            this.busService.addChannel("sb_cc_hermes_" + cid);
            this.busService.subscribe("exception_upsert", this._onExceptionMsg);
            this.busService.subscribe("exception_resolved", this._onExceptionMsg);
            this.busService.subscribe("ops_event", this._onAlertMsg);
            this.busService.subscribe("hermes_upsert", this._onHermesMsg);
            this.state.busConnected = true;
        } catch {
            this.state.busConnected = false;
        }
    }

    _unsubscribeBus() {
        try {
            this.busService.unsubscribe("exception_upsert", this._onExceptionMsg);
            this.busService.unsubscribe("exception_resolved", this._onExceptionMsg);
            this.busService.unsubscribe("ops_event", this._onAlertMsg);
            this.busService.unsubscribe("hermes_upsert", this._onHermesMsg);
        } catch {
            // best effort
        }
    }

    _onExceptionMsg(payload) {
        if (!payload || !payload.exception_id) {
            return;
        }
        if (payload.state === "resolved" || payload.state === "dismissed") {
            const gone = this.state.exceptions.findIndex((r) => r.id === payload.exception_id);
            if (gone !== -1) {
                this.state.exceptions.splice(gone, 1);
            }
            this.state.exceptionsTotal = Math.max(0, this.state.exceptionsTotal - 1);
            this.state.factoryHealthStale = true;
            return;
        }
        this.orm.read("southbrook.command.exception", [payload.exception_id], EXCEPTION_FIELDS)
            .then((records) => {
                if (!records.length) {
                    return;
                }
                const idx = this.state.exceptions.findIndex((r) => r.id === payload.exception_id);
                if (idx === -1) {
                    this.state.exceptions.unshift(records[0]);
                } else {
                    this.state.exceptions[idx] = records[0];
                }
                this.state.factoryHealthStale = true;
            });
    }

    _onAlertMsg(payload) {
        if (!payload) {
            return;
        }
        this.state.alerts.unshift(payload);
        if (this.state.alerts.length > 30) {
            this.state.alerts.pop();
        }
    }

    _onHermesMsg() {
        // Cheapest correct behavior: re-pull the recommendations panel.
        rpc("/command_center/bootstrap", { company_id: this.companyId, role: this.state.role })
            .then((p) => {
                this.state.recommendations = p.recommendations || [];
            })
            .catch(() => {});
    }

    // -- interaction contract -----------------------------------------
    onNavigate(model, resId) {
        if (!model || !resId) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            res_id: resId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    onAcknowledge(id) {
        this.orm.call("southbrook.command.exception", "action_acknowledge", [[id]])
            .then(() => this._loadAll());
    }

    onResolve(id) {
        this.orm.call("southbrook.command.exception", "action_resolve", [[id]])
            .then(() => this._loadAll());
    }

    severityClass(sev) {
        return "sb_cc_sev sb_cc_sev_" + (sev || "low");
    }
}

registry.category("actions").add("southbrook_command_center.central_command", CentralCommand);
