# Review: `feat/assetflow-base` + `feat/assetflow-booking`

- **Date:** 2026-11-21
- **Reviewer:** northern-envelope
- **Targets:**
  - `origin/feat/assetflow-base` @ `0b3e05a` (base `25ec332`, assets `0b3e05a`)
  - `origin/feat/assetflow-booking` @ `b04646a` (built on top of the above)
- **Contract:** `docs/spec/domain-model.md`, `docs/spec/workflows-rules-rbac.md`,
  `docs/instructions/coding-instructions.md`, ADR-0001/0002/0003.
- **Verdict:** **changes requested.** The scaffold is a good start and most Odoo 19 API corrections
  are applied, but security and data-integrity gaps block the gate.

## Findings

### Critical / merge blockers

- **B1 — Committed Python bytecode.** `assetflow_base/__pycache__/`, `assetflow_assets/**/__pycache__/`,
  and `assetflow_booking/**/__pycache__/` are tracked (15 files on base/assets, 21 on booking).
  Bytecode is machine-specific, bloats the repo, and can mask stale source. Remove them from the
  branch and add a `.gitignore` covering `__pycache__/`, `*.pyc`, `.venv/`, `.env`, `*.log`.

- **B2 — Allocation and transfer records are effectively unprotected.**
  `assetflow_assets/security/ir.model.access.csv:6-10` grants every `base.group_user` read on all
  allocations and read/write/create on all transfers, and
  `assetflow_assets/security/assetflow_assets_rules.xml` defines record rules **only for assets**.
  Any internal user can list every allocation, edit any transfer, and set `state` directly via RPC
  (bypassing `action_approve`). Add employee/head/manager record rules for both models, remove
  `base.group_user`, and make `state` readonly outside transition methods.

- **B3 — `hr.employee` read is a privacy hole and contradicts ADR-0002.**
  `assetflow_base/security/ir.model.access.csv:5` grants `base.group_user` read on the full
  `hr.employee` model, and `assetflow_base/views/assetflow_menus.xml:3-8` opens the HR employee
  list/form. In Odoo 19 the HR ACL is `hr.group_hr_user`; this override exposes private fields
  (addresses, bank, contracts, notes) to every internal user. Odoo's own public directory is
  `hr.employee.public`. Either implement the spec's `assetflow.employee`/`assetflow.department`
  (preferred, per ADR-0002) or formally change the ADR and use `hr.employee.public` for reads with
  no broad ACL on `hr.employee`. This is also the root cause of B4-B6.

- **B4 — Signup is not implemented.** `assetflow_base/__manifest__.py:15` depends on `base` and `hr`
  only; there is no `auth_signup` override or controller. Odoo's default signup creates a portal
  user with no employee record and no backend access, so the brief's Screen 1 and R2 are unmet.
  Add the signup hook that creates an internal Employee with **no** AssetFlow group; verify with an
  HTTP/tour test, not only a unit test.

- **B5 — Department management is missing.** There is no `assetflow.department` model and no
  Department menu; `assetflow_base/views/assetflow_menus.xml` exposes only Employee Directory and
  Asset Categories. Screen 3A and the department-scoped approvals cannot be demonstrated. Implement
  the model (hierarchy, code, head, active) and the admin tab, or get the team to accept
  `hr.department` and document it.

- **B6 — Role promotion UI is missing.** `assetflow_base/models/hr_employee.py:7-18` only computes
  `assetflow_role`; there are no admin-only promote/revoke buttons, and no service method that
  writes `res.users.group_ids`. Screen 3C and "roles are assigned only here" are unmet.

- **B7 — Asset lifecycle transitions are unguarded.**
  `assetflow_assets/models/assetflow_asset.py:55-60` writes any state; `action_set_maintenance`,
  `action_mark_lost`, `action_retire`, and `action_dispose` (`:110-135`) can run from any state,
  allow manager (not admin) for destructive actions, and require no reason. This breaks the state
  machine, allows disposing an allocated asset, and bypasses the maintenance approval flow. Add a
  transition table and guarded actions, and reserve lost/retire/dispose for Admin with a note.

- **B8 — Allocation/transfer invariants can be bypassed.**
  `assetflow_assets/models/assetflow_allocation.py:17-30` and
  `assetflow_assets/views/assetflow_allocation_views.xml:24-43` allow creating/editing an active
  allocation directly: `state`, `asset_id`, and dates are writable, there is no "employee or
  department" constraint, and the asset is not moved to `allocated`. The asset can therefore show a
  holder while still `available`. Transfer approval (`assetflow_transfer.py:58-75`) also allocates
  an asset that has no active allocation, sets it available first, and never locks it. Move the
  state changes into allocation methods, add the holder constraint, and make transfer approval
  require and lock the current allocation.

- **B9 — Return flow does not meet R5.** `assetflow_assets/models/assetflow_asset.py:96-108` makes
  the note optional and records no check-in condition; `assetflow_allocation.py:22-23` has no
  `checkin_condition` field. Require a condition and notes, and keep them on the allocation.

- **B10 — Booking accepts invalid resources and states.**
  `assetflow_booking/models/assetflow_booking.py:22-25` enforces `is_bookable` only as a UI domain;
  a direct create can book a non-bookable, `lost`, `disposed`, or `maintenance` asset. `state` is
  writable (`:33`), so an employee with write access can set `ongoing`/`completed` and desync the
  asset. The asset is only set `reserved` by the 5-minute cron, so a booking whose window started
  still leaves the asset allocatable (R4), and nothing blocks a booking during an active allocation
  or vice versa. Add model guards for `is_bookable` and asset state, deny direct state writes,
  reserve immediately when the window is current, and implement the booking/allocation and
  booking/maintenance conflicts.

### Major

- **M1 — Field and semantic drift from the spec.** `tag` vs `asset_tag`, `serial_number` vs
  `serial_no`, `warranty_days` vs `warranty_months`, `condition` lacks `damaged`, asset has no
  `expected_return_date`, `acquisition_cost` is a Float without `currency_id`, `category_id` is not
  required, and `serial_number` is not unique when set. These names are consumed by audit, reports,
  and the dashboard; align code to the spec now or update the spec deliberately.
- **M2 — Category identity is incomplete.** `assetflow_base/models/assetflow_category.py:10,24-27`
  makes `name` unique but leaves `code` optional and non-unique; the spec requires a unique code.
- **M3 — No notification or activity log.** Base has neither `assetflow.notification` nor
  `assetflow.activity.log`, so reminders post to asset chatter and there is no Activity Logs screen
  (Screen 10) or R16 audit trail.
- **M4 — Assets can be deleted.** Manager/admin ACLs grant `perm_unlink` and there is no
  `@api.ondelete` guard; the spec says archive, never delete records with history.
- **M5 — Transfer state machine diverges.** `draft`/`done`/`transferred` are used, there is no
  `cancelled`, and rejection has no reason/decision timestamp. See `assetflow_transfer.py:26-35`.
- **M6 — Department Head cannot do the role's job.** `_require_manager` in
  `assetflow_asset.py:62-65` and `assetflow_transfer.py:84-87` only accepts the manager group, and
  the ACLs give heads no write access. Heads cannot approve department transfers or update
  condition/location as specified.
- **M7 — `noupdate="1"` on record rules.** `assetflow_assets/security/assetflow_assets_rules.xml:3`
  and `assetflow_booking/security/assetflow_booking_rules.xml:3` mean a rule fix will not apply on
  `-u`; reviewers will see the old rule. Prefer no `noupdate` for code-managed rules, or document
  the manual cleanup.
- **M8 — Legacy chatter markup.** `assetflow_assets/views/assetflow_asset_views.xml:86-90` uses
  `<div class="oe_chatter">` with the follower/activity/message fields. Odoo 19 documents
  `<chatter/>`; use it to avoid asset/JS drift.
- **M9 — No allocation action or conflict UI on the asset form.**
  `assetflow_asset_views.xml:19-39` has no Allocate button; the only way to allocate is creating an
  Allocation row in the History action. Screen 5's "currently held by Priya / Transfer Request"
  flow is not reachable.
- **M10 — Allocation form exposes lifecycle fields.** `assetflow_allocation_views.xml:24-43` lets a
  manager edit `state`, `asset_id`, `returned_on`, and has no return action or condition field.
- **M11 — Broad `base.group_user` usage.** ACLs/rules for categories, assets, and allocation use
  `base.group_user` instead of `assetflow_base.group_assetflow_employee` (`base` CSV line 4,
  assets CSV lines 4/7/10, assets rules line 8). That includes internal users who never joined
  AssetFlow.
- **M12 — Tests are happy-path only.** Base/assets has 4 tests; booking has 4. Missing: tag
  sequence, direct-SQL double allocation, transfer double approval, unallocated transfer, record
  rule leaks, department-head scope, non-bookable asset, past slot, containment overlap, direct
  state writes, reminder idempotence, and cron transitions. Base tests use bare
  `assertRaises(Exception)` (`test_assetflow_assets.py:58-60`, `test_assetflow_category.py:24-30`).
- **M13 — Booking test uses a naive local `datetime.now()`** (`tests/test_assetflow_booking.py:64-66`)
  while Odoo stores UTC; this is timezone-flaky. Use `fields.Datetime.now()`.
- **M14 — Cross-addon private call.** Booking calls `asset._set_state(...)`
  (`assetflow_booking.py:97,99`), a private method of `assetflow_assets`. Add public
  `action_reserve()` / `action_release()` methods on the asset, or a booking-side service method.
- **M15 — `size` on a Char is deprecated.** `assetflow_category.py:10` uses `size=16`; Odoo 19
  documents it as deprecated. Drop it unless a database-level limit is intentional.
- **M16 — Chatter reminders are not notifications.** `assetflow_booking.py:108-121` posts to the
  asset chatter with no recipient targeting; the brief expects a reminder notification to the
  booker. This is tracked with M3.

### Minor

- `assetflow_asset_views.xml:8-14` has no visual decoration for lost/overdue/disposed.
- Transfer form does not show `requested_by_id`, `approved_by_id`, or a decision note.
- `action_reject` has no reason field; `action_cancel` does not guard `completed` bookings.
- `_search_is_overdue` handles only `=`/`!=`, not `in`/`not in`.
- Category form hides `active` with no archive action.
- Menu root has no `web_icon`; the app is hard to spot in the Apps menu.
- `hr.employee` role values (`manager`, `head`) differ from the spec labels; harmless but align if
  reports expose them.

## Checks run

- Read every Python, XML, and CSV file in both branches, plus the manifests and tests.
- `python -m compileall` on `assetflow_base`, `assetflow_assets`, and `assetflow_booking`: OK.
- XML well-formedness: 9 files base/assets, 4 files booking: OK.
- Tracked bytecode count: 15 (base/assets), 21 (booking branch).
- Verified against Odoo 19 source/docs: `res.users.group_ids`, `<list>`, `<chatter/>`,
  `date_stop`, `ir.cron.ir_actions_server_id`, `ir_actions_server_id` inheritance, partial
  `models.UniqueIndex`, `res.groups.privilege`, `@api.private`, `lock_for_update()`. The branch's
  uses of these are correct.
- Not run: Odoo install, module tests, browser flows, concurrency execution. There is no Odoo
  server/PostgreSQL on this machine and Docker Desktop is not running, so flat-orchid's reported
  "12 tests, 0 failures" is accepted as their evidence, not independently reproduced.

## Residual risks

- HR field exposure depends on `hr.employee` ACLs; any future HR module adds more sensitive fields
  under the same model.
- The booking overlap guarantee relies on the constraint running while the row lock is held; this
  should be proven with a real concurrency test, not only sequential unit tests.
- The reported install used a fresh database; upgrade behaviour (`-u`) with `noupdate="1"` rules and
  the committed bytecode was not exercised.
- No demo data, no signup tour, no dashboard yet, so the end-to-end narrative is unproven.

## Summary

Good early scaffold: Odoo 19 API corrections were applied correctly, the booking overlap logic is
on the right track, and the tests that exist are readable. The branch is not mergeable yet: the
security rules for allocation/transfer and the `hr.employee` ACL are real exposure, and several
brief requirements (signup, departments, role promotion, guarded lifecycle, return condition) are
not implemented. B1-B10 must be fixed before the base/assets/booking gate passes; M1-M6 should be
fixed in the same pass because they affect every later addon.
