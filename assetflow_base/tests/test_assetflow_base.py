from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase
from odoo.tools import mute_logger


class TestAssetflowBase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.department = cls.env['assetflow.department'].create({
            'name': 'IT', 'code': 'IT',
        })
        cls.employee_user = cls.env['res.users'].create({
            'name': 'Employee User',
            'login': 'af_base_employee',
            'group_ids': [(6, 0, [cls.env.ref('assetflow_base.group_assetflow_employee').id])],
        })
        cls.employee = cls.env['assetflow.employee'].create({
            'name': 'Priya',
            'email': 'Priya@Example.COM',
            'department_id': cls.department.id,
            'user_id': cls.employee_user.id,
        })
        cls.admin = cls.env.ref('base.user_admin')

    @mute_logger('odoo.sql_db')
    def test_department_code_unique(self):
        with self.assertRaises(Exception), self.env.cr.savepoint():
            self.env['assetflow.department'].create({'name': 'Other', 'code': 'IT'})

    def test_employee_email_is_lowercased(self):
        self.assertEqual(self.employee.email, 'priya@example.com')

    def test_employee_role_derived_from_groups(self):
        self.assertEqual(self.employee.role, 'employee')

    def test_only_admin_can_promote(self):
        with self.assertRaises(UserError):
            self.employee.with_user(self.employee_user).action_promote_manager()
        self.employee.with_user(self.admin).action_promote_manager()
        self.assertEqual(self.employee.role, 'asset_manager')

    def test_signup_creates_internal_employee_without_role(self):
        self.env['ir.config_parameter'].sudo().set_param('auth_signup.invitation_scope', 'b2c')
        user = self.env['res.users'].signup({
            'name': 'New Hire',
            'login': 'new.hire@example.com',
            'password': 'Password123!',
        })
        created = self.env['res.users'].search([('login', '=', user[0])])
        self.assertTrue(created.employee_id)
        self.assertFalse(created.has_group('base.group_portal'))
        self.assertFalse(created.has_group('assetflow_base.group_assetflow_asset_manager'))
        self.assertEqual(created.employee_id.role, 'none')
