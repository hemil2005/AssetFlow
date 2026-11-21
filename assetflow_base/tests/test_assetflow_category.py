from odoo.tests import TransactionCase
from odoo.tools import mute_logger


class TestAssetflowCategory(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category = cls.env['assetflow.category'].create({
            'name': 'Electronics', 'code': 'ELEC', 'warranty_months': 12,
        })

    @mute_logger('odoo.sql_db')
    def test_name_is_unique(self):
        with self.assertRaises(Exception), self.env.cr.savepoint():
            self.env['assetflow.category'].create({'name': 'Electronics', 'code': 'EL2'})

    @mute_logger('odoo.sql_db')
    def test_code_is_unique(self):
        with self.assertRaises(Exception), self.env.cr.savepoint():
            self.env['assetflow.category'].create({'name': 'Other', 'code': 'ELEC'})

    @mute_logger('odoo.sql_db')
    def test_warranty_cannot_be_negative(self):
        with self.assertRaises(Exception), self.env.cr.savepoint():
            self.category.write({'warranty_months': -1})
