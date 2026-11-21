# Odoo 19 platform research

Everything here is for **Odoo 19.0 Community**. Facts marked **verified** were checked on
2026-11-21 against the official 19.0 documentation or the `odoo/odoo` `19.0` source, not only
against the repo-local skills. Source links are at the end.

## 1. What Odoo is, in one page

Odoo is a Python server plus a PostgreSQL database plus a set of addons. There is no separate
"Odoo library" you import into an arbitrary app: you run the Odoo server, and your product is one or
more addons that the server loads.

```
browser  ->  Odoo 19 server (Python, ORM, controllers, cron, QWeb)
                    |
                    +-- addons-path: core addons + assetflow_base + assetflow_assets + ...
                    |
                    +-- PostgreSQL 13+ (one database per deployment)
```

Runtime requirements (**verified** in the 19.0 source-install docs):

- Python **3.10 or later**
- PostgreSQL **13 or later**
- `wkhtmltopdf` 0.12.6 for PDF reports
- Node.js + `rtlcss` only if right-to-left languages or asset tooling need it

The official Docker image `odoo:19.0` is live (**verified** on Docker Hub, pushed 2026-11-20), so a
Docker route is available in addition to a source install.

## 2. Addon anatomy

Odoo 19 still uses the classic addon layout. A minimal addon is:

```
assetflow_base/
├── __init__.py                 # from . import models, controllers, wizard
├── __manifest__.py
├── models/
│   ├── __init__.py             # one import per module file
│   ├── department.py
│   └── employee.py
├── security/
│   ├── assetflow_security.xml  # groups/privileges, record rules
│   └── ir.model.access.csv     # ACLs
├── views/
│   ├── department_views.xml
│   └── menus.xml
├── data/
│   └── assetflow_sequence.xml
├── wizard/
├── controllers/
├── static/
│   └── src/{js,xml,scss}/
├── tests/
│   ├── __init__.py
│   └── test_department.py
└── i18n/
```

A manifest lists real dependencies and data files in load-safe order:

```python
{
    "name": "AssetFlow Base",
    "version": "19.0.1.0.0",
    "category": "Operations/Asset Management",
    "summary": "Departments, categories, employees, roles, sequences",
    "license": "LGPL-3",
    "depends": ["base", "mail", "auth_signup"],
    "data": [
        "security/assetflow_security.xml",
        "security/ir.model.access.csv",
        "data/assetflow_sequence.xml",
        "views/department_views.xml",
        "views/employee_views.xml",
        "views/menus.xml",
    ],
    "application": True,
    "installable": True,
}
```

Load order that avoids failures:

1. module category / privilege / groups and record rules,
2. `ir.model.access.csv`,
3. sequences and other master data,
4. views,
5. actions and menus.

## 3. Odoo 19 ORM facts that change how we write code

### 3.1 `_name` can be derived, but write it explicitly

In Odoo 19 the metaclass derives `_name` from the class name and logs a warning
(**verified** in `odoo/orm/models.py`):

```python
if not attrs.get('_name'):
    attrs['_name'] = re.sub(r"(?<=[^_])([A-Z])", r".\1", name).lower()
    _logger.warning("Class %s has no _name, please make it explicit: _name = %r", name, attrs['_name'])
```

Team rule: always write `_name`. The convenience is not worth the warning noise, and explicit names
survive renames.

```python
from odoo import fields, models

class AssetflowDepartment(models.Model):
    _name = "assetflow.department"
    _description = "AssetFlow Department"
    _parent_store = True

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    parent_id = fields.Many2one("assetflow.department", ondelete="restrict")
    parent_path = fields.Char(index=True)
    active = fields.Boolean(default=True)
```

### 3.2 Declarative constraints and indexes replace `_sql_constraints`

`_sql_constraints` is gone from the 19.0 ORM reference. Odoo 19 declares database objects as model
attributes (**verified** in the ORM reference and `odoo/orm/table_objects.py`):

```python
class AssetflowAllocation(models.Model):
    _name = "assetflow.allocation"

    _name_uniq = models.Constraint(
        "UNIQUE (asset_id, employee_id, start_datetime)",
        "This allocation already exists.",
    )
    _only_one_active = models.UniqueIndex(
        "(asset_id) WHERE state = 'active'",
        "This asset already has an active allocation.",
    )
    _employee_idx = models.Index("(employee_id, state)")
```

`models.Index` and `models.UniqueIndex` both accept a full SQL index definition, including a
`WHERE` clause. This is the clean way to enforce "one active allocation per asset" without a manual
`init()`.

### 3.3 Domains and recordsets

- Domains are lists of tuples; prefix `'|'`, `'&'`, `'!'` for logic.
- `odoo.fields.Domain` (Odoo 19) supports `&`, `|`, `~` and is safer than concatenating
  user-supplied domains.
- Use `search`, `search_count`, `search_read`, `search_fetch`; batch instead of looping searches.
- Read/write through recordsets; never build SQL with string concatenation. If SQL is genuinely
  needed, use `odoo.tools.SQL` and parameters, and `env.cr.execute(...)`.

### 3.4 Concurrency primitives

Odoo 19 exposes row locks (**verified** in `odoo/orm/models.py`):

```python
asset.lock_for_update()          # raises LockError if the row cannot be locked
locked = records.try_lock_for_update(limit=1)  # returns the records that were locked
```

Use them inside the transaction that performs a read-check-write sequence (booking overlap,
transfer approval, audit close). Do not call `cr.commit()` in business methods.

### 3.5 Money and dates

- Acquisition cost is stored with `fields.Monetary` + `currency_id` for reports only. It is not
  linked to accounting, per the brief.
- Store datetimes in UTC. Compare and validate in UTC; display in the user's timezone.
- Use `fields.Date.context_today(self)` for date defaults, not `date.today()`.

## 4. Security model

The chain is **module category -> privilege -> group -> user**, then ACLs and record rules.

Odoo 19 replaced `res.groups.category_id` with `privilege_id` on `res.groups`; privileges carry the
category (**verified** in `odoo/addons/base/models/res_groups.py` and
`res_groups_privilege.py`). The published 19.0 security page still documents the old `category_id`
attribute, so trust the source here.

```xml
<record id="module_category_assetflow" model="ir.module.category">
    <field name="name">AssetFlow</field>
</record>

<record id="privilege_assetflow" model="res.groups.privilege">
    <field name="name">AssetFlow</field>
    <field name="category_id" ref="module_category_assetflow"/>
    <field name="sequence">10</field>
</record>

<record id="group_assetflow_employee" model="res.groups">
    <field name="name">Employee</field>
    <field name="privilege_id" ref="privilege_assetflow"/>
    <field name="implied_ids" eval="[(4, ref('base.group_user'))]"/>
</record>

<record id="group_assetflow_department_head" model="res.groups">
    <field name="name">Department Head</field>
    <field name="privilege_id" ref="privilege_assetflow"/>
    <field name="implied_ids" eval="[(4, ref('group_assetflow_employee'))]"/>
</record>
```

ACL file (`security/ir.model.access.csv`):

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_assetflow_department_employee,assetflow.department.employee,model_assetflow_department,group_assetflow_employee,1,0,0,0
access_assetflow_department_admin,assetflow.department.admin,model_assetflow_department,group_assetflow_admin,1,1,1,1
```

Record rules:

- **Global rules** (no groups) intersect with each other and with group rules.
- **Group rules** unify: any matching group rule grants access.
- Therefore: give employees a restricting group rule, and give managers a `[(1, '=', 1)]` group
  rule. Do not add several global rules unless you intend an AND.

```xml
<record id="rule_allocation_employee" model="ir.rule">
    <field name="name">Allocations: own records</field>
    <field name="model_id" ref="model_assetflow_allocation"/>
    <field name="groups" eval="[(4, ref('assetflow_base.group_assetflow_employee'))]"/>
    <field name="domain_force">[('employee_id.user_id', '=', user.id)]</field>
</record>
```

Security habits:

- Every persistent model has ACL entries; a missing entry means "no access", not "default access".
- Use `groups=` on sensitive fields (for example internal notes).
- Mark internal methods `@api.private` (Odoo 19, **verified**); do not rely on the underscore
  convention for RPC safety.
- Use `sudo()` only at an explicit trust boundary, with a comment explaining why.
- Add access tests for every role and every model you expose.

## 5. Views, actions, menus

Odoo 19 uses `<list>` for the table view; `<tree>` is the old tag (**verified**). Form chatter is
`<chatter/>` on models that inherit `mail.thread`.

```xml
<record id="view_assetflow_asset_list" model="ir.ui.view">
    <field name="name">assetflow.asset.list</field>
    <field name="model">assetflow.asset</field>
    <field name="arch" type="xml">
        <list decoration-danger="state == 'lost'" decoration-muted="state == 'disposed'">
            <field name="asset_tag"/>
            <field name="name"/>
            <field name="category_id"/>
            <field name="state" widget="badge"/>
            <field name="holder_employee_id"/>
        </list>
    </field>
</record>

<record id="action_assetflow_asset" model="ir.actions.act_window">
    <field name="name">Assets</field>
    <field name="res_model">assetflow.asset</field>
    <field name="view_mode">list,kanban,form</field>
</record>

<menuitem id="menu_assetflow_assets" name="Assets"
          parent="assetflow_base.menu_assetflow_root"
          action="action_assetflow_asset" sequence="20"/>
```

Available views that matter for AssetFlow: `list`, `form`, `search`, `kanban`, `calendar` (bookings),
`graph` and `pivot` (reports), `activity`. Use standard views for CRUD; reserve OWL for the dashboard
and the booking heatmap.

## 6. Mail, notifications, cron

- Inherit `mail.thread` and `mail.activity.mixin` to get chatter, tracking, and activities.
- `message_post(body=..., partner_ids=...)` posts to chatter; `activity_schedule(...)` creates a
  to-do for a user.
- Scheduled jobs are `ir.cron` records calling a model method. Keep batches bounded and use
  `self.env["ir.cron"]._commit_progress(...)` for long jobs.
- Business notifications that must survive as a visible feed belong in a dedicated
  `assetflow.notification` model (see the spec), with chatter posts for the audit trail.

## 7. OWL (frontend)

Odoo 19's web client is OWL-based. An OWL component needs:

1. a JS class with `static template`,
2. a QWeb template in `static/src/xml/`,
3. registration in an action/widget/registry,
4. asset bundle entries in the manifest (`web.assets_backend`).

```javascript
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class AssetflowDashboard extends Component {
    static template = "assetflow_reports.Dashboard";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.state = useState({ kpi: null, loading: true });
        onWillStart(async () => {
            this.state.kpi = await this.orm.call("assetflow.dashboard", "get_kpi_data", []);
            this.state.loading = false;
        });
    }
}

registry.category("actions").add("assetflow.dashboard", AssetflowDashboard);
```

**Caveat:** the repo's `odoo-19-owl-guide.md` is generic and includes older markers such as
`owl="1"`. Treat it as a starting point, not authority. Before shipping a component, compare with
`$ODOO_SOURCE/addons/web/static/src/` and the 19.0 web framework docs.

## 8. Reports

- QWeb template + `ir.actions.report` with `report_type` `qweb-pdf` or `qweb-html`.
- PDF requires `wkhtmltopdf` 0.12.6 (included in the official Docker image; manual install for a
  Windows source setup).
- Bind reports to a model with `binding_model_id` to get the Print menu.
- Exportable tabular reports can also lean on the standard list export and pivot views, which need
  no extra code.

## 9. Tests

- Python tests: `TransactionCase` per test transaction; `HttpCase` for routes/tours.
- Put tests in `tests/` and import them from `tests/__init__.py`.
- Run with `--test-enable --test-tags /assetflow_base` (or the module under change).
- JS tests in Odoo 19 use Hoot; the skill's JS example still shows QUnit, so verify against the
  installed source before writing JS tests.
- `assertQueryCount` guards against N+1 regressions in dashboards and list views.

## 10. CLI cheat sheet

```bash
# install modules into a database
odoo-bin -d assetflow -i assetflow_base,assetflow_assets --stop-after-init

# update after changing Python/XML
odoo-bin -d assetflow -u assetflow_assets --stop-after-init

# run tests for one module
odoo-bin -d assetflow -u assetflow_assets --test-enable --test-tags /assetflow_assets --stop-after-init

# development server with auto-reload and verbose errors
odoo-bin -d assetflow --dev=all --addons-path=addons,../assetflow
```

Inside Docker, prefix with `docker compose exec odoo odoo ...`; the image's binary is `odoo`.

## 11. Corrections to the local skills

The repo-local skills are useful but not fully accurate for 19.0. Verified corrections:

| Skill claim | Verified 19.0 reality | Action |
|-------------|-----------------------|--------|
| `res.groups.category_id` was removed and replaced by `privilege_id` | `res.groups` has `privilege_id`; `res.groups.privilege` has `category_id`. The 19.0 security docs still show the old attribute (stale page). | Use `privilege_id` on groups and `category_id` on the privilege record. |
| `_name` is optional and derived automatically | It is derived, **but the ORM logs a warning telling you to make it explicit**. | Always write `_name`. |
| Only `models.Constraint` and `models.Index` exist | `models.UniqueIndex` also exists and supports partial `WHERE` definitions. | Use `UniqueIndex` for one-active-allocation. |
| Button visibility examples use `states="draft"` | Odoo 19 view docs use `invisible="state != 'draft'"`; `states`/`attrs` are legacy. | Use `invisible=` expressions (and `column_invisible=` where relevant). |
| Calendar view examples use `date_end` | Odoo 19 calendar attributes are `date_start` / `date_stop` / `date_delay`. | Use `date_stop`. |
| OWL snippets with `owl="1"` and QUnit | Odoo 19 web source and Hoot are the authority; snippets are generic/legacy. | Verify every OWL/JS pattern against `$ODOO_SOURCE`. |
| `_sql_constraints` examples elsewhere | Not supported in 19; use declarative `models.Constraint`. | Never write `_sql_constraints`. |

Anything not verified above should be checked in `$ODOO_SOURCE` before use. The installed source on
daksh's machine is the fastest oracle.

## 12. References

- Source install and requirements: <https://www.odoo.com/documentation/19.0/administration/on_premise/source.html>
- ORM reference: <https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html>
- Security reference: <https://www.odoo.com/documentation/19.0/developer/reference/backend/security.html>
- View architectures: <https://www.odoo.com/documentation/19.0/developer/reference/user_interface/view_architectures.html>
- Actions: <https://www.odoo.com/documentation/19.0/developer/reference/backend/actions.html>
- Testing: <https://www.odoo.com/documentation/19.0/developer/reference/backend/testing.html>
- 19.0 source: <https://github.com/odoo/odoo/tree/19.0>
- Docker image tags: <https://hub.docker.com/_/odoo>
