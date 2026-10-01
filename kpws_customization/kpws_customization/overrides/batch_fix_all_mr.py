# Copyright (c) 2025, Kpws Customization
# License: MIT

"""
Batch fix script - Run this once to fix ALL Material Requests
Copy paste this entire code in bench console
"""

BATCH_FIX_CODE = """
import frappe
from frappe.query_builder.functions import Sum

print("\\n" + "="*60)
print("BATCH FIX: All Material Requests")
print("="*60 + "\\n")

# Get all Material Transfer Requests
material_requests = frappe.get_all(
    "Material Request",
    filters={
        "material_request_type": ["in", ["Material Transfer", "Material Issue", "Customer Provided"]],
        "docstatus": 1
    },
    fields=["name"]
)

print(f"Found {len(material_requests)} Material Requests to fix\\n")

fixed = 0
errors = 0

for idx, mr in enumerate(material_requests, 1):
    mr_name = mr.name
    print(f"[{idx}/{len(material_requests)}] {mr_name}...", end=" ")
    
    try:
        # Get Material Request
        mr_doc = frappe.get_doc("Material Request", mr_name)
        mr_items = [d.name for d in mr_doc.get("items")]
        
        # Build query
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
        
        # Convert to dict
        mr_items_ordered_qty = {}
        for d in result:
            mr_items_ordered_qty[d.material_request_item] = d.qty
        
        # Update items
        updated = False
        for item in mr_doc.items:
            if item.name in mr_items_ordered_qty:
                new_qty = mr_items_ordered_qty[item.name]
                if item.ordered_qty != new_qty:
                    frappe.db.set_value("Material Request Item", item.name, "ordered_qty", new_qty)
                    updated = True
            else:
                if item.ordered_qty != 0:
                    frappe.db.set_value("Material Request Item", item.name, "ordered_qty", 0)
                    updated = True
        
        # Update percentage if needed
        if updated:
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
        fixed += 1
        print("✓")
        
    except Exception as e:
        errors += 1
        print(f"✗ {str(e)}")
        frappe.log_error(f"Error fixing MR {mr_name}: {str(e)}", "Batch Fix MR")

print("\\n" + "="*60)
print(f"✓ Fixed: {fixed}")
print(f"✗ Errors: {errors}")
print(f"Total: {len(material_requests)}")
print("="*60)
print("\\nDone! Refresh your browser to see updated values.")
"""

