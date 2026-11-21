from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user
from odoo.tools import mute_logger


class TestAssetflowMaintenance(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.department = cls.env['assetflow.department'].create({'name': 'IT', 'code': 'IT'})
        cls.other_department = cls.env['assetflow.department'].create({'name': 'Ops', 'code': 'OPS'})
        cls.category = cls.env['assetflow.category'].create({'name': 'Laptops', 'code': 'LAP'})

        cls.manager_user = new_test_user(
            cls.env, login='af_maint_manager',
            groups='base.group_user,assetflow_base.group_assetflow_asset_manager',
        )
        cls.employee_user = new_test_user(
            cls.env, login='af_maint_employee',
            groups='base.group_user,assetflow_base.group_assetflow_employee',
        )
        cls.other_user = new_test_user(
            cls.env, login='af_maint_other',
            groups='base.group_user,assetflow_base.group_assetflow_employee',
        )
        cls.head_user = new_test_user(
            cls.env, login='af_maint_head',
            groups='base.group_user,assetflow_base.group_assetflow_department_head',
        )
        cls.technician_user = new_test_user(
            cls.env, login='af_maint_technician',
            groups='base.group_user,assetflow_base.group_assetflow_employee',
        )

        cls.manager = cls.env['assetflow.employee'].create({
            'name': 'Manager', 'email': 'maint.manager@assetflow.test',
            'department_id': cls.department.id, 'user_id': cls.manager_user.id,
        })
        cls.employee = cls.env['assetflow.employee'].create({
            'name': 'Priya', 'email': 'maint.priya@assetflow.test',
            'department_id': cls.department.id, 'user_id': cls.employee_user.id,
        })
        cls.other_employee = cls.env['assetflow.employee'].create({
            'name': 'Raj', 'email': 'maint.raj@assetflow.test',
            'department_id': cls.other_department.id, 'user_id': cls.other_user.id,
        })
        cls.head = cls.env['assetflow.employee'].create({
            'name': 'Head', 'email': 'maint.head@assetflow.test',
            'department_id': cls.department.id, 'user_id': cls.head_user.id,
        })
        cls.technician = cls.env['assetflow.employee'].create({
            'name': 'Tech', 'email': 'maint.tech@assetflow.test',
            'department_id': cls.department.id, 'user_id': cls.technician_user.id,
        })

        cls.asset = cls._create_asset('Laptop', 'AF-9001')
        cls.asset.with_user(cls.manager_user).action_allocate(employee=cls.employee)

    @classmethod
    def _create_asset(cls, name, tag, department=None):
        return cls.env['assetflow.asset'].create({
            'name': name,
            'asset_tag': tag,
            'category_id': cls.category.id,
            'department_id': (department or cls.department).id,
        })

    def _raise(self, asset=None, user=None, **values):
        user = user or self.employee_user
        vals = {
            'asset_id': (asset or self.asset).id,
            'name': 'Broken screen',
            'description': 'The screen flickers.',
            'priority': 'medium',
        }
        vals.update(values)
        return self.env['assetflow.maintenance.request'].with_user(user).create(vals)

    def _approved(self):
        request = self._raise()
        request.with_user(self.manager_user).action_approve()
        return request

    def _in_progress(self, request):
        request.with_user(self.manager_user).action_assign(self.technician)
        request.with_user(self.technician_user).action_start()
        return request

    def _notifications(self, user, request):
        return self.env['assetflow.notification'].sudo().search([
            ('user_id', '=', user.id),
            ('res_model', '=', request._name),
            ('res_id', '=', request.id),
        ])

    def test_pending_does_not_change_asset(self):
        request = self._raise()
        self.assertEqual(request.state, 'pending')
        self.assertEqual(request.reference[:3], 'MR-')
        self.assertFalse(request.previous_asset_state)
        self.assertEqual(self.asset.state, 'allocated')
        self.assertTrue(self._notifications(self.manager_user, request))

    def test_approval_flips_asset_and_records_previous_state(self):
        request = self._approved()
        self.assertEqual(request.state, 'approved')
        self.assertEqual(request.approved_by, self.manager_user)
        self.assertEqual(request.previous_asset_state, 'allocated')
        self.assertEqual(self.asset.state, 'maintenance')
        self.assertTrue(self._notifications(self.employee_user, request))

    def test_rejection_requires_reason_and_leaves_asset(self):
        request = self._raise()
        with self.assertRaises(UserError):
            request.with_user(self.manager_user).action_reject()
        self.assertEqual(self.asset.state, 'allocated')
        request.with_user(self.manager_user).action_reject(reason='Covered by warranty')
        self.assertEqual(request.state, 'rejected')
        self.assertEqual(request.rejection_reason, 'Covered by warranty')
        self.assertEqual(self.asset.state, 'allocated')
        self.assertTrue(self._notifications(self.employee_user, request))

    def test_only_manager_or_admin_approves(self):
        request = self._raise()
        with self.assertRaises(UserError):
            request.with_user(self.employee_user).action_approve()
        with self.assertRaises(UserError):
            request.with_user(self.head_user).action_approve()
        self.assertEqual(request.state, 'pending')

    def test_technician_flow_resolves_and_restores_allocated(self):
        request = self._approved()
        request.with_user(self.manager_user).action_assign(self.technician)
        self.assertEqual(request.state, 'assigned')
        request.with_user(self.technician_user).action_start()
        self.assertEqual(request.state, 'in_progress')
        request.with_user(self.technician_user).action_resolve(notes='Replaced the panel')
        self.assertEqual(request.state, 'resolved')
        self.assertEqual(request.resolution_notes, 'Replaced the panel')
        self.assertEqual(self.asset.state, 'allocated')
        self.assertTrue(self._notifications(self.employee_user, request))
        self.assertTrue(request.message_ids)

    def test_resolve_requires_notes(self):
        request = self._in_progress(self._approved())
        with self.assertRaises(UserError):
            request.with_user(self.technician_user).action_resolve()
        self.assertEqual(request.state, 'in_progress')

    def test_resolve_restores_available_without_allocation(self):
        asset = self._create_asset('Spare monitor', 'AF-9002')
        request = self._raise(asset=asset, user=self.manager_user)
        request.with_user(self.manager_user).action_approve()
        self.assertEqual(request.previous_asset_state, 'available')
        request.with_user(self.manager_user).action_assign(self.technician)
        request.with_user(self.technician_user).action_start()
        request.with_user(self.technician_user).action_resolve(notes='Cable replaced')
        self.assertEqual(asset.state, 'available')

    def test_one_open_request_per_asset(self):
        self._raise()
        with self.assertRaises(ValidationError):
            self._raise(user=self.manager_user, name='Second issue')

    @mute_logger('odoo.sql_db')
    def test_database_rejects_second_open_request(self):
        request = self._raise()
        with self.assertRaises(Exception), self.env.cr.savepoint():
            self.env.cr.execute("""
                INSERT INTO assetflow_maintenance_request
                    (asset_id, raised_by_id, name, description, priority, state, reference,
                     active, create_date, write_date)
                VALUES (%s, %s, 'Duplicate', 'Duplicate', 'medium', 'pending', 'MR-DUP',
                        true, now() at time zone 'utc', now() at time zone 'utc')
            """, (self.asset.id, self.employee.id))
        self.assertEqual(request.state, 'pending')

    def test_direct_state_write_rejected(self):
        request = self._raise()
        with self.assertRaises(UserError):
            request.with_user(self.manager_user).write({'state': 'approved'})
        self.assertEqual(request.state, 'pending')

    def test_employee_cannot_see_other_request(self):
        other_asset = self._create_asset('Ops radio', 'AF-9003', department=self.other_department)
        other_asset.with_user(self.manager_user).action_allocate(employee=self.other_employee)
        other_request = self._raise(asset=other_asset, user=self.other_user)
        visible = self.env['assetflow.maintenance.request'].with_user(self.employee_user).search([])
        self.assertNotIn(other_request, visible)

    def test_employee_cannot_raise_for_foreign_asset(self):
        other_asset = self._create_asset('Ops radio', 'AF-9004', department=self.other_department)
        other_asset.with_user(self.manager_user).action_allocate(employee=self.other_employee)
        with self.assertRaises(UserError):
            self._raise(asset=other_asset)

    def test_technician_sees_assigned_request(self):
        request = self._approved()
        request.with_user(self.manager_user).action_assign(self.technician)
        visible = self.env['assetflow.maintenance.request'].with_user(self.technician_user).search([])
        self.assertIn(request, visible)
        hidden = self.env['assetflow.maintenance.request'].with_user(self.other_user).search([])
        self.assertNotIn(request, hidden)

    def test_history_links_request_to_asset(self):
        request = self._in_progress(self._approved())
        request.with_user(self.technician_user).action_resolve(notes='Cleaned the fan')
        self.assertIn(request, self.asset.maintenance_ids)
        self.assertGreaterEqual(self.asset.history_count, 1)

    def test_aging_cron_notifies_once_per_day(self):
        request = self._raise()
        self.env.cr.execute("""
            UPDATE assetflow_maintenance_request
               SET create_date = now() at time zone 'utc' - interval '3 days'
             WHERE id = %s
        """, (request.id,))
        self.env['assetflow.maintenance.request'].invalidate_model(['create_date'])
        self.env['assetflow.maintenance.request']._cron_flag_aging_requests()
        self.env['assetflow.maintenance.request']._cron_flag_aging_requests()
        notifications = self.env['assetflow.notification'].sudo().search([
            ('user_id', '=', self.manager_user.id),
            ('res_model', '=', request._name),
            ('res_id', '=', request.id),
            ('title', 'like', 'Maintenance pending'),
        ])
        self.assertEqual(len(notifications), 1)

    def test_booking_conflict_blocks_approval(self):
        if not self.env['ir.model'].sudo().search_count([('model', '=', 'assetflow.booking')]):
            self.skipTest('assetflow_booking is not installed on this branch')
        # A shared resource with an ongoing booking: booking create sets it ongoing and
        # reserves the asset, and maintenance approval must refuse while it runs.
        asset = self._create_asset('Meeting room B2', 'AF-9005')
        asset.is_bookable = True
        request = self._raise(asset=asset, user=self.manager_user)
        now = fields.Datetime.now()
        self.env['assetflow.booking'].create({
            'asset_id': asset.id,
            'employee_id': self.employee.id,
            'start_datetime': now,
            'end_datetime': now + timedelta(hours=1),
        })
        with self.assertRaises(UserError):
            request.with_user(self.manager_user).action_approve()
        self.assertEqual(asset.state, 'reserved')
