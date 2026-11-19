# Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from vendor_portal.api import (
	get_vendor_dashboard,
	submit_vendor_rating,
	get_supplier_comparison,
	get_onboarding_status_summary,
	get_vendor_rating_history,
)
from vendor_portal.permissions import (
	has_rating_log_permission,
	get_onboarding_permission_conditions,
)
from vendor_portal.utils import star_rating, recalculate_vendor_rating


class TestDay2(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.supplier_name = "Test Day2 Supplier"
		if not frappe.db.exists("Supplier", cls.supplier_name):
			sup = frappe.get_doc({
				"doctype": "Supplier",
				"supplier_name": cls.supplier_name,
				"supplier_group": "Local",
			}).insert(ignore_permissions=True)
			cls.supplier = sup.name
		else:
			cls.supplier = cls.supplier_name

		# Create Vendor Category if missing
		if not frappe.db.exists("Vendor Category", "Test Day2 Category"):
			cat = frappe.get_doc({
				"doctype": "Vendor Category",
				"category_name": "Test Day2 Category",
				"minimum_rating_threshold": 3.0,
			}).insert(ignore_permissions=True)

		# Ensure Vendor Portal Settings exist with default weights
		settings = frappe.get_single("Vendor Portal Settings")
		settings.weight_delivery = 40.0
		settings.weight_quality = 30.0
		settings.weight_pricing = 20.0
		settings.weight_communication = 10.0
		settings.low_rating_threshold = 2.5
		settings.save(ignore_permissions=True)

	def test_star_rating_filter(self):
		"""Test Jinja star_rating filter formatting"""
		self.assertEqual(star_rating(5), "★★★★★")
		self.assertEqual(star_rating(3), "★★★☆☆")
		self.assertEqual(star_rating(1), "★☆☆☆☆")
		self.assertEqual(star_rating(0), "☆☆☆☆☆")
		# Test normalized 0.6 * 5 = 3
		self.assertEqual(star_rating(0.6), "★★★☆☆")

	def test_submit_vendor_rating_api(self):
		"""Test submit_vendor_rating whitelisted API and calculation"""
		res = submit_vendor_rating(
			supplier=self.supplier,
			rating_type="Quality",
			score=4.0,
			remarks="Excellent quality delivery",
		)
		self.assertEqual(res.get("status"), "success")
		self.assertEqual(res.get("supplier"), self.supplier)
		self.assertGreaterEqual(float(res.get("vendor_rating", 0)), 1.0)
		self.assertGreaterEqual(int(res.get("total_rating_count", 0)), 1)

		# Verify log created
		log_name = res.get("rating_log")
		self.assertTrue(frappe.db.exists("Vendor Rating Log", log_name))
		log_doc = frappe.get_doc("Vendor Rating Log", log_name)
		self.assertEqual(log_doc.rating_type, "Quality")
		self.assertEqual(log_doc.score, 4.0)

	def test_get_vendor_dashboard_api(self):
		"""Test get_vendor_dashboard whitelisted API"""
		dashboard = get_vendor_dashboard(self.supplier)
		self.assertEqual(dashboard.get("supplier"), self.supplier)
		self.assertIn("total_pos", dashboard)
		self.assertIn("total_po_value", dashboard)
		self.assertIn("total_receipts", dashboard)
		self.assertIn("pending_receipts", dashboard)
		self.assertIn("avg_rating", dashboard)
		self.assertIn("rating_breakdown", dashboard)
		self.assertIn("recent_ratings", dashboard)
		self.assertIn("total_invoiced", dashboard)
		self.assertIn("outstanding_amount", dashboard)

		# Check breakdown includes all 4 dimensions
		breakdown = dashboard["rating_breakdown"]
		for dim in ["Delivery", "Quality", "Pricing", "Communication"]:
			self.assertIn(dim, breakdown)

	def test_get_onboarding_status_summary_api(self):
		"""Test get_onboarding_status_summary whitelisted API"""
		summary = get_onboarding_status_summary()
		self.assertIn("total_pending", summary)
		self.assertIn("total_approved", summary)
		self.assertIn("total_rejected", summary)
		self.assertIn("total_all", summary)
		self.assertIn("recent_submissions", summary)

	def test_get_vendor_rating_history_api(self):
		"""Test get_vendor_rating_history whitelisted API"""
		history = get_vendor_rating_history(self.supplier)
		self.assertIsInstance(history, list)
		if history:
			self.assertIn("rating_type", history[0])
			self.assertIn("score", history[0])

	def test_get_supplier_comparison_api(self):
		"""Test get_supplier_comparison whitelisted API"""
		# Test with non-existent or empty item
		comparison = get_supplier_comparison("NON-EXISTENT-ITEM-12345", qty=5)
		self.assertIsInstance(comparison, list)
		self.assertEqual(len(comparison), 0)

	def test_print_format_rendering(self):
		"""Test rendering of Vendor Purchase Order print format with Jinja filter"""
		if frappe.db.exists("Print Format", "Vendor Purchase Order"):
			pf = frappe.get_doc("Print Format", "Vendor Purchase Order")
			self.assertTrue(pf.html)
			# Create a test PO document to simulate rendering
			test_po = frappe.new_doc("Purchase Order")
			test_po.name = "PO-TEST-0001"
			test_po.supplier = self.supplier
			test_po.supplier_name = self.supplier_name
			test_po.company = "Test Company"
			test_po.transaction_date = frappe.utils.today()
			test_po.schedule_date = frappe.utils.today()
			test_po.currency = "INR"
			test_po.grand_total = 5000.0
			test_po.append(
				"items",
				{
					"item_code": "ITEM-01",
					"item_name": "Test Item 1",
					"qty": 10,
					"uom": "Nos",
					"rate": 500.0,
					"amount": 5000.0,
				},
			)
			rendered = frappe.render_template(pf.html, {"doc": test_po, "_": frappe._})
			self.assertIn("PURCHASE ORDER", rendered)
			self.assertIn("Vendor Details", rendered)
			self.assertIn(self.supplier_name, rendered)

	def test_role_based_permission_hooks(self):
		"""Test Task 2.4 permission hooks for Rating Log and Onboarding"""
		# 1. Rating Log has_permission
		fake_log = frappe._dict({
			"doctype": "Vendor Rating Log",
			"name": "TEST-LOG-001",
			"rated_by": "purchase_user@test.com",
			"owner": "purchase_user@test.com",
		})

		# Vendor Manager can edit any log
		self.assertTrue(
			has_rating_log_permission(fake_log, ptype="write", user="vendor_mgr@test.com")
		)
		# Purchase Team user can edit own log
		self.assertTrue(
			has_rating_log_permission(fake_log, ptype="write", user="purchase_user@test.com")
		)
		# Other user cannot edit
		self.assertFalse(
			has_rating_log_permission(fake_log, ptype="write", user="other_user@test.com")
		)

		# 2. Onboarding permission_query_conditions
		vm_cond = get_onboarding_permission_conditions(user="vendor_mgr@test.com")
		self.assertEqual(vm_cond, "")  # Vendor Manager sees all

		pu_cond = get_onboarding_permission_conditions(user="purchase_user@test.com")
		self.assertIn("`tabVendor Onboarding`.owner = 'purchase_user@test.com'", pu_cond)
