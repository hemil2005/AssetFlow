{
    'name': 'AssetFlow Reports',
    'version': '19.0.1.0.0',
    'category': 'AssetFlow',
    'summary': 'KPI dashboard, operational reports, pivots and PDF exports.',
    'description': """
    AssetFlow Reports
    =================

    Adds the operational dashboard, utilization and maintenance analysis views,
    and the department allocation summary PDF.
    """,
    'author': 'AssetFlow Team',
    'license': 'LGPL-3',
    'depends': [
        'assetflow_base',
        'assetflow_assets',
        'assetflow_booking',
        'assetflow_maintenance',
        'assetflow_audit',
        'web',
    ],
    'data': [
        'security/ir.model.access.csv',
        'report/assetflow_department_report_templates.xml',
        'report/assetflow_department_report.xml',
        'views/assetflow_report_views.xml',
        'views/assetflow_reports_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'assetflow_reports/static/src/js/dashboard.js',
            'assetflow_reports/static/src/xml/dashboard.xml',
            'assetflow_reports/static/src/scss/dashboard.scss',
        ],
    },
    'installable': True,
    'application': False,
}
