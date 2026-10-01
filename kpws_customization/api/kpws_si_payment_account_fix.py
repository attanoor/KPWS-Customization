import frappe
from frappe.utils import nowdate

def _mode_account(mode_of_payment, company):
    if not mode_of_payment or not frappe.db.exists("Mode of Payment", mode_of_payment):
        return ""

    mop = frappe.get_doc("Mode of Payment", mode_of_payment)

    for row in mop.get("accounts") or []:
        if row.company == company and row.default_account:
            return row.default_account

    for row in mop.get("accounts") or []:
        if row.default_account:
            return row.default_account

    return ""


def _mode(names):
    for name in names:
        if frappe.db.exists("Mode of Payment", name):
            return name

    rows = frappe.get_all("Mode of Payment", fields=["name"], limit=200)
    for row in rows:
        low = row.name.lower()
        for name in names:
            if name.lower() in low:
                return row.name

    return names[0]


def _total(doc):
    return float(doc.get("rounded_total") or doc.get("grand_total") or doc.get("net_total") or 0)


def _latest_welfare(patient):
    if not patient or not frappe.db.exists("DocType", "Patient Registration Form"):
        return {}

    meta = frappe.get_meta("Patient Registration Form")
    fields = ["name", "modified"]

    for f in [
        "custom_patient",
        "patient",
        "purpose",
        "discount_value",
        "custom_kpws_welfare_type",
        "custom_kpws_welfare_percentage",
    ]:
        if meta.get_field(f):
            fields.append(f)

    filters_list = []
    if meta.get_field("custom_patient"):
        filters_list.append({"custom_patient": patient, "docstatus": ["<", 2]})
    if meta.get_field("patient"):
        filters_list.append({"patient": patient, "docstatus": ["<", 2]})

    for filters in filters_list:
        rows = frappe.get_all(
            "Patient Registration Form",
            filters=filters,
            fields=list(set(fields)),
            order_by="modified desc",
            limit=1,
        )

        if rows:
            row = rows[0]
            percentage = row.get("discount_value")
            if percentage in (None, ""):
                percentage = row.get("custom_kpws_welfare_percentage") or 0

            return {
                "name": row.name,
                "type": row.get("purpose") or row.get("custom_kpws_welfare_type") or "",
                "percentage": float(percentage or 0),
            }

    return {}


def _append_payment(doc, mode, amount):
    amount = float(amount or 0)
    if amount <= 0:
        return

    account = _mode_account(mode, doc.company)
    if not account:
        frappe.throw(
            f"Mode of Payment <b>{mode}</b> has no default account for company <b>{doc.company}</b>. "
            f"Open Mode of Payment {mode} and add account in the Accounts table."
        )

    doc.append("payments", {
        "mode_of_payment": mode,
        "account": account,
        "amount": amount,
        "base_amount": amount,
    })


def enforce_payment_accounts_on_sales_invoice(doc, method=None):
    if doc.doctype != "Sales Invoice":
        return

    if not int(doc.get("is_pos") or 0):
        return

    total = _total(doc)
    if total <= 0:
        return

    patient_type = doc.get("custom_kpws_billing_type") or ""

    cash_mode = _mode(["Cash"])
    card_mode = _mode(["Credit Card", "Card"])
    panel_mode = _mode(["Panel"])
    zakat_mode = _mode(["Zakat"])
    donation_mode = _mode(["Donation"])

    doc.set("payments", [])

    if patient_type == "Panel":
        _append_payment(doc, panel_mode, total)

    elif patient_type == "Welfare":
        welfare_type = doc.get("custom_kpws_welfare_type")
        percentage = doc.get("custom_kpws_welfare_percentage")

        if (not welfare_type or percentage in (None, "")) and doc.get("patient"):
            welfare = _latest_welfare(doc.patient)
            welfare_type = welfare_type or welfare.get("type")
            percentage = percentage if percentage not in (None, "") else welfare.get("percentage")

        percentage = float(percentage or 0)
        percentage = max(0, min(100, percentage))

        sponsor_amount = total * percentage / 100
        cash_amount = total - sponsor_amount

        sponsor_mode = zakat_mode if "zakat" in str(welfare_type or "").lower() else donation_mode

        _append_payment(doc, sponsor_mode, sponsor_amount)
        _append_payment(doc, cash_mode, cash_amount)

    else:
        # Cash / Walk-in: preserve credit-card split only if user entered it.
        existing_card = 0
        for row in doc.get("payments") or []:
            mop = str(row.mode_of_payment or "").lower()
            if "card" in mop or "credit" in mop:
                existing_card += float(row.amount or 0)

        if existing_card > total:
            existing_card = 0

        _append_payment(doc, cash_mode, total - existing_card)
        _append_payment(doc, card_mode, existing_card)

    doc.paid_amount = sum(float(row.amount or 0) for row in doc.get("payments") or [])


def show_mode_accounts():
    print("Mode of Payment account setup:")
    for mode in ["Cash", "Credit Card", "Donation", "Zakat", "Panel"]:
        if not frappe.db.exists("Mode of Payment", mode):
            print(mode, "=> MISSING")
            continue

        acc = _mode_account(mode, frappe.defaults.get_defaults().get("company") or "")
        print(mode, "=>", acc or "NO DEFAULT ACCOUNT")


def repair_invoice(invoice_name):
    doc = frappe.get_doc("Sales Invoice", invoice_name)

    print("Invoice:", doc.name)
    print("Docstatus:", doc.docstatus)
    print("Status:", doc.status)
    print("Outstanding before:", doc.outstanding_amount)
    print("Paid Amount field:", doc.paid_amount)

    if doc.docstatus != 1:
        frappe.throw("Invoice must be submitted before repair.")

    if float(doc.outstanding_amount or 0) <= 0:
        print("Invoice already has no outstanding amount.")
        return

    if not doc.debit_to:
        frappe.throw("Sales Invoice debit_to account is missing.")

    remaining = float(doc.outstanding_amount or 0)

    for row in doc.payments:
        amount = float(row.amount or 0)
        if amount <= 0 or remaining <= 0:
            continue

        allocate = min(amount, remaining)
        account = _mode_account(row.mode_of_payment, doc.company)

        if not account:
            frappe.throw(
                f"Cannot repair. Mode of Payment {row.mode_of_payment} has no default account for {doc.company}."
            )

        pe = frappe.new_doc("Payment Entry")
        pe.payment_type = "Receive"
        pe.company = doc.company
        pe.posting_date = nowdate()
        pe.mode_of_payment = row.mode_of_payment
        pe.party_type = "Customer"
        pe.party = doc.customer
        pe.paid_from = doc.debit_to
        pe.paid_to = account
        pe.paid_amount = allocate
        pe.received_amount = allocate
        pe.reference_no = f"Repair-{doc.name}-{row.mode_of_payment}"[:140]
        pe.reference_date = nowdate()

        pe.append("references", {
            "reference_doctype": "Sales Invoice",
            "reference_name": doc.name,
            "allocated_amount": allocate,
        })

        pe.insert(ignore_permissions=True)
        pe.submit()

        print("Created Payment Entry:", pe.name, row.mode_of_payment, allocate, "to", account)

        remaining -= allocate

    doc.reload()
    print("Outstanding after:", doc.outstanding_amount)
    print("Status after:", doc.status)


def install():
    frappe.db.commit()
    frappe.clear_cache()
    print("Payment account enforcement module installed.")
