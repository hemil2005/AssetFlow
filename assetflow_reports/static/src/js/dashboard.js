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
            const [kpi, recent, heatmap] = await Promise.all([
                this.orm.call("assetflow.dashboard", "get_kpi_data", []),
                this.orm.call("assetflow.dashboard", "get_recent_activity", []),
                this.orm.call("assetflow.dashboard", "get_booking_heatmap", []),
            ]);
            this.state.data = { ...kpi, ...recent, heatmap };
            this.state.error = null;
        } catch (error) {
            this.state.error = error.message || String(error);
        } finally {
            this.state.loading = false;
        }
    }

    heatStyle(count) {
        const max = (this.state.data && this.state.data.heatmap && this.state.data.heatmap.max) || 0;
        if (!count || !max) {
            return "";
        }
        const ratio = Math.min(count / max, 1);
        return `background-color: rgba(113, 75, 103, ${(0.12 + ratio * 0.7).toFixed(2)});`;
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
