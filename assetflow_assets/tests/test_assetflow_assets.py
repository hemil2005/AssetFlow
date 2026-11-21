from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase


class TestAssetflowAssets(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = cls.env['res.users'].create({
            'name': 'AssetFlow Manager',
            'login': 'af_manager_test',
            'group_ids': [(6, 0, [cls.env.ref('assetflow_base.group_assetflow_asset_manager').id])],
        })
        cls.employee = cls.env['res.users'].create({
            'name': 'AssetFlow Holder',
            'login': 'af_holder_test',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.employee_record = cls.env['hr.employee'].create({
            'name': 'Priya',
            'user_id': cls.employee.id,
        })
        cls.other_employee = cls.env['hr.employee'].create({'name': 'Raj'})
        cls.asset = cls.env['assetflow.asset'].create({
            'name': 'Laptop',
            'tag': 'AF-0114',
        })

    def test_allocation_blocks_double_allocation(self):
        asset = self.asset.with_user(self.manager)
        asset.action_allocate(employee=self.employee_record)
        self.assertEqual(asset.state, 'allocated')
        with self.assertRaises(ValidationError):
            asset.action_allocate(employee=self.other_employee)
        self.assertEqual(asset.employee_id, self.employee_record)

    def test_return_releases_asset(self):
        asset = self.asset.with_user(self.manager)
        asset.action_allocate(employee=self.employee_record)
        asset.action_return(note='Returned in good condition')
        self.assertEqual(asset.state, 'available')
        self.assertFalse(asset.employee_id)

    def test_transfer_reallocates_asset(self):
        asset = self.asset.with_user(self.manager)
        asset.action_allocate(employee=self.employee_record)
        transfer = self.env['assetflow.transfer'].with_user(self.manager).create({
            'asset_id': asset.id,
            'to_employee_id': self.other_employee.id,
        })
        transfer.action_request()
        transfer.action_approve()
        self.assertEqual(transfer.state, 'approved')
        self.assertEqual(asset.state, 'allocated')
        self.assertEqual(asset.employee_id, self.other_employee)

    def test_employee_cannot_allocate(self):
        with self.assertRaises(Exception):
            self.asset.with_user(self.employee).action_allocate(employee=self.employee_record)
