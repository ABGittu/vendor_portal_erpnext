# Copyright (c) 2026, Abhijit Prakashkumar Dodiya and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from vendor_portal.vendor_portal.doctype.vendor_onboarding.vendor_onboarding import (
	approve_onboarding,
	reject_onboarding,
)


class TestVendorOnboarding(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Ensure Vendor Portal Settings exists
		settings = frappe.get_single("Vendor Portal Settings")
		settings.require_gst_verification = 1
		settings.min_documents_required = 2
		settings.default_supplier_group = "Local"
		settings.save(ignore_permissions=True)

		# Ensure a Category exists
		if not frappe.db.exists("Vendor Category", "Industrial Goods"):
			frappe.get_doc({
				"doctype": "Vendor Category",
				"category_name": "Industrial Goods",
				"minimum_rating_threshold": 3.0,
			}).insert(ignore_permissions=True)

	def test_gst_validation_format(self):
		"""Submit with invalid GST -> ValidationError"""
		doc = frappe.get_doc({
			"doctype": "Vendor Onboarding",
			"supplier_name": "Test Invalid GST",
			"company_name": "Test Invalid GST Ltd",
			"email": "test_gst@example.com",
			"vendor_category": "Industrial Goods",
			"gst_number": "INVALID_GST_123",
			"pan_number": "ABCDE1234F",
			"documents": [
				{"document_type": "GST Certificate", "document_name": "gst.pdf"},
				{"document_type": "PAN Card", "document_name": "pan.pdf"},
			],
		})
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_pan_validation_format(self):
		"""Submit with invalid PAN -> ValidationError"""
		doc = frappe.get_doc({
			"doctype": "Vendor Onboarding",
			"supplier_name": "Test Invalid PAN",
			"company_name": "Test Invalid PAN Ltd",
			"email": "test_pan@example.com",
			"vendor_category": "Industrial Goods",
			"gst_number": "27ABCDE1234F1Z5",
			"pan_number": "INVALID_PAN",
			"documents": [
				{"document_type": "GST Certificate", "document_name": "gst.pdf"},
				{"document_type": "PAN Card", "document_name": "pan.pdf"},
			],
		})
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_minimum_documents_required(self):
		"""Submit with fewer documents than required by settings -> ValidationError"""
		doc = frappe.get_doc({
			"doctype": "Vendor Onboarding",
			"supplier_name": "Test Min Docs",
			"company_name": "Test Min Docs Ltd",
			"email": "test_docs@example.com",
			"vendor_category": "Industrial Goods",
			"gst_number": "27ABCDE1234F1Z5",
			"pan_number": "ABCDE1234F",
			"documents": [
				{"document_type": "GST Certificate", "document_name": "gst.pdf"}
			],
		})
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_approve_creates_supplier(self):
		"""Approve onboarding -> assert Supplier record created with mapped fields"""
		gst = "27AAACB1234P1Z8"
		# Remove any existing conflict
		frappe.db.delete("Supplier", {"tax_id": gst})
		frappe.db.delete("Vendor Onboarding", {"gst_number": gst})

		doc = frappe.get_doc({
			"doctype": "Vendor Onboarding",
			"supplier_name": "Test Approval Vendor",
			"company_name": "Test Approval Vendor Ltd",
			"email": "approval_test@example.com",
			"phone": "9876543210",
			"address_line_1": "123 Industrial Estate",
			"city": "Mumbai",
			"state": "Maharashtra",
			"pincode": "400001",
			"vendor_category": "Industrial Goods",
			"gst_number": gst,
			"pan_number": "AAACB1234P",
			"onboarding_status": "Draft",
			"documents": [
				{
					"document_type": "GST Certificate",
					"document_name": "gst.pdf",
					"document_file": "/files/gst.pdf",
				},
				{
					"document_type": "PAN Card",
					"document_name": "pan.pdf",
					"document_file": "/files/pan.pdf",
				},
			],
		}).insert(ignore_permissions=True)

		# Submit for Review
		frappe.model.workflow.apply_workflow(doc, "Submit for Review")

		# Approve as Administrator (has System Manager role)
		orig_user = frappe.session.user
		frappe.set_user("Administrator")
		try:
			res = approve_onboarding(doc.name)
			self.assertEqual(res.get("status"), "success")
			supplier_name = res.get("supplier")
			self.assertTrue(frappe.db.exists("Supplier", supplier_name))

			supplier = frappe.get_doc("Supplier", supplier_name)
			self.assertEqual(supplier.vendor_category, "Industrial Goods")
			self.assertEqual(supplier.tax_id, gst)
			self.assertEqual(supplier.onboarding_reference, doc.name)
		finally:
			frappe.set_user(orig_user)

	def test_reject_sets_reason(self):
		"""Reject with reason -> assert status = Rejected and reason saved"""
		doc = frappe.get_doc({
			"doctype": "Vendor Onboarding",
			"supplier_name": "Test Reject Vendor",
			"company_name": "Test Reject Vendor Ltd",
			"email": "reject_test@example.com",
			"phone": "9876543210",
			"address_line_1": "123 Industrial Estate",
			"city": "Mumbai",
			"state": "Maharashtra",
			"pincode": "400001",
			"vendor_category": "Industrial Goods",
			"gst_number": "27XYZAB9999K1Z2",
			"pan_number": "XYZAB9999K",
			"onboarding_status": "Draft",
			"documents": [
				{
					"document_type": "GST Certificate",
					"document_name": "gst.pdf",
					"document_file": "/files/gst.pdf",
				},
				{
					"document_type": "PAN Card",
					"document_name": "pan.pdf",
					"document_file": "/files/pan.pdf",
				},
			],
		}).insert(ignore_permissions=True)

		# Submit for Review
		frappe.model.workflow.apply_workflow(doc, "Submit for Review")

		orig_user = frappe.session.user
		frappe.set_user("Administrator")
		try:
			res = reject_onboarding(doc.name, reason="Incomplete bank statements")
			self.assertEqual(res.get("status"), "success")

			updated = frappe.get_doc("Vendor Onboarding", doc.name)
			self.assertEqual(updated.onboarding_status, "Rejected")
			self.assertEqual(updated.rejection_reason, "Incomplete bank statements")
		finally:
			frappe.set_user(orig_user)

	def test_duplicate_gst_blocked(self):
		"""Submit two onboardings with same approved GST -> second blocked"""
		gst = "27DUPAB1111L1Z9"
		# Clean previous
		frappe.db.delete("Supplier", {"tax_id": gst})
		frappe.db.delete("Vendor Onboarding", {"gst_number": gst})

		first = frappe.get_doc({
			"doctype": "Vendor Onboarding",
			"supplier_name": "Test First GST",
			"company_name": "Test First GST Ltd",
			"email": "first@example.com",
			"phone": "9876543210",
			"address_line_1": "123 Industrial Estate",
			"city": "Mumbai",
			"state": "Maharashtra",
			"pincode": "400001",
			"vendor_category": "Industrial Goods",
			"gst_number": gst,
			"pan_number": "DUPAB1111L",
			"onboarding_status": "Draft",
			"documents": [
				{
					"document_type": "GST Certificate",
					"document_name": "gst.pdf",
					"document_file": "/files/gst.pdf",
				},
				{
					"document_type": "PAN Card",
					"document_name": "pan.pdf",
					"document_file": "/files/pan.pdf",
				},
			],
		}).insert(ignore_permissions=True)

		# Submit and Approve first
		frappe.model.workflow.apply_workflow(first, "Submit for Review")
		orig_user = frappe.session.user
		frappe.set_user("Administrator")
		try:
			approve_onboarding(first.name)
		finally:
			frappe.set_user(orig_user)

		second = frappe.get_doc({
			"doctype": "Vendor Onboarding",
			"supplier_name": "Test Second GST",
			"company_name": "Test Second GST Ltd",
			"email": "second@example.com",
			"phone": "9876543210",
			"address_line_1": "123 Industrial Estate",
			"city": "Mumbai",
			"state": "Maharashtra",
			"pincode": "400001",
			"vendor_category": "Industrial Goods",
			"gst_number": gst,
			"pan_number": "DUPAB1111L",
			"onboarding_status": "Draft",
			"documents": [
				{
					"document_type": "GST Certificate",
					"document_name": "gst.pdf",
					"document_file": "/files/gst.pdf",
				},
				{
					"document_type": "PAN Card",
					"document_name": "pan.pdf",
					"document_file": "/files/pan.pdf",
				},
			],
		})
		self.assertRaises(frappe.ValidationError, second.insert)
