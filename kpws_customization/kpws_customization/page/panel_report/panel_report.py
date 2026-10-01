import frappe
from frappe import _
from frappe.utils import getdate, flt, get_datetime


@frappe.whitelist()
def get_panel_report_data(filters):
	"""
	Get panel report data for POS invoices filtered by Panel POS Profile, grouped by customer
	"""
	filters = frappe.parse_json(filters)
	
	# Validate required filters
	if not filters.get("date_from") or not filters.get("date_to"):
		frappe.throw(_("Date From and Date To are mandatory"))
	
	date_from = getdate(filters.get("date_from"))
	date_to = getdate(filters.get("date_to"))
	user = filters.get("user")
	
	# Get Panel POS Profile - assuming it contains "Panel" in the name
	panel_pos_profiles = frappe.db.sql("""
		SELECT name FROM `tabPOS Profile`
		WHERE name LIKE '%Panel%' AND disabled = 0
	""", as_dict=True)
	
	if not panel_pos_profiles:
		frappe.throw(_("No Panel POS Profile found. Please create a POS Profile with 'Panel' in the name."))
	
	panel_pos_profile_names = [p.name for p in panel_pos_profiles]
	
	# Build conditions
	conditions = [
		"pi.docstatus = 1",
		"pi.posting_date BETWEEN %(date_from)s AND %(date_to)s",
		"pi.pos_profile IN %(pos_profiles)s"
	]
	
	if user:
		conditions.append("pi.owner = %(user)s")
	
	conditions_str = " AND ".join(conditions)
	
	# Get POS Invoices
	query = f"""
		SELECT 
			pi.name as pos_invoice,
			pi.posting_date,
			pi.posting_time,
			pi.customer,
			pi.customer_name,
			pi.owner,
			pi.base_grand_total,
			pi.is_return
		FROM `tabPOS Invoice` pi
		WHERE {conditions_str}
		ORDER BY pi.customer_name, pi.posting_date, pi.posting_time, pi.name
	"""
	
	invoices = frappe.db.sql(query, {
		"date_from": date_from,
		"date_to": date_to,
		"pos_profiles": panel_pos_profile_names,
		"user": user
	}, as_dict=True)
	
	# Group invoices by customer (sales and returns separately)
	customer_data = {}
	returns_customer_data = {}
	total_credit = 0
	total_returns = 0
	
	for invoice in invoices:
		customer = invoice.customer or "Unknown"
		customer_name = invoice.customer_name or "Unknown"
		
		# Initialize customer data only for sales (non-returns)
		if not invoice.is_return:
			if customer not in customer_data:
				customer_data[customer] = {
					"customer": customer,
					"customer_name": customer_name,
					"invoices": [],
					"total_amount": 0
				}
		
		# Get patient info
		custom_reference_number = ""
		kpws_number = ""
		patient_name = invoice.customer_name or ""
		
		if invoice.customer:
			patient_doc = frappe.db.sql("""
				SELECT name, patient_name, custom_reference_number
				FROM `tabPatient`
				WHERE customer = %(customer)s
				LIMIT 1
			""", {"customer": invoice.customer}, as_dict=True)
			
			if patient_doc and len(patient_doc) > 0:
				patient_doc = patient_doc[0]
				mr_num = patient_doc.get("custom_reference_number")
				if mr_num is not None and str(mr_num).strip():
					custom_reference_number = str(mr_num).strip()
				if patient_doc.get("name"):
					kpws_number = str(patient_doc.name).strip()
				if patient_doc.get("patient_name"):
					patient_name = patient_doc.patient_name
		
		# If not found by customer, try by customer_name
		if (not custom_reference_number or not kpws_number) and invoice.customer_name:
			customer_name_clean = invoice.customer_name.strip() if invoice.customer_name else ""
			if customer_name_clean:
				# Try exact match first
				patient_doc = frappe.db.sql("""
					SELECT name, patient_name, custom_reference_number, customer
					FROM `tabPatient`
					WHERE TRIM(LOWER(patient_name)) = TRIM(LOWER(%(customer_name)s))
					LIMIT 1
				""", {"customer_name": customer_name_clean}, as_dict=True)
				
				if patient_doc and len(patient_doc) > 0:
					patient_doc = patient_doc[0]
					mr_num = patient_doc.get("custom_reference_number")
					if mr_num and str(mr_num).strip():
						custom_reference_number = str(mr_num).strip()
					if patient_doc.get("name"):
						kpws_number = str(patient_doc.name).strip()
					if patient_doc.get("patient_name"):
						patient_name = patient_doc.patient_name
				
				# If still not found, try LIKE match (partial)
				if not custom_reference_number or not kpws_number:
					patient_doc = frappe.db.sql("""
						SELECT name, patient_name, custom_reference_number, customer
						FROM `tabPatient`
						WHERE TRIM(LOWER(patient_name)) LIKE TRIM(LOWER(%(customer_name)s))
						LIMIT 1
					""", {"customer_name": f"%{customer_name_clean}%"}, as_dict=True)
					
					if patient_doc and len(patient_doc) > 0:
						patient_doc = patient_doc[0]
						mr_num = patient_doc.get("custom_reference_number")
						if mr_num and str(mr_num).strip():
							custom_reference_number = str(mr_num).strip()
						if patient_doc.get("name"):
							kpws_number = str(patient_doc.name).strip()
						if patient_doc.get("patient_name"):
							patient_name = patient_doc.patient_name
		
		amount = flt(invoice.base_grand_total)
		
		invoice_data = {
			"pos_invoice": invoice.pos_invoice,
			"kpws_number": kpws_number,
			"mr_number": custom_reference_number,
			"patient_name": patient_name,
			"amount": amount,
			"posting_date": invoice.posting_date,
			"posting_time": invoice.posting_time
		}
		
		# Separate returns from sales
		if invoice.is_return:
			if customer not in returns_customer_data:
				returns_customer_data[customer] = {
					"customer": customer,
					"customer_name": customer_name,
					"invoices": [],
					"total_amount": 0
				}
			
			returns_customer_data[customer]["invoices"].append(invoice_data)
			returns_customer_data[customer]["total_amount"] += amount
			total_returns += amount
		else:
			customer_data[customer]["invoices"].append(invoice_data)
			customer_data[customer]["total_amount"] += amount
			total_credit += amount
	
	# Convert to list and add serial numbers for sales
	customers_list = []
	for customer_key, customer_info in sorted(customer_data.items(), key=lambda x: x[1]["customer_name"]):
		s_no = 1
		for invoice in customer_info["invoices"]:
			invoice["s_no"] = s_no
			s_no += 1
		customers_list.append(customer_info)
	
	# Convert to list and add serial numbers for returns
	returns_customers_list = []
	for customer_key, customer_info in sorted(returns_customer_data.items(), key=lambda x: x[1]["customer_name"]):
		s_no = 1
		for invoice in customer_info["invoices"]:
			invoice["s_no"] = s_no
			s_no += 1
		returns_customers_list.append(customer_info)
	
	return {
		"customers": customers_list,
		"returns_customers": returns_customers_list,
		"total_credit": total_credit,
		"total_returns": total_returns
	}


def get_context(context):
	"""Context for the page template"""
	return context

