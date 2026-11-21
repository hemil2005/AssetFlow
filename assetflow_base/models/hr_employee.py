from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    assetflow_role = fields.Selection(
        selection=[
            ('admin', 'Administrator'),
            ('manager', 'Asset Manager'),
            ('head', 'Department Head'),
            ('employee', 'Employee'),
        ],
        string='AssetFlow Role',
        compute='_compute_assetflow_role',
        store=True,
        help='Role derived from the user groups; roles are never set at signup.',
    )

    @api.depends('user_id.group_ids')
    def _compute_assetflow_role(self):
        for employee in self:
            user = employee.user_id
            if not user:
                employee.assetflow_role = 'employee'
            elif user.has_group('assetflow_base.group_assetflow_admin'):
                employee.assetflow_role = 'admin'
            elif user.has_group('assetflow_base.group_assetflow_asset_manager'):
                employee.assetflow_role = 'manager'
            elif user.has_group('assetflow_base.group_assetflow_department_head'):
                employee.assetflow_role = 'head'
            else:
                employee.assetflow_role = 'employee'
