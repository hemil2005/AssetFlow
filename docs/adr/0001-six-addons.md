# ADR-0001: Six addons with an `assetflow_` prefix

- **Status:** accepted, 2026-11-21
- **Deciders:** daksh, flat-orchid, northern-envelope
- **Supersedes:** the earlier single-addon `assetflow` assumption in the first drafts of these docs

## Context

The brief covers five fairly separate subdomains: master data, assets and allocation, booking,
maintenance, and audit, plus reporting. A hackathon team can work in parallel, but only if the code
boundaries are explicit. Odoo addons are the natural module boundary: each has its own manifest,
security CSV, tests, and install/lifecycle.

A single addon would be simpler to install, but every agent would edit the same `__manifest__.py`,
the same security CSV, and the same `models/__init__.py`, which is a collision magnet. It would also
make it impossible to accept one subdomain without accepting all of them.

## Decision

Build six addons at the repo root, all prefixed `assetflow_`:

| Addon | Responsibility |
|-------|----------------|
| `assetflow_base` | privilege/groups, department, category, employee, sequences, notifications, activity log, `res.users.employee_id`, signup |
| `assetflow_assets` | asset, allocation, transfer |
| `assetflow_booking` | booking of shared/bookable assets |
| `assetflow_maintenance` | maintenance requests and approval workflow |
| `assetflow_audit` | audit cycles and lines |
| `assetflow_reports` | dashboard KPI action, pivots, PDFs, heatmap |

Dependencies are one-directional:

```
base <- assets <- booking
             <- maintenance
             <- audit
base + all of the above <- reports
```

Rules:

- `assetflow_base` never depends on another `assetflow_*` addon.
- Security groups live only in base and are referenced by XML ID everywhere else.
- Shared helpers live in base; no cross-addon Python imports.
- Installing `assetflow_reports` may pull everything through `depends`, but each addon must also
  install on its own once its dependencies are met.

## Consequences

**Positive**

- Parallel work with clear file ownership and review gates.
- Security and tests are scoped per subdomain.
- A broken reporting experiment cannot block the core demo.
- Odoo's dependency mechanism enforces load order.

**Negative**

- Six manifests, six ACL files, and six test suites to keep consistent.
- A cross-cutting model change touches several addons and needs coordinated reviews.
- Demo setup must install or update all six in order.
- Duplicate XML IDs across addons are a real risk; prefix every ID with the addon's concern.

## Alternatives considered

1. **Single `assetflow` addon.** Rejected: merge conflicts, one failing import blocks everything, no
   independently demoable slices.
2. **Two addons: core + extras.** Rejected: still one hot file for the booking/maintenance/audit
   work, and reporting would drag everything.
3. **Separate Git repositories per addon.** Rejected: the hackathon has one remote and Murmur
   coordinates a single repo; multi-repo adds release overhead with no benefit.

## Enforcement

- Review gate checks the dependency direction and that no addon imports another's private module.
- `docs/spec/domain-model.md` lists the owning addon of every model.
