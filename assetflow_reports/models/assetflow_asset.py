from datetime import timedelta

from odoo import _, fields, models

USEFUL_LIFE_YEARS = 5


class AssetflowAsset(models.Model):
    _inherit = 'assetflow.asset'

    is_near_retirement = fields.Boolean(
        string='Near Retirement',
        compute='_compute_is_near_retirement',
        search='_search_is_near_retirement',
        help='Acquired more than five years ago (configurable heuristic, not depreciation).',
    )

    def _compute_is_near_retirement(self):
        today = fields.Date.context_today(self)
        threshold = today - timedelta(days=365 * USEFUL_LIFE_YEARS)
        for asset in self:
            asset.is_near_retirement = bool(
                asset.acquisition_date and asset.acquisition_date <= threshold
            )

    def _search_is_near_retirement(self, operator, value):
        today = fields.Date.context_today(self)
        threshold = today - timedelta(days=365 * USEFUL_LIFE_YEARS)
        near = [('acquisition_date', '!=', False), ('acquisition_date', '<=', threshold)]
        not_near = ['|', ('acquisition_date', '=', False), ('acquisition_date', '>', threshold)]
        if operator in ('=', 'in'):
            wants_near = bool(value) if operator == '=' else any(value)
        elif operator in ('!=', 'not in'):
            wants_near = not value if operator == '!=' else not any(value)
        else:
            raise NotImplementedError(_('Unsupported operator for Near Retirement.'))
        return near if wants_near else not_near
