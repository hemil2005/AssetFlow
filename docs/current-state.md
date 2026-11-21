# Current state — 2026-11-21

This is the factual snapshot taken before planning. Re-check it at the start of a session; another
agent may have landed work.

## 1. Repository

| Item | Value |
|------|-------|
| Path | `E:\Mumur\AssetFlow` |
| Remote | `https://github.com/hemil2005/AssetFlow` (public) |
| Branch | `main`, tracking `origin/main` |
| HEAD | `455b7b8 docs: implementation contracts...` |
| Working tree | clean on `main`; addon work is on feature branches |
| Other branches | `feat/assetflow-base` @ `5c831a5`, `feat/assetflow-booking` @ `55025a4` (second review, B8/B10 open) |

Commit history:

```
f4625d3 odoo-skills
7f3c519 PS
5b39c89 Say in AGENTS.md and CLAUDE.md that this repo uses Murmur
e199108 first commit
```

`5b39c89` was pushed by Murmur's `mur init`; `7f3c519` added the problem statement PDF;
`f4625d3` added the Odoo skills.

### Files that exist

| Path | State |
|------|-------|
| `README.md` | project overview, docs links, quick start |
| `AGENTS.md`, `CLAUDE.md` | Murmur + project rules + Murmur-message rule |
| `AssetFlow problem statement.pdf` | 5-page brief (source of requirements) |
| `.opencode/skills/` | 21 skill folders, 127 tracked files, committed in `f4625d3` |
| `docs/` | research, specs, instructions, reviews |
| `.gitignore` | Python bytecode, venvs, env files, Odoo runtime data |
| `assetflow_base`, `assetflow_assets`, `assetflow_booking` | on feature branches, not merged |
| `docker-compose.yml`, `.env.example`, `scripts/test.ps1` | merged in `2440d94` (patient-wallaby) |
| `assetflow_maintenance`, `assetflow_audit`, `assetflow_reports` | **do not exist yet** |
| `requirements.txt`, `.venv/`, CI | **do not exist yet** |

### Skills present (repo-scoped, not global)

`grill-me`, `grill-with-docs`, `improve-codebase-architecture`, `odoo`, `odoo-17.0`, `odoo-18.0`,
`odoo-19.0`, `odoo-20.0`, `odoo-code-review`, `odoo-code-tracer`, `odoo-grill-me`,
`odoo-idea-gates`, `odoo-migration`, `odoo-owl`, `odoo-report-design`, `odoo-report-migration`,
`odoo-test-writer`, `odoo-web-security`, `odoo-web-testing`, `odoo-website`, `zoom-out`.

For this project use **`odoo` + `odoo-19.0`** (and routed skills such as `odoo-code-review`,
`odoo-test-writer`, `odoo-owl`, `odoo-report-design`). Do not consult `odoo-17/18/20` for API
decisions.

Verification that they are repo-only: no copies in `~/.config/opencode/skills` (only `impeccable`
and the three Murmur skills), `~/.claude/skills`, `~/.codex/skills`, `~/.pi/agent/skills`, or
`~/.gemini/config/skills`; `odoo-17.0` exists nowhere else under `C:\Users\hemil`.

## 2. Machines and toolchain

### Hemil's machine (this session, `device-54f4143c`)

| Tool | Status |
|------|--------|
| OS | Windows (`win32`) |
| Git | 2.51.0 |
| Python | 3.12.10 (default) and 3.11 available |
| Node | v22.19.0 |
| Docker CLI | installed (`C:\Program Files\Docker\Docker\resources\bin\docker.exe`) |
| Docker daemon | **not running** at check time (`dockerDesktopLinuxEngine` pipe missing) |
| Odoo source / `odoo-bin` | **not installed** |
| PostgreSQL client (`psql`) | **not installed** |
| Repo `.venv` | **absent** |

### daksh's machine (`device-f7d42339`, OMEGA2099), per flat-orchid

| Tool | Status |
|------|--------|
| `.venv` | CPython 3.11.9 |
| Odoo 19 source | installed editable at `C:\Users\daksh\.local\odoo-19-src` |
| Odoo server | 19.0 verified running |
| Addon code | being scaffolded by flat-orchid (six addons, see below) |

Odoo 19 requirements are Python >= 3.10 and PostgreSQL >= 13 (official 19.0 docs). Both machines
satisfy the Python side.

## 3. Team and coordination

| Identity | Device | Role |
|----------|--------|------|
| Hemil (human) | `device-54f4143c` | product owner |
| dakshshah2099 (human) | `device-f7d42339` | product owner / developer |
| northern-envelope (opencode) | `device-54f4143c/b22fe3` | docs, review gate, later Audit/Reports |
| flat-orchid (opencode) | `device-f7d42339/399ac5` | all addon code; base/assets/booking fixes |
| patient-wallaby (opencode) | `device-54f4143c/c1af5b` | env/verification harness, then Maintenance |
| tasseled-chisel (antigravity) | `device-7db7b502/94abab` | withdrawn (owner offline) |
| pleasing-dumpling (antigravity) | `device-54f4143c/3b2650` | excluded, muted |

Murmur is joined and working in this clone. The remote carries `refs/murmur/*`; see `mur ui`.

### Locked team decisions

- Odoo **19** Community; all development uses the repo-local skills.
- Six addons at repo root with the `assetflow_` prefix (flat-orchid, 2026-11-21):
  `assetflow_base`, `assetflow_assets`, `assetflow_booking`, `assetflow_maintenance`,
  `assetflow_audit`, `assetflow_reports`.
- flat-orchid writes all addon Python/XML/CSV; northern-envelope stays in `docs/` until a named
  handoff.

## 4. What is missing

1. Addon code exists only on `feat/assetflow-base` and `feat/assetflow-booking`; both are **changes
   requested** and not merged. Maintenance, audit, and reports are not started.
2. No running database on Hemil's machine (Docker daemon stopped, no local PostgreSQL); flat-orchid
   runs Odoo 19 on daksh's machine and reports install/tests there.
3. The harness is merged (`docker-compose.yml`, `scripts/test.ps1`), but the real addon install/test
   path has not run yet because the addons are on feature branches.
4. The base security model still exposes HR data and lacks allocation/transfer record rules; see the
   review findings B1-B10.
5. Signup, department management, and role-promotion UI are missing (B4-B6).
6. QR generation, forgot-password behavior, and report export need an explicit decision (see
   `docs/spec/traceability.md`).

## 5. Risks and open questions

| Risk / question | Impact | Proposed handling |
|-----------------|--------|-------------------|
| Local skill claims differ from Odoo 19 source in a few places | wrong API usage | verified facts in `research/odoo-19-platform.md#11-corrections-to-the-local-skills`; always cross-check `$ODOO_SOURCE` |
| HR reuse exposes private employee fields | security/privacy failure | B3: implement custom employee/department or restrict reads to `hr.employee.public` and update ADR-0002 |
| Missing allocation/transfer record rules | every internal user can read/edit transfers | B2: add rules before any merge |
| Double-allocation and booking overlap under concurrency | data corruption, failed demo | DB-level `models.UniqueIndex` for active allocation; `lock_for_update()` before overlap checks |
| Signup must create an Employee with no role, while Odoo signup defaults to portal | broken auth flow | ADR-0002: extend `auth_signup`; test with a real signup tour (B4) |
| Department Head scoping via record rules is easy to over-restrict | empty screens | test ACLs with `new_test_user` for every role |
| Booking "Reserved" asset state can fight maintenance/allocation | inconsistent lifecycle | single-writer transition methods + state tests (B10) |
| PNG/PDF export on Windows needs wkhtmltopdf | missing reports in demo | Docker image includes it; document the source-install fix |
| Timezones in booking overlap | off-by-one-hour bugs | store UTC, compare UTC, display in user tz; test boundaries |
| Six addons multiply manifest/security wiring | slow setup | dependency graph in ADR-0001; install in order; one security CSV per addon |
| No deployment target yet | demo-day risk | Docker Compose locally; decide hosting in Phase 8 |

## 6. Immediate next actions

1. flat-orchid: fix B1-B9 on `feat/assetflow-base`, rebase booking, fix B10/M13, push both.
2. patient-wallaby: push `chore/env-harness`; take maintenance after the base gate.
3. Hemil: start Docker Desktop so the harness and independent test runs can proceed.
4. northern-envelope: re-review both branches on the next push; then implement Audit/Reports from the
   implementation contracts in `docs/spec/`.
5. Resolve the employee/department decision (custom models vs HR public directory) before more code
   depends on it.
