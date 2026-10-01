# Copyright (c) 2025, Kpws Customization
# License: MIT

import frappe


# Save original function BEFORE monkey patching
_original_get_print_format_doc = None
_in_override = False


def override_get_print_format_doc(print_format_name, meta):
	"""Override to set return print format for POS Invoice returns"""
	global _in_override, _original_get_print_format_doc
	
	# Prevent recursion
	if _in_override:
		# Call original directly
		return _original_get_print_format_doc(print_format_name, meta)
	
	_in_override = True
	
	try:
		# Only override if it's a POS Invoice and no format is specified
		if meta.doctype == "POS Invoice" and not print_format_name and not frappe.form_dict.get("format"):
			# Check if we have a document name to check if it's a return
			doc_name = frappe.form_dict.get("name")
			if doc_name:
				try:
					doc = frappe.get_cached_doc("POS Invoice", doc_name)
					if doc.is_return and doc.pos_profile:
						profile = frappe.get_cached_doc("POS Profile", doc.pos_profile)
						return_print_format = profile.get("return_print_format")
						
						if return_print_format:
							# Verify the print format exists
							print_format_doc = frappe.db.get_value(
								"Print Format",
								return_print_format,
								["name", "doc_type", "disabled"],
								as_dict=True
							)
							
							if print_format_doc and print_format_doc.doc_type == "POS Invoice" and not print_format_doc.disabled:
								# Set it on meta so it's used
								meta.default_print_format = return_print_format
				except Exception as e:
					frappe.log_error(f"Error in override_get_print_format_doc: {str(e)}", "POS Invoice Return Print Format")
		
		# Call original function
		return _original_get_print_format_doc(print_format_name, meta)
	finally:
		_in_override = False


# Monkey patch the function when module is imported
def setup_printview_override():
	import frappe.www.printview as printview_module
	global _original_get_print_format_doc
	
	if not hasattr(printview_module, '_kpws_override_applied'):
		# Save original BEFORE patching
		_original_get_print_format_doc = printview_module.get_print_format_doc
		printview_module.get_print_format_doc = override_get_print_format_doc
		printview_module._kpws_override_applied = True

# Apply the override
setup_printview_override()

