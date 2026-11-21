# Build plan

Six addons, one integration branch (`main`), short review gates between phases. The plan is ordered so
each phase can be demoed on its own and no phase depends on work that has not landed.

## 0. Working agreement

- **Branches:** each phase lands on a short-lived branch (`feat/assetflow-base`, `feat/assetflow-assets`,
  ...) and merges to `main` only after the review gate. Never force-push `main`.
- **Small pushes:** push a WIP branch within 30-60 minutes of starting a phase, even if incomplete.
  Review cannot happen against an unpushed working tree.
- **One writer per file set:** claim the file set in Murmur before editing. Current claim:
  flat-orchid owns all addon Python/XML/CSV; northern-envelope owns `docs/`.
- **Docs first:** if implementation must diverge from `spec/`, change the spec in the same branch and
  say why in the commit message.
- **Definition of done:** see [`coding-instructions.md`](coding-instructions.md#11-definition-of-done).
- **Evidence:** every phase ends with the commands run and their output (tests, install log, screenshot
  path) pasted into the review thread.

## 1. Phase map

| Phase | Addon | Depends on | Main outcome |
|-------|-------|------------|--------------|
| 0 | repo | - | docs, env, compose, conventions, CI skeleton |
| 1 | `assetflow_base` | - | roles, departments, categories, employees, sequences, signup, notifications/log |
| 2 | `assetflow_assets` | base | asset directory, allocation, transfer, returns |
| 3 | `assetflow_booking` | base, assets | calendar booking, overlap rejection, reminders |
| 4 | `assetflow_maintenance` | base, assets | approval workflow, state flip/restore, history |
| 5 | `assetflow_audit` | base, assets | cycles, lines, discrepancy report, close |
| 6 | `assetflow_reports` | all | KPI dashboard, pivots, PDFs |
| 7 | integration | all | demo data, tours, performance, release |

Phases 3, 4, and 5 are independent after Phase 2 and can run in parallel if each claims separate
addons. Phase 6 starts only when the models it aggregates are stable.

### Current status (2026-11-21)

| Phase | Status | Branch / note |
|-------|--------|---------------|
| 0 | done (harness merged) | docs + `.gitignore` + compose/test runner on main (`2440d94`) |
| 1 | second review, B8/B10 open | `feat/assetflow-base` @ `5c831a5` |
| 2 | second review, B8/B10 open | same branch |
| 3 | second review, B10 open | `feat/assetflow-booking` @ `55025a4` |
| 4 | started | patient-wallaby, based on `5c831a5` |
| 5 | contract ready | `docs/spec/audit-implementation.md` |
| 6 | contract ready | `docs/spec/reports-implementation.md` |
| 7 | not started | needs a stable demo and the harness |

The full finding list is in [`../reviews/2026-11-21-base-assets-booking.md`](../reviews/2026-11-21-base-assets-booking.md).

## Phase 0 — Repo and environment

**Owner:** northern-envelope (docs), Hemil (Docker), flat-orchid (source install)

Tasks:

1. `docs/` published and linked from `README.md`; `AGENTS.md` points agents at the docs.
2. `docker-compose.yml` and `.env.example` added; Docker Desktop running on Hemil's machine.
3. `.gitignore` for `.env`, `.venv/`, `__pycache__/`, `*.pyc`, `*.log`, `odoo-data/`.
4. `README.md` quick start: run, create DB, install addons, run tests.
5. A clean database `assetflow` exists.

Acceptance:

- [ ] `docker compose up -d` starts both services and `/web/login` loads.
- [ ] `odoo-bin --version` (or the container) reports 19.0.
- [ ] No secrets are committed.
- [ ] Docs links resolve.

## Phase 1 — `assetflow_base`

**Outcome:** the master data and the security model everything else uses.

Tasks:

1. Manifest with `depends = ["base", "mail", "auth_signup"]`.
2. Module category, privilege, four groups, record rules, ACL CSV.
3. `res.users.employee_id` extension.
4. `assetflow.department` with hierarchy guard and complete name.
5. `assetflow.category` with `warranty_months`.
6. `assetflow.employee` with role compute and admin-only promotion buttons.
7. `assetflow.notification` and `assetflow.activity.log` plus the logging helper.
8. Three sequences and the root menu/icon.
9. Signup override: new accounts are internal Employees with no AssetFlow role.
10. Admin-only Organization Setup menu with three actions.

Acceptance:

- [ ] Fresh install creates all tables with no warnings.
- [ ] A new signup can log in, has no admin menus, and has an employee record.
- [ ] Only Admin sees the promotion buttons; an employee cannot write groups.
- [ ] Department cycle is rejected; deactivated department is not selectable.
- [ ] `assetflow.notification` is scoped to its recipient.
- [ ] Tests: model constraints, role compute, ACL matrix for base models.

## Phase 2 — `assetflow_assets`

**Outcome:** the core asset story, demoable end to end.

Tasks:

1. `assetflow.asset` with lifecycle, tag sequence, search/kanban/form views, chatter.
2. `assetflow.allocation` with partial unique active index.
3. Allocation create/return methods and asset denormalized fields.
4. `assetflow.transfer` with one-pending index and atomic approval.
5. Conflict message naming the current holder and offering the transfer action.
6. Overdue computed field and the daily cron.
7. History tabs on the asset form.

Acceptance:

- [ ] `AF-0001` is generated and immutable.
- [ ] A second active allocation is rejected by the database, not just the UI.
- [ ] Raj's allocation attempt shows "currently held by Priya" and the transfer action.
- [ ] Transfer approval moves history in one transaction; double approval is impossible.
- [ ] Return requires condition + notes and reopens the asset.
- [ ] Overdue allocation appears in the dashboard query and sends one notification per day.
- [ ] Tests: state transitions, conflict, return, transfer, overdue, ACLs.

## Phase 3 — `assetflow_booking`

**Outcome:** time-slot booking with real overlap protection.

Tasks:

1. `assetflow.booking` model, calendar/list/form views.
2. Half-open overlap validation under `lock_for_update()`.
3. Asset `reserved`/`available` sync on ongoing/end/cancel.
4. Cancel and reschedule flows.
5. Reminder cron with idempotent flag.
6. Booking state cron.

Acceptance:

- [ ] 09:00-10:00 then 10:00-11:00 succeeds; 09:30-10:30 fails with a clear conflict message.
- [ ] Two simultaneous requests cannot both succeed (concurrency test with threads or a forced lock).
- [ ] Cancelling frees the slot; rescheduling revalidates.
- [ ] Reminder is sent once, 15 minutes before start.
- [ ] Only bookable assets can be selected.
- [ ] Tests: boundaries, overlaps, cancel, reminders, ACLs.

## Phase 4 — `assetflow_maintenance`

**Outcome:** approval-gated repair workflow.

Tasks:

1. `assetflow.maintenance.request` with statusbar, priority, photo.
2. Approve/reject buttons restricted to manager/admin.
3. `previous_asset_state` capture and restore.
4. Technician assignment and in-progress/resolved transitions.
5. Maintenance history on the asset form.
6. Aging cron for pending requests.

Acceptance:

- [ ] Request stays pending and the asset does not change until approval.
- [ ] Approval flips to Under Maintenance; resolving restores the prior state (or allocated).
- [ ] Rejection requires a reason and does not change the asset.
- [ ] A second open request for the same asset is blocked.
- [ ] Maintenance is blocked while a booking is active, and vice versa.
- [ ] Tests: approval matrix, state restore, duplicate request, ACLs.

## Phase 5 — `assetflow_audit`

**Outcome:** structured audit cycles and discrepancy reporting.

Tasks:

1. `assetflow.audit.cycle` and `assetflow.audit.line`.
2. Start generates lines from scope and snapshots location.
3. Editable line list for assigned auditors only.
4. Close guard: every line decided; lock after close.
5. Missing -> Lost, damaged -> condition damaged.
6. Discrepancy PDF.
7. Audit history on the asset form.

Acceptance:

- [ ] Undecided line blocks close with a list of offending assets.
- [ ] Auditor sees only assigned cycles; manager sees all.
- [ ] Close is atomic and cannot run twice.
- [ ] Missing asset becomes Lost; damaged asset keeps its state but changes condition.
- [ ] Tests: generation scope, close guard, role access, repeated close.

## Phase 6 — `assetflow_reports`

**Outcome:** the screen judges look at after the demo.

Tasks:

1. `assetflow.dashboard.get_kpi_data()` with the nine KPIs.
2. OWL dashboard action with cards, overdue/upcoming lists, quick actions.
3. Graph/pivot views for utilization, maintenance frequency, department summary.
4. Department allocation PDF and audit discrepancy PDF.
5. Booking heatmap (OWL) with pivot fallback.
6. Query-count test for the dashboard.

Acceptance:

- [ ] Counts match the underlying models in a seeded database.
- [ ] Employee vs manager sees rule-filtered numbers (no `sudo` leakage).
- [ ] Dashboard loads in under ~300 ms on the demo database.
- [ ] PDFs render with the Docker image and with a source install that has wkhtmltopdf.
- [ ] `assertQueryCount` guards the KPI query count.

## Phase 7 — Integration and release

Tasks:

1. Demo data fixtures for all roles and the narrative in
   [`../spec/workflows-rules-rbac.md#8-demo-narrative-what-the-judges-must-see`](../spec/workflows-rules-rbac.md#8-demo-narrative-what-the-judges-must-see).
2. One tour for signup -> promote -> allocate -> book -> maintain -> audit.
3. Performance pass: search views, indexes, no N+1 in lists.
4. Security pass with the `odoo-code-review` skill.
5. README quick start verified from a clean clone.
6. Tag `v0.1.0` and record the demo URL/credentials (not in git).

Acceptance:

- [ ] Clean clone + compose + install + demo data reproduces the narrative without manual SQL.
- [ ] All module tests green in one command.
- [ ] No critical findings from the security review.
- [ ] A non-admin user cannot reach admin screens by URL or RPC.

## 2. Suggested parallel split after Phase 2

| Track | Files | Owner |
|-------|-------|-------|
| Booking | `assetflow_booking/**` | flat-orchid |
| Maintenance | `assetflow_maintenance/**` | patient-wallaby |
| Audit | `assetflow_audit/**` | northern-envelope |
| Reports | `assetflow_reports/**` | northern-envelope |
| Audit | `assetflow_audit/**` | northern-envelope (after handoff) |
| Reports | `assetflow_reports/**` | northern-envelope (after handoff) |
| Verification | `docs/instructions/verification.md`, test runs | rotating reviewer |

Only one owner per addon at a time. Handoffs include: branch name, files, tests run, open issues,
and the next concrete task.

## 3. Review gates

Every phase branch gets a review before merge:

1. **Spec check:** models, fields, states, rules match `docs/spec/`.
2. **Security check:** ACL and record rules exist for every model; role tests pass; no `sudo` leaks.
3. **Odoo 19 check:** no `_sql_constraints`, no `<tree>`, explicit `_name`, verified view/action XML.
4. **Tests:** module tests green; concurrency and boundary cases present.
5. **Docs:** any divergence is written down before merge.
6. **Demo:** the phase's acceptance list is demonstrably true.

Findings are numbered, assigned, and tracked in [`../reviews/review-log.md`](../reviews/review-log.md).
A gate does not pass with open high-severity findings.
