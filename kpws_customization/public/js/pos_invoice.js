// Copyright (c) 2025, Kpws Customization
// License: MIT

frappe.ui.form.on('POS Invoice', {
	refresh: function(frm) {
		// If it's a return, set the return print format from POS Profile
		if (frm.doc.is_return && frm.doc.pos_profile) {
			frappe.db.get_doc('POS Profile', frm.doc.pos_profile).then(function(profile) {
				if (profile.return_print_format) {
					// Verify print format exists
					frappe.db.get_value('Print Format', profile.return_print_format, ['name', 'disabled'], function(r) {
						if (r && r.name && !r.disabled) {
							frm.pos_print_format = profile.return_print_format;
							frm.meta.default_print_format = profile.return_print_format;
							frm.return_print_format = profile.return_print_format;
							// Also set on the document meta for print view
							if (frm.meta) {
								frm.meta._default_print_format = frm.meta.default_print_format;
								frm.meta.default_print_format = profile.return_print_format;
							}
						}
					});
				}
			}).catch(function(err) {
				console.error('Error fetching POS Profile:', err);
			});
		}
	},
	
	pos_profile: function(frm) {
		// When POS Profile changes, check for return print format
		if (frm.doc.is_return && frm.doc.pos_profile) {
			frappe.db.get_doc('POS Profile', frm.doc.pos_profile).then(function(profile) {
				if (profile.return_print_format) {
					frappe.db.get_value('Print Format', profile.return_print_format, ['name', 'disabled'], function(r) {
						if (r && r.name && !r.disabled) {
							frm.pos_print_format = profile.return_print_format;
							frm.meta.default_print_format = profile.return_print_format;
							frm.return_print_format = profile.return_print_format;
						}
					});
				}
			});
		}
	}
});

// Override the set_pos_data method to handle return print format
frappe.provide("erpnext.selling");

if (erpnext.selling.POSInvoiceController) {
	const original_set_pos_data = erpnext.selling.POSInvoiceController.prototype.set_pos_data;
	
	erpnext.selling.POSInvoiceController.prototype.set_pos_data = async function() {
		await original_set_pos_data.call(this);
		
		// After set_missing_values, check for return print format
		if (this.frm.doc.is_return && this.frm.doc.pos_profile) {
			try {
				const profile = await frappe.db.get_doc('POS Profile', this.frm.doc.pos_profile);
				if (profile.return_print_format) {
					const print_format = await frappe.db.get_value('Print Format', profile.return_print_format, ['name', 'disabled']);
					if (print_format && print_format.name && !print_format.disabled) {
						this.frm.pos_print_format = profile.return_print_format;
						this.frm.meta.default_print_format = profile.return_print_format;
						this.frm.return_print_format = profile.return_print_format;
					}
				}
			} catch (err) {
				console.error('Error setting return print format:', err);
			}
		}
	};
}

