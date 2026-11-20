# Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
# For license information, please see license.txt

import datetime
import random
import frappe
from frappe.utils import add_days, add_months, getdate, nowdate, now_datetime


def setup_everything():
	"""
	Complete end-to-end setup across all Month 3 assessment requirements:
	1. Company & Letter Head (Sanskar Technologies Pvt Ltd, GSTIN, PAN, Address, Branding)
	2. GST & Tax Settings (Input/Output CGST, SGST, IGST, Templates, Tax Categories)
	3. Email Digest & Notifications (Management Weekly Digest, Email Account, Alert Rules)
	4. Workspace & Navigation Integration (Dock item, Buying sidebar, Vendor Portal workspace)
	5. Stock & Inventory (Warehouses, Stock Items, Stock Entries, SLEs)
	6. Manufacturing Cycle (Multi-level BOM, Work Order, Stock Entry Manufacture)
	7. Complete Buying Cycle (Material Requests, Supplier Quotations, Purchase Invoices, Payment Entries)
	8. Complete Selling Cycle (Leads, Opportunities, Quotations, Sales Orders, Delivery Notes, Sales Invoices, Payment Entries)
	9. Support & HR Records (Issues, Leave Applications)
	10. Dashboards & Reports Synchronization (2026 current transaction dates)
	"""
	company = "Sanskar Technologies Pvt Ltd"
	print(f"Starting complete enterprise environment setup for {company}...")

	setup_company_and_letter_head(company)
	setup_gst_and_tax_settings(company)
	setup_email_digest_and_notifications(company)
	setup_workspace_and_dock_navigation()
	setup_stock_and_inventory(company)
	setup_manufacturing_module(company)
	setup_complete_buying_cycle(company)
	setup_complete_selling_cycle(company)
	setup_support_and_hr(company)

	frappe.db.commit()
	print(f"Enterprise environment setup for {company} completed successfully!")


def setup_company_and_letter_head(company):
	"""Setup company GSTIN, PAN, Address and default Letter Head."""
	comp = frappe.get_doc("Company", company)
	comp.tax_id = "24AAACS1429B1Z1"
	comp.abbr = "STPL"
	comp.default_currency = "INR"
	comp.country = "India"

	# Letter Head
	lh_name = "Sanskar Technologies Letter Head"
	if not frappe.db.exists("Letter Head", lh_name):
		lh = frappe.get_doc({
			"doctype": "Letter Head",
			"letter_head_name": lh_name,
			"is_default": 1,
			"content": """
<div style="border-bottom: 3px solid #1e3a8a; padding-bottom: 12px; margin-bottom: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
	<table style="width: 100%; border-collapse: collapse;">
		<tr>
			<td style="vertical-align: middle;">
				<div style="font-size: 24px; font-weight: 800; color: #1e3a8a; letter-spacing: -0.5px;">SANSKAR TECHNOLOGIES</div>
				<div style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin-top: 2px;">Enterprise ERPNext Solutions & Cloud Systems</div>
			</td>
			<td style="text-align: right; vertical-align: middle; font-size: 11px; color: #475569; line-height: 1.5;">
				<b>Sanskar Technologies Pvt Ltd</b><br>
				Sanskar House, Infocity, Gandhinagar, Gujarat 382007<br>
				<b>GSTIN:</b> 24AAACS1429B1Z1 | <b>PAN:</b> AAACS1429B<br>
				<b>Email:</b> contact@sanskartechnolabs.com | <b>Phone:</b> +91 79 4000 8000
			</td>
		</tr>
	</table>
</div>
			""",
			"footer": """
<div style="border-top: 1px solid #cbd5e1; padding-top: 8px; margin-top: 20px; font-size: 10px; color: #94a3b8; text-align: center; font-family: sans-serif;">
	Sanskar Technologies Pvt Ltd | Confidential & Proprietary Document | Regd. Office: Infocity, Gandhinagar, Gujarat 382007 | www.sanskartechnolabs.com
</div>
			""",
		})
		lh.insert(ignore_permissions=True)
	else:
		frappe.db.set_value("Letter Head", lh_name, "is_default", 1)

	comp.default_letter_head = lh_name
	comp.save(ignore_permissions=True)

	# Company Address
	addr_name = f"{company}-Registered"
	if not frappe.db.exists("Address", addr_name):
		addr = frappe.get_doc({
			"doctype": "Address",
			"address_title": company,
			"address_type": "Billing",
			"address_line1": "Sanskar House, Infocity Phase-2",
			"city": "Gandhinagar",
			"state": "Gujarat",
			"gst_state": "Gujarat",
			"gst_state_number": "24",
			"country": "India",
			"pincode": "382007",
			"email_id": "contact@sanskartechnolabs.com",
			"phone": "+91 79 4000 8000",
			"is_primary_address": 1,
			"links": [{"link_doctype": "Company", "link_name": company}],
		})
		addr.insert(ignore_permissions=True)


def setup_gst_and_tax_settings(company):
	"""Setup Chart of Accounts GST tax accounts, templates and tax categories."""
	# 1. Tax Accounts
	abbr = "STPL"
	tax_assets_parent = f"Tax Assets - {abbr}"
	duties_parent = f"Duties and Taxes - {abbr}"
	bank_parent = f"Bank Accounts - {abbr}"

	tax_accounts = [
		{"account_name": "Input Tax CGST", "parent_account": tax_assets_parent, "account_type": "Tax", "root_type": "Asset"},
		{"account_name": "Input Tax SGST", "parent_account": tax_assets_parent, "account_type": "Tax", "root_type": "Asset"},
		{"account_name": "Input Tax IGST", "parent_account": tax_assets_parent, "account_type": "Tax", "root_type": "Asset"},
		{"account_name": "Output Tax CGST", "parent_account": duties_parent, "account_type": "Tax", "root_type": "Liability"},
		{"account_name": "Output Tax SGST", "parent_account": duties_parent, "account_type": "Tax", "root_type": "Liability"},
		{"account_name": "Output Tax IGST", "parent_account": duties_parent, "account_type": "Tax", "root_type": "Liability"},
		{"account_name": "HDFC Bank", "parent_account": bank_parent, "account_type": "Bank", "root_type": "Asset"},
	]

	for acc in tax_accounts:
		full_name = f"{acc['account_name']} - {abbr}"
		if not frappe.db.exists("Account", full_name):
			doc = frappe.get_doc({
				"doctype": "Account",
				"account_name": acc["account_name"],
				"company": company,
				"parent_account": acc["parent_account"],
				"account_type": acc["account_type"],
				"root_type": acc["root_type"],
			})
			doc.insert(ignore_permissions=True)

	# 2. Tax Categories
	for tc in ["In-State GST", "Out-of-State GST", "Zero-Rated"]:
		if not frappe.db.exists("Tax Category", tc):
			frappe.get_doc({"doctype": "Tax Category", "title": tc}).insert(ignore_permissions=True)

	# 3. Purchase Taxes and Charges Template
	pt_instate = "In-State GST 18% (CGST 9% + SGST 9%)"
	if not frappe.db.exists("Purchase Taxes and Charges Template", {"company": company, "tax_category": "In-State GST"}):
		pt = frappe.get_doc({
			"doctype": "Purchase Taxes and Charges Template",
			"title": pt_instate,
			"company": company,
			"is_default": 1,
			"tax_category": "In-State GST",
			"taxes": [
				{
					"category": "Total",
					"charge_type": "On Net Total",
					"account_head": f"Input Tax CGST - {abbr}",
					"rate": 9.0,
					"description": "CGST @ 9% on Purchase",
				},
				{
					"category": "Total",
					"charge_type": "On Net Total",
					"account_head": f"Input Tax SGST - {abbr}",
					"rate": 9.0,
					"description": "SGST @ 9% on Purchase",
				},
			],
		})
		pt.insert(ignore_permissions=True)

	pt_inter = "Out-of-State IGST 18%"
	if not frappe.db.exists("Purchase Taxes and Charges Template", {"company": company, "tax_category": "Out-of-State GST"}):
		pt = frappe.get_doc({
			"doctype": "Purchase Taxes and Charges Template",
			"title": pt_inter,
			"company": company,
			"is_default": 0,
			"tax_category": "Out-of-State GST",
			"taxes": [
				{
					"category": "Total",
					"charge_type": "On Net Total",
					"account_head": f"Input Tax IGST - {abbr}",
					"rate": 18.0,
					"description": "IGST @ 18% on Interstate Purchase",
				},
			],
		})
		pt.insert(ignore_permissions=True)

	# 4. Sales Taxes and Charges Template
	st_instate = "In-State GST 18% (CGST 9% + SGST 9%)"
	if not frappe.db.exists("Sales Taxes and Charges Template", {"company": company, "tax_category": "In-State GST"}):
		st = frappe.get_doc({
			"doctype": "Sales Taxes and Charges Template",
			"title": st_instate,
			"company": company,
			"is_default": 1,
			"tax_category": "In-State GST",
			"taxes": [
				{
					"charge_type": "On Net Total",
					"account_head": f"Output Tax CGST - {abbr}",
					"rate": 9.0,
					"description": "Output CGST @ 9% on Sales",
				},
				{
					"charge_type": "On Net Total",
					"account_head": f"Output Tax SGST - {abbr}",
					"rate": 9.0,
					"description": "Output SGST @ 9% on Sales",
				},
			],
		})
		st.insert(ignore_permissions=True)

	st_inter = "Out-of-State IGST 18%"
	if not frappe.db.exists("Sales Taxes and Charges Template", {"company": company, "tax_category": "Out-of-State GST"}):
		st = frappe.get_doc({
			"doctype": "Sales Taxes and Charges Template",
			"title": st_inter,
			"company": company,
			"is_default": 0,
			"tax_category": "Out-of-State GST",
			"taxes": [
				{
					"charge_type": "On Net Total",
					"account_head": f"Output Tax IGST - {abbr}",
					"rate": 18.0,
					"description": "Output IGST @ 18% on Interstate Sales",
				},
			],
		})
		st.insert(ignore_permissions=True)


def setup_email_digest_and_notifications(company):
	"""Setup Email Digest and event-driven Notification rules."""
	# 1. Email Digest
	digest_name = "Sanskar Weekly Executive Digest"
	if not frappe.db.exists("Email Digest", digest_name):
		ed = frappe.get_doc({
			"doctype": "Email Digest",
			"name": digest_name,
			"company": company,
			"frequency": "Weekly",
			"enabled": 1,
			"recipients": [
				{"recipient": "Administrator"},
				{"recipient": "vendor_mgr@test.com"},
			],
			"purchase_order": 1,
			"purchase_receipt": 1,
			"sales_order": 1,
			"invoiced_amount": 1,
			"payables": 1,
			"payments": 1,
			"bank_balance": 1,
			"new_quotations": 1,
		})
		ed.insert(ignore_permissions=True)

	# 2. Email Account
	acc_name = "Notifications - Sanskar"
	if not frappe.db.exists("Email Account", acc_name):
		ea = frappe.get_doc({
			"doctype": "Email Account",
			"email_account_name": acc_name,
			"email_id": "notifications@sanskartechnolabs.com",
			"default_outgoing": 1,
			"enable_outgoing": 0,
			"no_smtp_authentication": 1,
		})
		ea.insert(ignore_permissions=True)

	# 3. Notification Rules
	notifications = [
		{
			"subject": "Vendor Onboarding Approved: {{ doc.vendor_name }}",
			"document_type": "Vendor Onboarding",
			"event": "Save",
			"condition": "doc.get('workflow_state') == 'Approved'",
			"recipients": [{"receiver_by_role": "Purchase Team"}, {"receiver_by_role": "Vendor Manager"}],
		},
		{
			"subject": "Low Vendor Rating Warning for Supplier: {{ doc.supplier }}",
			"document_type": "Vendor Rating Log",
			"event": "New",
			"condition": "doc.score < 3.0",
			"recipients": [{"receiver_by_role": "Vendor Manager"}],
		},
		{
			"subject": "Purchase Order Submitted: {{ doc.name }}",
			"document_type": "Purchase Order",
			"event": "Submit",
			"condition": "",
			"recipients": [{"receiver_by_role": "Purchase Manager"}],
		},
	]

	for n in notifications:
		if not frappe.db.exists("Notification", n["subject"]):
			doc = frappe.get_doc({
				"doctype": "Notification",
				"channel": "Email",
				"subject": n["subject"],
				"document_type": n["document_type"],
				"event": n["event"],
				"condition": n.get("condition", ""),
				"recipients": n["recipients"],
				"message": f"System Alert for {n['document_type']} event triggered automatically.",
				"enabled": 1,
			})
			doc.insert(ignore_permissions=True)


def setup_workspace_and_dock_navigation():
	"""
	Ensure Vendor Portal workspace is directly mounted into the Desk Dock (left icon rail)
	and the Buying Sidebar, guaranteeing complete UI visibility in Frappe v16.
	"""
	orig_dev_mode = getattr(frappe.conf, "developer_mode", 0)
	try:
		frappe.conf.developer_mode = 0
		# 1. Mount into Dock (erpnext dock document)
		if frappe.db.exists("DocType", "Dock") and frappe.db.exists("Dock", "erpnext"):
			dock = frappe.get_doc("Dock", "erpnext")
			if not any(it.title == "Vendor Portal" for it in dock.items):
				dock.append("items", {
					"link_type": "Workspace",
					"link_to": "Vendor Portal",
					"icon": "shopping-cart-soft",
					"title": "Vendor Portal",
					"added": 0,
					"hidden": 0,
				})
				dock.save(ignore_permissions=True)

		# 2. Add into Sidebar 'Buying'
		if frappe.db.exists("DocType", "Sidebar") and frappe.db.exists("Sidebar", "Buying"):
			sidebar = frappe.get_doc("Sidebar", "Buying")
			if not any(it.label == "Vendor Management" for it in sidebar.items):
				sidebar.append("items", {
					"label": "Vendor Management",
					"type": "Section Break",
					"collapsible": 1,
					"indent": 1,
					"icon": "truck",
				})
				sidebar.append("items", {
					"label": "Vendor Portal",
					"link_type": "Workspace",
					"link_to": "Vendor Portal",
					"type": "Link",
					"icon": "building",
				})
				sidebar.append("items", {
					"label": "Vendor Onboarding",
					"link_type": "DocType",
					"link_to": "Vendor Onboarding",
					"type": "Link",
					"icon": "user-check",
				})
				sidebar.append("items", {
					"label": "Vendor Rating Log",
					"link_type": "DocType",
					"link_to": "Vendor Rating Log",
					"type": "Link",
					"icon": "star",
				})
				sidebar.append("items", {
					"label": "Vendor Category",
					"link_type": "DocType",
					"link_to": "Vendor Category",
					"type": "Link",
					"icon": "tag",
				})
				sidebar.append("items", {
					"label": "Vendor Portal Settings",
					"link_type": "DocType",
					"link_to": "Vendor Portal Settings",
					"type": "Link",
					"icon": "settings",
				})
				sidebar.save(ignore_permissions=True)
	finally:
		frappe.conf.developer_mode = orig_dev_mode


def setup_stock_and_inventory(company):
	"""Setup inventory items, warehouses, and opening stock entries to generate real SLEs."""
	abbr = "STPL"

	# 1. Warehouses
	warehouses = [
		{"name": f"Stores - {abbr}", "warehouse_name": "Stores"},
		{"name": f"Work In Progress - {abbr}", "warehouse_name": "Work In Progress"},
		{"name": f"Finished Goods - {abbr}", "warehouse_name": "Finished Goods"},
	]
	parent_wh = f"All Warehouses - {abbr}"
	for wh in warehouses:
		if not frappe.db.exists("Warehouse", wh["name"]):
			w = frappe.get_doc({
				"doctype": "Warehouse",
				"warehouse_name": wh["warehouse_name"],
				"company": company,
				"parent_warehouse": parent_wh,
			})
			w.insert(ignore_permissions=True)

	# 2. Stock items
	stock_items = [
		{
			"item_code": "RAW-STEEL-10MM",
			"item_name": "High-Grade Structural Steel Rods 10mm",
			"item_group": "Raw Material",
			"is_stock_item": 1,
			"stock_uom": "Meter",
			"valuation_rate": 150.0,
			"standard_rate": 180.0,
		},
		{
			"item_code": "RAW-COPPER-WIRE",
			"item_name": "Insulated Pure Copper Wire 2.5 sq mm",
			"item_group": "Raw Material",
			"is_stock_item": 1,
			"stock_uom": "Meter",
			"valuation_rate": 80.0,
			"standard_rate": 95.0,
		},
		{
			"item_code": "RAW-FASTENERS",
			"item_name": "Precision Industrial Bolt & Nut Fasteners",
			"item_group": "Raw Material",
			"is_stock_item": 1,
			"stock_uom": "Box",
			"valuation_rate": 350.0,
			"standard_rate": 420.0,
		},
		{
			"item_code": "FG-CONTROL-PANEL",
			"item_name": "Industrial Automation Control Panel System",
			"item_group": "Products",
			"is_stock_item": 1,
			"stock_uom": "Nos",
			"valuation_rate": 12500.0,
			"standard_rate": 18500.0,
		},
	]

	for it in stock_items:
		if not frappe.db.exists("Item", it["item_code"]):
			doc = frappe.get_doc({
				"doctype": "Item",
				"item_code": it["item_code"],
				"item_name": it["item_name"],
				"item_group": it["item_group"],
				"is_stock_item": 1,
				"stock_uom": it["stock_uom"],
				"valuation_rate": it["valuation_rate"],
				"standard_rate": it["standard_rate"],
			})
			doc.insert(ignore_permissions=True)
		else:
			frappe.db.set_value("Item", it["item_code"], "is_stock_item", 1)

	# 3. Stock Entry: Material Receipt (Initial Opening Stock in 2026)
	if frappe.db.count("Stock Entry", {"company": company, "stock_entry_type": "Material Receipt"}) == 0:
		se = frappe.get_doc({
			"doctype": "Stock Entry",
			"company": company,
			"stock_entry_type": "Material Receipt",
			"posting_date": "2026-08-01",
			"posting_time": "10:00:00",
			"to_warehouse": f"Stores - {abbr}",
			"items": [
				{
					"item_code": "RAW-STEEL-10MM",
					"qty": 500,
					"basic_rate": 150.0,
					"t_warehouse": f"Stores - {abbr}",
					"uom": "Meter",
					"stock_uom": "Meter",
					"conversion_factor": 1.0,
				},
				{
					"item_code": "RAW-COPPER-WIRE",
					"qty": 1000,
					"basic_rate": 80.0,
					"t_warehouse": f"Stores - {abbr}",
					"uom": "Meter",
					"stock_uom": "Meter",
					"conversion_factor": 1.0,
				},
				{
					"item_code": "RAW-FASTENERS",
					"qty": 200,
					"basic_rate": 350.0,
					"t_warehouse": f"Stores - {abbr}",
					"uom": "Box",
					"stock_uom": "Box",
					"conversion_factor": 1.0,
				},
			],
		})
		se.flags.ignore_permissions = True
		se.flags.ignore_mandatory = True
		se.insert()
		se.submit()

	# 4. Stock Entry: Material Transfer to WIP
	if frappe.db.count("Stock Entry", {"company": company, "stock_entry_type": "Material Transfer"}) == 0:
		se_tr = frappe.get_doc({
			"doctype": "Stock Entry",
			"company": company,
			"stock_entry_type": "Material Transfer",
			"posting_date": "2026-09-01",
			"posting_time": "11:30:00",
			"from_warehouse": f"Stores - {abbr}",
			"to_warehouse": f"Work In Progress - {abbr}",
			"items": [
				{
					"item_code": "RAW-STEEL-10MM",
					"qty": 100,
					"basic_rate": 150.0,
					"s_warehouse": f"Stores - {abbr}",
					"t_warehouse": f"Work In Progress - {abbr}",
					"uom": "Meter",
					"stock_uom": "Meter",
					"conversion_factor": 1.0,
				},
				{
					"item_code": "RAW-COPPER-WIRE",
					"qty": 200,
					"basic_rate": 80.0,
					"s_warehouse": f"Stores - {abbr}",
					"t_warehouse": f"Work In Progress - {abbr}",
					"uom": "Meter",
					"stock_uom": "Meter",
					"conversion_factor": 1.0,
				},
			],
		})
		se_tr.flags.ignore_permissions = True
		se_tr.flags.ignore_mandatory = True
		se_tr.insert()
		se_tr.submit()


def setup_manufacturing_module(company):
	"""Setup Bill of Materials (BOM) and Work Order for manufacturing."""
	abbr = "STPL"
	fg_item = "FG-CONTROL-PANEL"

	# BOM
	bom_name = f"BOM-{fg_item}-001"
	if not frappe.db.exists("BOM", {"item": fg_item, "is_active": 1}):
		bom = frappe.get_doc({
			"doctype": "BOM",
			"item": fg_item,
			"company": company,
			"quantity": 1.0,
			"is_active": 1,
			"is_default": 1,
			"items": [
				{"item_code": "RAW-STEEL-10MM", "qty": 10.0, "rate": 150.0, "uom": "Meter", "stock_uom": "Meter"},
				{"item_code": "RAW-COPPER-WIRE", "qty": 20.0, "rate": 80.0, "uom": "Meter", "stock_uom": "Meter"},
				{"item_code": "RAW-FASTENERS", "qty": 2.0, "rate": 350.0, "uom": "Box", "stock_uom": "Box"},
			],
		})
		bom.flags.ignore_permissions = True
		bom.flags.ignore_mandatory = True
		bom.insert()
		bom.submit()
		bom_name = bom.name
	else:
		bom_name = frappe.db.get_value("BOM", {"item": fg_item, "is_active": 1}, "name")

	# Work Order
	if frappe.db.count("Work Order", {"company": company}) == 0 and bom_name:
		wo = frappe.get_doc({
			"doctype": "Work Order",
			"company": company,
			"production_item": fg_item,
			"bom_no": bom_name,
			"qty": 5.0,
			"wip_warehouse": f"Work In Progress - {abbr}",
			"fg_warehouse": f"Finished Goods - {abbr}",
			"planned_start_date": "2026-10-01 09:00:00",
			"status": "Submitted",
		})
		wo.flags.ignore_permissions = True
		wo.flags.ignore_mandatory = True
		wo.insert()
		wo.submit()


def setup_complete_buying_cycle(company):
	"""Complete full buying cycle: Material Requests, Supplier Quotations, Purchase Invoices & Payment Entries."""
	abbr = "STPL"
	today = getdate(nowdate())

	# 1. Material Requests
	if frappe.db.count("Material Request", {"company": company}) == 0:
		for idx, it_code in enumerate(["RAW-STEEL-10MM", "RAW-COPPER-WIRE", "HW-MON-4K"]):
			mr = frappe.get_doc({
				"doctype": "Material Request",
				"company": company,
				"material_request_type": "Purchase",
				"transaction_date": add_days(today, -30 + idx * 5).strftime("%Y-%m-%d"),
				"schedule_date": add_days(today, -15 + idx * 5).strftime("%Y-%m-%d"),
				"items": [
					{
						"item_code": it_code,
						"qty": 50 + idx * 25,
						"schedule_date": add_days(today, -15 + idx * 5).strftime("%Y-%m-%d"),
						"uom": frappe.db.get_value("Item", it_code, "stock_uom") or "Nos",
					}
				],
			})
			mr.flags.ignore_permissions = True
			mr.flags.ignore_mandatory = True
			mr.insert()
			mr.submit()

	# 2. Supplier Quotations
	if frappe.db.count("Supplier Quotation", {"company": company}) == 0:
		suppliers = ["DevGear Hardware Pvt Ltd", "Precision Tools India", "Acme Industrial Supplies Pvt Ltd"]
		for idx, sup in enumerate(suppliers):
			sq = frappe.get_doc({
				"doctype": "Supplier Quotation",
				"company": company,
				"supplier": sup,
				"transaction_date": add_days(today, -25 + idx * 3).strftime("%Y-%m-%d"),
				"items": [
					{
						"item_code": "RAW-STEEL-10MM" if idx != 0 else "HW-MON-4K",
						"qty": 20,
						"rate": 145.0 if idx != 0 else 42000.0,
						"uom": "Meter" if idx != 0 else "Nos",
					}
				],
			})
			sq.flags.ignore_permissions = True
			sq.flags.ignore_mandatory = True
			sq.insert()
			sq.submit()

	# 3. Purchase Invoices & Payment Entries for submitted POs / PRs
	submitted_pos = frappe.get_all(
		"Purchase Order",
		filters={"company": company, "docstatus": 1, "per_billed": ["<", 100]},
		fields=["name", "supplier", "grand_total", "net_total", "transaction_date"],
		limit=12,
	)

	tax_template = f"In-State GST 18% (CGST 9% + SGST 9%) - {abbr}"

	for po_data in submitted_pos:
		po_doc = frappe.get_doc("Purchase Order", po_data.name)
		if frappe.db.exists("Purchase Invoice", {"purchase_order": po_doc.name}):
			continue

		pi = frappe.get_doc({
			"doctype": "Purchase Invoice",
			"company": company,
			"supplier": po_doc.supplier,
			"posting_date": po_doc.transaction_date,
			"due_date": add_days(getdate(po_doc.transaction_date), 30).strftime("%Y-%m-%d"),
			"taxes_and_charges": tax_template if frappe.db.exists("Purchase Taxes and Charges Template", tax_template) else None,
			"credit_to": f"Creditors - {abbr}",
			"items": [
				{
					"item_code": it.item_code,
					"item_name": it.item_name,
					"qty": it.qty,
					"rate": it.rate,
					"amount": it.amount,
					"purchase_order": po_doc.name,
					"po_detail": it.name,
					"uom": it.uom,
					"stock_uom": it.stock_uom,
					"conversion_factor": 1.0,
					"expense_account": f"Stock Received But Not Billed - {abbr}",
				}
				for it in po_doc.items
			],
		})
		pi.flags.ignore_permissions = True
		pi.flags.ignore_mandatory = True
		pi.flags.ignore_validate = True
		try:
			pi.insert()
			pi.submit()

			# Create Payment Entry for 50% of these invoices
			if random.random() > 0.3:
				pe = frappe.get_doc({
					"doctype": "Payment Entry",
					"payment_type": "Pay",
					"company": company,
					"party_type": "Supplier",
					"party": po_doc.supplier,
					"posting_date": add_days(getdate(po_doc.transaction_date), 5).strftime("%Y-%m-%d"),
					"paid_from": f"HDFC Bank - {abbr}",
					"paid_to": f"Creditors - {abbr}",
					"paid_amount": pi.grand_total,
					"received_amount": pi.grand_total,
					"target_exchange_rate": 1.0,
					"reference_no": f"UTR-{pi.name[-6:]}",
					"reference_date": add_days(getdate(po_doc.transaction_date), 5).strftime("%Y-%m-%d"),
					"references": [
						{
							"reference_doctype": "Purchase Invoice",
							"reference_name": pi.name,
							"total_amount": pi.grand_total,
							"outstanding_amount": 0.0,
							"allocated_amount": pi.grand_total,
						}
					],
				})
				pe.flags.ignore_permissions = True
				pe.flags.ignore_mandatory = True
				pe.insert()
				pe.submit()
		except Exception as e:
			frappe.log_error(title="Purchase Invoice Creation Error", message=str(e))


def setup_complete_selling_cycle(company):
	"""Complete full selling cycle: Leads, Opportunities, Quotations, Sales Orders, Delivery Notes, Sales Invoices & Payments."""
	abbr = "STPL"
	today = getdate(nowdate())

	customers = frappe.get_all("Customer", filters={"disabled": 0}, fields=["name", "customer_name"], limit=4)
	if not customers:
		return

	# 1. Opportunities from Leads
	leads = frappe.get_all("Lead", limit=3, fields=["name", "lead_name"])
	for l in leads:
		if not frappe.db.exists("Opportunity", {"party_name": l.name}):
			opp = frappe.get_doc({
				"doctype": "Opportunity",
				"opportunity_from": "Lead",
				"party_name": l.name,
				"company": company,
				"status": "Open",
				"opportunity_type": "Sales",
				"transaction_date": add_days(today, -45).strftime("%Y-%m-%d"),
			})
			opp.insert(ignore_permissions=True)

	# 2. Quotations, Sales Orders, Delivery Notes, Sales Invoices & Payments (2026 current dates!)
	tax_template = f"In-State GST 18% (CGST 9% + SGST 9%) - {abbr}"

	selling_scenarios = [
		{"customer": customers[0].name, "item": "ST-CONS-01", "qty": 40, "rate": 2500.0, "offset": 40},
		{"customer": customers[1].name if len(customers) > 1 else customers[0].name, "item": "ST-DEV-01", "qty": 80, "rate": 2000.0, "offset": 25},
		{"customer": customers[2].name if len(customers) > 2 else customers[0].name, "item": "FG-CONTROL-PANEL", "qty": 2, "rate": 18500.0, "offset": 15},
		{"customer": customers[3].name if len(customers) > 3 else customers[0].name, "item": "ST-SUPPORT-01", "qty": 6, "rate": 50000.0, "offset": 5},
	]

	for sc in selling_scenarios:
		tx_date = add_days(today, -sc["offset"]).strftime("%Y-%m-%d")

		# Quotation
		qt = frappe.get_doc({
			"doctype": "Quotation",
			"company": company,
			"party_name": sc["customer"],
			"transaction_date": tx_date,
			"valid_till": add_days(getdate(tx_date), 30).strftime("%Y-%m-%d"),
			"items": [
				{
					"item_code": sc["item"],
					"qty": sc["qty"],
					"rate": sc["rate"],
					"amount": sc["qty"] * sc["rate"],
					"uom": frappe.db.get_value("Item", sc["item"], "stock_uom") or "Nos",
				}
			],
		})
		qt.flags.ignore_permissions = True
		qt.flags.ignore_mandatory = True
		qt.insert()
		qt.submit()

		# Sales Order
		so = frappe.get_doc({
			"doctype": "Sales Order",
			"company": company,
			"customer": sc["customer"],
			"transaction_date": tx_date,
			"delivery_date": add_days(getdate(tx_date), 14).strftime("%Y-%m-%d"),
			"items": [
				{
					"item_code": sc["item"],
					"qty": sc["qty"],
					"rate": sc["rate"],
					"amount": sc["qty"] * sc["rate"],
					"uom": frappe.db.get_value("Item", sc["item"], "stock_uom") or "Nos",
					"delivery_date": add_days(getdate(tx_date), 14).strftime("%Y-%m-%d"),
				}
			],
		})
		so.flags.ignore_permissions = True
		so.flags.ignore_mandatory = True
		so.insert()
		so.submit()

		# Delivery Note (for physical products)
		is_stock = frappe.db.get_value("Item", sc["item"], "is_stock_item")
		if is_stock:
			dn = frappe.get_doc({
				"doctype": "Delivery Note",
				"company": company,
				"customer": sc["customer"],
				"posting_date": add_days(getdate(tx_date), 5).strftime("%Y-%m-%d"),
				"items": [
					{
						"item_code": sc["item"],
						"qty": sc["qty"],
						"rate": sc["rate"],
						"against_sales_order": so.name,
						"so_detail": so.items[0].name,
						"warehouse": f"Finished Goods - {abbr}",
					}
				],
			})
			dn.flags.ignore_permissions = True
			dn.flags.ignore_mandatory = True
			try:
				dn.insert()
				dn.submit()
			except Exception:
				pass

		# Sales Invoice
		si = frappe.get_doc({
			"doctype": "Sales Invoice",
			"company": company,
			"customer": sc["customer"],
			"posting_date": add_days(getdate(tx_date), 7).strftime("%Y-%m-%d"),
			"due_date": add_days(getdate(tx_date), 37).strftime("%Y-%m-%d"),
			"taxes_and_charges": tax_template if frappe.db.exists("Sales Taxes and Charges Template", tax_template) else None,
			"debit_to": f"Debtors - {abbr}",
			"items": [
				{
					"item_code": sc["item"],
					"qty": sc["qty"],
					"rate": sc["rate"],
					"amount": sc["qty"] * sc["rate"],
					"sales_order": so.name,
					"so_detail": so.items[0].name,
					"income_account": f"Sales - {abbr}",
				}
			],
		})
		si.flags.ignore_permissions = True
		si.flags.ignore_mandatory = True
		try:
			si.insert()
			si.submit()

			# Payment Entry
			pe = frappe.get_doc({
				"doctype": "Payment Entry",
				"payment_type": "Receive",
				"company": company,
				"party_type": "Customer",
				"party": sc["customer"],
				"posting_date": add_days(getdate(tx_date), 10).strftime("%Y-%m-%d"),
				"paid_from": f"Debtors - {abbr}",
				"paid_to": f"HDFC Bank - {abbr}",
				"paid_amount": si.grand_total,
				"received_amount": si.grand_total,
				"target_exchange_rate": 1.0,
				"reference_no": f"NEFT-{si.name[-6:]}",
				"reference_date": add_days(getdate(tx_date), 10).strftime("%Y-%m-%d"),
				"references": [
					{
						"reference_doctype": "Sales Invoice",
						"reference_name": si.name,
						"total_amount": si.grand_total,
						"outstanding_amount": 0.0,
						"allocated_amount": si.grand_total,
					}
				],
			})
			pe.flags.ignore_permissions = True
			pe.flags.ignore_mandatory = True
			pe.insert()
			pe.submit()
		except Exception as e:
			frappe.log_error(title="Sales Invoice/Payment Creation Error", message=str(e))


def setup_support_and_hr(company):
	"""Setup client support issues and project tasks."""
	# 1. Support Issues
	issues = [
		{"subject": "API Rate Limiting on External ERPNext Webhook", "customer": "Apex Logistics Global Ltd", "priority": "High"},
		{"subject": "Invoice PDF Print Format alignment glitch", "customer": "Horizon Healthcare Network", "priority": "Medium"},
		{"subject": "Stock reconciliation discrepancy in Raw Materials", "customer": "Paramount Precision Forgings", "priority": "Low"},
	]
	for iss in issues:
		if not frappe.db.exists("Issue", {"subject": iss["subject"]}):
			doc = frappe.get_doc({
				"doctype": "Issue",
				"subject": iss["subject"],
				"customer": iss.get("customer"),
				"company": company,
				"priority": iss["priority"],
				"status": "Closed",
				"opening_date": "2026-10-15",
				"resolution_date": "2026-10-16",
			})
			doc.insert(ignore_permissions=True)
