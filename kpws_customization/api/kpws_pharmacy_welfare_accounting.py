import json
import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate

SETTINGS_DOCTYPE = "KPWS Pharmacy Billing Settings"

SETTINGS_FIELDS = [
    {
        "fieldname": "accounting_automation_section",
        "label": "Accounting Automation",
        "fieldtype": "Section Break",
        "insert_after": "enable_customer_advance_allocation",
    },
    {
        "fieldname": "enable_welfare_auto_journal",
        "label": "Auto Post Welfare Zakat/Donation Journal Entry",
        "fieldtype": "Check",
        "default": "1",
    },
    {
        "fieldname": "enable_welfare_patient_share_payment_entry",
        "label": "Auto Post Patient Share Payment Entry for Welfare",
        "fieldtype": "Check",
        "default": "1",
    },
    {
        "fieldname": "welfare_receivable_account",
        "label": "Welfare Receivable Account",
        "fieldtype": "Link",
        "options": "Account",
    },
    {
        "fieldname": "zakat_disbursement_account",
        "label": "Zakat Disbursement Account",
        "fieldtype": "Link",
        "options": "Account",
    },
    {
        "fieldname": "donation_disbursement_account",
        "label": "Donation Disbursement Account",
        "fieldtype": "Link",
        "options": "Account",
    },
    {
        "fieldname": "accounting_automation_column_break",
        "fieldtype": "Column Break",
    },
    {
        "fieldname": "panel_billing_mode",
        "label": "Panel Billing Mode",
        "fieldtype": "Select",
        "options": "Receivable\nPOS Payment",
        "default": "Receivable",
    },
    {
        "fieldname": "panel_receivable_account",
        "label": "Panel Receivable Account",
        "fieldtype": "Link",
        "options": "Account",
    },
    {
        "fieldname": "cash_income_account",
        "label": "Cash/Welfare Income Account",
        "fieldtype": "Link",
        "options": "Account",
    },
    {
        "fieldname": "panel_income_account",
        "label": "Panel Income Account",
        "fieldtype": "Link",
        "options": "Account",
    },
    {
        "fieldname": "pharmacy_cogs_account",
        "label": "Pharmacy COGS / Expense Account",
        "fieldtype": "Link",
        "options": "Account",
    },
]

SI_FIELDS = [
    {
        "fieldname": "kpws_accounting_section",
        "label": "KPWS Accounting",
        "fieldtype": "Section Break",
        "insert_after": "custom_kpws_approved_percentage",
        "collapsible": 1,
    },
    {
        "fieldname": "custom_kpws_welfare_covered_amount",
        "label": "Welfare Covered Amount",
        "fieldtype": "Currency",
        "read_only": 1,
    },
    {
        "fieldname": "custom_kpws_patient_share_amount",
        "label": "Patient Share Amount",
        "fieldtype": "Currency",
        "read_only": 1,
    },
    {
        "fieldname": "custom_kpws_patient_cash_amount",
        "label": "Patient Cash Amount",
        "fieldtype": "Currency",
        "read_only": 1,
    },
    {
        "fieldname": "custom_kpws_patient_card_amount",
        "label": "Patient Card Amount",
        "fieldtype": "Currency",
        "read_only": 1,
    },
    {
        "fieldname": "kpws_accounting_column_break",
        "fieldtype": "Column Break",
    },
    {
        "fieldname": "custom_kpws_auto_journal_entry",
        "label": "Auto Welfare Journal Entry",
        "fieldtype": "Link",
        "options": "Journal Entry",
        "read_only": 1,
    },
    {
        "fieldname": "custom_kpws_cash_payment_entry",
        "label": "Auto Cash Payment Entry",
        "fieldtype": "Link",
        "options": "Payment Entry",
        "read_only": 1,
    },
    {
        "fieldname": "custom_kpws_card_payment_entry",
        "label": "Auto Card Payment Entry",
        "fieldtype": "Link",
        "options": "Payment Entry",
        "read_only": 1,
    },
]


def _has_field(doctype, fieldname):
    try:
        return frappe.get_meta(doctype).has_field(fieldname)
    except Exception:
        return False


def _field_exists(doctype, fieldname):
    return bool(frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": fieldname})) or _has_field(doctype, fieldname)


def _safe_insert_custom_field(doctype, field):
    if _field_exists(doctype, field.get("fieldname")):
        return

    doc = frappe.new_doc("Custom Field")
    doc.dt = doctype

    for key, value in field.items():
        doc.set(key, value)

    doc.insert(ignore_permissions=True)


def _first_existing_account(names, company=None):
    for name in names:
        if name and frappe.db.exists("Account", name):
            return name

    filters = {}
    if company:
        filters["company"] = company

    for name in names:
        if not name:
            continue
        filters["account_name"] = ["like", name.replace(" - KPWS", "") + "%"]
        found = frappe.db.get_value("Account", filters, "name")
        if found:
            return found

    return None


def _account_is_group(account):
    return bool(account and cint(frappe.db.get_value("Account", account, "is_group") or 0))


def _first_existing_group_account(names, company=None):
    """Return the first existing account from names that is a group account."""
    for name in names:
        if name and frappe.db.exists("Account", name) and _account_is_group(name):
            return name

    filters = {"is_group": 1}
    if company:
        filters["company"] = company

    for name in names:
        if not name:
            continue
        filters["account_name"] = ["like", name.replace(" - KPWS", "") + "%"]
        found = frappe.db.get_value("Account", filters, "name")
        if found:
            return found

    return None


def _first_existing_ledger_account(names, company=None):
    """Return the first existing account from names that is NOT a group account."""
    for name in names:
        if name and frappe.db.exists("Account", name) and not _account_is_group(name):
            return name

    filters = {"is_group": 0}
    if company:
        filters["company"] = company

    for name in names:
        if not name:
            continue
        filters["account_name"] = ["like", name.replace(" - KPWS", "") + "%"]
        found = frappe.db.get_value("Account", filters, "name")
        if found:
            return found

    return None


def _ensure_account(account_name, parent_account, company, root_type="Asset", account_type="Receivable"):
    if not account_name:
        return None

    if frappe.db.exists("Account", account_name):
        # Existing account is usable only if it is a ledger, not a group.
        if _account_is_group(account_name):
            return None
        return account_name

    # ERPNext allows child accounts only under group accounts. If an old COA account
    # like RECEIVABLES - KPWS is a ledger, climb to its parent group; otherwise use
    # a safe asset group fallback.
    if parent_account and frappe.db.exists("Account", parent_account) and not _account_is_group(parent_account):
        possible_parent = frappe.db.get_value("Account", parent_account, "parent_account")
        if _account_is_group(possible_parent):
            parent_account = possible_parent

    if not parent_account or not frappe.db.exists("Account", parent_account) or not _account_is_group(parent_account):
        parent_account = _first_existing_group_account([
            "CURRENT ASSETS - KPWS",
            "ASSETS - KPWS",
            "Current Assets - KPWS",
            "Debtors - KPWS",
        ], company)

    if not parent_account:
        frappe.throw(_("Could not find a group Asset account under which WELFARE RECEIVABLE - KPWS can be created."))

    doc = frappe.new_doc("Account")
    doc.account_name = account_name.replace(" - KPWS", "")
    doc.parent_account = parent_account
    doc.company = company
    doc.root_type = root_type
    doc.report_type = "Balance Sheet" if root_type in ("Asset", "Liability", "Equity") else "Profit and Loss"
    doc.account_type = account_type
    doc.is_group = 0
    doc.insert(ignore_permissions=True)
    return doc.name


def _get_settings():
    if not frappe.db.exists("DocType", SETTINGS_DOCTYPE):
        frappe.throw(_("{0} DocType is missing.").format(SETTINGS_DOCTYPE))
    return frappe.get_single(SETTINGS_DOCTYPE)


def setup():
    """Create custom fields and fill safe default accounting accounts."""
    if not frappe.db.exists("DocType", SETTINGS_DOCTYPE):
        frappe.throw(_("{0} DocType is missing. Install/fix Pharmacy Billing Settings first.").format(SETTINGS_DOCTYPE))

    for field in SETTINGS_FIELDS:
        _safe_insert_custom_field(SETTINGS_DOCTYPE, field)

    for field in SI_FIELDS:
        _safe_insert_custom_field("Sales Invoice", field)

    frappe.clear_cache(doctype=SETTINGS_DOCTYPE)
    frappe.clear_cache(doctype="Sales Invoice")

    settings = frappe.get_single(SETTINGS_DOCTYPE)
    company = settings.get("company") or frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")

    if company:
        if not settings.get("welfare_receivable_account"):
            parent = _first_existing_group_account(["CURRENT ASSETS - KPWS", "ASSETS - KPWS", "Current Assets - KPWS"], company)
            welfare = _first_existing_ledger_account(["WELFARE RECEIVABLE - KPWS"], company)
            if not welfare:
                welfare = _ensure_account("WELFARE RECEIVABLE - KPWS", parent, company, "Asset", "Receivable")
            if welfare:
                settings.welfare_receivable_account = welfare

        defaults = {
            "zakat_disbursement_account": ["ZAKAT DISBURSE - KPWS"],
            "donation_disbursement_account": ["DONATION DISBURSE - KPWS"],
            "cash_income_account": ["SALES (PHARMACY) - KPWS"],
            "panel_income_account": ["SALES (PANEL) - KPWS"],
            "pharmacy_cogs_account": ["COST OF GOODS SOLD - KPWS"],
        }

        for fieldname, names in defaults.items():
            if not settings.get(fieldname):
                account = _first_existing_account(names, company)
                if account:
                    settings.set(fieldname, account)

        # Panel receivable must be a ledger account, not the PANEL RECEIVABLES group.
        if not settings.get("panel_receivable_account"):
            panel_account = _first_existing_ledger_account([
                "SEHAT SAHULAT PROGRAM - KPWS",
                "KIRAN RECEIVABLE - KPWS",
                "BAITHUMALL RECEIVABLE - KPWS",
            ], company)
            if panel_account:
                settings.panel_receivable_account = panel_account

    if not settings.get("enable_welfare_auto_journal"):
        settings.enable_welfare_auto_journal = 1
    if not settings.get("enable_welfare_patient_share_payment_entry"):
        settings.enable_welfare_patient_share_payment_entry = 1
    if not settings.get("panel_billing_mode"):
        settings.panel_billing_mode = "Receivable"

    settings.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "ok": True,
        "message": "KPWS welfare/panel accounting settings installed.",
        "settings": settings.name,
    }


def _mop_account(mode_of_payment, company):
    if not mode_of_payment:
        return None
    try:
        mop = frappe.get_doc("Mode of Payment", mode_of_payment)
        for row in mop.get("accounts") or []:
            if row.company == company and row.default_account:
                return row.default_account
    except Exception:
        return None
    return None


def _existing_journal(invoice_name):
    rows = frappe.db.sql(
        """
        SELECT a.parent
        FROM `tabJournal Entry Account` a
        INNER JOIN `tabJournal Entry` j ON j.name = a.parent
        WHERE a.reference_type = 'Sales Invoice'
          AND a.reference_name = %s
          AND j.docstatus = 1
        LIMIT 1
        """,
        invoice_name,
        as_dict=True,
    )
    return rows[0].parent if rows else None


def _existing_payment(invoice_name, mode_of_payment=None):
    params = [invoice_name]
    mode_sql = ""
    if mode_of_payment:
        mode_sql = " AND pe.mode_of_payment = %s"
        params.append(mode_of_payment)

    rows = frappe.db.sql(
        f"""
        SELECT pe.name
        FROM `tabPayment Entry Reference` r
        INNER JOIN `tabPayment Entry` pe ON pe.name = r.parent
        WHERE r.reference_doctype = 'Sales Invoice'
          AND r.reference_name = %s
          AND pe.docstatus = 1
          {mode_sql}
        LIMIT 1
        """,
        params,
        as_dict=True,
    )
    return rows[0].name if rows else None


def _get_party_receivable_account(si, fallback_account=None):
    if fallback_account:
        return fallback_account
    if si.get("debit_to"):
        return si.get("debit_to")
    return frappe.db.get_value("Company", si.company, "default_receivable_account")


def _make_payment_entry(si, mode_of_payment, amount, link_field=None):
    amount = flt(amount, 2)
    if amount <= 0 or not mode_of_payment:
        return None

    existing = _existing_payment(si.name, mode_of_payment)
    if existing:
        if link_field and _has_field("Sales Invoice", link_field):
            frappe.db.set_value("Sales Invoice", si.name, link_field, existing, update_modified=False)
        return existing

    paid_to = _mop_account(mode_of_payment, si.company)
    if not paid_to:
        frappe.throw(_("Mode of Payment {0} has no default account for company {1}.").format(mode_of_payment, si.company))

    receivable = _get_party_receivable_account(si)
    if not receivable:
        frappe.throw(_("Receivable account is missing for invoice {0}.").format(si.name))

    pe = frappe.new_doc("Payment Entry")
    pe.payment_type = "Receive"
    pe.company = si.company
    pe.posting_date = si.posting_date or nowdate()
    pe.mode_of_payment = mode_of_payment
    pe.party_type = "Customer"
    pe.party = si.customer
    pe.paid_from = receivable
    pe.paid_to = paid_to
    pe.paid_amount = amount
    pe.received_amount = amount
    pe.reference_no = si.name
    pe.reference_date = si.posting_date or nowdate()
    pe.append("references", {
        "reference_doctype": "Sales Invoice",
        "reference_name": si.name,
        "allocated_amount": amount,
    })
    pe.flags.ignore_permissions = True
    pe.insert(ignore_permissions=True)
    pe.submit()

    if link_field and _has_field("Sales Invoice", link_field):
        frappe.db.set_value("Sales Invoice", si.name, link_field, pe.name, update_modified=False)

    return pe.name


def _make_welfare_journal(si, expense_account, receivable_account, amount, purpose):
    amount = flt(amount, 2)
    if amount <= 0:
        return None

    existing = _existing_journal(si.name)
    if existing:
        if _has_field("Sales Invoice", "custom_kpws_auto_journal_entry"):
            frappe.db.set_value("Sales Invoice", si.name, "custom_kpws_auto_journal_entry", existing, update_modified=False)
        return existing

    if not expense_account:
        frappe.throw(_("{0} disbursement account is missing in KPWS Pharmacy Billing Settings.").format(purpose))
    if not receivable_account:
        frappe.throw(_("Welfare Receivable Account is missing in KPWS Pharmacy Billing Settings."))

    je = frappe.new_doc("Journal Entry")
    je.voucher_type = "Journal Entry"
    je.company = si.company
    je.posting_date = si.posting_date or nowdate()
    je.user_remark = "Auto {0} welfare disbursement against Sales Invoice {1}".format(purpose, si.name)

    cost_center = None
    try:
        cost_center = si.get("cost_center") or frappe.db.get_value("Company", si.company, "cost_center")
    except Exception:
        cost_center = None

    debit_row = {
        "account": expense_account,
        "debit_in_account_currency": amount,
        "credit_in_account_currency": 0,
    }
    if cost_center:
        debit_row["cost_center"] = cost_center
    je.append("accounts", debit_row)

    credit_row = {
        "account": receivable_account,
        "party_type": "Customer",
        "party": si.customer,
        "reference_type": "Sales Invoice",
        "reference_name": si.name,
        "debit_in_account_currency": 0,
        "credit_in_account_currency": amount,
    }
    je.append("accounts", credit_row)

    je.flags.ignore_permissions = True
    je.insert(ignore_permissions=True)
    je.submit()

    if _has_field("Sales Invoice", "custom_kpws_auto_journal_entry"):
        frappe.db.set_value("Sales Invoice", si.name, "custom_kpws_auto_journal_entry", je.name, update_modified=False)

    return je.name


def _sales_invoice_value(si, fieldname):
    if _has_field("Sales Invoice", fieldname):
        return si.get(fieldname)
    return None


def process_sales_invoice_submit(invoice_name):
    if not invoice_name or not frappe.db.exists("Sales Invoice", invoice_name):
        return {"ok": False, "message": "Sales Invoice not found"}

    si = frappe.get_doc("Sales Invoice", invoice_name)
    if cint(si.docstatus) != 1 or cint(si.get("is_return")):
        return {"ok": False, "message": "Only submitted non-return invoices are processed"}

    group = si.get("custom_kpws_patient_billing_group") if _has_field("Sales Invoice", "custom_kpws_patient_billing_group") else None
    if group != "Welfare":
        return {"ok": True, "skipped": True, "message": "Not a Welfare invoice"}

    settings = _get_settings()
    if not cint(settings.get("enable_welfare_auto_journal")):
        return {"ok": True, "skipped": True, "message": "Auto welfare journal disabled"}

    purpose = (si.get("custom_kpws_purpose") or "").strip()
    purpose_lower = purpose.lower()
    if purpose_lower not in ("zakat", "donation"):
        frappe.throw(_("Welfare purpose must be Zakat or Donation on invoice {0}.").format(si.name))

    welfare_amount = flt(_sales_invoice_value(si, "custom_kpws_welfare_covered_amount"), 2)
    if welfare_amount <= 0:
        pct = flt(si.get("custom_kpws_approved_percentage") or 0)
        welfare_amount = flt(flt(si.grand_total) * pct / 100, 2)

    patient_cash = flt(_sales_invoice_value(si, "custom_kpws_patient_cash_amount"), 2)
    patient_card = flt(_sales_invoice_value(si, "custom_kpws_patient_card_amount"), 2)

    created = {}

    if cint(settings.get("enable_welfare_patient_share_payment_entry")):
        if patient_cash > 0:
            created["cash_payment_entry"] = _make_payment_entry(
                si,
                settings.get("cash_mode_of_payment") or settings.get("default_mode_of_payment"),
                patient_cash,
                "custom_kpws_cash_payment_entry",
            )
        if patient_card > 0:
            created["card_payment_entry"] = _make_payment_entry(
                si,
                settings.get("card_mode_of_payment"),
                patient_card,
                "custom_kpws_card_payment_entry",
            )

    expense_account = settings.get("zakat_disbursement_account") if purpose_lower == "zakat" else settings.get("donation_disbursement_account")
    purpose_label = "Zakat" if purpose_lower == "zakat" else "Donation"
    receivable_account = settings.get("welfare_receivable_account") or si.get("debit_to")
    created["journal_entry"] = _make_welfare_journal(si, expense_account, receivable_account, welfare_amount, purpose_label)

    frappe.db.commit()
    return {"ok": True, "invoice": si.name, "created": created}


def on_sales_invoice_submit(doc, method=None):
    if getattr(frappe.flags, "kpws_processing_welfare_invoice", False):
        return
    try:
        frappe.flags.kpws_processing_welfare_invoice = True
        process_sales_invoice_submit(doc.name)
    finally:
        frappe.flags.kpws_processing_welfare_invoice = False


def apply_invoice_accounting_before_insert(si, group, settings, registration, payment_plan, payment_rows):
    """Apply debit_to, POS/non-POS behavior and item account mapping before insert."""
    group = group or "Cash"
    purpose = (registration or {}).get("purpose") or ""

    # Item income / COGS mapping
    income_account = None
    if group == "Panel":
        income_account = settings.get("panel_income_account") or None
    else:
        income_account = settings.get("cash_income_account") or None

    expense_account = settings.get("pharmacy_cogs_account") or None

    for item in si.get("items") or []:
        if income_account and hasattr(item, "income_account"):
            item.income_account = income_account
        if expense_account and hasattr(item, "expense_account"):
            item.expense_account = expense_account

    # Welfare must remain receivable; Zakat/Donation is cleared by Journal Entry after submit.
    if group == "Welfare":
        si.is_pos = 0
        si.set("payments", [])
        if settings.get("welfare_receivable_account"):
            si.debit_to = settings.get("welfare_receivable_account")

    # Panel should be receivable by default, unless admin chooses old POS payment behavior.
    elif group == "Panel" and (settings.get("panel_billing_mode") or "Receivable") == "Receivable":
        si.is_pos = 0
        si.set("payments", [])
        if settings.get("panel_receivable_account"):
            si.debit_to = settings.get("panel_receivable_account")

    # Cash/Walk-in remain POS if payment rows are present.
    elif payment_rows:
        si.is_pos = 1


def _cancel_doc_if_submitted(doctype, name):
    if not name or not frappe.db.exists(doctype, name):
        return None
    doc = frappe.get_doc(doctype, name)
    if cint(doc.docstatus) == 1:
        doc.flags.ignore_permissions = True
        doc.cancel()
        return name
    return None


def on_sales_invoice_cancel(doc, method=None):
    group = doc.get("custom_kpws_patient_billing_group") if _has_field("Sales Invoice", "custom_kpws_patient_billing_group") else None
    if group != "Welfare":
        return

    canceled = {}

    if _has_field("Sales Invoice", "custom_kpws_auto_journal_entry") and doc.get("custom_kpws_auto_journal_entry"):
        canceled["journal_entry"] = _cancel_doc_if_submitted("Journal Entry", doc.get("custom_kpws_auto_journal_entry"))

    for fieldname, label in [
        ("custom_kpws_cash_payment_entry", "cash_payment_entry"),
        ("custom_kpws_card_payment_entry", "card_payment_entry"),
    ]:
        if _has_field("Sales Invoice", fieldname) and doc.get(fieldname):
            canceled[label] = _cancel_doc_if_submitted("Payment Entry", doc.get(fieldname))

    return canceled


# KPWS_BEFORE_SUBMIT_FORCE_NON_POS_V30
def before_sales_invoice_submit(doc, method=None):
    """
    Runs before ERPNext Sales Invoice on_submit validation.

    Purpose:
    If KPWS Pharmacy Billing creates a Welfare/Panel receivable invoice but
    the invoice is still marked as POS / Include POS Payment, ERPNext throws:
        At least one mode of payment is required for POS invoice.

    This converts such invoices to normal receivable invoices before ERPNext
    POS validation runs.
    """
    import frappe
    from frappe.utils import flt, nowdate, cint

    if doc.doctype != "Sales Invoice":
        return

    # Only handle invoices that are still marked POS
    if not cint(getattr(doc, "is_pos", 0)):
        return

    # If invoice has actual payment rows, keep normal POS behavior
    has_paid_row = False
    for row in (getattr(doc, "payments", None) or []):
        if flt(getattr(row, "amount", 0)) > 0:
            has_paid_row = True
            break

    if has_paid_row:
        return

    settings = frappe.get_single("KPWS Pharmacy Billing Settings")

    welfare_receivable = settings.get("welfare_receivable_account")
    panel_receivable = settings.get("panel_receivable_account")
    panel_mode = settings.get("panel_billing_mode") or "Receivable"

    price_list = (getattr(doc, "selling_price_list", "") or "").lower()
    debit_to = getattr(doc, "debit_to", None)

    welfare_covered = flt(getattr(doc, "custom_kpws_welfare_covered_amount", 0))
    patient_share = flt(getattr(doc, "custom_kpws_patient_share_amount", 0))

    # Detect KPWS custom page invoices.
    # Strong cases:
    # - Welfare amount exists
    # - Debit To is Welfare Receivable
    # - Price List is panel SPP
    # - Debit To is panel receivable
    # - No payment rows and page has created an invoice from KPWS billing
    is_welfare = bool(
        welfare_covered > 0
        or patient_share > 0
        or (welfare_receivable and debit_to == welfare_receivable)
    )

    is_panel_receivable = bool(
        panel_mode == "Receivable"
        and (
            (panel_receivable and debit_to == panel_receivable)
            or "spp" in price_list
            or "panel" in price_list
        )
    )

    # Last safety: if it is POS but has no payment rows, it will fail anyway.
    # Convert it to normal Sales Invoice instead of letting submission break.
    should_convert = bool(is_welfare or is_panel_receivable or not has_paid_row)

    if not should_convert:
        return

    doc.is_pos = 0
    doc.pos_profile = None
    doc.set("payments", [])

    for fieldname in (
        "paid_amount",
        "base_paid_amount",
        "change_amount",
        "base_change_amount",
        "write_off_amount",
        "base_write_off_amount",
    ):
        if hasattr(doc, fieldname):
            doc.set(fieldname, 0)

    if is_welfare and welfare_receivable:
        doc.debit_to = welfare_receivable

    if is_panel_receivable and panel_receivable:
        doc.debit_to = panel_receivable

    if not getattr(doc, "due_date", None):
        doc.due_date = getattr(doc, "posting_date", None) or nowdate()


# KPWS_FIX_WELFARE_JE_ALLOCATION_V31
def _kpws_create_allocated_welfare_journal_entry(si, settings, source_account, amount):
    """
    Correct JE allocation:
      Dr ZAKAT/DONATION DISBURSE
      Cr Sales Invoice debit_to account
         with Party + Reference Type/Name

    This is required so ERPNext reduces Sales Invoice outstanding.
    """
    import frappe
    from frappe.utils import flt, nowdate

    amount = flt(amount, 2)
    if amount <= 0:
        return None

    if not source_account:
        frappe.throw("Missing Zakat/Donation disbursement account in KPWS Pharmacy Billing Settings")

    credit_account = si.debit_to

    if not credit_account:
        credit_account = settings.get("welfare_receivable_account")

    if not credit_account:
        frappe.throw("Missing Sales Invoice Debit To / Welfare Receivable Account")

    existing = frappe.db.get_value(
        "Journal Entry Account",
        {
            "reference_type": "Sales Invoice",
            "reference_name": si.name,
            "account": credit_account,
            "credit_in_account_currency": [">", 0],
            "docstatus": 1,
        },
        "parent",
    )

    if existing:
        return existing

    je = frappe.new_doc("Journal Entry")
    je.voucher_type = "Journal Entry"
    je.company = si.company
    je.posting_date = si.posting_date or nowdate()
    je.user_remark = "Auto welfare settlement against Sales Invoice {0}".format(si.name)

    je.append("accounts", {
        "account": source_account,
        "debit_in_account_currency": amount,
        "credit_in_account_currency": 0,
        "cost_center": getattr(si, "cost_center", None),
    })

    je.append("accounts", {
        "account": credit_account,
        "party_type": "Customer",
        "party": si.customer,
        "reference_type": "Sales Invoice",
        "reference_name": si.name,
        "debit_in_account_currency": 0,
        "credit_in_account_currency": amount,
        "cost_center": getattr(si, "cost_center", None),
    })

    je.insert(ignore_permissions=True)
    je.submit()

    frappe.db.set_value("Sales Invoice", si.name, "custom_kpws_auto_journal_entry", je.name)

    # Force ERPNext to refresh invoice outstanding/status
    try:
        si.reload()
        si.set_status(update=True)
        si.notify_update()
    except Exception:
        pass

    return je.name


# Override old submit handler with allocated JE logic
def on_sales_invoice_submit(doc, method=None):
    import frappe
    from frappe.utils import flt

    settings = frappe.get_single("KPWS Pharmacy Billing Settings")

    if not settings.get("enable_welfare_auto_journal"):
        return

    welfare_amount = flt(doc.get("custom_kpws_welfare_covered_amount"))
    if welfare_amount <= 0:
        return

    # Detect source from available fields / context
    source_text = " ".join([
        str(doc.get("custom_kpws_welfare_source") or ""),
        str(doc.get("custom_kpws_assistance_source") or ""),
        str(doc.get("custom_kpws_purpose") or ""),
        str(doc.get("custom_patient_type") or ""),
        str(doc.get("remarks") or ""),
    ]).lower()

    # Default to Zakat only if Donation is not detected.
    if "donation" in source_text:
        disbursement_account = settings.get("donation_disbursement_account")
    else:
        disbursement_account = settings.get("zakat_disbursement_account")

    _kpws_create_allocated_welfare_journal_entry(
        doc,
        settings,
        disbursement_account,
        welfare_amount,
    )


# KPWS_PARTIAL_WELFARE_PAYMENT_ENTRY_V33
def _kpws_v33_mop_account(mode_of_payment, company):
    import frappe

    if not mode_of_payment:
        return None

    if not frappe.db.exists("Mode of Payment", mode_of_payment):
        return None

    mop = frappe.get_doc("Mode of Payment", mode_of_payment)
    for row in mop.get("accounts") or []:
        if row.company == company and row.default_account:
            return row.default_account

    return None


def _kpws_v33_existing_payment(invoice_name, mode_of_payment):
    import frappe

    row = frappe.db.sql("""
        SELECT pe.name
        FROM `tabPayment Entry Reference` ref
        INNER JOIN `tabPayment Entry` pe ON pe.name = ref.parent
        WHERE ref.reference_doctype='Sales Invoice'
          AND ref.reference_name=%s
          AND pe.mode_of_payment=%s
          AND pe.docstatus=1
        LIMIT 1
    """, (invoice_name, mode_of_payment), as_dict=True)

    return row[0].name if row else None


def _kpws_v33_make_patient_payment_entry(si, settings, mode_of_payment, amount, link_field=None):
    import frappe
    from frappe.utils import flt, nowdate

    amount = flt(amount, 2)

    if amount <= 0:
        return None

    if not mode_of_payment:
        frappe.throw("Patient share Mode of Payment is missing in KPWS Pharmacy Billing Settings.")

    existing = _kpws_v33_existing_payment(si.name, mode_of_payment)
    if existing:
        if link_field and si.meta.has_field(link_field):
            frappe.db.set_value("Sales Invoice", si.name, link_field, existing, update_modified=False)
        return existing

    paid_to = _kpws_v33_mop_account(mode_of_payment, si.company)
    if not paid_to:
        frappe.throw("Mode of Payment {0} has no Cash/Bank account for company {1}.".format(mode_of_payment, si.company))

    receivable = si.debit_to or settings.get("welfare_receivable_account")
    if not receivable:
        frappe.throw("Receivable account missing on Sales Invoice {0}.".format(si.name))

    pe = frappe.new_doc("Payment Entry")
    pe.payment_type = "Receive"
    pe.company = si.company
    pe.posting_date = si.posting_date or nowdate()
    pe.mode_of_payment = mode_of_payment
    pe.party_type = "Customer"
    pe.party = si.customer
    pe.paid_from = receivable
    pe.paid_to = paid_to
    pe.paid_amount = amount
    pe.received_amount = amount
    pe.reference_no = si.name
    pe.reference_date = si.posting_date or nowdate()

    pe.append("references", {
        "reference_doctype": "Sales Invoice",
        "reference_name": si.name,
        "allocated_amount": amount,
    })

    pe.insert(ignore_permissions=True)
    pe.submit()

    if link_field and si.meta.has_field(link_field):
        frappe.db.set_value("Sales Invoice", si.name, link_field, pe.name, update_modified=False)

    return pe.name


def _kpws_v33_existing_welfare_journal(invoice_name):
    import frappe

    row = frappe.db.sql("""
        SELECT je.name
        FROM `tabJournal Entry Account` acc
        INNER JOIN `tabJournal Entry` je ON je.name = acc.parent
        WHERE acc.reference_type='Sales Invoice'
          AND acc.reference_name=%s
          AND acc.credit_in_account_currency > 0
          AND je.docstatus=1
        LIMIT 1
    """, invoice_name, as_dict=True)

    return row[0].name if row else None


def _kpws_v33_make_welfare_journal(si, settings, amount):
    import frappe
    from frappe.utils import flt, nowdate

    amount = flt(amount, 2)

    if amount <= 0:
        return None

    existing = _kpws_v33_existing_welfare_journal(si.name)
    if existing:
        if si.meta.has_field("custom_kpws_auto_journal_entry"):
            frappe.db.set_value("Sales Invoice", si.name, "custom_kpws_auto_journal_entry", existing, update_modified=False)
        return existing

    purpose = (si.get("custom_kpws_purpose") or "").strip().lower()

    if purpose == "donation":
        expense_account = settings.get("donation_disbursement_account")
        purpose_label = "Donation"
    else:
        expense_account = settings.get("zakat_disbursement_account")
        purpose_label = "Zakat"

    if not expense_account:
        frappe.throw("{0} Disbursement Account is missing in KPWS Pharmacy Billing Settings.".format(purpose_label))

    receivable = si.debit_to or settings.get("welfare_receivable_account")
    if not receivable:
        frappe.throw("Welfare Receivable Account is missing.")

    je = frappe.new_doc("Journal Entry")
    je.voucher_type = "Journal Entry"
    je.company = si.company
    je.posting_date = si.posting_date or nowdate()
    je.user_remark = "Auto {0} welfare settlement against Sales Invoice {1}".format(purpose_label, si.name)

    je.append("accounts", {
        "account": expense_account,
        "debit_in_account_currency": amount,
        "credit_in_account_currency": 0,
    })

    je.append("accounts", {
        "account": receivable,
        "party_type": "Customer",
        "party": si.customer,
        "reference_type": "Sales Invoice",
        "reference_name": si.name,
        "debit_in_account_currency": 0,
        "credit_in_account_currency": amount,
    })

    je.insert(ignore_permissions=True)
    je.submit()

    if si.meta.has_field("custom_kpws_auto_journal_entry"):
        frappe.db.set_value("Sales Invoice", si.name, "custom_kpws_auto_journal_entry", je.name, update_modified=False)

    return je.name


# Override latest submit handler for partial Welfare.
def on_sales_invoice_submit(doc, method=None):
    import frappe
    from frappe.utils import flt, cint

    if getattr(frappe.flags, "kpws_v33_processing_welfare", False):
        return

    try:
        frappe.flags.kpws_v33_processing_welfare = True

        si = frappe.get_doc("Sales Invoice", doc.name)

        group = si.get("custom_kpws_patient_billing_group")
        if group != "Welfare":
            return

        settings = frappe.get_single("KPWS Pharmacy Billing Settings")

        welfare_amount = flt(si.get("custom_kpws_welfare_covered_amount"), 2)
        patient_cash = flt(si.get("custom_kpws_patient_cash_amount"), 2)
        patient_card = flt(si.get("custom_kpws_patient_card_amount"), 2)

        created = {}

        # 1. Patient share through real Cash/Card Payment Entries
        if cint(settings.get("enable_welfare_patient_share_payment_entry")):
            if patient_cash > 0:
                created["cash_payment_entry"] = _kpws_v33_make_patient_payment_entry(
                    si,
                    settings,
                    settings.get("cash_mode_of_payment") or settings.get("default_mode_of_payment"),
                    patient_cash,
                    "custom_kpws_cash_payment_entry",
                )

            if patient_card > 0:
                created["card_payment_entry"] = _kpws_v33_make_patient_payment_entry(
                    si,
                    settings,
                    settings.get("card_mode_of_payment"),
                    patient_card,
                    "custom_kpws_card_payment_entry",
                )

        # 2. Welfare covered share through Zakat/Donation Journal Entry
        if cint(settings.get("enable_welfare_auto_journal")) and welfare_amount > 0:
            created["journal_entry"] = _kpws_v33_make_welfare_journal(
                si,
                settings,
                welfare_amount,
            )

        # 3. Refresh status/outstanding
        try:
            si.reload()
            si.set_status(update=True)
            si.notify_update()
        except Exception:
            pass

        frappe.db.commit()

    finally:
        frappe.flags.kpws_v33_processing_welfare = False


# KPWS_PARTIAL_WELFARE_PAYMENT_ENTRY_V33
def _kpws_v33_mop_account(mode_of_payment, company):
    import frappe

    if not mode_of_payment:
        return None

    if not frappe.db.exists("Mode of Payment", mode_of_payment):
        return None

    mop = frappe.get_doc("Mode of Payment", mode_of_payment)
    for row in mop.get("accounts") or []:
        if row.company == company and row.default_account:
            return row.default_account

    return None


def _kpws_v33_existing_payment(invoice_name, mode_of_payment):
    import frappe

    row = frappe.db.sql("""
        SELECT pe.name
        FROM `tabPayment Entry Reference` ref
        INNER JOIN `tabPayment Entry` pe ON pe.name = ref.parent
        WHERE ref.reference_doctype='Sales Invoice'
          AND ref.reference_name=%s
          AND pe.mode_of_payment=%s
          AND pe.docstatus=1
        LIMIT 1
    """, (invoice_name, mode_of_payment), as_dict=True)

    return row[0].name if row else None


def _kpws_v33_make_patient_payment_entry(si, settings, mode_of_payment, amount, link_field=None):
    import frappe
    from frappe.utils import flt, nowdate

    amount = flt(amount, 2)

    if amount <= 0:
        return None

    if not mode_of_payment:
        frappe.throw("Patient share Mode of Payment is missing in KPWS Pharmacy Billing Settings.")

    existing = _kpws_v33_existing_payment(si.name, mode_of_payment)
    if existing:
        if link_field and si.meta.has_field(link_field):
            frappe.db.set_value("Sales Invoice", si.name, link_field, existing, update_modified=False)
        return existing

    paid_to = _kpws_v33_mop_account(mode_of_payment, si.company)
    if not paid_to:
        frappe.throw("Mode of Payment {0} has no Cash/Bank account for company {1}.".format(mode_of_payment, si.company))

    receivable = si.debit_to or settings.get("welfare_receivable_account")
    if not receivable:
        frappe.throw("Receivable account missing on Sales Invoice {0}.".format(si.name))

    pe = frappe.new_doc("Payment Entry")
    pe.payment_type = "Receive"
    pe.company = si.company
    pe.posting_date = si.posting_date or nowdate()
    pe.mode_of_payment = mode_of_payment
    pe.party_type = "Customer"
    pe.party = si.customer
    pe.paid_from = receivable
    pe.paid_to = paid_to
    pe.paid_amount = amount
    pe.received_amount = amount
    pe.reference_no = si.name
    pe.reference_date = si.posting_date or nowdate()

    pe.append("references", {
        "reference_doctype": "Sales Invoice",
        "reference_name": si.name,
        "allocated_amount": amount,
    })

    pe.insert(ignore_permissions=True)
    pe.submit()

    if link_field and si.meta.has_field(link_field):
        frappe.db.set_value("Sales Invoice", si.name, link_field, pe.name, update_modified=False)

    return pe.name


def _kpws_v33_existing_welfare_journal(invoice_name):
    import frappe

    row = frappe.db.sql("""
        SELECT je.name
        FROM `tabJournal Entry Account` acc
        INNER JOIN `tabJournal Entry` je ON je.name = acc.parent
        WHERE acc.reference_type='Sales Invoice'
          AND acc.reference_name=%s
          AND acc.credit_in_account_currency > 0
          AND je.docstatus=1
        LIMIT 1
    """, invoice_name, as_dict=True)

    return row[0].name if row else None


def _kpws_v33_make_welfare_journal(si, settings, amount):
    import frappe
    from frappe.utils import flt, nowdate

    amount = flt(amount, 2)

    if amount <= 0:
        return None

    existing = _kpws_v33_existing_welfare_journal(si.name)
    if existing:
        if si.meta.has_field("custom_kpws_auto_journal_entry"):
            frappe.db.set_value("Sales Invoice", si.name, "custom_kpws_auto_journal_entry", existing, update_modified=False)
        return existing

    purpose = (si.get("custom_kpws_purpose") or "").strip().lower()

    if purpose == "donation":
        expense_account = settings.get("donation_disbursement_account")
        purpose_label = "Donation"
    else:
        expense_account = settings.get("zakat_disbursement_account")
        purpose_label = "Zakat"

    if not expense_account:
        frappe.throw("{0} Disbursement Account is missing in KPWS Pharmacy Billing Settings.".format(purpose_label))

    receivable = si.debit_to or settings.get("welfare_receivable_account")
    if not receivable:
        frappe.throw("Welfare Receivable Account is missing.")

    je = frappe.new_doc("Journal Entry")
    je.voucher_type = "Journal Entry"
    je.company = si.company
    je.posting_date = si.posting_date or nowdate()
    je.user_remark = "Auto {0} welfare settlement against Sales Invoice {1}".format(purpose_label, si.name)

    je.append("accounts", {
        "account": expense_account,
        "debit_in_account_currency": amount,
        "credit_in_account_currency": 0,
    })

    je.append("accounts", {
        "account": receivable,
        "party_type": "Customer",
        "party": si.customer,
        "reference_type": "Sales Invoice",
        "reference_name": si.name,
        "debit_in_account_currency": 0,
        "credit_in_account_currency": amount,
    })

    je.insert(ignore_permissions=True)
    je.submit()

    if si.meta.has_field("custom_kpws_auto_journal_entry"):
        frappe.db.set_value("Sales Invoice", si.name, "custom_kpws_auto_journal_entry", je.name, update_modified=False)

    return je.name


# Override latest submit handler for partial Welfare.
def on_sales_invoice_submit(doc, method=None):
    import frappe
    from frappe.utils import flt, cint

    if getattr(frappe.flags, "kpws_v33_processing_welfare", False):
        return

    try:
        frappe.flags.kpws_v33_processing_welfare = True

        si = frappe.get_doc("Sales Invoice", doc.name)

        group = si.get("custom_kpws_patient_billing_group")
        if group != "Welfare":
            return

        settings = frappe.get_single("KPWS Pharmacy Billing Settings")

        welfare_amount = flt(si.get("custom_kpws_welfare_covered_amount"), 2)
        patient_cash = flt(si.get("custom_kpws_patient_cash_amount"), 2)
        patient_card = flt(si.get("custom_kpws_patient_card_amount"), 2)

        created = {}

        # 1. Patient share through real Cash/Card Payment Entries
        if cint(settings.get("enable_welfare_patient_share_payment_entry")):
            if patient_cash > 0:
                created["cash_payment_entry"] = _kpws_v33_make_patient_payment_entry(
                    si,
                    settings,
                    settings.get("cash_mode_of_payment") or settings.get("default_mode_of_payment"),
                    patient_cash,
                    "custom_kpws_cash_payment_entry",
                )

            if patient_card > 0:
                created["card_payment_entry"] = _kpws_v33_make_patient_payment_entry(
                    si,
                    settings,
                    settings.get("card_mode_of_payment"),
                    patient_card,
                    "custom_kpws_card_payment_entry",
                )

        # 2. Welfare covered share through Zakat/Donation Journal Entry
        if cint(settings.get("enable_welfare_auto_journal")) and welfare_amount > 0:
            created["journal_entry"] = _kpws_v33_make_welfare_journal(
                si,
                settings,
                welfare_amount,
            )

        # 3. Refresh status/outstanding
        try:
            si.reload()
            si.set_status(update=True)
            si.notify_update()
        except Exception:
            pass

        frappe.db.commit()

    finally:
        frappe.flags.kpws_v33_processing_welfare = False


# KPWS_FINAL_WELFARE_SETTLEMENT_V34
def _kpws_v34_flt(value, precision=2):
    from frappe.utils import flt
    return flt(value or 0, precision)


def _kpws_v34_get_mop_account(mode_of_payment, company):
    import frappe

    if not mode_of_payment:
        return None

    if not frappe.db.exists("Mode of Payment", mode_of_payment):
        return None

    mop = frappe.get_doc("Mode of Payment", mode_of_payment)

    for row in mop.get("accounts") or []:
        if row.company == company and row.default_account:
            return row.default_account

    return None


def _kpws_v34_get_cash_mode(settings):
    for field in ("cash_mode_of_payment", "default_cash_mode_of_payment", "default_mode_of_payment"):
        value = settings.get(field)
        if value:
            return value
    return "Cash"


def _kpws_v34_get_card_mode(settings):
    for field in ("card_mode_of_payment", "bank_mode_of_payment", "default_card_mode_of_payment"):
        value = settings.get(field)
        if value:
            return value
    return None


def _kpws_v34_get_welfare_registration_context(si):
    """
    Flexible lookup because KPWS Patient Registration Form field names have changed multiple times.
    Returns:
        {"purpose": "Zakat"/"Donation", "percentage": 70}
    """
    import frappe

    possible_doctypes = [
        "Patient Registration Form",
        "KPWS Patient Registration Form",
    ]

    patient = (
        si.get("patient")
        or si.get("custom_patient")
        or si.get("custom_kpws_patient")
        or si.get("custom_patient_id")
    )

    if not patient:
        return {}

    for dt in possible_doctypes:
        if not frappe.db.exists("DocType", dt):
            continue

        meta = frappe.get_meta(dt)

        patient_fields = [
            "patient",
            "custom_patient",
            "custom_kpws_patient",
            "patient_id",
            "custom_patient_id",
        ]

        patient_field = None
        for fieldname in patient_fields:
            if meta.has_field(fieldname):
                patient_field = fieldname
                break

        if not patient_field:
            continue

        rows = frappe.get_all(
            dt,
            filters={
                patient_field: patient,
                "docstatus": 1,
            },
            fields=["name"],
            order_by="modified desc",
            limit=1,
        )

        if not rows:
            continue

        reg = frappe.get_doc(dt, rows[0].name)

        purpose = None
        for fieldname in (
            "purpose",
            "custom_kpws_welfare_type",
            "custom_welfare_type",
            "assistance_source",
            "custom_assistance_source",
        ):
            if meta.has_field(fieldname) and reg.get(fieldname):
                purpose = reg.get(fieldname)
                break

        percentage = 0
        for fieldname in (
            "custom_kpws_welfare_percentage",
            "custom_welfare_percentage",
            "discount_value",
            "custom_discount_value",
            "percentage",
            "assistance_percentage",
            "custom_assistance_percentage",
        ):
            if meta.has_field(fieldname) and reg.get(fieldname):
                percentage = _kpws_v34_flt(reg.get(fieldname))
                break

        return {
            "registration": reg.name,
            "purpose": purpose,
            "percentage": percentage,
        }

    return {}


def _kpws_v34_get_context(si, covered_amount=None, patient_cash=None, patient_card=None):
    """
    Determines welfare covered amount and patient share.
    Priority:
      1. Explicit override
      2. Custom fields on invoice
      3. Welfare Registration percentage
    """
    total = _kpws_v34_flt(si.get("rounded_total") or si.get("grand_total"))

    covered = _kpws_v34_flt(
        covered_amount
        if covered_amount is not None
        else si.get("custom_kpws_welfare_covered_amount")
    )

    cash = _kpws_v34_flt(
        patient_cash
        if patient_cash is not None
        else si.get("custom_kpws_patient_cash_amount")
    )

    card = _kpws_v34_flt(
        patient_card
        if patient_card is not None
        else si.get("custom_kpws_patient_card_amount")
    )

    purpose = (
        si.get("custom_kpws_purpose")
        or si.get("custom_kpws_assistance_source")
        or si.get("custom_kpws_welfare_source")
        or ""
    )

    percentage = _kpws_v34_flt(si.get("custom_kpws_approved_percentage"))

    reg_ctx = {}

    if covered <= 0 or not purpose or percentage <= 0:
        reg_ctx = _kpws_v34_get_welfare_registration_context(si)

    if not purpose:
        purpose = reg_ctx.get("purpose") or "Zakat"

    if percentage <= 0:
        percentage = _kpws_v34_flt(reg_ctx.get("percentage"))

    if covered <= 0 and percentage > 0:
        covered = _kpws_v34_flt(total * percentage / 100)

    if covered > total:
        covered = total

    patient_share = _kpws_v34_flt(total - covered)

    # If patient share exists but cash/card split is not stored, default it to cash.
    # This prevents full outstanding from remaining.
    if patient_share > 0 and _kpws_v34_flt(cash + card) <= 0:
        cash = patient_share

    # Fix small rounding difference.
    if patient_share > 0 and _kpws_v34_flt(cash + card) != patient_share:
        diff = _kpws_v34_flt(patient_share - cash - card)
        cash = _kpws_v34_flt(cash + diff)

    return {
        "total": total,
        "covered": covered,
        "patient_share": patient_share,
        "patient_cash": cash,
        "patient_card": card,
        "purpose": purpose,
        "percentage": percentage,
        "registration": reg_ctx.get("registration"),
    }


def _kpws_v34_existing_allocated_je(si_name):
    import frappe

    rows = frappe.db.sql("""
        SELECT je.name
        FROM `tabJournal Entry Account` acc
        INNER JOIN `tabJournal Entry` je ON je.name = acc.parent
        WHERE acc.reference_type='Sales Invoice'
          AND acc.reference_name=%s
          AND acc.credit_in_account_currency > 0
          AND je.docstatus=1
        LIMIT 1
    """, (si_name,), as_dict=True)

    return rows[0].name if rows else None


def _kpws_v34_existing_payment(si_name, mode_of_payment):
    import frappe

    rows = frappe.db.sql("""
        SELECT pe.name
        FROM `tabPayment Entry Reference` ref
        INNER JOIN `tabPayment Entry` pe ON pe.name = ref.parent
        WHERE ref.reference_doctype='Sales Invoice'
          AND ref.reference_name=%s
          AND pe.mode_of_payment=%s
          AND pe.docstatus=1
        LIMIT 1
    """, (si_name, mode_of_payment), as_dict=True)

    return rows[0].name if rows else None


def _kpws_v34_make_welfare_je(si, settings, context):
    import frappe
    from frappe.utils import nowdate

    amount = _kpws_v34_flt(context.get("covered"))

    if amount <= 0:
        return None

    existing = _kpws_v34_existing_allocated_je(si.name)
    if existing:
        if si.meta.has_field("custom_kpws_auto_journal_entry"):
            frappe.db.set_value("Sales Invoice", si.name, "custom_kpws_auto_journal_entry", existing, update_modified=False)
        return existing

    purpose = (context.get("purpose") or "Zakat").strip().lower()

    if "donation" in purpose:
        expense_account = settings.get("donation_disbursement_account")
        label = "Donation"
    else:
        expense_account = settings.get("zakat_disbursement_account")
        label = "Zakat"

    if not expense_account:
        frappe.throw("{0} Disbursement Account is missing in KPWS Pharmacy Billing Settings.".format(label))

    receivable = si.debit_to or settings.get("welfare_receivable_account")

    if not receivable:
        frappe.throw("Sales Invoice Debit To / Welfare Receivable Account is missing.")

    je = frappe.new_doc("Journal Entry")
    je.voucher_type = "Journal Entry"
    je.company = si.company
    je.posting_date = si.posting_date or nowdate()
    je.user_remark = "Auto {0} welfare settlement against Sales Invoice {1}".format(label, si.name)

    je.append("accounts", {
        "account": expense_account,
        "debit_in_account_currency": amount,
        "credit_in_account_currency": 0,
    })

    je.append("accounts", {
        "account": receivable,
        "party_type": "Customer",
        "party": si.customer,
        "reference_type": "Sales Invoice",
        "reference_name": si.name,
        "debit_in_account_currency": 0,
        "credit_in_account_currency": amount,
    })

    je.insert(ignore_permissions=True)
    je.submit()

    if si.meta.has_field("custom_kpws_auto_journal_entry"):
        frappe.db.set_value("Sales Invoice", si.name, "custom_kpws_auto_journal_entry", je.name, update_modified=False)

    return je.name


def _kpws_v34_make_patient_payment(si, settings, mode_of_payment, amount, link_field=None):
    import frappe
    from frappe.utils import nowdate

    amount = _kpws_v34_flt(amount)

    if amount <= 0:
        return None

    if not mode_of_payment:
        frappe.throw("Patient share Mode of Payment is missing in KPWS Pharmacy Billing Settings.")

    existing = _kpws_v34_existing_payment(si.name, mode_of_payment)

    if existing:
        if link_field and si.meta.has_field(link_field):
            frappe.db.set_value("Sales Invoice", si.name, link_field, existing, update_modified=False)
        return existing

    paid_to = _kpws_v34_get_mop_account(mode_of_payment, si.company)

    if not paid_to:
        frappe.throw("Mode of Payment {0} has no Cash/Bank account for company {1}.".format(mode_of_payment, si.company))

    receivable = si.debit_to or settings.get("welfare_receivable_account")

    if not receivable:
        frappe.throw("Receivable account is missing for Sales Invoice {0}.".format(si.name))

    pe = frappe.new_doc("Payment Entry")
    pe.payment_type = "Receive"
    pe.company = si.company
    pe.posting_date = si.posting_date or nowdate()
    pe.mode_of_payment = mode_of_payment
    pe.party_type = "Customer"
    pe.party = si.customer
    pe.paid_from = receivable
    pe.paid_to = paid_to
    pe.paid_amount = amount
    pe.received_amount = amount
    pe.reference_no = si.name
    pe.reference_date = si.posting_date or nowdate()

    pe.append("references", {
        "reference_doctype": "Sales Invoice",
        "reference_name": si.name,
        "allocated_amount": amount,
    })

    pe.insert(ignore_permissions=True)
    pe.submit()

    if link_field and si.meta.has_field(link_field):
        frappe.db.set_value("Sales Invoice", si.name, link_field, pe.name, update_modified=False)

    return pe.name


def _kpws_v34_finalize_invoice(si_name):
    import frappe

    si = frappe.get_doc("Sales Invoice", si_name)

    try:
        si.set_status(update=True)
    except Exception:
        pass

    frappe.db.commit()

    return {
        "invoice": si.name,
        "status": frappe.db.get_value("Sales Invoice", si.name, "status"),
        "outstanding": frappe.db.get_value("Sales Invoice", si.name, "outstanding_amount"),
        "auto_journal": frappe.db.get_value("Sales Invoice", si.name, "custom_kpws_auto_journal_entry"),
        "cash_pe": frappe.db.get_value("Sales Invoice", si.name, "custom_kpws_cash_payment_entry"),
        "card_pe": frappe.db.get_value("Sales Invoice", si.name, "custom_kpws_card_payment_entry"),
    }


def _kpws_v34_set_invoice_fields_direct(si, context):
    import frappe

    updates = {
        "is_pos": 0,
        "pos_profile": "",
    }

    if si.meta.has_field("custom_kpws_welfare_covered_amount"):
        updates["custom_kpws_welfare_covered_amount"] = context.get("covered")

    if si.meta.has_field("custom_kpws_patient_share_amount"):
        updates["custom_kpws_patient_share_amount"] = context.get("patient_share")

    if si.meta.has_field("custom_kpws_patient_cash_amount"):
        updates["custom_kpws_patient_cash_amount"] = context.get("patient_cash")

    if si.meta.has_field("custom_kpws_patient_card_amount"):
        updates["custom_kpws_patient_card_amount"] = context.get("patient_card")

    if si.meta.has_field("custom_kpws_purpose"):
        updates["custom_kpws_purpose"] = context.get("purpose")

    if si.meta.has_field("custom_kpws_approved_percentage"):
        updates["custom_kpws_approved_percentage"] = context.get("percentage")

    for field, value in updates.items():
        frappe.db.set_value("Sales Invoice", si.name, field, value, update_modified=False)

    frappe.db.sql("""
        DELETE FROM `tabSales Invoice Payment`
        WHERE parent=%s AND parenttype='Sales Invoice'
    """, (si.name,))


def repair_welfare_invoice(si_name, covered_amount=None, patient_cash=None, patient_card=None):
    """
    Manual repair for already-posted invoices.

    Example:
        repair_welfare_invoice("SINV-KPWS-2492/26")

    For explicit split:
        repair_welfare_invoice("SINV-KPWS-2492/26", covered_amount=7000, patient_cash=3000, patient_card=0)
    """
    import frappe

    si = frappe.get_doc("Sales Invoice", si_name)
    settings = frappe.get_single("KPWS Pharmacy Billing Settings")

    context = _kpws_v34_get_context(
        si,
        covered_amount=covered_amount,
        patient_cash=patient_cash,
        patient_card=patient_card,
    )

    if context.get("covered") <= 0 and context.get("patient_share") <= 0:
        frappe.throw("Could not calculate welfare coverage or patient share for invoice {0}".format(si.name))

    _kpws_v34_set_invoice_fields_direct(si, context)

    si.reload()

    if context.get("patient_cash") > 0:
        _kpws_v34_make_patient_payment(
            si,
            settings,
            _kpws_v34_get_cash_mode(settings),
            context.get("patient_cash"),
            "custom_kpws_cash_payment_entry",
        )

    if context.get("patient_card") > 0:
        _kpws_v34_make_patient_payment(
            si,
            settings,
            _kpws_v34_get_card_mode(settings),
            context.get("patient_card"),
            "custom_kpws_card_payment_entry",
        )

    if context.get("covered") > 0:
        _kpws_v34_make_welfare_je(si, settings, context)

    return _kpws_v34_finalize_invoice(si.name)


def on_sales_invoice_submit(doc, method=None):
    """
    Future invoices:
    Handles both full and partial welfare settlement.
    """
    import frappe
    from frappe.utils import cint

    if getattr(frappe.flags, "kpws_v34_on_submit_running", False):
        return

    try:
        frappe.flags.kpws_v34_on_submit_running = True

        si = frappe.get_doc("Sales Invoice", doc.name)
        settings = frappe.get_single("KPWS Pharmacy Billing Settings")

        context = _kpws_v34_get_context(si)

        is_welfare = bool(
            context.get("covered") > 0
            or si.debit_to == settings.get("welfare_receivable_account")
            or si.get("custom_kpws_patient_billing_group") == "Welfare"
        )

        if not is_welfare:
            return

        _kpws_v34_set_invoice_fields_direct(si, context)

        si.reload()

        if cint(settings.get("enable_welfare_patient_share_payment_entry")):
            if context.get("patient_cash") > 0:
                _kpws_v34_make_patient_payment(
                    si,
                    settings,
                    _kpws_v34_get_cash_mode(settings),
                    context.get("patient_cash"),
                    "custom_kpws_cash_payment_entry",
                )

            if context.get("patient_card") > 0:
                _kpws_v34_make_patient_payment(
                    si,
                    settings,
                    _kpws_v34_get_card_mode(settings),
                    context.get("patient_card"),
                    "custom_kpws_card_payment_entry",
                )

        if cint(settings.get("enable_welfare_auto_journal")) and context.get("covered") > 0:
            _kpws_v34_make_welfare_je(si, settings, context)

        _kpws_v34_finalize_invoice(si.name)

    finally:
        frappe.flags.kpws_v34_on_submit_running = False


def protect_submitted_kpws_invoice_before_save(doc, method=None):
    """
    Prevent submitted KPWS welfare invoices from being made dirty by browser scripts.
    This fixes:
      - Include Payment (POS) changing from 0 to 1
      - Price List changing after submission
    """
    import frappe

    if doc.doctype != "Sales Invoice" or doc.docstatus != 1 or not doc.name:
        return

    db = frappe.db.get_value(
        "Sales Invoice",
        doc.name,
        [
            "is_pos",
            "pos_profile",
            "selling_price_list",
            "price_list_currency",
            "plc_conversion_rate",
            "conversion_rate",
        ],
        as_dict=True,
    )

    if not db:
        return

    settings = frappe.get_single("KPWS Pharmacy Billing Settings")

    is_kpws_welfare = bool(
        doc.get("custom_kpws_auto_journal_entry")
        or doc.get("custom_kpws_welfare_covered_amount")
        or doc.debit_to == settings.get("welfare_receivable_account")
    )

    if not is_kpws_welfare:
        return

    doc.is_pos = db.is_pos
    doc.pos_profile = db.pos_profile
    doc.selling_price_list = db.selling_price_list
    doc.price_list_currency = db.price_list_currency
    doc.plc_conversion_rate = db.plc_conversion_rate
    doc.conversion_rate = db.conversion_rate

    # Keep POS payments empty for welfare invoices.
    doc.set("payments", [])
