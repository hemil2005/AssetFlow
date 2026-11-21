from datetime import datetime, timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase


class TestAssetflowBooking(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = cls.env['res.users'].create({
            'name': 'Booking Manager',
            'login': 'af_booking_manager',
            'group_ids': [(6, 0, [cls.env.ref('assetflow_base.group_assetflow_asset_manager').id])],
        })
        cls.employee_user = cls.env['res.users'].create({
            'name': 'Booking Employee',
            'login': 'af_booking_employee',
            'group_ids': [(6, 0, [cls.env.ref('assetflow_base.group_assetflow_employee').id])],
        })
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Priya', 'user_id': cls.employee_user.id,
        })
        tomorrow = fields.Datetime.to_datetime(fields.Datetime.now()) + timedelta(days=1)
        cls.base = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)

        cls.asset = cls.env['assetflow.asset'].create({
            'name': 'Room B2', 'is_bookable': True,
        }).with_user(cls.manager)

    def _slot(self, start_hour, end_hour):
        return (
            fields.Datetime.to_string(self.base + timedelta(hours=start_hour)),
            fields.Datetime.to_string(self.base + timedelta(hours=end_hour)),
        )

    def _book(self, start_hour, end_hour):
        start, end = self._slot(start_hour, end_hour)
        return self.env['assetflow.booking'].with_user(self.manager).create({
            'asset_id': self.asset.id,
            'employee_id': self.employee.id,
            'start_datetime': start,
            'end_datetime': end,
        })

    def test_adjacent_slots_allowed(self):
        self._book(0, 1)
        booking = self._book(1, 2)
        self.assertTrue(booking.id)

    def test_overlap_rejected(self):
        self._book(0, 1)
        with self.assertRaises(ValidationError):
            self._book(0, 1)

    def test_cancel_releases_slot(self):
        booking = self._book(0, 1)
        booking.action_cancel(reason='No longer needed')
        self.assertEqual(booking.state, 'cancelled')
        self.assertTrue(self._book(0, 1).id)

    def test_ongoing_booking_reserves_asset(self):
        start = fields.Datetime.to_string(datetime.now() - timedelta(hours=1))
        end = fields.Datetime.to_string(datetime.now() + timedelta(hours=1))
        booking = self.env['assetflow.booking'].with_user(self.manager).create({
            'asset_id': self.asset.id,
            'employee_id': self.employee.id,
            'start_datetime': start,
            'end_datetime': end,
        })
        self.env['assetflow.booking']._cron_sync_states()
        self.assertEqual(booking.state, 'ongoing')
        self.assertEqual(self.asset.state, 'reserved')
