from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AssetflowAuditLine(models.Model):
    _name = 'assetflow.audit.line'
    _description = 'Asset Audit Line'
    _order = 'cycle_id, asset_id'

    cycle_id = fields.Many2one('assetflow.audit.cycle', string='Audit', required=True, ondelete='cascade')
    asset_id = fields.Many2one('assetflow.asset', string='Asset', required=True, ondelete='restrict')
    expected_location = fields.Char(string='Expected Location', readonly=True)
    result = fields.Selection(
        [
            ('pending', 'Pending'),
            ('verified', 'Verified'),
            ('missing', 'Missing'),
            ('damaged', 'Damaged'),
        ],
        string='Result', default='pending', required=True, index=True,
    )
    notes = fields.Text(string='Notes')
    verified_by_id = fields.Many2one('assetflow.employee', string='Verified By', readonly=True)
    verified_at = fields.Datetime(string='Verified At', readonly=True)
    photo = fields.Image(string='Evidence Photo', max_width=1024, max_height=1024)

    _cycle_asset_uniq = models.Constraint(
        'UNIQUE(cycle_id, asset_id)', 'This asset is already in the audit cycle.',
    )
    _cycle_result_idx = models.Index('(cycle_id, result)')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            cycle = self.env['assetflow.audit.cycle'].browse(vals.get('cycle_id'))
            if cycle.state == 'closed':
                raise UserError(_('Cannot add lines to a closed audit.'))
            if vals.get('asset_id') and not vals.get('expected_location'):
                asset = self.env['assetflow.asset'].browse(vals['asset_id'])
                vals['expected_location'] = asset.location
        return super().create(vals_list)

    def write(self, vals):
        for line in self:
            if line.cycle_id.state != 'in_progress':
                raise UserError(_('Audit lines can only be edited while the audit is in progress.'))
        if 'result' in vals and vals['result'] != 'pending':
            vals = dict(
                vals,
                verified_by_id=self.env.user.employee_id.id or False,
                verified_at=fields.Datetime.now(),
            )
        elif vals.get('result') == 'pending':
            vals = dict(vals, verified_by_id=False, verified_at=False)
        return super().write(vals)

    @api.constrains('cycle_id', 'asset_id')
    def _check_scope(self):
        for line in self:
            cycle = line.cycle_id
            asset = line.asset_id
            if cycle.scope_department_id and asset.department_id != cycle.scope_department_id:
                raise ValidationError(_(
                    'Asset %s is outside the department scope of this audit.',
                    asset.asset_tag,
                ))
            if cycle.scope_location and cycle.scope_location.lower() not in (asset.location or '').lower():
                raise ValidationError(_(
                    'Asset %s is outside the location scope of this audit.',
                    asset.asset_tag,
                ))

    @api.ondelete(at_uninstall=False)
    def _unlink_if_draft(self):
        if any(line.cycle_id.state != 'draft' for line in self):
            raise UserError(_('Audit lines cannot be deleted after the audit has started.'))

    def action_mark_verified(self):
        self.write({'result': 'verified'})

    def action_mark_missing(self):
        self.write({'result': 'missing'})

    def action_mark_damaged(self):
        self.write({'result': 'damaged'})
