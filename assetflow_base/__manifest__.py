{
    'name': 'AssetFlow Base',
    'version': '19.0.2.0.0',
    'category': 'AssetFlow',
    'summary': 'Foundation for AssetFlow: roles, departments, employees, categories and numbering.',
    'description': """
    AssetFlow Base
    ==============

    Defines AssetFlow roles, the employee directory, departments, asset categories,
    notifications, the activity log and the shared sequences.
    """,
    'author': 'AssetFlow Team',
    'license': 'LGPL-3',
    'depends': ['base', 'auth_signup'],
    'data': [
        'security/assetflow_security.xml',
        'security/ir.model.access.csv',
        'security/assetflow_base_rules.xml',
        'data/assetflow_sequence.xml',
        'data/assetflow_departments.xml',
        'views/assetflow_department_views.xml',
        'views/assetflow_category_views.xml',
        'views/assetflow_employee_views.xml',
        'views/assetflow_notification_views.xml',
        'views/assetflow_activity_log_views.xml',
        'views/assetflow_menus.xml',
    ],
    'installable': True,
    'application': True,
}
