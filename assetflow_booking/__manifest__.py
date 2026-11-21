{
    'name': 'AssetFlow Booking',
    'version': '19.0.2.0.0',
    'category': 'AssetFlow',
    'summary': 'Time-slot booking of shared assets with overlap validation.',
    'description': """
    AssetFlow Booking
    =================

    Books shared/bookable assets by half-open time slot, rejects overlaps under an
    asset row lock, synchronizes the asset state with ongoing bookings and sends
    one reminder per booking.
    """,
    'author': 'AssetFlow Team',
    'license': 'LGPL-3',
    'depends': ['assetflow_base', 'assetflow_assets'],
    'data': [
        'security/ir.model.access.csv',
        'security/assetflow_booking_rules.xml',
        'data/assetflow_booking_cron.xml',
        'views/assetflow_booking_views.xml',
        'views/assetflow_booking_menus.xml',
    ],
    'installable': True,
    'application': False,
}
