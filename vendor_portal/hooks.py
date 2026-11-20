app_name = "vendor_portal"
app_title = "Vendor Portal"
app_publisher = "Abhijit Prakashkumar Dodiya"
app_description = "Web Portal for Vendors"
app_email = "vendorportal@erpnext.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "vendor_portal",
# 		"logo": "/assets/vendor_portal/logo.png",
# 		"title": "Vendor Portal",
# 		"route": "/vendor_portal",
# 		"has_permission": "vendor_portal.api.permission.has_app_permission",
# 	}
# ]

# The dock, the rail down the left of the desk, is a document rather than a hook. Author it in
# Manage Dock on a developer-mode site and press Export to App, and it is written to
# `vendor_portal/dock/vendor_portal/vendor_portal.json` for git to carry. An app that ships none has no
# rail: its sidebar gets a switcher in the header instead.
#
# A companion app, one that extends a host app rather than standing on its own, says so with
# `mount_on` on that same record, and its entries are appended to the host's rail. Mounting keeps
# the companion off the apps screen, so it takes precedence over any add_to_apps_screen above.

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = "/assets/vendor_portal/css/vendor_portal.css"
app_include_js = "/assets/vendor_portal/js/vendor_portal.js"

# include js in doctype views
doctype_js = {
	"Purchase Order": "public/js/purchase_order.js",
	"Supplier": "public/js/supplier.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_kanban_js = {"doctype" : "public/js/doctype_kanban.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "vendor_portal/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

website_route_rules = [
	{"from_route": "/vendor-register", "to_route": "vendor_register"},
	{"from_route": "/vendor-status", "to_route": "vendor_status"},
]

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
jinja = {
	"methods": [],
	"filters": [
		"vendor_portal.utils.star_rating",
	],
}

# Installation
# ------------

# before_install = "vendor_portal.install.before_install"
# after_install = "vendor_portal.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "vendor_portal.uninstall.before_uninstall"
# after_uninstall = "vendor_portal.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "vendor_portal.utils.before_app_install"
# after_app_install = "vendor_portal.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "vendor_portal.utils.before_app_uninstall"
# after_app_uninstall = "vendor_portal.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "vendor_portal.build.after_build"

# To hook into the build process of other apps
# The list of apps being built is passed as an argument

# after_app_build = "vendor_portal.build.after_app_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "vendor_portal.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["vendor_portal.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
	"Vendor Onboarding": "vendor_portal.permissions.get_onboarding_permission_conditions",
}

has_permission = {
	"Vendor Rating Log": "vendor_portal.permissions.has_rating_log_permission",
}

# Override DocType Class
# ----------------------
override_doctype_class = {
	"Purchase Order": "vendor_portal.overrides.purchase_order.CustomPurchaseOrder"
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Purchase Receipt": {
		"validate": "vendor_portal.overrides.purchase_receipt.validate",
		"on_submit": "vendor_portal.overrides.purchase_receipt.on_submit",
	},
	"Vendor Onboarding": {
		"after_insert": "vendor_portal.events.on_vendor_onboarding_after_insert",
	},
	"Supplier": {
		"on_update": "vendor_portal.events.on_supplier_update",
	},
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"vendor_portal.tasks.auto_calculate_vendor_ratings",
	],
	"hourly": [
		"vendor_portal.tasks.auto_rate_deliveries",
	],
	"weekly": [
		"vendor_portal.tasks.send_vendor_performance_digest",
	],
	"cron": {
		"0 9 * * *": [
			"vendor_portal.tasks.auto_expire_stale_onboardings",
		],
	},
}

# Testing
# -------

# before_tests = "vendor_portal.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "vendor_portal.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "vendor_portal.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "vendor_portal.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["vendor_portal.utils.before_request"]
# after_request = ["vendor_portal.utils.after_request"]

# Job Events
# ----------
# before_job = ["vendor_portal.utils.before_job"]
# after_job = ["vendor_portal.utils.after_job"]

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
# 	"vendor_portal.auth.validate"
# ]

# on_social_login = "vendor_portal.auth.on_social_login"

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

# Fixtures
# --------
fixtures = [
	{
		"dt": "Custom Field",
		"filters": [
			[
				"name",
				"in",
				[
					"Supplier-vendor_category",
					"Supplier-vendor_rating",
					"Supplier-total_rating_count",
					"Supplier-onboarding_reference",
					"Supplier-is_blacklisted",
					"Supplier-blacklist_reason",
				],
			]
		],
	},
	{
		"dt": "Workflow State",
		"filters": [
			[
				"name",
				"in",
				[
					"Draft",
					"Under Review",
					"Approved",
					"Rejected",
					"Rework",
				],
			]
		],
	},
	{
		"dt": "Workflow Action Master",
		"filters": [
			[
				"name",
				"in",
				[
					"Submit for Review",
					"Approve",
					"Reject",
					"Resubmit",
					"Request Rework",
				],
			]
		],
	},
	{
		"dt": "Workflow",
		"filters": [
			[
				"name",
				"=",
				"Vendor Onboarding Approval",
			]
		],
	},
	{
		"dt": "Print Format",
		"filters": [
			[
				"name",
				"=",
				"Vendor Purchase Order",
			]
		],
	},
	{
		"dt": "Role",
		"filters": [
			[
				"name",
				"in",
				[
					"Vendor Manager",
					"Purchase Team",
				],
			]
		],
	},
]


