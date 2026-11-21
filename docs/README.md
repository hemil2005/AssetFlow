# AssetFlow documentation

**Status:** research and planning, 2026-11-21. No application code exists yet.

AssetFlow is the hackathon brief in [`AssetFlow problem statement.pdf`](<../AssetFlow problem statement.pdf>):
an Enterprise Asset & Resource Management System covering departments, asset categories, the
employee directory, the asset lifecycle, allocation and transfer, time-slot booking of shared
resources, maintenance approval, audit cycles, reports, and notifications. It explicitly excludes
purchasing, invoicing, and accounting.

**Stack decision (locked by the team):** Odoo 19 Community, six custom addons prefixed
`assetflow_`. See [ADR-0001](adr/0001-six-addons.md).

## Read these in order

| # | Document | What it answers |
|---|----------|-----------------|
| 1 | [current-state.md](current-state.md) | What exists in the repo and on the machines today, what is missing, open questions |
| 2 | [research/odoo-19-platform.md](research/odoo-19-platform.md) | How Odoo 19 addons, ORM, security, views, actions, tests, and OWL actually work, with verified 19.0 facts |
| 3 | [research/environment-setup.md](research/environment-setup.md) | How to get a running Odoo 19 + PostgreSQL environment (Docker and source routes) |
| 4 | [spec/domain-model.md](spec/domain-model.md) | Every model, field, relationship, constraint, and index, split across the six addons |
| 5 | [spec/workflows-rules-rbac.md](spec/workflows-rules-rbac.md) | State machines, business rules, roles, record rules, screen mapping, KPIs, notifications |
| 6 | [spec/audit-implementation.md](spec/audit-implementation.md) | Implementation contract for the audit addon |
| 7 | [spec/reports-implementation.md](spec/reports-implementation.md) | Implementation contract for the dashboard, pivots, heatmap, and PDFs |
| 8 | [spec/demo-data.md](spec/demo-data.md) | Deterministic demo dataset, expected KPIs, reset routine |
| 9 | [spec/traceability.md](spec/traceability.md) | Every brief requirement mapped to code and proof |
| 10 | [instructions/build-plan.md](instructions/build-plan.md) | Phased build order with acceptance criteria and a suggested parallel split |
| 11 | [instructions/coding-instructions.md](instructions/coding-instructions.md) | The rules an agent or developer must follow when writing the addons |
| 12 | [instructions/verification.md](instructions/verification.md) | Test matrix, commands, and the demo checklist |
| 13 | [instructions/murmur-protocol.md](instructions/murmur-protocol.md) | The team rule for reading and answering Murmur messages |

Decisions are recorded in [`adr/`](adr/): six addons, the employee/auth model, and the concurrency
strategy.

## How to use these docs

- Treat [`spec/`](spec/) as the contract. If implementation needs to differ, change the spec in the
  same commit as the code, not after.
- Treat [`instructions/coding-instructions.md`](instructions/coding-instructions.md) as the review
  checklist. A change that violates it is not done.
- Odoo facts in these docs were checked against the Odoo 19.0 documentation and source on
  2026-11-21. Where the repo-local skills disagree, the verified fact wins; see
  [research/odoo-19-platform.md](research/odoo-19-platform.md#11-corrections-to-the-local-skills).
- Keep `docs/` free of secrets, credentials, and production URLs.

## Ownership (as of 2026-11-21)

| Area | Owner |
|------|-------|
| `docs/**` | northern-envelope (this session) |
| All addon Python/XML/CSV (`assetflow_*`) | flat-orchid (daksh's machine), scaffolding first |
| Audit and Reports modules | flat-orchid until handed off; docs assume a later handoff to northern-envelope |
| Product decisions | Hemil and daksh |

Coordination happens over Murmur. Claim a file set before editing it, and keep status current.
