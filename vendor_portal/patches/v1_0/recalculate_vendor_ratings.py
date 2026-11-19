# Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
# For license information, please see license.txt

import frappe
from vendor_portal.utils import recalculate_vendor_rating


def execute():
	"""
	Patch 2: Recalculate vendor_rating and total_rating_count for all Suppliers
	based on actual Vendor Rating Log entries using the weighted formula.
	"""
	frappe.logger("patch").info("Executing patch: recalculate_vendor_ratings")

	suppliers = frappe.db.sql_list("SELECT name FROM `tabSupplier`")
	recalculated = 0

	for s_name in suppliers:
		rating, count = recalculate_vendor_rating(s_name)
		if count > 0:
			recalculated += 1

	frappe.logger("patch").info(
		f"Completed recalculate_vendor_ratings: recalculated ratings for {recalculated} suppliers"
	)
