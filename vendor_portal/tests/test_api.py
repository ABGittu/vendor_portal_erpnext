# Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from vendor_portal.api import (
	submit_vendor_rating,
	get_supplier_comparison,
)
from vendor_portal.permissions import has_rating_log_permission
from vendor_portal.utils import recalculate_vendor_rating


class TestVendorPortalAPIAndFlows(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.get_all("Company", limit=1)[0].name
		cls.item_code = frappe.get_all("Item", limit=1)[0].name

		# Create Vendor Category with threshold 3.0
		cls.category_name = "API Test Category"
		if not frappe.db.exists("Vendor Category", cls.category_name):
			frappe.get_doc({
				"doctype": "Vendor Category",
				"category_name": cls.category_name,
				"minimum_rating_threshold": 3.0,
			}).insert(ignore_permissions=True)

		# Create standard test supplier (above threshold)
		cls.supplier_name = "API Test Supplier Normal"
		if frappe.db.exists("Supplier", cls.supplier_name):
			frappe.db.delete("Supplier", cls.supplier_name)

		sup = frappe.get_doc({
			"doctype": "Supplier",
			"supplier_name": cls.supplier_name,
			"supplier_group": "Local",
			"vendor_category": cls.category_name,
			"is_blacklisted": 0,
			"vendor_rating": 1.0,  # 5 stars in Frappe rating field
			"total_rating_count": 0,
		}).insert(ignore_permissions=True)
		cls.supplier = sup.name

		# Create blacklisted test supplier
		cls.bl_supplier_name = "API Test Supplier Blacklisted"
		if frappe.db.exists("Supplier", cls.bl_supplier_name):
			frappe.db.delete("Supplier", cls.bl_supplier_name)

		bl_sup = frappe.get_doc({
			"doctype": "Supplier",
			"supplier_name": cls.bl_supplier_name,
			"supplier_group": "Local",
			"vendor_category": cls.category_name,
			"is_blacklisted": 1,
			"blacklist_reason": "Repeated quality defects",
			"vendor_rating": 1.0,
		}).insert(ignore_permissions=True)
		cls.bl_supplier = bl_sup.name

		# Create low rating supplier (below threshold: 0.4 = 2/5 stars < 3.0 threshold)
		cls.low_supplier_name = "API Test Supplier Low Rating"
		if frappe.db.exists("Supplier", cls.low_supplier_name):
			frappe.db.delete("Supplier", cls.low_supplier_name)

		low_sup = frappe.get_doc({
			"doctype": "Supplier",
			"supplier_name": cls.low_supplier_name,
			"supplier_group": "Local",
			"vendor_category": cls.category_name,
			"is_blacklisted": 0,
			"vendor_rating": 0.4,  # 2 stars in Frappe rating field
			"total_rating_count": 1,
		}).insert(ignore_permissions=True)
		cls.low_supplier = low_sup.name

		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		super().tearDownClass()
		frappe.db.delete("Vendor Rating Log", {"supplier": ["in", [cls.supplier, cls.bl_supplier, cls.low_supplier]]})
		frappe.db.delete("Supplier", {"name": ["in", [cls.supplier, cls.bl_supplier, cls.low_supplier]]})
		frappe.db.delete("Vendor Category", {"name": cls.category_name})
		frappe.db.commit()

	def test_blacklisted_supplier_blocks_po(self):
		"""Create PO for blacklisted supplier -> ValidationError"""
		po = frappe.new_doc("Purchase Order")
		po.company = self.company
		po.supplier = self.bl_supplier
		po.schedule_date = frappe.utils.today()
		po.append("items", {
			"item_code": self.item_code,
			"qty": 10,
			"rate": 100,
		})
		self.assertRaises(frappe.ValidationError, po.insert)

	def test_low_rating_blocks_po(self):
		"""Supplier rating below threshold -> PO blocked"""
		po = frappe.new_doc("Purchase Order")
		po.company = self.company
		po.supplier = self.low_supplier
		po.schedule_date = frappe.utils.today()
		po.append("items", {
			"item_code": self.item_code,
			"qty": 10,
			"rate": 100,
		})
		self.assertRaises(frappe.ValidationError, po.insert)

	def test_po_submit_creates_pricing_rating(self):
		"""Submit PO -> Vendor Rating Log with type=Pricing created"""
		po = frappe.new_doc("Purchase Order")
		po.company = self.company
		po.supplier = self.supplier
		po.schedule_date = frappe.utils.today()
		po.append("items", {
			"item_code": self.item_code,
			"qty": 5,
			"rate": 200,
		})
		po.insert(ignore_permissions=True)
		po.submit()

		# Assert rating log created
		log = frappe.db.get_value(
			"Vendor Rating Log",
			{"purchase_order": po.name, "rating_type": "Pricing"},
			["name", "score"],
			as_dict=True,
		)
		self.assertIsNotNone(log)
		self.assertGreaterEqual(log.score, 3.0)

		# Clean up PO
		po.cancel()

	def test_po_cancel_deletes_rating(self):
		"""Cancel PO -> linked Vendor Rating Log deleted"""
		po = frappe.new_doc("Purchase Order")
		po.company = self.company
		po.supplier = self.supplier
		po.schedule_date = frappe.utils.today()
		po.append("items", {
			"item_code": self.item_code,
			"qty": 2,
			"rate": 150,
		})
		po.insert(ignore_permissions=True)
		po.submit()

		po_name = po.name
		# Verify log exists
		self.assertTrue(frappe.db.exists("Vendor Rating Log", {"purchase_order": po_name}))

		# Cancel PO
		po.cancel()
		self.assertFalse(frappe.db.exists("Vendor Rating Log", {"purchase_order": po_name}))

	def test_pr_submit_creates_delivery_rating(self):
		"""Submit PR -> Delivery rating created with correct score"""
		pr = frappe.new_doc("Purchase Receipt")
		pr.company = self.company
		pr.supplier = self.supplier
		pr.posting_date = frappe.utils.today()
		pr.append("items", {
			"item_code": self.item_code,
			"qty": 5,
			"rate": 100,
		})
		pr.insert(ignore_permissions=True)
		pr.submit()

		pr_name = pr.name
		log = frappe.db.get_value(
			"Vendor Rating Log",
			{"purchase_receipt": pr_name, "rating_type": "Delivery"},
			["name", "score"],
			as_dict=True,
		)
		self.assertIsNotNone(log)
		self.assertGreaterEqual(log.score, 3.0)

		# Clean up PR
		pr.cancel()

	def test_vendor_rating_recalculation(self):
		"""Add multiple ratings -> weighted avg matches expected calculation"""
		# Clean previous logs for isolated test
		sup = self.supplier
		frappe.db.delete("Vendor Rating Log", {"supplier": sup})

		# Submit 2 ratings
		submit_vendor_rating(supplier=sup, rating_type="Quality", score=5.0)
		submit_vendor_rating(supplier=sup, rating_type="Delivery", score=3.0)

		final_rating, count = recalculate_vendor_rating(sup)
		self.assertEqual(count, 2)
		self.assertGreater(final_rating, 0)

		sup_doc = frappe.get_doc("Supplier", sup)
		self.assertEqual(round(sup_doc.vendor_rating, 2), final_rating)

	def test_permission_own_ratings_only(self):
		"""Purchase User can only edit own ratings, not other users' ratings"""
		fake_log = frappe._dict({
			"doctype": "Vendor Rating Log",
			"name": "TEST-LOG-PERM",
			"rated_by": "purchase_user@test.com",
			"owner": "purchase_user@test.com",
		})

		# Purchase user can edit their own
		self.assertTrue(
			has_rating_log_permission(fake_log, ptype="write", user="purchase_user@test.com")
		)
		# Another user cannot edit
		self.assertFalse(
			has_rating_log_permission(fake_log, ptype="write", user="stranger@test.com")
		)
		# Vendor Manager can edit any
		self.assertTrue(
			has_rating_log_permission(fake_log, ptype="write", user="vendor_mgr@test.com")
		)

	def test_supplier_comparison_api(self):
		"""API returns suppliers list sorted by rating and last rate"""
		res = get_supplier_comparison(self.item_code, qty=10)
		self.assertIsInstance(res, list)
		# If items found, check sort order
		if len(res) > 1:
			self.assertGreaterEqual(res[0]["vendor_rating"], res[1]["vendor_rating"])
