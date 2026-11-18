# Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
# For license information, please see license.txt

import frappe


def recalculate_vendor_rating(supplier_name):
	"""
	Recalculate a supplier's vendor_rating as a weighted average of all
	Vendor Rating Logs according to weights configured in Vendor Portal Settings.
	Updates Supplier's vendor_rating and total_rating_count.
	"""
	if not supplier_name:
		return 0.0, 0

	settings = frappe.get_single("Vendor Portal Settings")
	weights = {
		"Delivery": float(getattr(settings, "rating_weight_delivery", 0.3) or 0.3),
		"Quality": float(getattr(settings, "rating_weight_quality", 0.3) or 0.3),
		"Pricing": float(getattr(settings, "rating_weight_pricing", 0.2) or 0.2),
		"Communication": float(getattr(settings, "rating_weight_communication", 0.2) or 0.2),
	}

	# Aggregate average scores per rating_type for this supplier
	ratings = frappe.db.sql(
		"""
		SELECT rating_type, AVG(score) as avg_score, COUNT(*) as cnt
		FROM `tabVendor Rating Log`
		WHERE supplier = %s
		GROUP BY rating_type
		""",
		(supplier_name,),
		as_dict=True,
	)

	if not ratings:
		frappe.db.set_value(
			"Supplier",
			supplier_name,
			{"vendor_rating": 0, "total_rating_count": 0},
			update_modified=False,
		)
		return 0.0, 0

	total_count = sum(int(r.cnt) for r in ratings)
	weighted_sum = 0.0
	total_weight = 0.0

	for r in ratings:
		weight = weights.get(r.rating_type, 0.25)
		weighted_sum += float(r.avg_score) * weight
		total_weight += weight

	final_rating = round(weighted_sum / total_weight, 2) if total_weight > 0 else 0.0

	frappe.db.set_value(
		"Supplier",
		supplier_name,
		{"vendor_rating": final_rating, "total_rating_count": total_count},
		update_modified=False,
	)

	return final_rating, total_count
