// Copyright (c) 2025, Kpws Customization
// License: MIT

frappe.ui.form.on('Quotation', {
	setup: function(frm) {
		// Setup patient field handler
		setup_patient_field(frm);
	},

	refresh: function(frm) {
		// Ensure patient field handler is set up
		setup_patient_field(frm);
	},

	patient: function(frm) {
		// When patient is selected, auto-populate customer
		if (frm.doc.patient) {
			frappe.db.get_doc('Patient', frm.doc.patient).then(function(patient_doc) {
				if (patient_doc.customer) {
					// Set quotation_to to Customer
					frm.set_value('quotation_to', 'Customer');
					// Set party_name (customer) from patient's customer
					frm.set_value('party_name', patient_doc.customer);
					// Trigger party_name change to load customer details
					frm.trigger('party_name');
					frappe.show_alert({
						message: __('Customer auto-selected from Patient'),
						indicator: 'green'
					});
				} else {
					frappe.msgprint({
						title: __('No Customer Linked'),
						message: __('This patient is not linked to a Customer. Please link a customer to the patient first.'),
						indicator: 'orange'
					});
					frm.set_value('patient', '');
				}
			}).catch(function(error) {
				console.error('Error fetching patient:', error);
				frappe.show_alert({
					message: __('Error fetching patient details'),
					indicator: 'red'
				});
			});
		}
	}
});

function setup_patient_field(frm) {
	// Prevent multiple setups
	if (frm._patient_field_setup_done) {
		return;
	}

	// Wait for field to be available
	if (!frm.fields_dict.patient) {
		setTimeout(function() {
			setup_patient_field(frm);
		}, 100);
		return;
	}

	// Mark as setup
	frm._patient_field_setup_done = true;

	// Set onchange in field definition
	if (frm.fields_dict.patient.df) {
		frm.fields_dict.patient.df.onchange = function() {
			frm.trigger('patient');
		};
	}

	// Also add direct event listener to the input field
	if (frm.fields_dict.patient.$input) {
		frm.fields_dict.patient.$input.off('change.patient_custom').on('change.patient_custom', function() {
			// Small delay to ensure value is set
			setTimeout(function() {
				if (frm.doc.patient) {
					frm.trigger('patient');
				}
			}, 100);
		});
	}
}

