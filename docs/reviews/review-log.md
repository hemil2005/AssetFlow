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
| `assetflow_base` scaffold | flat-orchid | in progress, nothing pushed | unknown | blocked: no branch |
| `assetflow_assets` | flat-orchid | not started | — | — |
| `assetflow_booking` | unassigned | not started | — | — |
| `assetflow_maintenance` | unassigned | not started | — | — |
| `assetflow_audit` | northern-envelope (proposed) | not started | — | — |
| `assetflow_reports` | northern-envelope (proposed) | not started | — | — |
| Environment / Docker | Hemil | blocked: Docker daemon stopped | — | — |
| Verification harness | unassigned | not started | — | — |

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

_No code review yet: no addon branch has been pushed. The first gate opens when flat-orchid pushes
`assetflow_base`._

| ID | Severity | Area | Finding | Owner | State |
|----|----------|------|---------|-------|-------|
| —  | —        | —    | —       | —     | —     |

## Delegation requests

| To | Task | Why | Due |
|----|------|-----|-----|
| flat-orchid | push the WIP `assetflow_base` branch, even incomplete | review cannot start against an unpushed tree | first checkpoint |
| flat-orchid | confirm six-addon paths and technical model names against the spec | docs must match reality | with the first push |
| pleasing-dumpling | take `assetflow_maintenance` after the base lands, or own the Docker/verification harness | parallel work, clear file set | after base gate |
| tasseled-chisel | take `assetflow_booking` after the base lands | independent addon, clear file set | after base gate |
| Hemil | start Docker Desktop and create the `assetflow` database | unblocks local verification | before Phase 2 review |

Delegation is only effective when the assignee accepts; the Murmur thread is the record of
acceptance.

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
