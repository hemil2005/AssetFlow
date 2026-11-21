from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

ASSET_STATES = [
    ('available', 'Available'),
    ('allocated', 'Allocated'),
    ('reserved', 'Reserved'),
    ('maintenance', 'Under Maintenance'),
    ('lost', 'Lost'),
    ('retired', 'Retired'),
    ('disposed', 'Disposed'),
]

CONDITIONS = [
    ('new', 'New'),
    ('good', 'Good'),
    ('fair', 'Fair'),
    ('poor', 'Poor'),
    ('damaged', 'Damaged'),
]


class AssetflowAsset(models.Model):
    _name = 'assetflow.asset'
    _description = 'Asset'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'asset_tag'

    _asset_tag_uniq = models.Constraint('UNIQUE(asset_tag)', 'An asset with this tag already exists.')
    _serial_uniq = models.UniqueIndex(
        '(serial_no) WHERE serial_no IS NOT NULL', 'This serial number is already registered.',
    )
    _state_idx = models.Index('(state)')
    _bookable_idx = models.Index('(is_bookable)')

    asset_tag = fields.Char(
        string='Asset Tag', required=True, readonly=True, copy=False, index=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('assetflow.asset.tag'),
    )
    name = fields.Char(string='Name', required=True, tracking=True)
    serial_no = fields.Char(string='Serial Number', index=True)
    category_id = fields.Many2one('assetflow.category', string='Category', required=True, ondelete='restrict')
    department_id = fields.Many2one('assetflow.department', string='Owning Department', ondelete='set null')
    location = fields.Char(string='Location')
    acquisition_date = fields.Date(string='Acquisition Date', default=fields.Date.context_today)
    acquisition_cost = fields.Monetary(string='Acquisition Cost', currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', string='Currency', default=lambda self: self.env.company.currency_id,
    )
    condition = fields.Selection(CONDITIONS, string='Condition', default='good', tracking=True)
    state = fields.Selection(ASSET_STATES, string='Lifecycle Status', default='available', required=True, tracking=True)
    is_bookable = fields.Boolean(string='Shared / Bookable', default=False)
    holder_employee_id = fields.Many2one('assetflow.employee', string='Current Holder', ondelete='set null')
    expected_return_date = fields.Date(string='Expected Return Date')
    image_1920 = fields.Image(string='Photo', max_width=1024, max_height=1024)
    active = fields.Boolean(string='Active', default=True)
    allocation_ids = fields.One2many('assetflow.allocation', 'asset_id', string='Allocation History')
    transfer_ids = fields.One2many('assetflow.transfer', 'asset_id', string='Transfer History')
    is_overdue = fields.Boolean(string='Overdue', compute='_compute_is_overdue', search='_search_is_overdue')
    history_count = fields.Integer(string='History Entries', compute='_compute_history_count')
    note = fields.Text(string='Notes')
    transition_reason = fields.Text(string='Reason for Status Change')
    return_condition = fields.Selection(CONDITIONS, string='Return Condition')
    return_notes = fields.Text(string='Return Check-in Notes')
    allocate_employee_id = fields.Many2one('assetflow.employee', string='Allocate To Employee', store=False)
    allocate_department_id = fields.Many2one('assetflow.department', string='Allocate To Department', store=False)
    allocate_expected_return_date = fields.Date(string='New Expected Return Date', store=False)

    @api.depends('holder_employee_id', 'expected_return_date', 'state')
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for asset in self:
            asset.is_overdue = bool(
                asset.state == 'allocated' and asset.expected_return_date and asset.expected_return_date < today
            )

    def _search_is_overdue(self, operator, value):
        today = fields.Date.context_today(self)
        overdue = [('state', '=', 'allocated'), ('expected_return_date', '<', today)]
        not_overdue = [
            '|', ('state', '!=', 'allocated'),
            '|', ('expected_return_date', '=', False), ('expected_return_date', '>=', today),
        ]
        wants_overdue = (operator == '=' and value) or (operator == '!=' and not value)
        return overdue if wants_overdue else not_overdue

    def _compute_history_count(self):
        maintenance_installed = self.env['ir.model'].sudo().search_count([('model', '=', 'assetflow.maintenance.request')])
        for asset in self:
            extra = (
                self.env['assetflow.maintenance.request'].search_count([('asset_id', '=', asset.id)])
                if maintenance_installed else 0
            )
            asset.history_count = len(asset.allocation_ids) + extra

    @api.private
    def _active_allocation(self):
        return self.env['assetflow.allocation'].search([
            ('asset_id', '=', self.id), ('state', '=', 'active'),
        ], limit=1)

    @api.private
    def _require_assigner(self):
        if self.env.user.has_group('assetflow_base.group_assetflow_asset_manager'):
            return
        department = self.env.user.employee_id.department_id
        if not (self.env.user.has_group('assetflow_base.group_assetflow_department_head')
                and department and self.department_id == department):
            raise UserError(_('Only an Asset Manager or the head of this department can do that.'))

    @api.private
    def _require_admin(self):
        if not self.env.user.has_group('assetflow_base.group_assetflow_admin'):
            raise UserError(_('Only an AssetFlow Administrator can perform this action.'))

    @api.private
    def _has_current_booking(self):
        if not self.env['ir.model'].sudo().search_count([('model', '=', 'assetflow.booking')]):
            return False
        now = fields.Datetime.now()
        return bool(self.env['assetflow.booking'].search_count([
            ('asset_id', '=', self.id), ('state', '=', 'ongoing'),
            ('start_datetime', '<=', now), ('end_datetime', '>', now),
        ]))

    @api.private
    def _transition(self, new_state, allowed_from, note=None, admin_only=False, require_note=False):
        self.ensure_one()
        if admin_only:
            self._require_admin()
        else:
            self._require_assigner()
        if self.state not in allowed_from:
            raise UserError(_(
                'Cannot move %s from %s to %s.', self.asset_tag, self.state, new_state,
            ))
        if require_note and not note:
            raise UserError(_('A reason is required for this transition.'))
        self.write({'state': new_state})
        self.env['assetflow.activity.log']._log_activity(
            'update', self, _('Asset %s moved to %s', self.asset_tag, new_state),
        )

    def action_allocate(self, employee=None, department=None, expected_return_date=None):
        self.ensure_one()
        self._require_assigner()
        self.lock_for_update()
        if self.state != 'available':
            raise ValidationError(_('Only an available asset can be allocated.'))
        if self._active_allocation():
            raise ValidationError(_('Asset %s already has an active allocation.', self.asset_tag))
        if self._has_current_booking():
            raise ValidationError(_('Asset %s is booked right now.', self.asset_tag))
        if not employee and not department:
            raise ValidationError(_('Select an employee or a department to allocate to.'))
        self.env['assetflow.allocation'].create({
            'asset_id': self.id,
            'employee_id': employee.id if employee else False,
            'department_id': department.id if department else False,
            'expected_return_date': expected_return_date,
        })
        self.env['assetflow.activity.log']._log_activity(
            'allocate', self, _('Asset %s allocated', self.asset_tag),
        )

    def action_return(self, condition=None, notes=None):
        self.ensure_one()
        self._require_assigner()
        condition = condition or self.return_condition
        notes = notes or self.return_notes
        if not condition or not notes:
            raise UserError(_('A return condition and check-in notes are required.'))
        allocation = self._active_allocation()
        if not allocation:
            raise UserError(_('Asset %s is not currently allocated.', self.asset_tag))
        self.lock_for_update()
        allocation.with_context(allow_state_write=True).write({
            'state': 'returned',
            'return_datetime': fields.Datetime.now(),
            'checkin_condition': condition,
            'checkin_notes': notes,
        })
        self.write({
            'state': 'available', 'holder_employee_id': False, 'expected_return_date': False,
        })
        self.env['assetflow.activity.log']._log_activity(
            'return', self, _('Asset %s returned', self.asset_tag),
        )

    def action_allocate_from_form(self):
        for asset in self:
            asset.action_allocate(
                employee=asset.allocate_employee_id,
                department=asset.allocate_department_id,
                expected_return_date=asset.allocate_expected_return_date,
            )

    def action_open_transfer(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Transfer Request',
            'res_model': 'assetflow.transfer',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_asset_id': self.id},
        }

    def action_reserve(self):
        """Public workflow method used by booking; no UI permission of its own."""
        for asset in self:
            if asset.state == 'available':
                asset.write({'state': 'reserved'})

    def action_release(self):
        """Public workflow method used by booking; no UI permission of its own."""
        for asset in self:
            if asset.state == 'reserved':
                asset.write({'state': 'available'})

    def action_set_maintenance(self, reason=None):
        self._transition('maintenance', ['available', 'allocated', 'reserved'],
                         note=reason or self.transition_reason, require_note=True)

    def action_mark_lost(self, reason=None):
        self._transition('lost', ['available', 'allocated', 'reserved', 'maintenance'],
                         note=reason or self.transition_reason, admin_only=True, require_note=True)

    def action_retire(self, reason=None):
        self._transition('retired', ['available', 'reserved', 'maintenance', 'lost'],
                         note=reason or self.transition_reason, admin_only=True, require_note=True)

    def action_dispose(self, reason=None):
        self._transition('disposed', ['available', 'reserved', 'maintenance', 'lost', 'retired'],
                         note=reason or self.transition_reason, admin_only=True, require_note=True)

    def action_archive(self):
        self._require_admin()
        self.write({'active': False})

    @api.ondelete(at_uninstall=False)
    def _unlink_if_no_history(self):
        for asset in self:
            if asset.allocation_ids or asset.transfer_ids or asset.state != 'available' or not asset.active:
                raise UserError(_(
                    'Archive %s instead of deleting it: historical records must be preserved.',
                    asset.asset_tag,
                ))
