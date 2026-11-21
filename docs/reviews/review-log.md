# Review log and delegation board

One row per review gate. Findings are numbered and assigned. A phase does not merge with an open
**high** finding.

Severity:

- **H** — breaks the demo, security, data integrity, or install.
- **M** — diverges from the spec or makes a flow confusing; fix before merge unless explicitly
  deferred.
- **L** — polish, naming, docs, or a follow-up.

## Status board (2026-11-21)

| Workstream | Owner | State | Branch | Review |
|------------|-------|-------|--------|--------|
| Docs: research, spec, plan, instructions, ADRs | northern-envelope | complete, in review by team | local `docs/` | self-checked |
| `assetflow_base` scaffold | flat-orchid | reviewed, changes requested | `feat/assetflow-base` @ `0b3e05a` | B1-B9 open |
| `assetflow_assets` | flat-orchid | reviewed, changes requested | `feat/assetflow-base` @ `0b3e05a` | B1-B10 open |
| `assetflow_booking` | flat-orchid | reviewed, changes requested | `feat/assetflow-booking` @ `b04646a` | B10, M13 open |
| `assetflow_maintenance` | patient-wallaby | queued after env harness + base gate | — | — |
| `assetflow_audit` | northern-envelope (proposed) | not started | — | — |
| `assetflow_reports` | northern-envelope (proposed) | not started | — | — |
| Environment / Docker | patient-wallaby (assigned) | blocked: Docker daemon stopped | `chore/env-harness` | pending |
| Verification harness | patient-wallaby (assigned) | in progress | `chore/env-harness` | pending |

## Review protocol

1. Owner pushes a branch (`feat/<addon>`) with a WIP commit and posts: branch, commit SHA, files,
   commands run, known gaps.
2. Reviewer fetches the branch and checks it against:
   - `docs/spec/domain-model.md`,
   - `docs/spec/workflows-rules-rbac.md`,
   - `docs/instructions/coding-instructions.md`,
   - the Odoo 19 facts in `docs/research/odoo-19-platform.md`.
3. Reviewer posts numbered findings with file/line and the rule violated. No vague feedback.
4. Owner fixes or replies with a reasoned disagreement; the reviewer updates the finding.
5. A gate passes when no H/M findings remain and evidence is attached.

## Finding log

_First review completed 2026-11-21 against `feat/assetflow-base` and `feat/assetflow-booking`:
[`2026-11-21-base-assets-booking.md`](2026-11-21-base-assets-booking.md)._

| ID | Severity | Area | Finding | Owner | State |
|----|----------|------|---------|-------|-------|
| B1 | H | hygiene | committed `__pycache__` / `.pyc` (15 base/assets, 21 booking) | flat-orchid | open |
| B2 | H | security | no allocation/transfer record rules; every internal user can read/edit transfers | flat-orchid | open |
| B3 | H | security | `base.group_user` read on all `hr.employee`; private HR data exposed; ADR-0002 divergence | flat-orchid | open |
| B4 | H | spec | signup missing (`auth_signup` not implemented) | flat-orchid | open |
| B5 | H | spec | department model/screen missing (Screen 3A) | flat-orchid | open |
| B6 | H | spec | role promotion UI missing (Screen 3C, R2) | flat-orchid | open |
| B7 | H | lifecycle | `_set_state` has no transition guards; destructive actions manager-only, no reason | flat-orchid | open |
| B8 | H | integrity | direct allocation create/edit bypasses asset state; transfer allocates unallocated asset | flat-orchid | open |
| B9 | H | spec | return flow has no required condition/notes | flat-orchid | open |
| B10 | H | booking | non-bookable/lost assets bookable; state writable; reserve only via cron; no allocation/maintenance conflict | flat-orchid | open |
| M1-M16 | M | mixed | field drift, category code, notifications/log, unlink, transfer states, head RBAC, noupdate, chatter, allocation UI, tests, TZ test, private call, `size`, reminders | flat-orchid | open |

## Delegation requests

| To | Task | Why | Due |
|----|------|-----|-----|
| flat-orchid | fix B1-B9 on `feat/assetflow-base` and B10/M13 on `feat/assetflow-booking`, then push both | gate is blocked on security and data integrity | next push |
| flat-orchid | reply with any blocker you dispute, with the reason and the spec/ADR you want changed | disagreements are resolved before code, not after | next push |
| flat-orchid | do not start `assetflow_maintenance` until base/assets/booking pass the gate | later addons depend on stable asset/employee models | after gate |
| northern-envelope | re-review both branches within one turn of the next push and update this log | keep the loop short | next push |
| pleasing-dumpling | **withdrawn** — session is out of scope by the repo owner's decision; no files may be written | assignment reclaimed by northern-envelope | — |
| northern-envelope | harness reclaimed from pleasing-dumpling, then handed to patient-wallaby | keep ownership explicit | done |
| patient-wallaby | take the env/verification harness now on `chore/env-harness`; then `assetflow_maintenance` after the base/assets/booking gate | new free session, clear file set, no addon collisions | harness now, maintenance after gate |
| flat-orchid | take `assetflow_booking` after base + assets land | tasseled-chisel's assignment withdrawn (owner offline); keep the code with the active install | after assets gate |
| tasseled-chisel | **withdrawn** — owner offline; session is out of scope, no files may be written | work reassigned to flat-orchid | — |
| Hemil | start Docker Desktop and create the `assetflow` database | unblocks local verification | before Phase 2 review |

Delegation is only effective when the assignee accepts; the Murmur thread is the record of
acceptance.

## Session exclusions

- **pleasing-dumpling** (`device-54f4143c/3b2650`, antigravity on Hemil's machine) — excluded by the
  repo owner on 2026-11-21. Its assignment was withdrawn, its messages are muted, and it must not be
  assigned work or waited on. Murmur has no per-session removal command; closing that agent drops the
  session from `who`.
- **tasseled-chisel** (`device-7db7b502/94abab`, antigravity on dhruviljpatel's machine) — assignment
  withdrawn on 2026-11-21 because its owner is offline. It must not start `assetflow_booking` or write
  files; that work moved to flat-orchid. The session may be offline and will see the withdrawal on its
  next turn.

## Known spec decisions to check in code

These are the places implementation is most likely to drift. Verify each explicitly:

1. Six addons and dependency direction (`base` never imports the others).
2. `assetflow.employee` + `res.users` groups, not `hr.employee` and not a writable role field.
3. Signup creates an internal employee with no role; only Admin promotes.
4. `models.UniqueIndex("(asset_id) WHERE state = 'active'")` for allocations.
5. Booking intervals are half-open and the check runs under `lock_for_update()`.
6. Maintenance stores `previous_asset_state` and restores it on resolve.
7. Audit close is atomic, requires all lines decided, and locks the cycle.
8. No `_sql_constraints`, `<tree>`, `states=`, or `attrs=`.
9. Every model has ACL + record rules + role tests.
10. Dashboard counts respect record rules (no `sudo` leakage).
