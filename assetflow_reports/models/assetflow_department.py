from odoo import models

REPORT_ROW_LIMIT = 500


class AssetflowDepartment(models.Model):
    _inherit = 'assetflow.department'

    def report_asset_rows(self):
        """Assets printed by the department allocation summary.

        Called once per department from QWeb; capped so a large department
        cannot build an unbounded PDF.
        """
        self.ensure_one()
        return self.env['assetflow.asset'].search(
            [('department_id', '=', self.id), ('state', '!=', 'disposed')],
            order='asset_tag', limit=REPORT_ROW_LIMIT,
        )
