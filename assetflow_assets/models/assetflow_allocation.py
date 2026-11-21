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
