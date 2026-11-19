# Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
# For license information, please see license.txt

import frappe


def has_rating_log_permission(doc, ptype="read", user=None):
	"""
	Custom permission hook for Vendor Rating Log (Task 2.4).
	- Vendor Managers and System Managers have full permissions on all logs.
	- Regular users (e.g. Purchase Team, Purchase User) can only edit/delete their own ratings (rated_by == user).
	- Read and create are permitted according to standard role permissions.
	"""
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return True

	user_roles = frappe.get_roles(user)
	if "System Manager" in user_roles or "Vendor Manager" in user_roles:
		return True

	# Only restrict modification actions (write, delete)
	if ptype in ("write", "delete"):
		if not doc:
			return True
		doc_rated_by = getattr(doc, "rated_by", None) or getattr(doc, "owner", None)
		if doc_rated_by and doc_rated_by == user:
			return True
		return False

	return True


def get_onboarding_permission_conditions(user=None):
	"""
	Permission query condition hook for Vendor Onboarding (Task 2.4).
	- Vendor Managers, Purchase Managers, and System Managers see all records.
	- Purchase Team members see only records where they are the owner (their own submissions).
	"""
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return ""

	user_roles = frappe.get_roles(user)
	if (
		"System Manager" in user_roles
		or "Vendor Manager" in user_roles
		or "Purchase Manager" in user_roles
	):
		return ""

	if "Purchase Team" in user_roles:
		return f"`tabVendor Onboarding`.owner = {frappe.db.escape(user)}"

	return ""
