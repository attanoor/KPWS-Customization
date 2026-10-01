import frappe
from frappe import _
from frappe.utils import flt


@frappe.whitelist()
def get_formulary_report_data(filters):
	"""
	Get formulary report data with all item details and prices
	"""
	filters = frappe.parse_json(filters)
	
	# Build conditions for Item
	conditions = ["item.disabled = 0"]
	
	# Optional filters
	if filters.get("custom_drug_category"):
		conditions.append("item.custom_drug_category = %(custom_drug_category)s")
	
	if filters.get("custom_manufacturerorigin"):
		conditions.append("item.custom_manufacturerorigin = %(custom_manufacturerorigin)s")
	
	if filters.get("custom_drug_consumtion_type"):
		conditions.append("item.custom_drug_consumtion_type = %(custom_drug_consumtion_type)s")
	
	if filters.get("custom_manufacturer"):
		conditions.append("item.custom_manufacturer = %(custom_manufacturer)s")
	
	if filters.get("custom_generic"):
		conditions.append("item.custom_generic = %(custom_generic)s")
	
	# Warehouse filter for Bin
	warehouse_condition = ""
	if filters.get("warehouse"):
		warehouse_condition = "AND bin.warehouse = %(warehouse)s"
	
	conditions_str = " AND ".join(conditions)
	
	# Get all items with their details
	query = f"""
		SELECT 
			item.name as item_code,
			item.item_name,
			item.custom_drug_category,
			item.custom_manufacturerorigin,
			item.custom_drug_consumtion_type,
			item.custom_manufacturer,
			item.custom_generic,
			item.stock_uom,
			COALESCE(SUM(bin.actual_qty), 0) as total_qty
		FROM `tabItem` item
		LEFT JOIN `tabBin` bin ON bin.item_code = item.name {warehouse_condition}
		WHERE {conditions_str}
		GROUP BY item.name
		ORDER BY item.item_name, item.name
	"""
	
	query_params = {}
	if filters.get("custom_drug_category"):
		query_params["custom_drug_category"] = filters.get("custom_drug_category")
	if filters.get("custom_manufacturerorigin"):
		query_params["custom_manufacturerorigin"] = filters.get("custom_manufacturerorigin")
	if filters.get("custom_drug_consumtion_type"):
		query_params["custom_drug_consumtion_type"] = filters.get("custom_drug_consumtion_type")
	if filters.get("custom_manufacturer"):
		query_params["custom_manufacturer"] = filters.get("custom_manufacturer")
	if filters.get("custom_generic"):
		query_params["custom_generic"] = filters.get("custom_generic")
	if filters.get("warehouse"):
		query_params["warehouse"] = filters.get("warehouse")
	
	items = frappe.db.sql(query, query_params, as_dict=True)
	
	# Price list names
	price_lists = {
		"mrp": "MRP - Maximum Retail Price",
		"tp": "TP - Trade Price",
		"pp": "PP - Purchase Price",
		"spw": "SPW - Selling Price Welfare",
		"spc": "SPC - Selling Price Cash",
		"spp": "SPP - Selling Price Panel"
	}
	
	# Process items and get prices
	report_data = []
	
	for item in items:
		item_code = item.get("item_code")
		
		# Get prices from Item Price
		mrp = get_price_from_list(item_code, price_lists["mrp"])
		tp = get_price_from_list(item_code, price_lists["tp"])
		pp = get_price_from_list(item_code, price_lists["pp"])
		spw = get_price_from_list(item_code, price_lists["spw"])
		spc = get_price_from_list(item_code, price_lists["spc"])
		spp = get_price_from_list(item_code, price_lists["spp"])
		
		# Calculate percentages from PP
		spw_perc = calculate_percentage(pp, spw) if pp and pp > 0 else 0
		spc_perc = calculate_percentage(pp, spc) if pp and pp > 0 else 0
		spp_perc = calculate_percentage(pp, spp) if pp and pp > 0 else 0
		
		report_data.append({
			"item_code": item_code or "-",
			"item_name": item.get("item_name") or item_code or "-",
			"custom_drug_category": item.get("custom_drug_category") or "-",
			"custom_manufacturerorigin": item.get("custom_manufacturerorigin") or "-",
			"custom_drug_consumtion_type": item.get("custom_drug_consumtion_type") or "-",
			"custom_manufacturer": item.get("custom_manufacturer") or "-",
			"custom_generic": item.get("custom_generic") or "-",
			"total_qty": flt(item.get("total_qty") or 0),
			"uom": item.get("stock_uom") or "-",
			"mrp": flt(mrp or 0),
			"tp": flt(tp or 0),
			"pp": flt(pp or 0),
			"spw": flt(spw or 0),
			"spw_perc": flt(spw_perc, 2),
			"spc": flt(spc or 0),
			"spc_perc": flt(spc_perc, 2),
			"spp": flt(spp or 0),
			"spp_perc": flt(spp_perc, 2)
		})
	
	return {
		"items": report_data
	}


def get_price_from_list(item_code, price_list_name):
	"""
	Get price from a specific price list for an item
	"""
	if not item_code or not price_list_name:
		return None
	
	# Try to find price list with similar name if exact match not found
	actual_price_list = price_list_name
	if not frappe.db.exists("Price List", price_list_name):
		# Try to find price list with similar name
		similar_lists = frappe.db.sql("""
			SELECT name FROM `tabPrice List` 
			WHERE name LIKE %s OR name LIKE %s
			LIMIT 1
		""", (f"%{price_list_name.split(' - ')[0]}%", f"%{price_list_name.split(' - ')[-1]}%"), as_dict=True)
		
		if similar_lists:
			actual_price_list = similar_lists[0].name
		else:
			return None
	
	price = frappe.db.get_value(
		"Item Price",
		{
			"item_code": item_code,
			"price_list": actual_price_list
		},
		"price_list_rate"
	)
	
	return flt(price) if price else None


def calculate_percentage(base_value, target_value):
	"""
	Calculate percentage: ((target_value - base_value) / base_value) * 100
	"""
	if not base_value or base_value == 0:
		return 0
	
	if not target_value:
		return 0
	
	return ((flt(target_value) - flt(base_value)) / flt(base_value)) * 100


def get_context(context):
	"""Context for the page template"""
	return context

