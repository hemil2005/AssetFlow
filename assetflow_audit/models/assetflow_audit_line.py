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
            if cycle.state != 'draft':
                raise UserError(_('Audit lines can only be added to a draft audit.'))
            if vals.get('asset_id') and not vals.get('expected_location'):
                asset = self.env['assetflow.asset'].browse(vals['asset_id'])
                vals['expected_location'] = asset.location
        return super().create(vals_list)

    def write(self, vals):
        if {'verified_by_id', 'verified_at'} & set(vals):
            raise UserError(_('Verification identity and time are set by the audit action.'))
        if 'expected_location' in vals:
            raise UserError(_('The expected location snapshot cannot be changed.'))
        if {'cycle_id', 'asset_id'} & set(vals):
            raise UserError(_('Audit lines cannot be moved to another audit or asset.'))
        for cycle in self.cycle_id:
            cycle.lock_for_update()
            if cycle.state != 'in_progress':
                raise UserError(_('Audit lines can only be edited while the audit is in progress.'))
        previous = {line.id: line.result for line in self}
        if 'result' in vals and vals['result'] != 'pending':
            vals = dict(
                vals,
                verified_by_id=self.env.user.employee_id.id or False,
                verified_at=fields.Datetime.now(),
            )
        elif vals.get('result') == 'pending':
            vals = dict(vals, verified_by_id=False, verified_at=False)
        result = super().write(vals)
        new_result = vals.get('result')
        if new_result in ('missing', 'damaged'):
            for line in self.filtered(lambda record: previous.get(record.id) != new_result):
                line._notify_discrepancy()
        return result

    @api.private
    def _notify_discrepancy(self):
        self.ensure_one()
        cycle = self.cycle_id
        body = _(
            'Asset %(tag)s marked %(result)s in audit %(reference)s.',
            tag=self.asset_id.asset_tag, result=self.result, reference=cycle.reference,
        )
        cycle.sudo().message_post(body=body)
        recipients = cycle.auditor_ids.mapped('user_id')
        recipients |= self.env.ref('assetflow_base.group_assetflow_asset_manager').user_ids
        recipients |= self.env.ref('assetflow_base.group_assetflow_admin').user_ids
        for user in recipients:
            self.env['assetflow.notification']._notify(
                user,
                _('Audit discrepancy: %(tag)s', tag=self.asset_id.asset_tag),
                body,
                notification_type='audit',
                res_model=self._name, res_id=self.id,
            )

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
