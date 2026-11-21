# AssetFlow

Enterprise **Asset & Resource Management** built as six Odoo 19 Community addons for the hackathon
brief in [`AssetFlow problem statement.pdf`](AssetFlow%20problem%20statement.pdf).

[![Odoo 19 addon tests](https://github.com/hemil2005/AssetFlow/actions/workflows/tests.yml/badge.svg)](https://github.com/hemil2005/AssetFlow/actions/workflows/tests.yml)

AssetFlow covers departments, categories and an employee directory; the full asset lifecycle,
allocation, transfers and returns; half-open time-slot booking of shared resources; maintenance
approval and technician workflow; audit cycles with discrepancy reports; and a KPI dashboard with
utilization views and PDFs. Purchasing, invoicing, accounting, stock valuation, payroll,
multi-company and external messaging are explicitly out of scope.

## Status

**v0.1.0 — feature complete for the brief, demo-ready.** All six addons are on `main`, CI runs the
full install + test suite, and the demo seed/narrative are scripted. Current verification:

- **82 tests, 0 failed** across the six addons on a fresh Odoo 19 + PostgreSQL 16 database.
- Browser-verified dashboard for both an admin and an employee (cards, heatmap, role gating).
- Independent gate evidence for the base/assets/booking slice (33 tests + an 11-case runtime probe)
  and the integrated branch (73 tests + audit/heatmap/KPI probes).

## Addons

| Addon | What it does |
|-------|--------------|
| `assetflow_base` | Departments, categories, employees, roles/signup, sequences, notifications, activity log, admin setup |
| `assetflow_assets` | Asset registry and lifecycle, allocation, transfer, return, overdue flag + daily notification cron |
| `assetflow_booking` | Shared-resource bookings: overlap-safe half-open intervals, calendar/list, reminders, state sync |
| `assetflow_maintenance` | Requests, manager approval/rejection, technician assignment, start/resolve with asset state restore |
| `assetflow_audit` | Audit cycles/lines, scoped generation, auditor workflow, close locks + discrepancy PDF |
| `assetflow_reports` | OWL KPI dashboard, booking heatmap, utilization/maintenance/booking analysis, department PDF |

## Quick start (Docker)

```powershell
Copy-Item .env.example .env      # set POSTGRES_PASSWORD; .env is git-ignored
docker compose up -d             # Odoo 19 Community + PostgreSQL 16
```

Open <http://localhost:8069>, create a database with demo data **off**, then install the addons in
order: `assetflow_base`, `assetflow_assets`, `assetflow_booking`, `assetflow_maintenance`,
`assetflow_audit`, `assetflow_reports`.

### Seed the demo and walk it

```powershell
./scripts/demo.ps1               # fresh DB, install six addons, seed, run the narrative
```

The wrapper creates `assetflow_demo`, seeds users/org/assets/bookings/maintenance/audit, runs the
five-step narrative (transfer, booking conflict, maintenance, audit close, KPI checks), and prints
the URL. Demo logins are `maya.manager`, `dev.head`, `priya.employee`, `raj.employee`, `auditor`;
the password is `ASSETFLOW_DEMO_PASSWORD` (default `AssetFlow!2026`). See
[`docs/instructions/demo-runbook.md`](docs/instructions/demo-runbook.md) for the manual steps and
troubleshooting.

### Test

```powershell
./scripts/test.ps1                        # install all six, then run each addon's tests
./scripts/test.ps1 -Addon assetflow_audit # one addon
./scripts/test.ps1 -SkipInstall           # tests only
```

Logs land in `odoo-data/logs/`. CI runs the same command shape in `.github/workflows/tests.yml`.

## Design notes

- **One active allocation per asset** is enforced by a partial unique index, not just Python.
- **Bookings are half-open** `[start, end)`; overlap checks run under a row lock, with adjacent
  slots allowed and concurrent writers proven to serialize.
- **Lifecycle fields are workflow-owned**: form/RPC writes to `state`, holder and expected return
  dates are rejected; transitions go through guarded actions. A trusted context flag remains for
  server workflows (documented residual).
- **Record rules first**: employee, department head, asset manager and admin each see their slice;
  the dashboard and heatmap are rule-filtered, not `sudo()`-padded.
- **Signup is internal but role-less**: a new account gets `base.group_user` and no AssetFlow role;
  only an administrator can promote it.
- **Odoo 19 patterns only**: `models.Constraint`/`models.UniqueIndex`, `<list>`, `invisible=`,
  `_read_group`, `group_ids`, no `_sql_constraints`/`<tree>`/`states=`/`attrs=`.

## Documentation

Start at [`docs/README.md`](docs/README.md):

- [`docs/current-state.md`](docs/current-state.md) — current status and next actions
- [`docs/spec/domain-model.md`](docs/spec/domain-model.md) — models and data ownership
- [`docs/spec/workflows-rules-rbac.md`](docs/spec/workflows-rules-rbac.md) — states, rules, roles, KPIs
- [`docs/spec/demo-data.md`](docs/spec/demo-data.md) — demo dataset and narrative
- [`docs/instructions/`](docs/instructions/) — coding rules, build plan, verification, demo runbook
- [`docs/reviews/`](docs/reviews/) — review log and gate evidence

## Contributing

This repo uses **Murmur** for coordination between agents on different machines; see
[`AGENTS.md`](AGENTS.md) and [`docs/instructions/murmur-protocol.md`](docs/instructions/murmur-protocol.md).
Claim an addon before editing it, push a `feat/assetflow-*` branch, and get independent review
before merging to `main`.
