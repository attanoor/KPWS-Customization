frappe.pages["item-wise-average-pr"].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Item Wise Average Price Report",
		single_column: true
	});

	// Append HTML content directly to page
	var html_content = `
		<div class="item-wise-average-pr-container" style="padding: 20px;">
			<!-- Header -->
			<div class="report-header text-center" style="margin-bottom: 30px;">
				<h2 style="font-weight: bold; margin-bottom: 10px;">Kiran Patient Welfare Society</h2>
				<h3 style="margin-bottom: 10px;">Item Wise Average Price Report</h3>
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
							<label>Generic Name</label>
							<div id="generic-name-filter"></div>
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
				<div class="table-responsive">
					<table class="table table-bordered table-striped" id="report-table">
						<thead>
							<tr>
								<th>S.No</th>
								<th>Generic Name</th>
								<th>Item Name</th>
								<th>Supplier Name</th>
								<th>Qty</th>
								<th>Avg Rate</th>
								<th>Amount</th>
							</tr>
						</thead>
						<tbody id="report-table-body">
							<!-- Data will be populated here -->
						</tbody>
						<tfoot id="report-table-footer">
							<!-- Totals will be populated here -->
						</tfoot>
					</table>
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
				.item-wise-average-pr-container {
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
					font-size: 8pt !important;
				}
				
				.table tfoot td {
					border: 1px solid #000 !important;
					padding: 4px !important;
					font-weight: bold !important;
					background-color: #f0f0f0 !important;
					font-size: 8pt !important;
				}
				
				.table-striped tbody tr:nth-child(odd) {
					background-color: #f5f5f5 !important;
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

		// Setup generic name field
		setup_generic_name_field();

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

	function setup_generic_name_field() {
		// Get all unique generic names from Item using custom_generic field
		frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "Item",
				fields: ["custom_generic"],
				filters: {
					custom_generic: ["!=", ""],
					disabled: 0
				},
				limit_page_length: 0
			},
			callback: function(r) {
				if (r.message) {
					// Get unique generic names
					var genericNames = [...new Set(r.message.map(function(item) {
						return item.custom_generic;
					}).filter(function(name) {
						return name && name.trim();
					}))].sort();
					
					// Create select field
					var select = $("<select class='form-control' id='generic-name-select'></select>");
					select.append("<option value=''>All</option>");
					genericNames.forEach(function(name) {
						select.append("<option value='" + name + "'>" + name + "</option>");
					});
					$("#generic-name-filter").html(select);
				} else {
					// Fallback to text input
					var input = $("<input type='text' class='form-control' id='generic-name-input' placeholder='Enter Generic Name'>");
					$("#generic-name-filter").html(input);
				}
			},
			error: function() {
				// Fallback to text input
				var input = $("<input type='text' class='form-control' id='generic-name-input' placeholder='Enter Generic Name'>");
				$("#generic-name-filter").html(input);
			}
		});
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
		var genericName = "";
		
		// Get generic name from select or input
		if ($("#generic-name-select").length) {
			genericName = $("#generic-name-select").val() || "";
		} else if ($("#generic-name-input").length) {
			genericName = $("#generic-name-input").val() || "";
		}

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
			generic_name: genericName || ""
		};

		frappe.call({
			method: "kpws_customization.kpws_customization.page.item_wise_average_pr.item_wise_average_pr.get_item_wise_average_price_data",
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
		render_table(data.data || []);
		$("#report-content").show();
	}

	function render_table(data) {
		var tbody = $("#report-table-body");
		var footer = $("#report-table-footer");
		
		tbody.empty();
		footer.empty();

		if (data.length === 0) {
			tbody.append("<tr><td colspan='7' class='text-center'>No data found</td></tr>");
			return;
		}

		var total_qty = 0;
		var total_amount = 0;

		data.forEach(function(row) {
			var tr = $("<tr></tr>");
			tr.append("<td>" + row.s_no + "</td>");
			tr.append("<td>" + (row.generic_name || "-") + "</td>");
			tr.append("<td>" + (row.item_name || "-") + "</td>");
			tr.append("<td>" + (row.supplier_name || "-") + "</td>");
			tr.append("<td class='text-right'>" + format_number(row.qty) + "</td>");
			tr.append("<td class='text-right'>" + format_currency(row.avg_rate) + "</td>");
			tr.append("<td class='text-right'>" + format_currency(row.amount) + "</td>");
			tbody.append(tr);

			total_qty += parseFloat(row.qty || 0);
			total_amount += parseFloat(row.amount || 0);
		});

		// Add footer totals
		var footer_tr = $("<tr class='bg-light' style='font-weight: bold;'></tr>");
		footer_tr.append("<td colspan='4'><strong>Total</strong></td>");
		footer_tr.append("<td class='text-right'><strong>" + format_number(total_qty) + "</strong></td>");
		footer_tr.append("<td></td>"); // Empty for Avg Rate column
		footer_tr.append("<td class='text-right'><strong>" + format_currency(total_amount) + "</strong></td>");
		footer.append(footer_tr);
	}

	function format_currency(value) {
		if (!value) value = 0;
		return frappe.format(parseFloat(value), {
			fieldtype: "Currency",
			precision: 2
		});
	}

	function format_number(value) {
		if (!value) value = 0;
		return frappe.format(parseFloat(value), {
			fieldtype: "Float",
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

