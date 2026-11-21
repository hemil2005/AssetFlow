# AssetFlow

Enterprise Asset & Resource Management System for the hackathon brief
[`AssetFlow problem statement.pdf`](<AssetFlow problem statement.pdf>).

AssetFlow tracks departments, categories, employees, physical assets, allocations and transfers,
time-slot bookings of shared resources, maintenance approvals, audit cycles, reports, and
notifications. Purchasing, invoicing, and accounting are explicitly out of scope.

## Stack

- **Odoo 19 Community** (Python 3.10+, PostgreSQL 13+)
- Six custom addons: `assetflow_base`, `assetflow_assets`, `assetflow_booking`,
  `assetflow_maintenance`, `assetflow_audit`, `assetflow_reports`

## Status

Research and planning are complete; the addons are being scaffolded. Nothing in this repo is
production-ready yet.

## Documentation

Start at [`docs/README.md`](docs/README.md). The short version:

- [`docs/current-state.md`](docs/current-state.md) — what exists today
- [`docs/spec/domain-model.md`](docs/spec/domain-model.md) — models and data ownership
- [`docs/spec/workflows-rules-rbac.md`](docs/spec/workflows-rules-rbac.md) — states, rules, roles, screens
- [`docs/instructions/build-plan.md`](docs/instructions/build-plan.md) — phased plan and review gates
- [`docs/instructions/coding-instructions.md`](docs/instructions/coding-instructions.md) — rules for contributors
- [`docs/instructions/verification.md`](docs/instructions/verification.md) — tests and demo checklist

## Local development

Docker route (recommended on Windows). Start Docker Desktop and wait for "Engine running", then:

```powershell
Copy-Item .env.example .env   # set POSTGRES_PASSWORD; .env is git-ignored
docker compose up -d          # Odoo 19 Community + PostgreSQL 16
```

Open <http://localhost:8069>, create the database `assetflow` with demo data **off**, then install
the addons in dependency order: `assetflow_base`, `assetflow_assets`, `assetflow_booking`,
`assetflow_maintenance`, `assetflow_audit`, `assetflow_reports`.

`docker-compose.yml` mounts the repo root at `/mnt/extra-addons`, so the addons at the repo root are
picked up directly, and runs Odoo with `--dev=all` so Python and XML reload on change. Manifest
changes and new files still need `docker compose restart odoo`. PostgreSQL and Odoo state live in
named volumes; `docker compose down -v` wipes them.

Install and test from the command line (dependency order, stops at the first failure, logs under
`odoo-data/logs/`):

```powershell
./scripts/test.ps1                        # install all six, then test each
./scripts/test.ps1 -Addon assetflow_base  # one addon
./scripts/test.ps1 -SkipInstall           # tests only
```

If PowerShell refuses to run the script, use
`powershell -ExecutionPolicy Bypass -File scripts/test.ps1`.

The source route, Windows `wkhtmltopdf` notes and troubleshooting are in
[`docs/research/environment-setup.md`](docs/research/environment-setup.md).

## Contributing

This repo uses **Murmur** for coordination between agents on different machines. Join instructions
are in [`AGENTS.md`](AGENTS.md). Claim an addon before editing it, follow the coding instructions, and
push a branch for review before merging to `main`.

Murmur messages must be read in full, never from the one-line notice: see
[`docs/instructions/murmur-protocol.md`](docs/instructions/murmur-protocol.md).
