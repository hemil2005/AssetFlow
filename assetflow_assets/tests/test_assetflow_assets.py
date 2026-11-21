from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase
from odoo.tools import mute_logger


class TestAssetflowAssets(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.department = cls.env['assetflow.department'].create({'name': 'IT', 'code': 'IT'})
        cls.category = cls.env['assetflow.category'].create({'name': 'Electronics', 'code': 'ELEC'})
        cls.manager = cls.env['res.users'].create({
            'name': 'Manager', 'login': 'af_manager_test',
            'group_ids': [(6, 0, [cls.env.ref('assetflow_base.group_assetflow_asset_manager').id])],
        })
        cls.employee_user = cls.env['res.users'].create({
            'name': 'Holder', 'login': 'af_holder_test',
            'group_ids': [(6, 0, [cls.env.ref('assetflow_base.group_assetflow_employee').id])],
        })
        cls.employee = cls.env['assetflow.employee'].create({
            'name': 'Priya', 'email': 'priya@assetflow.test',
            'department_id': cls.department.id, 'user_id': cls.employee_user.id,
        })
        cls.other_employee = cls.env['assetflow.employee'].create({
            'name': 'Raj', 'email': 'raj@assetflow.test', 'department_id': cls.department.id,
        })
        cls.asset = cls.env['assetflow.asset'].create({
            'name': 'Laptop', 'asset_tag': 'AF-0114', 'category_id': cls.category.id,
            'department_id': cls.department.id,
        })

    def test_allocation_blocks_double_allocation(self):
        asset = self.asset.with_user(self.manager)
        asset.action_allocate(employee=self.employee)
        self.assertEqual(asset.state, 'allocated')
        with self.assertRaises(ValidationError):
            asset.action_allocate(employee=self.other_employee)
        self.assertEqual(asset.holder_employee_id, self.employee)

    @mute_logger('odoo.sql_db')
    def test_direct_second_active_allocation_rejected_by_database(self):
        self.asset.with_user(self.manager).action_allocate(employee=self.employee)
        with self.assertRaises(Exception), self.env.cr.savepoint():
            self.env['assetflow.allocation'].create({
                'asset_id': self.asset.id, 'employee_id': self.other_employee.id,
            })

    def test_return_requires_condition_and_notes(self):
        asset = self.asset.with_user(self.manager)
        asset.action_allocate(employee=self.employee)
        with self.assertRaises(UserError):
            asset.action_return()
        asset.action_return(condition='good', notes='Returned in good condition')
        self.assertEqual(asset.state, 'available')
        allocation = asset.allocation_ids.filtered(lambda a: a.state == 'returned')
        self.assertEqual(allocation.checkin_condition, 'good')

    def test_state_cannot_be_written_directly(self):
        asset = self.asset.with_user(self.manager)
        asset.action_allocate(employee=self.employee)
        allocation = asset.allocation_ids
        with self.assertRaises(UserError):
            allocation.with_context(allow_state_write=False).write({'state': 'returned'})

    def test_create_cannot_forge_lifecycle_fields(self):
        with self.assertRaises(UserError):
            self.env['assetflow.asset'].with_user(self.manager).create({
                'name': 'Forged lost', 'asset_tag': 'AF-FORGED-1',
                'category_id': self.category.id, 'state': 'lost',
            })
        with self.assertRaises(UserError):
            self.env['assetflow.asset'].with_user(self.manager).create({
                'name': 'Forged holder', 'asset_tag': 'AF-FORGED-2',
                'category_id': self.category.id, 'holder_employee_id': self.employee.id,
            })

    def test_active_allocation_cannot_be_deleted(self):
        asset = self.asset.with_user(self.manager)
        asset.action_allocate(employee=self.employee)
        with self.assertRaises(UserError):
            asset.allocation_ids.unlink()

    def test_transfer_requires_active_allocation(self):
        transfer = self.env['assetflow.transfer'].with_user(self.manager).create({
            'asset_id': self.asset.id, 'to_employee_id': self.other_employee.id,
            'reason': 'Move to Raj',
        })
        with self.assertRaises(UserError):
            transfer.action_approve()

    def test_transfer_reallocates_asset(self):
        asset = self.asset.with_user(self.manager)
        asset.action_allocate(employee=self.employee)
        transfer = self.env['assetflow.transfer'].with_user(self.manager).create({
            'asset_id': self.asset.id, 'to_employee_id': self.other_employee.id,
        })
        transfer.action_approve()
        self.assertEqual(transfer.state, 'approved')
        self.assertEqual(asset.holder_employee_id, self.other_employee)

    def test_destructive_transition_requires_admin_and_reason(self):
        asset = self.asset.with_user(self.manager)
        with self.assertRaises(UserError):
            asset.action_dispose(reason='broken')
        admin = self.env.ref('base.user_admin')
        with self.assertRaises(UserError):
            self.asset.with_user(admin).action_dispose()
        self.asset.with_user(admin).action_dispose(reason='broken beyond repair')
        self.assertEqual(self.asset.state, 'disposed')

    def test_employee_cannot_allocate(self):
        with self.assertRaises(UserError):
            self.asset.with_user(self.employee_user).action_allocate(employee=self.employee)

    def test_manager_cannot_write_state_or_tag_directly(self):
        with self.assertRaises(UserError):
            self.asset.with_user(self.manager).write({'state': 'disposed'})
        with self.assertRaises(UserError):
            self.asset.with_user(self.manager).write({'asset_tag': 'HACK-9'})

    def test_past_expected_return_is_overdue_not_rejected(self):
        yesterday = fields.Date.to_string(fields.Date.today() - timedelta(days=1))
        with self.assertRaises(UserError):
            self.asset.with_user(self.manager).write({'expected_return_date': yesterday})
        asset = self.asset.with_user(self.manager)
        asset.action_allocate(employee=self.employee, expected_return_date=yesterday)
        self.assertEqual(asset.expected_return_date, fields.Date.from_string(yesterday))
        self.assertTrue(asset.is_overdue)
        # The workflow write guard is untouched: only the date restriction was removed.
        asset.with_context(allow_state_write=True).write({'expected_return_date': yesterday})
        self.assertTrue(asset.is_overdue)

    def test_allocation_notifies_holder_and_department_head(self):
        head_user = self.env['res.users'].create({
            'name': 'Head User', 'login': 'af_head_notify',
            'group_ids': [(6, 0, [self.env.ref('assetflow_base.group_assetflow_department_head').id])],
        })
        self.env['assetflow.employee'].create({
            'name': 'Head', 'email': 'head@assetflow.test',
            'department_id': self.department.id, 'user_id': head_user.id,
        })
        self.asset.with_user(self.manager).action_allocate(employee=self.employee)
        notifications = self.env['assetflow.notification'].sudo()
        for user in (self.employee_user, head_user):
            self.assertTrue(notifications.search_count([
                ('user_id', '=', user.id),
                ('res_model', '=', 'assetflow.asset'),
                ('res_id', '=', self.asset.id),
            ]))

    def test_transfer_decision_notifies_requester(self):
        self.asset.with_user(self.manager).action_allocate(employee=self.employee)
        transfer = self.env['assetflow.transfer'].with_user(self.employee_user).create({
            'asset_id': self.asset.id, 'to_employee_id': self.other_employee.id,
            'reason': 'Test transfer',
        })
        transfer.with_user(self.manager).action_approve()
        self.assertTrue(self.env['assetflow.notification'].sudo().search_count([
            ('user_id', '=', self.employee_user.id),
            ('res_model', '=', 'assetflow.transfer'),
            ('res_id', '=', transfer.id),
        ]))

    def test_allocation_derives_department_from_employee(self):
        self.asset.with_user(self.manager).action_allocate(employee=self.employee)
        allocation = self.asset.allocation_ids
        self.assertEqual(allocation.department_id, self.department)

    def test_active_allocation_edit_syncs_asset(self):
        asset = self.asset.with_user(self.manager)
        asset.action_allocate(employee=self.employee)
        allocation = asset.allocation_ids
        new_date = fields.Date.today() + timedelta(days=3)
        allocation.write({
            'employee_id': self.other_employee.id,
            'expected_return_date': new_date,
        })
        self.assertEqual(asset.holder_employee_id, self.other_employee)
        self.assertEqual(asset.expected_return_date, new_date)

    def test_employee_cannot_transfer_an_asset_they_do_not_hold(self):
        bookable = self.env['assetflow.asset'].with_user(self.manager).create({
            'name': 'Room', 'asset_tag': 'AF-ROOM-TEST', 'category_id': self.category.id,
            'is_bookable': True,
        })
        with self.assertRaises(UserError):
            self.env['assetflow.transfer'].with_user(self.employee_user).create({
                'asset_id': bookable.id, 'to_employee_id': self.other_employee.id,
            })

    def test_employee_cannot_see_other_allocation(self):
        self.asset.with_user(self.manager).action_allocate(employee=self.employee)
        other_user = self.env['res.users'].create({
            'name': 'Other', 'login': 'af_other_test',
            'group_ids': [(6, 0, [self.env.ref('assetflow_base.group_assetflow_employee').id])],
        })
        visible = self.env['assetflow.allocation'].with_user(other_user).search([])
        self.assertNotIn(self.asset.allocation_ids, visible)

    def test_overdue_cron_notifies_once_per_day(self):
        head_user = self.env['res.users'].create({
            'name': 'IT Head', 'login': 'af_head_test',
            'group_ids': [(6, 0, [self.env.ref('assetflow_base.group_assetflow_employee').id])],
        })
        head = self.env['assetflow.employee'].create({
            'name': 'Dev Head', 'email': 'dev.head@assetflow.test',
            'department_id': self.department.id, 'user_id': head_user.id,
        })
        self.department.head_id = head

        asset = self.asset.with_user(self.manager)
        asset.action_allocate(
            employee=self.employee,
            expected_return_date=fields.Date.today() - timedelta(days=1),
        )
        allocation = asset.allocation_ids
        notification_model = self.env['assetflow.notification']
        domain = [
            ('notification_type', '=', 'overdue_return'),
            ('res_model', '=', 'assetflow.allocation'),
            ('res_id', '=', allocation.id),
        ]

        self.env['assetflow.allocation']._cron_flag_overdue_allocations()
        notifications = notification_model.search(domain)
        self.assertIn(self.employee_user, notifications.user_id)
        self.assertIn(self.manager, notifications.user_id)
        self.assertIn(head_user, notifications.user_id)
        self.assertEqual(allocation.last_overdue_notified_on, fields.Date.today())
        chatter_count = len(asset.message_ids)

        self.env['assetflow.allocation']._cron_flag_overdue_allocations()
        self.assertEqual(notification_model.search_count(domain), len(notifications))
        self.assertEqual(len(asset.message_ids), chatter_count)

    def test_overdue_cron_ignores_current_and_returned_allocations(self):
        asset = self.asset.with_user(self.manager)
        asset.action_allocate(employee=self.employee)
        allocation = asset.allocation_ids
        self.env['assetflow.allocation']._cron_flag_overdue_allocations()
        self.assertFalse(allocation.last_overdue_notified_on)
        self.assertEqual(self.env['assetflow.notification'].search_count([
            ('notification_type', '=', 'overdue_return'),
            ('res_id', '=', allocation.id),
        ]), 0)

        allocation.write({'expected_return_date': fields.Date.today() - timedelta(days=1)})
        asset.action_return(condition='good', notes='Late but fine')
        self.env['assetflow.allocation']._cron_flag_overdue_allocations()
        self.assertFalse(allocation.last_overdue_notified_on)
