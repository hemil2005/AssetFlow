from datetime import timedelta

from odoo import api, fields, models


class AssetflowDashboard(models.TransientModel):
    _name = 'assetflow.dashboard'
    _description = 'AssetFlow Dashboard'

    @api.model
    def get_kpi_data(self):
        today = fields.Date.context_today(self)
        week_end = today + timedelta(days=7)
        allocation_model = self.env['assetflow.allocation']
        active_allocations = allocation_model.search([('state', '=', 'active')])
        overdue = active_allocations.filtered(
            lambda allocation: allocation.expected_return_date
            and allocation.expected_return_date < today
        )
        upcoming = active_allocations.filtered(
            lambda allocation: allocation.expected_return_date
            and today <= allocation.expected_return_date <= week_end
        )
        notifications = self.env['assetflow.notification'].search([
            ('user_id', '=', self.env.user.id),
            ('is_read', '=', False),
        ], limit=5, order='create_date desc')

        def allocation_row(allocation):
            return {
                'asset_id': allocation.asset_id.id,
                'asset_tag': allocation.asset_id.asset_tag,
                'asset_name': allocation.asset_id.name,
                'holder': allocation.employee_id.name or allocation.department_id.name or '',
                'expected_return_date': fields.Date.to_string(allocation.expected_return_date),
            }

        return {
            'assets_available': self.env['assetflow.asset'].search_count([('state', '=', 'available')]),
            'assets_allocated': self.env['assetflow.asset'].search_count([('state', '=', 'allocated')]),
            'maintenance_today': self.env['assetflow.asset'].search_count([('state', '=', 'maintenance')]),
            'active_bookings': self.env['assetflow.booking'].search_count([('state', '=', 'ongoing')]),
            'pending_transfers': self.env['assetflow.transfer'].search_count([('state', '=', 'requested')]),
            'upcoming_returns': len(upcoming),
            'overdue_returns': len(overdue),
            'open_maintenance': self.env['assetflow.maintenance.request'].search_count([
                ('state', 'in', ('pending', 'approved', 'assigned', 'in_progress')),
            ]),
            'unread_notifications': self.env['assetflow.notification'].search_count([
                ('user_id', '=', self.env.user.id),
                ('is_read', '=', False),
            ]),
            'recent_overdue': [allocation_row(allocation) for allocation in overdue[:10]],
            'recent_upcoming': [allocation_row(allocation) for allocation in upcoming[:10]],
            'recent_notifications': [
                {
                    'id': notification.id,
                    'title': notification.title,
                    'body': notification.body or '',
                    'type': notification.notification_type,
                }
                for notification in notifications
            ],
            'generated_at': fields.Datetime.to_string(fields.Datetime.now()),
        }
