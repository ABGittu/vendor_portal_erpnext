# Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
# For license information, please see license.txt

import frappe
from vendor_portal.utils import recalculate_vendor_rating


def execute():
	"""
	Patch 2: Recalculate vendor_rating and total_rating_count for all Suppliers
	based on actual Vendor Rating Log entries using the weighted formula.
	Safely checks field and table existence before execution.
	"""
	frappe.logger("patch").info("Executing patch: recalculate_vendor_ratings")

	if not frappe.db.table_exists("Supplier") or not frappe.db.has_column("Supplier", "vendor_rating"):
		frappe.logger("patch").info("Supplier table or vendor_rating column not found. Skipping patch.")
		return

	if not frappe.db.table_exists("Vendor Rating Log"):
		frappe.logger("patch").info("Vendor Rating Log table not found. Skipping patch.")
		return

	suppliers = frappe.db.sql_list("SELECT name FROM `tabSupplier`")
	recalculated = 0

	for s_name in suppliers:
		rating, count = recalculate_vendor_rating(s_name)
		if count > 0:
			recalculated += 1

	frappe.logger("patch").info(
		f"Completed recalculate_vendor_ratings: recalculated ratings for {recalculated} suppliers"
	)
