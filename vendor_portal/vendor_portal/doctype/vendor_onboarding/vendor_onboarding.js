// Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
// For license information, please see license.txt

frappe.ui.form.on("Vendor Onboarding", {
	refresh: function (frm) {
		frm.trigger("render_document_progress");
		frm.trigger("add_approval_buttons");
	},

	vendor_category: function (frm) {
		if (frm.doc.vendor_category) {
			frappe.db.get_value(
				"Vendor Category",
				frm.doc.vendor_category,
				"minimum_rating_threshold",
				function (r) {
					if (r && r.minimum_rating_threshold !== undefined) {
						frm.set_df_property(
							"vendor_category",
							"description",
							__("Minimum Rating Threshold for {0}: <b>{1} ★</b>", [
								frm.doc.vendor_category,
								r.minimum_rating_threshold,
							])
						);
					}
				}
			);
		} else {
			frm.set_df_property("vendor_category", "description", "");
		}
	},

	validate: function (frm) {
		// Client-side GST validation for prompt UX feedback
		if (frm.doc.gst_number) {
			const gst = frm.doc.gst_number.trim().toUpperCase();
			const gstRegex = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/;
			if (!gstRegex.test(gst)) {
				frappe.msgprint(
					__(
						"Invalid GST Number format: <b>{0}</b>.<br>Expected 15 alphanumeric characters matching standard GST structure (e.g., 22AAAAA0000A1Z5).",
						[gst]
					)
				);
				frappe.validated = false;
				return;
			}
			frm.doc.gst_number = gst;
		}

		// Client-side PAN validation
		if (frm.doc.pan_number) {
			const pan = frm.doc.pan_number.trim().toUpperCase();
			const panRegex = /^[A-Z]{5}[0-9]{4}[A-Z]{1}$/;
			if (!panRegex.test(pan)) {
				frappe.msgprint(
					__("Invalid PAN Number format: <b>{0}</b>.<br>Expected 5 letters, 4 digits, 1 letter (e.g., ABCDE1234F).", [pan])
				);
				frappe.validated = false;
				return;
			}
			frm.doc.pan_number = pan;
		}
	},

	render_document_progress: function (frm) {
		const docs = frm.doc.documents || [];
		if (docs.length === 0) {
			return;
		}

		const total = docs.length;
		const verified = docs.filter((d) => d.is_verified).length;
		const percentage = Math.round((verified / total) * 100);

		const is_complete = verified === total;
		const color = is_complete ? "green" : "orange";

		frm.dashboard.set_headline(
			__("Verification Progress: <b>{0} of {1} documents verified</b> ({2}%)", [
				verified,
				total,
				percentage,
			]),
			color
		);
	},

	add_approval_buttons: function (frm) {
		// Visible when status = 'Under Review' to Purchase Manager / Vendor Manager / System Manager
		const can_review =
			frappe.user.has_role("Purchase Manager") ||
			frappe.user.has_role("Vendor Manager") ||
			frappe.user.has_role("System Manager");

		if (can_review && frm.doc.onboarding_status === "Under Review") {
			// 1. Approve Button
			frm.add_custom_button(
				__("Approve"),
				function () {
					frappe.confirm(
						__(
							"Are you sure you want to approve this vendor onboarding? An ERPNext Supplier record will be created automatically."
						),
						function () {
							frappe.call({
								method: "vendor_portal.api.approve_onboarding",
								args: { onboarding_name: frm.doc.name },
								freeze: true,
								freeze_message: __("Approving onboarding & provisioning supplier..."),
								callback: function (r) {
									if (r.message && r.message.status === "success") {
										frappe.show_alert({
											message: __("Onboarding Approved! Supplier {0} created.", [
												r.message.supplier,
											]),
											indicator: "green",
										});
										frm.reload_doc();
									}
								},
							});
						}
					);
				},
				__("Review")
			).addClass("btn-primary");

			// 2. Reject Button
			frm.add_custom_button(
				__("Reject"),
				function () {
					frappe.prompt(
						[
							{
								fieldname: "reason",
								fieldtype: "Small Text",
								label: __("Rejection Reason"),
								reqd: 1,
							},
						],
						function (values) {
							frappe.call({
								method: "vendor_portal.api.reject_onboarding",
								args: {
									onboarding_name: frm.doc.name,
									reason: values.reason,
								},
								freeze: true,
								freeze_message: __("Rejecting onboarding..."),
								callback: function (r) {
									if (r.message && r.message.status === "success") {
										frappe.show_alert({
											message: __("Onboarding has been rejected."),
											indicator: "red",
										});
										frm.reload_doc();
									}
								},
							});
						},
						__("Reject Vendor Onboarding"),
						__("Reject")
					);
				},
				__("Review")
			).addClass("btn-danger");
		}
	},
});

// Update progress indicator on child table edits
frappe.ui.form.on("Vendor Document", {
	is_verified: function (frm) {
		frm.trigger("render_document_progress");
	},
	documents_remove: function (frm) {
		frm.trigger("render_document_progress");
	},
});
