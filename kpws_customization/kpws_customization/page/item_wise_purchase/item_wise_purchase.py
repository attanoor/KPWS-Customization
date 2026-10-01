import frappe
from frappe import _
from frappe.utils import getdate, flt, get_datetime


@frappe.whitelist()
def get_item_wise_purchase_data(filters):
	"""
	Get item-wise purchase data grouped by Generic Name
	"""
	filters = frappe.parse_json(filters)
	
	# Validate required filters
	if not filters.get("date_from") or not filters.get("date_to"):
		frappe.throw(_("Date From and Date To are mandatory"))
	
	date_from = getdate(filters.get("date_from"))
	date_to = getdate(filters.get("date_to"))
	generic_name = filters.get("generic_name", "").strip() if filters.get("generic_name") else ""
	
	# Build conditions for Purchase Receipt
	conditions = [
		"pr.docstatus = 1",
		"pr.posting_date BETWEEN %(date_from)s AND %(date_to)s",
		"pr.is_return = 0"
	]
	
	# Build conditions for Item (Generic Name filter - using custom_generic field)
	item_conditions = []
	if generic_name:
		item_conditions.append("item.custom_generic = %(generic_name)s")
	
	item_condition_str = ""
	if item_conditions:
		item_condition_str = " AND " + " AND ".join(item_conditions)
	
	conditions_str = " AND ".join(conditions)
	
	# Get Purchase Receipt Items with Purchase Order details
	# Note: We need to get all Purchase Receipts, even if they don't have Purchase Order
	query = f"""
		SELECT 
			item.custom_generic as generic_name,
			pri.item_code,
			pri.item_name,
			COALESCE(po.supplier, pr.supplier) as supplier_name,
			COALESCE(po.name, '') as po_number,
			COALESCE(po.transaction_date, pr.posting_date) as po_date,
			COALESCE(poi.qty, pri.qty) as po_qty,
			pr.name as purchase_receipt_no,
			pr.posting_date as purchase_receipt_date,
			pri.qty as purchase_receipt_qty,
			pri.purchase_order,
			pri.purchase_order_item
		FROM `tabPurchase Receipt` pr
		INNER JOIN `tabPurchase Receipt Item` pri ON pri.parent = pr.name
		INNER JOIN `tabItem` item ON item.name = pri.item_code
		LEFT JOIN `tabPurchase Order` po ON po.name = pri.purchase_order
		LEFT JOIN `tabPurchase Order Item` poi ON poi.name = pri.purchase_order_item
		WHERE {conditions_str}
		{item_condition_str}
		ORDER BY item.custom_generic, pr.posting_date, pr.name, pri.idx
	"""
	
	query_params = {
		"date_from": date_from,
		"date_to": date_to
	}
	if generic_name:
		query_params["generic_name"] = generic_name
	
	items = frappe.db.sql(query, query_params, as_dict=True)
	
	# Get Trade Price from Price List "TP - Trade Price"
	price_list_name = "TP - Trade Price"
	
	# Group by Generic Name
	generic_name_data = {}
	
	for item in items:
		generic = item.generic_name or "Unknown"
		
		if generic not in generic_name_data:
			generic_name_data[generic] = {
				"generic_name": generic,
				"items": []
			}
		
		# Get Trade Price for this item
		trade_price = 0
		if item.item_code:
			price = frappe.db.get_value(
				"Item Price",
				{
					"item_code": item.item_code,
					"price_list": price_list_name
				},
				"price_list_rate"
			)
			if price:
				trade_price = flt(price)
		
		generic_name_data[generic]["items"].append({
			"item_name": item.item_name or item.item_code or "-",
			"supplier_name": item.supplier_name or "-",
			"po_number": item.po_number or "-",
			"po_date": item.po_date or "-",
			"po_qty": flt(item.po_qty or 0),
			"purchase_receipt_no": item.purchase_receipt_no or "-",
			"purchase_receipt_date": item.purchase_receipt_date or "-",
			"purchase_receipt_qty": flt(item.purchase_receipt_qty or 0),
			"trade_price": trade_price
		})
	
	# Convert to list
	generic_names_list = []
	for generic_key, generic_info in sorted(generic_name_data.items()):
		generic_names_list.append(generic_info)
	
	return {
		"generic_names": generic_names_list
	}


def get_context(context):
	"""Context for the page template"""
	return context

