// Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
// For license information, please see license.txt

frappe.ui.form.on("Supplier", {
	refresh: function (frm) {
		frm.trigger("render_custom_dashboard");
		frm.trigger("render_rating_status_indicator");
		frm.trigger("add_custom_actions");
	},

	render_custom_dashboard: function (frm) {
		if (frm.is_new()) return;

		frappe.call({
			method: "vendor_portal.api.get_vendor_dashboard",
			args: { supplier: frm.doc.name },
			callback: function (r) {
				if (!r.message) return;
				const d = r.message;

				const currency = frappe.defaults.get_default("currency") || "INR";
				const formatted_val = format_currency(d.total_po_value, currency);

				const stars = "★".repeat(Math.round(d.avg_rating || 0)) + "☆".repeat(Math.max(0, 5 - Math.round(d.avg_rating || 0)));

				const dashboard_html = `
					<div class="vendor-metrics-dashboard" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 16px;">
						<div class="metric-card" style="background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e5e7eb); border-radius: 8px; padding: 12px 16px; text-align: center; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
							<div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted, #6b7280); font-weight: 600;">${__("Total POs")}</div>
							<div style="font-size: 22px; font-weight: 700; color: var(--text-color, #111827); margin-top: 4px;">${d.total_pos}</div>
						</div>
						<div class="metric-card" style="background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e5e7eb); border-radius: 8px; padding: 12px 16px; text-align: center; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
							<div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted, #6b7280); font-weight: 600;">${__("Total PO Value")}</div>
							<div style="font-size: 18px; font-weight: 700; color: #10b981; margin-top: 4px;">${formatted_val}</div>
						</div>
						<div class="metric-card" style="background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e5e7eb); border-radius: 8px; padding: 12px 16px; text-align: center; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
							<div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted, #6b7280); font-weight: 600;">${__("Avg Rating")}</div>
							<div style="font-size: 20px; font-weight: 700; color: #f59e0b; margin-top: 4px;">${d.avg_rating} <span style="font-size: 14px;">${stars}</span></div>
						</div>
						<div class="metric-card" style="background: var(--card-bg, #ffffff); border: 1px solid var(--border-color, #e5e7eb); border-radius: 8px; padding: 12px 16px; text-align: center; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
							<div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted, #6b7280); font-weight: 600;">${__("Total Ratings")}</div>
							<div style="font-size: 22px; font-weight: 700; color: #6366f1; margin-top: 4px;">${d.total_rating_count}</div>
						</div>
					</div>
				`;

				// Render inside dashboard
				if ($("#supplier-vendor-dashboard").length === 0) {
					frm.dashboard.wrapper.prepend(
						`<div id="supplier-vendor-dashboard">${dashboard_html}</div>`
					);
				} else {
					$("#supplier-vendor-dashboard").html(dashboard_html);
				}
			},
		});
	},

	render_rating_status_indicator: function (frm) {
		if (frm.is_new()) return;

		// Fetch low rating threshold from Vendor Portal Settings
		frappe.db.get_single_value("Vendor Portal Settings", "low_rating_threshold").then((threshold) => {
			const min_thresh = parseFloat(threshold || 2.5);
			let rating = parseFloat(frm.doc.vendor_rating || 0);
			if (rating > 0 && rating <= 1.0) {
				rating = rating * 5.0;
			}

			if (frm.doc.is_blacklisted) {
				frm.dashboard.set_headline(
					__("Supplier is Blacklisted: {0}", [frm.doc.blacklist_reason || __("No reason provided")]),
					"red"
				);
			} else if (frm.doc.total_rating_count && rating < min_thresh) {
				frm.dashboard.set_headline(
					__("Low Rating — Review Required (Rating: {0}/5, Minimum: {1})", [rating, min_thresh]),
					"orange"
				);
			}
		});
	},

	add_custom_actions: function (frm) {
		if (frm.is_new()) return;

		const can_blacklist =
			frappe.user.has_role("Purchase Manager") ||
			frappe.user.has_role("Vendor Manager") ||
			frappe.user.has_role("System Manager");

		// 1. Blacklist Supplier Button
		if (can_blacklist) {
			if (!frm.doc.is_blacklisted) {
				frm.add_custom_button(
					__("Blacklist Supplier"),
					function () {
						frappe.prompt(
							[
								{
									fieldname: "reason",
									fieldtype: "Small Text",
									label: __("Reason for Blacklisting"),
									reqd: 1,
								},
							],
							function (values) {
								frm.set_value("is_blacklisted", 1);
								frm.set_value("blacklist_reason", values.reason);
								frm.save().then(() => {
									frappe.show_alert({
										message: __("Supplier has been blacklisted."),
										indicator: "red",
									});
								});
							},
							__("Confirm Blacklist Supplier"),
							__("Blacklist")
						);
					},
					__("Vendor Portal")
				);
			} else {
				frm.add_custom_button(
					__("Remove Blacklist"),
					function () {
						frappe.confirm(
							__("Are you sure you want to remove {0} from the blacklist?", [frm.doc.name]),
							function () {
								frm.set_value("is_blacklisted", 0);
								frm.set_value("blacklist_reason", "");
								frm.save().then(() => {
									frappe.show_alert({
										message: __("Supplier blacklist status removed."),
										indicator: "green",
									});
								});
							}
						);
					},
					__("Vendor Portal")
				);
			}
		}

		// 2. View Onboarding Button
		if (frm.doc.onboarding_reference) {
			frm.add_custom_button(
				__("View Onboarding"),
				function () {
					frappe.set_route("Form", "Vendor Onboarding", frm.doc.onboarding_reference);
				},
				__("Vendor Portal")
			);
		}
	},
});
