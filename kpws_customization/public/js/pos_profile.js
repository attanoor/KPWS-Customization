// Copyright (c) 2025, Kpws Customization
// License: MIT

frappe.ui.form.on('POS Profile', {
	setup: function(frm) {
		// Add query filter for Return Print Format field
		frm.set_query("return_print_format", function() {
			return {
				filters: [
					['Print Format', 'doc_type', '=', 'POS Invoice']
				]
			};
		});
	}
});

