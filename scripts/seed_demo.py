"""Deterministic AssetFlow demo seed. Run through `odoo-bin shell` on a fresh DB.

Password comes from ASSETFLOW_DEMO_PASSWORD (default AssetFlow!2026) and is never
committed. All dates are relative to today so the dataset does not age.
"""

import os
from datetime import datetime, time, timedelta

from odoo import fields

password = os.environ.get('ASSETFLOW_DEMO_PASSWORD', 'AssetFlow!2026')
today = fields.Date.today()
tomorrow = today + timedelta(days=1)

groups = {
    name: env.ref(f'assetflow_base.group_assetflow_{name}')
    for name in ('employee', 'department_head', 'asset_manager', 'admin')
}
base_user_group = env.ref('base.group_user')

# --- Organization -----------------------------------------------------------
dept_it = env['assetflow.department'].create({'name': 'IT', 'code': 'IT'})
dept_ops = env['assetflow.department'].create({'name': 'Operations', 'code': 'OPS'})
env['assetflow.department'].create({
    'name': 'Facilities', 'code': 'FAC', 'parent_id': dept_ops.id,
})
categories = {
    code: env['assetflow.category'].create({
        'name': name, 'code': code, 'warranty_months': warranty,
    })
    for code, name, warranty in (
        ('ELEC', 'Electronics', 24),
        ('FURN', 'Furniture', 0),
        ('VEH', 'Vehicles', 0),
        ('ROOM', 'Rooms', 0),
    )
}

# --- Users and employee directory ------------------------------------------
user_specs = (
    ('maya.manager', 'Maya (Asset Manager)', 'maya.manager@assetflow.test', 'asset_manager'),
    ('dev.head', 'Dev (Department Head)', 'dev.head@assetflow.test', 'department_head'),
    ('priya.employee', 'Priya', 'priya.employee@assetflow.test', 'employee'),
    ('raj.employee', 'Raj', 'raj.employee@assetflow.test', 'employee'),
    ('auditor', 'Sam (Auditor)', 'sam.auditor@assetflow.test', 'employee'),
)
users = {}
employees = {}
for login, name, email, role in user_specs:
    user = env['res.users'].create({
        'name': name,
        'login': login,
        'email': email,
        'group_ids': [(6, 0, [base_user_group.id, groups['employee'].id, groups[role].id])],
    })
    # Odoo 19: `password` is a computed field with the hashing inverse
    # `_set_password`; assigning it after create stores a real hash. Passing
    # `new_password` in create vals leaves plaintext and breaks login.
    user.password = password
    users[login] = user
    employees[login] = env['assetflow.employee'].create({
        'name': name,
        'email': email,
        'department_id': dept_it.id,
        'user_id': user.id,
    })
env.ref('base.user_admin').write({'group_ids': [(4, groups['admin'].id)]})
admin = env.ref('base.user_admin')

# --- Assets -----------------------------------------------------------------
asset_specs = (
    ('AF-0001', 'Laptop', 'ELEC', 'available', False),
    ('AF-0002', 'Spare Laptop', 'ELEC', 'available', False),
    ('AF-0003', 'Projector', 'ELEC', 'available', True),
    ('AF-0004', 'Meeting Room B2', 'ROOM', 'available', True),
    ('AF-0005', 'Delivery Van', 'VEH', 'available', False),
    ('AF-0006', 'Office Chair', 'FURN', 'available', False),
    ('AF-0007', 'Old Router', 'ELEC', 'available', False),
    ('AF-0008', 'Reception Sofa', 'FURN', 'available', False),
    ('AF-0009', 'Tablet', 'ELEC', 'available', True),
)
assets = {}
for tag, name, category_code, _state, bookable in asset_specs:
    assets[tag] = env['assetflow.asset'].create({
        'asset_tag': tag,
        'name': name,
        'category_id': categories[category_code].id,
        'department_id': dept_it.id,
        'location': 'HQ',
        'is_bookable': bookable,
    })

# No workflow reaches "maintenance" without an approval decision, and the demo
# starts with the request still pending: seed this initial state explicitly.
assets['AF-0005'].with_context(allow_state_write=True).write({'state': 'maintenance'})
assets['AF-0007'].with_user(admin).action_mark_lost(reason='Lost before demo audit')
assets['AF-0008'].with_user(admin).action_retire(reason='Retired before demo')

# --- Allocations (AF-0009 is intentionally overdue) -------------------------
maya = users['maya.manager']
assets['AF-0001'].with_user(maya).action_allocate(
    employee=employees['priya.employee'],
    expected_return_date=today + timedelta(days=5),
)
assets['AF-0009'].with_user(maya).action_allocate(
    employee=employees['priya.employee'],
    expected_return_date=today - timedelta(days=1),
)

# --- Bookings (future slots: state stays upcoming) --------------------------
def slot(hour):
    return fields.Datetime.to_string(datetime.combine(tomorrow, time(hour, 0)))

for tag, employee_login, hour in (
    ('AF-0004', 'priya.employee', 9),
    ('AF-0003', 'dev.head', 10),
):
    env['assetflow.booking'].with_user(maya).create({
        'asset_id': assets[tag].id,
        'employee_id': employees[employee_login].id,
        'start_datetime': slot(hour),
        'end_datetime': slot(hour + 1),
        'purpose': 'Demo booking',
    })

# --- Maintenance (pending; approve during the demo) -------------------------
env['assetflow.maintenance.request'].with_user(maya).create({
    'name': 'Delivery van engine warning',
    'asset_id': assets['AF-0005'].id,
    'raised_by_id': employees['priya.employee'].id,
    'description': 'Dashboard warning light; inspect before the next delivery.',
    'priority': 'high',
})

# --- Transfer request (Priya -> Raj; Dev approves during the demo) ----------
env['assetflow.transfer'].with_user(users['priya.employee']).create({
    'asset_id': assets['AF-0001'].id,
    'to_employee_id': employees['raj.employee'].id,
    'expected_return_date': today + timedelta(days=5),
    'reason': 'Raj needs the laptop for a client visit.',
})

# --- Audit cycle in progress (one line deliberately left pending) -----------
cycle = env['assetflow.audit.cycle'].with_user(maya).create({
    'name': 'Q4 IT asset audit',
    'scope_department_id': dept_it.id,
    'date_from': today,
    'date_to': tomorrow,
    'auditor_ids': [(6, 0, [employees['auditor'].id])],
})
cycle.with_user(maya).action_start()
line_by_tag = {line.asset_id.asset_tag: line for line in cycle.line_ids}
line_by_tag['AF-0006'].with_user(maya).action_mark_damaged()
line_by_tag['AF-0007'].with_user(maya).action_mark_missing()
for tag, line in line_by_tag.items():
    if tag not in ('AF-0006', 'AF-0007', 'AF-0002'):
        line.with_user(maya).action_mark_verified()

# --- KPI assertions ---------------------------------------------------------
kpis = env['assetflow.dashboard'].sudo().get_kpi_data()
expected = {
    'assets_available': 4,
    'assets_allocated': 2,
    'maintenance_today': 1,
    'active_bookings': 0,
    'pending_transfers': 1,
    'upcoming_returns': 1,
    'overdue_returns': 1,
    'open_maintenance': 1,
}
for key, value in expected.items():
    assert kpis[key] == value, f'{key}: expected {value}, got {kpis[key]}'

# Prove the demo accounts can actually log in. The KPI block alone is not enough.
auth_info = env['res.users'].authenticate(
    {'type': 'password', 'login': 'maya.manager', 'password': password}, {'interactive': True},
)
assert auth_info.get('uid') == users['maya.manager'].id, f'login failed: {auth_info}'
print(f'maya.manager login: OK (uid={auth_info["uid"]})')

print('=== AssetFlow demo KPIs ===')
for key in (*expected, 'unread_notifications'):
    print(f'{key}: {kpis[key]}')
print('=== demo seed complete ===')

# `odoo shell` rolls back on exit; the seed must persist explicitly.
env.cr.commit()
