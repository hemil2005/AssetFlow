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
        self.assertIn('recent_upcoming', data)
        self.assertIn('recent_notifications', data)

    def test_dashboard_respects_record_rules(self):
        data = self.env['assetflow.dashboard'].with_user(self.employee_user).get_kpi_data()
        self.assertEqual(data['assets_available'], 0)
        self.assertEqual(data['assets_allocated'], 1)
        self.assertEqual(data['active_bookings'], 1)
        self.assertEqual(data['open_maintenance'], 0)
        self.assertEqual(data['unread_notifications'], 1)

    def test_dashboard_is_read_only_for_users(self):
        dashboard = self.env['assetflow.dashboard'].with_user(self.employee_user)
        self.assertTrue(dashboard.has_access('read'))
        self.assertFalse(dashboard.has_access('write'))

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
