# Second review: base `5c831a5` / booking `55025a4`

- **Date:** 2026-11-21
- **Reviewer:** northern-envelope
- **Targets:** `origin/feat/assetflow-base` @ `5c831a5`, `origin/feat/assetflow-booking` @ `55025a4`
- **Evidence:** cruising-barbet install + 17 tests on `0e1ad9c` (base+assets): 0 failed, 0 errors, exit 0.
  That SHA is superseded by `5c831a5` (rules + bytecode removal), but the install/test path is proven.
- **Verdict:** **changes requested.** B1 is closed; B8/B10 remain open, plus two new behavioral gaps.

## Closed or structurally fixed

| Finding | Status |
|---------|--------|
| B1 bytecode | **closed**: 0 tracked `.pyc` on both branches; `.gitignore` correct |
| B2 record rules | **partial**: rules exist for allocation/transfer; no `base.group_user`; transfer ACL no longer grants write to employees. Behavioral RPC tests and the transfer-create guard are still open |
| B3 `hr.employee` exposure | **closed**: custom `assetflow.employee`/`assetflow.department`; no `hr` reference in base |
| B4 signup | **closed structurally**: `auth_signup` + `_signup_create_user`; test ran green |
| B5 departments | **closed structurally**: model, views, menu |
| B6 role promotion | **closed structurally**: admin-gated buttons/service |
| B7 lifecycle guards | **reopened**: action guards exist, but `assetflow.asset` has no `write()` guard; a manager can RPC-write `state`, `asset_tag`, and a past `expected_return_date` (cruising-barbet probe) |
| B9 return | **closed**: condition + notes required and stored on the allocation |
| M1/M2/M4/M5/M6/M8/M11/M13-M16 | addressed in the diff (field alignment, category code, archive, states, head approvals, chatter, tests) |
| New gap: missing rules for department/category/activity log | **closed** in `5c831a5` |

## Open findings

- **B7 — asset state, tag, and expected return are writable outside the transition methods (H).**
  Confirmed by cruising-barbet's runtime probe on `0e1ad9c`; the asset model is unchanged on
  `5c831a5`.
  - `env['assetflow.asset'].browse(id).with_user(manager).write({'state': 'disposed'})` succeeds:
    `assetflow_assets/models/assetflow_asset.py:51` has no `readonly` and the model has no `write()`
    guard, so only the `action_*` methods enforce B7. Add a write guard (or `readonly=True` plus an
    explicit `allow_state_write` context used by the transition methods) and an RPC-as-manager test.
  - `asset_tag` is `readonly=True` at `:36-38` but writable through RPC: `write({'asset_tag':
    'HACK-9'})` succeeds. Make it immutable in `write()`; test it.
  - `expected_return_date` (`:54`) accepts a past date, while
    `assetflow_allocation._check_dates` rejects one. Add the matching asset constraint and a
    boundary test.
  The action-level checks (dispose from allocated, retire without reason, lost as manager) did pass
  the probe; the bypass is specifically the ORM write path.

- **B10 — immediate reserve is still not implemented (H).**
  `assetflow_booking/models/assetflow_booking.py:39-52` creates the booking and calls
  `_sync_asset_state()`, but `_sync_asset_state()` (`:103-120`) counts only `state='ongoing'`.
  A booking whose window is current is still `upcoming`, so the asset remains `available` until the
  5-minute cron (or a test explicitly calls it). The test at `tests/test_assetflow_booking.py:91-100`
  calls `_cron_sync_states()`; a real demo does not. Result: an allocation can slip into a booked
  window.
  **Fix:** on create/write, treat a non-cancelled booking whose `start <= now < end` as current
  (set it `ongoing` with the context guard, or make `_sync_asset_state()` time-based instead of
  state-based), then reserve under an explicit trusted path.

- **B10 — reminder cron crashes for a booker without a login (H).**
  `:133-151` calls `_notify(booking.employee_id.user_id, ...)`, but `assetflow.employee.user_id` is
  optional. An empty recordset has no `id`, so `_notify` raises. **Fix:** skip the notification or
  route it to the department head/manager when `user_id` is empty; add a test.

- **B8 — allocations to employees are invisible to their department head (H/M).**
  `assetflow_assets/models/assetflow_allocation.py:68-91` does not derive `department_id` from
  `employee_id`, while the head rule (`assetflow_assets/security/assetflow_assets_rules.xml:38-43`)
  matches `department_id`. The allocation shows for the employee but not the head. **Fix:** set
  `department_id = employee_id.department_id` when only the employee is given (single-record and
  batch), and cover it with a head-visibility test.

- **B8 — editing an active allocation leaves the asset stale (H/M).**
  `allocation.write` blocks `state`/`asset_id`/`start_datetime` but allows `employee_id`,
  `department_id`, and `expected_return_date`; the asset's `holder_employee_id` and
  `expected_return_date` are not updated. The dashboard and overdue rule then disagree with the
  allocation. **Fix:** block those edits on an active allocation (use transfer/return), or sync the
  asset in the same transaction; test both.

- **B2/B8 — employees can request a transfer for an asset they do not hold (H/M).**
  `assetflow_assets/models/assetflow_transfer.py:34-47` only snapshots the current holder; it does
  not require the requester to be that holder. A bookable asset is readable by every employee, so an
  employee can request its transfer. **Fix:** require `active.employee_id.user_id == user` or a
  manager/head of the asset department; test as an employee.

- **B2 — employees cannot select a transfer target (M).**
  The employee directory rule is own-record only (`assetflow_base/security/assetflow_base_rules.xml:3-8`),
  so an employee's transfer form cannot see a colleague. Allow read of department colleagues (or a
  safe public directory) without exposing private fields; test the employee transfer flow.

- **M7 — booking rules still use `noupdate="1"` (M).**
  `assetflow_booking/security/assetflow_booking_rules.xml:3`; a rule fix will not apply on `-u`.
  Remove it for code-managed rules.

- **`action_reserve`/`action_release` are public and write asset state (M).**
  `assetflow_assets/models/assetflow_asset.py:209-219` has no permission of its own. Today employees
  usually do not reach the write (the current-booking count is 0), but once immediate reserve is
  fixed the booking flow will write the asset as an employee and hit the read-only asset ACL. Make
  them private and call them through an explicit `sudo()`/service boundary from booking, with a
  comment; add an employee-booking test.

## Runtime evidence

cruising-barbet ran an `odoo-bin shell` probe against `0e1ad9c` (base+assets, throwaway DB, 14 PASS /
3 FAIL):

- **FAIL — B7:** manager RPC write of `state='disposed'`, `asset_tag='HACK-9'`, and a past
  `expected_return_date` all succeed.
- **PASS:** dispose-from-allocated, retire-without-reason, lost-by-manager via actions; allocate a
  maintenance asset; one-pending-transfer unique index; transfer double-approve; return needs
  condition/notes; return reopens; department cycle; notification scoping; activity-log ACL; overdue
  compute; employee direct state write blocked by ACL.
- **Not covered:** booking (needs the rebased branch), department-head scoping, overdue notification
  idempotence, signup over HTTP, disabled-department view domain.
- Non-findings: sequence gaps on a reused DB (expected), and `is_overdue` needed SQL to set a past
  date because both date constraints reject past dates.

## Checks run

- Reviewed every changed file in both branches around the fixes; `python -m compileall` OK; XML
  well-formed: base/assets 15 files, booking 19 files; 0 tracked `.pyc` on both.
- cruising-barbet's install/test evidence on `0e1ad9c`: 17 tests, 0 failed/errors, clean install.
- Not run here: the behavioral RPC matrix and the concurrency force-lock; cruising-barbet is running
  those on `55025a4` and will report per-finding evidence.

## Summary

The security architecture and lifecycle work are now in good shape, and B1/B3-B6/B9 are effectively
closed. The gate is still blocked by the B7 RPC bypass, the booking reserve timing, and the
allocation/transfer integrity gaps above. Fix them with tests, and this should be the last
substantive round before the base/assets/booking gate passes.
