# Copyright (c) 2025, Kpws Customization
# License: MIT

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_install():
	create_quotation_patient_field()
	create_pos_profile_return_print_format_field()


def create_quotation_patient_field():
	"""Create Patient field in Quotation doctype"""
	custom_fields = {
		"Quotation": [
			{
				"fieldname": "patient",
				"fieldtype": "Link",
				"options": "Patient",
				"label": "Patient",
				"insert_after": "quotation_to",
				"description": "Select patient to auto-populate customer"
			}
		]
	}
	
	create_custom_fields(custom_fields, ignore_validate=True, update=True)
	
	# Update the custom field to ensure onchange is set
	custom_field = frappe.get_doc("Custom Field", {"dt": "Quotation", "fieldname": "patient"})
	if custom_field:
		# The onchange will be handled by the JavaScript file
		custom_field.save(ignore_permissions=True)
	
	frappe.clear_cache(doctype="Quotation")


def create_pos_profile_return_print_format_field():
	"""Create Return Print Format field in POS Profile"""
	custom_fields = {
		"POS Profile": [
			{
				"fieldname": "return_print_format",
				"fieldtype": "Link",
				"options": "Print Format",
				"label": "Return Print Format",
				"insert_after": "print_format",
				"description": "Print format to use when printing POS Returns. If not set, will use the regular Print Format."
			}
		]
	}
	
	create_custom_fields(custom_fields, ignore_validate=True, update=True)
	frappe.clear_cache(doctype="POS Profile")

