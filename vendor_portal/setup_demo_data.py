# Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
# For license information, please see license.txt

import datetime
import random
import frappe
from frappe.utils import add_days, add_months, getdate, nowdate, now_datetime
from vendor_portal.scorecard import sync_supplier_scorecard
from vendor_portal.utils import recalculate_vendor_rating
from vendor_portal.setup_enterprise_environment import setup_everything


def setup_all():
	"""
	Complete master setup and rich realistic data generation for Sanskar Technolabs demo:
	1. Setup configuration (Company, Departments, Designations, Cost Centers)
	2. Master Data (Employees, Users, Clients, Projects, Tasks, Items, Categories, Suppliers)
	3. Historical Transactions (POs, PRs, Rating Logs over past 6 months)
	4. Onboarding records across all stages (Draft, Under Review, Rework, Approved, Rejected)
	5. Supplier Scorecard synchronizations
	"""
	frappe.logger("vendor_portal").info("Starting Sanskar Technolabs enterprise demo setup...")

	company = get_or_setup_company()
	setup_departments_and_designations(company)
	setup_employees_and_users(company)
	setup_items()
	setup_vendor_categories()
	setup_clients_and_projects(company)
	setup_suppliers()
	setup_historical_purchases_and_ratings(company)
	setup_onboarding_lifecycle_records()
	sync_all_scorecards()
	setup_everything()

	frappe.db.commit()
	frappe.logger("vendor_portal").info("Sanskar Technolabs demo setup completed successfully!")
	print("Demo data setup completed successfully!")


def get_or_setup_company():
	"""Ensure company exists with proper default currency."""
	comp_name = "Sanskar Technologies Pvt Ltd"
	if not frappe.db.exists("Company", comp_name):
		comp = frappe.get_doc({
			"doctype": "Company",
			"company_name": comp_name,
			"abbr": "STPL",
			"default_currency": "INR",
			"country": "India",
		})
		comp.insert(ignore_permissions=True)
	return comp_name


def setup_departments_and_designations(company):
	"""Create departments and designations for Sanskar consulting organization."""
	departments = [
		"Consulting - STPL",
		"Development - STPL",
		"Procurement & Admin - STPL",
		"Finance & Accounts - STPL",
		"Human Resources - STPL",
		"Quality & Support - STPL",
	]
	for dept in departments:
		if not frappe.db.exists("Department", dept):
			d = frappe.get_doc({
				"doctype": "Department",
				"department_name": dept.replace(" - STPL", ""),
				"company": company,
			})
			d.insert(ignore_permissions=True)

	designations = [
		"Principal ERPNext Consultant",
		"Senior Frappe Developer",
		"Project Manager",
		"Procurement Specialist",
		"Finance Controller",
		"HR Manager",
		"ERPNext Functional Consultant",
		"QA Engineer",
	]
	for desig in designations:
		if not frappe.db.exists("Designation", desig):
			d = frappe.get_doc({
				"doctype": "Designation",
				"designation_name": desig,
			})
			d.insert(ignore_permissions=True)


def setup_employees_and_users(company):
	"""Setup Sanskar team members and assign appropriate roles."""
	team = [
		{
			"first_name": "Abhijit",
			"last_name": "Dodiya",
			"email": "abhijit.dodiya@sanskar.com",
			"designation": "Principal ERPNext Consultant",
			"department": "Procurement & Admin - STPL",
			"roles": ["System Manager", "Vendor Manager", "Purchase Manager"],
		},
		{
			"first_name": "Kavita",
			"last_name": "Patel",
			"email": "kavita.patel@sanskar.com",
			"designation": "Senior Frappe Developer",
			"department": "Development - STPL",
			"roles": ["Projects User", "Employee"],
		},
		{
			"first_name": "Rahul",
			"last_name": "Sharma",
			"email": "rahul.sharma@sanskar.com",
			"designation": "Project Manager",
			"department": "Consulting - STPL",
			"roles": ["Projects Manager", "Employee"],
		},
		{
			"first_name": "Priya",
			"last_name": "Mehta",
			"email": "priya.mehta@sanskar.com",
			"designation": "Procurement Specialist",
			"department": "Procurement & Admin - STPL",
			"roles": ["Purchase Team", "Purchase User", "Employee"],
		},
		{
			"first_name": "Anand",
			"last_name": "Verma",
			"email": "anand.verma@sanskar.com",
			"designation": "Finance Controller",
			"department": "Finance & Accounts - STPL",
			"roles": ["Accounts Manager", "Employee"],
		},
		{
			"first_name": "Sneha",
			"last_name": "Joshi",
			"email": "sneha.joshi@sanskar.com",
			"designation": "HR Manager",
			"department": "Human Resources - STPL",
			"roles": ["HR Manager", "Employee"],
		},
		{
			"first_name": "Vikram",
			"last_name": "Desai",
			"email": "vikram.desai@sanskar.com",
			"designation": "ERPNext Functional Consultant",
			"department": "Consulting - STPL",
			"roles": ["Projects User", "Employee"],
		},
		{
			"first_name": "Rohan",
			"last_name": "Shah",
			"email": "rohan.shah@sanskar.com",
			"designation": "QA Engineer",
			"department": "Quality & Support - STPL",
			"roles": ["Quality Manager", "Employee"],
		},
	]

	for m in team:
		# User
		if not frappe.db.exists("User", m["email"]):
			u = frappe.get_doc({
				"doctype": "User",
				"email": m["email"],
				"first_name": m["first_name"],
				"last_name": m["last_name"],
				"send_welcome_email": 0,
				"roles": [{"role": r} for r in m["roles"] if frappe.db.exists("Role", r)],
			})
			u.insert(ignore_permissions=True)
		else:
			u = frappe.get_doc("User", m["email"])
			for r in m["roles"]:
				if frappe.db.exists("Role", r) and not any(hr.role == r for hr in u.roles):
					u.append("roles", {"role": r})
			u.save(ignore_permissions=True)

		# Employee
		emp_name = f"{m['first_name']} {m['last_name']}"
		existing_emp = frappe.db.get_value("Employee", {"user_id": m["email"]}, "name")
		if not existing_emp:
			gender = "Female" if m["first_name"] in ["Kavita", "Priya", "Sneha"] else "Male"
			emp = frappe.get_doc({
				"doctype": "Employee",
				"first_name": m["first_name"],
				"last_name": m["last_name"],
				"company": company,
				"user_id": m["email"],
				"personal_email": m["email"],
				"company_email": m["email"],
				"gender": gender,
				"date_of_birth": "1994-06-15",
				"designation": m["designation"],
				"department": m["department"],
				"status": "Active",
				"date_of_joining": "2024-01-15",
			})
			emp.insert(ignore_permissions=True)


def setup_items():
	"""Setup consulting service items and procured equipment/consumables."""
	if not frappe.db.exists("UOM", "Month"):
		frappe.get_doc({"doctype": "UOM", "uom_name": "Month"}).insert(ignore_permissions=True)

	items = [
		# Services
		{
			"item_code": "ST-CONS-01",
			"item_name": "ERPNext Implementation Consulting",
			"item_group": "Services",
			"is_stock_item": 0,
			"stock_uom": "Hour",
			"standard_rate": 2500.0,
		},
		{
			"item_code": "ST-DEV-01",
			"item_name": "Frappe Custom App Development (Hourly)",
			"item_group": "Services",
			"is_stock_item": 0,
			"stock_uom": "Hour",
			"standard_rate": 2000.0,
		},
		{
			"item_code": "ST-SUPPORT-01",
			"item_name": "Annual ERPNext Support Contract",
			"item_group": "Services",
			"is_stock_item": 0,
			"stock_uom": "Month",
			"standard_rate": 50000.0,
		},
		# Hardware & IT
		{
			"item_code": "HW-LAP-M3",
			"item_name": "Apple MacBook Pro M3 Workstation",
			"item_group": "Products",
			"is_stock_item": 0,
			"stock_uom": "Nos",
			"standard_rate": 185000.0,
		},
		{
			"item_code": "HW-MON-4K",
			"item_name": "Dell UltraSharp 27-inch 4K Monitor",
			"item_group": "Products",
			"is_stock_item": 0,
			"stock_uom": "Nos",
			"standard_rate": 45000.0,
		},
		{
			"item_code": "INFRA-CLOUD",
			"item_name": "Dedicated Production Cloud Hosting Instance",
			"item_group": "Services",
			"is_stock_item": 0,
			"stock_uom": "Month",
			"standard_rate": 15000.0,
		},
		# Office Equipment
		{
			"item_code": "OFF-CHAIR",
			"item_name": "Ergonomic Mesh Executive Chair",
			"item_group": "Products",
			"is_stock_item": 0,
			"stock_uom": "Nos",
			"standard_rate": 12000.0,
		},
		{
			"item_code": "OFF-DESK",
			"item_name": "Modular Developer Workstation Desk",
			"item_group": "Products",
			"is_stock_item": 0,
			"stock_uom": "Nos",
			"standard_rate": 22000.0,
		},
		# Raw Materials
		{
			"item_code": "RAW-FASTENER",
			"item_name": "Precision Industrial Fasteners & Bolts",
			"item_group": "Raw Material",
			"is_stock_item": 0,
			"stock_uom": "Kg",
			"standard_rate": 350.0,
		},
	]

	for it in items:
		if not frappe.db.exists("Item", it["item_code"]):
			doc = frappe.get_doc({
				"doctype": "Item",
				"item_code": it["item_code"],
				"item_name": it["item_name"],
				"item_group": it["item_group"],
				"is_stock_item": it["is_stock_item"],
				"stock_uom": it["stock_uom"],
				"standard_rate": it["standard_rate"],
			})
			doc.insert(ignore_permissions=True)


def setup_vendor_categories():
	"""Ensure standard vendor categories exist with configured minimum rating thresholds."""
	categories = [
		{"category_name": "IT Equipment", "min_rating_threshold": 3.5},
		{"category_name": "Cloud Services", "min_rating_threshold": 3.0},
		{"category_name": "Raw Materials", "min_rating_threshold": 3.0},
		{"category_name": "Office Supplies", "min_rating_threshold": 2.5},
		{"category_name": "Subcontracting Services", "min_rating_threshold": 4.0},
	]
	for c in categories:
		if not frappe.db.exists("Vendor Category", c["category_name"]):
			doc = frappe.get_doc({
				"doctype": "Vendor Category",
				"category_name": c["category_name"],
				"min_rating_threshold": c["min_rating_threshold"],
			})
			doc.insert(ignore_permissions=True)


def setup_clients_and_projects(company):
	"""Setup client customers and ERPNext consulting projects."""
	clients = [
		"Apex Logistics Global Ltd",
		"Horizon Healthcare Network",
		"Paramount Precision Forgings",
		"Zenith Retailers India Pvt Ltd",
	]
	for cust in clients:
		if not frappe.db.exists("Customer", cust):
			doc = frappe.get_doc({
				"doctype": "Customer",
				"customer_name": cust,
				"customer_group": "Commercial",
				"territory": "India",
			})
			doc.insert(ignore_permissions=True)

	projects = [
		{
			"project_name": "Apex Logistics ERPNext Implementation",
			"customer": "Apex Logistics Global Ltd",
			"tasks": [
				"Requirements Gathering & Gap Analysis",
				"Custom Fleet & Transport Module Development",
				"Data Migration from Legacy ERP",
				"UAT & End-User Training",
				"Production Go-Live Support",
			],
		},
		{
			"project_name": "Horizon Healthcare Hospital Management",
			"customer": "Horizon Healthcare Network",
			"tasks": [
				"Patient OPD/IPD Workflow Configuration",
				"Pharmacy Billing & Inventory Integration",
				"Laboratory Reports Management",
			],
		},
		{
			"project_name": "Paramount Shop Floor Production System",
			"customer": "Paramount Precision Forgings",
			"tasks": [
				"Multi-Level BOM Setup",
				"Workstation Capacity Planning",
				"Job Card Barcode Scanning",
			],
		},
		{
			"project_name": "Sanskar Internal Vendor Portal & Automations",
			"customer": None,
			"tasks": [
				"Vendor Self-Service Portal",
				"Supplier Scorecard Sync Engine",
				"Analytics Dashboard & Reports",
			],
		},
	]

	for prj in projects:
		p_name = prj["project_name"]
		if not frappe.db.exists("Project", {"project_name": p_name}):
			p = frappe.get_doc({
				"doctype": "Project",
				"project_name": p_name,
				"company": company,
				"customer": prj.get("customer"),
				"status": "Open",
				"expected_start_date": "2026-06-01",
				"expected_end_date": "2026-12-31",
			})
			p.insert(ignore_permissions=True)

			for t in prj["tasks"]:
				if not frappe.db.exists("Task", {"subject": t, "project": p.name}):
					task_doc = frappe.get_doc({
						"doctype": "Task",
						"subject": t,
						"project": p.name,
						"status": "Working",
						"exp_start_date": "2026-06-15",
						"exp_end_date": "2026-11-30",
					})
					task_doc.insert(ignore_permissions=True)


def setup_suppliers():
	"""Setup suppliers across categories with defined ratings and blacklist records."""
	suppliers = [
		{
			"supplier_name": "DevGear Hardware Pvt Ltd",
			"vendor_category": "IT Equipment",
			"vendor_rating": 4.8,
			"tax_id": "27AABCD1111E1Z1",
		},
		{
			"supplier_name": "Prime Cloud Infrastructure",
			"vendor_category": "Cloud Services",
			"vendor_rating": 4.6,
			"tax_id": "27BCCDE2222F1Z2",
		},
		{
			"supplier_name": "Matrix Peripherals India",
			"vendor_category": "IT Equipment",
			"vendor_rating": 3.8,
			"tax_id": "27CDEEF3333G1Z3",
		},
		{
			"supplier_name": "Acme Industrial Supplies Pvt Ltd",
			"vendor_category": "Raw Materials",
			"vendor_rating": 4.2,
			"tax_id": "27DEFFA4444H1Z4",
		},
		{
			"supplier_name": "Apex Office Solutions",
			"vendor_category": "Office Supplies",
			"vendor_rating": 3.2,
			"tax_id": "27EFFAB5555I1Z5",
		},
		{
			"supplier_name": "Zenith Network Solutions",
			"vendor_category": "Cloud Services",
			"vendor_rating": 4.5,
			"tax_id": "27FFABC6666J1Z6",
		},
		{
			"supplier_name": "Precision Tools India",
			"vendor_category": "Raw Materials",
			"vendor_rating": 4.0,
			"tax_id": "27GGABC7777K1Z7",
		},
		{
			"supplier_name": "Omega Fasteners & Tools",
			"vendor_category": "Raw Materials",
			"vendor_rating": 2.2,
			"tax_id": "27HHABC8888L1Z8",
		},
		{
			"supplier_name": "Blacklisted Rogue Supplies",
			"vendor_category": "Raw Materials",
			"vendor_rating": 1.0,
			"is_blacklisted": 1,
			"blacklist_reason": "Repeated quality failures and fraudulent billing",
			"tax_id": "27IIABC9999M1Z9",
		},
	]

	for s in suppliers:
		s_name = s["supplier_name"]
		if not frappe.db.exists("Supplier", s_name):
			doc = frappe.get_doc({
				"doctype": "Supplier",
				"supplier_name": s_name,
				"supplier_group": "Local",
				"vendor_category": s.get("vendor_category"),
				"vendor_rating": s.get("vendor_rating", 0.0),
				"total_rating_count": 5,
				"tax_id": s.get("tax_id"),
				"is_blacklisted": s.get("is_blacklisted", 0),
				"blacklist_reason": s.get("blacklist_reason"),
			})
			doc.insert(ignore_permissions=True)
		else:
			frappe.db.set_value(
				"Supplier",
				s_name,
				{
					"vendor_category": s.get("vendor_category"),
					"vendor_rating": s.get("vendor_rating", 0.0),
					"total_rating_count": 5,
					"is_blacklisted": s.get("is_blacklisted", 0),
					"blacklist_reason": s.get("blacklist_reason"),
				},
				update_modified=False,
			)


def setup_historical_purchases_and_ratings(company):
	"""
	Create historical purchase orders, receipts, and rating logs across June-Nov 2026.
	This ensures that all 4 dashboard charts and Script Reports render non-empty, rich metrics.
	"""
	transactions_matrix = [
		# (supplier, item, qty, rate, month_offset, on_time_bool, deliv_score)
		("DevGear Hardware Pvt Ltd", "HW-LAP-M3", 3, 180000.0, 5, True, 4.8),
		("DevGear Hardware Pvt Ltd", "HW-MON-4K", 6, 44000.0, 4, True, 4.7),
		("Prime Cloud Infrastructure", "INFRA-CLOUD", 2, 15000.0, 5, True, 4.9),
		("Prime Cloud Infrastructure", "INFRA-CLOUD", 2, 15000.0, 4, True, 4.8),
		("Prime Cloud Infrastructure", "INFRA-CLOUD", 2, 15000.0, 3, True, 4.6),
		("Prime Cloud Infrastructure", "INFRA-CLOUD", 2, 15000.0, 2, True, 4.5),
		("Prime Cloud Infrastructure", "INFRA-CLOUD", 2, 15000.0, 1, True, 4.7),
		("Matrix Peripherals India", "HW-MON-4K", 4, 45000.0, 3, True, 4.0),
		("Acme Industrial Supplies Pvt Ltd", "RAW-FASTENER", 50, 340.0, 4, True, 4.4),
		("Acme Industrial Supplies Pvt Ltd", "RAW-FASTENER", 100, 335.0, 2, True, 4.3),
		("Apex Office Solutions", "OFF-CHAIR", 10, 11500.0, 3, False, 3.5),
		("Apex Office Solutions", "OFF-DESK", 5, 21000.0, 1, True, 3.8),
		("Zenith Network Solutions", "INFRA-CLOUD", 1, 14500.0, 2, True, 4.5),
		("Precision Tools India", "RAW-FASTENER", 40, 350.0, 1, True, 4.2),
		("Omega Fasteners & Tools", "RAW-FASTENER", 20, 360.0, 2, False, 2.2),
	]

	today = getdate(nowdate())

	for s_name, item_code, qty, rate, m_offset, on_time, deliv_score in transactions_matrix:
		tx_date = add_months(today, -m_offset)
		tx_date_str = tx_date.strftime("%Y-%m-%d")

		# 1. Purchase Order
		po = frappe.get_doc({
			"doctype": "Purchase Order",
			"company": company,
			"supplier": s_name,
			"transaction_date": tx_date_str,
			"schedule_date": tx_date_str,
			"items": [
				{
					"item_code": item_code,
					"qty": qty,
					"rate": rate,
					"amount": qty * rate,
					"conversion_factor": 1.0,
					"stock_qty": qty,
					"uom": frappe.db.get_value("Item", item_code, "stock_uom") or "Nos",
					"stock_uom": frappe.db.get_value("Item", item_code, "stock_uom") or "Nos",
					"schedule_date": tx_date_str,
				}
			],
		})
		po.flags.ignore_mandatory = True
		po.flags.ignore_validate = True
		po.insert(ignore_permissions=True)
		po.db_set("docstatus", 1)
		po.db_set("grand_total", qty * rate)
		po.db_set("net_total", qty * rate)

		# 2. Purchase Receipt
		pr_date = tx_date if on_time else add_days(tx_date, 4)
		pr = frappe.get_doc({
			"doctype": "Purchase Receipt",
			"company": company,
			"supplier": s_name,
			"posting_date": pr_date.strftime("%Y-%m-%d"),
			"items": [
				{
					"item_code": item_code,
					"qty": qty,
					"received_qty": qty,
					"rate": rate,
					"amount": qty * rate,
					"conversion_factor": 1.0,
					"stock_qty": qty,
					"uom": frappe.db.get_value("Item", item_code, "stock_uom") or "Nos",
					"stock_uom": frappe.db.get_value("Item", item_code, "stock_uom") or "Nos",
					"purchase_order": po.name,
					"purchase_order_item": po.items[0].name,
				}
			],
		})
		pr.flags.ignore_mandatory = True
		pr.flags.ignore_validate = True
		pr.insert(ignore_permissions=True)
		pr.db_set("docstatus", 1)

		# 3. Create Rating Logs across multiple dimensions
		for r_type, sc in [
			("Delivery", deliv_score),
			("Quality", min(5.0, deliv_score + 0.1)),
			("Pricing", max(1.0, deliv_score - 0.2)),
			("Communication", min(5.0, deliv_score + 0.2)),
		]:
			rlog = frappe.get_doc({
				"doctype": "Vendor Rating Log",
				"supplier": s_name,
				"rating_date": tx_date_str,
				"rating_type": r_type,
				"score": round(sc, 1),
				"rated_by": "Administrator",
				"purchase_order": po.name,
				"purchase_receipt": pr.name,
				"remarks": f"Automated performance evaluation for {po.name}",
			})
			rlog.insert(ignore_permissions=True)


def setup_onboarding_lifecycle_records():
	"""
	Ensure Onboarding pipeline has realistic records across ALL 5 stages:
	Draft, Under Review, Rework, Approved, and Rejected.
	"""
	pipeline_records = [
		{
			"supplier_name": "CyberNet Telecom Ltd",
			"category": "Cloud Services",
			"email": "telecom@cybernet.com",
			"status": "Draft",
			"notes": None,
		},
		{
			"supplier_name": "Apex Micro Devices",
			"category": "IT Equipment",
			"email": "sales@apexdevices.com",
			"status": "Under Review",
			"notes": None,
		},
		{
			"supplier_name": "TechnoFab Structural Works",
			"category": "Raw Materials",
			"email": "contact@technofab.com",
			"status": "Rework",
			"rework_notes": "Please provide an updated GST 3B return and clarification on banking IFSC code.",
		},
		{
			"supplier_name": "SwiftLine Logistics Services",
			"category": "Office Supplies",
			"email": "info@swiftline.com",
			"status": "Rework",
			"rework_notes": "Certificate of Incorporation document was unreadable; please re-upload in high resolution.",
		},
		{
			"supplier_name": "Unverified Trading Entity",
			"category": "Raw Materials",
			"email": "unverified@entity.com",
			"status": "Rejected",
			"rejection_reason": "Failed compliance check: entity flagged for non-filing of GST returns.",
		},
		{
			"supplier_name": "Horizon Paper & Stationery",
			"category": "Office Supplies",
			"email": "paper@horizon.com",
			"status": "Rejected",
			"rejection_reason": "Vendor does not meet minimum credit terms and pricing thresholds.",
		},
	]

	for rec in pipeline_records:
		s_name = rec["supplier_name"]
		if not frappe.db.exists("Vendor Onboarding", {"supplier_name": s_name}):
			doc = frappe.get_doc({
				"doctype": "Vendor Onboarding",
				"supplier_name": s_name,
				"company_name": f"{s_name} Pvt Ltd",
				"contact_person": "Operations Manager",
				"email": rec["email"],
				"phone": "9876543200",
				"address_line_1": "Sanskar Tech Park, Phase 2",
				"city": "Ahmedabad",
				"state": "Gujarat",
				"pincode": "380015",
				"vendor_category": rec["category"],
				"gst_number": f"24AAAAA{random.randint(1000, 9999)}A1Z5",
				"onboarding_status": "Draft",
				"documents": [
					{
						"document_type": "GST Certificate",
						"document_name": "gst_cert.pdf",
						"document_file": "/files/gst.pdf",
						"is_verified": 1,
					},
					{
						"document_type": "PAN Card",
						"document_name": "pan_card.pdf",
						"document_file": "/files/pan.pdf",
						"is_verified": 1,
					},
				],
			})
			doc.insert(ignore_permissions=True)
			if rec["status"] != "Draft":
				doc.db_set("onboarding_status", rec["status"])
				if rec.get("rework_notes"):
					doc.db_set("rework_notes", rec["rework_notes"])
				if rec.get("rejection_reason"):
					doc.db_set("rejection_reason", rec["rejection_reason"])


def sync_all_scorecards():
	"""Recalculate weighted ratings and sync ERPNext Supplier Scorecards for all suppliers."""
	suppliers = frappe.get_all("Supplier", pluck="name")
	for sup in suppliers:
		try:
			rating, count = recalculate_vendor_rating(sup)
			sync_supplier_scorecard(sup, rating)
		except Exception as e:
			frappe.logger("vendor_portal").warning(f"Failed to sync scorecard for {sup}: {e}")
