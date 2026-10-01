frappe.pages["panel-report"].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Panel Report",
		single_column: true
	});

	// Append HTML content directly to page
	var html_content = `
		<div class="panel-report-container" style="padding: 20px;">
			<!-- Header -->
			<div class="report-header text-center" style="margin-bottom: 30px;">
				<h2 style="font-weight: bold; margin-bottom: 10px;">Kiran Patient Welfare Society</h2>
				<h3 style="margin-bottom: 10px;">Panel Report</h3>
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
				<div id="customers-container">
					<!-- Customer sections will be populated here -->
				</div>

				<!-- Returns Section -->
				<div id="returns-container" style="margin-top: 30px;">
					<!-- Returns sections will be populated here -->
				</div>

				<!-- Grand Total -->
				<div class="grand-total-section" style="margin-top: 30px;">
					<div class="table-responsive">
						<table class="table table-bordered" style="max-width: 500px; margin-left: auto;">
							<tbody>
								<tr class="bg-primary" style="color: black;">
									<td><strong>Total Credit</strong></td>
									<td class="text-right" id="total-credit"><strong>0.00</strong></td>
								</tr>
								<tr class="bg-danger" style="color: black;">
									<td><strong>Total Returns</strong></td>
									<td class="text-right" id="total-returns"><strong>0.00</strong></td>
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
				
				/* Page setup */
				@page {
					size: A4 portrait;
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
				.panel-report-container {
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
				
				/* Customer section */
				.customer-section {
					margin-bottom: 25px !important;
					page-break-inside: avoid;
				}
				
				.customer-section h4 {
					font-size: 12pt !important;
					font-weight: bold !important;
					margin: 10px 0 8px 0 !important;
					page-break-after: avoid;
				}
				
				/* Tables */
				.table {
					font-size: 8pt !important;
					border-collapse: collapse !important;
					width: 100% !important;
					margin-bottom: 15px !important;
					page-break-inside: auto;
				}
				
				.table thead {
					display: table-header-group;
				}
				
				.table thead th {
					background-color: #e0e0e0 !important;
					border: 1px solid #000 !important;
					padding: 4px !important;
					font-weight: bold !important;
					text-align: center !important;
					font-size: 8pt !important;
				}
				
				.table tbody td {
					border: 1px solid #000 !important;
					padding: 3px !important;
					vertical-align: top;
				}
				
				.table tbody tr.bg-light td {
					background-color: #f0f0f0 !important;
					font-weight: bold;
					border: 1px solid #000 !important;
				}
				
				.table-striped tbody tr:nth-child(odd) {
					background-color: #f5f5f5 !important;
				}
				
				/* Grand total */
				.grand-total-section .table {
					font-size: 9pt !important;
					max-width: 350px !important;
				}
				
				.grand-total-section .table td {
					padding: 5px 8px !important;
					font-size: 9pt !important;
				}
				
				.grand-total-section .table tr.bg-primary {
					background-color: #337ab7 !important;
					color: black !important;
				}
				
				.grand-total-section .table tr.bg-danger {
					background-color: #d9534f !important;
					color: black !important;
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
			}
		</style>
	`;
	$(page.main).html(html_content);

	// Initialize page
	init_page();

	function init_page() {
		// Set default dates
		var today = new Date();
		var firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
		$("#date-from").val(formatDate(firstDay));
		$("#date-to").val(formatDate(today));

		// Setup user field
		setup_user_field();

		// Update printed info
		update_printed_info();

		// Event handlers
		$("#generate-report").on("click", generate_report);
		$("#print-report").on("click", function() {
			if ($("#report-content").is(":visible")) {
				window.print();
			} else {
				frappe.msgprint("Please generate the report first.");
			}
		});
	}

	function setup_user_field() {
		page.add_field({
			fieldtype: "Link",
			fieldname: "user",
			options: "User",
			label: "User",
			change: function() {
				// User selection changed
			}
		});

		// Move the field to our custom location
		setTimeout(function() {
			var field = page.fields_dict.user.$wrapper;
			$("#user-filter").html(field);
		}, 100);
	}

	function update_printed_info() {
		var now = new Date();
		$("#printed-time").text(now.toLocaleString());
		var dateFrom = $("#date-from").val();
		var dateTo = $("#date-to").val();
		if (dateFrom && dateTo) {
			$("#report-date").text(dateFrom + " to " + dateTo);
		}
	}

	function generate_report() {
		var dateFrom = $("#date-from").val();
		var dateTo = $("#date-to").val();
		var user = page.fields_dict.user ? page.fields_dict.user.get_value() : "";

		if (!dateFrom || !dateTo) {
			show_error("Date From and Date To are mandatory");
			return;
		}

		$("#error-message").hide();
		$("#loading-indicator").show();
		$("#report-content").hide();

		var filters = {
			date_from: dateFrom,
			date_to: dateTo,
			user: user || ""
		};

		frappe.call({
			method: "kpws_customization.kpws_customization.page.panel_report.panel_report.get_panel_report_data",
			args: {
				filters: filters
			},
			callback: function(r) {
				$("#loading-indicator").hide();
				if (r.message) {
					render_report(r.message);
				} else {
					show_error("No data returned from server");
				}
			},
			error: function(r) {
				$("#loading-indicator").hide();
				var error_msg = "An error occurred";
				if (r.message && r.message.exc) {
					error_msg = r.message.exc;
				} else if (r.message && r.message._server_messages) {
					error_msg = JSON.parse(r.message._server_messages[0]).message;
				}
				show_error(error_msg);
			}
		});
	}

	function render_report(data) {
		update_printed_info();
		render_customers(data.customers || []);
		render_returns_customers(data.returns_customers || []);
		render_grand_total(data.total_credit || 0, data.total_returns || 0);
		$("#report-content").show();
	}

	function render_customers(customers) {
		var container = $("#customers-container");
		container.empty();

		if (customers.length === 0) {
			container.append("<p class='text-center'>No data found</p>");
			return;
		}

		customers.forEach(function(customer) {
			var customerSection = $("<div class='customer-section'></div>");
			
			// Customer name heading
			customerSection.append("<h4>" + (customer.customer_name || customer.customer || "Unknown") + "</h4>");
			
			// Table
			var table = $("<table class='table table-bordered table-striped'></table>");
			var thead = $("<thead></thead>");
			thead.append("<tr>" +
				"<th>S.No</th>" +
				"<th>POS Invoice Number</th>" +
				"<th>KPWS Number</th>" +
				"<th>MR Number</th>" +
				"<th>Patient Name</th>" +
				"<th>Amount</th>" +
				"</tr>");
			table.append(thead);
			
			var tbody = $("<tbody></tbody>");
			
			if (customer.invoices && customer.invoices.length > 0) {
				customer.invoices.forEach(function(invoice) {
					var tr = $("<tr></tr>");
					tr.append("<td>" + invoice.s_no + "</td>");
					tr.append("<td><a href='#Form/POS Invoice/" + invoice.pos_invoice + "'>" + invoice.pos_invoice + "</a></td>");
					tr.append("<td>" + (invoice.kpws_number || "-") + "</td>");
					tr.append("<td>" + (invoice.mr_number || "-") + "</td>");
					tr.append("<td>" + (invoice.patient_name || "-") + "</td>");
					tr.append("<td class='text-right'>" + format_currency(invoice.amount) + "</td>");
					tbody.append(tr);
				});
				
				// Total row for this customer
				var totalRow = $("<tr class='bg-light' style='font-weight: bold;'></tr>");
				totalRow.append("<td colspan='5'><strong>Total</strong></td>");
				totalRow.append("<td class='text-right'><strong>" + format_currency(customer.total_amount) + "</strong></td>");
				tbody.append(totalRow);
			} else {
				tbody.append("<tr><td colspan='6' class='text-center'>No invoices found</td></tr>");
			}
			
			table.append(tbody);
			customerSection.append($("<div class='table-responsive'></div>").append(table));
			container.append(customerSection);
		});
	}

	function render_returns_customers(customers) {
		var container = $("#returns-container");
		container.empty();

		if (customers.length === 0) {
			return;
		}

		// Add Returns heading
		container.append("<h3 style='margin-bottom: 20px; font-weight: bold;'>Returns</h3>");

		customers.forEach(function(customer) {
			var customerSection = $("<div class='customer-section'></div>");
			
			// Customer name heading
			customerSection.append("<h4>" + (customer.customer_name || customer.customer || "Unknown") + "</h4>");
			
			// Table
			var table = $("<table class='table table-bordered table-striped'></table>");
			var thead = $("<thead></thead>");
			thead.append("<tr>" +
				"<th>S.No</th>" +
				"<th>POS Invoice Number</th>" +
				"<th>KPWS Number</th>" +
				"<th>MR Number</th>" +
				"<th>Patient Name</th>" +
				"<th>Amount</th>" +
				"</tr>");
			table.append(thead);
			
			var tbody = $("<tbody></tbody>");
			
			if (customer.invoices && customer.invoices.length > 0) {
				customer.invoices.forEach(function(invoice) {
					var tr = $("<tr></tr>");
					tr.append("<td>" + invoice.s_no + "</td>");
					tr.append("<td><a href='#Form/POS Invoice/" + invoice.pos_invoice + "'>" + invoice.pos_invoice + "</a></td>");
					tr.append("<td>" + (invoice.kpws_number || "-") + "</td>");
					tr.append("<td>" + (invoice.mr_number || "-") + "</td>");
					tr.append("<td>" + (invoice.patient_name || "-") + "</td>");
					tr.append("<td class='text-right'>" + format_currency(invoice.amount) + "</td>");
					tbody.append(tr);
				});
				
				// Total row for this customer
				var totalRow = $("<tr class='bg-light' style='font-weight: bold;'></tr>");
				totalRow.append("<td colspan='5'><strong>Total</strong></td>");
				totalRow.append("<td class='text-right'><strong>" + format_currency(customer.total_amount) + "</strong></td>");
				tbody.append(totalRow);
			} else {
				tbody.append("<tr><td colspan='6' class='text-center'>No invoices found</td></tr>");
			}
			
			table.append(tbody);
			customerSection.append($("<div class='table-responsive'></div>").append(table));
			container.append(customerSection);
		});
	}

	function render_grand_total(totalCredit, totalReturns) {
		$("#total-credit").html("<strong>" + format_currency(totalCredit) + "</strong>");
		$("#total-returns").html("<strong>" + format_currency(totalReturns) + "</strong>");
	}

	function format_currency(value) {
		if (!value) value = 0;
		return frappe.format(parseFloat(value), {
			fieldtype: "Currency",
			precision: 2
		});
	}

	function formatDate(date) {
		var d = new Date(date),
			month = '' + (d.getMonth() + 1),
			day = '' + d.getDate(),
			year = d.getFullYear();

		if (month.length < 2) month = '0' + month;
		if (day.length < 2) day = '0' + day;

		return [year, month, day].join('-');
	}

	function show_error(message) {
		$("#error-message").html("<strong>Error:</strong> " + message).show();
		$("#report-content").hide();
	}
}

