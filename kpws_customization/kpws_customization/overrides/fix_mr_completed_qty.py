# Copyright (c) 2025, Kpws Customization
# License: MIT

"""
Direct fix script to update Material Request completed qty
This bypasses the override and directly updates using the correct query
"""

import frappe
from frappe.query_builder.functions import Sum
from frappe.cache_manager import clear_controller_cache


@frappe.whitelist()
def fix_material_request_completed_qty(mr_name):
	"""Fix completed qty for a specific Material Request"""
	try:
		mr_doc = frappe.get_doc("Material Request", mr_name)
		
		if mr_doc.material_request_type not in ("Material Issue", "Material Transfer", "Customer Provided"):
			print(f"Material Request type is {mr_doc.material_request_type}, skipping...")
			return
		
		print(f"\nFixing Material Request: {mr_name}")
		print(f"Type: {mr_doc.material_request_type}")
		
		# Get all MR items
		mr_items = [d.name for d in mr_doc.get("items")]
		print(f"MR Items: {mr_items}")
		
		# Build query with correct join
		doctype = frappe.qb.DocType("Stock Entry Detail")
		stock_entry = frappe.qb.DocType("Stock Entry")
		
		query = (
			frappe.qb.from_(doctype)
			.inner_join(stock_entry)
			.on(doctype.parent == stock_entry.name)
			.select(doctype.material_request_item, Sum(doctype.transfer_qty).as_("qty"))
			.where(
				(doctype.material_request == mr_name)
				& (doctype.material_request_item.isin(mr_items))
				& (stock_entry.docstatus == 1)
			)
			.groupby(doctype.material_request_item)
		)
		
		# Run query
		result = query.run(as_dict=True)
		print(f"\nQuery Result: {result}")
		
		# Convert to dict
		mr_items_ordered_qty = {}
		for d in result:
			mr_items_ordered_qty[d.material_request_item] = d.qty
		
		print(f"Ordered Qty Dict: {mr_items_ordered_qty}")
		
		# Update each item
		updated_count = 0
		for item in mr_doc.items:
			if item.name in mr_items_ordered_qty:
				old_qty = item.ordered_qty
				new_qty = mr_items_ordered_qty[item.name]
				
				if old_qty != new_qty:
					frappe.db.set_value(
						"Material Request Item",
						item.name,
						"ordered_qty",
						new_qty
					)
					print(f"  Updated {item.item_code}: {old_qty} -> {new_qty}")
					updated_count += 1
				else:
					print(f"  No change for {item.item_code}: {old_qty}")
			else:
				# No stock entries found, set to 0
				if item.ordered_qty != 0:
					frappe.db.set_value(
						"Material Request Item",
						item.name,
						"ordered_qty",
						0
					)
					print(f"  Set {item.item_code} to 0 (no stock entries)")
					updated_count += 1
		
		# Update percentage
		mr_doc.reload()
		mr_doc._update_percent_field(
			{
				"target_dt": "Material Request Item",
				"target_parent_dt": "Material Request",
				"target_parent_field": "per_ordered",
				"target_ref_field": "stock_qty",
				"target_field": "ordered_qty",
				"name": mr_name,
			},
			True,
		)
		
		frappe.db.commit()
		
		print(f"\n✓ Updated {updated_count} items for Material Request: {mr_name}")
		return True
		
	except Exception as e:
		import traceback
		frappe.log_error(f"Error fixing MR {mr_name}: {str(e)}\n{traceback.format_exc()}", "Fix MR Completed Qty")
		print(f"Error: {str(e)}")
		print(traceback.format_exc())
		return False


@frappe.whitelist()
def fix_all_material_requests():
	"""Fix all Material Transfer Requests at once"""
	material_requests = frappe.get_all(
		"Material Request",
		filters={
			"material_request_type": ["in", ["Material Transfer", "Material Issue", "Customer Provided"]],
			"docstatus": 1
		},
		fields=["name"]
	)
	
	print(f"\n{'='*60}")
	print(f"Fixing {len(material_requests)} Material Requests...")
	print(f"{'='*60}\n")
	
	fixed = 0
	errors = 0
	
	for idx, mr in enumerate(material_requests, 1):
		print(f"[{idx}/{len(material_requests)}] Processing {mr.name}...", end=" ")
		try:
			if fix_material_request_completed_qty(mr.name):
				fixed += 1
				print("✓")
			else:
				errors += 1
				print("✗")
		except Exception as e:
			errors += 1
			print(f"✗ Error: {str(e)}")
			frappe.log_error(f"Error fixing MR {mr.name}: {str(e)}", "Fix All MR Completed Qty")
	
	print(f"\n{'='*60}")
	print(f"✓ Fixed: {fixed}")
	print(f"✗ Errors: {errors}")
	print(f"Total: {len(material_requests)}")
	print(f"{'='*60}\n")
	
	return {"fixed": fixed, "errors": errors, "total": len(material_requests)}

