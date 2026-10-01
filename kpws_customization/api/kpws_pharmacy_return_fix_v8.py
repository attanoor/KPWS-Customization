from pathlib import Path
import frappe


PATCH_MARKER = "KPWS_PHARMACY_RETURN_FIX_V8_PATCH"


SERVER_PATCH = r'''

# KPWS_PHARMACY_RETURN_FIX_V8_PATCH

def _kpws_invoice_summary(invoice_name):
    si = frappe.get_doc("Sales Invoice", invoice_name)
    patient = _kpws_si_patient_value(si)

    patient_name = None
    mr_number = None
    billing_group = si.get("custom_kpws_patient_billing_group")

    if patient and frappe.db.exists("Patient", patient):
        try:
            pdoc = frappe.get_doc("Patient", patient)
            patient_name = _patient_name(pdoc)
            mr_number = _patient_mr(pdoc)
        except Exception:
            pass

    items = _kpws_returnable_items(invoice_name)
    returnable_items = [
        i for i in items
        if flt(i.get("available_qty") or 0) > 0
    ]

    returnable_amount = 0
    for i in returnable_items:
        returnable_amount += flt(i.get("amount_available") or 0)

    return {
        "name": si.name,
        "posting_date": str(si.posting_date),
        "customer": si.customer,
        "customer_name": si.customer_name,
        "patient": patient,
        "patient_name": patient_name,
        "mr_number": mr_number,
        "billing_group": billing_group,
        "grand_total": flt(si.grand_total),
        "rounded_total": flt(si.rounded_total),
        "paid_amount": flt(si.paid_amount),
        "outstanding_amount": flt(si.outstanding_amount),
        "docstatus": si.docstatus,
        "returnable_item_count": len(returnable_items),
        "returnable_amount": flt(returnable_amount, 2),
    }


def _kpws_returnable_items(invoice_name):
    si = frappe.get_doc("Sales Invoice", invoice_name)
    returned_by_source_row, returned_by_item_code = _kpws_returned_qty_map(invoice_name)

    items = []

    for row in si.get("items") or []:
        original_qty = abs(flt(row.qty))

        returned_qty = returned_by_source_row.get(row.name)
        if returned_qty is None:
            returned_qty = returned_by_item_code.get(row.item_code, 0)

        available_qty = max(original_qty - flt(returned_qty), 0)
        rate = flt(row.rate)
        amount_available = flt(available_qty * rate, 2)

        items.append({
            "source_item_name": row.name,
            "idx": row.idx,
            "item_code": row.item_code,
            "item_name": row.item_name,
            "uom": row.uom,
            "warehouse": row.warehouse,
            "batch_no": row.get("batch_no"),
            "serial_no": row.get("serial_no"),
            "rate": rate,
            "original_qty": original_qty,
            "returned_qty": flt(returned_qty),
            "available_qty": available_qty,
            "amount_available": amount_available,
        })

    return items


@frappe.whitelist()
def debug_return_invoice(invoice_name):
    _require_role()

    if not frappe.db.exists("Sales Invoice", invoice_name):
        return {
            "ok": False,
            "message": "Sales Invoice not found",
            "invoice": invoice_name,
        }

    si = frappe.get_doc("Sales Invoice", invoice_name)

    return {
        "ok": True,
        "invoice": si.name,
        "docstatus": si.docstatus,
        "is_return": si.get("is_return"),
        "return_against": si.get("return_against"),
        "customer": si.customer,
        "grand_total": si.grand_total,
        "items_count": len(si.get("items") or []),
        "summary": _kpws_invoice_summary(invoice_name),
        "returnable_items": _kpws_returnable_items(invoice_name),
    }
'''


def _append_once(path, patch, marker):
    p = Path(path)
    if not p.exists():
        return False

    text = p.read_text()

    if marker in text:
        return False

    p.write_text(text + "\n\n" + patch)
    return True


@frappe.whitelist()
def install():
    app_path = Path(frappe.get_app_path("kpws_customization"))
    api_file = app_path / "api" / "kpws_pharmacy_billing_desk.py"

    changed = _append_once(api_file, SERVER_PATCH, PATCH_MARKER)

    frappe.clear_cache()
    frappe.db.commit()

    return {
        "ok": True,
        "changed": changed,
        "message": "Return invoice summary and returnable amount calculation fixed."
    }
