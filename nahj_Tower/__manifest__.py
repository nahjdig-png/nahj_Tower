{
    'name': 'Nahj Tower | نهج تاور',
    'version': '17.0.1.2.0',
    'category': 'Real Estate',
    'summary': 'Residential Tower Management – إدارة الأبراج السكنية',
    'description': """
Nahj Tower – Residential Tower Management System
=================================================
Manage residential towers, units, residents, monthly subscriptions,
and building expenses with a simple and practical interface.

نهج تاور – نظام إدارة الأبراج السكنية
========================================
إدارة الأبراج السكنية والشقق والسكان والاشتراكات الشهرية
ومصاريف العمارة بواجهة بسيطة وعملية.
    """,
    'author': 'Nahj Tower',
    'website': '',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'portal'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/expense_category_data.xml',
        'data/email_templates.xml',
        'views/dashboard_views.xml',
        # wizard/report actions must be defined before tower_views.xml references them
        'views/generate_subscriptions_views.xml',
        'report/report_monthly_summary.xml',
        'views/import_views.xml',
        'report/report_subscription_receipt.xml',
        'views/export_views.xml',
        'views/unit_transfer_views.xml',
        # main views
        'views/tower_asset_views.xml',
        'views/expense_views.xml',
        'views/maintenance_log_views.xml',
        'views/expense_distribution_views.xml',
        'views/tower_views.xml',
        'views/unit_views.xml',
        'views/resident_views.xml',
        'views/subscription_views.xml',
        'data/cron_data.xml',
        'views/portal_templates.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'nahj_Tower/static/src/css/dashboard.css',
            'nahj_Tower/static/src/xml/dashboard.xml',
            'nahj_Tower/static/src/js/dashboard.js',
            'compliance_base/static/src/css/dashboard_scroll_fab.css',
            'compliance_base/static/src/js/dashboard_scroll_fab.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
