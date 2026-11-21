{
    'name': 'AssetFlow Audit',
    'version': '19.0.1.0.1',
    'category': 'AssetFlow',
    'summary': 'Audit cycles, discrepancy tracking and audit close.',
    'description': """
    AssetFlow Audit
    ===============

    Creates audit cycles scoped by department/location, generates lines for the
    assets in scope, lets assigned auditors mark them verified/missing/damaged,
    and closes the cycle with a discrepancy report and asset status updates.
    """,
    'author': 'AssetFlow Team',
    'license': 'LGPL-3',
    'depends': ['assetflow_base', 'assetflow_assets', 'mail'],
    'data': [
        'security/assetflow_audit_security.xml',
        'security/ir.model.access.csv',
        'views/assetflow_audit_cycle_views.xml',
        'views/assetflow_audit_line_views.xml',
        'views/assetflow_audit_menus.xml',
        'report/assetflow_audit_report_templates.xml',
        'report/assetflow_audit_report.xml',
    ],
    'installable': True,
    'application': False,
}
