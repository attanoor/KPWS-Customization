import frappe
from frappe import _
from frappe.utils import getdate, flt


@frappe.whitelist()
def get_pending_supplier_purchase_data(filters):
	"""
	Get pending supplier purchase order data
	"""
	filters = frappe.parse_json(filters)
	
	# Validate required filters
	if not filters.get("date_from") or not filters.get("date_to"):
		frappe.throw(_("Date From and Date To are mandatory"))
	
	date_from = getdate(filters.get("date_from"))
	date_to = getdate(filters.get("date_to"))
	supplier = filters.get("supplier", "").strip() if filters.get("supplier") else ""
	
	# Build conditions for Purchase Order
	conditions = [
		"po.docstatus = 1",
		"po.transaction_date BETWEEN %(date_from)s AND %(date_to)s"
	]
	
	if supplier:
		conditions.append("po.supplier = %(supplier)s")
	
	conditions_str = " AND ".join(conditions)
	
	# Get Purchase Order Items with received quantities
	query = f"""
		SELECT 
			po.supplier,
			po.name as po_number,
			po.transaction_date as po_date,
			poi.item_code,
			poi.item_name,
			poi.qty as qty_ordered,
			poi.received_qty as qty_received,
			poi.qty - poi.received_qty as pending_qty
		FROM `tabPurchase Order` po
		INNER JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
		WHERE {conditions_str}
			AND (poi.qty - poi.received_qty) > 0
		ORDER BY po.supplier, po.transaction_date, po.name, poi.idx
	"""
	
	query_params = {
		"date_from": date_from,
		"date_to": date_to
	}
	if supplier:
		query_params["supplier"] = supplier
	
	po_items = frappe.db.sql(query, query_params, as_dict=True)
	
	# Group by Supplier
	supplier_data = {}
	
	for item in po_items:
		supplier_name = item.supplier or "Unknown"
		
		if supplier_name not in supplier_data:
			# Get supplier details using direct SQL to avoid field issues
			supplier_info = frappe.db.sql("""
				SELECT supplier_name, mobile_no, email_id
				FROM `tabSupplier`
				WHERE name = %(supplier_name)s
				LIMIT 1
			""", {"supplier_name": supplier_name}, as_dict=True)
			
			supplier_info = supplier_info[0] if supplier_info else {}
			
			supplier_data[supplier_name] = {
				"supplier_name": supplier_info.get("supplier_name") or supplier_name,
				"phone": supplier_info.get("mobile_no") or "-",
				"email": supplier_info.get("email_id") or "-",
				"items": []
			}
		
		# Get Purchase Receipt numbers for this PO Item
		# First get the PO Item name
		po_item_name = frappe.db.get_value(
			"Purchase Order Item",
			{"parent": item.po_number, "item_code": item.item_code},
			"name"
		)
		
		purchase_receipt_nos = []
		if po_item_name:
			pr_items = frappe.db.sql("""
				SELECT DISTINCT pri.parent as purchase_receipt_no
				FROM `tabPurchase Receipt Item` pri
				INNER JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
				WHERE pri.purchase_order_item = %(po_item_name)s
					AND pr.docstatus = 1
					AND pr.is_return = 0
				ORDER BY pr.posting_date, pr.name
			""", {"po_item_name": po_item_name}, as_dict=True)
			
			if pr_items:
				purchase_receipt_nos = [pr["purchase_receipt_no"] for pr in pr_items]
		
		purchase_receipt_no_str = ", ".join(purchase_receipt_nos) if purchase_receipt_nos else "-"
		
		supplier_data[supplier_name]["items"].append({
			"item_name": item.item_name or item.item_code or "-",
			"po_number": item.po_number,
			"po_date": item.po_date,
			"qty_ordered": flt(item.qty_ordered or 0),
			"qty_received": flt(item.qty_received or 0),
			"purchase_receipt_no": purchase_receipt_no_str,
			"pending_qty": flt(item.pending_qty or 0)
		})
	
	# Convert to list
	suppliers_list = []
	for supplier_key, supplier_info in sorted(supplier_data.items()):
		suppliers_list.append(supplier_info)
	
	return {
		"suppliers": suppliers_list
	}


def get_context(context):
	"""Context for the page template"""
	return context

