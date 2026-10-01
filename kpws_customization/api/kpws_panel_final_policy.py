import frappe
from frappe.utils import cint

COMPANY = "Kiran Patient Welfare Society"
PANEL_RECEIVABLE = "PANEL RECEIVABLE CONTROL - KPWS"
PANEL_INCOME = "SALES (PANEL) - KPWS"


def _is_ledger(account):
    if not account or not frappe.db.exists("Account", account):
        return False
    return not cint(frappe.db.get_value("Account", account, "is_group"))


def _ensure_panel_receivable():
    if _is_ledger(PANEL_RECEIVABLE):
        return PANEL_RECEIVABLE

    parent = "CURRENT ASSETS - KPWS"
    if frappe.db.exists("Account", "PANEL RECEIVABLES - KPWS"):
        if cint(frappe.db.get_value("Account", "PANEL RECEIVABLES - KPWS", "is_group")):
            parent = "PANEL RECEIVABLES - KPWS"

    if not frappe.db.exists("Account", PANEL_RECEIVABLE):
        acc = frappe.new_doc("Account")
        acc.account_name = "PANEL RECEIVABLE CONTROL"
        acc.company = COMPANY
        acc.parent_account = parent
        acc.root_type = "Asset"
        acc.account_type = "Receivable"
        acc.is_group = 0
        acc.insert(ignore_permissions=True)

    return PANEL_RECEIVABLE


def _settings():
    try:
        return frappe.get_single("KPWS Pharmacy Billing Settings")
    except Exception:
        return frappe._dict()


def _get_panel_receivable_account():
    settings = _settings()
    configured = settings.get("panel_receivable_account")

    if _is_ledger(configured):
        return configured

    return _ensure_panel_receivable()


def _is_panel_invoice(doc):
    price_list = (doc.get("selling_price_list") or "").lower()
    group = (doc.get("custom_kpws_patient_billing_group") or "").lower()
    customer = doc.get("customer")

    if group == "panel":
        return True

    if "spp" in price_list or "panel" in price_list:
        return True

    if customer:
        customer_group = (frappe.db.get_value("Customer", customer, "customer_group") or "").lower()
        if "panel" in customer_group:
            return True

    return False


def apply_panel_policy(doc, method=None):
    """
    Future Panel invoices:
    - Non-POS
    - No payment rows
    - Debit To = Panel Receivable Control
    - Income = SALES (PANEL)
    - Remains unpaid until panel pays later
    """
    if doc.doctype != "Sales Invoice":
        return

    if doc.docstatus == 1:
        return

    if not _is_panel_invoice(doc):
        return

    panel_account = _get_panel_receivable_account()

    doc.is_pos = 0
    doc.pos_profile = None
    doc.debit_to = panel_account
    doc.set("payments", [])

    if doc.meta.has_field("custom_kpws_patient_billing_group"):
        doc.custom_kpws_patient_billing_group = "Panel"

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

    settings = _settings()
    income_account = settings.get("panel_income_account") or PANEL_INCOME

    for item in doc.get("items") or []:
        if hasattr(item, "income_account"):
            item.income_account = income_account


def protect_submitted_panel_invoice(doc, method=None):
    """
    Submitted Panel invoices must not become dirty because of client scripts.
    Restore protected fields from DB before save/update.
    """
    if doc.doctype != "Sales Invoice":
        return

    if doc.docstatus != 1 or not doc.name:
        return

    db = frappe.db.get_value(
        "Sales Invoice",
        doc.name,
        [
            "customer",
            "customer_name",
            "debit_to",
            "is_pos",
            "pos_profile",
            "selling_price_list",
            "price_list_currency",
            "plc_conversion_rate",
            "conversion_rate",
            "currency",
            "status",
            "outstanding_amount",
        ],
        as_dict=True,
    )

    if not db:
        return

    saved_price_list = (db.selling_price_list or "").lower()
    saved_group = frappe.db.get_value("Sales Invoice", doc.name, "custom_kpws_patient_billing_group") if doc.meta.has_field("custom_kpws_patient_billing_group") else ""

    is_panel = bool(
        (doc.name or "").startswith("SINV-KPWS")
        and (
            saved_group == "Panel"
            or "spp" in saved_price_list
            or "panel" in saved_price_list
            or db.debit_to == PANEL_RECEIVABLE
        )
    )

    if not is_panel:
        return

    for fieldname in [
        "customer",
        "customer_name",
        "debit_to",
        "is_pos",
        "pos_profile",
        "selling_price_list",
        "price_list_currency",
        "plc_conversion_rate",
        "conversion_rate",
        "currency",
        "status",
        "outstanding_amount",
    ]:
        if doc.meta.has_field(fieldname):
            doc.set(fieldname, db.get(fieldname))

    doc.is_pos = 0
    doc.pos_profile = None
    doc.set("payments", [])
