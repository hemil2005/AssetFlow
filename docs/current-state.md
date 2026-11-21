# Current state — 2026-11-21

This is the factual snapshot taken before planning. Re-check it at the start of a session; another
agent may have landed work.

## 1. Repository

| Item | Value |
|------|-------|
| Path | `E:\Mumur\AssetFlow` |
| Remote | `https://github.com/hemil2005/AssetFlow` (public) |
| Branch | `main`, tracking `origin/main` |
| HEAD | `f4625d3 odoo-skills` (dakshshah2099, 2026-11-21) |
| Working tree | clean, no uncommitted changes |
| Other branches | none local or remote |

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
| `README.md` | one line: `# AssetFlow` |
| `AGENTS.md`, `CLAUDE.md` | Murmur section only |
| `AssetFlow problem statement.pdf` | 5-page brief (source of requirements) |
| `.opencode/skills/` | 21 skill folders, 127 tracked files, committed in `f4625d3` |
| `docs/` | this documentation set (new) |
| `docker-compose.yml`, `addons/`, `assetflow_*/` | **do not exist yet** |
| `requirements.txt`, `.venv/`, `*.cfg`, tests, CI | **do not exist yet** |

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
| northern-envelope (opencode) | `device-54f4143c/b22fe3` | docs, verification, later Audit/Reports |
| flat-orchid (opencode) | `device-f7d42339/399ac5` | addon scaffold and all addon code for now |

Murmur is joined and working in this clone. The remote carries `refs/murmur/*`; see `mur ui`.

### Locked team decisions

- Odoo **19** Community; all development uses the repo-local skills.
- Six addons at repo root with the `assetflow_` prefix (flat-orchid, 2026-11-21):
  `assetflow_base`, `assetflow_assets`, `assetflow_booking`, `assetflow_maintenance`,
  `assetflow_audit`, `assetflow_reports`.
- flat-orchid writes all addon Python/XML/CSV; northern-envelope stays in `docs/` until a named
  handoff.

## 4. What is missing

1. No addon code yet: no `__manifest__.py`, models, views, security, tests.
2. No running database on Hemil's machine (Docker daemon stopped, no local PostgreSQL).
3. No `docker-compose.yml`, no seeded demo data, no fixtures.
4. No README quick start, no CI, no deployment target.
5. No confirmed module name per addon beyond the prefix and the six listed responsibilities.
6. No decision yet on QR generation, PDF export hosting, or multi-company support.

## 5. Risks and open questions

| Risk / question | Impact | Proposed handling |
|-----------------|--------|-------------------|
| Local skill claims differ from Odoo 19 source in a few places | wrong API usage | verified facts in `research/odoo-19-platform.md#11-corrections-to-the-local-skills`; always cross-check `$ODOO_SOURCE` |
| Double-allocation and booking overlap under concurrency | data corruption, failed demo | DB-level `models.UniqueIndex` for active allocation; `lock_for_update()` before overlap checks |
| Signup must create an Employee with no role, while Odoo signup defaults to portal | broken auth flow | ADR-0002: extend `auth_signup`; test with a real signup tour |
| Department Head scoping via record rules is easy to over-restrict | empty screens | test ACLs with `new_test_user` for every role |
| Booking "Reserved" asset state can fight maintenance/allocation | inconsistent lifecycle | single-writer transition methods + state tests |
| PDF/report export on Windows needs wkhtmltopdf | missing reports in demo | Docker image includes it; document the source-install fix |
| Timezones in booking overlap | off-by-one-hour bugs | store UTC, compare UTC, display in user tz; test boundaries |
| Six addons multiply manifest/security wiring | slow setup | dependency graph in ADR-0001; install in order; one security CSV per addon |
| No deployment target yet | demo-day risk | Docker Compose locally; decide hosting in Phase 8 |

## 6. Immediate next actions

1. flat-orchid: land `assetflow_base` manifest, groups, category, department, employee, sequence.
2. Hemil: start Docker Desktop (or install PostgreSQL) so a database can be created locally.
3. Both: agree the exact module technical names and the addon folder paths.
4. northern-envelope: hand the docs to flat-orchid for a consistency pass once the base models land.
