# Copyright (c) 2025, Kpws Customization
# License: MIT

"""
Script to manually update completed qty for Material Requests
Run this via bench console to fix existing Material Requests

Usage in bench console:
    from kpws_customization.kpws_customization.overrides.update_mr_completed_qty import update_material_request_completed_qty, clear_cache_and_reload
    clear_cache_and_reload()
    update_material_request_completed_qty("MAT-MR-2025-00009")
"""

import frappe
from frappe.cache_manager import clear_controller_cache


def clear_cache_and_reload():
	"""Clear controller cache and app hooks cache to reload override"""
	frappe.cache().delete_value("app_hooks")
	clear_controller_cache("Material Request")
	frappe.clear_cache(doctype="Material Request")
	print("Cache cleared. Override should now be loaded.")


@frappe.whitelist()
def update_material_request_completed_qty(mr_name):
	"""Update completed qty for a specific Material Request"""
	try:
		# Clear cache first
		clear_cache_and_reload()
		
		# Verify override is being used
		from frappe.model.base_document import get_controller
		controller = get_controller("Material Request")
		print(f"Using controller: {controller}")
		print(f"Is KPWSCustomMaterialRequest: {'KPWSCustomMaterialRequest' in str(controller)}")
		
		# Reload the document to use the new override
		mr_doc = frappe.get_doc("Material Request", mr_name)
		
		# Check current ordered_qty before update
		print("\nBefore update:")
		for item in mr_doc.items:
			print(f"  Item {item.item_code}: ordered_qty = {item.ordered_qty}, qty = {item.qty}")
		
		# Update completed qty
		mr_doc.update_completed_qty()
		
		# Reload to see updated values
		mr_doc.reload()
		
		# Check ordered_qty after update
		print("\nAfter update:")
		for item in mr_doc.items:
			print(f"  Item {item.item_code}: ordered_qty = {item.ordered_qty}, qty = {item.qty}")
		
		frappe.db.commit()
		
		print(f"\nUpdated completed qty for Material Request: {mr_name}")
		return True
	except Exception as e:
		import traceback
		frappe.log_error(f"Error updating MR {mr_name}: {str(e)}\n{traceback.format_exc()}", "Update MR Completed Qty")
		print(f"Error: {str(e)}")
		print(traceback.format_exc())
		return False


@frappe.whitelist()
def update_all_material_requests_completed_qty():
	"""Update completed qty for all Material Transfer Requests"""
	clear_cache_and_reload()
	
	material_requests = frappe.get_all(
		"Material Request",
		filters={
			"material_request_type": ["in", ["Material Transfer", "Material Issue", "Customer Provided"]],
			"docstatus": 1
		},
		fields=["name"]
	)
	
	updated = 0
	for mr in material_requests:
		try:
			mr_doc = frappe.get_doc("Material Request", mr.name)
			mr_doc.update_completed_qty()
			updated += 1
			frappe.db.commit()
		except Exception as e:
			frappe.log_error(f"Error updating MR {mr.name}: {str(e)}", "Update MR Completed Qty")
	
	print(f"Updated {updated} Material Requests")
	return updated

