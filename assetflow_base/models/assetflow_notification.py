from odoo import api, fields, models
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
                raise UserError('You can only mark your own notifications as read.')
            notification.write({'is_read': True, 'read_at': fields.Datetime.now()})

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
