from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase


class TestAssetflowBooking(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.department = cls.env['assetflow.department'].create({'name': 'Facilities', 'code': 'FAC'})
        cls.category = cls.env['assetflow.category'].create({'name': 'Rooms', 'code': 'ROOM'})
        cls.manager = cls.env['res.users'].create({
            'name': 'Booking Manager', 'login': 'af_booking_manager',
            'group_ids': [(6, 0, [cls.env.ref('assetflow_base.group_assetflow_asset_manager').id])],
        })
        cls.employee_user = cls.env['res.users'].create({
            'name': 'Booking Employee', 'login': 'af_booking_employee',
            'group_ids': [(6, 0, [cls.env.ref('assetflow_base.group_assetflow_employee').id])],
        })
        cls.employee = cls.env['assetflow.employee'].create({
            'name': 'Priya', 'email': 'priya.booking@assetflow.test',
            'department_id': cls.department.id, 'user_id': cls.employee_user.id,
        })
        cls.base = fields.Datetime.to_datetime(fields.Datetime.now()) + timedelta(days=1)
        cls.base = cls.base.replace(hour=9, minute=0, second=0, microsecond=0)
        cls.asset = cls.env['assetflow.asset'].create({
            'name': 'Room B2', 'asset_tag': 'AF-BOOK-TEST', 'category_id': cls.category.id,
            'is_bookable': True,
        }).with_user(cls.manager)

    def _slot(self, start_hour, end_hour):
        return (
            fields.Datetime.to_string(self.base + timedelta(hours=start_hour)),
            fields.Datetime.to_string(self.base + timedelta(hours=end_hour)),
        )

    def _book(self, start_hour, end_hour, asset=None):
        start, end = self._slot(start_hour, end_hour)
        return self.env['assetflow.booking'].with_user(self.manager).create({
            'asset_id': (asset or self.asset).id,
            'employee_id': self.employee.id,
            'start_datetime': start,
            'end_datetime': end,
        })

    def test_adjacent_slots_allowed(self):
        self._book(0, 1)
        self.assertTrue(self._book(1, 2).id)

    def test_employee_cannot_overlap_another_users_booking(self):
        self._book(0, 1)
        other_user = self.env['res.users'].create({
            'name': 'Other Booker', 'login': 'af_booking_other',
            'group_ids': [(6, 0, [self.env.ref('assetflow_base.group_assetflow_employee').id])],
        })
        other_employee = self.env['assetflow.employee'].create({
            'name': 'Raj', 'email': 'raj.booking@assetflow.test',
            'department_id': self.department.id, 'user_id': other_user.id,
        })
        start, end = self._slot(0, 2)
        with self.assertRaises(ValidationError):
            self.env['assetflow.booking'].with_user(other_user).create({
                'asset_id': self.asset.id,
                'employee_id': other_employee.id,
                'start_datetime': start,
                'end_datetime': end,
            })

    def test_create_cannot_forge_state(self):
        booking = self.env['assetflow.booking'].with_user(self.manager).create({
            'asset_id': self.asset.id,
            'employee_id': self.employee.id,
            'start_datetime': self._slot(2, 3)[0],
            'end_datetime': self._slot(2, 3)[1],
            'state': 'completed',
        })
        self.assertEqual(booking.state, 'upcoming')

    def test_overlap_rejected(self):
        self._book(0, 1)
        with self.assertRaises(ValidationError):
            self._book(0, 1)

    def test_containment_overlap_rejected(self):
        self._book(0, 3)
        with self.assertRaises(ValidationError):
            self._book(1, 2)

    def test_past_slot_rejected(self):
        past = fields.Datetime.to_string(fields.Datetime.to_datetime(fields.Datetime.now()) - timedelta(hours=2))
        with self.assertRaises(ValidationError):
            self.env['assetflow.booking'].with_user(self.manager).create({
                'asset_id': self.asset.id, 'employee_id': self.employee.id,
                'start_datetime': past,
                'end_datetime': fields.Datetime.to_string(
                    fields.Datetime.to_datetime(fields.Datetime.now()) - timedelta(hours=1)),
            })

    def test_non_bookable_asset_rejected(self):
        other = self.env['assetflow.asset'].with_user(self.manager).create({
            'name': 'Laptop', 'asset_tag': 'AF-NBOOK-TEST', 'category_id': self.category.id,
        })
        with self.assertRaises(ValidationError):
            self._book(0, 1, asset=other)

    def test_booking_created_and_cancelled_notify_booker(self):
        booking = self._book(0, 1)
        notifications = self.env['assetflow.notification'].sudo()
        domain = [
            ('user_id', '=', self.employee_user.id),
            ('res_model', '=', 'assetflow.booking'),
            ('res_id', '=', booking.id),
        ]
        self.assertEqual(notifications.search_count(domain), 1)
        booking.action_cancel(reason='Schedule change')
        self.assertEqual(notifications.search_count(domain), 2)

    def test_state_write_denied(self):
        booking = self._book(0, 1)
        with self.assertRaises(UserError):
            booking.write({'state': 'ongoing'})

    def test_cancel_releases_slot(self):
        booking = self._book(0, 1)
        booking.action_cancel(reason='No longer needed')
        self.assertEqual(booking.state, 'cancelled')
        self.assertTrue(self._book(0, 1).id)

    def test_ongoing_booking_reserves_asset(self):
        start = fields.Datetime.to_string(fields.Datetime.to_datetime(fields.Datetime.now()) - timedelta(hours=1))
        end = fields.Datetime.to_string(fields.Datetime.to_datetime(fields.Datetime.now()) + timedelta(hours=1))
        booking = self.env['assetflow.booking'].with_user(self.manager).create({
            'asset_id': self.asset.id, 'employee_id': self.employee.id,
            'start_datetime': start, 'end_datetime': end,
        })
        self.env['assetflow.booking']._cron_sync_states()
        self.assertEqual(booking.state, 'ongoing')
        self.assertEqual(self.asset.state, 'reserved')

    def test_employee_can_book_and_reserve_immediately(self):
        start = fields.Datetime.to_string(fields.Datetime.to_datetime(fields.Datetime.now()) - timedelta(minutes=5))
        end = fields.Datetime.to_string(fields.Datetime.to_datetime(fields.Datetime.now()) + timedelta(hours=1))
        booking = self.env['assetflow.booking'].with_user(self.employee_user).create({
            'asset_id': self.asset.id, 'employee_id': self.employee.id,
            'start_datetime': start, 'end_datetime': end,
        })
        self.assertEqual(booking.state, 'ongoing')
        self.assertEqual(self.asset.state, 'reserved')

    def test_reminder_skips_booker_without_login(self):
        no_login = self.env['assetflow.employee'].create({
            'name': 'Visitor', 'email': 'visitor@assetflow.test', 'department_id': self.department.id,
        })
        start = fields.Datetime.to_string(fields.Datetime.to_datetime(fields.Datetime.now()) + timedelta(minutes=10))
        end = fields.Datetime.to_string(fields.Datetime.to_datetime(fields.Datetime.now()) + timedelta(hours=1))
        booking = self.env['assetflow.booking'].with_user(self.manager).create({
            'asset_id': self.asset.id, 'employee_id': no_login.id,
            'start_datetime': start, 'end_datetime': end,
        })
        self.env['assetflow.booking']._cron_send_reminders()
        self.assertTrue(booking.reminder_sent)

    def test_reminder_is_idempotent(self):
        start = fields.Datetime.to_string(fields.Datetime.to_datetime(fields.Datetime.now()) + timedelta(minutes=10))
        end = fields.Datetime.to_string(fields.Datetime.to_datetime(fields.Datetime.now()) + timedelta(hours=1))
        booking = self.env['assetflow.booking'].with_user(self.manager).create({
            'asset_id': self.asset.id, 'employee_id': self.employee.id,
            'start_datetime': start, 'end_datetime': end,
        })
        self.assertFalse(booking.reminder_sent)
        self.env['assetflow.booking']._cron_send_reminders()
        self.assertTrue(booking.reminder_sent)
        before = self.env['assetflow.notification'].search_count([('res_id', '=', booking.id)])
        self.env['assetflow.booking']._cron_send_reminders()
        self.assertEqual(
            self.env['assetflow.notification'].search_count([('res_id', '=', booking.id)]), before,
        )
