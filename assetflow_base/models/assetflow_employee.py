from odoo import _, api, fields, models
from odoo.exceptions import UserError


ROLE_SELECTION = [
    ('none', 'No Role'),
    ('employee', 'Employee'),
    ('department_head', 'Department Head'),
    ('asset_manager', 'Asset Manager'),
    ('admin', 'Administrator'),
]


class AssetflowEmployee(models.Model):
    _name = 'assetflow.employee'
    _description = 'Employee Directory'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    email = fields.Char(string='Email', required=True, index=True)
    phone = fields.Char(string='Phone')
    department_id = fields.Many2one('assetflow.department', string='Department', required=True, ondelete='restrict')
    job_title = fields.Char(string='Job Title')
    user_id = fields.Many2one('res.users', string='Login Account', ondelete='set null', index=True)
    active = fields.Boolean(string='Active', default=True)
    role = fields.Selection(ROLE_SELECTION, string='AssetFlow Role', compute='_compute_role', store=True)

    _email_uniq = models.Constraint('UNIQUE(email)', 'An employee with this email already exists.')
    _user_uniq = models.UniqueIndex(
        '(user_id) WHERE user_id IS NOT NULL', 'This login already belongs to another employee.',
    )

    @api.depends('user_id.group_ids')
    def _compute_role(self):
        for employee in self:
            user = employee.user_id
            if not user:
                employee.role = 'none'
            elif user.has_group('assetflow_base.group_assetflow_admin'):
                employee.role = 'admin'
            elif user.has_group('assetflow_base.group_assetflow_asset_manager'):
                employee.role = 'asset_manager'
            elif user.has_group('assetflow_base.group_assetflow_department_head'):
                employee.role = 'department_head'
            elif user.has_group('assetflow_base.group_assetflow_employee'):
                employee.role = 'employee'
            else:
                employee.role = 'none'

    @api.model
    def _normalize_email(self, vals):
        if vals.get('email'):
            vals['email'] = vals['email'].strip().lower()
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._normalize_email(vals) for vals in vals_list])

    def write(self, vals):
        return super().write(self._normalize_email(vals))

    @api.private
    def _require_admin(self):
        if not self.env.user.has_group('assetflow_base.group_assetflow_admin'):
            raise UserError(_('Only an AssetFlow Administrator can assign roles.'))

    @api.private
    def _set_group(self, group_xmlid, add=True):
        self.ensure_one()
        if not self.user_id:
            raise UserError(_('This employee has no login account to promote.'))
        group = self.env.ref(group_xmlid)
        # Trust boundary: role assignment is admin-only (checked above) and is the
        # single place where AssetFlow groups may be granted.
        self.user_id.sudo().write({
            'group_ids': [(4 if add else 3, group.id)],
        })

    def action_promote_manager(self):
        self._require_admin()
        for employee in self:
            employee._set_group('assetflow_base.group_assetflow_asset_manager')

    def action_promote_head(self):
        self._require_admin()
        for employee in self:
            employee._set_group('assetflow_base.group_assetflow_department_head')

    def action_demote(self):
        self._require_admin()
        for employee in self:
            for group_xmlid in (
                'assetflow_base.group_assetflow_asset_manager',
                'assetflow_base.group_assetflow_department_head',
            ):
                employee._set_group(group_xmlid, add=False)
