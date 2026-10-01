# Copyright (c) 2025, Kpws Customization
# License: MIT

"""
Test script to verify Material Request override is working
Run this in bench console to test
"""

import frappe
from frappe.cache_manager import clear_controller_cache
from frappe.query_builder.functions import Sum


def test_override_loading():
	"""Test if override is loaded"""
	from frappe.model.base_document import get_controller
	
	# Clear cache
	frappe.cache().delete_value("app_hooks")
	clear_controller_cache("Material Request")
	frappe.clear_cache(doctype="Material Request")
	
	# Get controller
	controller = get_controller("Material Request")
	print(f"Controller class: {controller}")
	print(f"Module: {controller.__module__}")
	print(f"Class name: {controller.__name__}")
	
	# Check if it's our custom class
	if "KPWSCustomMaterialRequest" in controller.__name__:
		print("✓ Override is loaded correctly!")
		return True
	else:
		print("✗ Override is NOT loaded. Using default MaterialRequest class.")
		return False


def test_query_directly(mr_name):
	"""Test the query directly to see what it returns"""
	mr_doc = frappe.get_doc("Material Request", mr_name)
	
	print(f"\nTesting query for Material Request: {mr_name}")
	print(f"Material Request Type: {mr_doc.material_request_type}")
	
	if mr_doc.material_request_type not in ("Material Issue", "Material Transfer", "Customer Provided"):
		print("Not a Material Transfer/Issue type. Skipping query test.")
		return
	
	# Get all MR items
	mr_items = [d.name for d in mr_doc.get("items")]
	print(f"MR Items: {mr_items}")
	
	# Build query manually
	doctype = frappe.qb.DocType("Stock Entry Detail")
	stock_entry = frappe.qb.DocType("Stock Entry")
	qty_field = doctype.transfer_qty
	
	query = (
		frappe.qb.from_(doctype)
		.inner_join(stock_entry)
		.on(doctype.parent == stock_entry.name)
		.select(doctype.material_request_item, Sum(qty_field).as_("qty"))
		.where(
			(doctype.material_request == mr_name)
			& (doctype.material_request_item.isin(mr_items))
			& (stock_entry.docstatus == 1)
		)
		.groupby(doctype.material_request_item)
	)
	
	# Print SQL
	print(f"\nSQL Query:")
	print(str(query))
	
	# Run query
	result = query.run(as_dict=True)
	print(f"\nQuery Result: {result}")
	
	# Convert to dict
	mr_items_ordered_qty = {}
	for d in result:
		mr_items_ordered_qty[d.material_request_item] = d.qty
	
	print(f"\nConverted Dict: {mr_items_ordered_qty}")
	
	# Check what the override method returns
	print(f"\nTesting override method:")
	ordered_qty_dict = mr_doc.get_mr_items_ordered_qty(mr_items)
	print(f"Override method result: {ordered_qty_dict}")
	
	# Compare with current ordered_qty
	print(f"\nCurrent ordered_qty in items:")
	for item in mr_doc.items:
		print(f"  {item.item_code}: ordered_qty={item.ordered_qty}, qty={item.qty}, name={item.name}")


def full_test(mr_name):
	"""Run full test"""
	print("=" * 60)
	print("TESTING MATERIAL REQUEST OVERRIDE")
	print("=" * 60)
	
	# Test 1: Override loading
	print("\n1. Testing Override Loading:")
	print("-" * 60)
	is_loaded = test_override_loading()
	
	if not is_loaded:
		print("\n⚠️  Override is not loaded. Please check hooks.py and restart bench.")
		return
	
	# Test 2: Query test
	print("\n2. Testing Query Directly:")
	print("-" * 60)
	test_query_directly(mr_name)
	
	print("\n" + "=" * 60)
	print("TEST COMPLETE")
	print("=" * 60)

