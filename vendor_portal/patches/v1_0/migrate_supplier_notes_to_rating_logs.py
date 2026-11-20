# Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import today
from vendor_portal.utils import recalculate_vendor_rating


def execute():
	"""
	Patch 3: Migrate historical Supplier comments containing rating keywords
	into structured Vendor Rating Log entries with estimated scores.
	Safely checks table existence before execution to prevent migration failure.
	"""
	frappe.logger("patch").info("Executing patch: migrate_supplier_notes_to_rating_logs")

	if not frappe.db.table_exists("Supplier") or not frappe.db.table_exists("Comment"):
		frappe.logger("patch").info("Supplier or Comment table not found. Skipping patch.")
		return

	if not frappe.db.table_exists("Vendor Rating Log"):
		frappe.logger("patch").info("Vendor Rating Log table not found. Skipping patch.")
		return

	# Keyword rules: (keyword, rating_type, score)
	keyword_rules = [
		("excellent", "Quality", 5.0),
		("outstanding", "Quality", 5.0),
		("on time delivery", "Delivery", 5.0),
		("good", "Quality", 4.0),
		("satisfactory", "Quality", 4.0),
		("reliable", "Delivery", 4.5),
		("average", "Quality", 3.0),
		("fair", "Pricing", 3.0),
		("late delivery", "Delivery", 2.0),
		("delayed", "Delivery", 2.5),
		("poor quality", "Quality", 1.5),
		("defective", "Quality", 1.0),
		("bad", "Quality", 2.0),
		("expensive", "Pricing", 2.0),
		("unresponsive", "Communication", 1.5),
	]

	# Query comments linked to Supplier
	comments = frappe.db.sql(
		"""
		SELECT name, reference_name as supplier, content, owner, creation
		FROM `tabComment`
		WHERE reference_doctype = 'Supplier'
		  AND comment_type = 'Comment'
		""",
		as_dict=True,
	)

	migrated_count = 0
	affected_suppliers = set()

	for c in comments:
		content_lower = (c.content or "").lower()
		for kw, rating_type, score in keyword_rules:
			if kw in content_lower:
				# Check if already migrated
				exists = frappe.db.exists(
					"Vendor Rating Log",
					{
						"supplier": c.supplier,
						"remarks": ["like", f"%[Migrated from comment {c.name}]%"],
					},
				)
				if not exists:
					log = frappe.get_doc({
						"doctype": "Vendor Rating Log",
						"supplier": c.supplier,
						"rating_type": rating_type,
						"score": score,
						"remarks": f"Migrated from historical comment: {frappe.utils.strip_html(c.content)} [Migrated from comment {c.name}]",
						"rated_by": c.owner or "Administrator",
						"rating_date": c.creation.date() if c.creation else today(),
					})
					log.insert(ignore_permissions=True)
					migrated_count += 1
					affected_suppliers.add(c.supplier)
				break  # match first dominant keyword

	# Recalculate ratings for affected suppliers
	for sup in affected_suppliers:
		recalculate_vendor_rating(sup)

	frappe.logger("patch").info(
		f"Completed migrate_supplier_notes_to_rating_logs: created {migrated_count} logs for {len(affected_suppliers)} suppliers"
	)
