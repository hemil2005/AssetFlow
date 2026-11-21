{
    'name': 'AssetFlow Assets',
    'version': '19.0.2.0.0',
    'category': 'AssetFlow',
    'summary': 'Asset registry, lifecycle states, allocation, transfer and return.',
    'description': """
    AssetFlow Assets
    ================

    Registers assets, tracks their lifecycle, enforces the single-holder rule and
    implements the transfer and return workflows.
    """,
    'author': 'AssetFlow Team',
    'license': 'LGPL-3',
    'depends': ['assetflow_base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/assetflow_assets_rules.xml',
        'data/assetflow_assets_cron.xml',
        'views/assetflow_asset_views.xml',
        'views/assetflow_allocation_views.xml',
        'views/assetflow_transfer_views.xml',
        'views/assetflow_assets_menus.xml',
    ],
    'installable': True,
    'application': False,
}
