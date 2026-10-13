{
    'name': 'Government Violations Register',
    'version': '19.0.3.0.0',
    'category': 'Productivity',
    'summary': 'Register of labor office / municipality / other government '
               'violations with payment, objection and Balady import',
    'description': """
Government Violations Register
==============================
Track fines issued by the labor office, the municipality (Balady) and other
government authorities, their payment status (SADAD) and the objection window.

* Violation register with chatter, tracking and activities
* Payment status: unpaid / paid / cancelled / linked (zero-fine linked record)
* Objection window computed from the deadline, refreshed by a daily cron
* Outstanding exposure: unpaid, non-duplicate, present in the Balady register
* EW / EM / hotels / unallocated division computed from branch and company
* License to branch map used by the Balady import
* Balady import wizard (20-column master layout), idempotent upsert by
  violation number; register records missing from a newer file are flagged
* Data-quality flags (needs review, suspected duplicate, date warning)
""",
    'author': 'Enaya IT',
    'license': 'LGPL-3',
    'depends': ['mail', 'analytic'],
    'external_dependencies': {'python': ['openpyxl']},
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/mail_activity_type_data.xml',
        'data/gov_violation_category_data.xml',
        'data/ir_cron_data.xml',
        'views/gov_violation_category_views.xml',
        'views/gov_license_map_views.xml',
        'views/gov_violation_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/gov_violation_import_views.xml',
        'views/menus.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
}
