// Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
// For license information, please see license.txt

/**
 * Global Vendor Portal Client Customizations
 * - Task 2.2 A: Purchase Order List View override (indicators & Quick Rate Supplier action)
 * - Task 2.1 A: Purchase Order List View columns (supplier_name, grand_total, per_received, status)
 * - Task 2.2 B: Purchase Invoice low vendor rating banner
 */

// 1. Purchase Order List View Enhancements (Task 2.1 A & Task 2.2 A)
frappe.listview_settings["Purchase Order"] = frappe.listview_settings["Purchase Order"] || {};

// Extend fields fetched for Purchase Order list view
frappe.listview_settings["Purchase Order"].add_fields = [
	...(frappe.listview_settings["Purchase Order"].add_fields || []),
	"supplier_name",
	"grand_total",
	"per_received",
	"status",
	"schedule_date",
	"supplier",
];

// Custom Indicators: Green = Completed, Orange = To Receive, Red = Overdue
const original_po_indicator = frappe.listview_settings["Purchase Order"].get_indicator;
frappe.listview_settings["Purchase Order"].get_indicator = function (doc) {
	const today = frappe.datetime.get_today();
	const per_received = parseFloat(doc.per_received || 0);

	// Green = Completed
	if (doc.status === "Completed" || per_received >= 100) {
		return [__("Completed"), "green", "status,=,Completed"];
	}

	// Red = Overdue (schedule_date has passed but per_received < 100)
	if (doc.schedule_date && frappe.datetime.get_diff(today, doc.schedule_date) > 0 && per_received < 100) {
		return [__("Overdue"), "red", "status,=,To Receive and Bill"];
	}

	// Orange = To Receive
	if (
		doc.status === "To Receive and Bill" ||
		doc.status === "To Receive" ||
		per_received < 100
	) {
		return [__("To Receive"), "orange", "status,=,To Receive"];
	}

	if (original_po_indicator) {
		return original_po_indicator(doc);
	}
	return [__(doc.status), "blue", "status,=," + doc.status];
};

// Add "Quick Rate Supplier" in list view (both as an action item and context menu)
const original_po_onload = frappe.listview_settings["Purchase Order"].onload;
frappe.listview_settings["Purchase Order"].onload = function (listview) {
	if (original_po_onload) {
		original_po_onload(listview);
	}

	// Add listview action item
	listview.page.add_action_item(__("Quick Rate Supplier"), function () {
		const checked_items = listview.get_checked_items();
		if (!checked_items || checked_items.length === 0) {
			frappe.msgprint(__("Please select at least one Purchase Order to rate its supplier."));
			return;
		}

		const po_doc = checked_items[0];
		const supplier = po_doc.supplier;
		if (!supplier) {
			frappe.msgprint(__("Selected Purchase Order has no linked supplier."));
			return;
		}

		open_quick_rate_dialog(supplier, po_doc.name, function () {
			listview.refresh();
		});
	});

	// Context menu (right-click) support on list rows
	if (listview.$result) {
		listview.$result.off("contextmenu", ".list-row");
		listview.$result.on("contextmenu", ".list-row", function (e) {
			e.preventDefault();
			const $row = $(this);
			const docname = $row.attr("data-name");
			if (!docname) return;

			const doc = listview.data.find((d) => d.name === docname);
			if (!doc || !doc.supplier) return;

			// Show right-click contextual menu or launch Quick Rate dialog directly
			frappe.ui.form.make_quick_entry
				? open_quick_rate_dialog(doc.supplier, doc.name, function () {
						listview.refresh();
				  })
				: null;
		});
	}
};

/**
 * Reusable Quick Rate Dialog for Supplier
 */
function open_quick_rate_dialog(supplier, purchase_order, on_success) {
	const dialog = new frappe.ui.Dialog({
		title: __("Quick Rate Supplier: {0}", [supplier]),
		fields: [
			{
				fieldname: "rating_type",
				label: __("Rating Type"),
				fieldtype: "Select",
				options: "\nDelivery\nQuality\nPricing\nCommunication",
				default: "Quality",
				reqd: 1,
			},
			{
				fieldname: "score",
				label: __("Score (1 to 5 Stars)"),
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
			// Convert fraction to 1-5 scale if Rating field returned 0-1
			let final_score = raw_score > 0 && raw_score <= 1.0 ? raw_score * 5.0 : raw_score;
			if (final_score < 1.0) final_score = 1.0;

			frappe.call({
				method: "vendor_portal.api.submit_vendor_rating",
				args: {
					supplier: supplier,
					rating_type: values.rating_type,
					score: final_score,
					remarks: values.remarks,
					purchase_order: purchase_order || null,
				},
				freeze: true,
				freeze_message: __("Recording rating..."),
				callback: function (r) {
					if (r.message && r.message.status === "success") {
						frappe.show_alert({
							message: __("Supplier rated successfully! New rating: {0}/5 ★", [
								r.message.vendor_rating,
							]),
							indicator: "green",
						});
						dialog.hide();
						if (on_success) on_success(r.message);
					}
				},
			});
		},
	});
	dialog.show();
}

// 2. Purchase Invoice Form Override (Task 2.2 B)
// Hook into Purchase Invoice refresh event via app_include_js
frappe.ui.form.on("Purchase Invoice", {
	refresh: function (frm) {
		if (!frm.doc.supplier) {
			frm.dashboard.clear_headline();
			return;
		}

		frappe.db.get_value(
			"Supplier",
			frm.doc.supplier,
			["vendor_rating", "supplier_name"],
			function (r) {
				if (!r) return;

				let rating = parseFloat(r.vendor_rating || 0);
				if (rating > 0 && rating <= 1.0) {
					rating = rating * 5.0;
				}
				rating = Math.round(rating * 10) / 10;

				// If vendor_rating < 3, add comment-style banner
				if (rating > 0 && rating < 3.0) {
					const banner_text = __(
						"Note: This supplier has a low vendor rating ({0}/5). Consider reviewing vendor performance.",
						[rating]
					);
					frm.dashboard.set_headline(
						`<div class="vendor-low-rating-note" style="display: flex; align-items: center; gap: 8px;">
							<span style="font-size: 16px;">⚠️</span>
							<span><b>${__("Vendor Advisory:")}</b> ${banner_text}</span>
						</div>`,
						"orange"
					);
				}
			}
		);
	},

	supplier: function (frm) {
		frm.trigger("refresh");
	},
});

// 3. Bonus Task 5: Vendor Comparison Matrix Interactive Dialog
window.vendor_portal = window.vendor_portal || {};
window.vendor_portal.show_vendor_comparison_dialog = function (initial_item, initial_qty, target_frm) {
	let dialog = new frappe.ui.Dialog({
		title: __("Vendor Comparison Matrix"),
		size: "large",
		fields: [
			{
				label: __("Select Item"),
				fieldname: "item_code",
				fieldtype: "Link",
				options: "Item",
				default: initial_item || null,
				reqd: 1,
				onchange: function () {
					load_matrix();
				},
			},
			{
				label: __("Required Quantity"),
				fieldname: "qty",
				fieldtype: "Float",
				default: initial_qty || 1,
				onchange: function () {
					load_matrix();
				},
			},
			{
				fieldtype: "Section Break",
			},
			{
				fieldname: "matrix_html",
				fieldtype: "HTML",
			},
		],
		primary_action_label: __("Refresh Comparison"),
		primary_action: function () {
			load_matrix();
		},
	});

	function load_matrix() {
		const item_code = dialog.get_value("item_code");
		const qty = parseFloat(dialog.get_value("qty") || 1);
		const $wrapper = dialog.get_field("matrix_html").$wrapper;

		if (!item_code) {
			$wrapper.html(`<div class="alert alert-info text-center my-3">${__("Please select an item to view supplier comparison.")}</div>`);
			return;
		}

		$wrapper.html(`<div class="text-center py-4 text-muted"><i class="fa fa-spinner fa-spin fa-2x"></i><p class="mt-2">${__("Fetching supplier comparative analysis...")}</p></div>`);

		frappe.call({
			method: "vendor_portal.api.get_supplier_comparison",
			args: {
				item_code: item_code,
				qty: qty,
			},
			callback: function (r) {
				const suppliers = r.message || [];
				if (suppliers.length === 0) {
					$wrapper.html(`
						<div class="alert alert-warning text-center my-3">
							<i class="fa fa-info-circle mr-1"></i> ${__("No active suppliers or purchase history found for item:")} <b>${frappe.utils.escape_html(item_code)}</b>
						</div>
					`);
					return;
				}

				let rows_html = "";
				suppliers.forEach(function (sup) {
					const rating = parseFloat(sup.vendor_rating || 0);
					const star_count = Math.min(5, Math.max(0, Math.round(rating)));
					const stars = "★".repeat(star_count) + "☆".repeat(5 - star_count);
					const deliv = parseFloat(sup.on_time_delivery_rate || 0);
					const deliv_color = deliv >= 90 ? "success" : deliv >= 75 ? "warning" : "danger";

					// Format pricing history
					let price_history_pills = "-";
					if (sup.pricing_history && sup.pricing_history.length > 0) {
						price_history_pills = sup.pricing_history
							.map(function (ph) {
								return `<span class="badge badge-light border mr-1" title="${ph.date}">₹${ph.rate}</span>`;
							})
							.join("");
					}

					let action_btn = "";
					if (target_frm) {
						action_btn = `<button class="btn btn-xs btn-primary btn-select-supplier" data-supplier="${frappe.utils.escape_html(sup.supplier)}">
							<i class="fa fa-check mr-1"></i> ${__("Select")}
						</button>`;
					}

					rows_html += `
						<tr>
							<td>
								<strong><a href="/app/supplier/${encodeURIComponent(sup.supplier)}" target="_blank">${frappe.utils.escape_html(sup.supplier_name)}</a></strong>
								<br><small class="text-muted font-monospace">${frappe.utils.escape_html(sup.supplier)}</small>
							</td>
							<td>
								<span style="color: #f59e0b; font-size: 15px; font-weight: bold;">${stars}</span>
								<small class="text-muted d-block">${rating.toFixed(1)} / 5.0</small>
							</td>
							<td>
								<span class="badge badge-${deliv_color} bg-${deliv_color} text-white px-2 py-1">${deliv.toFixed(1)}%</span>
							</td>
							<td>
								<strong class="text-dark">₹${(sup.last_rate || 0).toFixed(2)}</strong>
							</td>
							<td>
								${price_history_pills}
							</td>
							<td>
								<strong class="text-primary font-weight-bold">₹${(sup.estimated_total || 0).toFixed(2)}</strong>
							</td>
							${target_frm ? `<td>${action_btn}</td>` : ""}
						</tr>
					`;
				});

				const html = `
					<div class="table-responsive mt-3">
						<table class="table table-bordered table-hover align-middle">
							<thead class="thead-light bg-light">
								<tr>
									<th>${__("Supplier")}</th>
									<th style="width: 15%;">${__("Rating")}</th>
									<th style="width: 15%;">${__("Delivery Score")}</th>
									<th style="width: 15%;">${__("Last Rate")}</th>
									<th>${__("Recent Pricing History")}</th>
									<th style="width: 15%;">${__("Estimated Total")}</th>
									${target_frm ? `<th style="width: 10%;">${__("Action")}</th>` : ""}
								</tr>
							</thead>
							<tbody>
								${rows_html}
							</tbody>
						</table>
					</div>
				`;

				$wrapper.html(html);

				if (target_frm) {
					$wrapper.find(".btn-select-supplier").on("click", function () {
						const selected_sup = $(this).attr("data-supplier");
						target_frm.set_value("supplier", selected_sup);
						dialog.hide();
						frappe.show_alert({
							message: __("Supplier set to {0}", [selected_sup]),
							indicator: "green",
						});
					});
				}
			},
		});
	}

	dialog.show();
	if (initial_item) {
		load_matrix();
	}
};
