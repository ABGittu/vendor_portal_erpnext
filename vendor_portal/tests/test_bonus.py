# Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from vendor_portal.api import (
	bulk_vendor_import,
	check_vendor_status_web,
	get_supplier_comparison,
	register_vendor_web,
)
from vendor_portal.scorecard import get_supplier_scorecard, sync_supplier_scorecard
from vendor_portal.vendor_portal.page.vendor_dashboard.vendor_dashboard import get_dashboard_data


class TestBonusTasks(FrappeTestCase):
	"""
	Comprehensive automated test suite for Section 4 Bonus Tasks:
	- Bonus Task 1: Vendor Self-Service Portal (register & status check)
	- Bonus Task 2: ERPNext Supplier Scorecard Integration & Standing Sync
	- Bonus Task 3: Vendor Analytics Dashboard Data Provider & 4 Charts
	- Bonus Task 4: Bulk Vendor Import API (synchronous and async enqueue)
	- Bonus Task 5: Vendor Comparison Matrix API with pricing history & scores
	"""

	def setUp(self):
		# Ensure default Vendor Category exists
		if not frappe.db.exists("Vendor Category", "Raw Materials"):
			frappe.get_doc({
				"doctype": "Vendor Category",
				"category_name": "Raw Materials",
				"min_rating_threshold": 3.0,
			}).insert(ignore_permissions=True)

		# Ensure test supplier exists
		if not frappe.db.exists("Supplier", "Bonus Test Supplier"):
			sup = frappe.get_doc({
				"doctype": "Supplier",
				"supplier_name": "Bonus Test Supplier",
				"supplier_group": "Local",
				"vendor_category": "Raw Materials",
				"vendor_rating": 4.5,
			})
			sup.insert(ignore_permissions=True)

	def test_bonus_1_web_vendor_registration(self):
		"""
		Bonus Task 1: Test public registration endpoint creates Vendor Onboarding in Draft.
		"""
		res = register_vendor_web(
			supplier_name="Portal Registered Supplier",
			company_name="Portal Registered Supplier Pvt Ltd",
			contact_person="Portal Contact",
			email="portal_test_unique@example.com",
			phone="9876543210",
			vendor_category="Raw Materials",
			gst_number="27ABCDE1234F1Z5",
			address_line_1="100 Portal Way",
			city="Mumbai",
			state="Maharashtra",
			pincode="400001",
		)

		self.assertEqual(res.get("status"), "success")
		app_id = res.get("application_id")
		self.assertTrue(app_id.startswith("VOB-") or app_id.startswith("VO-"))

		# Verify record
		doc = frappe.get_doc("Vendor Onboarding", app_id)
		self.assertEqual(doc.onboarding_status, "Draft")
		self.assertEqual(doc.pan_number, "ABCDE1234F")

	def test_bonus_1_web_status_check(self):
		"""
		Bonus Task 1: Test status inquiry by application ID and GST.
		"""
		# Register
		res = register_vendor_web(
			supplier_name="Status Track Vendor",
			email="status_track@example.com",
			phone="9876543211",
			gst_number="27XYZAB1234C1Z9",
			address_line_1="200 Status Road",
			city="Pune",
			state="Maharashtra",
			pincode="411001",
		)
		app_id = res.get("application_id")

		# Lookup by app_id
		records = check_vendor_status_web(app_id)
		self.assertTrue(len(records) > 0)
		self.assertEqual(records[0]["name"], app_id)
		self.assertEqual(records[0]["onboarding_status"], "Draft")

		# Lookup by GST
		records_gst = check_vendor_status_web("27XYZAB1234C1Z9")
		self.assertTrue(len(records_gst) > 0)
		self.assertEqual(records_gst[0]["name"], app_id)

	def test_bonus_2_scorecard_sync(self):
		"""
		Bonus Task 2: Test integration between vendor ratings and ERPNext Supplier Scorecard.
		"""
		supplier = "Bonus Test Supplier"
		# Set high rating -> Excellent
		res = sync_supplier_scorecard(supplier, vendor_rating=4.5)
		self.assertEqual(res["status"], "Excellent")
		self.assertEqual(res["prevent_pos"], 0)
		self.assertEqual(res["warn_pos"], 0)

		# Check ERPNext doc
		sc = get_supplier_scorecard(supplier)
		self.assertEqual(sc["status"], "Excellent")

		# Set low rating -> Poor / Very Poor
		res_low = sync_supplier_scorecard(supplier, vendor_rating=1.2)
		self.assertIn(res_low["status"], ["Poor", "Very Poor"])
		self.assertEqual(res_low["warn_pos"], 1)

		# Blacklist supplier -> Very Poor with prevent_pos = 1
		frappe.db.set_value("Supplier", supplier, "is_blacklisted", 1)
		res_bl = sync_supplier_scorecard(supplier)
		self.assertEqual(res_bl["status"], "Very Poor")
		self.assertEqual(res_bl["prevent_pos"], 1)

		# Reset blacklist
		frappe.db.set_value("Supplier", supplier, "is_blacklisted", 0)

	def test_bonus_3_dashboard_page_data(self):
		"""
		Bonus Task 3: Test that get_dashboard_data returns valid datasets for 4 charts and KPIs.
		"""
		data = get_dashboard_data()
		self.assertIn("kpis", data)
		self.assertIn("rating_distribution", data)
		self.assertIn("onboarding_pipeline", data)
		self.assertIn("po_volume_by_category", data)
		self.assertIn("delivery_trend", data)

		# Verify Chart 1: 5 rating brackets
		self.assertEqual(len(data["rating_distribution"]["labels"]), 5)
		self.assertEqual(len(data["rating_distribution"]["datasets"][0]["values"]), 5)

		# Verify Chart 2: 4 pipeline stages
		self.assertEqual(len(data["onboarding_pipeline"]["labels"]), 4)

		# Verify Chart 4: 6 monthly intervals
		self.assertEqual(len(data["delivery_trend"]["labels"]), 6)

	def test_bonus_4_bulk_vendor_import_sync(self):
		"""
		Bonus Task 4: Test synchronous CSV bulk vendor import.
		"""
		csv_data = """supplier_name,email,phone,vendor_category,gst_number,city,state,pincode
Bulk Vendor Alpha,alpha@bulktest.com,9988776655,Raw Materials,27AAAAA1111A1Z1,Mumbai,Maharashtra,400001
Bulk Vendor Beta,beta@bulktest.com,9988776656,Raw Materials,27BBBBB2222B1Z2,Pune,Maharashtra,411001
"""
		res = bulk_vendor_import(csv_content=csv_data, async_mode=0)
		self.assertEqual(res["status"], "completed")
		self.assertEqual(res["total_rows"], 2)
		self.assertEqual(res["created_count"], 2)
		self.assertEqual(len(res["errors"]), 0)

		for app_id in res["created_records"]:
			self.assertTrue(frappe.db.exists("Vendor Onboarding", app_id))

	def test_bonus_4_bulk_vendor_import_async_queue(self):
		"""
		Bonus Task 4: Test that large imports (>3 rows) with async_mode=1 enqueue properly.
		"""
		csv_data = """supplier_name,email,phone,vendor_category,gst_number
Bulk Vendor 1,bulk1@test.com,9000000001,Raw Materials,27AAAAA1111A1Z1
Bulk Vendor 2,bulk2@test.com,9000000002,Raw Materials,27BBBBB2222B1Z2
Bulk Vendor 3,bulk3@test.com,9000000003,Raw Materials,27CCCCC3333C1Z3
Bulk Vendor 4,bulk4@test.com,9000000004,Raw Materials,27DDDDD4444D1Z4
"""
		res = bulk_vendor_import(csv_content=csv_data, async_mode=1)
		self.assertEqual(res["status"], "queued")
		self.assertEqual(res["total_rows"], 4)

	def test_bonus_5_vendor_comparison_matrix(self):
		"""
		Bonus Task 5: Test get_supplier_comparison returns comparative pricing & delivery data.
		"""
		# Test with existing or arbitrary item
		item_code = frappe.db.get_value("Item", {}, "name") or "TEST-ITEM-1"
		res = get_supplier_comparison(item_code=item_code, qty=10)
		self.assertIsInstance(res, list)
		if res:
			first = res[0]
			self.assertIn("supplier", first)
			self.assertIn("vendor_rating", first)
			self.assertIn("on_time_delivery_rate", first)
			self.assertIn("last_rate", first)
			self.assertIn("estimated_total", first)
			self.assertIn("pricing_history", first)
