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

The full setup is in [`docs/research/environment-setup.md`](docs/research/environment-setup.md).
Docker route:

```powershell
docker compose up -d
# open http://localhost:8069, create database "assetflow", install the addons in order
```

Source route and Windows notes are in the same document.

## Contributing

This repo uses **Murmur** for coordination between agents on different machines. Join instructions
are in [`AGENTS.md`](AGENTS.md). Claim an addon before editing it, follow the coding instructions, and
push a branch for review before merging to `main`.

Murmur messages must be read in full, never from the one-line notice: see
[`docs/instructions/murmur-protocol.md`](docs/instructions/murmur-protocol.md).
