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

    @mute_logger('odoo.sql_db')
    def test_asset_rejects_past_expected_return(self):
        with self.assertRaises(UserError):
            self.asset.with_user(self.manager).write({'expected_return_date': '2020-01-01'})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.asset.with_user(self.manager).with_context(allow_state_write=True).write({
                'expected_return_date': '2020-01-01',
            })

    def test_allocation_derives_department_from_employee(self):
        self.asset.with_user(self.manager).action_allocate(employee=self.employee)
        allocation = self.asset.allocation_ids
        self.assertEqual(allocation.department_id, self.department)

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
