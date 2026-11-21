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
    department_id = fields.Many2one(
        'assetflow.department', string='Department', index=True, ondelete='set null',
        help='Department the entry belongs to. Department Heads read the entries of their own department.',
    )
    description = fields.Text(string='Description')
    timestamp = fields.Datetime(string='When', default=fields.Datetime.now, index=True)

    # A transfer and an audit cycle name their department as scope/target, so those
    # come first; most other records carry the plain department_id.
    _DEPARTMENT_FIELDS = ('scope_department_id', 'to_department_id', 'department_id')

    @api.model
    def _log_department(self, record):
        """Department an entry belongs to, for Department Head scoping.

        Uses the record's own department field, then the owning department of the
        asset it points at, and last the actor's department. A log row can point at
        any model, so this is what makes the head rule expressible.
        """
        if record:
            record = record.sudo()[:1]
            for field_name in self._DEPARTMENT_FIELDS:
                if field_name in record._fields:
                    department = record[field_name]
                    if department:
                        return department
            asset = record.asset_id if 'asset_id' in record._fields else False
            if asset and 'department_id' in asset._fields and asset.department_id:
                return asset.department_id
        return self.env.user.sudo().employee_id.department_id

    @api.model
    def _log_activity(self, action, record=None, description='', model_name=False, res_id=False):
        # Trust boundary: the audit trail must survive the originating record's
        # access rules, so the helper writes with elevated rights.
        return self.sudo().create({
            'user_id': self.env.user.id,
            'action': action,
            'model_name': model_name or (record._name if record else False),
            'res_id': res_id or (record.id if record else False),
            'department_id': self._log_department(record).id or False,
            'description': description,
        })
