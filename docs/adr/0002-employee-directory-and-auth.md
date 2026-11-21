# ADR-0002: Employee directory and role assignment

- **Status:** accepted, 2026-11-21
- **Deciders:** daksh, flat-orchid, northern-envelope

## Context

The brief requires:

- signup creates an **Employee account only**, with no role selection;
- an Admin creates or promotes Department Heads and Asset Managers from the Employee Directory;
- employees have name, email, department, role, and active status;
- Department Heads see and approve within their department;
- roles must not be self-assigned or elevated at signup.

Odoo already has `res.users` (login, groups), `hr.employee` (HR record), and `res.partner`. Using
`hr.employee` would drag in HR, leave, contracts, and payroll-shaped assumptions the brief explicitly
does not need. Storing "role" as a plain Selection on a custom record would make authorization
advisory rather than enforceable.

## Decision

1. Use a custom `assetflow.employee` model for the directory: name, email, phone, department, job
   title, active, and a nullable `user_id` link to `res.users`.
2. Authorization uses **Odoo groups**, not a selection field:
   - `group_assetflow_employee` implies `base.group_user`;
   - `group_assetflow_department_head` implies employee;
   - `group_assetflow_asset_manager` implies employee;
   - `group_assetflow_admin` implies asset manager.
   The `role` field on the employee is a **computed display** derived from `user_id.groups_id`.
3. The only place roles are assigned is the Employee Directory form, through admin-only buttons that
   add/remove the groups on the linked user. The buttons are hidden for non-admins and the write is
   rejected server-side.
4. Signup is implemented by extending `auth_signup` (dependency in `assetflow_base`):
   - a new signup creates a `res.users` with `base.group_user` (internal, not portal),
   - creates the matching `assetflow.employee`,
   - assigns **no** AssetFlow group.
   The exact hook is verified against `$ODOO_SOURCE/addons/auth_signup/` before implementation.
5. `assetflow_base` adds `res.users.employee_id` so record rules can express
   `user.employee_id.department_id` without joining through email or partner.
6. An AssetFlow Admin is an application role and does **not** imply `base.group_system`. System
   settings stay with the Odoo administrator account.

## Consequences

**Positive**

- Authorization is enforced by ACLs and record rules, not by UI or a string field.
- No HR/payroll dependency and no HR data model to explain in the demo.
- Signup meets the "no self-elevation" requirement by construction.
- Department scoping is simple and testable.

**Negative**

- Two records per person (user + employee) must be linked and kept consistent; `user_id` is nullable
  for employees who never log in.
- Signup override is authentication-sensitive and needs a real signup test (HTTP/tour), not only a
  unit test.
- Deleting users/employees requires care: deactivate, never delete, because history references them.
- The computed role can be stale in a cached form until reload; it is display-only, so authorization
  never relies on it.

## Alternatives considered

1. **Use `hr.employee`.** Rejected: unnecessary dependency and scope; the brief is not HR.
2. **Use `res.partner` as the employee directory.** Rejected: partners mix customers/vendors with
   staff and have no department/job semantics by default.
3. **A `role` Selection field as the source of truth.** Rejected: not enforceable by Odoo security;
   every rule would need custom checks.
4. **Admin creates all users manually, no signup.** Rejected: the brief explicitly requires signup.
5. **Signup creates a portal user and an admin upgrades it.** Rejected: the brief says signup creates
   an Employee account; a portal account cannot use the backend and adds a confusing intermediate
   state.

## Verification

- Signup tour: sign up, log in, no AssetFlow menus, employee row exists, no AssetFlow groups.
- Access tests: employee cannot write `groups_id`; admin promotes/demotes; department head scope.
- A promoted Department Head can approve a department transfer and cannot approve another
  department's transfer.
