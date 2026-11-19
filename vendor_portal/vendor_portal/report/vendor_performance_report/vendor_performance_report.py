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
			"label": _("Supplier"),
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 180,
		},
		{
			"label": _("Vendor Category"),
			"fieldname": "vendor_category",
			"fieldtype": "Link",
			"options": "Vendor Category",
			"width": 150,
		},
		{
			"label": _("Total POs"),
			"fieldname": "total_pos",
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"label": _("Total PO Value"),
			"fieldname": "total_po_value",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 140,
		},
		{
			"label": _("Avg Delivery Score"),
			"fieldname": "avg_delivery_score",
			"fieldtype": "Float",
			"precision": 2,
			"width": 140,
		},
		{
			"label": _("Avg Quality Score"),
			"fieldname": "avg_quality_score",
			"fieldtype": "Float",
			"precision": 2,
			"width": 140,
		},
		{
			"label": _("Avg Pricing Score"),
			"fieldname": "avg_pricing_score",
			"fieldtype": "Float",
			"precision": 2,
			"width": 140,
		},
		{
			"label": _("Overall Rating"),
			"fieldname": "overall_rating",
			"fieldtype": "Float",
			"precision": 2,
			"width": 120,
		},
		{
			"label": _("Total Receipts"),
			"fieldname": "total_receipts",
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"label": _("On-Time Delivery %"),
			"fieldname": "on_time_delivery_pct",
			"fieldtype": "Percent",
			"width": 150,
		},
		{
			"label": _("Short Delivery Count"),
			"fieldname": "short_delivery_count",
			"fieldtype": "Int",
			"width": 150,
		},
	]


def get_data(filters):
	conditions = []
	values = {}

	if filters.get("vendor_category"):
		conditions.append("s.vendor_category = %(vendor_category)s")
		values["vendor_category"] = filters.get("vendor_category")

	if filters.get("supplier"):
		conditions.append("s.name = %(supplier)s")
		values["supplier"] = filters.get("supplier")

	if filters.get("minimum_rating"):
		conditions.append("s.vendor_rating >= %(minimum_rating)s")
		values["minimum_rating"] = float(filters.get("minimum_rating"))

	where_clause = " AND ".join(conditions)
	if where_clause:
		where_clause = "WHERE " + where_clause
	else:
		where_clause = "WHERE s.disabled = 0"

	# Date filters for transactions
	po_date_cond = ""
	pr_date_cond = ""
	if filters.get("from_date"):
		po_date_cond += " AND po.transaction_date >= %(from_date)s"
		pr_date_cond += " AND pr.posting_date >= %(from_date)s"
		values["from_date"] = filters.get("from_date")
	if filters.get("to_date"):
		po_date_cond += " AND po.transaction_date <= %(to_date)s"
		pr_date_cond += " AND pr.posting_date <= %(to_date)s"
		values["to_date"] = filters.get("to_date")

	# Fetch base suppliers
	suppliers = frappe.db.sql(
		f"""
		SELECT
			s.name as supplier,
			s.supplier_name,
			s.vendor_category,
			COALESCE(s.vendor_rating, 0) as overall_rating
		FROM `tabSupplier` s
		{where_clause}
		ORDER BY s.vendor_rating DESC, s.name ASC
		""",
		values,
		as_dict=True,
	)

	if not suppliers:
		return []

	supplier_names = [s.supplier for s in suppliers]

	# 1. Purchase Order aggregation
	po_data = frappe.db.sql(
		f"""
		SELECT
			po.supplier,
			COUNT(po.name) as total_pos,
			COALESCE(SUM(po.grand_total), 0) as total_po_value
		FROM `tabPurchase Order` po
		WHERE po.supplier IN %(suppliers)s
		  AND po.docstatus = 1
		  {po_date_cond}
		GROUP BY po.supplier
		""",
		{"suppliers": supplier_names, **values},
		as_dict=True,
	)
	po_map = {row.supplier: row for row in po_data}

	# 2. Purchase Receipt & Delivery Metrics
	pr_data = frappe.db.sql(
		f"""
		SELECT
			pr.supplier,
			COUNT(DISTINCT pr.name) as total_receipts,
			COUNT(DISTINCT CASE
				WHEN pr.posting_date <= COALESCE(po.schedule_date, pr.posting_date) THEN pr.name
			END) as on_time_receipts,
			COUNT(DISTINCT CASE
				WHEN pri.qty < COALESCE(poi.qty, pri.qty) THEN pr.name
			END) as short_delivery_count
		FROM `tabPurchase Receipt` pr
		LEFT JOIN `tabPurchase Receipt Item` pri ON pri.parent = pr.name
		LEFT JOIN `tabPurchase Order` po ON po.name = pri.purchase_order
		LEFT JOIN `tabPurchase Order Item` poi ON poi.name = pri.purchase_order_item
		WHERE pr.supplier IN %(suppliers)s
		  AND pr.docstatus = 1
		  {pr_date_cond}
		GROUP BY pr.supplier
		""",
		{"suppliers": supplier_names, **values},
		as_dict=True,
	)
	pr_map = {row.supplier: row for row in pr_data}

	# 3. Rating Log Breakdown per dimension
	rating_data = frappe.db.sql(
		"""
		SELECT
			vrl.supplier,
			AVG(CASE WHEN vrl.rating_type = 'Delivery' THEN vrl.score END) as avg_delivery_score,
			AVG(CASE WHEN vrl.rating_type = 'Quality' THEN vrl.score END) as avg_quality_score,
			AVG(CASE WHEN vrl.rating_type = 'Pricing' THEN vrl.score END) as avg_pricing_score
		FROM `tabVendor Rating Log` vrl
		WHERE vrl.supplier IN %(suppliers)s
		GROUP BY vrl.supplier
		""",
		{"suppliers": supplier_names},
		as_dict=True,
	)
	rating_map = {row.supplier: row for row in rating_data}

	# Assemble final dataset
	data = []
	for s in suppliers:
		po_info = po_map.get(s.supplier, {})
		pr_info = pr_map.get(s.supplier, {})
		r_info = rating_map.get(s.supplier, {})

		total_rec = int(pr_info.get("total_receipts") or 0)
		on_time_rec = int(pr_info.get("on_time_receipts") or 0)
		on_time_pct = round((on_time_rec / total_rec) * 100, 2) if total_rec > 0 else 0.0

		data.append({
			"supplier": s.supplier,
			"supplier_name": s.supplier_name or s.supplier,
			"vendor_category": s.vendor_category or "-",
			"total_pos": int(po_info.get("total_pos") or 0),
			"total_po_value": round(float(po_info.get("total_po_value") or 0), 2),
			"avg_delivery_score": round(float(r_info.get("avg_delivery_score") or 0), 2),
			"avg_quality_score": round(float(r_info.get("avg_quality_score") or 0), 2),
			"avg_pricing_score": round(float(r_info.get("avg_pricing_score") or 0), 2),
			"overall_rating": round(float(s.overall_rating or 0), 2),
			"total_receipts": total_rec,
			"on_time_delivery_pct": on_time_pct,
			"short_delivery_count": int(pr_info.get("short_delivery_count") or 0),
		})

	return data


def get_chart(data):
	if not data:
		return None

	# Top 10 suppliers by overall rating
	top_10 = sorted(data, key=lambda x: x["overall_rating"], reverse=True)[:10]

	labels = [d["supplier_name"] for d in top_10]
	values = [d["overall_rating"] for d in top_10]

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{
					"name": _("Overall Rating"),
					"values": values,
				}
			],
		},
		"type": "bar",
		"colors": ["#f59e0b"],
		"fieldtype": "Float",
	}


def get_report_summary(data):
	if not data:
		return []

	total_suppliers = len(data)
	total_po_val = sum(d["total_po_value"] for d in data)
	avg_overall = sum(d["overall_rating"] for d in data) / total_suppliers if total_suppliers else 0

	currency = frappe.db.get_default("currency") or "INR"

	return [
		{
			"value": total_suppliers,
			"label": _("Total Suppliers"),
			"datatype": "Int",
		},
		{
			"value": total_po_val,
			"label": _("Total PO Value"),
			"datatype": "Currency",
			"currency": currency,
		},
		{
			"value": round(avg_overall, 2),
			"label": _("Average Overall Rating"),
			"datatype": "Float",
		},
	]
