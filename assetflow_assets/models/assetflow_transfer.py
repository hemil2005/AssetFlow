from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

TRANSFER_STATES = [
    ('requested', 'Requested'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
    ('cancelled', 'Cancelled'),
]


class AssetflowTransfer(models.Model):
    _name = 'assetflow.transfer'
    _description = 'Asset Transfer Request'
    _order = 'create_date desc'

    _only_one_pending = models.UniqueIndex(
        "(asset_id) WHERE state = 'requested'", 'This asset already has a pending transfer.',
    )
    _asset_state_idx = models.Index('(asset_id, state)')

    asset_id = fields.Many2one('assetflow.asset', string='Asset', required=True, ondelete='restrict')
    from_employee_id = fields.Many2one('assetflow.employee', string='Currently Held By', readonly=True)
    to_employee_id = fields.Many2one('assetflow.employee', string='Transfer To Employee')
    to_department_id = fields.Many2one('assetflow.department', string='Transfer To Department')
    expected_return_date = fields.Date(string='Expected Return Date')
    reason = fields.Text(string='Reason')
    requested_by = fields.Many2one('res.users', string='Requested By', default=lambda self: self.env.user, readonly=True)
    state = fields.Selection(TRANSFER_STATES, string='Status', default='requested', required=True, index=True, readonly=True)
    decided_by = fields.Many2one('res.users', string='Decided By', readonly=True)
    decided_at = fields.Datetime(string='Decided At', readonly=True)
    decision_note = fields.Text(string='Decision Note', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        user = self.env.user
        for vals in vals_list:
            asset = self.env['assetflow.asset'].browse(vals.get('asset_id'))
            if not asset:
                continue
            active = asset._active_allocation()
            vals.setdefault('from_employee_id', active.employee_id.id if active else False)
            is_privileged = user.has_group('assetflow_base.group_assetflow_asset_manager') or (
                user.has_group('assetflow_base.group_assetflow_department_head')
                and user.employee_id.department_id
                and asset.department_id == user.employee_id.department_id
            )
            if not is_privileged and not (active and active.employee_id.user_id == user):
                raise UserError(_('Only the current holder or an Asset Manager can transfer this asset.'))
        transfers = super().create(vals_list)
        for transfer in transfers:
            transfer._notify_requested()
        return transfers

    @api.private
    def _notify_users(self, users, title, body):
        for user in users:
            self.env['assetflow.notification']._notify_once(
                user, title, body, 'transfer', self._name, self.id,
            )

    @api.private
    def _notify_requested(self):
        self.ensure_one()
        heads = self.env.ref('assetflow_base.group_assetflow_department_head').sudo().user_ids
        heads = heads.filtered(
            lambda user: user.employee_id.department_id == self.asset_id.department_id
        )
        managers = self.env.ref('assetflow_base.group_assetflow_asset_manager').sudo().user_ids
        self._notify_users(
            heads | managers,
            _('Transfer requested: %s', self.asset_id.asset_tag),
            _('A transfer of %s was requested by %s.', self.asset_id.asset_tag, self.requested_by.name),
        )

    @api.private
    def _notify_decision(self, decision):
        self.ensure_one()
        users = self.requested_by
        for employee in (self.from_employee_id, self.to_employee_id):
            if employee and employee.user_id:
                users |= employee.user_id
        self._notify_users(
            users,
            _('Transfer %s: %s', decision, self.asset_id.asset_tag),
            _('The transfer of %s was %s.', self.asset_id.asset_tag, decision),
        )

    @api.constrains('to_employee_id', 'to_department_id')
    def _check_target(self):
        for transfer in self:
            if not transfer.to_employee_id and not transfer.to_department_id:
                raise ValidationError(_('Select a new holder for the transfer.'))

    @api.private
    def _require_decider(self):
        for transfer in self:
            user = self.env.user
            if user.has_group('assetflow_base.group_assetflow_asset_manager'):
                continue
            department = user.employee_id.department_id
            if not (user.has_group('assetflow_base.group_assetflow_department_head')
                    and department and transfer.asset_id.department_id == department):
                raise UserError(_('Only an Asset Manager or the head of this department can decide.'))

    def write(self, vals):
        if not self.env.context.get('allow_state_write') and 'state' in vals:
            raise UserError(_('Use the transfer actions to change its status.'))
        return super().write(vals)

    def action_approve(self):
        for transfer in self:
            transfer._require_decider()
            asset = transfer.asset_id
            asset.lock_for_update()
            transfer.invalidate_recordset(['state'])
            if transfer.state != 'requested':
                raise UserError(_('Only a requested transfer can be approved.'))
            active = asset._active_allocation()
            if not active:
                raise UserError(_('Asset %s has no active allocation to transfer.', asset.asset_tag))
            active.with_context(allow_state_write=True).write({
                'state': 'returned', 'return_datetime': fields.Datetime.now(),
            })
            asset.with_context(allow_state_write=True).write({
                'state': 'available', 'holder_employee_id': False, 'expected_return_date': False,
            })
            asset.action_allocate(
                employee=transfer.to_employee_id,
                department=transfer.to_department_id,
                expected_return_date=transfer.expected_return_date,
            )
            transfer.with_context(allow_state_write=True).write({
                'state': 'approved',
                'decided_by': self.env.user.id,
                'decided_at': fields.Datetime.now(),
                'decision_note': transfer.decision_note,
            })
            self.env['assetflow.activity.log']._log_activity(
                'transfer_approve', transfer, _('Transfer of %s approved', asset.asset_tag),
            )
            transfer._notify_decision(_('approved'))

    def action_reject(self, reason=None):
        for transfer in self:
            transfer._require_decider()
            if transfer.state != 'requested':
                raise UserError(_('Only a requested transfer can be rejected.'))
            reason = reason or transfer.decision_note
            if not reason:
                raise UserError(_('A rejection reason is required.'))
            transfer.with_context(allow_state_write=True).write({
                'state': 'rejected',
                'decided_by': self.env.user.id,
                'decided_at': fields.Datetime.now(),
                'decision_note': reason,
            })
            transfer._notify_decision(_('rejected'))

    def action_cancel(self):
        for transfer in self:
            if transfer.state != 'requested':
                raise UserError(_('Only a requested transfer can be cancelled.'))
            if transfer.requested_by != self.env.user and not self.env.user.has_group(
                'assetflow_base.group_assetflow_asset_manager'
            ):
                raise UserError(_('Only the requester or an Asset Manager can cancel this transfer.'))
            transfer.with_context(allow_state_write=True).write({'state': 'cancelled'})
