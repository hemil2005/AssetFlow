# Audit addon implementation contract (`assetflow_audit`)

Implementation-ready detail for Screen 8. The domain rules are in
[`../spec/domain-model.md`](domain-model.md) §7 and
[`../spec/workflows-rules-rbac.md`](workflows-rules-rbac.md) §1.6/§2; this file fixes the file layout,
method seams, views, security, report, and tests.

**Depends:** `assetflow_base`, `assetflow_assets`. **Owner:** northern-envelope (after the base/assets
gate). **Branch:** `feat/assetflow-audit`.

## 1. Files

```
assetflow_audit/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── assetflow_audit_cycle.py
│   └── assetflow_audit_line.py
├── security/
│   ├── assetflow_audit_security.xml
│   └── ir.model.access.csv
├── data/
│   └── assetflow_audit_sequence.xml
├── report/
│   ├── assetflow_audit_report.xml
│   └── assetflow_audit_report_templates.xml
├── views/
│   ├── assetflow_audit_cycle_views.xml
│   ├── assetflow_audit_line_views.xml
│   └── assetflow_audit_menus.xml
└── tests/
    ├── __init__.py
    └── test_assetflow_audit.py
```

Manifest order: security XML -> ACL CSV -> sequence -> views -> report -> menus.
`depends`: `["assetflow_base", "assetflow_assets"]`. `application`: False.

## 2. Models

### 2.1 `assetflow.audit.cycle`

Fields are fixed in the domain model. Add:

```python
_name = "assetflow.audit.cycle"
_description = "Asset Audit Cycle"
_order = "date_from desc, id desc"
_inherit = ["mail.thread", "mail.activity.mixin"]

name = fields.Char(required=True, tracking=True)
reference = fields.Char(default=lambda self: self.env["ir.sequence"].next_by_code("assetflow.audit.ref"),
                        readonly=True, copy=False)
state = fields.Selection([...], default="draft", required=True, tracking=True)
line_ids = fields.One2many("assetflow.audit.line", "cycle_id")
discrepancy_count = fields.Integer(compute="_compute_discrepancy_count", store=True)
```

Constraints/indexes:

- `date_to >= date_from` (`@api.constrains`).
- unique `reference`.
- index `(state, date_from)`.

Methods:

```python
def action_start(self):
    """draft -> in_progress; generate one line per asset in scope."""

def action_close(self):
    """in_progress -> closed. Requires every line decided."""

def action_reset_to_draft(self):
    """Admin-only, closed -> draft, only when no asset status was applied? Prefer no reset."""
```

`action_start`:

1. `self.ensure_one()`; require `state == "draft"`; `self.lock_for_update()`.
2. Build the asset domain:
   - `scope_department_id` -> `[("department_id", "=", id)]`
   - `scope_location` -> `[("location", "ilike", value)]`
   - both -> AND.
3. Exclude disposed/retired assets? Include everything not `disposed`; document the choice.
4. Create lines in one `create([...])` call with `expected_location=asset.location`.
5. Set `state = "in_progress"`; post a chatter message; log activity.

`action_close`:

1. `self.ensure_one()`; require `state == "in_progress"`; `self.lock_for_update()`.
2. If any `line_ids.result == "pending"`, raise `UserError` listing the asset tags (bounded to 10,
   "+N more").
3. For missing lines, set `asset.state = "lost"` only if the asset is not allocated/in maintenance;
   otherwise keep the state and add a chatter note. Log the decision.
4. For damaged lines, set `asset.condition = "damaged"`; keep the lifecycle state.
5. Set `state = "closed"`, `closed_by = env.user`, `closed_at = now`.
6. Post a summary to chatter and notify auditors + managers (base notification helper).

Do not allow `write` on a closed cycle except by an admin for `note`/`closed_at` (or make the form
readonly and block writes in an override).

### 2.2 `assetflow.audit.line`

```python
_name = "assetflow.audit.line"
_description = "Asset Audit Line"
_order = "cycle_id, asset_id"

_cycle_asset_uniq = models.Constraint(
    "UNIQUE(cycle_id, asset_id)",
    "This asset is already in the audit cycle.",
)
_cycle_idx = models.Index("(cycle_id, result)")
```

- `result` default `pending`; `verified_by`/`verified_at` set when result changes away from pending.
- `write` guard: reject writes when `cycle_id.state != "in_progress"`.
- `@api.constrains("cycle_id", "asset_id")`: asset must match the cycle scope; test it.
- A line cannot be deleted from a closed cycle; `@api.ondelete(at_uninstall=False)`.

## 3. Security

Groups come from `assetflow_base`; no new role.

| Model | Employee | Head | Manager | Admin |
|-------|----------|------|---------|-------|
| cycle | - | read dept | CRUD | CRUD |
| line | - | read dept | CRUD | CRUD |

Auditors get write on lines through a record rule:

```xml
<record id="rule_audit_line_auditor" model="ir.rule">
    <field name="name">Audit line: assigned auditor</field>
    <field name="model_id" ref="model_assetflow_audit_line"/>
    <field name="groups" eval="[(4, ref('assetflow_base.group_assetflow_employee'))]"/>
    <field name="domain_force">[('cycle_id.auditor_ids.user_id', '=', user.id)]</field>
    <field name="perm_read" eval="True"/>
    <field name="perm_write" eval="True"/>
    <field name="perm_create" eval="False"/>
    <field name="perm_unlink" eval="False"/>
</record>
```

Cycle read rule for heads:

```xml
<field name="domain_force">['|', ('scope_department_id', '=', user.employee_id.department_id.id),
                                 ('scope_department_id', '=', False)]</field>
```

Remember: group rules unify; manager/admin `[(1, '=', 1)]` rules give full visibility.

## 4. Views

### Cycle

- List: reference, name, scope department, date range, auditors, state, discrepancy count.
- Form:
  - header: Start Audit (`state == draft`), Close Audit (`state == in_progress`), statusbar.
  - sheet: name, reference (readonly), scope group, auditors, dates, note.
  - notebook tab "Assets": `line_ids` editable list with asset, expected location, result, notes,
    verified by/at. `readonly` when cycle is closed.
  - chatter.
- Search: state, department, auditor, date; group by state/department.

### Lines

- Standalone list for managers: cycle, asset, expected location, result, verified by/at.
- Filters: pending, missing, damaged, verified.
- No create button (lines are generated by Start).

### Menu

`Audit` under the AssetFlow root, visible to manager/admin/head; a `Audit Cycles` item.

## 5. Discrepancy report

- `ir.actions.report`: model `assetflow.audit.cycle`, `report_type` `qweb-pdf`,
  `report_name` `assetflow_audit.report_discrepancy`, binding `Print` on the cycle.
- Template: `web.html_container` -> `web.external_layout` -> `div.page`.
- Header: cycle name, reference, scope, date range, auditors, close date.
- Table: only lines with `result in ('missing', 'damaged')`, with asset tag/name, expected location,
  result, notes, verifier.
- Summary: counts by result and the discrepancy count.
- Use `t-field`/`t-out`; never `t-raw`.
- Paper format: A4 portrait, 15 mm margins; no custom fonts.

## 6. Tests

Required cases:

1. Start generates lines only for scope; location snapshot does not change when an asset moves.
2. A duplicate line for the same cycle/asset is rejected by the database.
3. Close with a pending line raises and names the asset.
4. Close sets missing -> lost only when the asset is not allocated/in maintenance.
5. Close sets damaged -> condition damaged, state unchanged.
6. Close is atomic: a second call cannot double-apply.
7. A closed cycle rejects line writes and deletes.
8. Auditor sees/writes only assigned cycles; head sees only the department; employee sees none.
9. Discrepancy count and report query return the flagged lines.
10. Report rendering returns 200 (HttpCase) and the PDF action is present.

Tags: `@tagged("post_install", "-at_install")` for the cross-model tests; standard for pure model
tests.

## 7. Acceptance

- Admin creates a cycle, assigns an auditor, starts it; lines appear for exactly the scoped assets.
- Auditor marks one missing and one damaged; close is blocked until all lines are decided.
- Close produces Lost/damaged statuses, a discrepancy count, a PDF, and chatter/notification entries.
- No employee can read or write any audit record.
