frappe.pages["pending-requistion-r"].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Pending Requisition Report",
		single_column: true
	});

	// Append HTML content directly to page
	var html_content = `
		<div class="pending-requisition-container" style="padding: 20px;">
			<!-- Header -->
			<div class="report-header text-center" style="margin-bottom: 30px;">
				<h2 style="font-weight: bold; margin-bottom: 10px;">Kiran Patient Welfare Society</h2>
				<h3 style="margin-bottom: 10px;">Pending Requisition Report</h3>
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
							<label>Material Request No</label>
							<div id="material-request-filter"></div>
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
				<div id="material-requests-container">
					<!-- Material Request sections will be populated here -->
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
					font-size: 8pt;
					background: white !important;
				}
				
				/* Main container */
				.pending-requisition-container {
					padding: 10px !important;
					margin: 0 !important;
					background: white !important;
				}
				
				/* Tables */
				table {
					width: 100%;
					border-collapse: collapse;
					margin-bottom: 15px;
					page-break-inside: avoid;
				}
				
				table th, table td {
					border: 1px solid #000;
					padding: 4px;
					text-align: left;
					font-size: 7pt;
				}
				
				table th {
					background-color: #f0f0f0 !important;
					font-weight: bold;
				}
				
				/* Material Request heading */
				.material-request-heading {
					page-break-after: avoid;
					margin-top: 15px;
					margin-bottom: 10px;
				}
			}
			
			/* Screen styles */
			.pending-requisition-container {
				background: #fff;
			}
			
			.report-header {
				border-bottom: 2px solid #333;
				padding-bottom: 15px;
			}
			
			table {
				width: 100%;
				border-collapse: collapse;
				margin-bottom: 20px;
			}
			
			table th, table td {
				border: 1px solid #ddd;
				padding: 8px;
				text-align: left;
			}
			
			table th {
				background-color: #f8f9fa;
				font-weight: bold;
			}
			
			table tr:nth-child(even) {
				background-color: #f9f9f9;
			}
			
			.material-request-heading {
				background-color: #e9ecef;
				padding: 10px;
				margin-top: 20px;
				margin-bottom: 10px;
				border-left: 4px solid #007bff;
				font-weight: bold;
			}
			
			.text-right {
				text-align: right;
			}
			
			.text-center {
				text-align: center;
			}
		</style>
	`;
	
	$(wrapper).append(html_content);
	
	// Initialize Material Request filter
	var material_request_field = frappe.ui.form.make_control({
		df: {
			fieldtype: "Link",
			fieldname: "material_request",
			options: "Material Request",
			label: "Material Request No",
			placeholder: "Select Material Request"
		},
		parent: $("#material-request-filter"),
		render_input: true
	});
	material_request_field.refresh();
	
	// Set default dates
	var today = new Date();
	var firstDayOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
	$("#date-from").val(firstDayOfMonth.toISOString().split('T')[0]);
	$("#date-to").val(today.toISOString().split('T')[0]);
	
	// Update printed time and date
	function updateHeader() {
		var now = new Date();
		$("#printed-time").text(now.toLocaleString());
		var dateFrom = $("#date-from").val();
		var dateTo = $("#date-to").val();
		if (dateFrom && dateTo) {
			$("#report-date").text(dateFrom + " to " + dateTo);
		}
	}
	updateHeader();
	
	// Generate Report
	$("#generate-report").on("click", function() {
		var dateFrom = $("#date-from").val();
		var dateTo = $("#date-to").val();
		var materialRequestNo = material_request_field.get_value() || "";
		
		if (!dateFrom || !dateTo) {
			frappe.msgprint({
				title: __("Validation Error"),
				message: __("Please select Date From and Date To"),
				indicator: "red"
			});
			return;
		}
		
		// Show loading
		$("#loading-indicator").show();
		$("#report-content").hide();
		$("#error-message").hide();
		
		// Update header
		updateHeader();
		
		var filters = {
			date_from: dateFrom,
			date_to: dateTo,
			material_request_no: materialRequestNo
		};
		
		frappe.call({
			method: "kpws_customization.kpws_customization.page.pending_requistion_r.pending_requistion_r.get_pending_requisition_data",
			args: {
				filters: filters
			},
			callback: function(r) {
				$("#loading-indicator").hide();
				
				if (r.message) {
					renderReport(r.message);
					$("#report-content").show();
				} else {
					$("#error-message").html("No data found").show();
				}
			},
			error: function(r) {
				$("#loading-indicator").hide();
				var errorMsg = r.message || "An error occurred while generating the report";
				$("#error-message").html("<strong>Error:</strong> " + errorMsg).show();
			}
		});
	});
	
	// Render Report
	function renderReport(data) {
		var container = $("#material-requests-container");
		container.empty();
		
		if (!data.material_requests || data.material_requests.length === 0) {
			container.html('<div style="text-align: center; padding: 40px; color: #666;">No data found</div>');
			return;
		}
		
		data.material_requests.forEach(function(mr) {
			// Material Request Heading
			var heading = $('<div class="material-request-heading">Material Request No: ' + mr.material_request_no + '</div>');
			container.append(heading);
			
			// Table
			var table = $('<table class="table table-bordered"></table>');
			var thead = $('<thead></thead>');
			var tbody = $('<tbody></tbody>');
			
			// Header row
			var headerRow = $('<tr></tr>');
			headerRow.append('<th>S.No</th>');
			headerRow.append('<th>Item Code</th>');
			headerRow.append('<th>Item Name</th>');
			headerRow.append('<th>UOM</th>');
			headerRow.append('<th>Request Quantity</th>');
			headerRow.append('<th>Received Qty</th>');
			headerRow.append('<th>Pending Qty</th>');
			thead.append(headerRow);
			
			// Data rows
			if (mr.items && mr.items.length > 0) {
				mr.items.forEach(function(item, index) {
					var row = $('<tr></tr>');
					row.append('<td>' + (index + 1) + '</td>');
					row.append('<td>' + (item.item_code || '-') + '</td>');
					row.append('<td>' + (item.item_name || '-') + '</td>');
					row.append('<td>' + (item.uom || '-') + '</td>');
					row.append('<td>' + parseFloat(item.request_qty || 0).toFixed(2) + '</td>');
					row.append('<td>' + parseFloat(item.received_qty || 0).toFixed(2) + '</td>');
					row.append('<td>' + parseFloat(item.pending_qty || 0).toFixed(2) + '</td>');
					tbody.append(row);
				});
				
				// Footer row with totals
				var footerRow = $('<tr style="font-weight: bold; background-color: #e9ecef;"></tr>');
				footerRow.append('<td colspan="4" style="text-align: right;">Total:</td>');
				var totalRequestQty = mr.items.reduce(function(sum, item) { return sum + parseFloat(item.request_qty || 0); }, 0);
				var totalReceivedQty = mr.items.reduce(function(sum, item) { return sum + parseFloat(item.received_qty || 0); }, 0);
				var totalPendingQty = mr.items.reduce(function(sum, item) { return sum + parseFloat(item.pending_qty || 0); }, 0);
				footerRow.append('<td>' + totalRequestQty.toFixed(2) + '</td>');
				footerRow.append('<td>' + totalReceivedQty.toFixed(2) + '</td>');
				footerRow.append('<td>' + totalPendingQty.toFixed(2) + '</td>');
				tbody.append(footerRow);
			} else {
				var noDataRow = $('<tr><td colspan="7" style="text-align: center; padding: 20px;">No items found</td></tr>');
				tbody.append(noDataRow);
			}
			
			table.append(thead);
			table.append(tbody);
			container.append(table);
		});
	}
	
	// Print Report
	$("#print-report").on("click", function() {
		if ($("#report-content").is(":visible")) {
			window.print();
		} else {
			frappe.msgprint({
				title: __("Info"),
				message: __("Please generate the report first"),
				indicator: "blue"
			});
		}
	});
};

