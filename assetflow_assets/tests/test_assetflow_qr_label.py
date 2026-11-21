import base64

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase

PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


class TestAssetflowQrLabel(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category = cls.env['assetflow.category'].create({'name': 'Electronics', 'code': 'ELEC'})
        cls.asset = cls.env['assetflow.asset'].create({
            'name': 'QR Test Laptop', 'asset_tag': 'AF-QR-TEST', 'category_id': cls.category.id,
        })
        cls.report = cls.env.ref('assetflow_assets.action_report_asset_qr_label')

    def test_qr_code_is_a_png_image(self):
        image = base64.b64decode(self.asset.qr_code)
        self.assertTrue(image.startswith(PNG_SIGNATURE))
        self.assertGreater(len(image), 100)

    def test_qr_code_regenerates_when_base_url_changes(self):
        before = self.asset.qr_code
        param = self.env['ir.config_parameter'].set_param('web.base.url', 'https://demo.example.test')
        self.assertTrue(param)
        after = self.asset.qr_code
        self.assertNotEqual(after, before)
        self.assertTrue(base64.b64decode(after).startswith(PNG_SIGNATURE))

    def test_report_renders_asset_tag(self):
        html, report_type = self.env['ir.actions.report']._render_qweb_html(
            self.report.id, self.asset.ids,
        )
        self.assertEqual(report_type, 'html')
        self.assertIn(b'AF-QR-TEST', html)
        self.assertIn(b'data:image/png;base64,', html)

    def test_user_without_asset_access_cannot_render_report(self):
        user = self.env['res.users'].create({
            'name': 'No Asset Access',
            'login': 'af_no_asset_access',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        with self.assertRaises(AccessError):
            self.env['ir.actions.report'].with_user(user)._render_qweb_html(
                self.report.id, self.asset.ids,
            )
