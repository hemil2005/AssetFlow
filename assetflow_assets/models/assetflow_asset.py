import base64
import io

import qrcode

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
    qr_code = fields.Binary(string='QR Label', compute='_compute_qr_code', store=False)
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

    @api.depends('asset_tag')
    def _compute_qr_code(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '').rstrip('/')
        for asset in self:
            # With no configured base URL the tag itself is the payload, so the
            # label still carries a meaningful identifier.
            payload = (
                f'{base_url}/web#model=assetflow.asset&id={asset.id}&view_type=form'
                if base_url else asset.asset_tag
            )
            qr = qrcode.QRCode(
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=6,
                border=2,
            )
            qr.add_data(payload)
            qr.make(fit=True)
            image = qr.make_image(fill_color='black', back_color='white')
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            asset.qr_code = base64.b64encode(buffer.getvalue())

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

    @api.depends('allocation_ids')
    def _compute_history_count(self):
        maintenance_installed = 'assetflow.maintenance.request' in self.env.registry.models
        maintenance_counts = {}
        if maintenance_installed and self.ids:
            maintenance_counts = dict(self.env['assetflow.maintenance.request']._read_group(
                [('asset_id', 'in', self.ids)], ['asset_id'], ['__count'],
            ))
        for asset in self:
            extra = maintenance_counts.get(asset, 0) if maintenance_installed else 0
            asset.history_count = len(asset.allocation_ids) + extra

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('state', 'available') != 'available':
                raise UserError(_('A new asset must start in the Available state.'))
            if vals.get('holder_employee_id') or vals.get('expected_return_date'):
                raise UserError(_('Allocate an asset through the allocation workflow.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'asset_tag' in vals:
            raise UserError(_('An asset tag is generated once and cannot be changed.'))
        if not self.env.context.get('allow_state_write') and {
            'state', 'holder_employee_id', 'expected_return_date', 'active',
        } & set(vals):
            raise UserError(_('Use the asset workflow actions to change lifecycle fields.'))
        return super().write(vals)

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
    def _require_returner(self, allocation):
        if self.env.user.has_group('assetflow_base.group_assetflow_asset_manager'):
            return
        employee = self.env.user.employee_id
        if employee and allocation.employee_id == employee:
            return
        department = employee.department_id if employee else False
        if (self.env.user.has_group('assetflow_base.group_assetflow_department_head')
                and department and self.department_id == department):
            return
        raise UserError(_('Only the holder, the department head or an Asset Manager can return this asset.'))

    @api.private
    def _require_admin(self):
        if not self.env.user.has_group('assetflow_base.group_assetflow_admin'):
            raise UserError(_('Only an AssetFlow Administrator can perform this action.'))

    @api.private
    def _has_current_booking(self):
        if 'assetflow.booking' not in self.env.registry.models:
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
        self.with_context(allow_state_write=True).write({'state': new_state})
        self.env['assetflow.activity.log']._log_activity(
            'update', self, _('Asset %s moved to %s', self.asset_tag, new_state),
        )

    @api.private
    def _event_recipients(self, with_holder=False, with_heads=False, with_managers=False):
        users = self.env['res.users']
        if with_holder and self.holder_employee_id.user_id:
            users |= self.holder_employee_id.user_id
        if with_heads and self.department_id:
            heads = self.env.ref('assetflow_base.group_assetflow_department_head').sudo().user_ids
            users |= heads.filtered(
                lambda user: user.employee_id.department_id == self.department_id
            )
        if with_managers:
            users |= self.env.ref('assetflow_base.group_assetflow_asset_manager').sudo().user_ids
        return users

    @api.private
    def _notify_event(self, title, body, notification_type='system', **recipients):
        for user in self._event_recipients(**recipients):
            self.env['assetflow.notification']._notify_once(
                user, title, body, notification_type, self._name, self.id,
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
        department = department or (employee.department_id if employee else False)
        self.env['assetflow.allocation'].create({
            'asset_id': self.id,
            'employee_id': employee.id if employee else False,
            'department_id': department.id if department else False,
            'expected_return_date': expected_return_date,
        })
        self.env['assetflow.activity.log']._log_activity(
            'allocate', self, _('Asset %s allocated', self.asset_tag),
        )
        holder = self.holder_employee_id.name or self.department_id.name or _('a department')
        self._notify_event(
            _('Asset allocated: %s', self.asset_tag),
            _('%s was allocated to %s.', self.asset_tag, holder),
            with_holder=True, with_heads=True,
        )
        self.message_post(body=_('Allocated to %s.', holder))

    def action_return(self, condition=None, notes=None):
        self.ensure_one()
        condition = condition or self.return_condition
        notes = notes or self.return_notes
        if not condition or not notes:
            raise UserError(_('A return condition and check-in notes are required.'))
        self.lock_for_update()
        self.invalidate_recordset(['state'])
        if self.state != 'allocated':
            raise UserError(_('Asset %s is no longer allocated.', self.asset_tag))
        allocation = self._active_allocation()
        if not allocation:
            raise UserError(_('Asset %s has no active allocation to return.', self.asset_tag))
        self._require_returner(allocation)
        allocation.sudo().with_context(allow_state_write=True).write({
            'state': 'returned',
            'return_datetime': fields.Datetime.now(),
            'checkin_condition': condition,
            'checkin_notes': notes,
        })
        self.sudo().with_context(allow_state_write=True).write({
            'state': 'available', 'holder_employee_id': False, 'expected_return_date': False,
        })
        self.env['assetflow.activity.log']._log_activity(
            'return', self, _('Asset %s returned', self.asset_tag),
        )
        self.message_post(body=_(
            'Returned with condition %(condition)s. %(notes)s',
            condition=condition, notes=notes,
        ))

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

    @api.private
    def action_reserve(self):
        """Internal workflow hook called by booking through an explicit sudo boundary."""
        for asset in self:
            if asset.state == 'available':
                asset.with_context(allow_state_write=True).write({'state': 'reserved'})

    @api.private
    def action_release(self):
        """Internal workflow hook called by booking through an explicit sudo boundary."""
        for asset in self:
            if asset.state == 'reserved':
                asset.with_context(allow_state_write=True).write({'state': 'available'})

    def action_set_maintenance(self, reason=None):
        if not (
            self.env.user.has_group('assetflow_base.group_assetflow_asset_manager')
            or self.env.user.has_group('assetflow_base.group_assetflow_admin')
        ):
            raise UserError(_('Only an Asset Manager or Administrator can move an asset into maintenance.'))
        self._transition('maintenance', ['available', 'allocated', 'reserved'],
                         note=reason or self.transition_reason, require_note=True)

    def action_mark_lost(self, reason=None):
        self._transition('lost', ['available', 'allocated', 'reserved', 'maintenance'],
                         note=reason or self.transition_reason, admin_only=True, require_note=True)

    def action_found(self, reason=None):
        self._transition('available', ['lost'],
                         note=reason or self.transition_reason, admin_only=True, require_note=True)
        self.message_post(body=reason or _('Marked found.'))

    def action_retire(self, reason=None):
        self._transition('retired', ['available', 'reserved', 'maintenance', 'lost'],
                         note=reason or self.transition_reason, admin_only=True, require_note=True)

    def action_dispose(self, reason=None):
        self._transition('disposed', ['available', 'reserved', 'maintenance', 'lost', 'retired'],
                         note=reason or self.transition_reason, admin_only=True, require_note=True)

    @api.private
    def action_restore_after_maintenance(self, target_state):
        """Internal workflow hook for maintenance resolve; no group check of its own."""
        for asset in self:
            if asset.state != 'maintenance':
                raise UserError(_('Only an asset under maintenance can be restored.'))
            if target_state not in ('available', 'allocated'):
                raise UserError(_('Maintenance can only restore to available or allocated.'))
            if target_state == 'allocated' and not asset._active_allocation():
                raise UserError(_('Cannot restore to allocated without an active allocation.'))
            # Trust boundary: a technician may resolve without asset write rights.
            asset.sudo().with_context(allow_state_write=True).write({'state': target_state})
            self.env['assetflow.activity.log']._log_activity(
                'resolve', asset, _('Maintenance resolved; asset restored to %s', target_state),
            )

    def action_archive(self):
        self._require_admin()
        self.with_context(allow_state_write=True).write({'active': False})

    @api.ondelete(at_uninstall=False)
    def _unlink_if_no_history(self):
        for asset in self:
            if asset.allocation_ids or asset.transfer_ids or asset.state != 'available' or not asset.active:
                raise UserError(_(
                    'Archive %s instead of deleting it: historical records must be preserved.',
                    asset.asset_tag,
                ))
