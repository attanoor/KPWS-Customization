frappe.pages["cash-report"].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Cash Report",
		single_column: true
	});

	// Append HTML content directly to page
	var html_content = `
		<div class="cash-report-container" style="padding: 20px;">
			<!-- Header -->
			<div class="report-header text-center" style="margin-bottom: 30px;">
				<h2 style="font-weight: bold; margin-bottom: 10px;">Kiran Patient Welfare Society</h2>
				<h3 style="margin-bottom: 10px;">Daily Pharmacy Sales</h3>
				<div style="margin-bottom: 20px;">
					<div><strong>Printed Time:</strong> <span id="printed-time"></span></div>
					<div><strong>Date:</strong> <span id="report-date"></span></div>
				</div>
			</div>

			<!-- Filters -->
			<div class="report-filters" style="margin-bottom: 20px; padding: 15px; background: #f5f5f5; border-radius: 5px;">
				<div class="row">
					<div class="col-sm-4">
						<div class="form-group">
							<label>Date From <span class="text-danger">*</span></label>
							<input type="date" class="form-control" id="date-from" required>
						</div>
					</div>
					<div class="col-sm-4">
						<div class="form-group">
							<label>Date To <span class="text-danger">*</span></label>
							<input type="date" class="form-control" id="date-to" required>
						</div>
					</div>
					<div class="col-sm-4">
						<div class="form-group">
							<label>User</label>
							<div id="user-filter"></div>
						</div>
					</div>
				</div>
				<div class="row">
					<div class="col-sm-12 text-right">
						<button class="btn btn-primary" id="generate-report">Generate Report</button>
						<button class="btn btn-default" id="print-report">Print</button>
					</div>
				</div>
			</div>

			<!-- Report Data -->
			<div id="report-content" style="display: none;">
				<!-- Sales Table -->
				<div class="sales-table-section" style="margin-bottom: 30px;">
					<h4 style="margin-bottom: 15px;">Sales</h4>
					<div class="table-responsive">
						<table class="table table-bordered table-striped" id="sales-table">
							<thead>
								<tr>
									<th>S.No</th>
									<th>POS Invoice Number</th>
									<th>Cash Payment</th>
									<th>Card Payment</th>
									<th>Bank / Ref No</th>
									<th>Patient Name</th>
									<th>Total</th>
									<th>MR Number</th>
									<th>KPWS Number</th>
								</tr>
							</thead>
							<tbody id="sales-table-body">
								<!-- Data will be populated here -->
							</tbody>
							<tfoot id="sales-table-footer">
								<!-- Totals will be populated here -->
							</tfoot>
						</table>
					</div>
				</div>

				<!-- Returns Table -->
				<div class="returns-table-section" style="margin-bottom: 30px;">
					<h4 style="margin-bottom: 15px;">Returns</h4>
					<div class="table-responsive">
						<table class="table table-bordered table-striped" id="returns-table">
							<thead>
								<tr>
									<th>S.No</th>
									<th>POS Invoice Number</th>
									<th>Cash Payment</th>
									<th>Card Payment</th>
									<th>Bank / Ref No</th>
									<th>Patient Name</th>
									<th>Total</th>
									<th>MR Number</th>
									<th>KPWS Number</th>
								</tr>
							</thead>
							<tbody id="returns-table-body">
								<!-- Data will be populated here -->
							</tbody>
						</table>
					</div>
				</div>

				<!-- Summary Totals -->
				<div class="summary-section" style="margin-top: 30px;">
					<h4 style="margin-bottom: 15px;">Summary</h4>
					<div class="table-responsive">
						<table class="table table-bordered" style="max-width: 500px;">
							<tbody>
								<tr>
									<td><strong>Total Sales</strong></td>
									<td class="text-right" id="total-sales">0.00</td>
								</tr>
								<tr>
									<td><strong>Cash Payment</strong></td>
									<td class="text-right" id="total-cash-payment">0.00</td>
								</tr>
								<tr>
									<td><strong>Card Payment</strong></td>
									<td class="text-right" id="total-card-payment">0.00</td>
								</tr>
								<tr>
									<td><strong>Sales Return</strong></td>
									<td class="text-right" id="total-sales-return">0.00</td>
								</tr>
								<tr class="bg-primary" style="color: white;">
									<td><strong>Cash Received</strong></td>
									<td class="text-right" id="cash-received"><strong>0.00</strong></td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>
			</div>

			<!-- Loading Indicator -->
			<div id="loading-indicator" style="display: none; text-align: center; padding: 40px;">
				<i class="fa fa-spinner fa-spin fa-3x"></i>
				<p>Loading report data...</p>
			</div>

			<!-- Error Message -->
			<div id="error-message" style="display: none; padding: 15px; background: #f8d7da; color: #721c24; border-radius: 5px; margin-top: 20px;">
				<!-- Error messages will be shown here -->
			</div>
		</div>
		<style>
			@media print {
				/* Hide all unnecessary elements */
				.report-filters, .btn, #generate-report, #print-report,
				.page-header, .page-actions, .page-title,
				.navbar, .sidebar, .footer, .breadcrumb,
				.page-form, .page-actions-row {
					display: none !important;
				}
				
				/* Page setup - Landscape for better table fit */
				@page {
					size: A4 landscape;
					margin: 0.5cm;
				}
				
				* {
					-webkit-print-color-adjust: exact !important;
					print-color-adjust: exact !important;
				}
				
				body {
					margin: 0 !important;
					padding: 0 !important;
					font-size: 9pt;
					background: white !important;
				}
				
				/* Main container */
				.cash-report-container {
					padding: 10px !important;
					margin: 0 !important;
					width: 100% !important;
					background: white !important;
				}
				
				/* Header styling */
				.report-header {
					margin-bottom: 15px !important;
					page-break-after: avoid;
					text-align: center;
				}
				
				.report-header h2 {
					font-size: 16pt !important;
					margin: 5px 0 !important;
					font-weight: bold;
				}
				
				.report-header h3 {
					font-size: 12pt !important;
					margin: 5px 0 !important;
				}
				
				.report-header div {
					font-size: 9pt !important;
					margin: 3px 0 !important;
				}
				
				/* Tables - Compact and clear */
				.table {
					font-size: 8pt !important;
					border-collapse: collapse !important;
					width: 100% !important;
					margin-bottom: 10px !important;
					page-break-inside: auto;
				}
				
				.table thead {
					display: table-header-group;
				}
				
				.table thead th {
					background-color: #e0e0e0 !important;
					border: 1px solid #000 !important;
					padding: 4px 3px !important;
					font-weight: bold !important;
					text-align: center !important;
					font-size: 8pt !important;
				}
				
				.table tbody td {
					border: 1px solid #000 !important;
					padding: 3px 2px !important;
					font-size: 8pt !important;
				}
				
				.table tfoot td {
					border: 1px solid #000 !important;
					padding: 4px 3px !important;
					font-weight: bold !important;
					background-color: #f0f0f0 !important;
					font-size: 8pt !important;
				}
				
				.table-striped tbody tr:nth-child(odd) {
					background-color: #f9f9f9 !important;
				}
				
				/* Section headers */
				.sales-table-section h4,
				.returns-table-section h4,
				.summary-section h4 {
					font-size: 11pt !important;
					font-weight: bold !important;
					margin: 10px 0 5px 0 !important;
					page-break-after: avoid;
				}
				
				/* Summary table */
				.summary-section .table {
					font-size: 9pt !important;
					max-width: 400px !important;
				}
				
				.summary-section .table td {
					padding: 5px 8px !important;
					font-size: 9pt !important;
				}
				
				.summary-section .table tr.bg-primary {
					background-color: #337ab7 !important;
					color: black !important;
				}
				
				/* Page breaks - allow tables to break but keep headers together */
				.sales-table-section {
					page-break-inside: auto;
				}
				
				.returns-table-section {
					page-break-inside: auto;
				}
				
				.summary-section {
					page-break-inside: avoid;
				}
				
				/* Table rows - allow breaking */
				.table tbody tr {
					page-break-inside: avoid;
				}
				
				/* Links */
				a {
					color: #000 !important;
					text-decoration: none !important;
				}
				
				/* Hide loading and error messages */
				#loading-indicator,
				#error-message {
					display: none !important;
				}
				
				/* Ensure report content is visible */
				#report-content {
					display: block !important;
				}
				
				/* Text alignment */
				.text-right {
					text-align: right !important;
				}
				
				.text-center {
					text-align: center !important;
				}
				
				/* Remove table-responsive wrapper effects */
				.table-responsive {
					overflow: visible !important;
				}
				
				/* Ensure proper spacing */
				.sales-table-section,
				.returns-table-section,
				.summary-section {
					margin-bottom: 15px !important;
				}
			}
			
			/* Screen styles */
			@media screen {
				.cash-report-container {
					padding: 20px;
				}
			}
		</style>
	`;
	
	$(html_content).appendTo(page.main);

	// Set current date as default
	var today = frappe.datetime.get_today();
	var date_from = frappe.datetime.add_days(today, -7); // Default to last 7 days
	
	// Initialize page - wait a bit for DOM to be ready
	setTimeout(function() {
		init_page(page);
	}, 100);
	
	function init_page(page) {
		// Set printed time and date
		update_printed_info();
		
		// Set default dates
		$("#date-from").val(date_from);
		$("#date-to").val(today);
		
		// Setup User field with autocomplete
		setup_user_field(page);
		
		// Generate report button
		$("#generate-report").on("click", function() {
			generate_report();
		});
		
		// Print button
		$("#print-report").on("click", function() {
			// Ensure report content is visible before printing
			if ($("#report-content").is(":hidden")) {
				frappe.show_alert({
					message: __("Please generate the report first"),
					indicator: "orange"
				});
				return;
			}
			
			// Trigger print
			setTimeout(function() {
				window.print();
			}, 100);
		});
		
		// Allow Enter key to generate report
		$("#date-from, #date-to, #user-filter").on("keypress", function(e) {
			if (e.which === 13) {
				generate_report();
			}
		});
	}
	
	function setup_user_field(page) {
		// Use page.add_field to create the User field properly
		// This will add it to the page form, then we'll move it
		page.user_field = page.add_field({
			fieldname: "user",
			label: "User",
			fieldtype: "Link",
			options: "User",
			placeholder: __("Optional")
		});
		
		// Move the field to our custom location
		var user_container = $("#user-filter").parent();
		$("#user-filter").remove();
		
		// Move the field wrapper to our container
		$(page.user_field.wrapper).detach().appendTo(user_container);
		
		// Remove the label since we have our own
		$(page.user_field.wrapper).find(".page-control-label").remove();
		
		// Make it full width
		$(page.user_field.wrapper).removeClass("col-md-2").addClass("col-md-12");
	}
	
	function update_printed_info() {
		var now = new Date();
		var time_str = now.toLocaleTimeString();
		var date_str = frappe.datetime.str_to_user(frappe.datetime.get_today());
		
		$("#printed-time").text(time_str);
		$("#report-date").text(date_str);
	}
	
	function generate_report() {
		// Validate filters
		var date_from = $("#date-from").val();
		var date_to = $("#date-to").val();
		var user = "";
		if (page.user_field && page.user_field.get_value) {
			user = page.user_field.get_value();
		} else if (page.user_field && page.user_field.value) {
			user = page.user_field.value;
		}
		
		if (!date_from || !date_to) {
			frappe.show_alert({
				message: __("Please select Date From and Date To"),
				indicator: "red"
			});
			return;
		}
		
		if (date_from > date_to) {
			frappe.show_alert({
				message: __("Date From cannot be greater than Date To"),
				indicator: "red"
			});
			return;
		}
		
		// Show loading
		$("#loading-indicator").show();
		$("#report-content").hide();
		$("#error-message").hide();
		
		// Prepare filters
		var filters = {
			date_from: date_from,
			date_to: date_to,
			user: user || null
		};
		
		// Call backend
		frappe.call({
			method: "kpws_customization.kpws_customization.page.cash_report.cash_report.get_cash_report_data",
			args: {
				filters: filters
			},
			callback: function(r) {
				$("#loading-indicator").hide();
				
				if (r.message) {
					if (r.exc) {
						show_error(r.exc);
					} else {
						render_report(r.message);
					}
				} else {
					show_error("No data returned from server");
				}
			},
			error: function(r) {
				$("#loading-indicator").hide();
				show_error(r.message || "Error loading report data");
			}
		});
	}
	
	function render_report(data) {
		// Update printed info
		update_printed_info();
		
		// Render sales table
		render_sales_table(data.data || []);
		
		// Render returns table
		render_returns_table(data.returns || []);
		
		// Render summary
		render_summary(data.totals || {});
		
		// Show report content
		$("#report-content").show();
	}
	
	function render_sales_table(data) {
		var tbody = $("#sales-table-body");
		var footer = $("#sales-table-footer");
		
		tbody.empty();
		footer.empty();
		
		if (data.length === 0) {
			tbody.append("<tr><td colspan='9' class='text-center'>No sales data found</td></tr>");
			return;
		}
		
		var total_cash = 0;
		var total_card = 0;
		var total_amount = 0;
		
		data.forEach(function(row) {
			var tr = $("<tr>");
			tr.append("<td>" + row.s_no + "</td>");
			tr.append("<td><a href='#Form/POS Invoice/" + row.pos_invoice + "'>" + row.pos_invoice + "</a></td>");
			tr.append("<td class='text-right'>" + format_currency(row.cash_payment) + "</td>");
			tr.append("<td class='text-right'>" + format_currency(row.card_payment) + "</td>");
			tr.append("<td>" + (row.bank_ref || "-") + "</td>");
			tr.append("<td>" + (row.patient_name || "-") + "</td>");
			tr.append("<td class='text-right'>" + format_currency(row.total) + "</td>");
			tr.append("<td>" + (row.custom_reference_number || "-") + "</td>");
			tr.append("<td>" + (row.kpws_number || "-") + "</td>");
			tbody.append(tr);
			
			total_cash += parseFloat(row.cash_payment || 0);
			total_card += parseFloat(row.card_payment || 0);
			total_amount += parseFloat(row.total || 0);
		});
		
		// Add footer totals
		var footer_tr = $("<tr class='bg-light'>");
		footer_tr.append("<td colspan='2'><strong>Total</strong></td>");
		footer_tr.append("<td class='text-right'><strong>" + format_currency(total_cash) + "</strong></td>");
		footer_tr.append("<td class='text-right'><strong>" + format_currency(total_card) + "</strong></td>");
		footer_tr.append("<td colspan='2'></td>");
		footer_tr.append("<td class='text-right'><strong>" + format_currency(total_amount) + "</strong></td>");
		footer_tr.append("<td colspan='2'></td>");
		footer.append(footer_tr);
	}
	
	function render_returns_table(data) {
		var tbody = $("#returns-table-body");
		
		tbody.empty();
		
		if (data.length === 0) {
			tbody.append("<tr><td colspan='9' class='text-center'>No returns found</td></tr>");
			return;
		}
		
		data.forEach(function(row) {
			var tr = $("<tr>");
			tr.append("<td>" + row.s_no + "</td>");
			tr.append("<td><a href='#Form/POS Invoice/" + row.pos_invoice + "'>" + row.pos_invoice + "</a></td>");
			tr.append("<td class='text-right'>" + format_currency(row.cash_payment) + "</td>");
			tr.append("<td class='text-right'>" + format_currency(row.card_payment) + "</td>");
			tr.append("<td>" + (row.bank_ref || "-") + "</td>");
			tr.append("<td>" + (row.patient_name || "-") + "</td>");
			tr.append("<td class='text-right'>" + format_currency(row.total) + "</td>");
			tr.append("<td>" + (row.custom_reference_number || "-") + "</td>");
			tr.append("<td>" + (row.kpws_number || "-") + "</td>");
			tbody.append(tr);
		});
	}
	
	function render_summary(totals) {
		$("#total-sales").html(format_currency(totals.total_sales || 0));
		$("#total-cash-payment").html(format_currency(totals.total_cash_payment || 0));
		$("#total-card-payment").html(format_currency(totals.total_card_payment || 0));
		$("#total-sales-return").html(format_currency(totals.total_sales_return || 0));
		
		// Ensure Cash Received is calculated and displayed
		var cash_received = totals.cash_received || 0;
		if (cash_received === 0 && totals.total_cash_payment) {
			// Fallback: use total_cash_payment if cash_received is 0
			cash_received = totals.total_cash_payment;
		}
		$("#cash-received").html("<strong>" + format_currency(cash_received) + "</strong>");
		
		// Make sure the row is visible
		$("#cash-received").closest("tr").show();
	}
	
	function format_currency(value) {
		if (!value) value = 0;
		return frappe.format(flt(value), {
			fieldtype: "Currency",
			precision: 2
		});
	}
	
	function show_error(message) {
		$("#error-message").html("<strong>Error:</strong> " + message).show();
		$("#report-content").hide();
	}
}

