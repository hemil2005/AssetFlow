from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AssetflowDepartment(models.Model):
    _name = 'assetflow.department'
    _description = 'AssetFlow Department'
    _order = 'complete_name'
    _parent_store = True

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    parent_id = fields.Many2one('assetflow.department', string='Parent Department', ondelete='restrict')
    parent_path = fields.Char(index=True)
    head_id = fields.Many2one('assetflow.employee', string='Department Head', ondelete='set null')
    child_ids = fields.One2many('assetflow.department', 'parent_id', string='Child Departments')
    active = fields.Boolean(string='Active', default=True)
    employee_ids = fields.One2many('assetflow.employee', 'department_id', string='Members')
    member_count = fields.Integer(string='Member Count', compute='_compute_member_count')
    complete_name = fields.Char(string='Complete Name', compute='_compute_complete_name', store=True, recursive=True)

    _code_uniq = models.Constraint('UNIQUE(code)', 'A department with this code already exists.')

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for department in self:
            department.complete_name = (
                department.parent_id.complete_name + ' / ' + department.name
                if department.parent_id else department.name
            )

    @api.depends('employee_ids')
    def _compute_member_count(self):
        counts = dict(self.env['assetflow.employee']._read_group(
            [('department_id', 'in', self.ids)], ['department_id'], ['__count'],
        ))
        for department in self:
            department.member_count = counts.get(department, 0)

    @api.constrains('parent_id')
    def _check_parent_cycle(self):
        for department in self:
            parent = department.parent_id
            while parent:
                if parent == department:
                    raise ValidationError(_('A department cannot be its own ancestor.'))
                parent = parent.parent_id
