# Integration review: all six addons

- **Date:** 2026-11-21
- **Candidate:** `feat/assetflow-reports` @ `2346d84`
- **Composition:** `gate/booking-fix` @ `9054b46` (base `a06fdb9` + `fix/assetflow-gate` @ `376d90f`), maintenance `2602828`, audit `d364dfe`, reports `2346d84`.
- **Verdict:** **green locally; awaiting independent verification of `9054b46`/`2346d84` before merge to `main`.**

## Evidence

Fresh database `af_reports2`, Odoo 19.0, PostgreSQL 16, Docker `odoo:19.0`:

```
odoo -d af_reports2 \
  -i assetflow_base,assetflow_assets,assetflow_booking,assetflow_maintenance,assetflow_audit,assetflow_reports \
  --without-demo --no-http --http-port=8079 --stop-after-init

odoo -d af_reports2 \
  -u assetflow_base,assetflow_assets,assetflow_booking,assetflow_maintenance,assetflow_audit,assetflow_reports \
  --test-enable \
  --test-tags /assetflow_base,/assetflow_assets,/assetflow_booking,/assetflow_maintenance,/assetflow_audit,/assetflow_reports \
  --no-http --http-port=8079 --stop-after-init
```

Result: install clean; **62 tests, 0 failed, 0 errors**:

| Addon | Tests |
|-------|-------|
| base | 12 |
| assets | 16 |
| booking | 13 |
| maintenance | 18 |
| audit | 10 |
| reports | 7 |

The department PDF test renders the report and finds the seeded asset tag. The dashboard tests exercise manager vs employee KPI scoping.

## Fixes folded in

- `376d90f` — active-allocation edit now syncs the asset holder/date unconditionally; optional-model checks use `self.env.registry.models` instead of `ir.model`, fixing the integration `KeyError` when assets tests load before booking/maintenance.
- `2602828` — maintenance approval checks the live booking before the `reserved` state; the booking-conflict test now uses a bookable asset.
- `d364dfe` — audit addon: cycles/lines, auditor asset visibility, close locks, discrepancy PDF, 10 tests.
- `2346d84` — reports addon: nine KPI dashboard, OWL action, graph/pivot views, department PDF, 7 tests.

## Remaining risks / known gaps

1. **B7 residual:** `allow_state_write` is client-spoofable through RPC. Ordinary form/RPC writes are guarded; a caller deliberately passing the context key can bypass the transition methods. Documented, accepted for the hackathon unless hardened.
2. **Reports heatmap:** Screen 9's booking heatmap is not implemented; booking analysis is a graph/pivot by asset/state. The other reports, KPI dashboard, and department PDF exist.
3. **OWL browser test:** dashboard JS syntax and install are checked; the action has not been clicked in a browser. A smoke tour/click-through is still needed.
4. **Demo data:** no seeded demo dataset yet; `docs/spec/demo-data.md` is the plan.
5. **Signup HTTP/tour:** signup is covered by a unit test, not an HTTP browser tour.
6. **Concurrency:** cruising-barbet proved the allocation unique index and the booking row-lock race on the previous SHAs; the final fix branch has the same locking logic.

## Merge condition

Cruising-barbet confirms `9054b46` (base/assets/booking gate) and, if possible, `2346d84` (six-addon install/tests). Then merge `feat/assetflow-reports` to `main`, tag `v0.1.0`, and start the demo-data/polish phase.
