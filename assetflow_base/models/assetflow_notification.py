from odoo import _, api, fields, models
from odoo.exceptions import UserError


NOTIFICATION_TYPES = [
    ('booking_reminder', 'Booking Reminder'),
    ('overdue_return', 'Overdue Return'),
    ('transfer', 'Transfer'),
    ('maintenance', 'Maintenance'),
    ('audit', 'Audit'),
    ('system', 'System'),
]


class AssetflowNotification(models.Model):
    _name = 'assetflow.notification'
    _description = 'AssetFlow Notification'
    _order = 'create_date desc'

    user_id = fields.Many2one('res.users', string='Recipient', required=True, ondelete='cascade', index=True)
    title = fields.Char(string='Title', required=True)
    body = fields.Text(string='Detail')
    notification_type = fields.Selection(NOTIFICATION_TYPES, string='Type', default='system', index=True)
    res_model = fields.Char(string='Related Model')
    res_id = fields.Integer(string='Related Record ID')
    is_read = fields.Boolean(string='Read', default=False, index=True)
    read_at = fields.Datetime(string='Read At', readonly=True)

    def action_mark_read(self):
        for notification in self:
            if notification.user_id != self.env.user:
                raise UserError(_('You can only mark your own notifications as read.'))
            notification.write({'is_read': True, 'read_at': fields.Datetime.now()})

    @api.model
    def action_mark_all_read(self):
        unread = self.search([('user_id', '=', self.env.user.id), ('is_read', '=', False)])
        unread.write({'is_read': True, 'read_at': fields.Datetime.now()})
        return True

    def action_open_record(self):
        """Open the record a notification points at.

        ``exists`` is evaluated under the current user's record rules, so a
        notification can never be used to reach a record the user cannot read.
        """
        self.ensure_one()
        if not self.res_model or not self.res_id:
            raise UserError(_('This notification has no linked record.'))
        if self.res_model not in self.env.registry.models:
            raise UserError(_('The linked record is no longer available.'))
        record = self.env[self.res_model].browse(self.res_id)
        if not record.exists():
            raise UserError(_('The linked record was deleted or you cannot access it.'))
        return {
            'type': 'ir.actions.act_window',
            'name': self.title,
            'res_model': self.res_model,
            'res_id': self.res_id,
            'views': [[False, 'form']],
            'target': 'current',
        }

    @api.model
    def _notify_once(self, user, title, body='', notification_type='system', res_model=False, res_id=False):
        """Create at most one notification per event/recipient per day.

        Workflow actions may be retried by a client; this keeps the notification
        list stable without changing the business state transition itself.
        """
        day_start = fields.Datetime.start_of(fields.Datetime.now(), 'day')
        exists = self.sudo().search_count([
            ('user_id', '=', user.id),
            ('notification_type', '=', notification_type),
            ('title', '=', title),
            ('res_model', '=', res_model),
            ('res_id', '=', res_id),
            ('create_date', '>=', fields.Datetime.to_string(day_start)),
        ])
        if exists:
            return self.env['assetflow.notification']
        return self._notify(
            user, title, body, notification_type=notification_type,
            res_model=res_model, res_id=res_id,
        )

    @api.model
    def _notify(self, user, title, body='', notification_type='system', res_model=False, res_id=False):
        # Trust boundary: events from other users' workflows create notifications
        # for a named recipient; ACLs still restrict reading them.
        return self.sudo().create({
            'user_id': user.id,
            'title': title,
            'body': body,
            'notification_type': notification_type,
            'res_model': res_model,
            'res_id': res_id,
        })
