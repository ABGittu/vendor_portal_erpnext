# Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_days, get_datetime, now_datetime, today
from vendor_portal.utils import recalculate_vendor_rating


def get_vendor_manager_emails():
	"""Helper to fetch emails of all active users with Vendor Manager or System Manager role."""
	users = frappe.db.sql_list(
		"""
		SELECT DISTINCT parent
		FROM `tabHas Role` hr
		JOIN `tabUser` u ON u.name = hr.parent
		WHERE hr.role IN ('Vendor Manager', 'System Manager')
		  AND u.enabled = 1
		  AND u.name NOT IN ('Administrator', 'Guest')
		"""
	)
	return users or ["admin@example.com"]


def auto_calculate_vendor_ratings():
	"""
	Task 3.1 A: Auto-Calculate Vendor Ratings (Daily).
	For each active Supplier with vendor_category set:
	- Fetch all Vendor Rating Logs and recalculate weighted average.
	- Update vendor_rating and total_rating_count on Supplier.
	- If rating drops below low_rating_threshold, send email alert to Vendor Managers.
	"""
	frappe.logger("vendor_portal").info("Executing auto_calculate_vendor_ratings daily job")
	settings = frappe.get_single("Vendor Portal Settings")
	low_threshold = float(getattr(settings, "low_rating_threshold", 2.5) or 2.5)

	# Fetch all active suppliers having vendor_category
	suppliers = frappe.get_all(
		"Supplier",
		filters={"disabled": 0, "vendor_category": ["is", "set"]},
		fields=["name", "supplier_name", "vendor_category", "vendor_rating"],
	)

	low_rated_suppliers = []

	for sup in suppliers:
		old_rating = float(sup.vendor_rating or 0)
		new_rating, total_count = recalculate_vendor_rating(sup.name)

		# Alert if rating drops below threshold and has ratings
		if total_count > 0 and new_rating < low_threshold and old_rating >= low_threshold:
			low_rated_suppliers.append({
				"supplier": sup.name,
				"supplier_name": sup.supplier_name or sup.name,
				"old_rating": old_rating,
				"new_rating": new_rating,
				"threshold": low_threshold,
			})

	# Send email alert to Vendor Managers if any suppliers dropped below threshold
	if low_rated_suppliers:
		recipients = get_vendor_manager_emails()
		if recipients:
			rows_html = "".join(
				f"<tr><td>{s['supplier_name']} ({s['supplier']})</td><td>{s['old_rating']:.2f} ★</td><td style='color:red;'><b>{s['new_rating']:.2f} ★</b></td><td>{s['threshold']} ★</td></tr>"
				for s in low_rated_suppliers
			)
			message = f"""
			<h3>Vendor Performance Alert: Low Ratings Detected</h3>
			<p>The following suppliers have dropped below the acceptable minimum rating threshold:</p>
			<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse; width:100%;">
				<thead>
					<tr style="background:#f3f4f6;">
						<th>Supplier</th><th>Previous Rating</th><th>New Rating</th><th>Threshold</th>
					</tr>
				</thead>
				<tbody>
					{rows_html}
				</tbody>
			</table>
			<p>Please review vendor performance and take corrective action.</p>
			"""
			try:
				frappe.sendmail(
					recipients=recipients,
					subject=_("ALERT: Suppliers Dropped Below Rating Threshold"),
					message=message,
					now=True,
				)
			except Exception as e:
				frappe.logger("vendor_portal").error(f"Failed to send low rating alert email: {e}")

	return len(suppliers)


def auto_rate_deliveries():
	"""
	Task 3.1 B: Auto-Rate Deliveries (Hourly).
	Find Purchase Receipts submitted in the last 2 hours that don't have
	a corresponding Vendor Rating Log with rating_type = 'Delivery'.
	Auto-creates rating entries based on delivery timeliness and quantity accuracy.
	"""
	frappe.logger("vendor_portal").info("Executing auto_rate_deliveries hourly job")
	two_hours_ago = add_days(now_datetime(), -0.0833)  # approx 2 hours

	# Find submitted Purchase Receipts in past 2 hours
	prs = frappe.db.sql(
		"""
		SELECT pr.name, pr.supplier, pr.posting_date, pr.modified
		FROM `tabPurchase Receipt` pr
		WHERE pr.docstatus = 1
		  AND pr.modified >= %s
		  AND NOT EXISTS (
			SELECT 1 FROM `tabVendor Rating Log` vrl
			WHERE vrl.purchase_receipt = pr.name
			  AND vrl.rating_type = 'Delivery'
		  )
		""",
		(two_hours_ago,),
		as_dict=True,
	)

	created_count = 0
	for pr_info in prs:
		pr_doc = frappe.get_doc("Purchase Receipt", pr_info.name)
		# Calculate Delivery Score:
		# Timeliness: Check against linked Purchase Order schedule_date
		on_time = True
		for item in pr_doc.items:
			if item.purchase_order:
				po_date = frappe.db.get_value("Purchase Order", item.purchase_order, "schedule_date")
				if po_date and get_datetime(pr_doc.posting_date) > get_datetime(po_date):
					on_time = False
					break

		# Quantity accuracy
		short_delivery = False
		for item in pr_doc.items:
			if item.purchase_order_item:
				po_qty = frappe.db.get_value("Purchase Order Item", item.purchase_order_item, "qty") or 0
				if item.qty < po_qty:
					short_delivery = True
					break

		if on_time and not short_delivery:
			score = 5.0
			remarks = "Auto-rated: Delivery on time and in full."
		elif on_time and short_delivery:
			score = 3.5
			remarks = "Auto-rated: Delivery on time but partial quantity."
		elif not on_time and not short_delivery:
			score = 3.0
			remarks = "Auto-rated: Late delivery with full quantity."
		else:
			score = 2.0
			remarks = "Auto-rated: Late and partial delivery."

		log = frappe.get_doc({
			"doctype": "Vendor Rating Log",
			"supplier": pr_doc.supplier,
			"purchase_receipt": pr_doc.name,
			"purchase_order": pr_doc.items[0].purchase_order if pr_doc.items and pr_doc.items[0].purchase_order else None,
			"rating_type": "Delivery",
			"score": score,
			"remarks": remarks,
			"rated_by": "Administrator",
			"rating_date": today(),
		})
		log.insert(ignore_permissions=True)
		recalculate_vendor_rating(pr_doc.supplier)
		created_count += 1

	return created_count


def send_vendor_performance_digest():
	"""
	Task 3.1 C: Vendor Performance Digest (Weekly).
	Sends an HTML email to all Vendor Managers with:
	- Top 5 vendors by rating
	- Bottom 5 vendors by rating
	- Total POs this week
	- New vendor onboardings this week
	- Vendors with rating below threshold
	"""
	frappe.logger("vendor_portal").info("Executing send_vendor_performance_digest weekly job")
	week_start = add_days(today(), -7)
	settings = frappe.get_single("Vendor Portal Settings")
	low_threshold = float(getattr(settings, "low_rating_threshold", 2.5) or 2.5)

	# 1. Top 5 Vendors
	top_vendors = frappe.db.sql(
		"""
		SELECT name, supplier_name, vendor_category, vendor_rating, total_rating_count
		FROM `tabSupplier`
		WHERE disabled = 0 AND total_rating_count > 0
		ORDER BY vendor_rating DESC, total_rating_count DESC
		LIMIT 5
		""",
		as_dict=True,
	)

	# 2. Bottom 5 Vendors
	bottom_vendors = frappe.db.sql(
		"""
		SELECT name, supplier_name, vendor_category, vendor_rating, total_rating_count
		FROM `tabSupplier`
		WHERE disabled = 0 AND total_rating_count > 0
		ORDER BY vendor_rating ASC, total_rating_count DESC
		LIMIT 5
		""",
		as_dict=True,
	)

	# 3. Total POs this week
	po_count = frappe.db.count("Purchase Order", filters={"transaction_date": [">=", week_start], "docstatus": 1})
	po_value = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(grand_total), 0)
		FROM `tabPurchase Order`
		WHERE transaction_date >= %s AND docstatus = 1
		""",
		(week_start,),
	)[0][0]

	# 4. New onboardings this week
	new_onboardings = frappe.db.count("Vendor Onboarding", filters={"creation": [">=", week_start]})

	# 5. Vendors below threshold
	below_threshold_vendors = frappe.db.sql(
		"""
		SELECT name, supplier_name, vendor_category, vendor_rating
		FROM `tabSupplier`
		WHERE disabled = 0 AND total_rating_count > 0 AND vendor_rating < %s
		ORDER BY vendor_rating ASC
		""",
		(low_threshold,),
		as_dict=True,
	)

	recipients = get_vendor_manager_emails()
	if not recipients:
		return

	# Build HTML message
	top_rows = "".join(f"<tr><td>{v.supplier_name or v.name}</td><td>{v.vendor_category or '-'}</td><td><b>{v.vendor_rating:.2f} ★</b></td><td>{v.total_rating_count}</td></tr>" for v in top_vendors) or "<tr><td colspan='4'>No data</td></tr>"
	bot_rows = "".join(f"<tr><td>{v.supplier_name or v.name}</td><td>{v.vendor_category or '-'}</td><td style='color:orange;'><b>{v.vendor_rating:.2f} ★</b></td><td>{v.total_rating_count}</td></tr>" for v in bottom_vendors) or "<tr><td colspan='4'>No data</td></tr>"
	warn_rows = "".join(f"<tr><td>{v.supplier_name or v.name}</td><td>{v.vendor_category or '-'}</td><td style='color:red;'><b>{v.vendor_rating:.2f} ★</b></td></tr>" for v in below_threshold_vendors) or "<tr><td colspan='3'>None 🎉</td></tr>"

	html = f"""
	<div style="font-family:sans-serif; max-width:700px; margin:auto;">
		<h2 style="color:#1f2937; border-bottom:2px solid #e5e7eb; padding-bottom:8px;">Weekly Vendor Performance Digest</h2>
		<p style="color:#4b5563;">Weekly executive summary for purchasing leadership and vendor managers.</p>

		<div style="display:flex; gap:16px; margin:20px 0;">
			<div style="flex:1; background:#f9fafb; padding:12px; border-radius:6px; border:1px solid #e5e7eb; text-align:center;">
				<div style="font-size:12px; color:#6b7280; text-transform:uppercase;">POs This Week</div>
				<div style="font-size:20px; font-weight:bold; color:#111827;">{po_count} (₹{po_value:,.2f})</div>
			</div>
			<div style="flex:1; background:#f9fafb; padding:12px; border-radius:6px; border:1px solid #e5e7eb; text-align:center;">
				<div style="font-size:12px; color:#6b7280; text-transform:uppercase;">New Onboardings</div>
				<div style="font-size:20px; font-weight:bold; color:#2563eb;">{new_onboardings}</div>
			</div>
			<div style="flex:1; background:#f9fafb; padding:12px; border-radius:6px; border:1px solid #e5e7eb; text-align:center;">
				<div style="font-size:12px; color:#6b7280; text-transform:uppercase;">Vendors Below Threshold</div>
				<div style="font-size:20px; font-weight:bold; color:#dc2626;">{len(below_threshold_vendors)}</div>
			</div>
		</div>

		<h3>🏆 Top 5 Vendors by Rating</h3>
		<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse; width:100%; margin-bottom:20px;">
			<tr style="background:#f3f4f6;"><th>Supplier</th><th>Category</th><th>Rating</th><th>Ratings Count</th></tr>
			{top_rows}
		</table>

		<h3>⚠️ Bottom 5 Vendors by Rating</h3>
		<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse; width:100%; margin-bottom:20px;">
			<tr style="background:#f3f4f6;"><th>Supplier</th><th>Category</th><th>Rating</th><th>Ratings Count</th></tr>
			{bot_rows}
		</table>

		<h3>🚨 Suppliers Below Threshold (&lt; {low_threshold} ★)</h3>
		<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse; width:100%;">
			<tr style="background:#f3f4f6;"><th>Supplier</th><th>Category</th><th>Current Rating</th></tr>
			{warn_rows}
		</table>
	</div>
	"""

	try:
		frappe.sendmail(
			recipients=recipients,
			subject=_("Weekly Vendor Performance Digest — {0}").format(today()),
			message=html,
			now=True,
		)
	except Exception as e:
		frappe.logger("vendor_portal").error(f"Failed to send weekly performance digest: {e}")


def auto_expire_stale_onboardings():
	"""
	Task 3.1 D: Auto-Expire Stale Onboardings (Daily via cron '0 9 * * *').
	Vendor Onboarding records stuck in 'Under Review':
	- If > 7 days (and <= 14 days): Send reminder email to Vendor Managers.
	- If > 14 days: Auto-reject with reason 'Auto-rejected: Review period expired.'
	"""
	frappe.logger("vendor_portal").info("Executing auto_expire_stale_onboardings cron job")
	seven_days_ago = add_days(today(), -7)
	fourteen_days_ago = add_days(today(), -14)

	# 1. Stale > 14 days: Auto-reject
	stale_to_reject = frappe.get_all(
		"Vendor Onboarding",
		filters={
			"onboarding_status": "Under Review",
			"modified": ["<=", fourteen_days_ago],
		},
		fields=["name", "supplier_name", "modified"],
	)

	for record in stale_to_reject:
		doc = frappe.get_doc("Vendor Onboarding", record.name)
		doc.onboarding_status = "Rejected"
		doc.rejection_reason = "Auto-rejected: Review period expired."
		doc.save(ignore_permissions=True)
		frappe.logger("vendor_portal").info(
			f"Auto-rejected stale onboarding {record.name} (>14 days inactive)"
		)

	# 2. Stale between 7 and 14 days: Send reminder email
	stale_to_remind = frappe.get_all(
		"Vendor Onboarding",
		filters={
			"onboarding_status": "Under Review",
			"modified": ["between", [fourteen_days_ago, seven_days_ago]],
		},
		fields=["name", "supplier_name", "creation", "modified", "vendor_category"],
	)

	if stale_to_remind:
		recipients = get_vendor_manager_emails()
		if recipients:
			rows = "".join(
				f"<tr><td><a href='/app/vendor-onboarding/{r.name}'>{r.name}</a></td><td>{r.supplier_name}</td><td>{r.vendor_category or '-'}</td><td>{r.modified}</td></tr>"
				for r in stale_to_remind
			)
			message = f"""
			<h3>Reminder: Pending Vendor Onboardings Requiring Review</h3>
			<p>The following vendor onboarding applications have been awaiting review for more than 7 days:</p>
			<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse; width:100%;">
				<tr style="background:#f3f4f6;"><th>ID</th><th>Supplier</th><th>Category</th><th>Last Modified</th></tr>
				{rows}
			</table>
			<p><b>Note:</b> Applications pending review for over 14 days will be automatically rejected.</p>
			"""
			try:
				frappe.sendmail(
					recipients=recipients,
					subject=_("ACTION REQUIRED: Stale Vendor Onboardings Awaiting Review (>7 Days)"),
					message=message,
					now=True,
				)
			except Exception as e:
				frappe.logger("vendor_portal").error(f"Failed to send stale onboarding reminder: {e}")

	return {"rejected": len(stale_to_reject), "reminded": len(stale_to_remind)}
