frappe.pages["pending-supplier-pur"].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Pending Supplier Purchase Order",
		single_column: true
	});

	// Append HTML content directly to page
	var html_content = `
		<div class="pending-supplier-pur-container" style="padding: 20px;">
			<!-- Header -->
			<div class="report-header text-center" style="margin-bottom: 30px;">
				<h2 style="font-weight: bold; margin-bottom: 10px;">Kiran Patient Welfare Society</h2>
				<h3 style="margin-bottom: 10px;">Pending Supplier Purchase Order Report</h3>
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
							<label>Supplier</label>
							<div id="supplier-filter"></div>
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
				<div id="suppliers-container">
					<!-- Supplier sections will be populated here -->
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
				.pending-supplier-pur-container {
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
				
				/* Supplier section */
				.supplier-section {
					margin-bottom: 30px !important;
					page-break-inside: avoid;
				}
				
				.supplier-info {
					margin-bottom: 10px !important;
					padding: 8px !important;
					background-color: #f0f0f0 !important;
					border: 1px solid #000 !important;
					page-break-after: avoid;
				}
				
				.supplier-info h4 {
					font-size: 11pt !important;
					font-weight: bold !important;
					margin: 5px 0 !important;
				}
				
				.supplier-info div {
					font-size: 8pt !important;
					margin: 2px 0 !important;
				}
				
				/* Tables */
				.table {
					font-size: 7pt !important;
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
					padding: 3px 2px !important;
					font-weight: bold !important;
					text-align: center !important;
					font-size: 7pt !important;
				}
				
				.table tbody td {
					border: 1px solid #000 !important;
					padding: 2px 1px !important;
					vertical-align: top;
					font-size: 7pt !important;
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

		// Setup supplier field
		setup_supplier_field();

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

	function setup_supplier_field() {
		page.add_field({
			fieldtype: "Link",
			fieldname: "supplier",
			options: "Supplier",
			label: "Supplier",
			change: function() {
				// Supplier selection changed
			}
		});

		// Move the field to our custom location
		setTimeout(function() {
			var field = page.fields_dict.supplier.$wrapper;
			$("#supplier-filter").html(field);
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
		var supplier = page.fields_dict.supplier ? page.fields_dict.supplier.get_value() : "";

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
			supplier: supplier || ""
		};

		frappe.call({
			method: "kpws_customization.kpws_customization.page.pending_supplier_pur.pending_supplier_pur.get_pending_supplier_purchase_data",
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
		render_suppliers(data.suppliers || []);
		$("#report-content").show();
	}

	function render_suppliers(suppliers) {
		var container = $("#suppliers-container");
		container.empty();

		if (suppliers.length === 0) {
			container.append("<p class='text-center'>No data found</p>");
			return;
		}

		suppliers.forEach(function(supplier) {
			var supplierSection = $("<div class='supplier-section'></div>");
			
			// Supplier info box
			var supplierInfo = $("<div class='supplier-info'></div>");
			supplierInfo.append("<h4>" + (supplier.supplier_name || "Unknown") + "</h4>");
			supplierInfo.append("<div><strong>Phone:</strong> " + (supplier.phone || "-") + " &nbsp;&nbsp; <strong>Email:</strong> " + (supplier.email || "-") + "</div>");
			supplierSection.append(supplierInfo);
			
			// Table
			var table = $("<table class='table table-bordered table-striped'></table>");
			var thead = $("<thead></thead>");
			thead.append("<tr>" +
				"<th>Item Name</th>" +
				"<th>PO No</th>" +
				"<th>PO Date</th>" +
				"<th>Qty Ordered</th>" +
				"<th>Qty Received</th>" +
				"<th>Purchase Receipt No</th>" +
				"<th>Pending Qty</th>" +
				"</tr>");
			table.append(thead);
			
			var tbody = $("<tbody></tbody>");
			
			if (supplier.items && supplier.items.length > 0) {
				supplier.items.forEach(function(item) {
					var tr = $("<tr></tr>");
					tr.append("<td>" + (item.item_name || "-") + "</td>");
					tr.append("<td><a href='#Form/Purchase Order/" + item.po_number + "'>" + item.po_number + "</a></td>");
					tr.append("<td>" + (item.po_date ? formatDateDisplay(item.po_date) : "-") + "</td>");
					tr.append("<td class='text-right'>" + format_number(item.qty_ordered) + "</td>");
					tr.append("<td class='text-right'>" + format_number(item.qty_received) + "</td>");
					
					// Purchase Receipt No - can be multiple, so show as comma-separated links
					var prCell = $("<td></td>");
					if (item.purchase_receipt_no && item.purchase_receipt_no !== "-") {
						var prNos = item.purchase_receipt_no.split(", ");
						prNos.forEach(function(prNo, index) {
							if (index > 0) prCell.append(", ");
							prCell.append("<a href='#Form/Purchase Receipt/" + prNo.trim() + "'>" + prNo.trim() + "</a>");
						});
					} else {
						prCell.append("-");
					}
					tr.append(prCell);
					
					tr.append("<td class='text-right'><strong>" + format_number(item.pending_qty) + "</strong></td>");
					tbody.append(tr);
				});
			} else {
				tbody.append("<tr><td colspan='7' class='text-center'>No items found</td></tr>");
			}
			
			table.append(tbody);
			supplierSection.append($("<div class='table-responsive'></div>").append(table));
			container.append(supplierSection);
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

	function formatDateDisplay(dateStr) {
		if (!dateStr) return "-";
		var date = new Date(dateStr);
		return formatDate(date);
	}

	function show_error(message) {
		$("#error-message").html("<strong>Error:</strong> " + message).show();
		$("#report-content").hide();
	}
}

