# Coding instructions (Odoo 19)

These rules apply to every `assetflow_*` addon. A change that breaks them is not ready to merge,
even if it "works" in the browser.

## 1. Before writing code

1. Read the relevant spec in [`../spec/`](../spec/): fields, states, rules, and roles.
2. Read the matching Odoo 19 skill: `odoo` for workflow, `odoo-19.0` for API reference, then the routed
   skill (`odoo-code-review`, `odoo-test-writer`, `odoo-owl`, `odoo-report-design`).
3. Detect the target version. It is **19.0**; do not copy patterns from `odoo-17.0`, `odoo-18.0`, or
   `odoo-20.0`.
4. When a skill snippet and the installed source disagree, `$ODOO_SOURCE` wins. On daksh's machine:
   `C:\Users\daksh\.local\odoo-19-src`.
5. Claim the addon/file set in Murmur before editing. Check `who` for an agent already on it.

## 2. Hard rules for Odoo 19

| Never | Always |
|-------|--------|
| `_sql_constraints = [...]` | declarative `models.Constraint(...)` |
| `<tree>` | `<list>` |
| `states="draft"` or `attrs="{...}"` on buttons/fields | `invisible="state != 'draft'"` expressions |
| omit `_name` and rely on derivation | explicit `_name = "assetflow.x"` |
| `self.env.cr.commit()` in business code | let the request transaction commit |
| string-built SQL | ORM, or `odoo.tools.SQL` with parameters |
| `sudo()` to make a screen "work" | ACLs/record rules, or a documented trust boundary |
| directly editing `asset.state` from a view | a transition method with a guard |
| broad XPath rewrites of core views | narrow inheritance on stable anchors |
| deleting records with history | `active = False` / explicit archive action |

Also:

- Use `@api.private` on internal methods callable from RPC paths.
- Use `@api.model_create_multi` for batch-aware `create`.
- Use `@api.ondelete(at_uninstall=False)` for delete guards, not `unlink()` overrides.
- Use `fields.Date.context_today(self)` and UTC datetimes.
- Add `groups=` to sensitive fields.
- Keep methods small; put business rules in model methods, not controllers or onchange-only logic.
- Prefer one clear service-like method (`action_approve`, `action_return`) over logic spread across
  buttons and wizards.

## 3. Model pattern

```python
from odoo import _, api, fields, models

class AssetflowAllocation(models.Model):
    _name = "assetflow.allocation"
    _description = "Asset Allocation"
    _order = "start_datetime desc, id desc"

    asset_id = fields.Many2one("assetflow.asset", required=True, ondelete="restrict", index=True)
    employee_id = fields.Many2one("assetflow.employee", ondelete="restrict", index=True)
    department_id = fields.Many2one("assetflow.department", ondelete="restrict")
    state = fields.Selection(
        [("active", "Active"), ("returned", "Returned")],
        default="active", required=True, index=True,
    )
    is_overdue = fields.Boolean(compute="_compute_is_overdue", search="_search_is_overdue")

    _only_one_active = models.UniqueIndex(
        "(asset_id) WHERE state = 'active'",
        "This asset already has an active allocation.",
    )
    _employee_state_idx = models.Index("(employee_id, state)")

    @api.constrains("employee_id", "department_id")
    def _check_holder(self):
        for rec in self:
            if not rec.employee_id and not rec.department_id:
                raise ValidationError(_("Choose an employee or a department."))
```

State changes go through one guarded method, and every transition logs:

```python
def action_return(self, condition, notes):
    self.ensure_one()
    if self.state != "active":
        raise UserError(_("Only an active allocation can be returned."))
    if not notes:
        raise UserError(_("Check-in notes are required."))
    self.write({
        "state": "returned",
        "return_datetime": fields.Datetime.now(),
        "checkin_condition": condition,
        "checkin_notes": notes,
    })
    self.asset_id._recompute_holder()
    self.env["assetflow.activity.log"]._log(
        action="return", record=self, description=_("Returned by %s", self.employee_id.name),
    )
```

## 4. Concurrency pattern

Read-check-write sequences that can race must lock the contended row:

```python
def _check_overlap_and_lock(self, asset, start, end):
    asset.lock_for_update()  # LockError if another request holds it
    domain = [
        ("asset_id", "=", asset.id),
        ("state", "!=", "cancelled"),
        ("start_datetime", "<", end),
        ("end_datetime", ">", start),
    ]
    if self.search_count(domain):
        raise ValidationError(_("That slot overlaps an existing booking."))
```

- Half-open intervals: `[start, end)`. Equality at the boundary is allowed.
- Do not catch `LockError` and retry silently; show a clear "try again" message or let the user retry.
- Rely on database constraints for hard invariants (unique active allocation, one pending transfer),
  not only Python checks.

## 5. Security pattern

Every persistent model needs:

1. an ACL row per role in `security/ir.model.access.csv`;
2. record rules for row-level scoping;
3. tests proving the matrix.

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_assetflow_asset_employee,assetflow.asset.employee,model_assetflow_asset,group_assetflow_employee,1,0,0,0
access_assetflow_asset_manager,assetflow.asset.manager,model_assetflow_asset,group_assetflow_asset_manager,1,1,1,1
```

Group XML goes before the CSV in the manifest. Prefer group record rules over global rules. Never
add a global rule that could intersect with another global rule and hide everything.

Before merging a security change, answer:

- Which roles can read this model?
- Which roles can create/update/delete?
- What row-level scope applies to employees and department heads?
- Does the UI hide an action that the server would also reject? (Both must be true.)
- Is any `sudo()` justified in a comment and covered by a test?

## 6. Views and XML

- One file per model, plus `menus.xml`. Descriptive XML IDs (`view_assetflow_asset_form`).
- `<list>`, `<form>`, `<search>`, `<kanban>`, `<calendar>`, `<graph>`, `<pivot>`.
- Statusbar in `<header>`; actions with `invisible=` expressions and `groups=` where needed.
- Use `<chatter/>` on business documents that inherit `mail.thread`.
- Search views: filters for state, department, category, overdue, bookable; group-by state/department.
- Translatable strings for all user-facing text.
- Keep inherited views narrow and anchored to stable elements.

## 7. Manifest and data order

```python
"depends": ["assetflow_base", "assetflow_assets"],
"data": [
    "security/assetflow_security.xml",
    "security/ir.model.access.csv",
    "data/assetflow_data.xml",
    "views/asset_views.xml",
    "views/menus.xml",
],
```

Only list real dependencies. Update the manifest when adding a model, view, CSV, data file, asset, or
report. Demo data belongs in `demo/`, never in `data/`.

## 8. Tests

Minimum per addon:

- one test class per business rule group;
- `TransactionCase` for model logic;
- `Form` helper for form-level flows;
- `new_test_user` for each role and an access test per model;
- boundary tests for dates and intervals;
- a concurrency test for allocation/booking where practical;
- `assertQueryCount` for dashboard/list heavy paths.

```python
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

@tagged("post_install", "-at_install")
class TestBookingOverlap(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.asset = cls.env["assetflow.asset"].create({
            "name": "Room B2", "is_bookable": True,
        })

    def test_adjacent_slots_allowed(self):
        self.env["assetflow.booking"].create({
            "asset_id": self.asset.id,
            "start_datetime": "2026-11-21 09:00:00",
            "end_datetime": "2026-11-21 10:00:00",
        })
        booking = self.env["assetflow.booking"].create({
            "asset_id": self.asset.id,
            "start_datetime": "2026-11-21 10:00:00",
            "end_datetime": "2026-11-21 11:00:00",
        })
        self.assertTrue(booking.id)

    def test_overlap_rejected(self):
        self.env["assetflow.booking"].create({
            "asset_id": self.asset.id,
            "start_datetime": "2026-11-21 09:00:00",
            "end_datetime": "2026-11-21 10:00:00",
        })
        with self.assertRaises(ValidationError):
            self.env["assetflow.booking"].create({
                "asset_id": self.asset.id,
                "start_datetime": "2026-11-21 09:30:00",
                "end_datetime": "2026-11-21 10:30:00",
            })
```

## 9. Commands

```powershell
# install
docker compose exec odoo odoo -d assetflow -i assetflow_base --stop-after-init

# update one addon
docker compose exec odoo odoo -d assetflow -u assetflow_assets --stop-after-init

# tests
docker compose exec odoo odoo -d assetflow -u assetflow_assets --test-enable --test-tags /assetflow_assets --stop-after-init

# source route
python C:\src\odoo19\odoo-bin --addons-path=C:\src\odoo19\addons,E:\Mumur\AssetFlow -d assetflow --dev=all
```

Never run commands that touch a database or a shared service without saying so first when the
database is not disposable.

## 10. Review checklist

- [ ] `_name` explicit; manifest version/depends/data updated.
- [ ] No `_sql_constraints`, no `<tree>`, no `states=`/`attrs=`.
- [ ] ACL and record rules for every model; role tests included.
- [ ] State transitions guarded and logged; no direct writes from views.
- [ ] Concurrency invariants enforced in the database where possible.
- [ ] Dates in UTC; half-open intervals; timezone-safe display.
- [ ] XML IDs descriptive; views load without warnings.
- [ ] Tests cover happy path, boundary, conflict, and permission cases.
- [ ] Demo narrative still works.
- [ ] Spec and docs updated for any divergence.

## 11. Definition of done

A change is done when:

1. it matches the spec or the spec was updated in the same branch;
2. it installs/upgrades on a clean database;
3. its tests pass, including access tests;
4. the UI flow is reachable with the right role and hidden from the wrong one;
5. no new log warnings or errors;
6. the branch is pushed and the review gate passed;
7. the review log is updated with the result.

## 12. Murmur protocol

The full rule is in [`murmur-protocol.md`](murmur-protocol.md). The minimum:

- Never ignore a Murmur message. Read the full body with `inbox` at the next safe point, whether idle
  or mid-task, before continuing or ending the turn. The one-line notice is a pointer, not content.
- Set `status` to the addon and phase you are on.
- Check `who` before starting an addon; do not edit files another agent claimed.
- Send a short handoff when you finish or stop: branch, files, tests run, open issues, next task.
- Do not message for acknowledgements. Message for overlaps, interfaces, blockers, and handoffs.
- If a teammate's change conflicts with your work, raise it with the file and the rule, not with a
  vague "it's broken".
