from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user


class TestActivityLogScope(TransactionCase):
    """A Department Head reads their own department's activity, nothing else."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Department = cls.env['assetflow.department']
        cls.department_a = Department.create({'name': 'Log Dept A', 'code': 'LOG-A'})
        cls.department_b = Department.create({'name': 'Log Dept B', 'code': 'LOG-B'})

        cls.head_user = new_test_user(
            cls.env, login='af_log_head',
            groups='base.group_user,assetflow_base.group_assetflow_department_head',
        )
        cls.employee_a_user = new_test_user(
            cls.env, login='af_log_employee_a',
            groups='base.group_user,assetflow_base.group_assetflow_employee',
        )
        cls.employee_b_user = new_test_user(
            cls.env, login='af_log_employee_b',
            groups='base.group_user,assetflow_base.group_assetflow_employee',
        )
        cls.manager_user = new_test_user(
            cls.env, login='af_log_manager',
            groups='base.group_user,assetflow_base.group_assetflow_asset_manager',
        )
        Employee = cls.env['assetflow.employee']
        cls.head_employee = Employee.create({
            'name': 'Head A', 'email': 'head.a@assetflow.test',
            'department_id': cls.department_a.id, 'user_id': cls.head_user.id,
        })
        cls.employee_a = Employee.create({
            'name': 'Employee A', 'email': 'employee.a@assetflow.test',
            'department_id': cls.department_a.id, 'user_id': cls.employee_a_user.id,
        })
        cls.employee_b = Employee.create({
            'name': 'Employee B', 'email': 'employee.b@assetflow.test',
            'department_id': cls.department_b.id, 'user_id': cls.employee_b_user.id,
        })

        Log = cls.env['assetflow.activity.log']
        cls.log_a = Log._log_activity('update', cls.employee_a, 'A record')
        cls.log_b = Log._log_activity('update', cls.employee_b, 'B record')
        # A row whose subject is in B but whose actor is in A: the head rule covers
        # the department's people as well as its records.
        cls.log_actor_a = Log.with_user(cls.employee_a_user)._log_activity(
            'update', cls.department_b, 'B record touched by A',
        )

    def test_head_sees_only_own_department(self):
        seen = self.env['assetflow.activity.log'].with_user(self.head_user).search([])
        self.assertIn(self.log_a, seen)
        self.assertIn(self.log_actor_a, seen)
        self.assertNotIn(self.log_b, seen)

    def test_employee_has_no_activity_log_access(self):
        with self.assertRaises(AccessError):
            self.env['assetflow.activity.log'].with_user(self.employee_a_user).search([])

    def test_head_is_read_only(self):
        Log = self.env['assetflow.activity.log'].with_user(self.head_user)
        with self.assertRaises(AccessError):
            Log.create({'user_id': self.head_user.id, 'action': 'update'})
        with self.assertRaises(AccessError):
            self.log_a.with_user(self.head_user).write({'description': 'changed'})
        with self.assertRaises(AccessError):
            self.log_a.with_user(self.head_user).unlink()

    def test_manager_still_sees_everything(self):
        seen = self.env['assetflow.activity.log'].with_user(self.manager_user).search([])
        self.assertIn(self.log_a, seen)
        self.assertIn(self.log_b, seen)
        self.assertIn(self.log_actor_a, seen)

    def test_log_without_record_uses_actor_department(self):
        entry = self.env['assetflow.activity.log'].with_user(self.head_user)._log_activity(
            'update', model_name='res.users', res_id=self.head_user.id, description='system note',
        )
        self.assertEqual(entry.department_id, self.department_a)
