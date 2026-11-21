import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import {
    deserializeDate,
    deserializeDateTime,
    toLocaleDateString,
    toLocaleDateTimeString,
    today,
} from "@web/core/l10n/dates";

const NOTIFICATION_LABELS = {
    booking_reminder: "Booking reminder",
    overdue_return: "Overdue return",
    transfer: "Transfer",
    maintenance: "Maintenance",
    audit: "Audit",
    system: "System",
};

export class AssetflowDashboard extends Component {
    static template = "assetflow_reports.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: null, loading: true, error: null });
        this.legendSteps = [0.25, 0.5, 0.75, 1];
        this.hourTicks = Array.from({ length: 24 }, (_, hour) =>
            hour % 3 === 0 ? String(hour).padStart(2, "0") : ""
        );
        onWillStart(() => {
            // Render the skeleton first: the dashboard must not hold the tab
            // hostage on an RPC. Errors land in state and render as UI.
            this.load();
        });
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

    // --- presentation -----------------------------------------------------

    get canRegister() {
        return Boolean(this.state.data && this.state.data.can_manage_assets);
    }

    get updatedLabel() {
        if (!this.state.data) {
            return "";
        }
        return toLocaleDateTimeString(deserializeDateTime(this.state.data.generated_at));
    }

    /** The nine KPI values, grouped the way an operator reads them. */
    get kpiGroups() {
        const data = this.state.data || {};
        return [
            {
                key: "attention",
                title: "Needs attention",
                flagged: Boolean(data.overdue_returns || data.open_maintenance),
                items: [
                    {
                        key: "overdue_returns",
                        label: "Overdue returns",
                        flagged: Boolean(data.overdue_returns),
                    },
                    {
                        key: "open_maintenance",
                        label: "Open maintenance",
                        flagged: Boolean(data.open_maintenance),
                    },
                    { key: "unread_notifications", label: "Unread notifications" },
                ],
            },
            {
                key: "inventory",
                title: "Inventory",
                items: [
                    { key: "assets_available", label: "Available" },
                    { key: "assets_allocated", label: "Allocated" },
                    { key: "maintenance_today", label: "Under maintenance" },
                ],
            },
            {
                key: "movement",
                title: "Movement",
                items: [
                    { key: "active_bookings", label: "Active bookings" },
                    { key: "pending_transfers", label: "Pending transfers" },
                    { key: "upcoming_returns", label: "Upcoming returns" },
                ],
            },
        ];
    }

    shortDate(value) {
        return value ? toLocaleDateString(deserializeDate(value)) : "";
    }

    /** "3d late" / "due today" / "in 5d" for a date-only SQL string. */
    dueLabel(value) {
        if (!value) {
            return "";
        }
        const days = Math.round(today().diff(deserializeDate(value), "days").days);
        if (days > 0) {
            return `${days}d late`;
        }
        if (days === 0) {
            return "due today";
        }
        return `in ${Math.abs(days)}d`;
    }

    notificationLabel(type) {
        return NOTIFICATION_LABELS[type] || "Notice";
    }

    heatStyle(count) {
        const max = (this.state.data && this.state.data.heatmap && this.state.data.heatmap.max) || 0;
        if (!count || !max) {
            return "";
        }
        const ratio = Math.min(count / max, 1);
        // Deep cells carry white type, pale cells carry ink: never the other way round.
        return `background-color: rgba(72, 42, 62, ${(0.12 + ratio * 0.74).toFixed(2)}); color: ${
            ratio >= 0.75 ? "#ffffff" : "#2f1c29"
        };`;
    }

    legendStyle(ratio) {
        return `background-color: rgba(72, 42, 62, ${(0.12 + ratio * 0.74).toFixed(2)});`;
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
