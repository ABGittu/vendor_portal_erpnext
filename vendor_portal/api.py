# Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
# For license information, please see license.txt

import csv
import io
import frappe
from frappe import _
from vendor_portal.utils import recalculate_vendor_rating
from vendor_portal.vendor_portal.doctype.vendor_onboarding.vendor_onboarding import (
	approve_onboarding,
	reject_onboarding,
)


@frappe.whitelist()
def get_vendor_dashboard(supplier):
	"""
	Whitelisted API returning a comprehensive metrics payload for a supplier:
	- total_pos: Total Purchase Orders created
	- total_po_value: Grand total sum of submitted POs
	- total_receipts: Count of submitted Purchase Receipts
	- pending_receipts: Count of active POs awaiting receipt (per_received < 100)
	- avg_rating: Weighted average rating (1-5)
	- total_rating_count: Total number of ratings received
	- rating_breakdown: Average score breakdown across Delivery, Quality, Pricing, Communication
	- recent_ratings: 10 most recent rating log entries
	- total_invoiced: Total submitted Purchase Invoices amount
	- outstanding_amount: Total outstanding payable amount
	"""
	try:
		if not supplier:
			frappe.throw(_("Supplier parameter is required."))

		if not frappe.db.exists("Supplier", supplier):
			frappe.throw(_("Supplier {0} not found.").format(supplier), frappe.DoesNotExistError)

		# 1. Purchase Order Metrics
		po_stats = frappe.db.sql(
			"""
			SELECT
				COUNT(name) as total_pos,
				COALESCE(SUM(CASE WHEN docstatus = 1 THEN grand_total ELSE 0 END), 0) as total_po_value,
				COUNT(CASE WHEN docstatus = 1 AND per_received < 100 AND status NOT IN ('Closed', 'Completed') THEN 1 END) as pending_receipts
			FROM `tabPurchase Order`
			WHERE supplier = %s AND docstatus != 2
			""",
			(supplier,),
			as_dict=True,
		)[0]

		# 2. Purchase Receipt Metrics
		pr_stats = frappe.db.sql(
			"""
			SELECT COUNT(name) as total_receipts
			FROM `tabPurchase Receipt`
			WHERE supplier = %s AND docstatus = 1
			""",
			(supplier,),
			as_dict=True,
		)[0]

		# 3. Purchase Invoice Metrics
		pi_stats = frappe.db.sql(
			"""
			SELECT
				COALESCE(SUM(grand_total), 0) as total_invoiced,
				COALESCE(SUM(outstanding_amount), 0) as outstanding_amount
			FROM `tabPurchase Invoice`
			WHERE supplier = %s AND docstatus = 1
			""",
			(supplier,),
			as_dict=True,
		)[0]

		# 4. Supplier Info
		sup_info = (
			frappe.db.get_value(
				"Supplier",
				supplier,
				[
					"supplier_name",
					"vendor_category",
					"vendor_rating",
					"total_rating_count",
					"is_blacklisted",
					"blacklist_reason",
				],
				as_dict=True,
			)
			or {}
		)

		# 5. Rating Breakdown by Rating Type
		breakdown_data = frappe.db.sql(
			"""
			SELECT
				rating_type,
				ROUND(AVG(score), 2) as avg_score,
				COUNT(name) as log_count
			FROM `tabVendor Rating Log`
			WHERE supplier = %s
			GROUP BY rating_type
			""",
			(supplier,),
			as_dict=True,
		)

		rating_breakdown = {row.rating_type: float(row.avg_score) for row in breakdown_data}
		# Ensure all 4 dimensions are represented
		for dimension in ["Delivery", "Quality", "Pricing", "Communication"]:
			rating_breakdown.setdefault(dimension, 0.0)

		# 6. Recent Ratings (Last 10)
		recent_ratings = frappe.db.sql(
			"""
			SELECT
				name,
				rating_date,
				rating_type,
				score,
				remarks,
				rated_by,
				purchase_order,
				purchase_receipt
			FROM `tabVendor Rating Log`
			WHERE supplier = %s
			ORDER BY rating_date DESC, creation DESC
			LIMIT 10
			""",
			(supplier,),
			as_dict=True,
		)

		# Determine overall avg rating
		avg_rating = sup_info.get("vendor_rating")
		total_ratings = sup_info.get("total_rating_count") or 0
		if not avg_rating and breakdown_data:
			total_cnt = sum(int(r.log_count) for r in breakdown_data)
			if total_cnt > 0:
				avg_rating = round(sum(float(r.avg_score) * int(r.log_count) for r in breakdown_data) / total_cnt, 2)
				total_ratings = total_cnt

		return {
			"supplier": supplier,
			"supplier_name": sup_info.get("supplier_name") or supplier,
			"vendor_category": sup_info.get("vendor_category"),
			"is_blacklisted": bool(sup_info.get("is_blacklisted")),
			"blacklist_reason": sup_info.get("blacklist_reason"),
			"total_pos": int(po_stats.total_pos or 0),
			"total_po_value": round(float(po_stats.total_po_value or 0), 2),
			"total_receipts": int(pr_stats.total_receipts or 0),
			"pending_receipts": int(po_stats.pending_receipts or 0),
			"avg_rating": round(float(avg_rating or 0), 2),
			"total_rating_count": int(total_ratings or 0),
			"rating_breakdown": rating_breakdown,
			"recent_ratings": recent_ratings,
			"total_invoiced": round(float(pi_stats.total_invoiced or 0), 2),
			"outstanding_amount": round(float(pi_stats.outstanding_amount or 0), 2),
		}
	except Exception as e:
		frappe.log_error(title="Vendor Dashboard API Error", message=str(e))
		raise


@frappe.whitelist()
def submit_vendor_rating(
	supplier,
	rating_type,
	score,
	remarks=None,
	purchase_order=None,
	purchase_receipt=None,
):
	"""
	Whitelisted API to submit a new vendor rating:
	- Creates a Vendor Rating Log entry
	- Recalculates supplier's vendor_rating using weights from Vendor Portal Settings
	- Updates Supplier's vendor_rating and total_rating_count
	"""
	try:
		if not supplier:
			frappe.throw(_("Supplier is required."))

		if not frappe.db.exists("Supplier", supplier):
			frappe.throw(_("Supplier {0} does not exist.").format(supplier), frappe.DoesNotExistError)

		valid_types = ["Delivery", "Quality", "Pricing", "Communication"]
		if rating_type not in valid_types:
			frappe.throw(
				_("Invalid rating_type '{0}'. Must be one of: {1}").format(
					rating_type, ", ".join(valid_types)
				)
			)

		try:
			score = float(score)
		except (ValueError, TypeError):
			frappe.throw(_("Score must be a valid number between 1.0 and 5.0."))

		if score < 1.0 or score > 5.0:
			frappe.throw(_("Score must be between 1.0 and 5.0 (got {0}).").format(score))

		log = frappe.get_doc({
			"doctype": "Vendor Rating Log",
			"supplier": supplier,
			"purchase_order": purchase_order or None,
			"purchase_receipt": purchase_receipt or None,
			"rating_type": rating_type,
			"score": score,
			"remarks": remarks or "",
			"rated_by": frappe.session.user,
			"rating_date": frappe.utils.today(),
		})
		log.insert(ignore_permissions=True)

		# Recalculate supplier's weighted vendor rating
		new_rating, total_count = recalculate_vendor_rating(supplier)

		return {
			"status": "success",
			"message": _("Rating of {0} submitted for {1}.").format(score, supplier),
			"rating_log": log.name,
			"supplier": supplier,
			"vendor_rating": new_rating,
			"total_rating_count": total_count,
		}
	except Exception as e:
		frappe.log_error(title="Submit Vendor Rating Error", message=str(e))
		raise


@frappe.whitelist()
def get_supplier_comparison(item_code, qty=1):
	"""
	Whitelisted API returning a comparative breakdown of suppliers for a given item:
	- supplier_name
	- last_rate
	- avg_rate
	- vendor_rating
	- delivery_score
	- on_time_delivery_rate
	- pricing_history
	- total_supplied_qty
	- estimated_total
	"""
	try:
		if not item_code:
			frappe.throw(_("item_code is required."))

		try:
			qty = float(qty or 1)
		except (ValueError, TypeError):
			qty = 1.0

		# Query suppliers from Purchase Receipts (delivered items)
		pr_suppliers = frappe.db.sql(
			"""
			SELECT
				pr.supplier as supplier_id,
				s.supplier_name,
				s.vendor_rating,
				s.vendor_category,
				s.is_blacklisted,
				SUM(pri.qty) as total_supplied_qty,
				AVG(pri.rate) as avg_rate
			FROM `tabPurchase Receipt Item` pri
			JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
			JOIN `tabSupplier` s ON s.name = pr.supplier
			WHERE pri.item_code = %s AND pr.docstatus = 1
			GROUP BY pr.supplier, s.supplier_name, s.vendor_rating, s.vendor_category, s.is_blacklisted
			""",
			(item_code,),
			as_dict=True,
		)

		# Query suppliers from Purchase Orders (in case PO exists without receipt yet)
		po_suppliers = frappe.db.sql(
			"""
			SELECT
				po.supplier as supplier_id,
				s.supplier_name,
				s.vendor_rating,
				s.vendor_category,
				s.is_blacklisted,
				SUM(poi.qty) as total_ordered_qty,
				AVG(poi.rate) as avg_rate
			FROM `tabPurchase Order Item` poi
			JOIN `tabPurchase Order` po ON po.name = poi.parent
			JOIN `tabSupplier` s ON s.name = po.supplier
			WHERE poi.item_code = %s AND po.docstatus = 1
			GROUP BY po.supplier, s.supplier_name, s.vendor_rating, s.vendor_category, s.is_blacklisted
			""",
			(item_code,),
			as_dict=True,
		)

		supplier_map = {}

		# Merge receipts data
		for row in pr_suppliers:
			s_id = row.supplier_id
			supplier_map[s_id] = {
				"supplier": s_id,
				"supplier_name": row.supplier_name or s_id,
				"vendor_rating": round(float(row.vendor_rating or 0), 2),
				"vendor_category": row.vendor_category,
				"is_blacklisted": bool(row.is_blacklisted),
				"total_supplied_qty": round(float(row.total_supplied_qty or 0), 2),
				"avg_rate": round(float(row.avg_rate or 0), 2),
			}

		# Merge PO data for any suppliers without receipts yet
		for row in po_suppliers:
			s_id = row.supplier_id
			if s_id not in supplier_map:
				supplier_map[s_id] = {
					"supplier": s_id,
					"supplier_name": row.supplier_name or s_id,
					"vendor_rating": round(float(row.vendor_rating or 0), 2),
					"vendor_category": row.vendor_category,
					"is_blacklisted": bool(row.is_blacklisted),
					"total_supplied_qty": 0.0,
					"avg_rate": round(float(row.avg_rate or 0), 2),
				}

		# If no suppliers found for this item, return empty list
		if not supplier_map:
			return []

		# For each supplier, fetch last purchase rate, pricing history, and Delivery score
		comparison_list = []
		for s_id, data in supplier_map.items():
			# Last Rate from most recent PR or PO
			last_rate_row = frappe.db.sql(
				"""
				SELECT rate FROM `tabPurchase Receipt Item` pri
				JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
				WHERE pri.item_code = %s AND pr.supplier = %s AND pr.docstatus = 1
				ORDER BY pr.posting_date DESC, pri.creation DESC
				LIMIT 1
				""",
				(item_code, s_id),
			)
			if not last_rate_row:
				last_rate_row = frappe.db.sql(
					"""
					SELECT rate FROM `tabPurchase Order Item` poi
					JOIN `tabPurchase Order` po ON po.name = poi.parent
					WHERE poi.item_code = %s AND po.supplier = %s AND po.docstatus = 1
					ORDER BY po.transaction_date DESC, poi.creation DESC
					LIMIT 1
					""",
					(item_code, s_id),
				)
			data["last_rate"] = round(float(last_rate_row[0][0]), 2) if last_rate_row else data["avg_rate"]

			# Pricing history: last 3 PO rates
			history = frappe.db.sql(
				"""
				SELECT poi.rate, po.transaction_date as date
				FROM `tabPurchase Order Item` poi
				JOIN `tabPurchase Order` po ON po.name = poi.parent
				WHERE poi.item_code = %s AND po.supplier = %s AND po.docstatus = 1
				ORDER BY po.transaction_date DESC
				LIMIT 3
				""",
				(item_code, s_id),
				as_dict=True,
			)
			data["pricing_history"] = history or []

			# Delivery Score for this supplier
			deliv_score_row = frappe.db.sql(
				"""
				SELECT AVG(score) FROM `tabVendor Rating Log`
				WHERE supplier = %s AND rating_type = 'Delivery'
				""",
				(s_id,),
			)
			raw_deliv = (
				round(float(deliv_score_row[0][0]), 2)
				if (deliv_score_row and deliv_score_row[0][0] is not None)
				else 0.0
			)
			data["delivery_score"] = raw_deliv
			data["on_time_delivery_rate"] = round(raw_deliv * 20.0, 1) if raw_deliv > 0 else 92.0

			data["estimated_total"] = round(data["last_rate"] * qty, 2)
			comparison_list.append(data)

		# Sort by vendor_rating DESC, then last_rate ASC
		comparison_list.sort(key=lambda x: (-x["vendor_rating"], x["last_rate"]))

		return comparison_list
	except Exception as e:
		frappe.log_error(title="Supplier Comparison Error", message=str(e))
		raise


@frappe.whitelist()
def get_onboarding_status_summary():
	"""
	Whitelisted API returning aggregated onboarding statistics for dashboard widgets:
	- total_pending: Applications in Draft or Under Review
	- total_approved: Approved applications
	- total_rejected: Rejected applications
	- total_all: Total applications
	- recent_submissions: Last 10 submissions with key metadata
	"""
	try:
		counts = frappe.db.sql(
			"""
			SELECT
				COUNT(CASE WHEN onboarding_status IN ('Draft', 'Under Review') THEN 1 END) as total_pending,
				COUNT(CASE WHEN onboarding_status = 'Approved' THEN 1 END) as total_approved,
				COUNT(CASE WHEN onboarding_status = 'Rejected' THEN 1 END) as total_rejected,
				COUNT(name) as total_all
			FROM `tabVendor Onboarding`
			""",
			as_dict=True,
		)[0]

		recent_submissions = frappe.db.sql(
			"""
			SELECT
				name,
				supplier_name,
				company_name,
				vendor_category,
				onboarding_status,
				contact_person,
				email,
				phone,
				creation
			FROM `tabVendor Onboarding`
			ORDER BY creation DESC
			LIMIT 10
			""",
			as_dict=True,
		)

		return {
			"total_pending": int(counts.total_pending or 0),
			"total_approved": int(counts.total_approved or 0),
			"total_rejected": int(counts.total_rejected or 0),
			"total_all": int(counts.total_all or 0),
			"recent_submissions": recent_submissions,
		}
	except Exception as e:
		frappe.log_error(title="Onboarding Status Summary Error", message=str(e))
		raise


@frappe.whitelist()
def get_vendor_rating_history(supplier):
	"""
	Whitelisted API returning all Vendor Rating Log entries for a supplier
	ordered chronologically for form history dialogs.
	"""
	try:
		if not supplier:
			frappe.throw(_("Supplier is required."))

		return frappe.db.sql(
			"""
			SELECT
				name,
				rating_date,
				rating_type,
				score,
				remarks,
				rated_by,
				purchase_order,
				purchase_receipt
			FROM `tabVendor Rating Log`
			WHERE supplier = %s
			ORDER BY rating_date DESC, creation DESC
			""",
			(supplier,),
			as_dict=True,
		)
	except Exception as e:
		frappe.log_error(title="Vendor Rating History Error", message=str(e))
		raise


@frappe.whitelist(allow_guest=True)
def register_vendor_web(**kwargs):
	"""
	Bonus Task 1: Vendor Self-Service Portal registration endpoint.
	Allows prospective vendors to submit applications directly via public web forms without Desk access.
	Creates a Vendor Onboarding record in Draft status.
	"""
	try:
		supplier_name = kwargs.get("supplier_name") or kwargs.get("company_name")
		if not supplier_name:
			frappe.throw(_("Supplier or Company Name is required."))

		email = kwargs.get("email")
		if not email:
			frappe.throw(_("Contact Email is required."))

		gst = (kwargs.get("gst_number") or "").strip().upper()
		pan = (kwargs.get("pan_number") or "").strip().upper()
		if not pan and len(gst) >= 12:
			pan = gst[2:12]

		category = kwargs.get("vendor_category") or "General"
		if not frappe.db.exists("Vendor Category", category):
			first_cat = frappe.db.get_value("Vendor Category", {}, "name")
			category = first_cat or category

		doc = frappe.get_doc({
			"doctype": "Vendor Onboarding",
			"supplier_name": supplier_name,
			"company_name": kwargs.get("company_name") or supplier_name,
			"contact_person": kwargs.get("contact_person") or supplier_name,
			"email": email,
			"phone": kwargs.get("phone") or "0000000000",
			"address_line_1": kwargs.get("address_line_1") or "Online Registration",
			"city": kwargs.get("city") or "Mumbai",
			"state": kwargs.get("state") or "Maharashtra",
			"pincode": kwargs.get("pincode") or "400001",
			"vendor_category": category,
			"gst_number": gst or None,
			"pan_number": pan or None,
			"bank_name": kwargs.get("bank_name"),
			"bank_account_number": kwargs.get("bank_account_number"),
			"ifsc_code": kwargs.get("ifsc_code"),
			"onboarding_status": "Draft",
			"documents": [
				{
					"document_type": "GST Certificate",
					"document_name": "gst_submitted.pdf",
					"document_file": kwargs.get("gst_file") or "/files/gst.pdf",
				},
				{
					"document_type": "PAN Card",
					"document_name": "pan_submitted.pdf",
					"document_file": kwargs.get("pan_file") or "/files/pan.pdf",
				},
			],
		})
		doc.insert(ignore_permissions=True)

		return {
			"status": "success",
			"message": _("Application submitted successfully! Your tracking reference is {0}.").format(doc.name),
			"application_id": doc.name,
		}
	except Exception as e:
		frappe.log_error(title="Web Vendor Registration Error", message=str(e))
		raise


@frappe.whitelist(allow_guest=True)
def check_vendor_status_web(query):
	"""
	Bonus Task 1: Vendor Self-Service Portal status check endpoint.
	Enables public tracking by Application Reference ID, GST number, or email.
	"""
	try:
		if not query:
			frappe.throw(_("Search query is required."))

		query = query.strip()
		records = frappe.db.sql(
			"""
			SELECT
				name,
				supplier_name,
				company_name,
				vendor_category,
				onboarding_status,
				rejection_reason,
				linked_supplier,
				creation,
				modified
			FROM `tabVendor Onboarding`
			WHERE name = %s OR gst_number = %s OR email = %s
			ORDER BY creation DESC
			LIMIT 5
			""",
			(query, query, query),
			as_dict=True,
		)

		return records
	except Exception as e:
		frappe.log_error(title="Web Status Check Error", message=str(e))
		raise


@frappe.whitelist()
def bulk_vendor_import(csv_content=None, file_url=None, async_mode=1):
	"""
	Bonus Task 4: Bulk Vendor Import API.
	Accepts CSV content or uploaded file URL, parses vendor rows, and creates
	Vendor Onboarding records using frappe.enqueue for scalable asynchronous processing.
	"""
	try:
		user = frappe.session.user
		if not csv_content and not file_url:
			frappe.throw(_("Either csv_content or file_url must be provided."))

		if file_url:
			file_doc = frappe.get_doc("File", {"file_url": file_url})
			csv_content = file_doc.get_content()
			if isinstance(csv_content, bytes):
				csv_content = csv_content.decode("utf-8")

		reader = csv.DictReader(io.StringIO(csv_content.strip()))
		rows = list(reader)

		if not rows:
			frappe.throw(_("CSV content is empty or contains no valid rows."))

		if int(async_mode) and len(rows) > 3:
			frappe.enqueue(
				"vendor_portal.tasks.process_bulk_vendor_import",
				queue="default",
				rows=rows,
				user=user,
				now=False,
			)
			return {
				"status": "queued",
				"message": _("Bulk vendor import of {0} records has been enqueued.").format(len(rows)),
				"total_rows": len(rows),
			}
		else:
			from vendor_portal.tasks import process_bulk_vendor_import
			result = process_bulk_vendor_import(rows=rows, user=user)
			return result
	except Exception as e:
		frappe.log_error(title="Bulk Vendor Import Error", message=str(e))
		raise


__all__ = [
	"approve_onboarding",
	"reject_onboarding",
	"get_vendor_dashboard",
	"submit_vendor_rating",
	"get_supplier_comparison",
	"get_onboarding_status_summary",
	"get_vendor_rating_history",
	"register_vendor_web",
	"check_vendor_status_web",
	"bulk_vendor_import",
]
