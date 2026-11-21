from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AssetflowAsset(models.Model):
    _inherit = 'assetflow.asset'

    audit_line_ids = fields.One2many('assetflow.audit.line', 'asset_id', string='Audit History')
    audit_count = fields.Integer(string='Audits', compute='_compute_audit_count')

    @api.depends('audit_line_ids')
    def _compute_audit_count(self):
        for asset in self:
            asset.audit_count = len(asset.audit_line_ids)

    def action_audit_mark_lost(self, reason=None):
        """Trusted audit-close transition; the caller is the audit workflow."""
        for asset in self:
            if asset.state not in ('available', 'reserved'):
                raise UserError(_('Audit close cannot mark %s lost from %s.', asset.asset_tag, asset.state))
            asset.with_context(allow_state_write=True).write({'state': 'lost'})
            asset.message_post(body=reason or _('Marked lost by an audit.'))
            self.env['assetflow.activity.log']._log_activity(
                'update', asset, _('Asset %s marked lost by audit', asset.asset_tag),
            )

    def action_audit_mark_damaged(self, note=None):
        for asset in self:
            asset.write({'condition': 'damaged'})
            asset.message_post(body=note or _('Marked damaged by an audit.'))
