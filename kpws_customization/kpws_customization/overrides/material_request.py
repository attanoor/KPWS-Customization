# Copyright (c) 2025, Kpws Customization
# License: MIT

import frappe
from frappe.query_builder.functions import Sum
from erpnext.stock.doctype.material_request.material_request import MaterialRequest


class KPWSCustomMaterialRequest(MaterialRequest):
	def get_mr_items_ordered_qty(self, mr_items):
		"""
		Override to fix completed qty calculation by joining with parent Stock Entry
		to check docstatus correctly
		"""
		# Debug: Log that override is being called
		frappe.logger().debug(f"KPWSCustomMaterialRequest.get_mr_items_ordered_qty called for MR: {self.name}")
		
		mr_items_ordered_qty = {}
		mr_items = [d.name for d in self.get("items") if d.name in mr_items]

		doctype = qty_field = None
		if self.material_request_type in ("Material Issue", "Material Transfer", "Customer Provided"):
			doctype = frappe.qb.DocType("Stock Entry Detail")
			qty_field = doctype.transfer_qty
		elif self.material_request_type == "Manufacture":
			doctype = frappe.qb.DocType("Work Order")
			qty_field = doctype.qty

		if doctype and qty_field:
			if self.material_request_type in ("Material Issue", "Material Transfer", "Customer Provided"):
				# Join with parent Stock Entry to check docstatus correctly
				stock_entry = frappe.qb.DocType("Stock Entry")
				query = (
					frappe.qb.from_(doctype)
					.inner_join(stock_entry)
					.on(doctype.parent == stock_entry.name)
					.select(doctype.material_request_item, Sum(qty_field).as_("qty"))
					.where(
						(doctype.material_request == self.name)
						& (doctype.material_request_item.isin(mr_items))
						& (stock_entry.docstatus == 1)
					)
					.groupby(doctype.material_request_item)
				)
				
				# Run query and convert to dict format
				try:
					result = query.run(as_dict=True)
					
					# Debug logging
					frappe.logger().info(f"KPWSCustomMaterialRequest Query Result for MR {self.name}: {result}")
					
					# Convert to dict with material_request_item as key and qty as value
					mr_items_ordered_qty = {}
					for d in result:
						# Ensure we have the key and value
						if d.material_request_item and d.qty is not None:
							mr_items_ordered_qty[d.material_request_item] = d.qty
					
					frappe.logger().info(f"KPWSCustomMaterialRequest Final dict: {mr_items_ordered_qty}")
				except Exception as e:
					frappe.log_error(f"Error in get_mr_items_ordered_qty for MR {self.name}: {str(e)}", "Material Request Override Error")
					# Return empty dict on error
					mr_items_ordered_qty = {}
			else:
				# For Manufacture type, use original logic
				query = (
					frappe.qb.from_(doctype)
					.select(doctype.material_request_item, Sum(qty_field))
					.where(
						(doctype.material_request == self.name)
						& (doctype.material_request_item.isin(mr_items))
						& (doctype.docstatus == 1)
					)
					.groupby(doctype.material_request_item)
				)

				mr_items_ordered_qty = frappe._dict(query.run())

		return mr_items_ordered_qty

