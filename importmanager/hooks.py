app_name = "importmanager"
app_title = "Importmanager"
app_publisher = "SpotLedger"
app_description = "ERPnext app to handle import workflow/costing."
app_email = "ehsensiraj@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "importmanager",
# 		"logo": "/assets/importmanager/logo.png",
# 		"title": "Importmanager",
# 		"route": "/importmanager",
# 		"has_permission": "importmanager.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/importmanager/css/importmanager.css"
# app_include_js = "/assets/importmanager/js/importmanager.js"

# include js, css files in header of web template
# web_include_css = "/assets/importmanager/css/importmanager.css"
# web_include_js = "/assets/importmanager/js/importmanager.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "importmanager/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "importmanager/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

#Jinja
# ----------

# add methods and filters to jinja environment
jinja = {
	"methods": "importmanager.import_print_utils.fetch_jpg_from_import_doc",
# 	"filters": "importmanager.utils.jinja_filters"
}

fixtures = [
    {
        "doctype": "Custom Field",
        "filters": [
        
            ["module", "=", "Importmanager"]
        ]
    },
    {
        "doctype": "Property Setter",
        "filters": [
            
            ["module", "=", "Importmanager"]
        ]
    },
     

]

# Installation
# ------------

# before_install = "importmanager.install.before_install"
# after_install = "importmanager.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "importmanager.uninstall.before_uninstall"
# after_uninstall = "importmanager.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "importmanager.utils.before_app_install"
# after_app_install = "importmanager.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "importmanager.utils.before_app_uninstall"
# after_app_uninstall = "importmanager.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "importmanager.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
 	"Landed Cost Voucher": "importmanager.importmanager.overrides.custom_landed_cost_voucher.CustomLandedCostVoucher",
     "Item Tax Template":"importmanager.importmanager.overrides.custom_item_tax_template.CustomItemTaxTemplate"
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Sales Invoice": {
		"on_submit": "importmanager.importmanager.controllers.charge_allocation_controller.on_submit_create_allocation_entries",
	},
    "Purchase Invoice": {
		"on_update": "importmanager.import_utils.set_expense_head",
        "on_submit": "importmanager.import_utils.on_submit_purchase_invoice",
        "on_cancel": "importmanager.import_utils.on_cancel_purchase_invoice",
        "autoname": "importmanager.import_utils.autoname_purchase_invoice"
	},
    "Journal Entry": {
        "on_submit": "importmanager.import_utils.on_submit_journal_entry",
        "on_cancel": "importmanager.import_utils.on_cancel_journal_entry"
    },
    "Landed Cost Voucher": {
        "on_submit": "importmanager.import_utils.on_submit_landed_cost_voucher",
        "on_cancel": "importmanager.import_utils.on_cancel_landed_cost_voucher"
    }
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"importmanager.tasks.all"
# 	],
# 	"daily": [
# 		"importmanager.tasks.daily"
# 	],
# 	"hourly": [
# 		"importmanager.tasks.hourly"
# 	],
# 	"weekly": [
# 		"importmanager.tasks.weekly"
# 	],
# 	"monthly": [
# 		"importmanager.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "importmanager.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "importmanager.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "importmanager.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["importmanager.utils.before_request"]
# after_request = ["importmanager.utils.after_request"]

# Job Events
# ----------
# before_job = ["importmanager.utils.before_job"]
# after_job = ["importmanager.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"importmanager.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

#