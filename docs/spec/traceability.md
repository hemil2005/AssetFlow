# Requirements traceability

Every brief requirement mapped to its implementation and its proof. Status values:
**documented** (spec ready), **in review** (code pushed, gate open), **planned** (not started),
**gap** (no owner/decision yet).

## 1. Screens

| # | Brief screen | Implementation | Proof | Status |
|---|--------------|----------------|-------|--------|
| 1 | Login / Signup | Odoo auth + `auth_signup` override in `assetflow_base` | signup tour; portal/user group test | **gap** — B4 |
| 2 | Dashboard / Home | `assetflow_reports` OWL action + KPI contract | KPI tests; browser check | **planned** |
| 3A | Department management | `assetflow.department` + admin tab | CRUD + hierarchy tests | **gap** — B5 |
| 3B | Asset categories | `assetflow.category` | uniqueness/negative-warranty tests | **in review** (M2) |
| 3C | Employee directory + role promotion | `assetflow.employee` + admin buttons | promotion/ACL tests | **gap** — B3/B6 |
| 4 | Asset registration & directory | `assetflow.assets` asset views | lifecycle tests; tag sequence | **in review** (B7-B9, M1) |
| 5 | Allocation & transfer | allocation/transfer models + views | conflict/transfer/return tests | **in review** (B8, M9-M10) |
| 6 | Resource booking | `assetflow_booking` calendar/overlap/cron | boundary/overlap/cancel tests | **in review** (B10) |
| 7 | Maintenance | `assetflow_maintenance` | approval/state restore tests | **planned** (patient-wallaby) |
| 8 | Asset audit | `assetflow_audit` | generation/close/role tests | **documented** |
| 9 | Reports & analytics | `assetflow_reports` pivots/PDFs/heatmap | KPI/PDF/query-count tests | **documented** |
| 10 | Activity logs & notifications | `assetflow.notification` + `assetflow.activity.log` + chatter | ownership/idempotence tests | **gap** — M3 |

## 2. Capabilities

| Requirement | Implementation | Proof | Status |
|-------------|----------------|-------|--------|
| Departments, categories, employee directory | base models + admin menus | model/ACL tests | **gap** (departments/employees) |
| Asset tag `AF-0001` | `ir.sequence` + unique constraint | sequence test | **in review** — no sequence test (M12) |
| Lifecycle: Available, Allocated, Reserved, Under Maintenance, Lost, Retired, Disposed | asset state + guarded actions | transition matrix tests | **in review** (B7) |
| No double allocation | partial `UniqueIndex` + guard | DB + API test | **in review** (B8) |
| Conflict message + transfer offer | asset action/view | UI tour | **gap** — no allocate button (M9) |
| Transfer: Requested -> Approved -> Re-allocated | transfer model | atomic approval test | **in review** (M5/M6) |
| Return: condition check-in notes, status Available | allocation return | return tests | **in review** (B9) |
| Overdue allocations flagged | computed `is_overdue` + cron | boundary test | **in review** — cron missing |
| Booking overlap rejection | half-open interval + row lock | boundary/overlap/concurrency tests | **in review** (B10) |
| Booking statuses Upcoming/Ongoing/Completed/Cancelled | state + cron | state sync test | **in review** |
| Cancel/reschedule + reminder | actions + cron | cancel/reminder tests | **in review** — reminder is chatter |
| Maintenance approval workflow | maintenance model | approval/reject/restore tests | **planned** |
| Asset -> Maintenance on approval, back on resolve | `previous_asset_state` | state restore test | **planned** |
| Audit cycle, auditors, Verified/Missing/Damaged | audit models | generation/close tests | **documented** |
| Discrepancy report | QWeb PDF | PDF test | **documented** |
| Close locks cycle + updates statuses | close transaction | double-close test | **documented** |
| Utilization, maintenance frequency, department summary | pivots/graphs/PDF | view load + PDF test | **documented** |
| Booking heatmap | OWL/`_read_group` | bucket test | **documented** |
| Exportable reports | standard list export + PDFs | manual | **planned** |
| Notifications (assigned, approved, booking, overdue, audit) | notification model + helpers | idempotence/ownership tests | **gap** — M3 |
| Activity log (who did what, when) | activity log + helper | immutability/ACL test | **gap** — M3 |
| Photo/documents on assets | `image_1920` + chatter attachments | manual | **in review** |
| QR code search | not implemented | — | **gap** — decide scope |
| Forgot password | Odoo `auth_signup` | signup/reset tour | **gap** — follows B4 |
| Role-based menus and rules | groups + ACLs + record rules | role matrix tests | **in review** (B2/B3/M6/M11) |

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
