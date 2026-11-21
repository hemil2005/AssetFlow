from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AssetflowAllocation(models.Model):
    _name = 'assetflow.allocation'
    _description = 'Asset Allocation'
    _order = 'allocated_on desc'

    _only_one_active = models.UniqueIndex(
        "(asset_id) WHERE state = 'active'",
        'This asset already has an active allocation.',
    )
    _employee_state_idx = models.Index('(employee_id, state)')
    _expected_return_idx = models.Index('(expected_return_date, state)')

    asset_id = fields.Many2one('assetflow.asset', string='Asset', required=True, ondelete='restrict')
    employee_id = fields.Many2one('hr.employee', string='Employee', ondelete='set null')
    department_id = fields.Many2one('hr.department', string='Department', ondelete='set null')
    allocated_on = fields.Datetime(string='Allocated On', default=fields.Datetime.now, required=True)
    expected_return_date = fields.Date(string='Expected Return Date')
    returned_on = fields.Datetime(string='Returned On')
    return_note = fields.Text(string='Condition Check-in Notes')
    state = fields.Selection(
        [('active', 'Active'), ('returned', 'Returned'), ('transferred', 'Transferred')],
        string='Status', default='active', required=True, index=True,
    )
    is_overdue = fields.Boolean(
        string='Overdue', compute='_compute_is_overdue', search='_search_is_overdue',
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

    @api.constrains('state', 'asset_id')
    def _check_single_active_allocation(self):
        for allocation in self.filtered(lambda record: record.state == 'active'):
            other = self.search([
                ('asset_id', '=', allocation.asset_id.id),
                ('state', '=', 'active'),
                ('id', '!=', allocation.id),
            ], limit=1)
            if other:
                raise ValidationError(_(
                    'Asset %s is already allocated. Use a transfer request instead.',
                    allocation.asset_id.tag,
                ))
