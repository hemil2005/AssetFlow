from odoo import api, fields, models


ACTIVITY_ACTIONS = [
    ('create', 'Create'),
    ('update', 'Update'),
    ('delete', 'Delete'),
    ('allocate', 'Allocate'),
    ('return', 'Return'),
    ('transfer_request', 'Transfer Request'),
    ('transfer_approve', 'Transfer Approve'),
    ('book', 'Book'),
    ('cancel', 'Cancel'),
    ('approve', 'Approve'),
    ('reject', 'Reject'),
    ('resolve', 'Resolve'),
    ('audit_open', 'Audit Open'),
    ('audit_close', 'Audit Close'),
]


class AssetflowActivityLog(models.Model):
    _name = 'assetflow.activity.log'
    _description = 'AssetFlow Activity Log'
    _order = 'timestamp desc'

    user_id = fields.Many2one('res.users', string='Actor', required=True, default=lambda self: self.env.user)
    action = fields.Selection(ACTIVITY_ACTIONS, string='Action', required=True)
    model_name = fields.Char(string='Model')
    res_id = fields.Integer(string='Record ID')
    description = fields.Text(string='Description')
    timestamp = fields.Datetime(string='When', default=fields.Datetime.now, index=True)

    @api.model
    def _log_activity(self, action, record=None, description='', model_name=False, res_id=False):
        # Trust boundary: the audit trail must survive the originating record's
        # access rules, so the helper writes with elevated rights.
        return self.sudo().create({
            'user_id': self.env.user.id,
            'action': action,
            'model_name': model_name or (record._name if record else False),
            'res_id': res_id or (record.id if record else False),
            'description': description,
        })
