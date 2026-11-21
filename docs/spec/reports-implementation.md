# Reports addon implementation contract (`assetflow_reports`)

Implementation-ready detail for Screens 2 and 9, plus the booking heatmap. Rules are in
[`../spec/workflows-rules-rbac.md`](workflows-rules-rbac.md) §5-§6; this file fixes the KPI contract,
query strategy, OWL action, views, PDFs, and tests.

**Depends:** `assetflow_base`, `assetflow_assets`, `assetflow_booking`, `assetflow_maintenance`,
`assetflow_audit`. **Owner:** northern-envelope (after the base gate). **Branch:**
`feat/assetflow-reports`.

## 1. Files

```
assetflow_reports/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── assetflow_dashboard.py
├── security/
│   └── ir.model.access.csv
├── report/
│   ├── assetflow_department_report.xml
│   └── assetflow_department_report_templates.xml
├── views/
│   ├── assetflow_asset_report_views.xml
│   ├── assetflow_booking_report_views.xml
│   ├── assetflow_maintenance_report_views.xml
│   └── assetflow_reports_menus.xml
├── static/
│   └── src/
│       ├── js/dashboard.js
│       ├── xml/dashboard.xml
│       └── scss/dashboard.scss
└── tests/
    ├── __init__.py
    └── test_assetflow_reports.py
```

Manifest: `depends` on all five addons above; data order ACL -> report -> views -> menus; assets:

```python
"assets": {
    "web.assets_backend": [
        "assetflow_reports/static/src/js/dashboard.js",
        "assetflow_reports/static/src/xml/dashboard.xml",
        "assetflow_reports/static/src/scss/dashboard.scss",
    ],
},
```

## 2. KPI contract

`assetflow.dashboard` is a `TransientModel` with no persisted fields:

```python
_name = "assetflow.dashboard"
_description = "AssetFlow Dashboard"

def get_kpi_data(self):
    return {
        "assets_available": ...,
        "assets_allocated": ...,
        "maintenance_today": ...,
        "active_bookings": ...,
        "pending_transfers": ...,
        "upcoming_returns": ...,
        "overdue_returns": ...,
        "open_maintenance": ...,
        "unread_notifications": ...,
        "generated_at": fields.Datetime.now(),
    }
```

Definitions:

| Key | Query |
|-----|-------|
| `assets_available` | `asset.search_count([("state", "=", "available")])` |
| `assets_allocated` | `asset.search_count([("state", "=", "allocated")])` |
| `maintenance_today` | assets `state = maintenance`, or open requests with `approved_at` today |
| `active_bookings` | `booking.search_count([("state", "=", "ongoing")])` |
| `pending_transfers` | `transfer.search_count([("state", "=", "requested")])` |
| `upcoming_returns` | active allocations with `expected_return_date` between today and today+7 |
| `overdue_returns` | active allocations with `expected_return_date < today` |
| `open_maintenance` | requests in `pending/approved/assigned/in_progress` |
| `unread_notifications` | `notification.search_count([("user_id", "=", self.env.user.id), ("is_read", "=", False)])` |

All queries run as the current user. **Do not `sudo()`** to make the dashboard look full; an employee
must see their own numbers.

Simple counts use `search_count`. Grouped data uses Odoo 19 `_read_group`:

```python
# signature: _read_group(domain, groupby=(), aggregates=(), having=(), offset=0, limit=None, order=None)
rows = self.env["assetflow.asset"]._read_group(
    [("state", "!=", "disposed")],
    ["category_id", "state"],
    ["id:count"],
)
# rows -> [(category_record, state, count), ...]
```

Aggregate specs are `"field:agg"` (`count`, `sum`, `avg`, `count_distinct`, `recordset`). Groupby
granularities: `day`, `week`, `month`, `quarter`, `year`, plus integer parts such as `hour_number`,
`day_of_week`, `month_number`.

Dashboard payload caps:

- recent overdue/upcoming rows: 10 each, no more;
- activity feed: 10 rows;
- no unbounded recordset serialized to the browser.

## 3. OWL dashboard action

`static/src/js/dashboard.js`:

```javascript
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

    openAssets(domain) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "assetflow.asset",
            views: [[false, "list"], [false, "form"]],
            domain,
        });
    }
}

registry.category("actions").add("assetflow_reports.dashboard", AssetflowDashboard);
```

Template requirements:

- KPI cards for the nine values; overdue and upcoming visually distinct.
- A refresh button calling `load()`.
- Quick actions: Register Asset (open asset form), Book Resource (booking form), Raise Maintenance
  (maintenance form).
- Loading and error states are real UI states, not blank screens.
- `t-out` for all text; no `t-raw`.
- No `setInterval` polling; refresh is user-driven.

Client action + menu:

```xml
<record id="action_assetflow_dashboard" model="ir.actions.client">
    <field name="name">Dashboard</field>
    <field name="tag">assetflow_reports.dashboard</field>
</record>
<menuitem id="menu_assetflow_dashboard" name="Dashboard"
          parent="assetflow_base.menu_assetflow_root"
          action="action_assetflow_dashboard" sequence="5"/>
```

Register the action before the menus in the manifest.

## 4. Graph and pivot views

### Asset utilization

Graph/pivot on `assetflow.asset`:

- rows: `category_id`
- measures: `id` count, `acquisition_cost`
- group by `department_id`, `state`.

Also a pivot on `assetflow.allocation` grouped by `asset_id.category_id` and `start_datetime:month`,
with `id:count`; this shows "most used vs idle" when combined with assets that have zero
allocations.

### Maintenance frequency

Pivot on `assetflow.maintenance.request`: rows `asset_id.category_id`, columns
`approved_at:month`, measure `id:count`; filter out rejected.

### Department allocation summary

Pivot on `assetflow.allocation`: rows `asset_id.department_id`, columns `state`, measure
`id:count`; a companion list with `expected_return_date` filters.

### Assets due / near retirement

List on `assetflow.asset` with a search filter using the acquisition date + a configurable useful
life (default 5 years). Keep the heuristic explicit in the filter label; do not invent a
depreciation engine.

### Booking heatmap

OWL grid or `pivot` fallback. Data:

```python
rows = self.env["assetflow.booking"]._read_group(
    [("state", "!=", "cancelled")],
    ["start_datetime:day_of_week", "start_datetime:hour_number"],
    ["id:count"],
)
```

- X axis: hour 0-23; Y axis: day of week.
- Color scale from count; show the max and a legend.
- Respect record rules: an employee sees their own heat, a manager sees all.
- Pivot fallback is acceptable if the OWL grid risks the demo.

## 5. PDF report: department allocation summary

- Report action on `assetflow.department`: `qweb-pdf`, `report_name`
  `assetflow_reports.report_department_allocation`, bound to Print.
- Template structure:

```xml
<template id="report_department_allocation">
    <t t-call="web.html_container">
        <t t-foreach="docs" t-as="doc">
            <t t-call="web.external_layout">
                <div class="page">
                    <h2>Department Allocation Summary</h2>
                    <h3 t-field="doc.name"/>
                    <table class="table table-sm">
                        <thead><tr><th>Asset</th><th>Holder</th><th>State</th><th>Expected return</th></tr></thead>
                        <tbody>
                            <tr t-foreach="doc.asset_ids" t-as="asset">
                                <td t-out="asset.asset_tag"/>
                                <td t-out="asset.holder_employee_id.name"/>
                                <td t-out="asset.state"/>
                                <td t-out="asset.expected_return_date"/>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </t>
        </t>
    </t>
</template>
```

- Report access: manager/admin; department heads may print their own department (record rules do the
  filtering).
- Use a bounded recordset; if a department has many assets, paginate or aggregate instead of
  printing thousands of rows.

## 6. Security and performance

- Dashboard model ACL: `base.group_user` read (no create/write/unlink); the data methods are
  read-only and rule-filtered.
- No `sudo()` in KPI queries.
- One `_read_group` per chart; never a query per record.
- Cap lists at 10 and charts at a reasonable bucket count.
- Add `assertQueryCount` around `get_kpi_data` to catch N+1 regressions.
- Cache nothing in the database; the dashboard is computed per request.

## 7. Tests

1. KPI values match a seeded dataset exactly.
2. Employee sees rule-filtered counts; manager sees all; no cross-employee leak.
3. `upcoming_returns` boundary: today + 7 included, +8 excluded; overdue uses `< today`.
4. Heatmap grouping returns the expected buckets for two bookings in different hours.
5. `assertQueryCount` for `get_kpi_data` (set a realistic budget, for example 20).
6. Department report returns 200 and contains a seeded asset tag (HttpCase/`url_open`).
7. Dashboard action `tag` resolves to the registered component (manual/tour).
8. No `sudo` in the module: a grep test or review gate.

## 8. Acceptance

- Dashboard loads with all nine KPIs on the demo database and the quick actions work.
- Numbers match the records and change after an allocation/booking/maintenance action.
- An employee sees their own overdue/booking numbers, not another employee's.
- Pivot/graph views open without XML/JS errors.
- Department PDF prints with the expected header/table.
- Query count stays within budget.
