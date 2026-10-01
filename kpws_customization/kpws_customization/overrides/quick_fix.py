# Copyright (c) 2025, Kpws Customization
# License: MIT

"""
Quick fix - Copy paste this in bench console
"""

QUICK_FIX_CODE = """
import frappe
from frappe.query_builder.functions import Sum

mr_name = "MAT-MR-2025-00011"  # Change this to your MR name

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
print("Query Result:", result)

# Convert to dict
mr_items_ordered_qty = {}
for d in result:
    mr_items_ordered_qty[d.material_request_item] = d.qty

print("Ordered Qty Dict:", mr_items_ordered_qty)

# Update items
for item in mr_doc.items:
    if item.name in mr_items_ordered_qty:
        new_qty = mr_items_ordered_qty[item.name]
        print(f"Updating {item.item_code}: {item.ordered_qty} -> {new_qty}")
        frappe.db.set_value("Material Request Item", item.name, "ordered_qty", new_qty)
    else:
        print(f"Setting {item.item_code} to 0 (no stock entries)")
        frappe.db.set_value("Material Request Item", item.name, "ordered_qty", 0)

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
print("Done!")
"""

