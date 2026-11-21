from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    employee_ids = fields.One2many('assetflow.employee', 'user_id', string='Employee Records')
    employee_id = fields.Many2one(
        'assetflow.employee', string='AssetFlow Employee', compute='_compute_employee_id', store=True,
    )

    @api.depends('employee_ids')
    def _compute_employee_id(self):
        for user in self:
            user.employee_id = user.employee_ids[:1]

    @api.model
    def _signup_create_user(self, values):
        user = super()._signup_create_user(values)
        internal_group = self.env.ref('base.group_user', raise_if_not_found=False)
        portal_group = self.env.ref('base.group_portal', raise_if_not_found=False)
        if internal_group:
            commands = [(4, internal_group.id)]
            if portal_group and portal_group in user.group_ids:
                commands.insert(0, (3, portal_group.id))
            # Trust boundary: Odoo signup creates a portal user, while AssetFlow needs
            # an internal account with no AssetFlow role; promotion stays admin-only.
            user.sudo().write({'group_ids': commands})

        department = self.env.ref('assetflow_base.department_general', raise_if_not_found=False)
        if department:
            self.env['assetflow.employee'].sudo().create({
                'name': values.get('name') or user.name,
                'email': (values.get('email') or values.get('login') or user.email).lower(),
                'user_id': user.id,
                'department_id': department.id,
            })
        return user
