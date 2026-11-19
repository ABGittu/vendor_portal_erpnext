// Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
// For license information, please see license.txt

frappe.query_reports["Vendor Performance Report"] = {
	filters: [
		{
			fieldname: "vendor_category",
			label: __("Vendor Category"),
			fieldtype: "Link",
			options: "Vendor Category",
		},
		{
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "Link",
			options: "Supplier",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -3),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "minimum_rating",
			label: __("Minimum Rating"),
			fieldtype: "Float",
		},
	],
};
