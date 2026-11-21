"""Walk the seeded AssetFlow demo. Run via `odoo shell` after `seed_demo.py`.

Every step is labelled; a failure raises with the exact step name. No raw SQL.
"""

from odoo import fields
from odoo.exceptions import ValidationError

password = __import__('os').environ.get('ASSETFLOW_DEMO_PASSWORD', 'AssetFlow!2026')

users = {
    login: env['res.users'].search([('login', '=', login)], limit=1)
    for login in ('dev.head', 'priya.employee', 'raj.employee', 'maya.manager')
}
employees = {login: user.employee_id for login, user in users.items()}
assets = {
    tag: env['assetflow.asset'].search([('asset_tag', '=', tag)], limit=1)
    for tag in ('AF-0001', 'AF-0004', 'AF-0005', 'AF-0006', 'AF-0007')
}


def step(label, fn):
    print(f'STEP: {label}')
    try:
        return fn()
    except Exception as exc:
        raise RuntimeError(f'{label} FAILED: {exc}') from exc


def asset(tag):
    record = assets[tag]
    if not record:
        raise RuntimeError(f'Missing seeded asset {tag}; run seed_demo.py first')
    return record


# 1. Transfer: Dev approves Priya's seeded AF-0001 -> Raj request.
def transfer_step():
    transfer = env['assetflow.transfer'].search([
        ('asset_id', '=', asset('AF-0001').id), ('state', '=', 'requested'),
    ], limit=1)
    if not transfer:
        raise RuntimeError('No seeded requested transfer for AF-0001')
    transfer.with_user(users['dev.head']).action_approve()
    assert transfer.state == 'approved', transfer.state
    assert asset('AF-0001').holder_employee_id == employees['raj.employee']
    active = asset('AF-0001')._active_allocation()
    assert active and active.state == 'active'
    assert asset('AF-0001').allocation_ids  # history retained
    assert asset('AF-0001').message_ids  # chatter recorded
    return f'holder={asset("AF-0001").holder_employee_id.name}'


step('transfer approval (Dev, AF-0001 -> Raj)', transfer_step)


# 2. Booking conflict: Raj's overlapping slot refused, adjacent slot accepted.
def booking_step():
    tomorrow = fields.Date.today() + __import__('datetime').timedelta(days=1)
    base = __import__('datetime').datetime.combine(tomorrow, __import__('datetime').time(9, 0))

    def at(minutes):
        from datetime import timedelta
        return fields.Datetime.to_string(base + timedelta(minutes=minutes))

    try:
        # Savepoint: Odoo's constraint check happens after INSERT, so the
        # rejected row must be rolled back before the adjacent booking test.
        with env.cr.savepoint():
            env['assetflow.booking'].with_user(users['raj.employee']).create({
                'asset_id': asset('AF-0004').id,
                'employee_id': employees['raj.employee'].id,
                'start_datetime': at(30),
                'end_datetime': at(90),
            })
        raise RuntimeError('overlapping booking was accepted')
    except ValidationError:
        pass
    booked = env['assetflow.booking'].with_user(users['raj.employee']).create({
        'asset_id': asset('AF-0004').id,
        'employee_id': employees['raj.employee'].id,
        'start_datetime': at(60),
        'end_datetime': at(120),
    })
    assert booked.state == 'upcoming'
    return f'overlap rejected, adjacent booking {booked.id}'


step('booking conflict (AF-0004 09:30 vs 10:00)', booking_step)


# 3. Maintenance: approve, assign, start and resolve the van.
def maintenance_step():
    request = env['assetflow.maintenance.request'].search([
        ('asset_id', '=', asset('AF-0005').id), ('state', '=', 'pending'),
    ], limit=1)
    if not request:
        raise RuntimeError('No seeded pending maintenance request for AF-0005')
    # The seed shows the post-approval visual state for the opening KPI; the
    # approval workflow itself requires a pre-approval asset state.
    asset('AF-0005').with_context(allow_state_write=True).write({'state': 'available'})
    request.with_user(users['maya.manager']).action_approve()
    assert asset('AF-0005').state == 'maintenance', asset('AF-0005').state
    request.with_user(users['maya.manager']).action_assign(technician=employees['priya.employee'])
    request.with_user(users['priya.employee']).action_start()
    request.with_user(users['priya.employee']).action_resolve(notes='Engine warning cleared.')
    assert request.state == 'resolved', request.state
    assert asset('AF-0005').state == 'available', asset('AF-0005').state
    return f'asset restored to {asset("AF-0005").state}'


step('maintenance lifecycle (Maya approve, Priya resolve)', maintenance_step)


# 4. Audit: decide the last line and close the seeded cycle.
def audit_step():
    cycle = env['assetflow.audit.cycle'].search([('state', '=', 'in_progress')], limit=1)
    if not cycle:
        raise RuntimeError('No seeded in-progress audit cycle')
    pending = cycle.line_ids.filtered(lambda line: line.result == 'pending')
    for line in pending:
        line.with_user(users['maya.manager']).action_mark_verified()
    cycle.with_user(users['maya.manager']).action_close()
    assert cycle.state == 'closed', cycle.state
    damaged = cycle.line_ids.filtered(lambda line: line.asset_id.asset_tag == 'AF-0006')
    missing = cycle.line_ids.filtered(lambda line: line.asset_id.asset_tag == 'AF-0007')
    assert damaged.result == 'damaged' and damaged.asset_id.condition == 'damaged'
    assert missing.result == 'missing' and missing.asset_id.state == 'lost'
    assert cycle.discrepancy_count == 2, cycle.discrepancy_count
    return f'closed, discrepancies={cycle.discrepancy_count}'


step('audit close (AF-0006 damaged, AF-0007 lost)', audit_step)


# 5. Final KPI block.
def kpi_step():
    kpis = env['assetflow.dashboard'].sudo().get_kpi_data()
    expected = {
        'assets_available': 5,
        'assets_allocated': 2,
        'active_bookings': 0,
        'pending_transfers': 0,
        'upcoming_returns': 1,
        'overdue_returns': 1,
        'open_maintenance': 0,
    }
    for key, value in expected.items():
        assert kpis[key] == value, f'{key}: expected {value}, got {kpis[key]}'
    print('=== Final AssetFlow demo KPIs ===')
    for key in (*expected, 'maintenance_today', 'unread_notifications'):
        print(f'{key}: {kpis[key]}')
    return 'all final KPI assertions passed'


step('final KPI assertions', kpi_step)
print('=== demo narrative complete ===')
env.cr.commit()
