from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AssetflowAuditCycle(models.Model):
    _name = 'assetflow.audit.cycle'
    _description = 'Asset Audit Cycle'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'

    name = fields.Char(string='Audit Name', required=True, tracking=True)
    reference = fields.Char(
        string='Reference', readonly=True, copy=False, index=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('assetflow.audit.ref'),
    )
    scope_department_id = fields.Many2one(
        'assetflow.department', string='Scope Department', ondelete='restrict',
    )
    scope_location = fields.Char(string='Scope Location')
    date_from = fields.Date(string='Start Date', required=True, default=fields.Date.context_today)
    date_to = fields.Date(string='End Date', required=True, default=fields.Date.context_today)
    auditor_ids = fields.Many2many(
        'assetflow.employee', 'assetflow_audit_cycle_employee_rel',
        'cycle_id', 'employee_id', string='Auditors',
    )
    state = fields.Selection(
        [('draft', 'Draft'), ('in_progress', 'In Progress'), ('closed', 'Closed')],
        string='Status', default='draft', required=True, tracking=True, index=True,
    )
    line_ids = fields.One2many('assetflow.audit.line', 'cycle_id', string='Audit Lines')
    discrepancy_count = fields.Integer(string='Discrepancies', compute='_compute_discrepancy_count')
    closed_by = fields.Many2one('res.users', string='Closed By', readonly=True)
    closed_at = fields.Datetime(string='Closed At', readonly=True)
    note = fields.Text(string='Notes')

    _reference_uniq = models.Constraint('UNIQUE(reference)', 'This audit reference already exists.')

    @api.depends('line_ids.result')
    def _compute_discrepancy_count(self):
        for cycle in self:
            cycle.discrepancy_count = len(
                cycle.line_ids.filtered(lambda line: line.result in ('missing', 'damaged'))
            )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for cycle in self:
            if cycle.date_to < cycle.date_from:
                raise UserError(_('The audit end date cannot be before its start date.'))

    @api.private
    def _require_manager(self):
        if not self.env.user.has_group('assetflow_base.group_assetflow_asset_manager'):
            raise UserError(_('Only an Asset Manager or Administrator can run audits.'))

    @api.private
    def _scope_domain(self):
        self.ensure_one()
        domain = [('active', '=', True), ('state', '!=', 'disposed')]
        if self.scope_department_id:
            domain.append(('department_id', '=', self.scope_department_id.id))
        if self.scope_location:
            domain.append(('location', 'ilike', self.scope_location))
        return domain

    @api.private
    def _notify_auditors(self, title, body):
        self.ensure_one()
        notification_model = self.env['assetflow.notification']
        for auditor in self.auditor_ids.filtered('user_id'):
            notification_model._notify(
                auditor.user_id, title, body,
                notification_type='audit',
                res_model=self._name, res_id=self.id,
            )

    def action_start(self):
        for cycle in self:
            cycle._require_manager()
            if cycle.state != 'draft':
                raise UserError(_('Only a draft audit can be started.'))
            cycle.lock_for_update()
            assets = self.env['assetflow.asset'].search(cycle._scope_domain())
            existing = set(cycle.line_ids.asset_id.ids)
            to_create = assets.filtered(lambda asset: asset.id not in existing)
            if to_create:
                self.env['assetflow.audit.line'].create([
                    {
                        'cycle_id': cycle.id,
                        'asset_id': asset.id,
                        'expected_location': asset.location,
                    }
                    for asset in to_create
                ])
            cycle.write({'state': 'in_progress'})
            cycle.message_post(body=_('Audit %s started with %s asset(s).', cycle.reference, len(assets)))
            cycle._notify_auditors(
                _('Audit started: %s', cycle.name),
                _('You are assigned to audit %s.', cycle.reference),
            )
            self.env['assetflow.activity.log']._log_activity(
                'audit_open', cycle, _('Audit %s opened', cycle.reference),
            )

    def action_close(self):
        for cycle in self:
            cycle._require_manager()
            if cycle.state != 'in_progress':
                raise UserError(_('Only an in-progress audit can be closed.'))
            cycle.lock_for_update()
            pending = cycle.line_ids.filtered(lambda line: line.result == 'pending')
            if pending:
                tags = ', '.join(pending[:10].mapped('asset_id.asset_tag'))
                more = len(pending) - 10
                raise UserError(_(
                    'Every audit line must be decided before closing. Pending: %(tags)s%(more)s',
                    tags=tags, more=_(' and %s more', more) if more > 0 else '',
                ))
            for line in cycle.line_ids:
                if line.result == 'missing':
                    if line.asset_id.state in ('available', 'reserved'):
                        line.asset_id.action_audit_mark_lost(
                            reason=_('Marked missing in audit %s', cycle.reference),
                        )
                    else:
                        line.asset_id.message_post(body=_(
                            'Audit %(ref)s marked this asset missing while it was %(state)s; '
                            'status was not changed automatically.',
                            ref=cycle.reference, state=line.asset_id.state,
                        ))
                elif line.result == 'damaged':
                    line.asset_id.action_audit_mark_damaged(
                        note=_('Damaged in audit %s', cycle.reference),
                    )
            cycle.with_context(allow_audit_write=True).write({
                'state': 'closed',
                'closed_by': self.env.user.id,
                'closed_at': fields.Datetime.now(),
            })
            cycle.message_post(body=_(
                'Audit %(ref)s closed with %(count)s discrepancy(ies).',
                ref=cycle.reference, count=cycle.discrepancy_count,
            ))
            cycle._notify_auditors(
                _('Audit closed: %s', cycle.name),
                _('%s discrepancies were recorded.', cycle.discrepancy_count),
            )
            self.env['assetflow.activity.log']._log_activity(
                'audit_close', cycle, _('Audit %s closed', cycle.reference),
            )

    def write(self, vals):
        if not self.env.context.get('allow_audit_write'):
            closed = self.filtered(lambda cycle: cycle.state == 'closed')
            if closed:
                raise UserError(_('A closed audit cannot be modified.'))
        return super().write(vals)
