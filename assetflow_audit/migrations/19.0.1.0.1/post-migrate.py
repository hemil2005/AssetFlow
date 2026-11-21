"""Remove the old audit-owned sequence left behind by earlier builds.

``assetflow_audit`` used to define its own ``assetflow.audit.ref`` sequence while
``assetflow_base`` already owned one. Fresh installs only load the base record,
but an upgraded database keeps the orphaned audit record (same code, separate
counter), which can produce duplicate references. Delete it once.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    marker = env['ir.model.data'].search([
        ('module', '=', 'assetflow_audit'),
        ('name', '=', 'seq_assetflow_audit_ref'),
    ], limit=1)
    if not marker:
        return
    sequence = env['ir.sequence'].browse(marker.res_id)
    marker.unlink()
    if sequence.exists():
        sequence.unlink()
