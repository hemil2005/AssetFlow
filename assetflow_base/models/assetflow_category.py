from odoo import fields, models


class AssetflowCategory(models.Model):
    _name = 'assetflow.category'
    _description = 'Asset Category'
    _order = 'name'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', size=16)
    parent_id = fields.Many2one(
        'assetflow.category', string='Parent Category', ondelete='restrict',
    )
    child_ids = fields.One2many(
        'assetflow.category', 'parent_id', string='Child Categories',
    )
    active = fields.Boolean(string='Active', default=True)
    warranty_days = fields.Integer(
        string='Default Warranty (days)',
        help='Optional default warranty period for assets in this category.',
    )
    note = fields.Text(string='Notes', translate=True)

    _name_uniq = models.Constraint(
        'UNIQUE(name)',
        'An asset category with this name already exists.',
    )
    _warranty_non_negative = models.Constraint(
        'CHECK(warranty_days >= 0)',
        'The warranty period cannot be negative.',
    )
