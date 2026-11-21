# Demo data and reset

A deterministic dataset for the demo and for report/audit tests. It is a plan, not committed
credentials: use disposable local passwords and never put real ones in git.

## 1. Users and roles

| Login | Name | Groups | Purpose |
|-------|------|--------|---------|
| `admin` | System Admin | `base.group_system`, `assetflow_admin` | creates org, promotes roles, audits |
| `maya.manager` | Maya (Asset Manager) | `base.group_user`, `assetflow_employee`, `assetflow_asset_manager` | assets, approvals |
| `dev.head` | Dev (Department Head, IT) | `base.group_user`, `assetflow_employee`, `assetflow_department_head` | department approvals/bookings |
| `priya.employee` | Priya | `base.group_user`, `assetflow_employee` | holder, booking, maintenance |
| `raj.employee` | Raj | `base.group_user`, `assetflow_employee` | transfer target, conflict demo |
| `auditor` | Sam (Auditor) | `base.group_user`, `assetflow_employee` | assigned to the audit cycle |

Create users through the signup flow for the last three; promote Maya and Dev through the Employee
Directory buttons (or the equivalent group write in demo data). Passwords are local demo values such
as `AssetFlow!2026`; do not commit them.

## 2. Organization

| Department | Parent | Head |
|------------|--------|------|
| IT | — | Dev |
| Operations | — | — |
| Facilities | Operations | — |

| Category | Code | Warranty |
|----------|------|----------|
| Electronics | ELEC | 24 months |
| Furniture | FURN | 0 |
| Vehicles | VEH | 0 |
| Rooms | ROOM | 0 |

## 3. Assets

| Tag | Name | Category | State | Holder | Bookable | Notes |
|-----|------|----------|-------|--------|----------|-------|
| AF-0001 | Laptop | Electronics | allocated | Priya | no | transferred to Raj during the demo |
| AF-0002 | Spare Laptop | Electronics | available | — | no | Raj's first attempt |
| AF-0003 | Projector | Electronics | available | — | yes | booking demo |
| AF-0004 | Meeting Room B2 | Rooms | available | — | yes | 09:00-10:00 booking |
| AF-0005 | Delivery Van | Vehicles | maintenance | — | no | maintenance demo |
| AF-0006 | Office Chair | Furniture | available | — | no | audit "damaged" |
| AF-0007 | Old Router | Electronics | lost | — | no | audit "missing" |
| AF-0008 | Reception Sofa | Furniture | retired | — | no | reports |
| AF-0009 | Tablet | Electronics | available | — | yes | overdue return scenario |

## 4. Demo records

- Allocation: `AF-0001` active for Priya, expected return 5 days from now.
- Allocation: `AF-0009` active for Priya, expected return **yesterday** (overdue KPI).
- Booking: `AF-0004` 09:00-10:00 tomorrow, Priya.
- Booking: `AF-0003` 10:00-11:00 tomorrow, Dev (department head booking).
- Maintenance: `AF-0005`, pending, raised by Priya; approve during the demo.
- Transfer: Priya requests `AF-0001` -> Raj; Dev approves.
- Audit: cycle scoped to IT, tomorrow, auditor Sam; `AF-0006` damaged, `AF-0007` missing;
  one line stays pending until the presenter closes it.

## 5. Expected KPI values at the start

| KPI | Value |
|-----|-------|
| Assets Available | 4 (`AF-0002`, `AF-0003`, `AF-0004`, `AF-0006`) |
| Assets Allocated | 2 (`AF-0001`, `AF-0009`) |
| Maintenance Today | 1 (`AF-0005`) |
| Active Bookings | 0 before the slot starts |
| Pending Transfers | 1 |
| Upcoming Returns | 1 (`AF-0001`) |
| Overdue Returns | 1 (`AF-0009`) |
| Open Maintenance | 1 |
| Unread Notifications | depends on the presenter's actions |

These numbers must be recomputed if the seed changes; the report tests should assert the same
dataset.

## 6. Seeding method

Preferred: a `demo/assetflow_demo.xml` in each addon for categories/departments/assets, plus a
management script for group assignments and users:

- demo data loads only with **Load demonstration data** or `--demo`;
- users are created with `res.users.create`, not by SQL;
- passwords are set via `user.password` in the demo script, never committed as real secrets;
- tags use the sequence or explicit `AF-000x` values that match the table;
- dates are relative to today (`fields.Date.add(today, days=...)`) so the demo does not age.

Fallback: a `scripts/seed_demo.py` run through `odoo shell`, but prefer XML + tests so the dataset is
part of the module.

## 7. Reset routine

Before a demo:

1. Create a fresh database `assetflow_demo`.
2. Install the six addons in order.
3. Load demo data.
4. Run the demo-data smoke test (counts + roles).
5. Log in as each role once to warm caches.

Never "fix" the demo with manual SQL. If a status is wrong, change the seed and reinstall.

## 8. Demo order

1. Admin: show departments/categories/employee promotion.
2. Maya: register `AF-0010`, then allocate `AF-0001` conflict with Raj (blocked, transfer offered).
3. Priya: request transfer, Dev approves; history updates.
4. Priya: book Room B2 09:00-10:00; Raj tries 09:30-10:30 (rejected), then 10:00-11:00 (accepted).
5. Priya: raise maintenance for the van; Maya approves; asset flips; Maya resolves.
6. Admin: audit cycle, Sam marks missing/damaged, close; Lost/damaged and PDF.
7. Show the dashboard KPIs and notifications.
