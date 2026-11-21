from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase


class TestAssetflowAudit(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.department = cls.env['assetflow.department'].create({'name': 'IT', 'code': 'IT'})
        cls.other_department = cls.env['assetflow.department'].create({'name': 'Ops', 'code': 'OPS'})
        cls.category = cls.env['assetflow.category'].create({'name': 'Electronics', 'code': 'ELEC'})
        cls.manager = cls.env['res.users'].create({
            'name': 'Audit Manager', 'login': 'af_audit_manager',
            'group_ids': [(6, 0, [cls.env.ref('assetflow_base.group_assetflow_asset_manager').id])],
        })
        cls.auditor_user = cls.env['res.users'].create({
            'name': 'Auditor', 'login': 'af_auditor',
            'group_ids': [(6, 0, [cls.env.ref('assetflow_base.group_assetflow_employee').id])],
        })
        cls.other_user = cls.env['res.users'].create({
            'name': 'Other Employee', 'login': 'af_audit_other',
            'group_ids': [(6, 0, [cls.env.ref('assetflow_base.group_assetflow_employee').id])],
        })
        cls.auditor = cls.env['assetflow.employee'].create({
            'name': 'Sam Auditor', 'email': 'sam@assetflow.test',
            'department_id': cls.department.id, 'user_id': cls.auditor_user.id,
        })
        cls.asset = cls.env['assetflow.asset'].create({
            'name': 'Laptop', 'asset_tag': 'AF-AUD-1', 'category_id': cls.category.id,
            'department_id': cls.department.id, 'location': 'HQ Floor 1',
        })
        cls.other_asset = cls.env['assetflow.asset'].create({
            'name': 'Chair', 'asset_tag': 'AF-AUD-2', 'category_id': cls.category.id,
            'department_id': cls.department.id, 'location': 'HQ Floor 2',
        })
        cls.cycle = cls.env['assetflow.audit.cycle'].create({
            'name': 'Q4 IT Audit',
            'scope_department_id': cls.department.id,
            'date_from': fields.Date.today(),
            'date_to': fields.Date.today() + timedelta(days=1),
            'auditor_ids': [(6, 0, [cls.auditor.id])],
        })

    def _started_cycle(self):
        cycle = self.cycle.with_user(self.manager)
        cycle.action_start()
        return cycle

    def test_start_generates_scoped_lines(self):
        cycle = self._started_cycle()
        self.assertEqual(cycle.state, 'in_progress')
        self.assertEqual(set(cycle.line_ids.asset_id.ids), {self.asset.id, self.other_asset.id})
        self.assertEqual(cycle.line_ids[0].expected_location, cycle.line_ids[0].asset_id.location)

    def test_start_twice_is_rejected(self):
        cycle = self._started_cycle()
        with self.assertRaises(UserError):
            cycle.action_start()

    def test_close_requires_every_line_decided(self):
        cycle = self._started_cycle()
        with self.assertRaises(UserError):
            cycle.action_close()

    def test_close_applies_discrepancies_and_locks(self):
        cycle = self._started_cycle()
        line = cycle.line_ids.filtered(lambda record: record.asset_id == self.asset)
        line.write({'result': 'missing', 'notes': 'Not on the shelf'})
        other = cycle.line_ids.filtered(lambda record: record.asset_id == self.other_asset)
        other.write({'result': 'damaged'})
        cycle.action_close()

        self.assertEqual(cycle.state, 'closed')
        self.assertEqual(cycle.discrepancy_count, 2)
        self.assertEqual(self.asset.state, 'lost')
        self.assertEqual(self.other_asset.condition, 'damaged')
        with self.assertRaises(UserError):
            line.write({'notes': 'changed after close'})
        with self.assertRaises(UserError):
            cycle.action_close()

    def test_scope_location_limits_lines(self):
        cycle = self.env['assetflow.audit.cycle'].create({
            'name': 'Floor 1 audit',
            'scope_location': 'Floor 1',
            'date_from': fields.Date.today(),
            'date_to': fields.Date.today(),
            'auditor_ids': [(6, 0, [self.auditor.id])],
        }).with_user(self.manager)
        cycle.action_start()
        self.assertEqual(cycle.line_ids.asset_id, self.asset)

    def test_dates_must_be_ordered(self):
        with self.assertRaises(UserError):
            self.env['assetflow.audit.cycle'].create({
                'name': 'Bad dates',
                'date_from': fields.Date.today(),
                'date_to': fields.Date.today() - timedelta(days=1),
            })

    def test_auditor_sees_assigned_cycle_and_can_verify(self):
        cycle = self._started_cycle()
        visible = self.env['assetflow.audit.cycle'].with_user(self.auditor_user).search([])
        self.assertIn(cycle, visible)
        visible_assets = self.env['assetflow.asset'].with_user(self.auditor_user).search([
            ('id', 'in', [self.asset.id, self.other_asset.id]),
        ])
        self.assertEqual(set(visible_assets.ids), {self.asset.id, self.other_asset.id})
        line = cycle.line_ids[0]
        line.with_user(self.auditor_user).write({'result': 'verified'})
        self.assertEqual(line.result, 'verified')
        self.assertEqual(line.verified_by_id, self.auditor)

    def test_non_auditor_employee_sees_no_audit(self):
        cycle = self._started_cycle()
        visible = self.env['assetflow.audit.cycle'].with_user(self.other_user).search([])
        self.assertNotIn(cycle, visible)
        with self.assertRaises(Exception):
            cycle.with_user(self.other_user).read(['name'])
