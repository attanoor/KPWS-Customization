frappe.pages["formulary-report"].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Formulary Report",
		single_column: true
	});

	// Append HTML content directly to page
	var html_content = `
		<div class="formulary-report-container" style="padding: 20px;">
			<!-- Header -->
			<div class="report-header text-center" style="margin-bottom: 30px;">
				<h2 style="font-weight: bold; margin-bottom: 10px;">Kiran Patient Welfare Society</h2>
				<h3 style="margin-bottom: 10px;">Formulary Report</h3>
				<div style="margin-bottom: 20px;">
					<div><strong>Printed Time:</strong> <span id="printed-time"></span></div>
				</div>
			</div>

			<!-- Filters -->
			<div class="report-filters" style="margin-bottom: 20px; padding: 15px; background: #f5f5f5; border-radius: 5px;">
				<div class="row">
					<div class="col-sm-3">
						<div class="form-group">
							<label>Category</label>
							<div id="category-filter"></div>
						</div>
					</div>
					<div class="col-sm-3">
						<div class="form-group">
							<label>MNC/MEETOU</label>
							<div id="mnc-meetou-filter"></div>
						</div>
					</div>
					<div class="col-sm-3">
						<div class="form-group">
							<label>Med Type</label>
							<div id="med-type-filter"></div>
						</div>
					</div>
					<div class="col-sm-3">
						<div class="form-group">
							<label>Manufacturer</label>
							<div id="manufacturer-filter"></div>
						</div>
					</div>
				</div>
				<div class="row">
					<div class="col-sm-3">
						<div class="form-group">
							<label>Generic</label>
							<div id="generic-filter"></div>
						</div>
					</div>
					<div class="col-sm-3">
						<div class="form-group">
							<label>Warehouse</label>
							<div id="warehouse-filter"></div>
						</div>
					</div>
					<div class="col-sm-6 text-right" style="padding-top: 25px;">
						<button class="btn btn-primary" id="generate-report">Generate Report</button>
						<button class="btn btn-default" id="print-report">Print</button>
					</div>
				</div>
			</div>

			<!-- Report Data -->
			<div id="report-content" style="display: none;">
				<div id="items-container">
					<!-- Items table will be populated here -->
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
					font-size: 7pt;
					background: white !important;
				}
				
				/* Main container */
				.formulary-report-container {
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
					font-size: 6pt !important;
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
					font-size: 6pt !important;
				}
				
				.table tbody td {
					border: 1px solid #000 !important;
					padding: 2px 1px !important;
					vertical-align: top;
					font-size: 6pt !important;
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
		// Setup filter fields
		setup_filter_fields();

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

	function setup_filter_fields() {
		// Setup Category filter
		setup_select_field("custom_drug_category", "category-filter", "Category");
		
		// Setup MNC/MEETOU filter
		setup_select_field("custom_manufacturerorigin", "mnc-meetou-filter", "MNC/MEETOU");
		
		// Setup Med Type filter
		setup_select_field("custom_drug_consumtion_type", "med-type-filter", "Med Type");
		
		// Setup Manufacturer filter
		setup_select_field("custom_manufacturer", "manufacturer-filter", "Manufacturer");
		
		// Setup Generic filter
		setup_select_field("custom_generic", "generic-filter", "Generic");
		
		// Setup Warehouse filter
		setup_warehouse_field();
	}

	function setup_select_field(fieldname, container_id, label) {
		frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "Item",
				fields: [fieldname],
				filters: {
					[fieldname]: ["!=", ""],
					disabled: 0
				},
				limit_page_length: 0
			},
			callback: function(r) {
				if (r.message) {
					// Get unique values
					var values = [...new Set(r.message.map(function(item) {
						return item[fieldname];
					}).filter(function(val) {
						return val && val.trim();
					}))].sort();
					
					// Create select field
					var select = $("<select class='form-control' id='" + fieldname + "-select'></select>");
					select.append("<option value=''>All</option>");
					values.forEach(function(val) {
						select.append("<option value='" + val + "'>" + val + "</option>");
					});
					$("#" + container_id).html(select);
				} else {
					// Fallback to text input
					var input = $("<input type='text' class='form-control' id='" + fieldname + "-input' placeholder='Enter " + label + "'>");
					$("#" + container_id).html(input);
				}
			},
			error: function() {
				// Fallback to text input
				var input = $("<input type='text' class='form-control' id='" + fieldname + "-input' placeholder='Enter " + label + "'>");
				$("#" + container_id).html(input);
			}
		});
	}

	function setup_warehouse_field() {
		// Fetch all warehouses
		frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "Warehouse",
				fields: ["name", "warehouse_name"],
				limit_page_length: 0
			},
			callback: function(r) {
				if (r.message) {
					// Create select field
					var select = $("<select class='form-control' id='warehouse-select'></select>");
					select.append("<option value=''>All</option>");
					r.message.forEach(function(warehouse) {
						var display_name = warehouse.warehouse_name || warehouse.name;
						select.append("<option value='" + warehouse.name + "'>" + display_name + "</option>");
					});
					$("#warehouse-filter").html(select);
				} else {
					// Fallback to text input
					var input = $("<input type='text' class='form-control' id='warehouse-input' placeholder='Enter Warehouse'>");
					$("#warehouse-filter").html(input);
				}
			},
			error: function() {
				// Fallback to text input
				var input = $("<input type='text' class='form-control' id='warehouse-input' placeholder='Enter Warehouse'>");
				$("#warehouse-filter").html(input);
			}
		});
	}

	function update_printed_info() {
		var now = new Date();
		$("#printed-time").text(now.toLocaleString());
	}

	function generate_report() {
		// Get filter values
		var filters = {
			custom_drug_category: get_filter_value("custom_drug_category"),
			custom_manufacturerorigin: get_filter_value("custom_manufacturerorigin"),
			custom_drug_consumtion_type: get_filter_value("custom_drug_consumtion_type"),
			custom_manufacturer: get_filter_value("custom_manufacturer"),
			custom_generic: get_filter_value("custom_generic"),
			warehouse: get_warehouse_value()
		};

		$("#error-message").hide();
		$("#loading-indicator").show();
		$("#report-content").hide();

		frappe.call({
			method: "kpws_customization.kpws_customization.page.formulary_report.formulary_report.get_formulary_report_data",
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

	function get_filter_value(fieldname) {
		var select = $("#" + fieldname + "-select");
		var input = $("#" + fieldname + "-input");
		
		if (select.length) {
			return select.val() || "";
		} else if (input.length) {
			return input.val() || "";
		}
		return "";
	}

	function get_warehouse_value() {
		var select = $("#warehouse-select");
		var input = $("#warehouse-input");
		
		if (select.length) {
			return select.val() || "";
		} else if (input.length) {
			return input.val() || "";
		}
		return "";
	}

	function render_report(data) {
		update_printed_info();
		render_items(data.items || []);
		$("#report-content").show();
	}

	function render_items(items) {
		var container = $("#items-container");
		container.empty();

		if (items.length === 0) {
			container.append("<p class='text-center'>No data found</p>");
			return;
		}

		// Create table
		var table = $("<table class='table table-bordered table-striped'></table>");
		var thead = $("<thead></thead>");
		thead.append("<tr>" +
			"<th>S.No</th>" +
			"<th>Item Code</th>" +
			"<th>Category</th>" +
			"<th>MNC/MEETOU</th>" +
			"<th>Med Type</th>" +
			"<th>Item Name</th>" +
			"<th>Manufacturer</th>" +
			"<th>Generic</th>" +
			"<th>Total Qty</th>" +
			"<th>UOM</th>" +
			"<th>MRP</th>" +
			"<th>TP</th>" +
			"<th>PP</th>" +
			"<th>SPW</th>" +
			"<th>SPW Perc</th>" +
			"<th>SPC</th>" +
			"<th>SPC Perc</th>" +
			"<th>SPP</th>" +
			"<th>SPP Perc</th>" +
			"</tr>");
		table.append(thead);
		
		var tbody = $("<tbody></tbody>");
		
		items.forEach(function(item, index) {
			var tr = $("<tr></tr>");
			tr.append("<td>" + (index + 1) + "</td>");
			tr.append("<td><a href='#Form/Item/" + item.item_code + "'>" + (item.item_code || "-") + "</a></td>");
			tr.append("<td>" + (item.custom_drug_category || "-") + "</td>");
			tr.append("<td>" + (item.custom_manufacturerorigin || "-") + "</td>");
			tr.append("<td>" + (item.custom_drug_consumtion_type || "-") + "</td>");
			tr.append("<td>" + (item.item_name || "-") + "</td>");
			tr.append("<td>" + (item.custom_manufacturer || "-") + "</td>");
			tr.append("<td>" + (item.custom_generic || "-") + "</td>");
			tr.append("<td class='text-right'>" + format_number(item.total_qty) + "</td>");
			tr.append("<td>" + (item.uom || "-") + "</td>");
			tr.append("<td class='text-right'>" + format_currency(item.mrp) + "</td>");
			tr.append("<td class='text-right'>" + format_currency(item.tp) + "</td>");
			tr.append("<td class='text-right'>" + format_currency(item.pp) + "</td>");
			tr.append("<td class='text-right'>" + format_currency(item.spw) + "</td>");
			tr.append("<td class='text-right'>" + format_percentage(item.spw_perc) + "</td>");
			tr.append("<td class='text-right'>" + format_currency(item.spc) + "</td>");
			tr.append("<td class='text-right'>" + format_percentage(item.spc_perc) + "</td>");
			tr.append("<td class='text-right'>" + format_currency(item.spp) + "</td>");
			tr.append("<td class='text-right'>" + format_percentage(item.spp_perc) + "</td>");
			tbody.append(tr);
		});
		
		table.append(tbody);
		container.append($("<div class='table-responsive'></div>").append(table));
	}

	function format_currency(value) {
		if (!value || value == 0) return "0.00";
		return frappe.format(parseFloat(value), {
			fieldtype: "Currency",
			precision: 2
		});
	}

	function format_number(value) {
		if (!value || value == 0) return "0.00";
		return frappe.format(parseFloat(value), {
			fieldtype: "Float",
			precision: 2
		});
	}

	function format_percentage(value) {
		if (!value || value == 0) return "0.00%";
		return parseFloat(value).toFixed(2) + "%";
	}

	function show_error(message) {
		$("#error-message").html("<strong>Error:</strong> " + message).show();
		$("#report-content").hide();
	}
}

