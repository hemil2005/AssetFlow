from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

ASSET_STATES = [
    ('available', 'Available'),
    ('allocated', 'Allocated'),
    ('reserved', 'Reserved'),
    ('maintenance', 'Under Maintenance'),
    ('lost', 'Lost'),
    ('retired', 'Retired'),
    ('disposed', 'Disposed'),
]


class AssetflowAsset(models.Model):
    _name = 'assetflow.asset'
    _description = 'Asset'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'tag'

    tag = fields.Char(
        string='Asset Tag', required=True, readonly=True, copy=False, index=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('assetflow.asset.tag'),
    )
    name = fields.Char(string='Name', required=True, tracking=True)
    category_id = fields.Many2one('assetflow.category', string='Category', ondelete='restrict')
    serial_number = fields.Char(string='Serial Number', index=True)
    acquisition_date = fields.Date(string='Acquisition Date', default=fields.Date.context_today)
    acquisition_cost = fields.Float(string='Acquisition Cost', digits=(12, 2))
    condition = fields.Selection(
        [('excellent', 'Excellent'), ('good', 'Good'), ('fair', 'Fair'), ('poor', 'Poor')],
        string='Condition', default='good', tracking=True,
    )
    location = fields.Char(string='Location')
    image = fields.Image(string='Photo', max_width=1024, max_height=1024)
    is_bookable = fields.Boolean(string='Shared / Bookable', default=False)
    department_id = fields.Many2one('hr.department', string='Owning Department', ondelete='set null')
    state = fields.Selection(
        ASSET_STATES, string='Lifecycle Status', default='available', required=True, tracking=True,
    )
    employee_id = fields.Many2one(
        'hr.employee', string='Current Holder', compute='_compute_holder', store=True,
    )
    allocation_ids = fields.One2many('assetflow.allocation', 'asset_id', string='Allocation History')
    note = fields.Text(string='Notes')

    _tag_uniq = models.Constraint('UNIQUE(tag)', 'An asset with this tag already exists.')

    @api.depends('allocation_ids.state', 'allocation_ids.employee_id')
    def _compute_holder(self):
        for asset in self:
            active = asset.allocation_ids.filtered(lambda allocation: allocation.state == 'active')
            asset.employee_id = active[:1].employee_id

    @api.private
    def _set_state(self, state):
        self.ensure_one()
        if state not in dict(ASSET_STATES):
            raise ValidationError(_('Unknown asset lifecycle state.'))
        self.write({'state': state})

    @api.private
    def _require_manager(self):
        if not self.env.user.has_group('assetflow_base.group_assetflow_asset_manager'):
            raise UserError(_('Only an Asset Manager can perform this action.'))

    @api.private
    def _active_allocation(self):
        return self.env['assetflow.allocation'].search([
            ('asset_id', '=', self.id), ('state', '=', 'active'),
        ], limit=1)

    def action_allocate(self, employee=None, department=None, expected_return_date=None):
        """Allocate an available asset. Blocks double allocation."""
        self.ensure_one()
        self._require_manager()
        if self.state not in ('available', 'reserved'):
            raise ValidationError(_('Only available or reserved assets can be allocated.'))
        if not employee and not department:
            raise ValidationError(_('Select an employee or a department to allocate to.'))
        active = self._active_allocation()
        if active:
            holder = active.employee_id.name or active.department_id.name or _('another party')
            raise ValidationError(_(
                'Asset %s is currently held by %s. Create a transfer request instead.',
                self.tag, holder,
            ))
        self.env['assetflow.allocation'].create({
            'asset_id': self.id,
            'employee_id': employee.id if employee else False,
            'department_id': department.id if department else False,
            'expected_return_date': expected_return_date,
        })
        self._set_state('allocated')

    def action_return(self, note=None):
        """Mark the active allocation returned and make the asset available again."""
        self.ensure_one()
        self._require_manager()
        active = self._active_allocation()
        if not active:
            raise UserError(_('Asset %s is not currently allocated.', self.tag))
        active.write({
            'state': 'returned',
            'returned_on': fields.Datetime.now(),
            'return_note': note or active.return_note,
        })
        self._set_state('available')

    def action_set_maintenance(self):
        self.ensure_one()
        self._require_manager()
        self._set_state('maintenance')

    def action_resolve_maintenance(self):
        self.ensure_one()
        self._require_manager()
        if self.state != 'maintenance':
            raise UserError(_('Asset %s is not under maintenance.', self.tag))
        self._set_state('available')

    def action_mark_lost(self):
        self.ensure_one()
        self._require_manager()
        self._set_state('lost')

    def action_retire(self):
        self.ensure_one()
        self._require_manager()
        self._set_state('retired')

    def action_dispose(self):
        self.ensure_one()
        self._require_manager()
        self._set_state('disposed')
