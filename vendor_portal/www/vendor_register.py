# Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
# For license information, please see license.txt

import frappe
from frappe import _

no_cache = 1


def get_context(context):
	"""
	Provide template context for the public Vendor Self-Service Registration page.
	Populates active vendor categories for selection.
	"""
	context.title = _("Vendor Registration Portal")
	context.categories = frappe.get_all(
		"Vendor Category",
		fields=["name"],
		order_by="name asc"
	)
	context.csrf_token = frappe.sessions.get_csrf_token()
	return context
