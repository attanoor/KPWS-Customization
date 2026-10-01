import frappe
from frappe import _
from frappe.utils import getdate, flt


@frappe.whitelist()
def get_item_wise_average_price_data(filters):
	"""
	Get item-wise average price data grouped by Generic Name
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
	
	# Get Purchase Receipt Items with aggregated data
	query = f"""
		SELECT 
			item.custom_generic as generic_name,
			pri.item_code,
			pri.item_name,
			COALESCE(po.supplier, pr.supplier) as supplier_name,
			SUM(pri.qty) as total_qty,
			SUM(pri.base_amount) as total_amount,
			AVG(pri.base_rate) as avg_rate
		FROM `tabPurchase Receipt` pr
		INNER JOIN `tabPurchase Receipt Item` pri ON pri.parent = pr.name
		INNER JOIN `tabItem` item ON item.name = pri.item_code
		LEFT JOIN `tabPurchase Order` po ON po.name = pri.purchase_order
		WHERE {conditions_str}
		{item_condition_str}
		GROUP BY item.custom_generic, pri.item_code, pri.item_name, COALESCE(po.supplier, pr.supplier)
		ORDER BY item.custom_generic, pri.item_name, COALESCE(po.supplier, pr.supplier)
	"""
	
	query_params = {
		"date_from": date_from,
		"date_to": date_to
	}
	if generic_name:
		query_params["generic_name"] = generic_name
	
	items = frappe.db.sql(query, query_params, as_dict=True)
	
	# Process and format data
	report_data = []
	s_no = 1
	
	for item in items:
		generic = item.generic_name or "Unknown"
		qty = flt(item.total_qty or 0)
		avg_rate = flt(item.avg_rate or 0)
		amount = flt(item.total_amount or 0)
		
		report_data.append({
			"s_no": s_no,
			"generic_name": generic,
			"item_name": item.item_name or item.item_code or "-",
			"supplier_name": item.supplier_name or "-",
			"qty": qty,
			"avg_rate": avg_rate,
			"amount": amount
		})
		
		s_no += 1
	
	return {
		"data": report_data
	}


def get_context(context):
	"""Context for the page template"""
	return context

