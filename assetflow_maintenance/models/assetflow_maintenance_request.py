from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

MAINTENANCE_STATES = [
    ('pending', 'Pending'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
    ('assigned', 'Assigned'),
    ('in_progress', 'In Progress'),
    ('resolved', 'Resolved'),
]

OPEN_STATES = ('pending', 'approved', 'assigned', 'in_progress')

PRIORITIES = [
    ('low', 'Low'),
    ('medium', 'Medium'),
    ('high', 'High'),
    ('critical', 'Critical'),
]

ASSET_STATES = [
    ('available', 'Available'),
    ('allocated', 'Allocated'),
    ('reserved', 'Reserved'),
    ('maintenance', 'Under Maintenance'),
    ('lost', 'Lost'),
    ('retired', 'Retired'),
    ('disposed', 'Disposed'),
]


class AssetflowMaintenanceRequest(models.Model):
    _name = 'assetflow.maintenance.request'
    _description = 'Maintenance Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    _open_per_asset = models.UniqueIndex(
        "(asset_id) WHERE state IN ('pending', 'approved', 'assigned', 'in_progress')",
        'This asset already has an open maintenance request.',
    )
    _reference_uniq = models.UniqueIndex(
        '(reference) WHERE reference IS NOT NULL', 'This maintenance reference already exists.',
    )
    _asset_state_idx = models.Index('(asset_id, state)')
    _state_priority_idx = models.Index('(state, priority)')

    name = fields.Char(string='Subject', required=True, tracking=True)
    reference = fields.Char(
        string='Reference', readonly=True, copy=False,
        default=lambda self: self.env['ir.sequence'].next_by_code('assetflow.maintenance.ref'),
    )
    asset_id = fields.Many2one(
        'assetflow.asset', string='Asset', required=True, ondelete='restrict', index=True,
    )
    raised_by_id = fields.Many2one(
        'assetflow.employee', string='Raised By', required=True, ondelete='restrict',
        default=lambda self: self.env.user.employee_id,
    )
    description = fields.Text(string='Issue Description', required=True)
    priority = fields.Selection(PRIORITIES, string='Priority', default='medium', required=True)
    photo = fields.Image(string='Photo', max_width=1024, max_height=1024)
    state = fields.Selection(
        MAINTENANCE_STATES, string='Status', default='pending', required=True, index=True,
        readonly=True, tracking=True,
    )
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    approved_at = fields.Datetime(string='Approved At', readonly=True)
    rejection_reason = fields.Text(string='Rejection Reason')
    technician_id = fields.Many2one('assetflow.employee', string='Technician', ondelete='set null')
    assigned_at = fields.Datetime(string='Assigned At', readonly=True)
    started_at = fields.Datetime(string='Started At', readonly=True)
    resolved_at = fields.Datetime(string='Resolved At', readonly=True)
    resolution_notes = fields.Text(string='Resolution Notes')
    previous_asset_state = fields.Selection(ASSET_STATES, string='Previous Asset State', readonly=True)
    active = fields.Boolean(string='Active', default=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('raised_by_id'):
                vals['raised_by_id'] = self.env.user.employee_id.id
            if not vals['raised_by_id']:
                raise UserError(_(
                    'Your account has no employee record. Ask an administrator to create one before raising '
                    'a maintenance request.',
                ))
            asset = self.env['assetflow.asset'].browse(vals.get('asset_id'))
            self._check_raiser_scope(asset, vals['raised_by_id'])
            if asset:
                self._check_duplicate_open(asset)
        requests = super().create(vals_list)
        for request in requests:
            self.env['assetflow.activity.log']._log_activity(
                'create', request, _('Maintenance %s raised', request.reference),
            )
            request.message_post(body=_(
                'Maintenance %(reference)s raised by %(user)s for asset %(asset)s.',
                reference=request.reference, user=self.env.user.name, asset=request.asset_id.asset_tag,
            ))
            request._notify_managers(
                _('Maintenance request %s raised', request.reference),
                _('%(user)s raised a request for asset %(asset)s: %(subject)s',
                  user=request.raised_by_id.name, asset=request.asset_id.asset_tag, subject=request.name),
            )
        return requests

    @api.private
    def _check_raiser_scope(self, asset, raised_by_id):
        user = self.env.user
        if user.has_group('assetflow_base.group_assetflow_asset_manager'):
            return
        raised_by = self.env['assetflow.employee'].browse(raised_by_id)
        if raised_by != user.employee_id:
            raise UserError(_('You can only raise maintenance requests for yourself.'))
        if not asset:
            return
        department = user.employee_id.department_id
        if user.has_group('assetflow_base.group_assetflow_department_head') and department \
                and asset.department_id == department:
            return
        if asset.holder_employee_id != user.employee_id:
            raise UserError(_('You can only raise maintenance for an asset you currently hold.'))

    @api.private
    def _check_duplicate_open(self, asset):
        # Trust boundary: an employee creating a request only sees their own rows under the
        # record rules, so the duplicate open-request check must read across the whole table.
        if self.sudo().search_count([('asset_id', '=', asset.id), ('state', 'in', OPEN_STATES)]):
            raise ValidationError(_(
                'Asset %s already has an open maintenance request.', asset.asset_tag,
            ))

    def write(self, vals):
        allow_state = self.env.context.get('allow_state_write')
        if not allow_state:
            guarded = {
                'state', 'reference', 'approved_by', 'approved_at', 'assigned_at', 'started_at',
                'resolved_at', 'previous_asset_state', 'active',
            } & set(vals)
            if guarded:
                raise UserError(_('Use the maintenance actions to change status and decision fields.'))
            if not self.env.user.has_group('assetflow_base.group_assetflow_asset_manager'):
                manager_only = {'asset_id', 'raised_by_id', 'technician_id'} & set(vals)
                if manager_only:
                    raise UserError(_('Only an Asset Manager can change these fields.'))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _forbid_unlink(self):
        for request in self:
            raise UserError(_('Archive maintenance requests instead of deleting them.'))

    @api.private
    def _require_approver(self):
        if not self.env.user.has_group('assetflow_base.group_assetflow_asset_manager'):
            raise UserError(_('Only an Asset Manager or Administrator can decide a maintenance request.'))

    @api.private
    def _require_technician(self):
        for request in self:
            user = self.env.user
            if user.has_group('assetflow_base.group_assetflow_asset_manager'):
                continue
            if not request.technician_id or request.technician_id.user_id != user:
                raise UserError(_('Only the assigned technician or an Asset Manager can do that.'))

    @api.private
    def _notify_user(self, user, title, body):
        self.ensure_one()
        if user:
            self.env['assetflow.notification']._notify(
                user, title, body, 'maintenance', self._name, self.id,
            )

    @api.private
    def _notify_managers(self, title, body):
        # Trust boundary: notification fan-out needs the manager/admin membership list,
        # which an employee raising a request is not allowed to browse.
        groups = (
            self.env.ref('assetflow_base.group_assetflow_asset_manager').sudo()
            | self.env.ref('assetflow_base.group_assetflow_admin').sudo()
        )
        for user in groups.user_ids:
            self._notify_user(user, title, body)

    def action_approve(self):
        for request in self:
            request._require_approver()
            if request.state != 'pending':
                raise UserError(_('Only a pending request can be approved.'))
            asset = request.asset_id
            asset.lock_for_update()
            if asset._has_current_booking():
                raise UserError(_(
                    'Asset %s is booked right now. Cancel or finish the booking before approving maintenance.',
                    asset.asset_tag,
                ))
            if asset.state == 'reserved':
                raise UserError(_(
                    'Asset %s has an upcoming booking. Cancel the bookings before approving maintenance.',
                    asset.asset_tag,
                ))
            if asset.state not in ('available', 'allocated'):
                raise UserError(_(
                    'Asset %s cannot enter maintenance from state "%s".', asset.asset_tag, asset.state,
                ))
            previous_state = asset.state
            asset.action_set_maintenance(reason=_('Maintenance %s', request.reference))
            request.with_context(allow_state_write=True).write({
                'state': 'approved',
                'approved_by': self.env.user.id,
                'approved_at': fields.Datetime.now(),
                'previous_asset_state': previous_state,
            })
            self.env['assetflow.activity.log']._log_activity(
                'approve', request, _('Maintenance %s approved for %s', request.reference, asset.asset_tag),
            )
            request.message_post(body=_(
                'Maintenance %(reference)s approved by %(user)s. Asset %(asset)s is now under maintenance.',
                reference=request.reference, user=self.env.user.name, asset=asset.asset_tag,
            ))
            request._notify_user(
                request.raised_by_id.user_id,
                _('Maintenance request %s approved', request.reference),
                _('Your request for %s was approved and the asset is under maintenance.', asset.asset_tag),
            )

    def action_reject(self, reason=None):
        for request in self:
            request._require_approver()
            if request.state != 'pending':
                raise UserError(_('Only a pending request can be rejected.'))
            reason = (reason or request.rejection_reason or '').strip()
            if not reason:
                raise UserError(_('A rejection reason is required.'))
            request.with_context(allow_state_write=True).write({
                'state': 'rejected',
                'rejection_reason': reason,
            })
            self.env['assetflow.activity.log']._log_activity(
                'reject', request, _('Maintenance %s rejected', request.reference),
            )
            request.message_post(body=_(
                'Maintenance %(reference)s rejected by %(user)s: %(reason)s',
                reference=request.reference, user=self.env.user.name, reason=reason,
            ))
            request._notify_user(
                request.raised_by_id.user_id,
                _('Maintenance request %s rejected', request.reference),
                reason,
            )

    def action_assign(self, technician=None):
        for request in self:
            request._require_approver()
            if request.state != 'approved':
                raise UserError(_('Assign a technician only after the request is approved.'))
            technician = technician or request.technician_id
            if not technician:
                raise UserError(_('Select a technician to assign.'))
            request.with_context(allow_state_write=True).write({
                'state': 'assigned',
                'technician_id': technician.id,
                'assigned_at': fields.Datetime.now(),
            })
            self.env['assetflow.activity.log']._log_activity(
                'update', request, _('Maintenance %s assigned to %s', request.reference, technician.name),
            )
            request.message_post(body=_(
                'Maintenance %(reference)s assigned to %(technician)s.',
                reference=request.reference, technician=technician.name,
            ))
            request._notify_user(
                technician.user_id,
                _('Maintenance job %s assigned to you', request.reference),
                _('You are the technician for %s on asset %s.', request.reference, request.asset_id.asset_tag),
            )

    def action_start(self):
        for request in self:
            request._require_technician()
            if request.state != 'assigned':
                raise UserError(_('Only an assigned request can be started.'))
            request.with_context(allow_state_write=True).write({
                'state': 'in_progress',
                'started_at': fields.Datetime.now(),
            })
            self.env['assetflow.activity.log']._log_activity(
                'update', request, _('Maintenance %s started', request.reference),
            )
            request.message_post(body=_('Work started on %s.', request.reference))

    def action_resolve(self, notes=None):
        for request in self:
            request._require_technician()
            if request.state != 'in_progress':
                raise UserError(_('Only a request in progress can be resolved.'))
            notes = (notes or request.resolution_notes or '').strip()
            if not notes:
                raise UserError(_('Resolution notes are required.'))
            # Trust boundary: the assigned technician owns the resolution decision but may not
            # have write access to the asset or read access to its allocations. The approved
            # request is the authorization; the asset transition below runs on the sudo recordset.
            asset = request.asset_id.sudo()
            asset.lock_for_update()
            if asset.state == 'maintenance':
                target = self._target_state(request)
                request._restore_asset_state(target)
            request.with_context(allow_state_write=True).write({
                'state': 'resolved',
                'resolved_at': fields.Datetime.now(),
                'resolution_notes': notes,
            })
            self.env['assetflow.activity.log']._log_activity(
                'resolve', request, _('Maintenance %s resolved', request.reference),
            )
            request.message_post(body=_(
                'Maintenance %(reference)s resolved by %(user)s: %(notes)s',
                reference=request.reference, user=self.env.user.name, notes=notes,
            ))
            request._notify_user(
                request.raised_by_id.user_id,
                _('Maintenance request %s resolved', request.reference),
                _('Asset %s is back in service. %s', asset.asset_tag, notes),
            )

    @api.private
    def _target_state(self, request):
        # Trust boundary: same reasoning as action_resolve; the technician may not see allocations.
        allocation = request.asset_id.sudo()._active_allocation()
        if allocation:
            return 'allocated'
        target = request.previous_asset_state or 'available'
        return target if target in ('available', 'allocated') else 'available'

    @api.private
    def _restore_asset_state(self, target):
        self.ensure_one()
        # The assets addon owns the asset lifecycle and publishes this transition.
        # Trust boundary: the approved request authorizes the restore; the resolving
        # technician may have no write access to the asset record itself.
        self.asset_id.sudo().action_restore_after_maintenance(target)

    def action_archive(self):
        self._require_approver()
        self.with_context(allow_state_write=True).write({'active': False})

    @api.model
    def _cron_flag_aging_requests(self):
        cutoff = fields.Datetime.now() - timedelta(days=2)
        day_start = fields.Datetime.to_datetime(fields.Date.context_today(self))
        notification_model = self.env['assetflow.notification'].sudo()
        requests = self.search([('state', '=', 'pending'), ('create_date', '<', cutoff)])
        for request in requests:
            already = notification_model.search_count([
                ('notification_type', '=', 'maintenance'),
                ('res_model', '=', self._name),
                ('res_id', '=', request.id),
                ('create_date', '>=', day_start),
                ('title', 'like', 'Maintenance pending'),
            ])
            if already:
                continue
            request._notify_managers(
                _('Maintenance pending for %s', request.reference),
                _('Request %s for asset %s is still pending after two days.',
                  request.reference, request.asset_id.asset_tag),
            )
