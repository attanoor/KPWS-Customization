# Copyright (c) 2025, Kpws Customization
# License: MIT

import frappe
from frappe.utils import cint
from erpnext.accounts.doctype.pos_invoice.pos_invoice import POSInvoice

# Try to inherit from pos_customization's override if available
try:
	from pos_customization.overrides.pos_invoice import CustomPOSInvoice as BaseCustomPOSInvoice
	BaseClass = BaseCustomPOSInvoice
except ImportError:
	BaseClass = POSInvoice


class KPWSCustomPOSInvoice(BaseClass):
	@frappe.whitelist()
	def set_missing_values(self, for_validate=False):
		# Call parent method first
		result = super().set_missing_values(for_validate)
		
		# If it's a return and profile has return_print_format, use that
		if self.is_return and self.pos_profile:
			try:
				profile = frappe.get_cached_doc("POS Profile", self.pos_profile)
				return_print_format = profile.get("return_print_format")
				
				if return_print_format:
					# Verify the print format exists and is for POS Invoice
					print_format_doc = frappe.db.get_value(
						"Print Format",
						return_print_format,
						["name", "doc_type", "disabled"],
						as_dict=True
					)
					
					if print_format_doc and print_format_doc.doc_type == "POS Invoice" and not print_format_doc.disabled:
						if result:
							result["print_format"] = return_print_format
						else:
							result = {"print_format": return_print_format}
						
						# Also set it on the document for print view
						if hasattr(self, 'meta'):
							self.meta.default_print_format = return_print_format
			except Exception as e:
				# Log error for debugging
				frappe.log_error(f"Error setting return print format: {str(e)}", "POS Invoice Return Print Format")
		
		return result
	
	def before_print(self, print_settings=None):
		# Override before_print to set return print format
		if self.is_return and self.pos_profile:
			try:
				profile = frappe.get_cached_doc("POS Profile", self.pos_profile)
				return_print_format = profile.get("return_print_format")
				
				if return_print_format:
					print_format_doc = frappe.db.get_value(
						"Print Format",
						return_print_format,
						["name", "doc_type", "disabled"],
						as_dict=True
					)
					
					if print_format_doc and print_format_doc.doc_type == "POS Invoice" and not print_format_doc.disabled:
						# Set on meta - this is what printview uses
						if hasattr(self, 'meta'):
							self.meta.default_print_format = return_print_format
						# Also store it for later use
						if not hasattr(self, '_return_print_format'):
							self._return_print_format = return_print_format
			except Exception as e:
				frappe.log_error(f"Error in before_print setting return print format: {str(e)}", "POS Invoice Return Print Format")
		
		# Call parent if it exists
		if hasattr(super(), 'before_print'):
			super().before_print(print_settings)

