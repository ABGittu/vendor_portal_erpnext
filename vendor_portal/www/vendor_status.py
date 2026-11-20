# Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
# For license information, please see license.txt

import frappe
from frappe import _

no_cache = 1


def get_context(context):
	"""
	Provide template context for the public Vendor Self-Service Application Status Tracker.
	Extracts optional query parameter for direct bookmark/redirect lookups.
	"""
	context.title = _("Vendor Application Status Tracker")
	context.query = frappe.form_dict.get("query") or ""
	context.csrf_token = frappe.sessions.get_csrf_token()
	return context
