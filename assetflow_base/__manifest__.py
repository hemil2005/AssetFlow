{
    'name': 'AssetFlow Base',
    'version': '19.0.1.0.0',
    'category': 'AssetFlow',
    'summary': 'Foundation for AssetFlow: roles, asset categories and asset numbering.',
    'description': """
    AssetFlow Base
    ==============

    Defines the AssetFlow security roles, the asset category master data and the
    asset tag sequence used by the other AssetFlow addons.
    """,
    'author': 'AssetFlow Team',
    'license': 'LGPL-3',
    'depends': ['base', 'hr'],
    'data': [
        'security/assetflow_security.xml',
        'security/ir.model.access.csv',
        'data/assetflow_sequence.xml',
        'views/assetflow_category_views.xml',
        'views/assetflow_menus.xml',
    ],
    'installable': True,
    'application': True,
}
