from odoo import api, models


class IrConfigParameter(models.Model):
    _inherit = 'ir.config_parameter'

    @api.model_create_multi
    def create(self, vals_list):
        result = super().create(vals_list)
        if any(vals.get('key') == 'web.base.url' for vals in vals_list):
            self.env['assetflow.asset'].sudo().invalidate_model(['qr_code'])
        return result

    def write(self, vals):
        result = super().write(vals)
        if any(parameter.key == 'web.base.url' for parameter in self):
            self.env['assetflow.asset'].sudo().invalidate_model(['qr_code'])
        return result
