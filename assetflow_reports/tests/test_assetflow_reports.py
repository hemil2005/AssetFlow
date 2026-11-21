from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase


class TestAssetflowReports(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.department = cls.env['assetflow.department'].create({'name': 'IT', 'code': 'IT'})
        cls.category = cls.env['assetflow.category'].create({'name': 'Electronics', 'code': 'ELEC'})
        cls.manager_user = cls.env['res.users'].create({
            'name': 'Reports Manager', 'login': 'af_reports_manager',
            'group_ids': [(6, 0, [cls.env.ref('assetflow_base.group_assetflow_asset_manager').id])],
        })
        cls.employee_user = cls.env['res.users'].create({
            'name': 'Reports Employee', 'login': 'af_reports_employee',
            'group_ids': [(6, 0, [cls.env.ref('assetflow_base.group_assetflow_employee').id])],
        })
        cls.manager = cls.env['assetflow.employee'].create({
            'name': 'Manager', 'email': 'reports.manager@assetflow.test',
            'department_id': cls.department.id, 'user_id': cls.manager_user.id,
        })
        cls.employee = cls.env['assetflow.employee'].create({
            'name': 'Priya', 'email': 'reports.priya@assetflow.test',
            'department_id': cls.department.id, 'user_id': cls.employee_user.id,
        })
        cls.available = cls.env['assetflow.asset'].create({
            'name': 'Available Laptop', 'asset_tag': 'AF-REP-1',
            'category_id': cls.category.id, 'department_id': cls.department.id,
        })
        cls.allocated = cls.env['assetflow.asset'].create({
            'name': 'Allocated Laptop', 'asset_tag': 'AF-REP-2',
            'category_id': cls.category.id, 'department_id': cls.department.id,
        })
        cls.bookable = cls.env['assetflow.asset'].create({
            'name': 'Room B2', 'asset_tag': 'AF-REP-3',
            'category_id': cls.category.id, 'department_id': cls.department.id,
            'is_bookable': True,
        })
        cls.maintenance_asset = cls.env['assetflow.asset'].create({
            'name': 'Van', 'asset_tag': 'AF-REP-4',
            'category_id': cls.category.id, 'department_id': cls.department.id,
        })
        cls.allocated.with_user(cls.manager_user).action_allocate(
            employee=cls.employee,
            expected_return_date=fields.Date.today() + timedelta(days=2),
        )
        now = fields.Datetime.now()
        cls.env['assetflow.booking'].with_user(cls.manager_user).create({
            'asset_id': cls.bookable.id,
            'employee_id': cls.employee.id,
            'start_datetime': now - timedelta(minutes=5),
            'end_datetime': now + timedelta(hours=1),
        })
        cls.env['assetflow.maintenance.request'].with_user(cls.manager_user).create({
            'asset_id': cls.maintenance_asset.id,
            'raised_by_id': cls.manager.id,
            'name': 'Oil change',
            'description': 'Service due',
        })
        # Workflow events now create real notifications for the holder; keep
        # this fixture's unread count deterministic for the record-rule test.
        cls.env['assetflow.notification'].with_user(cls.employee_user).action_mark_all_read()
        cls.env['assetflow.notification']._notify(
            cls.employee_user, 'Test notification', 'A booking is due.',
            notification_type='system',
        )

    def test_dashboard_kpis_manager(self):
        data = self.env['assetflow.dashboard'].with_user(self.manager_user).get_kpi_data()
        self.assertEqual(data['assets_available'], 2)
        self.assertEqual(data['assets_allocated'], 1)
        self.assertEqual(data['active_bookings'], 1)
        self.assertEqual(data['open_maintenance'], 1)
        self.assertEqual(data['upcoming_returns'], 1)
        self.assertEqual(data['overdue_returns'], 0)
        self.assertEqual(data['maintenance_today'], 0)
        self.assertEqual(
            set(data),
            {
                'assets_available', 'assets_allocated', 'maintenance_today',
                'active_bookings', 'pending_transfers', 'upcoming_returns',
                'overdue_returns', 'open_maintenance', 'unread_notifications',
                'generated_at',
            },
        )
        recent = self.env['assetflow.dashboard'].with_user(self.manager_user).get_recent_activity()
        self.assertEqual(recent['recent_upcoming'][0]['asset_tag'], 'AF-REP-2')
        self.assertEqual(recent['recent_overdue'], [])
        self.assertIn('recent_log', recent)
        self.assertTrue(recent['recent_log'])
        self.assertTrue(recent['can_manage_assets'])

    def test_dashboard_respects_record_rules(self):
        data = self.env['assetflow.dashboard'].with_user(self.employee_user).get_kpi_data()
        self.assertEqual(data['assets_available'], 0)
        self.assertEqual(data['assets_allocated'], 1)
        self.assertEqual(data['active_bookings'], 1)
        self.assertEqual(data['open_maintenance'], 0)
        self.assertEqual(data['unread_notifications'], 1)
        recent = self.env['assetflow.dashboard'].with_user(self.employee_user).get_recent_activity()
        self.assertEqual(recent['recent_log'], [])
        self.assertEqual(len(recent['recent_notifications']), 1)
        self.assertFalse(recent['can_manage_assets'])

    def test_day_bounds_follow_user_timezone(self):
        dashboard = self.env['assetflow.dashboard'].with_context(tz='Asia/Kolkata')
        start, end = dashboard._day_bounds_utc(fields.Date.today())
        # IST is UTC+05:30, so the local day starts at 18:30 UTC the day before.
        self.assertEqual(start.hour, 18)
        self.assertEqual(start.minute, 30)
        self.assertEqual(end - start, timedelta(days=1))

    def test_kpi_query_budget(self):
        # 12 count queries plus ORM flush overhead; a regression that loads
        # allocations per record would blow far past this.
        with self.assertQueryCount(40):
            self.env['assetflow.dashboard'].with_user(self.manager_user).get_kpi_data()

    def test_near_retirement_filter(self):
        old_asset = self.env['assetflow.asset'].create({
            'name': 'Old Laptop', 'asset_tag': 'AF-REP-8',
            'category_id': self.category.id, 'department_id': self.department.id,
            'acquisition_date': fields.Date.today() - timedelta(days=365 * 6),
        })
        self.assertTrue(old_asset.is_near_retirement)
        found = self.env['assetflow.asset'].search([('is_near_retirement', '=', True)])
        self.assertIn(old_asset, found)
        self.assertNotIn(self.available, found)

    def test_dashboard_is_read_only_for_users(self):
        dashboard = self.env['assetflow.dashboard'].with_user(self.employee_user)
        self.assertTrue(dashboard.has_access('read'))
        self.assertFalse(dashboard.has_access('write'))

    def test_department_head_gets_rule_filtered_activity(self):
        head_user = self.env['res.users'].create({
            'name': 'Reports Head', 'login': 'af_reports_head',
            'group_ids': [(6, 0, [self.env.ref(
                'assetflow_base.group_assetflow_department_head',
            ).id])],
        })
        self.env['assetflow.employee'].create({
            'name': 'Reports Head', 'email': 'reports.head@assetflow.test',
            'department_id': self.department.id, 'user_id': head_user.id,
        })
        recent = self.env['assetflow.dashboard'].with_user(head_user).get_recent_activity()
        self.assertTrue(recent['recent_log'])
        self.assertFalse(recent['can_manage_assets'])

    def test_department_report_action_exists(self):
        report = self.env.ref('assetflow_reports.action_report_department_allocation')
        self.assertEqual(report.model, 'assetflow.department')
        self.assertEqual(report.report_type, 'qweb-pdf')

    def test_department_report_renders(self):
        report = self.env.ref('assetflow_reports.action_report_department_allocation')
        html, _report_type = self.env['ir.actions.report']._render_qweb_html(
            report, self.department.ids,
        )
        if isinstance(html, bytes):
            html = html.decode()
        self.assertIn('Department Allocation Summary', html)
        self.assertIn('AF-REP-1', html)

    def test_booking_heatmap_buckets(self):
        now = fields.Datetime.now()
        tomorrow = now + timedelta(days=1)
        first = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
        second = tomorrow.replace(hour=15, minute=0, second=0, microsecond=0)
        room_a = self.env['assetflow.asset'].create({
            'name': 'Room Heat A', 'asset_tag': 'AF-REP-5',
            'category_id': self.category.id, 'department_id': self.department.id,
            'is_bookable': True,
        })
        room_b = self.env['assetflow.asset'].create({
            'name': 'Room Heat B', 'asset_tag': 'AF-REP-6',
            'category_id': self.category.id, 'department_id': self.department.id,
            'is_bookable': True,
        })
        for room, start in ((room_a, first), (room_b, second)):
            self.env['assetflow.booking'].with_user(self.manager_user).create({
                'asset_id': room.id,
                'employee_id': self.employee.id,
                'start_datetime': start,
                'end_datetime': start + timedelta(hours=1),
            })

        heatmap = self.env['assetflow.dashboard'].with_user(self.manager_user).get_booking_heatmap()
        self.assertEqual(len(heatmap['rows']), 7)
        self.assertTrue(all(len(row['hours']) == 24 for row in heatmap['rows']))
        self.assertGreaterEqual(heatmap['max'], 1)
        self.assertGreaterEqual(heatmap['total'], 3)

        for start in (first, second):
            day = start.isoweekday() % 7
            self.assertGreaterEqual(heatmap['rows'][day]['hours'][start.hour], 1)

    def test_booking_heatmap_respects_record_rules(self):
        now = fields.Datetime.now()
        tomorrow = now + timedelta(days=1)
        room = self.env['assetflow.asset'].create({
            'name': 'Room Heat C', 'asset_tag': 'AF-REP-7',
            'category_id': self.category.id, 'department_id': self.department.id,
            'is_bookable': True,
        })
        start = tomorrow.replace(hour=11, minute=0, second=0, microsecond=0)
        self.env['assetflow.booking'].with_user(self.manager_user).create({
            'asset_id': room.id,
            'employee_id': self.manager.id,
            'start_datetime': start,
            'end_datetime': start + timedelta(hours=1),
        })

        manager_heatmap = self.env['assetflow.dashboard'].with_user(self.manager_user).get_booking_heatmap()
        employee_heatmap = self.env['assetflow.dashboard'].with_user(self.employee_user).get_booking_heatmap()
        self.assertGreater(manager_heatmap['total'], employee_heatmap['total'])
        day = start.isoweekday() % 7
        self.assertEqual(employee_heatmap['rows'][day]['hours'][start.hour], 0)

    def test_dashboard_action_is_registered(self):
        action = self.env.ref('assetflow_reports.action_assetflow_dashboard')
        self.assertEqual(action.tag, 'assetflow_reports.dashboard')
