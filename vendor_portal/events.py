# Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def on_vendor_onboarding_after_insert(doc, method=None):
	"""
	doc_events hook on Vendor Onboarding: after_insert
	Sends a welcome confirmation email to the prospective vendor applicant.
	"""
	if not doc.email:
		return

	subject = _("Welcome to Vendor Portal — Application Received ({0})").format(doc.name)
	message = f"""
	<h3>Welcome, {doc.supplier_name or doc.company_name}!</h3>
	<p>Thank you for submitting your onboarding application (Reference: <b>{doc.name}</b>).</p>
	<p>Our Procurement and Vendor Management team will verify your submitted documents and credentials.</p>
	<p>Current Status: <b>{doc.onboarding_status}</b></p>
	<br>
	<p>Best regards,<br>Vendor Management Team</p>
	"""

	try:
		frappe.sendmail(
			recipients=[doc.email],
			subject=subject,
			message=message,
			now=False,
		)
		frappe.logger("vendor_portal").info(
			f"Queued welcome email for new onboarding application {doc.name}"
		)
	except Exception as e:
		frappe.logger("vendor_portal").error(
			f"Failed to queue welcome email for onboarding {doc.name}: {e}"
		)


def on_supplier_update(doc, method=None):
	"""
	doc_events hook on Supplier: on_update
	Tracks changes to Supplier blacklist status and alerts the vendor management team.
	"""
	if not doc.has_value_changed("is_blacklisted"):
		return

	if doc.is_blacklisted:
		reason = doc.blacklist_reason or _("No reason specified")
		frappe.logger("vendor_portal").warning(
			f"Supplier {doc.name} was blacklisted. Reason: {reason}"
		)

		# Fetch all Vendor Managers
		vendor_managers = frappe.db.sql_list(
			"""
			SELECT DISTINCT parent
			FROM `tabHas Role` hr
			JOIN `tabUser` u ON u.name = hr.parent
			WHERE hr.role IN ('Vendor Manager', 'Purchase Manager')
			  AND u.enabled = 1
			  AND u.name NOT IN ('Administrator', 'Guest')
			"""
		)

		if vendor_managers:
			subject = _("SECURITY ALERT: Supplier {0} Has Been Blacklisted").format(
				doc.supplier_name or doc.name
			)
			message = f"""
			<h3>Supplier Blacklisted Notice</h3>
			<p>Supplier <b>{doc.supplier_name}</b> ({doc.name}) has been blacklisted.</p>
			<p><b>Reason:</b> {reason}</p>
			<p>All future Purchase Order creations for this vendor will be blocked by system validations.</p>
			"""
			try:
				frappe.sendmail(
					recipients=vendor_managers,
					subject=subject,
					message=message,
					now=True,
				)
			except Exception as e:
				frappe.logger("vendor_portal").error(f"Failed to send blacklist alert: {e}")
	else:
		frappe.logger("vendor_portal").info(
			f"Supplier {doc.name} was removed from the blacklist."
		)

	# Bonus Task 2: Keep ERPNext Supplier Scorecard in sync with blacklist state
	try:
		from vendor_portal.scorecard import sync_supplier_scorecard
		sync_supplier_scorecard(doc.name)
	except Exception as e:
		frappe.logger("vendor_portal").warning(
			f"Failed to sync supplier scorecard on supplier update for {doc.name}: {e}"
		)
