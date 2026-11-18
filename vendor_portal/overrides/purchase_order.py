# Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from erpnext.buying.doctype.purchase_order.purchase_order import PurchaseOrder
from vendor_portal.utils import recalculate_vendor_rating


class CustomPurchaseOrder(PurchaseOrder):
	"""
	Custom Purchase Order controller extending ERPNext PurchaseOrder:
	1. Blocks PO creation for blacklisted suppliers.
	2. Blocks PO creation if supplier rating is below category threshold.
	3. Automatically creates a Pricing Vendor Rating Log on submission.
	4. Cleans up linked Vendor Rating Logs on cancellation.

	Key Pattern: Always call super() first to preserve ERPNext standard behavior.
	"""

	def validate(self):
		# Always invoke ERPNext standard validations first
		super().validate()

		if not self.supplier:
			return

		# Fetch supplier rating and blacklist attributes
		supplier = frappe.db.get_value(
			"Supplier",
			self.supplier,
			[
				"is_blacklisted",
				"blacklist_reason",
				"vendor_category",
				"vendor_rating",
				"total_rating_count",
				"supplier_name",
			],
			as_dict=True,
		)

		if not supplier:
			return

		supplier_display = supplier.supplier_name or self.supplier

		# 1. Blacklist Check
		if supplier.is_blacklisted:
			reason = supplier.blacklist_reason or _("No reason provided")
			frappe.throw(
				_(
					"Cannot create Purchase Order for blacklisted supplier {0}. Reason: {1}"
				).format(supplier_display, reason)
			)

		# 2. Rating Threshold Check
		if supplier.vendor_category:
			min_threshold = frappe.db.get_value(
				"Vendor Category", supplier.vendor_category, "minimum_rating_threshold"
			)
			if min_threshold is not None:
				threshold = float(min_threshold)
				rating = float(supplier.vendor_rating or 0)

				# If rating logs exist, prefer calculated score from logs for accuracy
				if supplier.total_rating_count and int(supplier.total_rating_count) > 0:
					actual_avg = frappe.db.sql(
						"SELECT AVG(score) FROM `tabVendor Rating Log` WHERE supplier = %s",
						(self.supplier,),
					)[0][0]
					if actual_avg is not None:
						rating = round(float(actual_avg), 2)

				# Check if supplier has an established rating below threshold
				if supplier.total_rating_count and int(supplier.total_rating_count) > 0 and rating < threshold:
					frappe.throw(
						_(
							"Supplier {0} rating ({1}) is below the minimum threshold ({2}) for {3}."
						).format(supplier_display, rating, threshold, supplier.vendor_category)
					)
				elif rating > 0 and rating < threshold:
					frappe.throw(
						_(
							"Supplier {0} rating ({1}) is below the minimum threshold ({2}) for {3}."
						).format(supplier_display, rating, threshold, supplier.vendor_category)
					)

		# Log successful validation
		frappe.logger().info(f"PO {self.name} validated for supplier {self.supplier}")

	def on_submit(self):
		# Invoke ERPNext standard submission lifecycle first
		super().on_submit()

		if not self.supplier:
			return

		# Calculate historical average PO value for this supplier (excluding this PO)
		avg_po_val = frappe.db.sql(
			"""
			SELECT AVG(grand_total)
			FROM `tabPurchase Order`
			WHERE supplier = %s AND docstatus = 1 AND name != %s
			""",
			(self.supplier, self.name),
		)[0][0]

		if avg_po_val is not None and float(avg_po_val) > 0:
			avg_val = float(avg_po_val)
			current_val = float(self.grand_total or 0)
			# Compare current PO value with historical average
			if current_val < 0.9 * avg_val:
				score = 5.0
				remarks = _(
					"Pricing rating: Order value ({0}) is cheaper (>10% lower) than average PO value ({1})."
				).format(current_val, round(avg_val, 2))
			elif current_val > 1.1 * avg_val:
				score = 3.0
				remarks = _(
					"Pricing rating: Order value ({0}) is more expensive (>10% higher) than average PO value ({1})."
				).format(current_val, round(avg_val, 2))
			else:
				score = 4.0
				remarks = _(
					"Pricing rating: Order value ({0}) is within 10% of average PO value ({1})."
				).format(current_val, round(avg_val, 2))
		else:
			# First PO for this supplier: assign standard on-par rating
			score = 4.0
			remarks = _(
				"Pricing rating: First submitted Purchase Order for supplier. Standard rating assigned."
			)

		# Auto-create Vendor Rating Log entry
		rating_log = frappe.get_doc({
			"doctype": "Vendor Rating Log",
			"supplier": self.supplier,
			"purchase_order": self.name,
			"rating_type": "Pricing",
			"score": score,
			"remarks": remarks,
			"rated_by": frappe.session.user,
			"rating_date": frappe.utils.today(),
		})
		rating_log.insert(ignore_permissions=True)

		# Recalculate supplier's weighted vendor rating
		recalculate_vendor_rating(self.supplier)

	def on_cancel(self):
		# Invoke ERPNext standard cancellation lifecycle first
		super().on_cancel()

		# Delete any Vendor Rating Log entries linked to this PO
		frappe.db.delete("Vendor Rating Log", {"purchase_order": self.name})

		# Recalculate supplier's vendor rating after log deletion
		if self.supplier:
			recalculate_vendor_rating(self.supplier)
