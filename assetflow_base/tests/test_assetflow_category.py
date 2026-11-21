from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase
from odoo.tools import mute_logger


class TestAssetflowCategory(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category = cls.env['assetflow.category'].create({
            'name': 'Electronics',
            'code': 'ELEC',
            'warranty_days': 365,
        })
        cls.employee_user = cls.env['res.users'].create({
            'name': 'AssetFlow Employee',
            'login': 'af_employee_test',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })

    @mute_logger('odoo.sql_db')
    def test_name_is_unique(self):
        with self.assertRaises(Exception), self.env.cr.savepoint():
            self.env['assetflow.category'].create({'name': 'Electronics'})

    @mute_logger('odoo.sql_db')
    def test_warranty_cannot_be_negative(self):
        with self.assertRaises(Exception), self.env.cr.savepoint():
            self.category.write({'warranty_days': -1})

    def test_admin_can_manage_categories(self):
        admin = self.env.ref('base.user_admin')
        category = self.category.with_user(admin)
        self.assertTrue(category.has_access('write'))
        self.assertTrue(category.has_access('unlink'))

    def test_employee_cannot_change_categories(self):
        category = self.category.with_user(self.employee_user)
        self.assertTrue(category.has_access('read'))
        self.assertFalse(category.has_access('write'))
