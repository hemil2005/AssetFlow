from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

BOOKING_STATES = [
    ('upcoming', 'Upcoming'),
    ('ongoing', 'Ongoing'),
    ('completed', 'Completed'),
    ('cancelled', 'Cancelled'),
]


class AssetflowBooking(models.Model):
    _name = 'assetflow.booking'
    _description = 'Resource Booking'
    _order = 'start_datetime desc, id desc'

    _slot_idx = models.Index('(asset_id, start_datetime, end_datetime)')
    _state_idx = models.Index('(state, start_datetime)')

    asset_id = fields.Many2one(
        'assetflow.asset', string='Resource', required=True, ondelete='restrict',
        domain=[('is_bookable', '=', True)],
    )
    employee_id = fields.Many2one('assetflow.employee', string='Booked For', required=True, ondelete='restrict')
    department_id = fields.Many2one(
        'assetflow.department', string='Department', related='employee_id.department_id', store=True,
    )
    start_datetime = fields.Datetime(string='Start', required=True)
    end_datetime = fields.Datetime(string='End (exclusive)', required=True)
    purpose = fields.Char(string='Purpose')
    state = fields.Selection(BOOKING_STATES, string='Status', default='upcoming', required=True, index=True)
    cancelled_by = fields.Many2one('res.users', string='Cancelled By', readonly=True)
    cancel_reason = fields.Text(string='Cancellation Reason')
    reminder_sent = fields.Boolean(string='Reminder Sent', default=False)

    @api.model_create_multi
    def create(self, vals_list):
        asset_ids = {vals['asset_id'] for vals in vals_list if vals.get('asset_id')}
        assets = self.env['assetflow.asset'].browse(asset_ids)
        assets.lock_for_update()
        for vals in vals_list:
            # Workflow-owned fields are never accepted from the caller.
            vals['state'] = 'upcoming'
            vals['reminder_sent'] = False
            vals.pop('cancelled_by', None)
            vals.pop('cancel_reason', None)
        for asset in assets:
            if not asset.is_bookable:
                raise ValidationError(_('Only a shared/bookable resource can be booked.'))
            if asset.state not in ('available', 'reserved'):
                raise ValidationError(_(
                    'Asset %s is %s and cannot be booked.', asset.asset_tag, asset.state,
                ))
        bookings = super().create(vals_list)
        now = fields.Datetime.now()
        current = bookings.filtered(
            lambda booking: booking.start_datetime <= now < booking.end_datetime
        )
        if current:
            # Trust boundary: booking state is workflow-owned, not user-editable.
            current.with_context(allow_state_write=True).write({'state': 'ongoing'})
        bookings._sync_asset_state()
        return bookings

    def write(self, vals):
        allow_state = self.env.context.get('allow_state_write')
        if not allow_state and {'employee_id', 'asset_id'} & set(vals):
            if not self.env.user.has_group('assetflow_base.group_assetflow_asset_manager'):
                raise UserError(_('Only an Asset Manager can change the booker or the resource.'))
        if not allow_state and 'state' in vals:
            raise UserError(_('Use the booking actions or cron to change booking state.'))
        if {'asset_id', 'start_datetime', 'end_datetime'} & set(vals):
            asset_ids = set(self.mapped('asset_id').ids)
            if vals.get('asset_id'):
                asset_ids.add(vals['asset_id'])
            assets = self.env['assetflow.asset'].browse(asset_ids)
            assets.lock_for_update()
            for asset in assets:
                if asset.state not in ('available', 'reserved'):
                    raise ValidationError(_(
                        'Asset %s is %s and cannot be booked.', asset.asset_tag, asset.state,
                    ))
        return super().write(vals)

    @api.constrains('asset_id', 'start_datetime', 'end_datetime', 'state')
    def _check_slot(self):
        now = fields.Datetime.now()
        for booking in self:
            if booking.state == 'cancelled':
                continue
            if booking.end_datetime <= booking.start_datetime:
                raise ValidationError(_('The end of a booking must be after its start.'))
            if booking.state == 'upcoming' and booking.end_datetime < now:
                raise ValidationError(_('A booking cannot be created for a past time slot.'))
            conflict = self.sudo().search([
                ('asset_id', '=', booking.asset_id.id),
                ('id', '!=', booking.id),
                ('state', '!=', 'cancelled'),
                ('start_datetime', '<', booking.end_datetime),
                ('end_datetime', '>', booking.start_datetime),
            ], limit=1)
            if conflict:
                raise ValidationError(_(
                    'This slot overlaps an existing booking for %s (%s - %s).',
                    booking.asset_id.name, conflict.start_datetime, conflict.end_datetime,
                ))

    def action_cancel(self, reason=None):
        for booking in self:
            if booking.state == 'cancelled':
                continue
            if booking.state == 'ongoing' and not self.env.user.has_group(
                'assetflow_base.group_assetflow_asset_manager'
            ):
                raise UserError(_('Only an Asset Manager can cancel an ongoing booking.'))
            booking.with_context(allow_state_write=True).write({
                'state': 'cancelled',
                'cancel_reason': reason or booking.cancel_reason,
                'cancelled_by': self.env.user.id,
            })
            booking._sync_asset_state()

    @api.private
    def _sync_asset_state(self):
        for asset in self.mapped('asset_id'):
            if asset.state not in ('available', 'reserved'):
                continue
            now = fields.Datetime.now()
            current = self.sudo().search_count([
                ('asset_id', '=', asset.id), ('state', '=', 'ongoing'),
                ('start_datetime', '<=', now), ('end_datetime', '>', now),
            ])
            # Trust boundary: an employee may book a resource but has no asset
            # write right, so the state sync is elevated here.
            if current:
                asset.sudo().action_reserve()
            elif asset.state == 'reserved':
                asset.sudo().action_release()

    @api.model
    def _cron_sync_states(self):
        now = fields.Datetime.now()
        self.with_context(allow_state_write=True).search([
            ('state', '=', 'upcoming'), ('start_datetime', '<=', now),
        ]).write({'state': 'ongoing'})
        self.with_context(allow_state_write=True).search([
            ('state', '=', 'ongoing'), ('end_datetime', '<=', now),
        ]).write({'state': 'completed'})
        self.search([('state', 'in', ['ongoing', 'completed'])])._sync_asset_state()

    @api.model
    def _cron_send_reminders(self):
        now = fields.Datetime.now()
        soon = fields.Datetime.to_string(fields.Datetime.to_datetime(now) + timedelta(minutes=15))
        for booking in self.search([
            ('state', '=', 'upcoming'),
            ('reminder_sent', '=', False),
            ('start_datetime', '>', now),
            ('start_datetime', '<=', soon),
        ]):
            recipient = booking.employee_id.user_id
            if not recipient:
                # Booker has no login: record the reminder as handled rather
                # than crashing the cron on every run.
                booking.reminder_sent = True
                continue
            booking.reminder_sent = True
            self.env['assetflow.notification']._notify(
                recipient,
                _('Booking reminder: %s', booking.asset_id.name),
                _('%s starts at %s.', booking.asset_id.name, booking.start_datetime),
                notification_type='booking_reminder',
                res_model='assetflow.booking',
                res_id=booking.id,
            )
