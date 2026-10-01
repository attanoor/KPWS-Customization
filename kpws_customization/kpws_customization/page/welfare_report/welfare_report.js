frappe.pages["welfare-report"].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Welfare Report",
		single_column: true
	});

	// Append HTML content directly to page
	var html_content = `
		<div class="welfare-report-container" style="padding: 20px;">
			<!-- Header -->
			<div class="report-header text-center" style="margin-bottom: 30px;">
				<h2 style="font-weight: bold; margin-bottom: 10px;">Kiran Patient Welfare Society</h2>
				<h3 style="margin-bottom: 10px;">Welfare Report</h3>
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
									<th>KPWS No</th>
									<th>MR No</th>
									<th>Patient Number</th>
									<th>Cash Received</th>
									<th>Card Received</th>
									<th>Zakat Received</th>
									<th>Donation Received</th>
									<th>Total Invoice Amount</th>
									<th>Total Received</th>
								</tr>
							</thead>
							<tbody id="sales-table-body">
								<!-- Data will be populated here -->
							</tbody>
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
									<th>KPWS No</th>
									<th>MR No</th>
									<th>Patient Number</th>
									<th>Cash Received</th>
									<th>Card Received</th>
									<th>Zakat Received</th>
									<th>Donation Received</th>
									<th>Total Invoice Amount</th>
									<th>Total Received</th>
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
									<td><strong>Cash Received</strong></td>
									<td class="text-right" id="cash-received">0.00</td>
								</tr>
								<tr>
									<td><strong>Card Received</strong></td>
									<td class="text-right" id="card-received">0.00</td>
								</tr>
								<tr>
									<td><strong>Zakat Received</strong></td>
									<td class="text-right" id="zakat-received">0.00</td>
								</tr>
								<tr>
									<td><strong>Donation Received</strong></td>
									<td class="text-right" id="donation-received">0.00</td>
								</tr>
								<tr>
									<td><strong>Return</strong></td>
									<td class="text-right" id="return-amount">0.00</td>
								</tr>
								<tr class="bg-primary" style="color: black;">
									<td><strong>Total Cash Received</strong></td>
									<td class="text-right" id="total-cash-received"><strong>0.00</strong></td>
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
				.report-filters, .btn, #generate-report, #print-report,
				.page-header, .page-actions, .page-title,
				.navbar, .sidebar, .footer, .breadcrumb {
					display: none !important;
				}

				@page {
					size: A4 landscape;
					margin: 0.5cm;
				}

				body {
					margin: 0;
					padding: 0;
					font-size: 9pt;
					-webkit-print-color-adjust: exact;
					print-color-adjust: exact;
				}

				.welfare-report-container {
					padding: 0;
					margin: 0;
					width: 100%;
				}

				.report-header {
					margin-bottom: 15px;
					page-break-after: avoid;
				}

				.report-header h2 {
					font-size: 16pt;
					margin-bottom: 3px;
				}

				.report-header h3 {
					font-size: 12pt;
					margin-bottom: 8px;
				}

				.report-header div {
					font-size: 8pt;
				}

				.table {
					font-size: 8pt;
					border-collapse: collapse;
					width: 100%;
					margin-bottom: 10px;
				}

				.table thead th {
					background-color: #e0e0e0 !important;
					border: 1px solid #000;
					padding: 4px;
					font-weight: bold;
					text-align: center;
					vertical-align: middle;
				}

				.table tbody td {
					border: 1px solid #000;
					padding: 3px;
					vertical-align: top;
				}

				.table tbody tr.bg-light td {
					background-color: #f0f0f0 !important;
					font-weight: bold;
					border: 1px solid #000;
				}

				.table-striped tbody tr:nth-child(odd) {
					background-color: #f5f5f5 !important;
				}

				.sales-table-section h4,
				.returns-table-section h4,
				.summary-section h4 {
					font-size: 11pt;
					font-weight: bold;
					margin-bottom: 8px;
					page-break-after: avoid;
				}

				.summary-section .table {
					font-size: 9pt;
					max-width: 400px;
					margin-left: auto;
					margin-right: 0;
				}

				.summary-section .table td {
					padding: 6px;
				}

				.summary-section .table tr.bg-primary {
					background-color: #337ab7 !important;
					color: black !important;
				}

				.sales-table-section,
				.returns-table-section,
				.summary-section {
					page-break-inside: avoid;
					page-break-after: auto;
				}

				thead { display: table-header-group; }
				tr { page-break-inside: avoid; }
			}
		</style>
	`;
	$(page.main).html(html_content);

	// Set current date as default
	var today = frappe.datetime.get_today();
	var date_from = frappe.datetime.add_days(today, -7);

	// Initialize page
	setTimeout(function() {
		init_page(page);
	}, 100);

	function init_page(page) {
		update_printed_info();
		$("#date-from").val(date_from);
		$("#date-to").val(today);

		setup_user_field(page);

		$("#generate-report").on("click", function() {
			generate_report();
		});

		$("#print-report").on("click", function() {
			if ($("#report-content").is(":visible")) {
				window.print();
			} else {
				frappe.show_alert({
					message: __("Please generate the report first."),
					indicator: "orange"
				});
			}
		});

		$("#date-from, #date-to").on("keypress", function(e) {
			if (e.which === 13) {
				generate_report();
			}
		});
		$(document).on("keypress", '#user-filter input', function(e) {
			if (e.which === 13) {
				generate_report();
			}
		});
	}

	function setup_user_field(page) {
		page.user_field = page.add_field({
			fieldname: "user",
			label: "User",
			fieldtype: "Link",
			options: "User",
			placeholder: __("Optional")
		});

		var user_container = $("#user-filter").parent();
		$("#user-filter").empty();
		$(page.user_field.wrapper).detach().appendTo(user_container);
		$(page.user_field.wrapper).find(".page-control-label").remove();
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

		$("#loading-indicator").show();
		$("#report-content").hide();
		$("#error-message").hide();

		var filters = {
			date_from: date_from,
			date_to: date_to,
			user: user || null
		};

		frappe.call({
			method: "kpws_customization.kpws_customization.page.welfare_report.welfare_report.get_welfare_report_data",
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
		update_printed_info();
		render_sales_table(data.data || []);
		render_returns_table(data.returns || []);
		render_summary(data.totals || {});
		$("#report-content").show();
	}

	function render_sales_table(data) {
		var tbody = $("#sales-table-body");
		var table = $("#sales-table");
		tbody.empty();

		if (data.length === 0) {
			tbody.append("<tr><td colspan='11' class='text-center'>No sales data found</td></tr>");
			return;
		}

		var total_cash = 0;
		var total_card = 0;
		var total_zakat = 0;
		var total_donation = 0;
		var total_invoice = 0;
		var total_received = 0;

		data.forEach(function(row) {
			var tr = $("<tr>");
			tr.append("<td>" + row.s_no + "</td>");
			tr.append("<td><a href='#Form/POS Invoice/" + row.pos_invoice + "'>" + row.pos_invoice + "</a></td>");
			tr.append("<td>" + (row.kpws_number || "-") + "</td>");
			tr.append("<td>" + (row.mr_number || "-") + "</td>");
			tr.append("<td>" + (row.patient_number || "-") + "</td>");
			tr.append("<td class='text-right'>" + format_currency(row.cash_received) + "</td>");
			tr.append("<td class='text-right'>" + format_currency(row.card_received) + "</td>");
			tr.append("<td class='text-right'>" + format_currency(row.zakat_received) + "</td>");
			tr.append("<td class='text-right'>" + format_currency(row.donation_received) + "</td>");
			tr.append("<td class='text-right'>" + format_currency(row.total_invoice_amount) + "</td>");
			tr.append("<td class='text-right'>" + format_currency(row.total_received) + "</td>");
			tbody.append(tr);

			total_cash += parseFloat(row.cash_received || 0);
			total_card += parseFloat(row.card_received || 0);
			total_zakat += parseFloat(row.zakat_received || 0);
			total_donation += parseFloat(row.donation_received || 0);
			total_invoice += parseFloat(row.total_invoice_amount || 0);
			total_received += parseFloat(row.total_received || 0);
		});

		// Add totals row
		var footer_tr = $("<tr class='bg-light' style='font-weight: bold;'>");
		footer_tr.append("<td colspan='5'><strong>Total</strong></td>");
		footer_tr.append("<td class='text-right'><strong>" + format_currency(total_cash) + "</strong></td>");
		footer_tr.append("<td class='text-right'><strong>" + format_currency(total_card) + "</strong></td>");
		footer_tr.append("<td class='text-right'><strong>" + format_currency(total_zakat) + "</strong></td>");
		footer_tr.append("<td class='text-right'><strong>" + format_currency(total_donation) + "</strong></td>");
		footer_tr.append("<td class='text-right'><strong>" + format_currency(total_invoice) + "</strong></td>");
		footer_tr.append("<td class='text-right'><strong>" + format_currency(total_received) + "</strong></td>");
		tbody.append(footer_tr);
	}

	function render_returns_table(data) {
		var tbody = $("#returns-table-body");
		tbody.empty();

		if (data.length === 0) {
			tbody.append("<tr><td colspan='11' class='text-center'>No returns found</td></tr>");
			return;
		}

		var total_cash = 0;
		var total_card = 0;
		var total_zakat = 0;
		var total_donation = 0;
		var total_invoice = 0;
		var total_received = 0;

		data.forEach(function(row) {
			var tr = $("<tr>");
			tr.append("<td>" + row.s_no + "</td>");
			tr.append("<td><a href='#Form/POS Invoice/" + row.pos_invoice + "'>" + row.pos_invoice + "</a></td>");
			tr.append("<td>" + (row.kpws_number || "-") + "</td>");
			tr.append("<td>" + (row.mr_number || "-") + "</td>");
			tr.append("<td>" + (row.patient_number || "-") + "</td>");
			tr.append("<td class='text-right'>" + format_currency(row.cash_received) + "</td>");
			tr.append("<td class='text-right'>" + format_currency(row.card_received) + "</td>");
			tr.append("<td class='text-right'>" + format_currency(row.zakat_received) + "</td>");
			tr.append("<td class='text-right'>" + format_currency(row.donation_received) + "</td>");
			tr.append("<td class='text-right'>" + format_currency(row.total_invoice_amount) + "</td>");
			tr.append("<td class='text-right'>" + format_currency(row.total_received) + "</td>");
			tbody.append(tr);

			total_cash += parseFloat(row.cash_received || 0);
			total_card += parseFloat(row.card_received || 0);
			total_zakat += parseFloat(row.zakat_received || 0);
			total_donation += parseFloat(row.donation_received || 0);
			total_invoice += parseFloat(row.total_invoice_amount || 0);
			total_received += parseFloat(row.total_received || 0);
		});

		// Add totals row
		var footer_tr = $("<tr class='bg-light' style='font-weight: bold;'>");
		footer_tr.append("<td colspan='5'><strong>Total</strong></td>");
		footer_tr.append("<td class='text-right'><strong>" + format_currency(total_cash) + "</strong></td>");
		footer_tr.append("<td class='text-right'><strong>" + format_currency(total_card) + "</strong></td>");
		footer_tr.append("<td class='text-right'><strong>" + format_currency(total_zakat) + "</strong></td>");
		footer_tr.append("<td class='text-right'><strong>" + format_currency(total_donation) + "</strong></td>");
		footer_tr.append("<td class='text-right'><strong>" + format_currency(total_invoice) + "</strong></td>");
		footer_tr.append("<td class='text-right'><strong>" + format_currency(total_received) + "</strong></td>");
		tbody.append(footer_tr);
	}

	function render_summary(totals) {
		// Cash Received (sales only)
		$("#cash-received").html(format_currency(totals.total_cash_received || 0));
		// Card Received (sales only)
		$("#card-received").html(format_currency(totals.total_card_received || 0));
		// Zakat Received (sales only)
		$("#zakat-received").html(format_currency(totals.total_zakat_received || 0));
		// Donation Received (sales only)
		$("#donation-received").html(format_currency(totals.total_donation_received || 0));
		// Return (returns total)
		$("#return-amount").html(format_currency(totals.total_return_amount || 0));
		// Total Cash Received (net: sales - returns)
		$("#total-cash-received").html("<strong>" + format_currency(totals.net_cash_received || 0) + "</strong>");
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

