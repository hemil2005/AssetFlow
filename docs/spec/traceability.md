# Requirements traceability

Every brief requirement mapped to its implementation and its proof. Status values:
**documented** (spec ready), **in review** (code pushed, gate open), **planned** (not started),
**gap** (no owner/decision yet).

## 1. Screens

| # | Brief screen | Implementation | Proof | Status |
|---|--------------|----------------|-------|--------|
| 1 | Login / Signup | Odoo auth + `auth_signup` override in `assetflow_base` | signup unit test; HTTP tour missing | **implemented; HTTP tour pending** |
| 2 | Dashboard / Home | `assetflow_reports` OWL action + KPI contract | KPI/heatmap tests; admin+employee browser click | **implemented; browser verified** |
| 3A | Department management | `assetflow.department` + admin tab | CRUD + hierarchy tests | **implemented** |
| 3B | Asset categories | `assetflow.category` | uniqueness/negative-warranty tests | **implemented** |
| 3C | Employee directory + role promotion | `assetflow.employee` + admin buttons | promotion/ACL tests | **implemented** |
| 4 | Asset registration & directory | `assetflow.assets` asset views | lifecycle tests; tag sequence | **implemented; gate verified** |
| 5 | Allocation & transfer | allocation/transfer models + views | conflict/transfer/return tests | **implemented; gate verified** |
| 6 | Resource booking | `assetflow_booking` calendar/overlap/cron | boundary/overlap/cancel tests | **implemented; gate verified** |
| 7 | Maintenance | `assetflow_maintenance` | approval/state restore tests | **implemented** |
| 8 | Asset audit | `assetflow_audit` | generation/close/role tests; review probes | **implemented; review re-checked** |
| 9 | Reports & analytics | `assetflow_reports` pivots/PDFs/heatmap | KPI/PDF/query-count/heatmap tests | **implemented; browser verified** |
| 10 | Activity logs & notifications | `assetflow.notification` + `assetflow.activity.log` + chatter | ownership/idempotence tests | **implemented; UI minimal** |

## 2. Capabilities

| Requirement | Implementation | Proof | Status |
|-------------|----------------|-------|--------|
| Departments, categories, employee directory | base models + admin menus | model/ACL tests | **implemented** |
| Asset tag `AF-0001` | `ir.sequence` + unique constraint | sequence test | **implemented** |
| Lifecycle: Available, Allocated, Reserved, Under Maintenance, Lost, Retired, Disposed | asset state + guarded actions | transition matrix tests | **implemented**; trusted-context residual |
| No double allocation | partial `UniqueIndex` + guard | DB + API + concurrency test | **implemented; gate verified** |
| Conflict message + transfer offer | asset action/view | UI tour | **implemented; demo pending** |
| Transfer: Requested -> Approved -> Re-allocated | transfer model | atomic approval test | **implemented; gate verified** |
| Return: condition check-in notes, status Available | allocation return | return tests | **implemented** |
| Overdue allocations flagged | computed `is_overdue` + cron | boundary test | **implemented** (cron pending) |
| Booking overlap rejection | half-open interval + row lock | boundary/overlap/concurrency tests | **implemented; independently probed** |
| Booking statuses Upcoming/Ongoing/Completed/Cancelled | state + cron | state sync test | **implemented** |
| Cancel/reschedule + reminder | actions + cron | cancel/reminder tests | **implemented** |
| Maintenance approval workflow | maintenance model | approval/reject/restore tests | **implemented** |
| Asset -> Maintenance on approval, back on resolve | `previous_asset_state` | state restore test | **implemented** |
| Audit cycle, auditors, Verified/Missing/Damaged | audit models | generation/close tests | **implemented** |
| Discrepancy report | QWeb PDF | PDF test | **implemented** |
| Close locks cycle + updates statuses | close transaction | double-close test | **implemented; review re-checked** |
| Utilization, maintenance frequency, department summary | pivots/graphs/PDF | view load + PDF test | **implemented** |
| Booking heatmap | OWL/`_read_group` | bucket + browser test | **implemented** |
| Exportable reports | standard list export + PDFs | manual | **implemented (standard export)** |
| Notifications (assigned, approved, booking, overdue, audit) | notification model + helpers | idempotence/ownership tests | **implemented** |
| Activity log (who did what, when) | activity log + helper | immutability/ACL test | **implemented** |
| Photo/documents on assets | `image_1920` + chatter attachments | manual | **implemented** |
| QR code search | not implemented | — | **gap** — decide scope |
| Forgot password | Odoo `auth_signup` | signup/reset tour | **implemented; tour pending** |
| Role-based menus and rules | groups + ACLs + record rules | role matrix tests | **implemented; gate verified** |

## 3. Roles

| Role | Required abilities | Implemented? | Proof |
|------|--------------------|--------------|-------|
| Admin | org setup, roles, audits, org analytics | partial (no department/role UI) | role tests |
| Asset Manager | register/allocate, approve transfers/maintenance/audits/returns | partial (no dept head path, unguarded) | ACL tests |
| Department Head | view dept assets, approve dept transfers, book for dept | partial (no write, no approval) | dept scope tests |
| Employee | own assets, book, raise maintenance, request return/transfer | partial (allocation/transfer rules missing) | own-record tests |

## 4. Explicitly out of scope (from the brief)

Purchasing, invoicing, accounting/depreciation, stock valuation, payroll, multi-company, email/SMS
gateways, native mobile apps. Do not add them to satisfy "reports"; use acquisition cost as a
reporting value only.

## 5. Judging checklist

- [ ] Every row above has a proof, not just code.
- [ ] All ten screens are reachable by the right role.
- [ ] The demo narrative works on a fresh database.
- [ ] No requirement is "implemented" only in a doc.

Update this file whenever a status changes; it is the fastest way to see what is still missing.
