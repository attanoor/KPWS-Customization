# Copyright (c) 2025, Kpws Customization
# License: MIT
# Run this script to create the Patient field in Quotation

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

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
	frappe.clear_cache(doctype="Quotation")
	print("Patient field created successfully in Quotation doctype!")

if __name__ == "__main__":
	create_quotation_patient_field()

