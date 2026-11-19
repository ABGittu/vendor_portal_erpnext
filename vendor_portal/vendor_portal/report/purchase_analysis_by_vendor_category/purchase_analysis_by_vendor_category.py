# Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	report_summary = get_report_summary(data)

	return columns, data, None, chart, report_summary


def get_columns():
	return [
		{
			"label": _("Vendor Category"),
			"fieldname": "vendor_category",
			"fieldtype": "Link",
			"options": "Vendor Category",
			"width": 180,
		},
		{
			"label": _("Total Suppliers"),
			"fieldname": "total_suppliers",
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"label": _("Active Suppliers"),
			"fieldname": "active_suppliers",
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"label": _("Total PO Value"),
			"fieldname": "total_po_value",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 150,
		},
		{
			"label": _("Avg PO Value"),
			"fieldname": "avg_po_value",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 140,
		},
		{
			"label": _("Total Items Purchased"),
			"fieldname": "total_items_purchased",
			"fieldtype": "Float",
			"precision": 2,
			"width": 150,
		},
		{
			"label": _("Avg Vendor Rating"),
			"fieldname": "avg_vendor_rating",
			"fieldtype": "Float",
			"precision": 2,
			"width": 140,
		},
		{
			"label": _("Lowest Rating Supplier"),
			"fieldname": "lowest_rating_supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 180,
		},
	]


def get_data(filters):
	cat_conditions = []
	cat_values = {}

	if filters.get("vendor_category"):
		cat_conditions.append("name = %(vendor_category)s")
		cat_values["vendor_category"] = filters.get("vendor_category")

	cat_where = " WHERE " + " AND ".join(cat_conditions) if cat_conditions else ""
	categories = frappe.db.sql_list(f"SELECT name FROM `tabVendor Category` {cat_where} ORDER BY name")

	if not categories:
		# Check if any suppliers have categories not in Vendor Category doctype
		categories = frappe.db.sql_list(
			"SELECT DISTINCT vendor_category FROM `tabSupplier` WHERE vendor_category IS NOT NULL AND vendor_category != ''"
		)

	if not categories:
		return []

	po_conditions = ["po.docstatus = 1"]
	po_values = {}
	if filters.get("from_date"):
		po_conditions.append("po.transaction_date >= %(from_date)s")
		po_values["from_date"] = filters.get("from_date")
	if filters.get("to_date"):
		po_conditions.append("po.transaction_date <= %(to_date)s")
		po_values["to_date"] = filters.get("to_date")

	po_where = " AND ".join(po_conditions)

	data = []

	for category in categories:
		# Suppliers in this category
		suppliers = frappe.db.sql(
			"""
			SELECT
				name,
				disabled,
				COALESCE(vendor_rating, 0) as vendor_rating
			FROM `tabSupplier`
			WHERE vendor_category = %s
			ORDER BY vendor_rating ASC
			""",
			(category,),
			as_dict=True,
		)

		total_suppliers = len(suppliers)
		active_suppliers = len([s for s in suppliers if not s.disabled])

		if suppliers:
			ratings = [float(s.vendor_rating) for s in suppliers if float(s.vendor_rating) > 0]
			avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0.0
			lowest_supplier = suppliers[0].name if suppliers else None
		else:
			avg_rating = 0.0
			lowest_supplier = None

		# PO Stats for this category
		po_stats = frappe.db.sql(
			f"""
			SELECT
				COUNT(DISTINCT po.name) as po_count,
				COALESCE(SUM(po.grand_total), 0) as total_po_value,
				COALESCE(SUM(poi.qty), 0) as total_items
			FROM `tabPurchase Order` po
			JOIN `tabSupplier` s ON s.name = po.supplier
			LEFT JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
			WHERE s.vendor_category = %s
			  AND {po_where}
			""",
			(category,),
			as_dict=True,
		)[0]

		po_count = int(po_stats.po_count or 0)
		total_val = round(float(po_stats.total_po_value or 0), 2)
		avg_val = round(total_val / po_count, 2) if po_count > 0 else 0.0
		total_items = round(float(po_stats.total_items or 0), 2)

		data.append({
			"vendor_category": category,
			"total_suppliers": total_suppliers,
			"active_suppliers": active_suppliers,
			"total_po_value": total_val,
			"avg_po_value": avg_val,
			"total_items_purchased": total_items,
			"avg_vendor_rating": avg_rating,
			"lowest_rating_supplier": lowest_supplier or "-",
		})

	return data


def get_chart(data):
	if not data:
		return None

	# Filter out 0 value categories if some have values
	categories = [d["vendor_category"] for d in data]
	values = [d["total_po_value"] for d in data]

	# If all zero, default to total suppliers
	if sum(values) == 0:
		values = [d["total_suppliers"] for d in data]

	return {
		"data": {
			"labels": categories,
			"datasets": [
				{
					"name": _("PO Value Distribution"),
					"values": values,
				}
			],
		},
		"type": "pie",
	}


def get_report_summary(data):
	if not data:
		return []

	total_cats = len(data)
	total_po_val = sum(d["total_po_value"] for d in data)
	total_items = sum(d["total_items_purchased"] for d in data)

	currency = frappe.db.get_default("currency") or "INR"

	return [
		{
			"value": total_cats,
			"label": _("Vendor Categories"),
			"datatype": "Int",
		},
		{
			"value": total_po_val,
			"label": _("Total PO Value Across Categories"),
			"datatype": "Currency",
			"currency": currency,
		},
		{
			"value": total_items,
			"label": _("Total Items Purchased"),
			"datatype": "Float",
		},
	]
