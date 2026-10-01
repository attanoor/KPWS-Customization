import frappe

DONATION_INCOME_ACCOUNT = "DONATION IN KIND - KPWS"
DONATION_WAREHOUSE = "Pharmacy Donation Store - KPWS"
PHARMACY_WAREHOUSE = "Pharmacy - KPWS"
RECEIPT_ENTRY_TYPE = "Donation in Kind Receipt"
TRANSFER_ENTRY_TYPE = "Donation in Kind Transfer to Pharmacy"


def apply_donation_in_kind_defaults(doc, method=None):
    entry_type = doc.get("stock_entry_type")

    if entry_type == RECEIPT_ENTRY_TYPE:
        if not doc.get("to_warehouse"):
            doc.to_warehouse = DONATION_WAREHOUSE
        for row in doc.get("items") or []:
            if not row.get("t_warehouse"):
                row.t_warehouse = DONATION_WAREHOUSE
            if not row.get("expense_account"):
                row.expense_account = DONATION_INCOME_ACCOUNT

    elif entry_type == TRANSFER_ENTRY_TYPE:
        if not doc.get("from_warehouse"):
            doc.from_warehouse = DONATION_WAREHOUSE
        if not doc.get("to_warehouse"):
            doc.to_warehouse = PHARMACY_WAREHOUSE
        for row in doc.get("items") or []:
            if not row.get("s_warehouse"):
                row.s_warehouse = DONATION_WAREHOUSE
            if not row.get("t_warehouse"):
                row.t_warehouse = PHARMACY_WAREHOUSE
