// Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
// For license information, please see license.txt

frappe.pages['vendor_dashboard'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Vendor Analytics Dashboard'),
		single_column: true
	});

	page.set_secondary_action(__('Refresh'), function() {
		load_dashboard_data(page);
	}, 'fa fa-refresh');

	page.add_inner_button(__('Compare Suppliers'), function() {
		if (window.vendor_portal && window.vendor_portal.show_vendor_comparison_dialog) {
			window.vendor_portal.show_vendor_comparison_dialog();
		} else {
			show_comparison_dialog();
		}
	});

	page.add_inner_button(__('Bulk Import'), function() {
		show_bulk_import_dialog();
	});

	// Render layout
	var $container = $(`
		<div class="vendor-dashboard-content p-3">
			<!-- KPI Row -->
			<div class="row g-3 mb-4" id="kpi-cards-row">
				<div class="col-md-3">
					<div class="card shadow-sm border-0 bg-light p-3">
						<span class="text-muted small text-uppercase font-weight-bold">${__('Active Vendors')}</span>
						<h2 class="mt-2 mb-0 font-weight-bold text-primary" id="kpi-total-vendors">-</h2>
					</div>
				</div>
				<div class="col-md-3">
					<div class="card shadow-sm border-0 bg-light p-3">
						<span class="text-muted small text-uppercase font-weight-bold">${__('Avg Vendor Rating')}</span>
						<h2 class="mt-2 mb-0 font-weight-bold text-warning" id="kpi-avg-rating">-</h2>
					</div>
				</div>
				<div class="col-md-3">
					<div class="card shadow-sm border-0 bg-light p-3">
						<span class="text-muted small text-uppercase font-weight-bold">${__('Pending Onboardings')}</span>
						<h2 class="mt-2 mb-0 font-weight-bold text-info" id="kpi-pending-onboardings">-</h2>
					</div>
				</div>
				<div class="col-md-3">
					<div class="card shadow-sm border-0 bg-light p-3">
						<span class="text-muted small text-uppercase font-weight-bold">${__('Total PO Spend')}</span>
						<h2 class="mt-2 mb-0 font-weight-bold text-success" id="kpi-total-spend">-</h2>
					</div>
				</div>
			</div>

			<!-- Charts Grid (2x2) -->
			<div class="row g-4">
				<div class="col-md-6 mb-4">
					<div class="card shadow-sm border-0 h-100">
						<div class="card-header bg-white font-weight-bold border-bottom">
							<i class="fa fa-star text-warning mr-1"></i> ${__('Vendor Rating Distribution (Histogram)')}
						</div>
						<div class="card-body">
							<div id="chart-rating-distribution" style="height: 280px;"></div>
						</div>
					</div>
				</div>

				<div class="col-md-6 mb-4">
					<div class="card shadow-sm border-0 h-100">
						<div class="card-header bg-white font-weight-bold border-bottom">
							<i class="fa fa-filter text-info mr-1"></i> ${__('Onboarding Pipeline (Funnel)')}
						</div>
						<div class="card-body">
							<div id="chart-onboarding-pipeline" style="height: 280px;"></div>
						</div>
					</div>
				</div>

				<div class="col-md-6 mb-4">
					<div class="card shadow-sm border-0 h-100">
						<div class="card-header bg-white font-weight-bold border-bottom">
							<i class="fa fa-bar-chart text-primary mr-1"></i> ${__('PO Volume by Vendor Category')}
						</div>
						<div class="card-body">
							<div id="chart-po-category" style="height: 280px;"></div>
						</div>
					</div>
				</div>

				<div class="col-md-6 mb-4">
					<div class="card shadow-sm border-0 h-100">
						<div class="card-header bg-white font-weight-bold border-bottom">
							<i class="fa fa-line-chart text-success mr-1"></i> ${__('Delivery Performance Trend (Past 6 Months)')}
						</div>
						<div class="card-body">
							<div id="chart-delivery-trend" style="height: 280px;"></div>
						</div>
					</div>
				</div>
			</div>
		</div>
	`).appendTo(page.main);

	load_dashboard_data(page);
};

function load_dashboard_data(page) {
	frappe.call({
		method: 'vendor_portal.vendor_portal.page.vendor_dashboard.vendor_dashboard.get_dashboard_data',
		freeze: true,
		freeze_message: __('Loading Analytics Dashboard...'),
		callback: function(r) {
			if (!r.message) return;
			var data = r.message;

			// Populate KPIs
			$('#kpi-total-vendors').text(data.kpis.total_vendors || 0);
			$('#kpi-avg-rating').text((data.kpis.avg_rating || 0).toFixed(1) + ' ★');
			$('#kpi-pending-onboardings').text(data.kpis.pending_onboardings || 0);
			$('#kpi-total-spend').text(format_currency(data.kpis.total_spend || 0));

			// Chart 1: Rating Distribution (Bar / Histogram)
			new frappe.Chart('#chart-rating-distribution', {
				title: __('Suppliers by Rating Bracket'),
				data: data.rating_distribution,
				type: 'bar',
				height: 260,
				colors: ['#ffc107', '#fd7e14', '#20c997', '#0d6efd', '#6610f2']
			});

			// Chart 2: Onboarding Pipeline (Bar / Funnel)
			new frappe.Chart('#chart-onboarding-pipeline', {
				title: __('Applications per Lifecycle Stage'),
				data: data.onboarding_pipeline,
				type: 'bar',
				height: 260,
				colors: ['#6c757d', '#0dcaf0', '#198754', '#dc3545']
			});

			// Chart 3: PO Volume by Category
			new frappe.Chart('#chart-po-category', {
				title: __('Spend Distribution across Vendor Categories'),
				data: data.po_volume_by_category,
				type: 'bar',
				height: 260,
				colors: ['#0d6efd']
			});

			// Chart 4: Delivery Performance Trend (Line)
			new frappe.Chart('#chart-delivery-trend', {
				title: __('Monthly Average On-Time Delivery %'),
				data: data.delivery_trend,
				type: 'line',
				height: 260,
				colors: ['#198754'],
				lineOptions: {
					regionFill: 1,
					dotSize: 5
				}
			});
		}
	});
}

function show_comparison_dialog() {
	if (window.vendor_portal && window.vendor_portal.show_vendor_comparison_dialog) {
		window.vendor_portal.show_vendor_comparison_dialog();
	}
}

function show_bulk_import_dialog() {
	var d = new frappe.ui.Dialog({
		title: __('Bulk Vendor Import'),
		fields: [
			{
				label: __('Upload CSV File'),
				fieldname: 'csv_file',
				fieldtype: 'Attach',
				description: __('Upload a CSV file containing columns: supplier_name, email, phone, vendor_category, gst_number, pan_number, address_line_1, city, state, pincode')
			},
			{
				label: __('Or Paste Raw CSV Data'),
				fieldname: 'csv_text',
				fieldtype: 'Code',
				description: __('Header row required: supplier_name,email,phone,vendor_category,gst_number')
			}
		],
		primary_action_label: __('Process Import'),
		primary_action: function(values) {
			if (!values.csv_file && !values.csv_text) {
				frappe.msgprint(__('Please attach a CSV file or paste raw CSV text.'));
				return;
			}
			d.hide();
			frappe.call({
				method: 'vendor_portal.api.bulk_vendor_import',
				args: {
					file_url: values.csv_file,
					csv_content: values.csv_text,
					async_mode: 0
				},
				freeze: true,
				freeze_message: __('Importing vendors...'),
				callback: function(r) {
					if (r.message) {
						frappe.msgprint({
							title: __('Bulk Import Result'),
							message: __('Processed: {0} records, Created: {1}, Errors: {2}', [
								r.message.total_rows,
								r.message.created_count,
								r.message.errors ? r.message.errors.length : 0
							]),
							indicator: 'green'
						});
					}
				}
			});
		}
	});
	d.show();
}
