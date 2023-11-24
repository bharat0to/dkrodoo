# -*- coding: utf-8 -*----
{
    'name': "isha_life_vrs",

    'summary': """
        Vendor registration and Onboarding System for all vendord working with Isha Life
        """,

    'description': """
        Vendor registration and Onboarding System for all vendord working with Isha Life
    """,

    'author': "Isha IT",
    'website': "http://www.ishait.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/12.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'isha_life_vrs',
    'version': '15.0.1.0.0',

    # any module necessary for this one to work correctly
    'depends': [
        'base',
        'account',
        'l10n_in',
        'mail',
        'contacts',
        'calendar', # v15 to override _compute_meeting_count for res_partner
        'portal',
        'website',
        'hr',
        'auth_oauth',
        'website_slides',
        'web'
    ],

    # always loaded
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        # 'security/hide_group_template.xml',
        # 'security/user_rules_template.xml',
        'views/email_templates.xml',
        'views/in_pincode_state.xml',
        'views/yellow_ai_widget.xml',
               'views/test.xml',
        'views/partner_view.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            '/isha_life_vrs/static/src/css/frontend.css',
            '/isha_life_vrs/static/src/css/editpage.css',
            '/isha_life_vrs/static/src/css/layouts.css',
            '/isha_life_vrs/static/src/css/servicedesk.css',
            '/isha_life_vrs/static/src/style.css',
            '/isha_life_vrs/static/src/js/isha_vendor.js'
        ],
        'web.assets_backend': [
            '/isha_life_vrs/static/src/less/request_kanban.less',
            '/isha_life_vrs/static/src/less/request_dashboard_kanban.less'
        ]
    },
    # 'css': ['static/src/css/my_css.css'],
    # only loaded in demonstration mode
    'demo': [],
    'installable': True,
    'application': True,
    'license': 'OPL-1',
}
