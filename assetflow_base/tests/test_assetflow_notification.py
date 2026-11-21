from odoo.exceptions import UserError
from odoo.tests import TransactionCase, new_test_user


class TestAssetflowNotification(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(
            cls.env, login='af_notify_user',
            groups='base.group_user,assetflow_base.group_assetflow_employee',
        )
        cls.other_user = new_test_user(
            cls.env, login='af_notify_other',
            groups='base.group_user,assetflow_base.group_assetflow_employee',
        )
        cls.notification = cls.env['assetflow.notification']._notify(
            cls.user, 'Overdue return: AF-0001', 'Return it.',
            notification_type='overdue_return',
            res_model='assetflow.notification', res_id=0,
        )
        cls.notification.res_id = cls.notification.id
        cls.other_notification = cls.env['assetflow.notification']._notify(
            cls.other_user, 'Other notification', 'Not yours.',
        )

    def test_open_related_record_returns_action(self):
        action = self.notification.with_user(self.user).action_open_record()
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'assetflow.notification')
        self.assertEqual(action['res_id'], self.notification.id)

    def test_open_missing_or_unknown_record_is_rejected(self):
        self.notification.res_id = 999999
        with self.assertRaises(UserError):
            self.notification.with_user(self.user).action_open_record()
        self.notification.res_model = 'does.not.exist'
        with self.assertRaises(UserError):
            self.notification.with_user(self.user).action_open_record()

    def test_mark_all_read_only_touches_own_notifications(self):
        extra = self.env['assetflow.notification']._notify(self.user, 'Second', 'Body')
        self.env['assetflow.notification'].with_user(self.user).action_mark_all_read()
        self.assertTrue(self.notification.is_read)
        self.assertTrue(extra.is_read)
        self.assertFalse(self.other_notification.is_read)
        self.assertTrue(self.notification.read_at)

    def test_notify_once_is_idempotent_per_user_event_and_day(self):
        model = self.env['assetflow.notification']
        domain = [
            ('user_id', '=', self.user.id),
            ('res_model', '=', 'assetflow.asset'),
            ('res_id', '=', 42),
        ]
        model._notify_once(
            self.user, 'Allocated', 'Body', 'system', 'assetflow.asset', 42,
        )
        again = model._notify_once(
            self.user, 'Allocated', 'Body', 'system', 'assetflow.asset', 42,
        )
        self.assertFalse(again)
        self.assertEqual(model.sudo().search_count(domain), 1)

    def test_cannot_mark_someone_elses_notification_read(self):
        with self.assertRaises(UserError):
            self.other_notification.with_user(self.user).action_mark_read()
