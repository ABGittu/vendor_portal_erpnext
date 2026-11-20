// Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Order", {
	refresh: function (frm) {
		frm.trigger("render_supplier_headline");
		frm.trigger("add_rating_actions");
	},

	supplier: function (frm) {
		frm.trigger("render_supplier_headline");
	},

	render_supplier_headline: function (frm) {
		if (!frm.doc.supplier) {
			frm.dashboard.clear_headline();
			frm.enable_save();
			return;
		}

		frappe.db.get_value(
			"Supplier",
			frm.doc.supplier,
			[
				"vendor_rating",
				"vendor_category",
				"total_rating_count",
				"is_blacklisted",
				"blacklist_reason",
			],
			function (r) {
				if (!r) return;

				if (r.is_blacklisted) {
					const reason = r.blacklist_reason || __("No reason provided");
					frm.dashboard.set_headline(
						__("WARNING: This supplier is blacklisted! Reason: {0}", [reason]),
						"red"
					);
					frm.disable_save();
				} else {
					frm.enable_save();
					let rating = parseFloat(r.vendor_rating || 0);
					// Adjust for normalized 0-1 scale if present
					if (rating > 0 && rating <= 1.0) {
						rating = rating * 5.0;
					}
					rating = Math.round(rating * 10) / 10;

					const category = r.vendor_category || __("Uncategorized");
					const count = r.total_rating_count || 0;
					frm.dashboard.set_headline(
						__(
							"Vendor Category: <b>{0}</b> &nbsp;|&nbsp; Avg Rating: <b>{1}/5 ★</b> ({2} ratings)",
							[category, rating, count]
						),
						rating >= 3.0 ? "blue" : "orange"
					);
				}
			}
		);
	},

	add_rating_actions: function (frm) {
		if (!frm.doc.supplier) return;

		// 1. "View Vendor Rating History" in Actions Menu
		frm.page.add_action_item(__("View Vendor Rating History"), function () {
			frappe.call({
				method: "vendor_portal.api.get_vendor_rating_history",
				args: { supplier: frm.doc.supplier },
				callback: function (r) {
					const ratings = r.message || [];
					let table_rows = "";

					if (ratings.length === 0) {
						table_rows = `<tr><td colspan="4" class="text-muted text-center py-3">${__(
							"No rating records found for this supplier."
						)}</td></tr>`;
					} else {
						ratings.forEach((row) => {
							const stars = "★".repeat(Math.round(row.score || 0)) + "☆".repeat(Math.max(0, 5 - Math.round(row.score || 0)));
							table_rows += `
								<tr>
									<td>${row.rating_date || ""}</td>
									<td><span class="badge badge-info">${row.rating_type}</span></td>
									<td><span style="color: #f59e0b; font-weight: bold;">${stars}</span> (${row.score})</td>
									<td><small class="text-muted">${frappe.utils.escape_html(row.remarks || "-")}</small></td>
								</tr>
							`;
						});
					}

					const html = `
						<div class="table-responsive">
							<table class="table table-bordered table-striped" style="margin-bottom: 0;">
								<thead class="thead-light">
									<tr>
										<th style="width: 20%;">${__("Date")}</th>
										<th style="width: 25%;">${__("Rating Type")}</th>
										<th style="width: 25%;">${__("Score")}</th>
										<th style="width: 30%;">${__("Remarks")}</th>
									</tr>
								</thead>
								<tbody>
									${table_rows}
								</tbody>
							</table>
						</div>
					`;

					const dialog = new frappe.ui.Dialog({
						title: __("Vendor Rating History: {0}", [frm.doc.supplier]),
						size: "large",
						fields: [{ fieldtype: "HTML", fieldname: "history_html", options: html }],
						primary_action_label: __("Close"),
						primary_action: function () {
							dialog.hide();
						},
					});
					dialog.show();
				},
			});
		});

		// 2. "Rate This Supplier" custom button visible after submission
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(
				__("Rate This Supplier"),
				function () {
					const dialog = new frappe.ui.Dialog({
						title: __("Rate Supplier: {0}", [frm.doc.supplier]),
						fields: [
							{
								fieldname: "rating_type",
								label: __("Rating Type"),
								fieldtype: "Select",
								options: "\nDelivery\nQuality\nPricing\nCommunication",
								reqd: 1,
								default: "Quality",
							},
							{
								fieldname: "score",
								label: __("Score (1 to 5)"),
								fieldtype: "Rating",
								reqd: 1,
							},
							{
								fieldname: "remarks",
								label: __("Remarks / Feedback"),
								fieldtype: "Small Text",
							},
						],
						primary_action_label: __("Submit Rating"),
						primary_action: function (values) {
							if (!values.rating_type) {
								frappe.msgprint(__("Please select a rating type."));
								return;
							}

							let raw_score = parseFloat(values.score || 0);
							// Convert Rating field value (0-1 fraction) to 1-5 scale if needed
							let final_score = (raw_score > 0 && raw_score <= 1.0) ? (raw_score * 5.0) : raw_score;
							if (final_score < 1.0) final_score = 1.0;

							frappe.call({
								method: "vendor_portal.api.submit_vendor_rating",
								args: {
									supplier: frm.doc.supplier,
									rating_type: values.rating_type,
									score: final_score,
									remarks: values.remarks,
									purchase_order: frm.doc.name,
								},
								freeze: true,
								freeze_message: __("Recording rating..."),
								callback: function (r) {
									if (r.message && r.message.status === "success") {
										frappe.show_alert({
											message: __("Supplier rated successfully! New rating: {0}/5", [
												r.message.vendor_rating,
											]),
											indicator: "green",
										});
										dialog.hide();
										frm.reload_doc();
									}
								},
							});
						},
					});
					dialog.show();
				},
				__("Actions")
			);
		}

		// Bonus Task 5: Add "Compare Suppliers" button in Actions
		frm.page.add_action_item(__("Compare Suppliers"), function () {
			let item_code = null;
			let qty = 1;
			if (frm.doc.items && frm.doc.items.length > 0) {
				item_code = frm.doc.items[0].item_code;
				qty = frm.doc.items[0].qty || 1;
			}
			if (window.vendor_portal && window.vendor_portal.show_vendor_comparison_dialog) {
				window.vendor_portal.show_vendor_comparison_dialog(item_code, qty, frm);
			}
		});
	},
});
