import frappe
from frappe import _
from frappe.utils import getdate, flt, get_datetime


@frappe.whitelist()
def get_welfare_report_data(filters):
	"""
	Get welfare report data for POS invoices filtered by Welfare POS Profile
	"""
	filters = frappe.parse_json(filters)
	
	# Validate required filters
	if not filters.get("date_from") or not filters.get("date_to"):
		frappe.throw(_("Date From and Date To are mandatory"))
	
	date_from = getdate(filters.get("date_from"))
	date_to = getdate(filters.get("date_to"))
	user = filters.get("user")
	
	# Get Welfare POS Profile - assuming it contains "welfare" in the name
	welfare_pos_profiles = frappe.db.sql("""
		SELECT name FROM `tabPOS Profile`
		WHERE name LIKE '%welfare%' AND disabled = 0
	""", as_dict=True)
	
	if not welfare_pos_profiles:
		frappe.throw(_("No Welfare POS Profile found. Please create a POS Profile with 'welfare' in the name."))
	
	welfare_pos_profile_names = [p.name for p in welfare_pos_profiles]
	
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
		"pos_profiles": welfare_pos_profile_names,
		"user": user
	}, as_dict=True)
	
	# Get payment details for each invoice
	invoice_names = [inv.pos_invoice for inv in invoices]
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
	
	# Process invoices and build report data
	report_data = []
	returns_data = []
	s_no = 1
	
	total_cash_received = 0
	total_card_received = 0
	total_zakat_received = 0
	total_donation_received = 0
	total_invoice_amount = 0
	total_received = 0
	
	total_return_cash = 0
	total_return_card = 0
	total_return_zakat = 0
	total_return_donation = 0
	total_return_amount = 0
	total_return_received = 0
	
	for invoice in invoices:
		cash_received = 0
		card_received = 0
		zakat_received = 0
		donation_received = 0
		change_amount = flt(invoice.base_change_amount or 0)
		total_cash_paid = 0
		
		if invoice.is_return and invoice.return_against:
			# For returns, get payment info from the original invoice
			original_payments = payments_data.get(invoice.return_against, [])
			
			if not original_payments:
				original_payments = frappe.db.sql("""
					SELECT mode_of_payment, amount, base_amount, type, account
					FROM `tabSales Invoice Payment`
					WHERE parent = %(original_invoice)s
				""", {"original_invoice": invoice.return_against}, as_dict=True)
			
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
				return_ratio = return_total / original_total if original_total > 0 else 0
				
				# Calculate original payments by type
				orig_cash = 0
				orig_card = 0
				orig_zakat = 0
				orig_donation = 0
				
				for payment in original_payments:
					payment_type = payment.type or ""
					mode = (payment.mode_of_payment or "").strip()
					mode_lower = mode.lower()
					amount = flt(payment.base_amount)
					
					# Check mode_of_payment first for Zakat and Donation (exact match or contains)
					if mode and ("zakat" in mode_lower or mode == "Zakat"):
						orig_zakat += amount
					elif mode and ("donation" in mode_lower or mode == "Donation"):
						orig_donation += amount
					elif payment_type == "Cash":
						orig_cash += amount
					elif payment_type in ["Card", "Bank"]:
						orig_card += amount
				
				net_original_cash = max(0, orig_cash - original_change)
				total_original_payment = net_original_cash + orig_card + orig_zakat + orig_donation
				
				if total_original_payment > 0:
					cash_received = -(return_total * (net_original_cash / total_original_payment))
					card_received = -(return_total * (orig_card / total_original_payment))
					zakat_received = -(return_total * (orig_zakat / total_original_payment))
					donation_received = -(return_total * (orig_donation / total_original_payment))
				else:
					cash_received = -return_total
		else:
			# Get payments for regular invoice
			payments = payments_data.get(invoice.pos_invoice, [])
			
			for payment in payments:
				payment_type = payment.type or ""
				mode = (payment.mode_of_payment or "").strip()
				mode_lower = mode.lower()
				amount = flt(payment.base_amount)
				
				# Check mode_of_payment first for Zakat and Donation (exact match or contains)
				if mode and ("zakat" in mode_lower or mode == "Zakat"):
					zakat_received += amount
				elif mode and ("donation" in mode_lower or mode == "Donation"):
					donation_received += amount
				elif payment_type == "Cash":
					total_cash_paid += amount
				elif payment_type in ["Card", "Bank"]:
					card_received += amount
			
			# Cash received = total cash paid - change amount
			cash_received = max(0, total_cash_paid - change_amount)
		
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
		
		total_received_row = cash_received + card_received + zakat_received + donation_received
		
		row = {
			"s_no": s_no,
			"pos_invoice": invoice.pos_invoice,
			"kpws_number": kpws_number,
			"mr_number": custom_reference_number,
			"patient_number": patient_name,
			"cash_received": cash_received,
			"card_received": card_received,
			"zakat_received": zakat_received,
			"donation_received": donation_received,
			"total_invoice_amount": flt(invoice.base_grand_total),
			"total_received": total_received_row,
			"posting_date": invoice.posting_date,
			"posting_time": invoice.posting_time,
			"owner": invoice.owner
		}
		
		if invoice.is_return:
			returns_data.append(row)
			total_return_cash += cash_received
			total_return_card += card_received
			total_return_zakat += zakat_received
			total_return_donation += donation_received
			total_return_amount += flt(invoice.base_grand_total)
			total_return_received += total_received_row
		else:
			report_data.append(row)
			total_cash_received += cash_received
			total_card_received += card_received
			total_zakat_received += zakat_received
			total_donation_received += donation_received
			total_invoice_amount += flt(invoice.base_grand_total)
			total_received += total_received_row
		
		s_no += 1
	
	# Calculate net totals (sales - returns)
	net_cash_received = total_cash_received + total_return_cash
	net_card_received = total_card_received + total_return_card
	net_zakat_received = total_zakat_received + total_return_zakat
	net_donation_received = total_donation_received + total_return_donation
	net_invoice_amount = total_invoice_amount + total_return_amount
	net_received = total_received + total_return_received
	
	return {
		"data": report_data,
		"returns": returns_data,
		"totals": {
			"total_cash_received": total_cash_received,
			"total_card_received": total_card_received,
			"total_zakat_received": total_zakat_received,
			"total_donation_received": total_donation_received,
			"total_invoice_amount": total_invoice_amount,
			"total_received": total_received,
			"total_return_cash": total_return_cash,
			"total_return_card": total_return_card,
			"total_return_zakat": total_return_zakat,
			"total_return_donation": total_return_donation,
			"total_return_amount": abs(total_return_amount) if total_return_amount < 0 else total_return_amount,
			"total_return_received": total_return_received,
			"net_cash_received": net_cash_received,
			"net_card_received": net_card_received,
			"net_zakat_received": net_zakat_received,
			"net_donation_received": net_donation_received,
			"net_invoice_amount": net_invoice_amount,
			"net_received": net_received
		}
	}


def get_context(context):
	"""Context for the page template"""
	return context

