import frappe
from frappe import _
from frappe.utils import getdate, flt


@frappe.whitelist()
def get_pending_requisition_data(filters):
	"""
	Get pending requisition report data for Material Requests
	"""
	filters = frappe.parse_json(filters)
	
	# Validate required filters
	if not filters.get("date_from") or not filters.get("date_to"):
		frappe.throw(_("Date From and Date To are mandatory"))
	
	date_from = getdate(filters.get("date_from"))
	date_to = getdate(filters.get("date_to"))
	material_request_no = filters.get("material_request_no", "").strip() if filters.get("material_request_no") else ""
	
	# Build conditions
	conditions = [
		"mr.docstatus = 1",
		"mr.transaction_date BETWEEN %(date_from)s AND %(date_to)s"
	]
	
	if material_request_no:
		conditions.append("mr.name = %(material_request_no)s")
	
	conditions_str = " AND ".join(conditions)
	
	# Get Material Request Items
	query = f"""
		SELECT 
			mr.name as material_request_no,
			mr.transaction_date,
			mri.name as material_request_item_name,
			mri.item_code,
			mri.item_name,
			mri.uom,
			mri.qty as request_qty
		FROM `tabMaterial Request` mr
		INNER JOIN `tabMaterial Request Item` mri ON mri.parent = mr.name
		WHERE {conditions_str}
		ORDER BY mr.name, mri.idx
	"""
	
	query_params = {
		"date_from": date_from,
		"date_to": date_to
	}
	if material_request_no:
		query_params["material_request_no"] = material_request_no
	
	items = frappe.db.sql(query, query_params, as_dict=True)
	
	# Get received quantities from Stock Entry
	# Sum total qty by item_code and material_request (not by material_request_item)
	# This ensures we get total qty of the item from all Stock Entries
	material_request_nos = list(set([item.material_request_no for item in items]))
	
	received_qty_map = {}
	if material_request_nos:
		# Get all Stock Entry Details linked to these Material Requests
		# Sum qty by material_request and item_code - get total qty of each item
		# This will sum all rows for the same item_code within the same material_request
		received_qty_query = """
			SELECT 
				COALESCE(sed.material_request, mri.parent) as material_request,
				sed.item_code,
				SUM(sed.qty) as received_qty
			FROM `tabStock Entry Detail` sed
			INNER JOIN `tabStock Entry` se ON se.name = sed.parent
			LEFT JOIN `tabMaterial Request Item` mri ON mri.name = sed.material_request_item
			WHERE se.docstatus = 1
				AND (
					sed.material_request IN %(material_requests)s
					OR mri.parent IN %(material_requests)s
				)
				AND sed.item_code IS NOT NULL
				AND sed.item_code != ''
			GROUP BY COALESCE(sed.material_request, mri.parent), sed.item_code
		"""
		
		received_qty_results = frappe.db.sql(
			received_qty_query,
			{"material_requests": material_request_nos},
			as_dict=True
		)
		
		# Create map with key as (material_request, item_code)
		for result in received_qty_results:
			if result.material_request and result.item_code:
				key = (result.material_request, result.item_code)
				received_qty_map[key] = flt(result.received_qty or 0)
	
	# Group by Material Request No
	material_request_data = {}
	
	for item in items:
		mr_no = item.material_request_no
		item_code = item.item_code
		
		# Get received qty from Stock Entry by item_code and material_request
		key = (mr_no, item_code)
		received_qty = received_qty_map.get(key, 0)
		request_qty = flt(item.request_qty or 0)
		pending_qty = request_qty - received_qty
		
		if mr_no not in material_request_data:
			material_request_data[mr_no] = {
				"material_request_no": mr_no,
				"transaction_date": item.transaction_date,
				"items": []
			}
		
		material_request_data[mr_no]["items"].append({
			"item_code": item.item_code or "-",
			"item_name": item.item_name or item.item_code or "-",
			"uom": item.uom or "-",
			"request_qty": request_qty,
			"received_qty": received_qty,
			"pending_qty": pending_qty
		})
	
	# Convert to list
	material_requests_list = []
	for mr_key, mr_info in sorted(material_request_data.items()):
		material_requests_list.append(mr_info)
	
	return {
		"material_requests": material_requests_list
	}


def get_context(context):
	"""Context for the page template"""
	return context

