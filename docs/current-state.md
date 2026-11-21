# Current state — 2026-11-21

This is the factual snapshot taken before planning. Re-check it at the start of a session; another
agent may have landed work.

## 1. Repository

| Item | Value |
|------|-------|
| Path | `E:\Mumur\AssetFlow` |
| Remote | `https://github.com/hemil2005/AssetFlow` (public) |
| Branch | `main`, tracking `origin/main` |
| HEAD | `16d9c68 docs: six-addon integration green (62 tests), gate candidate recorded` |
| Working tree | docs edits in progress on `main`; addon work on feature branches |
| Other branches | verified gate `9d5618c` (base `0ed9434`), `feat/assetflow-maintenance` @ `2602828`, `feat/assetflow-reports` @ `8824520` (six-addon candidate), `feat/assetflow-demo` @ `3cb0933` (password fix pending) |

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
| `assetflow_base`, `assetflow_assets`, `assetflow_booking` | integrated on `feat/assetflow-reports`; gate verified at `9d5618c` |
| `docker-compose.yml`, `.env.example`, `scripts/test.ps1` | merged in `2440d94` (patient-wallaby) |
| `assetflow_maintenance`, `assetflow_audit`, `assetflow_reports` | written and integrated; 73 tests on a fresh DB |
| `scripts/seed_demo.py` | on `feat/assetflow-demo`; password fix pending |
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
| Docker daemon | running; `odoo:19.0` + PostgreSQL 16 stack validated |
| Odoo source / `odoo-bin` | not installed; addon runs use the Docker image |
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
| northern-envelope (opencode) | `device-54f4143c/b22fe3` | docs, review gate, Audit/Reports, integration and browser checks |
| flat-orchid (opencode) | `device-f7d42339/399ac5` | base/assets/booking; demo seed |
| patient-wallaby (opencode) | `device-54f4143c/c1af5b` | env/verification harness, Maintenance, independent review |
| cruising-barbet (opencode) | `device-f7d42339/6de467` | independent gate evidence |
| tasseled-chisel (antigravity) | `device-7db7b502/94abab` | withdrawn (owner offline) |
| pleasing-dumpling (antigravity) | `device-54f4143c/3b2650` | excluded, muted |

Murmur is joined and working in this clone. The remote carries `refs/murmur/*`; see `mur ui`.

### Locked team decisions

- Odoo **19** Community; all development uses the repo-local skills.
- Six addons at repo root with the `assetflow_` prefix (flat-orchid, 2026-11-21):
  `assetflow_base`, `assetflow_assets`, `assetflow_booking`, `assetflow_maintenance`,
  `assetflow_audit`, `assetflow_reports`.
- flat-orchid owns base/assets/booking and the demo seed; northern-envelope owns audit/reports and
  integration; patient-wallaby and cruising-barbet provide independent review/evidence.

## 4. What is missing

1. Final independent confirmation of `8824520` (73 tests + browser re-click) before merge to `main`.
2. Demo seed password handling: `feat/assetflow-demo` must use `new_password` and prove a real login.
3. Signup is covered by a unit test, not yet an HTTP browser tour.
4. QR generation and forgot-password behavior still need a decision (see
   `docs/spec/traceability.md`).
5. No CI/deployment target yet.

## 5. Risks and open questions

| Risk / question | Impact | Proposed handling |
|-----------------|--------|-------------------|
| Local skill claims differ from Odoo 19 source in a few places | wrong API usage | verified facts in `research/odoo-19-platform.md#11-corrections-to-the-local-skills`; always cross-check `$ODOO_SOURCE` |
| `allow_state_write` context is client-spoofable | trusted workflow flag can be bypassed by a deliberate RPC caller | documented residual; ordinary form/RPC writes are guarded |
| Missing allocation/transfer record rules | every internal user can read/edit transfers | fixed on the gate branch |
| Double-allocation and booking overlap under concurrency | data corruption, failed demo | DB-level `models.UniqueIndex` for active allocation; `lock_for_update()` before overlap checks; independently probed |
| Signup must create an Employee with no role, while Odoo signup defaults to portal | broken auth flow | ADR-0002: extend `auth_signup`; still needs a browser tour |
| Department Head scoping via record rules is easy to over-restrict | empty screens | covered by role tests; revisit in the demo |
| Booking "Reserved" asset state can fight maintenance/allocation | inconsistent lifecycle | single-writer transition methods + state tests |
| PNG/PDF export on Windows needs wkhtmltopdf | missing reports in demo | Docker image includes it |
| Timezones in booking overlap | off-by-one-hour bugs | store UTC, compare UTC, display in user tz; boundary tests |
| No deployment target yet | demo-day risk | Docker Compose locally; decide hosting later |

## 6. Immediate next actions

1. patient-wallaby: browser re-click `8824520` (cards, heatmap, admin/employee, console).
2. cruising-barbet: verify `8824520` suite + JS/menu/KPI deltas.
3. flat-orchid: fix `new_password` in the demo seed and prove a login, then push `feat/assetflow-demo`.
4. northern-envelope: merge `feat/assetflow-reports` to `main`, tag `v0.1.0`, merge the demo branch,
   run the narrative and update traceability.
5. Decide the remaining scope gaps (signup tour, QR, deployment) after the demo path is green.
