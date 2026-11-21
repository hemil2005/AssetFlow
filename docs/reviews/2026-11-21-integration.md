# Integration review: all six addons

- **Date:** 2026-11-21
- **Candidate:** `feat/assetflow-reports` @ `8824520`
- **Composition:** verified gate `9d5618c` (base `0ed9434`), maintenance `2602828`, audit and reports with review fixes (`dd32a1d`).
- **Verdict:** **green locally (73/73); independent gate and browser re-check pending before merge to `main`.**

## Evidence

Fresh database `af_final`, Odoo 19.0, PostgreSQL 16, Docker `odoo:19.0`:

```
odoo -d af_final \
  -i assetflow_base,assetflow_assets,assetflow_booking,assetflow_maintenance,assetflow_audit,assetflow_reports \
  --test-enable \
  --test-tags /assetflow_base,/assetflow_assets,/assetflow_booking,/assetflow_maintenance,/assetflow_audit,/assetflow_reports \
  --without-demo --no-http --http-port=8079 --stop-after-init
```

Result: install clean; **73 tests, 0 failed, 0 errors**:

| Addon | Tests |
|-------|-------|
| base | 12 |
| assets | 16 |
| booking | 13 |
| maintenance | 18 |
| audit | 16 |
| reports | 12 |

Independent evidence before the last two fixes:

- `9d5618c`: gate probe 11 PASS / 0 FAIL, 33/33 base+assets+booking tests.
- `2346d84`: six addons, 62/62 tests, shared harness 7/7.
- `8d9d108`: six addons, 72/72 tests; audit state/snapshot/line probes and heatmap/KPI probes 10 PASS / 0 FAIL.

## Fixes folded in

- `376d90f` / `9d5618c` — active-allocation edits sync the asset holder/date; optional-model checks use `self.env.registry.models`, fixing the load-order `KeyError`.
- `2602828` — maintenance approval checks a live booking before the `reserved` state.
- `dd32a1d` — audit review fixes A1-A11 and reports review fixes R1-R8:
  - audit: guarded cycle state, immutable scope/snapshot, no mid-audit lines, cycle lock on line writes, single base-owned sequence, discrepancy notifications, role-gated menu with an auditor-only "My Audits", locked lost transition, ondelete guard, escaped location scope;
  - reports: exact KPI keys, `get_recent_activity`, deduped `maintenance_today`, OWL booking heatmap, pivot fallback, near-retirement list/filter, capped PDF rows, query-count test.
- `8824520` — dashboard no longer uses the non-existent Odoo 19 `user` service (server-side `can_manage_assets`); Audits menu group set is replaced on upgrade; KPI union de-duplication.

## Browser evidence

Live stack, admin and a real employee user:

- admin: nine KPI cards, overdue/upcoming/notifications, 7x24 heatmap with the seeded cell, Register Asset visible, console clean;
- employee: Register Asset hidden, heatmap rule-filtered to the employee's own booking, Audits menu absent, My Audits present, console clean.

This caught two issues that server tests cannot see: the `useService("user")` crash and the stale menu group on upgraded databases. Both are fixed and covered by a menu regression test.

## Remaining risks / known gaps

1. **B7 residual:** `allow_state_write` is client-spoofable through RPC. Ordinary form/RPC writes are guarded; a caller deliberately passing the context key can bypass transitions. Documented, accepted for the hackathon.
2. **Demo data:** seed script exists on `feat/assetflow-demo` (`3cb0933`); its Odoo 19 password handling needs `new_password` and a proven login before merge.
3. **Signup HTTP/tour:** signup is covered by a unit test, not an HTTP browser tour.
4. **Concurrency:** allocation unique index and booking row locks were independently proven on the gate SHA; the final branch keeps the same locking code.
5. **Dashboard ACL:** the transient dashboard has read-only ACL for `base.group_user` and no record rule; its queries run through the underlying models' record rules (verified by employee-scoped KPIs and heatmap).

## Merge condition

Cruising-barbet confirms `8824520` (73-test suite + the three deltas), patient-wallaby repeats the browser click on `8824520`, and the demo branch passes a login test. Then merge `feat/assetflow-reports` to `main`, tag `v0.1.0`, merge the demo branch, and run the demo narrative.
