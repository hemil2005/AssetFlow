from odoo import api, fields, models


class AssetflowCategory(models.Model):
    _name = 'assetflow.category'
    _description = 'Asset Category'
    _order = 'name'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    parent_id = fields.Many2one('assetflow.category', string='Parent Category', ondelete='restrict')
    child_ids = fields.One2many('assetflow.category', 'parent_id', string='Child Categories')
    active = fields.Boolean(string='Active', default=True)
    warranty_months = fields.Integer(string='Default Warranty (months)', default=0)
    description = fields.Text(string='Description', translate=True)
    asset_count = fields.Integer(string='Assets', compute='_compute_asset_count')

    _name_uniq = models.Constraint('UNIQUE(name)', 'An asset category with this name already exists.')
    _code_uniq = models.Constraint('UNIQUE(code)', 'An asset category with this code already exists.')
    _warranty_non_negative = models.Constraint(
        'CHECK(warranty_months >= 0)', 'The warranty period cannot be negative.',
    )

    @api.depends('name')
    def _compute_asset_count(self):
        asset_model = self.env['ir.model'].sudo().search_count([('model', '=', 'assetflow.asset')])
        for category in self:
            category.asset_count = (
                self.env['assetflow.asset'].search_count([('category_id', '=', category.id)])
                if asset_model else 0
            )
