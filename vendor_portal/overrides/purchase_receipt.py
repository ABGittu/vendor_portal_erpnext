# Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import date_diff, getdate
from vendor_portal.utils import recalculate_vendor_rating


def validate(doc, method=None):
	"""
	Purchase Receipt validate hook via doc_events:
	Checks if any item in the receipt has accepted_qty (qty) < 90% of qty_ordered from the linked PO.
	If so, sets doc.flags.has_short_delivery = True and adds a comment to the document.
	"""
	has_short_delivery = False
	short_items = []

	for item in doc.items:
		if item.purchase_order and item.purchase_order_item:
			ordered_qty = frappe.db.get_value("Purchase Order Item", item.purchase_order_item, "qty")
			if ordered_qty and float(ordered_qty) > 0:
				accepted_qty = float(item.qty or 0)
				if accepted_qty < 0.9 * float(ordered_qty):
					has_short_delivery = True
					short_items.append(
						_("Item {0}: received/accepted {1} of {2} ordered ({3}%)").format(
							item.item_code,
							accepted_qty,
							ordered_qty,
							round((accepted_qty / float(ordered_qty)) * 100, 1),
						)
					)

	doc.flags.has_short_delivery = has_short_delivery

	if has_short_delivery:
		comment_msg = _(
			"Short delivery detected: One or more items received less than 90% of the ordered quantity.<br>{0}"
		).format("<br>".join(short_items))

		# Add comment if document exists in DB and comment has not already been recorded
		if not doc.is_new() and doc.name:
			already_commented = frappe.db.exists(
				"Comment",
				{
					"reference_doctype": "Purchase Receipt",
					"reference_name": doc.name,
					"content": ["like", "%Short delivery detected%"],
				},
			)
			if not already_commented:
				doc.add_comment("Comment", comment_msg)


def on_submit(doc, method=None):
	"""
	Purchase Receipt on_submit hook via doc_events:
	Auto-creates a Vendor Rating Log with rating_type = 'Delivery'.
	Score evaluation:
	- 5: On-time and full quantity
	- 4: On-time but short delivery
	- 3: Late (>2 days past expected delivery date) but full quantity
	- 2: Late (>2 days past expected delivery date) and short delivery
	"""
	if not doc.supplier:
		return

	# Re-evaluate short delivery if flag was reset across sessions
	has_short_delivery = getattr(doc.flags, "has_short_delivery", None)
	if has_short_delivery is None:
		has_short_delivery = False
		for item in doc.items:
			if item.purchase_order and item.purchase_order_item:
				ordered_qty = frappe.db.get_value(
					"Purchase Order Item", item.purchase_order_item, "qty"
				)
				if ordered_qty and float(ordered_qty) > 0:
					accepted_qty = float(item.qty or 0)
					if accepted_qty < 0.9 * float(ordered_qty):
						has_short_delivery = True
						break

	# Identify linked Purchase Order and expected delivery date
	linked_po = None
	expected_date = None

	for item in doc.items:
		if item.purchase_order:
			linked_po = item.purchase_order
			# Check item schedule date first, then PO schedule date
			item_date = frappe.db.get_value(
				"Purchase Order Item", item.purchase_order_item, "schedule_date"
			) or frappe.db.get_value(
				"Purchase Order Item", item.purchase_order_item, "expected_delivery_date"
			)
			po_date = frappe.db.get_value("Purchase Order", linked_po, "schedule_date")
			expected_date = item_date or po_date
			if expected_date:
				break

	# Fallback if no linked PO or schedule date found
	posting_date = getdate(doc.posting_date)
	if expected_date:
		expected_date = getdate(expected_date)
		days_late = date_diff(posting_date, expected_date)
	else:
		days_late = 0

	# Delivery score logic:
	# Late if > 2 days past expected delivery date
	is_late = days_late > 2

	if is_late and has_short_delivery:
		score = 2.0
		remarks = _(
			"Delivery rating: Late delivery ({0} days past expected {1}) and short delivery (<90% qty)."
		).format(days_late, expected_date)
	elif is_late and not has_short_delivery:
		score = 3.0
		remarks = _(
			"Delivery rating: Late delivery ({0} days past expected {1}) with full quantity received."
		).format(days_late, expected_date)
	elif not is_late and has_short_delivery:
		score = 4.0
		remarks = _(
			"Delivery rating: On-time delivery but short delivery detected (<90% qty)."
		)
	else:
		score = 5.0
		remarks = _(
			"Delivery rating: On-time delivery with full quantity received."
		)

	# Auto-create Vendor Rating Log
	rating_log = frappe.get_doc({
		"doctype": "Vendor Rating Log",
		"supplier": doc.supplier,
		"purchase_order": linked_po,
		"purchase_receipt": doc.name,
		"rating_type": "Delivery",
		"score": score,
		"remarks": remarks,
		"rated_by": frappe.session.user,
		"rating_date": frappe.utils.today(),
	})
	rating_log.insert(ignore_permissions=True)

	# Recalculate supplier's weighted rating
	recalculate_vendor_rating(doc.supplier)
