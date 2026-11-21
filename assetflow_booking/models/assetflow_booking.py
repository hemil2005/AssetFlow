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
    employee_id = fields.Many2one('hr.employee', string='Booked For', required=True, ondelete='restrict')
    department_id = fields.Many2one(
        'hr.department', string='Department', related='employee_id.department_id', store=True,
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
        self.env['assetflow.asset'].browse(asset_ids).lock_for_update()
        return super().create(vals_list)

    def write(self, vals):
        if {'asset_id', 'start_datetime', 'end_datetime'} & set(vals):
            asset_ids = set(self.mapped('asset_id').ids)
            if vals.get('asset_id'):
                asset_ids.add(vals['asset_id'])
            self.env['assetflow.asset'].browse(asset_ids).lock_for_update()
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
            conflict = self.search([
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
            booking.write({
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
            ongoing = self.search_count([('asset_id', '=', asset.id), ('state', '=', 'ongoing')])
            if ongoing:
                asset._set_state('reserved')
            elif asset.state == 'reserved':
                asset._set_state('available')

    @api.model
    def _cron_sync_states(self):
        now = fields.Datetime.now()
        self.search([('state', '=', 'upcoming'), ('start_datetime', '<=', now)]).write({'state': 'ongoing'})
        self.search([('state', '=', 'ongoing'), ('end_datetime', '<=', now)]).write({'state': 'completed'})
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
            booking.reminder_sent = True
            booking.asset_id.message_post(
                body=_('Booking reminder: %s starts at %s.', booking.asset_id.name, booking.start_datetime),
            )
