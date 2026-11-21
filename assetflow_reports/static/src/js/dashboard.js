import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class AssetflowDashboard extends Component {
    static template = "assetflow_reports.Dashboard";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: null, loading: true, error: null });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call("assetflow.dashboard", "get_kpi_data", []);
            this.state.error = null;
        } catch (error) {
            this.state.error = error.message || String(error);
        } finally {
            this.state.loading = false;
        }
    }

    openAsset(assetId) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "assetflow.asset",
            res_id: assetId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    newAsset() {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "assetflow.asset",
            views: [[false, "form"]],
            target: "current",
        });
    }

    newBooking() {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "assetflow.booking",
            views: [[false, "form"]],
            target: "current",
        });
    }

    newMaintenance() {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "assetflow.maintenance.request",
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("assetflow_reports.dashboard", AssetflowDashboard);
