# Copyright (c) 2025, Kpws Customization
# License: MIT

import frappe
from frappe import db, qb


# Save original function BEFORE monkey patching
_original_make_property_setter = None
_in_override = False
_patch_applied = False


def override_make_property_setter(
	args, ignore_validate=False, validate_fields_for_doctype=True, is_system_generated=True
):
	"""Override to fix AttributeError: 'PropertySetter' object has no attribute 'validate_fieldtype_change'"""
	global _in_override, _original_make_property_setter, _patch_applied
	
	# Ensure patch is applied (lazy loading)
	if not _patch_applied:
		setup_frappe_init_override()
	
	# Prevent recursion - if we're already in override and have original, use it
	if _in_override:
		if _original_make_property_setter:
			# Call original directly
			return _original_make_property_setter(args, ignore_validate, validate_fields_for_doctype, is_system_generated)
		else:
			# Fallback: if original not available, continue with our implementation
			pass
	
	_in_override = True
	
	try:
		# Replicate the original function's logic but with safety check for validate_fieldtype_change
		args = frappe._dict(args)
		if not args.doctype_or_field:
			args.doctype_or_field = "DocField"
			if not args.property_type:
				args.property_type = (
					db.get_value("DocField", {"parent": "DocField", "fieldname": args.property}, "fieldtype")
					or "Data"
				)

		if not args.doctype:
			DocField_doctype = qb.DocType("DocField")
			doctype_list = (
				qb.from_(DocField_doctype)
				.select(DocField_doctype.parent)
				.where(DocField_doctype.fieldname == args.fieldname)
				.distinct()
			).run(pluck=True)
		else:
			doctype_list = [args.doctype]

		for doctype in doctype_list:
			if not args.property_type:
				args.property_type = (
					db.get_value("DocField", {"parent": doctype, "fieldname": args.fieldname}, "fieldtype")
					or "Data"
				)

			ps = frappe.get_doc(
				{
					"doctype": "Property Setter",
					"doctype_or_field": args.doctype_or_field,
					"doc_type": doctype,
					"field_name": args.fieldname,
					"row_name": args.row_name,
					"property": args.property,
					"value": args.value,
					"property_type": args.property_type or "Data",
					"is_system_generated": is_system_generated,
					"__islocal": 1,
				}
			)
			ps.flags.ignore_validate = ignore_validate
			ps.flags.validate_fields_for_doctype = validate_fields_for_doctype
			# Safety check: only call if method exists
			if hasattr(ps, 'validate_fieldtype_change'):
				ps.validate_fieldtype_change()
			ps.insert()
	finally:
		_in_override = False


# Monkey patch the function when module is imported
def setup_frappe_init_override():
	global _original_make_property_setter, _patch_applied
	
	if _patch_applied:
		return
		
	try:
		# Patch via frappe namespace (this should work as frappe.make_property_setter points to the function)
		if hasattr(frappe, 'make_property_setter'):
			# Save original BEFORE patching
			_original_make_property_setter = frappe.make_property_setter
			frappe.make_property_setter = override_make_property_setter
			_patch_applied = True
			
			# Also try to patch at the module level if possible
			try:
				import sys
				frappe_module = sys.modules.get('frappe')
				if frappe_module and hasattr(frappe_module, 'make_property_setter'):
					frappe_module.make_property_setter = override_make_property_setter
			except:
				pass
	except Exception as e:
		# If patch fails, log but don't crash
		try:
			frappe.log_error(f"Failed to patch make_property_setter: {str(e)}", "KPWS Property Setter Patch")
		except:
			pass


# Try to apply the override immediately
try:
	setup_frappe_init_override()
except:
	# If it fails, it will be applied lazily on first call
	pass

