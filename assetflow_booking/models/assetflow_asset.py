from odoo import fields, models


class AssetflowAsset(models.Model):
    _inherit = 'assetflow.asset'

    booking_ids = fields.One2many(
        'assetflow.booking', 'asset_id', string='Booking History',
    )
