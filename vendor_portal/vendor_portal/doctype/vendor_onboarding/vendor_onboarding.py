# Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
# For license information, please see license.txt

import re
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, validate_email_address


class VendorOnboarding(Document):
	def validate(self):
		"""Validate onboarding inputs before save/submit."""
		self.validate_email()
		self.validate_gst_and_pan()
		self.validate_minimum_documents()
		self.validate_duplicate_gst()
		self.validate_remarks_and_status()

	def validate_remarks_and_status(self):
		"""Ensure mandatory remarks for Reject and Rework, optional for Approve."""
		if self.onboarding_status == "Rejected" and not (self.rejection_reason or "").strip():
			frappe.throw(_("Rejection reason or remarks are mandatory when rejecting an application."))

		if self.onboarding_status == "Rework" and not (self.rework_notes or "").strip():
			frappe.throw(_("Rework notes or remarks are mandatory when requesting rework."))

	def validate_email(self):
		"""Validate supplier email format."""
		if self.email:
			validate_email_address(self.email, throw=True)

	def validate_gst_and_pan(self):
		"""
		Validate GST number format (15 characters: 2-digit state code + 10-char PAN + 1 entity code + 1 Z + 1 check digit)
		and PAN format (5 letters + 4 digits + 1 letter).
		"""
		settings = frappe.get_single("Vendor Portal Settings")

		# Check if GST is required by settings
		if getattr(settings, "require_gst_verification", 0) and not self.gst_number:
			frappe.throw(_("GST Number is mandatory as per Vendor Portal Settings."))

		if self.gst_number:
			self.gst_number = self.gst_number.strip().upper()
			gst_regex = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
			if not re.match(gst_regex, self.gst_number):
				frappe.throw(
					_("Invalid GST Number format: {0}. Must be 15 characters (e.g., 22AAAAA0000A1Z5).").format(
						self.gst_number
					)
				)

			# Auto-extract PAN from GST if PAN is not filled
			pan_from_gst = self.gst_number[2:12]
			if not self.pan_number:
				self.pan_number = pan_from_gst

		if self.pan_number:
			self.pan_number = self.pan_number.strip().upper()
			pan_regex = r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$"
			if not re.match(pan_regex, self.pan_number):
				frappe.throw(
					_("Invalid PAN Number format: {0}. Must be 5 letters, 4 digits, and 1 letter (e.g., ABCDE1234F).").format(
						self.pan_number
					)
				)

			if self.gst_number and len(self.gst_number) >= 12 and self.gst_number[2:12] != self.pan_number:
				frappe.throw(
					_("PAN number ({0}) does not match the PAN in GST number ({1}).").format(
						self.pan_number, self.gst_number[2:12]
					)
				)

	def validate_minimum_documents(self):
		"""Ensure the minimum number of documents required by settings are attached."""
		settings = frappe.get_single("Vendor Portal Settings")
		min_docs = getattr(settings, "min_documents_required", 2) or 2
		doc_count = len(self.documents or [])
		if doc_count < min_docs:
			frappe.throw(
				_("At least {0} verification documents are required. Currently {1} attached.").format(
					min_docs, doc_count
				)
			)

	def validate_duplicate_gst(self):
		"""Ensure no other approved onboarding or active ERPNext Supplier has the same GST number."""
		if not self.gst_number:
			return

		# Check existing approved onboarding
		existing_onboarding = frappe.db.get_value(
			"Vendor Onboarding",
			{"gst_number": self.gst_number, "onboarding_status": "Approved", "name": ["!=", self.name]},
			"name",
		)
		if existing_onboarding:
			frappe.throw(
				_("An approved onboarding record ({0}) already exists with GST Number {1}.").format(
					existing_onboarding, self.gst_number
				)
			)

		# Check existing active Supplier
		existing_supplier = frappe.db.get_value(
			"Supplier",
			{"tax_id": self.gst_number, "disabled": 0},
			"name",
		)
		if existing_supplier:
			frappe.throw(
				_("An active Supplier ({0}) already exists with GST / Tax ID {1}.").format(
					existing_supplier, self.gst_number
				)
			)

	def on_submit(self):
		"""When submitted, transition to Under Review status."""
		if self.onboarding_status == "Draft":
			self.db_set("onboarding_status", "Under Review")

	def on_update(self):
		"""Handle state changes triggered via Workflow transitions."""
		if self.onboarding_status == "Approved" and not self.linked_supplier:
			supplier = self.create_linked_supplier()
			self.db_set("linked_supplier", supplier.name)
			self.db_set("reviewed_by", frappe.session.user)
			self.db_set("review_date", now_datetime())

	def create_linked_supplier(self):
		"""
		Create an ERPNext Supplier record with mapped fields, Address, Contact, and Bank details.
		"""
		settings = frappe.get_single("Vendor Portal Settings")
		default_group = getattr(settings, "default_supplier_group", None) or "Raw Material"

		supplier_name = self.company_name or self.supplier_name

		# Create Supplier
		supplier = frappe.new_doc("Supplier")
		supplier.supplier_name = supplier_name
		supplier.supplier_group = default_group
		supplier.vendor_category = self.vendor_category
		supplier.tax_id = self.gst_number
		supplier.pan = self.pan_number
		supplier.onboarding_reference = self.name
		supplier.is_blacklisted = 0
		supplier.total_rating_count = 0
		supplier.vendor_rating = 0
		supplier.insert(ignore_permissions=True)

		# Create Address if provided
		if self.address_line_1:
			try:
				address = frappe.new_doc("Address")
				address.address_title = supplier.name
				address.address_type = "Billing"
				address.address_line1 = self.address_line_1
				address.city = self.city
				address.state = self.state
				address.pincode = self.pincode
				address.country = "India"
				address.email_id = self.email
				address.phone = self.phone
				address.append("links", {
					"link_doctype": "Supplier",
					"link_name": supplier.name,
				})
				address.insert(ignore_permissions=True)
			except Exception as e:
				frappe.log_error(title="Failed to create Address for Supplier", message=str(e))

		# Create Contact
		if self.email or self.phone or self.contact_person:
			try:
				contact = frappe.new_doc("Contact")
				contact.first_name = self.contact_person or self.supplier_name
				contact.email_id = self.email
				contact.phone = self.phone
				contact.mobile_no = self.phone
				contact.is_primary_contact = 1
				contact.append("links", {
					"link_doctype": "Supplier",
					"link_name": supplier.name,
				})
				contact.insert(ignore_permissions=True)
			except Exception as e:
				frappe.log_error(title="Failed to create Contact for Supplier", message=str(e))

		# Create Bank details if provided
		if self.bank_name and self.bank_account_number:
			try:
				if not frappe.db.exists("Bank", self.bank_name):
					bank_doc = frappe.new_doc("Bank")
					bank_doc.bank_name = self.bank_name
					bank_doc.insert(ignore_permissions=True)

				bank_acc = frappe.new_doc("Bank Account")
				bank_acc.account_name = f"{supplier.name} - {self.bank_name}"
				bank_acc.bank = self.bank_name
				bank_acc.party_type = "Supplier"
				bank_acc.party = supplier.name
				bank_acc.bank_account_no = self.bank_account_number
				bank_acc.branch_code = self.ifsc_code
				bank_acc.is_default = 1
				bank_acc.insert(ignore_permissions=True)
			except Exception as e:
				frappe.log_error(title="Failed to create Bank Account for Supplier", message=str(e))

		return supplier


@frappe.whitelist()
def approve_onboarding(onboarding_name, remarks=None):
	"""
	Whitelisted API to approve a Vendor Onboarding record:
	- Validates user role (Purchase Manager, Vendor Manager, or System Manager)
	- Sets onboarding_status = 'Approved', reviewed_by, review_date
	- Remarks are optional
	- Auto-creates ERPNext Supplier with mapped fields
	- Links Supplier back to onboarding record
	- Sends email notification to vendor
	"""
	user_roles = frappe.get_roles(frappe.session.user)
	allowed_roles = ["Purchase Manager", "Vendor Manager", "System Manager"]
	if not any(r in user_roles for r in allowed_roles):
		frappe.throw(
			_("Permission Denied: Only users with 'Purchase Manager' or 'Vendor Manager' role can approve onboarding."),
			frappe.PermissionError,
		)

	doc = frappe.get_doc("Vendor Onboarding", onboarding_name)

	if doc.onboarding_status == "Approved":
		return {
			"status": "already_approved",
			"message": _("Onboarding {0} is already approved.").format(onboarding_name),
			"supplier": doc.linked_supplier,
		}

	# Create linked Supplier if not already created
	supplier_name = doc.linked_supplier
	if not supplier_name:
		supplier = doc.create_linked_supplier()
		supplier_name = supplier.name

	doc.db_set("linked_supplier", supplier_name)
	doc.db_set("onboarding_status", "Approved")
	doc.db_set("reviewed_by", frappe.session.user)
	doc.db_set("review_date", now_datetime())
	if remarks:
		doc.db_set("approval_notes", remarks.strip())

	# Send email notification to vendor
	try:
		frappe.sendmail(
			recipients=[doc.email],
			subject=_("Vendor Onboarding Approved - {0}").format(doc.company_name or doc.supplier_name),
			message=_(
				"""<p>Dear {0},</p>
<p>Congratulations! Your vendor onboarding application (<b>{1}</b>) has been reviewed and <b>Approved</b>.</p>
<p>You have been registered in our system as Supplier: <b>{2}</b> under category <b>{3}</b>.</p>
{4}
<p>Thank you for partnering with us.</p>"""
			).format(
				doc.contact_person or doc.supplier_name,
				doc.name,
				supplier_name,
				doc.vendor_category,
				f"<p><b>Notes:</b> {remarks}</p>" if remarks else "",
			),
			now=True,
		)
	except Exception as e:
		frappe.log_error(title="Vendor Approval Email Error", message=str(e))

	return {
		"status": "success",
		"message": _("Onboarding approved and Supplier {0} created.").format(supplier_name),
		"supplier": supplier_name,
	}


@frappe.whitelist()
def reject_onboarding(onboarding_name, reason=None, remarks=None):
	"""
	Whitelisted API to reject a Vendor Onboarding record:
	- Validates user role (Purchase Manager, Vendor Manager, or System Manager)
	- Rejection reason / remarks are MANDATORY
	- Sets onboarding_status = 'Rejected', rejection_reason, reviewed_by, review_date
	- Sends email notification to vendor with reason
	"""
	user_roles = frappe.get_roles(frappe.session.user)
	allowed_roles = ["Purchase Manager", "Vendor Manager", "System Manager"]
	if not any(r in user_roles for r in allowed_roles):
		frappe.throw(
			_("Permission Denied: Only users with 'Purchase Manager' or 'Vendor Manager' role can reject onboarding."),
			frappe.PermissionError,
		)

	reason_text = (reason or remarks or "").strip()
	if not reason_text:
		frappe.throw(_("Rejection reason or remarks are mandatory when rejecting an application."))

	doc = frappe.get_doc("Vendor Onboarding", onboarding_name)

	doc.db_set("onboarding_status", "Rejected")
	doc.db_set("rejection_reason", reason_text)
	doc.db_set("reviewed_by", frappe.session.user)
	doc.db_set("review_date", now_datetime())

	# Send email notification to vendor
	try:
		frappe.sendmail(
			recipients=[doc.email],
			subject=_("Vendor Onboarding Update - {0}").format(doc.company_name or doc.supplier_name),
			message=_(
				"""<p>Dear {0},</p>
<p>Your vendor onboarding application (<b>{1}</b>) has been reviewed and <b>Rejected</b>.</p>
<p><b>Reason:</b> {2}</p>
<p>Please review and submit an updated application if applicable.</p>"""
			).format(
				doc.contact_person or doc.supplier_name,
				doc.name,
				reason_text,
			),
			now=True,
		)
	except Exception as e:
		frappe.log_error(title="Vendor Rejection Email Error", message=str(e))

	return {
		"status": "success",
		"message": _("Onboarding {0} has been rejected.").format(onboarding_name),
	}


@frappe.whitelist()
def rework_onboarding(onboarding_name, rework_notes=None, remarks=None):
	"""
	Whitelisted API to request rework / corrections on a Vendor Onboarding record:
	- Validates user role (Purchase Manager, Vendor Manager, or System Manager)
	- Rework notes / remarks are MANDATORY
	- Sets onboarding_status = 'Rework', rework_notes, reviewed_by, review_date
	- Sends email notification to vendor detailing required corrections
	"""
	user_roles = frappe.get_roles(frappe.session.user)
	allowed_roles = ["Purchase Manager", "Vendor Manager", "System Manager"]
	if not any(r in user_roles for r in allowed_roles):
		frappe.throw(
			_("Permission Denied: Only users with 'Purchase Manager' or 'Vendor Manager' role can request rework."),
			frappe.PermissionError,
		)

	notes_text = (rework_notes or remarks or "").strip()
	if not notes_text:
		frappe.throw(_("Rework / correction notes are mandatory when requesting rework."))

	doc = frappe.get_doc("Vendor Onboarding", onboarding_name)

	doc.db_set("onboarding_status", "Rework")
	doc.db_set("rework_notes", notes_text)
	doc.db_set("reviewed_by", frappe.session.user)
	doc.db_set("review_date", now_datetime())

	# Send email notification to vendor
	try:
		frappe.sendmail(
			recipients=[doc.email],
			subject=_("Action Required: Corrections Requested on Onboarding Application ({0})").format(doc.name),
			message=_(
				"""<p>Dear {0},</p>
<p>Your vendor onboarding application (<b>{1}</b>) has been reviewed and requires corrections before approval.</p>
<p><b>Required Corrections:</b></p>
<blockquote style="background: #f8f9fa; border-left: 4px solid #ffc107; padding: 10px 15px; margin: 10px 0;">{2}</blockquote>
<p>Please update your details and resubmit for verification.</p>"""
			).format(
				doc.contact_person or doc.supplier_name,
				doc.name,
				notes_text,
			),
			now=True,
		)
	except Exception as e:
		frappe.log_error(title="Vendor Rework Email Error", message=str(e))

	return {
		"status": "success",
		"message": _("Rework requested for Onboarding {0}.").format(onboarding_name),
	}


@frappe.whitelist()
def resubmit_onboarding(onboarding_name):
	"""
	Whitelisted API to resubmit an onboarding record after rework corrections:
	- Sets onboarding_status = 'Under Review'
	"""
	doc = frappe.get_doc("Vendor Onboarding", onboarding_name)
	doc.db_set("onboarding_status", "Under Review")
	return {
		"status": "success",
		"message": _("Onboarding {0} resubmitted for review.").format(onboarding_name),
	}
