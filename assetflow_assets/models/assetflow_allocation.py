from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AssetflowAllocation(models.Model):
    _name = 'assetflow.allocation'
    _description = 'Asset Allocation'
    _order = 'start_datetime desc, id desc'

    _only_one_active = models.UniqueIndex(
        "(asset_id) WHERE state = 'active'", 'This asset already has an active allocation.',
    )
    _employee_state_idx = models.Index('(employee_id, state)')
    _return_idx = models.Index('(expected_return_date, state)')

    asset_id = fields.Many2one('assetflow.asset', string='Asset', required=True, ondelete='restrict')
    employee_id = fields.Many2one('assetflow.employee', string='Employee', ondelete='set null')
    department_id = fields.Many2one('assetflow.department', string='Department', ondelete='set null')
    allocated_by = fields.Many2one('res.users', string='Allocated By', default=lambda self: self.env.user, readonly=True)
    start_datetime = fields.Datetime(string='Allocated At', default=fields.Datetime.now, required=True, readonly=True)
    expected_return_date = fields.Date(string='Expected Return Date')
    return_datetime = fields.Datetime(string='Returned At', readonly=True)
    checkin_condition = fields.Selection(
        [('new', 'New'), ('good', 'Good'), ('fair', 'Fair'), ('poor', 'Poor'), ('damaged', 'Damaged')],
        string='Return Condition',
    )
    checkin_notes = fields.Text(string='Check-in Notes')
    state = fields.Selection(
        [('active', 'Active'), ('returned', 'Returned')],
        string='Status', default='active', required=True, index=True, readonly=True,
    )
    note = fields.Text(string='Notes')
    is_overdue = fields.Boolean(string='Overdue', compute='_compute_is_overdue', search='_search_is_overdue')
    last_overdue_notified_on = fields.Date(
        string='Last Overdue Notice', readonly=True, copy=False,
    )

    @api.depends('state', 'expected_return_date')
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for allocation in self:
            allocation.is_overdue = bool(
                allocation.state == 'active'
                and allocation.expected_return_date
                and allocation.expected_return_date < today
            )

    def _search_is_overdue(self, operator, value):
        today = fields.Date.context_today(self)
        overdue = [('state', '=', 'active'), ('expected_return_date', '<', today)]
        not_overdue = [
            '|', ('state', '!=', 'active'),
            '|', ('expected_return_date', '=', False), ('expected_return_date', '>=', today),
        ]
        wants_overdue = (operator == '=' and value) or (operator == '!=' and not value)
        return overdue if wants_overdue else not_overdue

    @api.model
    def _cron_flag_overdue_allocations(self):
        """Notify the holder, department head and managers once per day.

        Idempotent per allocation per day: an existing notification for the same
        allocation/user/type created today suppresses a second one. The asset
        chatter gets one entry when the allocation is first flagged.
        """
        today = fields.Date.context_today(self)
        day_start = fields.Datetime.to_datetime(today)
        day_end = day_start + timedelta(days=1)
        overdue = self.search([
            ('state', '=', 'active'),
            ('expected_return_date', '<', today),
        ])
        managers = (
            self.env.ref('assetflow_base.group_assetflow_asset_manager').user_ids
            | self.env.ref('assetflow_base.group_assetflow_admin').user_ids
        )
        notification_model = self.env['assetflow.notification']

        for allocation in overdue:
            if allocation.last_overdue_notified_on == today:
                continue
            recipients = managers | allocation.employee_id.user_id
            if allocation.department_id.head_id:
                recipients |= allocation.department_id.head_id.user_id

            title = _('Overdue return: %(tag)s', tag=allocation.asset_id.asset_tag)
            body = _(
                'Asset %(tag)s was due back on %(date)s and is still held by %(holder)s.',
                tag=allocation.asset_id.asset_tag,
                date=fields.Date.to_string(allocation.expected_return_date),
                holder=allocation.employee_id.name or allocation.department_id.name or _('a department'),
            )
            for user in recipients:
                already_sent = notification_model.search_count([
                    ('user_id', '=', user.id),
                    ('notification_type', '=', 'overdue_return'),
                    ('res_model', '=', self._name),
                    ('res_id', '=', allocation.id),
                    ('create_date', '>=', day_start),
                    ('create_date', '<', day_end),
                ])
                if already_sent:
                    continue
                notification_model._notify(
                    user, title, body,
                    notification_type='overdue_return',
                    res_model=self._name, res_id=allocation.id,
                )

            first_flag = not allocation.last_overdue_notified_on
            allocation.write({'last_overdue_notified_on': today})
            if first_flag:
                allocation.asset_id.message_post(body=body)

        return len(overdue)


    @api.constrains('employee_id', 'department_id')
    def _check_holder(self):
        for allocation in self:
            if not allocation.employee_id and not allocation.department_id:
                raise ValidationError(_('Choose an employee or a department.'))

    @api.model_create_multi
    def create(self, vals_list):
        assets = self.env['assetflow.asset'].browse([
            vals['asset_id'] for vals in vals_list if vals.get('asset_id')
        ])
        assets.lock_for_update()
        for vals in vals_list:
            asset = self.env['assetflow.asset'].browse(vals.get('asset_id'))
            if vals.get('employee_id') and not vals.get('department_id'):
                employee = self.env['assetflow.employee'].browse(vals['employee_id'])
                vals['department_id'] = employee.department_id.id
            if not (vals.get('employee_id') or vals.get('department_id')):
                raise ValidationError(_('Choose an employee or a department.'))
            if asset.state != 'available':
                raise ValidationError(_('Only an available asset can be allocated.'))
            if asset._active_allocation():
                raise ValidationError(_('Asset %s already has an active allocation.', asset.asset_tag))
            if asset._has_current_booking():
                raise ValidationError(_('Asset %s is booked right now.', asset.asset_tag))
        allocations = super().create(vals_list)
        for allocation in allocations:
            allocation.asset_id.with_context(allow_state_write=True).write({
                'state': 'allocated',
                'holder_employee_id': allocation.employee_id.id,
                'expected_return_date': allocation.expected_return_date,
            })
        return allocations

    def write(self, vals):
        if not self.env.context.get('allow_state_write') and {'state', 'asset_id', 'start_datetime'} & set(vals):
            raise UserError(_('Use asset allocation actions to change these fields.'))
        result = super().write(vals)
        if {'employee_id', 'department_id', 'expected_return_date', 'state'} & set(vals):
            for allocation in self.filtered(lambda record: record.state == 'active'):
                allocation.asset_id.with_context(allow_state_write=True).write({
                    'holder_employee_id': allocation.employee_id.id,
                    'expected_return_date': allocation.expected_return_date,
                })
        return result

    def action_return(self):
        for allocation in self:
            allocation.asset_id.action_return(allocation.checkin_condition, allocation.checkin_notes)
