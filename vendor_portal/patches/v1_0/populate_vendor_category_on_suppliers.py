# Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""
	Patch 1: Populate vendor_category on existing Suppliers based on supplier_group.
	Creates missing standard Vendor Categories and maps legacy supplier groups.
	"""
	frappe.logger("patch").info("Executing patch: populate_vendor_category_on_suppliers")

	group_mapping = {
		"Raw Material": "Raw Materials",
		"Services": "IT Services",
		"Hardware": "Hardware & Equipment",
		"Electrical": "Electrical Supplies",
		"Pharmaceutical": "Pharmaceuticals",
		"Distributor": "General Distributors",
		"Local": "Local Vendors",
	}

	# Ensure categories exist
	for target_cat in set(group_mapping.values()):
		if not frappe.db.exists("Vendor Category", target_cat):
			frappe.get_doc({
				"doctype": "Vendor Category",
				"category_name": target_cat,
				"minimum_rating_threshold": 3.0,
			}).insert(ignore_permissions=True)

	# Fetch unmapped suppliers
	suppliers = frappe.db.sql(
		"""
		SELECT name, supplier_name, supplier_group
		FROM `tabSupplier`
		WHERE (vendor_category IS NULL OR vendor_category = '')
		  AND supplier_group IS NOT NULL
		""",
		as_dict=True,
	)

	mapped_count = 0
	unmapped = []

	for s in suppliers:
		grp = s.supplier_group
		if grp in group_mapping:
			cat = group_mapping[grp]
			frappe.db.set_value("Supplier", s.name, "vendor_category", cat, update_modified=False)
			mapped_count += 1
		else:
			unmapped.append(f"{s.name} (Group: {grp})")

	if unmapped:
		frappe.logger("patch").warning(
			f"Unmapped suppliers during category migration: {', '.join(unmapped[:10])}"
		)

	frappe.logger("patch").info(
		f"Completed populate_vendor_category_on_suppliers: mapped {mapped_count} suppliers"
	)
