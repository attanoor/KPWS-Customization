from pathlib import Path
import frappe


PATCH_MARKER = "KPWS_RETURN_NO_POS_PAYMENT_FIX_V9_PATCH"


SERVER_PATCH = r'''

# KPWS_RETURN_NO_POS_PAYMENT_FIX_V9_PATCH

@frappe.whitelist()
def create_return_invoice(payload):
    _require_role()

    payload = _json(payload)
    invoice_name = payload.get("invoice")
    full_return = cint(payload.get("full_return"))
    submit_now = cint(payload.get("submit"))

    if not invoice_name or not frappe.db.exists("Sales Invoice", invoice_name):
        frappe.throw(_("Original Sales Invoice not found."))

    original = frappe.get_doc("Sales Invoice", invoice_name)

    if original.docstatus != 1:
        frappe.throw(_("Only submitted Sales Invoice can be returned."))

    if cint(original.get("is_return")):
        frappe.throw(_("Cannot create return against a return invoice."))

    returnable_items = _kpws_returnable_items(invoice_name)
    returnable_by_row = {
        row["source_item_name"]: row
        for row in returnable_items
    }

    requested = _list(payload.get("items"))

    if full_return:
        requested = [
            {
                "source_item_name": row["source_item_name"],
                "return_qty": row["available_qty"],
            }
            for row in returnable_items
            if flt(row.get("available_qty") or 0) > 0
        ]

    if not requested:
        frappe.throw(_("Please select at least one item to return."))

    requested_map = {}

    for row in requested:
        source_item_name = row.get("source_item_name")
        return_qty = flt(row.get("return_qty"))

        if not source_item_name or return_qty <= 0:
            continue

        if source_item_name not in returnable_by_row:
            frappe.throw(_("Invalid return item selected."))

        available_qty = flt(returnable_by_row[source_item_name].get("available_qty") or 0)

        if return_qty > available_qty:
            frappe.throw(
                _("Return qty for {0} cannot exceed available qty {1}.").format(
                    returnable_by_row[source_item_name].get("item_code"),
                    available_qty,
                )
            )

        requested_map[source_item_name] = return_qty

    if not requested_map:
        frappe.throw(_("Please enter return quantity for at least one item."))

    settings = _ensure_settings_doc()

    ret = frappe.new_doc("Sales Invoice")

    ret.is_return = 1
    ret.return_against = original.name
    ret.company = original.company
    ret.customer = original.customer
    ret.posting_date = nowdate()

    # Important:
    # Do not make return invoice POS.
    # POS negative payments cause ERPNext validation error:
    # "Paid amount + Write Off Amount can not be greater than Grand Total"
    ret.is_pos = 0
    ret.update_stock = cint(original.get("update_stock"))

    for fieldname in [
        "currency",
        "conversion_rate",
        "selling_price_list",
        "price_list_currency",
        "plc_conversion_rate",
        "debit_to",
        "cost_center",
        "set_warehouse",
        "taxes_and_charges",
        "tax_category",
    ]:
        _kpws_copy_if_has(original, ret, fieldname)

    for fieldname in PATIENT_FIELDS_ON_SI:
        if _has_field("Sales Invoice", fieldname) and original.get(fieldname):
            ret.set(fieldname, original.get(fieldname))

    for fieldname in [
        "custom_kpws_patient_billing_group",
        "custom_kpws_prf",
        "custom_kpws_purpose",
        "custom_kpws_approved_percentage",
    ]:
        _kpws_copy_if_has(original, ret, fieldname)

    original_items_by_name = {
        row.name: row
        for row in original.get("items") or []
    }

    for source_item_name, return_qty in requested_map.items():
        source_row = original_items_by_name.get(source_item_name)

        if not source_row:
            continue

        child = {
            "item_code": source_row.item_code,
            "qty": -abs(flt(return_qty)),
            "rate": flt(source_row.rate),
            "warehouse": source_row.get("warehouse"),
        }

        child = _kpws_copy_item_fields(source_row, child)

        # Force negative qty after copied fields
        child["qty"] = -abs(flt(return_qty))
        child["rate"] = flt(source_row.rate)

        ret.append("items", child)

    if not ret.get("items"):
        frappe.throw(_("No valid return items found."))

    # Do not append payments on return invoice.
    # This creates a clean credit note / return invoice and avoids POS payment validation.
    ret.set("payments", [])

    ret.insert(ignore_permissions=True)

    if submit_now:
        ret.submit()

    group = original.get("custom_kpws_patient_billing_group") or "Cash"

    return {
        "ok": True,
        "name": ret.name,
        "docstatus": ret.docstatus,
        "return_against": original.name,
        "print_format": _kpws_get_return_print_format(settings, group),
        "customer_group": group,
        "returned_amount": abs(flt(ret.grand_total)),
        "message": "Return invoice created successfully.",
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
        "message": "Return invoice fixed: POS payments are no longer copied to return invoice."
    }
