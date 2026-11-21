import uuid
from unittest.mock import patch

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestSignupHttp(HttpCase):
    """Exercise the real /web/signup route end to end.

    Free signup is enabled by auth_signup's own data (invitation_scope = b2c), so the test
    only has to fetch a CSRF token and post the form. The captcha hook is patched because a
    test database may have a captcha provider installed; with none installed it is a no-op.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.assetflow_groups = (
            'assetflow_base.group_assetflow_employee',
            'assetflow_base.group_assetflow_department_head',
            'assetflow_base.group_assetflow_asset_manager',
            'assetflow_base.group_assetflow_admin',
        )

    def _signup(self, name='New Visitor', password='AssetFlow-123'):
        login = 'signup-%s@example.com' % uuid.uuid4().hex[:10]
        self.authenticate(None, None)
        payload = {
            'login': login,
            'name': name,
            'password': password,
            'confirm_password': password,
            'csrf_token': http.Request.csrf_token(self),
        }
        with patch.object(
            self.env.registry['ir.http'],
            '_verify_request_recaptcha_token',
            lambda request, captcha: None,
        ):
            response = self.url_open('/web/signup', data=payload, timeout=60)
        self.assertEqual(response.status_code, 200, 'Signup should end on a rendered page.')
        user = self.env['res.users'].sudo().search([('login', '=', login)], limit=1)
        self.assertTrue(user, 'The signup route did not create a user.')
        return user

    def test_signup_creates_internal_user_without_assetflow_role(self):
        user = self._signup()
        employee = self.env['assetflow.employee'].sudo().search([('user_id', '=', user.id)], limit=1)

        self.assertTrue(user.has_group('base.group_user'), 'Signup must create an internal user.')
        self.assertFalse(user.has_group('base.group_portal'), 'Signup must not leave a portal user.')
        for group in self.assetflow_groups:
            self.assertFalse(user.has_group(group), 'Signup must not grant %s.' % group)

        self.assertTrue(employee, 'Signup must create a matching employee record.')
        self.assertEqual(employee.role, 'none')
        self.assertEqual(employee.department_id, self.env.ref('assetflow_base.department_general'))
        self.assertEqual(employee.email, user.login.lower())

    def test_signup_user_cannot_promote_itself(self):
        user = self._signup()
        employee = self.env['assetflow.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        with self.assertRaises(AccessError):
            user.with_user(user).write({
                'group_ids': [(4, self.env.ref('assetflow_base.group_assetflow_asset_manager').id)],
            })
        # The user has no AssetFlow role, so the directory model may deny access before the
        # action guard runs; either denial is a refusal to self-promote.
        with self.assertRaises(UserError):
            employee.with_user(user).action_promote_manager()
        self.assertFalse(user.has_group('assetflow_base.group_assetflow_asset_manager'))
        self.assertFalse(user.has_group('assetflow_base.group_assetflow_admin'))

    def test_promotion_action_requires_admin(self):
        employee_user = new_test_user(
            self.env, login='af_signup_promotion',
            groups='base.group_user,assetflow_base.group_assetflow_employee',
        )
        employee = self.env['assetflow.employee'].create({
            'name': 'Promotion Attempt',
            'email': 'promotion.attempt@assetflow.test',
            'department_id': self.env.ref('assetflow_base.department_general').id,
            'user_id': employee_user.id,
        })
        with self.assertRaises(UserError):
            employee.with_user(employee_user).action_promote_manager()
        self.assertFalse(employee_user.has_group('assetflow_base.group_assetflow_asset_manager'))
