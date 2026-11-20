# Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

CRITERIA_NAME = "Overall Vendor Rating & Performance"


def ensure_default_criteria():
	"""
	Ensure default Supplier Scorecard Criteria exists in ERPNext.
	"""
	if not frappe.db.exists("Supplier Scorecard Criteria", CRITERIA_NAME):
		doc = frappe.get_doc({
			"doctype": "Supplier Scorecard Criteria",
			"criteria_name": CRITERIA_NAME,
			"max_score": 100.0,
			"weight": 100.0,
			"formula": "100",
		})
		doc.insert(ignore_permissions=True)
	return CRITERIA_NAME


def sync_supplier_scorecard(supplier, vendor_rating=None):
	"""
	Bonus Task 2: Supplier Scorecard Integration.
	Integrates custom vendor rating (1.0 - 5.0) with ERPNext's native Supplier Scorecard feature.
	Maps rating to a 0-100% standing and synchronizes ERPNext standing flags (warn_pos, prevent_pos).
	"""
	if not supplier:
		return None

	ensure_default_criteria()

	sup_doc = frappe.get_cached_doc("Supplier", supplier)

	if vendor_rating is None:
		vendor_rating = flt(sup_doc.get("vendor_rating") or 0.0)

	is_blacklisted = int(sup_doc.get("is_blacklisted") or 0)

	# Calculate normalized percentage score [0.0 - 100.0]
	if is_blacklisted:
		score = 0.0
	elif vendor_rating > 0:
		# If stored on 0.0-1.0 scale (Frappe rating field), scale by 100, else if 1.0-5.0 scale by 20
		scale = 100.0 if vendor_rating <= 1.0 else 20.0
		score = min(round(vendor_rating * scale, 1), 100.0)
	else:
		score = 60.0  # Baseline neutral score for new unrated suppliers

	# Determine standing bracket
	if score >= 80.0:
		status = "Excellent"
		color = "Green"
		prevent_pos = 0
		warn_pos = 0
	elif score >= 50.0:
		status = "Average"
		color = "Orange"
		prevent_pos = 0
		warn_pos = 0
	elif score >= 30.0:
		status = "Poor"
		color = "Red"
		prevent_pos = 0
		warn_pos = 1
	else:
		status = "Very Poor"
		color = "Red"
		prevent_pos = 1
		warn_pos = 1

	if is_blacklisted:
		status = "Very Poor"
		prevent_pos = 1
		warn_pos = 1

	sc_name = frappe.db.get_value("Supplier Scorecard", {"supplier": supplier}, "name")
	if sc_name:
		sc = frappe.get_doc("Supplier Scorecard", sc_name)
	else:
		sc = frappe.get_doc({
			"doctype": "Supplier Scorecard",
			"supplier": supplier,
			"period": "Per Month",
			"weighting_function": "100",
			"criteria": [
				{
					"criteria_name": CRITERIA_NAME,
					"weight": 100.0,
					"max_score": 100.0,
					"formula": "100",
				}
			],
			"standings": [
				{
					"standing_name": "Very Poor",
					"min_grade": 0.0,
					"max_grade": 30.0,
					"standing_color": "Red",
					"prevent_pos": 1,
					"warn_pos": 1,
				},
				{
					"standing_name": "Poor",
					"min_grade": 30.0,
					"max_grade": 50.0,
					"standing_color": "Red",
					"prevent_pos": 0,
					"warn_pos": 1,
				},
				{
					"standing_name": "Average",
					"min_grade": 50.0,
					"max_grade": 80.0,
					"standing_color": "Orange",
					"prevent_pos": 0,
					"warn_pos": 0,
				},
				{
					"standing_name": "Excellent",
					"min_grade": 80.0,
					"max_grade": 100.0,
					"standing_color": "Green",
					"prevent_pos": 0,
					"warn_pos": 0,
				},
			],
		})

	sc.supplier_score = str(score)
	sc.status = status
	sc.indicator_color = color
	sc.prevent_pos = prevent_pos
	sc.warn_pos = warn_pos
	sc.flags.ignore_mandatory = True
	sc.save(ignore_permissions=True)

	# Update native Supplier document flags so ERPNext's built-in PO warnings fire
	frappe.db.set_value(
		"Supplier",
		supplier,
		{
			"prevent_pos": prevent_pos,
			"warn_pos": warn_pos,
		},
		update_modified=False,
	)

	return {
		"supplier": supplier,
		"scorecard": sc.name,
		"score": score,
		"status": status,
		"prevent_pos": prevent_pos,
		"warn_pos": warn_pos,
	}


@frappe.whitelist()
def get_supplier_scorecard(supplier):
	"""
	Whitelisted endpoint returning the active ERPNext Supplier Scorecard summary.
	"""
	from vendor_portal.api import PROCUREMENT_ROLES, check_api_permission

	check_api_permission(
		PROCUREMENT_ROLES,
		_("Permission Denied: You do not have permission to view supplier scorecards."),
	)
	if not supplier:
		frappe.throw(_("Supplier name is required."))

	sc_name = frappe.db.get_value("Supplier Scorecard", {"supplier": supplier}, "name")
	if not sc_name:
		# Auto sync if not yet created
		sync_result = sync_supplier_scorecard(supplier)
		sc_name = sync_result.get("scorecard")

	sc = frappe.get_doc("Supplier Scorecard", sc_name)
	return {
		"name": sc.name,
		"supplier": sc.supplier,
		"supplier_score": sc.supplier_score,
		"status": sc.status,
		"indicator_color": sc.indicator_color,
		"prevent_pos": sc.prevent_pos,
		"warn_pos": sc.warn_pos,
		"period": sc.period,
	}
