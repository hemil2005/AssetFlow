from odoo import fields, models


class AssetflowAsset(models.Model):
    _inherit = 'assetflow.asset'

    maintenance_ids = fields.One2many(
        'assetflow.maintenance.request', 'asset_id', string='Maintenance History',
    )
