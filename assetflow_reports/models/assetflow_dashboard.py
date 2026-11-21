from datetime import timedelta

from babel import Locale
from babel.dates import get_day_names

from odoo import api, fields, models


class AssetflowDashboard(models.TransientModel):
    _name = 'assetflow.dashboard'
    _description = 'AssetFlow Dashboard'

    @api.private
    def _allocation_row(self, allocation):
        return {
            'asset_id': allocation.asset_id.id,
            'asset_tag': allocation.asset_id.asset_tag,
            'asset_name': allocation.asset_id.name,
            'holder': allocation.employee_id.name or allocation.department_id.name or '',
            'expected_return_date': fields.Date.to_string(allocation.expected_return_date),
        }

    @api.model
    def get_kpi_data(self):
        """Return exactly the KPI contract keys (plus ``generated_at``)."""
        today = fields.Date.context_today(self)
        week_end = today + timedelta(days=7)
        allocation_model = self.env['assetflow.allocation']
        active = ('state', '=', 'active')

        maintenance_assets = self.env['assetflow.asset'].search_count([('state', '=', 'maintenance')])
        day_start = fields.Datetime.to_datetime(today)
        day_end = day_start + timedelta(days=1)
        approved_today_ids = self.env['assetflow.maintenance.request'].search([
            ('state', 'in', ('approved', 'assigned', 'in_progress')),
            ('approved_at', '>=', day_start),
            ('approved_at', '<', day_end),
        ]).asset_id.ids
        maintenance_today = maintenance_assets
        if approved_today_ids:
            extra = self.env['assetflow.asset'].search_count([
                ('state', '!=', 'maintenance'),
                ('id', 'in', approved_today_ids),
            ])
            maintenance_today += extra

        return {
            'assets_available': self.env['assetflow.asset'].search_count([('state', '=', 'available')]),
            'assets_allocated': self.env['assetflow.asset'].search_count([('state', '=', 'allocated')]),
            'maintenance_today': maintenance_today,
            'active_bookings': self.env['assetflow.booking'].search_count([('state', '=', 'ongoing')]),
            'pending_transfers': self.env['assetflow.transfer'].search_count([('state', '=', 'requested')]),
            'upcoming_returns': allocation_model.search_count([
                active,
                ('expected_return_date', '>=', today),
                ('expected_return_date', '<=', week_end),
            ]),
            'overdue_returns': allocation_model.search_count([
                active,
                ('expected_return_date', '<', today),
            ]),
            'open_maintenance': self.env['assetflow.maintenance.request'].search_count([
                ('state', 'in', ('pending', 'approved', 'assigned', 'in_progress')),
            ]),
            'unread_notifications': self.env['assetflow.notification'].search_count([
                ('user_id', '=', self.env.user.id),
                ('is_read', '=', False),
            ]),
            'generated_at': fields.Datetime.to_string(fields.Datetime.now()),
        }

    @api.model
    def get_recent_activity(self, limit=10):
        """Recent overdue/upcoming allocations, unread notifications, log rows."""
        limit = min(int(limit or 10), 50)
        today = fields.Date.context_today(self)
        week_end = today + timedelta(days=7)
        allocation_model = self.env['assetflow.allocation']
        base_domain = [('state', '=', 'active')]

        overdue = allocation_model.search(
            base_domain + [('expected_return_date', '<', today)],
            order='expected_return_date, id', limit=limit,
        )
        upcoming = allocation_model.search(
            base_domain + [
                ('expected_return_date', '>=', today),
                ('expected_return_date', '<=', week_end),
            ],
            order='expected_return_date, id', limit=limit,
        )
        notifications = self.env['assetflow.notification'].search([
            ('user_id', '=', self.env.user.id),
            ('is_read', '=', False),
        ], limit=limit, order='create_date desc')
        is_manager = self.env.user.has_group('assetflow_base.group_assetflow_asset_manager') or (
            self.env.user.has_group('assetflow_base.group_assetflow_admin')
        )
        log_entries = self.env['assetflow.activity.log']
        if is_manager:
            log_entries = log_entries.search([], limit=limit, order='timestamp desc')

        return {
            'recent_overdue': [self._allocation_row(allocation) for allocation in overdue],
            'recent_upcoming': [self._allocation_row(allocation) for allocation in upcoming],
            'recent_notifications': [
                {
                    'id': notification.id,
                    'title': notification.title,
                    'body': notification.body or '',
                    'type': notification.notification_type,
                }
                for notification in notifications
            ],
            'recent_log': [
                {
                    'id': entry.id,
                    'action': entry.action,
                    'description': entry.description or '',
                    'when': fields.Datetime.to_string(entry.timestamp),
                }
                for entry in log_entries
            ],
            'can_manage_assets': self.env.user.has_group(
                'assetflow_base.group_assetflow_asset_manager'
            ) or self.env.user.has_group('assetflow_base.group_assetflow_admin'),
            'generated_at': fields.Datetime.to_string(fields.Datetime.now()),
        }

    @api.model
    def get_booking_heatmap(self, date_from=None, date_to=None):
        """Bookings grouped by weekday and hour of day.

        One ``_read_group`` query, rule-filtered: an employee sees their own
        bookings, a manager sees every booking. Day index 0 is the first day
        of the week in the current user's locale.
        """
        today = fields.Date.context_today(self)
        if date_from:
            date_from = fields.Date.to_date(date_from)
        else:
            date_from = today - timedelta(weeks=12)
        date_to = fields.Date.to_date(date_to) if date_to else today + timedelta(days=7)
        if date_to < date_from:
            date_from, date_to = date_to, date_from

        start = fields.Datetime.to_datetime(date_from)
        end = fields.Datetime.to_datetime(date_to) + timedelta(days=1)
        groups = self.env['assetflow.booking']._read_group(
            [
                ('state', '!=', 'cancelled'),
                ('start_datetime', '>=', start),
                ('start_datetime', '<', end),
            ],
            ['start_datetime:day_of_week', 'start_datetime:hour_number'],
            ['id:count'],
        )

        grid = [[0] * 24 for _ in range(7)]
        for day, hour, count in groups:
            grid[int(day) % 7][int(hour) % 24] += count

        lang = self.env.lang or 'en_US'
        try:
            locale = Locale.parse(lang)
        except (ValueError, TypeError):
            locale = Locale.parse('en_US')
        names = [get_day_names('abbreviated', locale=locale)[index] for index in range(7)]
        first = locale.first_week_day
        labels = names[first:] + names[:first]

        total = sum(sum(row) for row in grid)
        return {
            'rows': [
                {'day': day, 'label': labels[day], 'hours': hours}
                for day, hours in enumerate(grid)
            ],
            'max': max((max(row) for row in grid), default=0),
            'total': total,
            'date_from': fields.Date.to_string(date_from),
            'date_to': fields.Date.to_string(date_to),
        }
