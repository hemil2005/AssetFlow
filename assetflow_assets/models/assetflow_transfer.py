from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AssetflowTransfer(models.Model):
    _name = 'assetflow.transfer'
    _description = 'Asset Transfer Request'
    _order = 'create_date desc'

    _only_one_pending = models.UniqueIndex(
        "(asset_id) WHERE state = 'requested'",
        'This asset already has a pending transfer request.',
    )
    _asset_state_idx = models.Index('(asset_id, state)')

    asset_id = fields.Many2one('assetflow.asset', string='Asset', required=True, ondelete='restrict')
    from_allocation_id = fields.Many2one('assetflow.allocation', string='Current Allocation')
    from_employee_id = fields.Many2one(
        'hr.employee', string='Currently Held By',
        related='from_allocation_id.employee_id', store=True, readonly=True,
    )
    to_employee_id = fields.Many2one('hr.employee', string='Transfer To Employee')
    to_department_id = fields.Many2one('hr.department', string='Transfer To Department')
    expected_return_date = fields.Date(string='Expected Return Date')
    reason = fields.Text(string='Reason')
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('requested', 'Requested'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('done', 'Completed'),
        ],
        string='Status', default='draft', required=True, index=True,
    )
    requested_by_id = fields.Many2one(
        'res.users', string='Requested By', default=lambda self: self.env.user, readonly=True,
    )
    approved_by_id = fields.Many2one('res.users', string='Approved By', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            asset = self.env['assetflow.asset'].browse(vals.get('asset_id'))
            if asset:
                active = asset._active_allocation()
                vals.setdefault('from_allocation_id', active.id if active else False)
        return super().create(vals_list)

    def action_request(self):
        for transfer in self:
            if transfer.state != 'draft':
                raise UserError(_('Only draft transfers can be requested.'))
            if not transfer.to_employee_id and not transfer.to_department_id:
                raise ValidationError(_('Select a new holder for the transfer.'))
            transfer.state = 'requested'

    def action_approve(self):
        for transfer in self:
            transfer._require_manager()
            if transfer.state != 'requested':
                raise UserError(_('Only requested transfers can be approved.'))
            active = transfer.asset_id._active_allocation()
            if active:
                active.write({'state': 'transferred', 'returned_on': fields.Datetime.now()})
            transfer.asset_id._set_state('available')
            transfer.asset_id.action_allocate(
                employee=transfer.to_employee_id,
                department=transfer.to_department_id,
                expected_return_date=transfer.expected_return_date,
            )
            transfer.write({
                'state': 'approved',
                'approved_by_id': self.env.user.id,
            })

    def action_reject(self):
        for transfer in self:
            transfer._require_manager()
            if transfer.state != 'requested':
                raise UserError(_('Only requested transfers can be rejected.'))
            transfer.state = 'rejected'

    @api.private
    def _require_manager(self):
        if not self.env.user.has_group('assetflow_base.group_assetflow_asset_manager'):
            raise UserError(_('Only an Asset Manager can approve or reject transfers.'))
