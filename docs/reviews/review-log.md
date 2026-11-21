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
| `assetflow_base` scaffold | flat-orchid | gate candidate `9054b46` | `gate/booking-fix` | B8 fixed, awaiting independent confirmation |
| `assetflow_assets` | flat-orchid | gate candidate `9054b46` | `gate/booking-fix` | B8 fixed, awaiting independent confirmation |
| `assetflow_booking` | flat-orchid | gate candidate `9054b46` | `gate/booking-fix` | B10 fixed; B8 fixed |
| `assetflow_maintenance` | patient-wallaby | integrated, 18 tests green | `2602828` | reviewed |
| `assetflow_audit` | northern-envelope | integrated, 10 tests green | `d364dfe` | pending independent review |
| `assetflow_reports` | northern-envelope | integrated, 7 tests green | `2346d84` | pending independent review |
| `assetflow_audit` | northern-envelope (proposed) | not started | — | — |
| `assetflow_reports` | northern-envelope (proposed) | not started | — | — |
| Environment / Docker | patient-wallaby | merged `2440d94` | main | approved |
| Verification harness | patient-wallaby | merged `2440d94` | main | approved |
| Gate verification (independent) | cruising-barbet | evidence on `0f4446d` (9 PASS / 1 FAIL B8); verifying `9054b46`/`2346d84` | temp worktree per SHA | evidence only |

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

_First review: [`2026-11-21-base-assets-booking.md`](2026-11-21-base-assets-booking.md).
Second review: [`2026-11-21-second-review.md`](2026-11-21-second-review.md).
Integration: [`2026-11-21-integration.md`](2026-11-21-integration.md) — six addons, 62 tests green._

| ID | Severity | Area | Finding | Owner | State |
|----|----------|------|---------|-------|-------|
| B1 | H | hygiene | committed `__pycache__` / `.pyc` | flat-orchid | **closed** at `5c831a5` (0 tracked) |
| B2 | H | security | allocation/transfer rules missing; transfer ACL write | flat-orchid | **partial**: rules/ACL fixed; transfer-create guard + behavioral RPC tests open |
| B3 | H | security | `hr.employee` privacy / ADR-0002 | flat-orchid | **closed**: custom employee/department |
| B4 | H | spec | signup missing | flat-orchid | **closed structurally** (test green) |
| B5 | H | spec | department model/screen missing | flat-orchid | **closed structurally** |
| B6 | H | spec | role promotion UI missing | flat-orchid | **closed structurally** |
| B7 | H | lifecycle | unguarded transitions/destructive actions | flat-orchid | **closed**: write guard; residual client-spoofable `allow_state_write` context |
| B8 | H | integrity | allocation edit/department sync; unallocated transfer; employee transfer target | flat-orchid | **fixed** in `376d90f`; independent confirmation pending |
| B9 | H | spec | return condition/notes | flat-orchid | **closed** |
| B10 | H | booking | immediate reserve; reminder crash without login | flat-orchid | **closed** in `0f4446d` |
| M7 | M | security | booking rules `noupdate="1"` | flat-orchid | **closed** |
| M3 | M | UI | notifications/activity log models exist; Screen 10 UI minimal | flat-orchid | deferred with reason |
| M1/M2/M4/M5/M6/M8/M11/M13-M16 | M | mixed | field alignment, category code, archive, transfer states, head approvals, chatter, tests, TZ, private calls | flat-orchid | mostly fixed in the diff; verify in tests |

## Delegation requests

| To | Task | Why | Due |
|----|------|-----|-----|
| flat-orchid | fix the remaining B8/B10 items and M7 on the current branches, then push | gate is blocked on booking timing and allocation/transfer integrity | next push |
| flat-orchid | reply with any blocker you dispute, with the reason and the spec/ADR you want changed | disagreements are resolved before code, not after | next push |
| patient-wallaby | `assetflow_maintenance` is started on `feat/assetflow-maintenance`, based on `5c831a5` | maintenance is unblocked while the base gate closes | next push |
| cruising-barbet | re-run combined evidence on `55025a4` including the targeted employee/booking/allocation/reminder cases | closes the behavioral evidence gap | this push |
| northern-envelope | re-review both branches within one turn of the next push and update this log | keep the loop short | next push |
| pleasing-dumpling | **withdrawn** — session is out of scope by the repo owner's decision; no files may be written | assignment reclaimed by northern-envelope | — |
| northern-envelope | harness reclaimed from pleasing-dumpling, then handed to patient-wallaby | keep ownership explicit | done |
| patient-wallaby | harness approved and merged (`2440d94`); next take `assetflow_maintenance` after the base/assets/booking gate | the harness is done; maintenance is the next unassigned addon | maintenance after gate |
| cruising-barbet | independent gate verification on each pushed SHA: install, tests, B1-B10 mechanical checks, concurrency; report PASS/FAIL, no code edits | has Docker/Postgres/Odoo 19 on daksh's machine; closes the "not run" evidence gap | each push |
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
