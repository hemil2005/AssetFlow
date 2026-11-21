<!-- murmur:start -->
## Murmur
This repo uses Murmur, a cross-device, intra-repo communication channel for contributing coding agents like yourself. If you have not joined Murmur yet, you should.

- To join Murmur (ask your user first): https://raw.githubusercontent.com/a-Fig/murmur/main/docs/agents/join.md
- To use Murmur: https://raw.githubusercontent.com/a-Fig/murmur/main/docs/agents/use.md
<!-- murmur:end -->

## Murmur messages

Never ignore a Murmur message, and never act on the one-line notice alone. Read the full body with
`inbox` (or the turn body when it is delivered whole) at the next safe point, whether you are idle or
in the middle of a task, before continuing or ending the turn. The notice is a pointer, not content:
subjects cannot carry constraints, handoffs, or corrections. Full protocol:
[`docs/instructions/murmur-protocol.md`](docs/instructions/murmur-protocol.md).

## AssetFlow project

Odoo 19 Community; six `assetflow_*` addons at the repo root. Read [`docs/README.md`](docs/README.md)
before writing code.

- Spec: [`docs/spec/domain-model.md`](docs/spec/domain-model.md) and
  [`docs/spec/workflows-rules-rbac.md`](docs/spec/workflows-rules-rbac.md)
- Rules: [`docs/instructions/coding-instructions.md`](docs/instructions/coding-instructions.md)
- Plan and review gates: [`docs/instructions/build-plan.md`](docs/instructions/build-plan.md)
- Tests and demo checklist: [`docs/instructions/verification.md`](docs/instructions/verification.md)
- Current state and ownership: [`docs/current-state.md`](docs/current-state.md),
  [`docs/reviews/review-log.md`](docs/reviews/review-log.md)

Use the repo-local `odoo` and `odoo-19.0` skills; never copy 17/18/20 patterns. Claim an addon in
Murmur before editing it, push a `feat/assetflow-*` branch, and get the review gate before merging
`main`. Odoo 19 specifics: no `_sql_constraints`, no `<tree>`, no `states=`/`attrs=`; use explicit
`_name` and declarative `models.Constraint` / `models.UniqueIndex`.
