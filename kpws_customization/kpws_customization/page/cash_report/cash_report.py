import frappe
from frappe import _
from frappe.utils import getdate, flt, get_datetime


@frappe.whitelist()
def get_cash_report_data(filters):
	"""
	Get cash report data for POS invoices filtered by Cash POS Profile
	"""
	filters = frappe.parse_json(filters)
	
	# Validate required filters
	if not filters.get("date_from") or not filters.get("date_to"):
		frappe.throw(_("Date From and Date To are mandatory"))
	
	date_from = getdate(filters.get("date_from"))
	date_to = getdate(filters.get("date_to"))
	user = filters.get("user")
	
	# Get Cash POS Profile - assuming it contains "Cash" in the name
	pos_profile_filter = "LIKE '%Cash%'"
	cash_pos_profiles = frappe.db.sql("""
		SELECT name FROM `tabPOS Profile`
		WHERE name LIKE '%Cash%' AND disabled = 0
	""", as_dict=True)
	
	if not cash_pos_profiles:
		frappe.throw(_("No Cash POS Profile found. Please create a POS Profile with 'Cash' in the name."))
	
	cash_pos_profile_names = [p.name for p in cash_pos_profiles]
	
	# Build conditions
	conditions = [
		"pi.docstatus = 1",
		"pi.posting_date BETWEEN %(date_from)s AND %(date_to)s",
		"pi.pos_profile IN %(pos_profiles)s"
	]
	
	if user:
		conditions.append("pi.owner = %(user)s")
	
	conditions_str = " AND ".join(conditions)
	
	# Get POS Invoices (excluding returns)
	query = f"""
		SELECT 
			pi.name as pos_invoice,
			pi.posting_date,
			pi.posting_time,
			pi.customer,
			pi.customer_name,
			pi.owner,
			pi.grand_total,
			pi.base_grand_total,
			pi.is_return,
			pi.return_against,
			pi.base_change_amount
		FROM `tabPOS Invoice` pi
		WHERE {conditions_str}
		ORDER BY pi.posting_date, pi.posting_time, pi.name
	"""
	
	invoices = frappe.db.sql(query, {
		"date_from": date_from,
		"date_to": date_to,
		"pos_profiles": cash_pos_profile_names,
		"user": user
	}, as_dict=True)
	
	# Get payment details for each invoice
	invoice_names = [inv.pos_invoice for inv in invoices]
	
	# Also get return_against invoice names for returns
	return_against_invoices = [inv.return_against for inv in invoices if inv.is_return and inv.return_against]
	all_invoice_names = list(set(invoice_names + return_against_invoices))
	
	payments_data = {}
	if all_invoice_names:
		payments_query = """
			SELECT 
				parent as pos_invoice,
				mode_of_payment,
				amount,
				base_amount,
				type,
				account
			FROM `tabSales Invoice Payment`
			WHERE parent IN %(invoice_names)s
		"""
		
		payments = frappe.db.sql(payments_query, {
			"invoice_names": all_invoice_names
		}, as_dict=True)
		
		for payment in payments:
			if payment.pos_invoice not in payments_data:
				payments_data[payment.pos_invoice] = []
			payments_data[payment.pos_invoice].append(payment)
	
	# Get patient information for each customer
	customers = list(set([inv.customer for inv in invoices if inv.customer]))
	customer_names = list(set([inv.customer_name for inv in invoices if inv.customer_name]))
	patient_data = {}
	
	if customers:
		# Get patients by customer link using frappe.get_all (safer)
		# IMPORTANT: Only fetch custom_reference_number, NOT Patient's name field
		patients_by_customer = frappe.get_all(
			"Patient",
			filters={"customer": ["in", customers]},
			fields=["patient_name", "customer", "custom_reference_number"]
		)
		
		for patient in patients_by_customer:
			if patient.customer:
				patient_data[patient.customer] = {
					"patient_name": patient.patient_name or "",
					"custom_reference_number": patient.custom_reference_number or ""
				}
	
	# Process invoices and build report data
	report_data = []
	returns_data = []
	s_no = 1
	
	total_sales = 0
	total_cash_payment = 0
	total_card_payment = 0
	total_sales_return = 0
	
	for invoice in invoices:
		cash_payment = 0
		card_payment = 0
		bank_ref = ""
		change_amount = flt(invoice.base_change_amount or 0)
		total_cash_paid = 0
		
		if invoice.is_return and invoice.return_against:
			# For returns, get payment info from the original invoice
			original_payments = payments_data.get(invoice.return_against, [])
			
			# If payment data not found, fetch it directly
			if not original_payments:
				original_payments_query = """
					SELECT 
						mode_of_payment,
						amount,
						base_amount,
						type,
						account
					FROM `tabSales Invoice Payment`
					WHERE parent = %(original_invoice)s
				"""
				original_payments = frappe.db.sql(original_payments_query, {
					"original_invoice": invoice.return_against
				}, as_dict=True)
			
			original_cash = 0
			original_card = 0
			
			# Calculate payment amounts based on original invoice
			for payment in original_payments:
				if payment.type == "Cash":
					original_cash += flt(payment.base_amount)
				elif payment.type in ["Card", "Bank"]:
					original_card += flt(payment.base_amount)
					if payment.type == "Bank":
						bank_ref = payment.account or payment.mode_of_payment or ""
			
			# Get change amount and grand total from original invoice
			original_invoice_data = frappe.db.get_value(
				"POS Invoice", 
				invoice.return_against, 
				["base_change_amount", "base_grand_total"], 
				as_dict=True
			)
			
			if original_invoice_data:
				original_change = flt(original_invoice_data.base_change_amount or 0)
				original_total = abs(flt(original_invoice_data.base_grand_total or 1))
				return_total = abs(flt(invoice.base_grand_total))
				
				# Calculate return ratio
				return_ratio = return_total / original_total if original_total > 0 else 0
				
				# Calculate net cash paid (after change)
				net_original_cash = max(0, original_cash - original_change)
				
				# Distribute return amount proportionally
				if net_original_cash > 0 or original_card > 0:
					total_original_payment = net_original_cash + original_card
					if total_original_payment > 0:
						cash_ratio = net_original_cash / total_original_payment
						card_ratio = original_card / total_original_payment
						
						cash_payment = -(return_total * cash_ratio)
						card_payment = -(return_total * card_ratio)
					else:
						# If no payment data, distribute equally or based on total
						cash_payment = -return_total
						card_payment = 0
				else:
					# No payment data found, show return amount in cash
					cash_payment = -return_total
					card_payment = 0
			else:
				# Original invoice not found, show return amount in cash
				return_total = abs(flt(invoice.base_grand_total))
				cash_payment = -return_total
				card_payment = 0
		else:
			# Get payments for regular invoice
			payments = payments_data.get(invoice.pos_invoice, [])
			
			# First, calculate total cash paid
			for payment in payments:
				if payment.type == "Cash":
					total_cash_paid += flt(payment.base_amount)
				elif payment.type in ["Card", "Bank"]:
					card_payment += flt(payment.base_amount)
					if payment.type == "Bank":
						bank_ref = payment.account or payment.mode_of_payment or ""
			
			# Cash payment = total cash paid - change amount
			cash_payment = max(0, total_cash_paid - change_amount)
		
		# Get patient info - ALWAYS do direct lookup for each invoice to ensure we get MR Number and KPWS Number
		# MR Number should be from custom_reference_number field (Kiran MR Number)
		# KPWS Number should be from Patient's name field (like KPWS-1183)
		custom_reference_number = ""
		kpws_number = ""
		patient_name = invoice.customer_name or ""
		
		# Try to get patient by customer first (using SQL for reliability)
		if invoice.customer:
			# Direct SQL query to get custom_reference_number and name from Patient
			patient_doc = frappe.db.sql("""
				SELECT name, patient_name, custom_reference_number
				FROM `tabPatient`
				WHERE customer = %(customer)s
				LIMIT 1
			""", {"customer": invoice.customer}, as_dict=True)
			
			if patient_doc and len(patient_doc) > 0:
				patient_doc = patient_doc[0]
				# Get custom_reference_number - this is the "Kiran MR Number" field (like "038076/25")
				mr_num = patient_doc.get("custom_reference_number")
				if mr_num is not None and str(mr_num).strip():
					custom_reference_number = str(mr_num).strip()
				# Get name - this is the "KPWS Number" field (like "KPWS-1183")
				if patient_doc.get("name"):
					kpws_number = str(patient_doc.name).strip()
				if patient_doc.get("patient_name"):
					patient_name = patient_doc.patient_name
		
		# If not found by customer, try by customer_name (case insensitive, exact match)
		# Try if either MR Number or KPWS Number is missing
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
		
		row = {
			"s_no": s_no,
			"pos_invoice": invoice.pos_invoice,
			"cash_payment": cash_payment,
			"card_payment": card_payment,
			"bank_ref": bank_ref,
			"patient_name": patient_name,
			"total": flt(invoice.base_grand_total),
			"mr_number": custom_reference_number,
			"custom_reference_number": custom_reference_number,  # Also add for JS compatibility
			"kpws_number": kpws_number,  # KPWS Number (Patient's name field)
			"posting_date": invoice.posting_date,
			"posting_time": invoice.posting_time,
			"owner": invoice.owner
		}
		
		if invoice.is_return:
			returns_data.append(row)
			total_sales_return += flt(invoice.base_grand_total)
			# For returns, subtract from totals (they're already negative)
			total_cash_payment += cash_payment  # cash_payment is already negative
			total_card_payment += card_payment   # card_payment is already negative
		else:
			report_data.append(row)
			total_sales += flt(invoice.base_grand_total)
			total_cash_payment += cash_payment
			total_card_payment += card_payment
		
		s_no += 1
	
	# Calculate cash received
	# total_cash_payment already includes negative returns (since returns have negative cash_payment)
	# So cash_received is simply total_cash_payment (which is net cash after returns)
	cash_received = total_cash_payment
	
	return {
		"data": report_data,
		"returns": returns_data,
		"totals": {
			"total_sales": total_sales,
			"total_cash_payment": total_cash_payment,
			"total_card_payment": total_card_payment,
			"total_sales_return": abs(total_sales_return) if total_sales_return < 0 else total_sales_return,
			"cash_received": cash_received
		}
	}


def get_context(context):
	"""Context for the page template"""
	return context

