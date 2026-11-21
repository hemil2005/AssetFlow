{
    'name': 'AssetFlow Maintenance',
    'version': '19.0.1.0.0',
    'category': 'AssetFlow',
    'summary': 'Maintenance requests, approval, technician assignment and resolution.',
    'description': """
    AssetFlow Maintenance
    =====================

    Employees raise maintenance requests for their assets. Asset Managers and
    Administrators approve or reject them, assign a technician, and the asset
    lifecycle is kept in sync while the repair runs.
    """,
    'author': 'AssetFlow Team',
    'license': 'LGPL-3',
    'depends': ['assetflow_base', 'assetflow_assets', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/assetflow_maintenance_rules.xml',
        'data/assetflow_maintenance_cron.xml',
        'views/assetflow_maintenance_views.xml',
        'views/assetflow_asset_views.xml',
        'views/assetflow_maintenance_menus.xml',
    ],
    'installable': True,
    'application': False,
}
