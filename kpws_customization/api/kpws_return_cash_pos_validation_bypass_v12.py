from pathlib import Path
import frappe


PATCH_MARKER = "KPWS_RETURN_CASH_POS_VALIDATION_BYPASS_V12_PATCH"


SERVER_PATCH = r'''

# KPWS_RETURN_CASH_POS_VALIDATION_BYPASS_V12_PATCH

def _kpws_disable_pos_validation_for_return(doc):
    """
    ERPNext POS validation does not handle negative grand_total return invoices well
    in this KPWS POS flow. We bypass only POS paid amount validation for generated
    cash return invoices. Other Sales Invoice validations still run.
    """
    def _noop(*args, **kwargs):
        return None

    try:
        doc.validate_pos = _noop
    except Exception:
        pass

    try:
        doc.validate_pos_paid_amount = _noop
    except Exception:
        pass


def _kpws_return_cash_mop(settings):
    mode = settings.get("cash_mode_of_payment") or settings.get("default_mode_of_payment")

    if mode and frappe.db.exists("Mode of Payment", mode):
        return mode

    for name in ("Cash", "CASH"):
        if frappe.db.exists("Mode of Payment", name):
            return name

    frappe.throw(_("Cash Mode of Payment is missing. Please set Cash Mode of Payment in Pharmacy Billing Settings."))


def _kpws_return_mop_account(mode_of_payment, company):
    if not mode_of_payment:
        return None

    if not frappe.db.exists("Mode of Payment", mode_of_payment):
        return None

    try:
        mop = frappe.get_doc("Mode of Payment", mode_of_payment)
        for row in mop.get("accounts") or []:
            if row.company == company and row.default_account:
                return row.default_account
    except Exception:
        pass

    return None


def _kpws_return_payment_group(original, settings):
    """
    Decide whether direct return is allowed.
    Direct allowed only for Cash.
    Welfare/Panel/Zakat/Donation must become approval request.
    """
    modes = []
    for row in original.get("payments") or []:
        if row.mode_of_payment:
            modes.append(row.mode_of_payment.lower())

    panel_mode = (settings.get("panel_mode_of_payment") or "panel").lower()
    zakat_mode = (settings.get("zakat_mode_of_payment") or "zakat").lower()
    donation_mode = (settings.get("donation_mode_of_payment") or "donation").lower()

    if any(m == panel_mode or "panel" in m for m in modes):
        return "Panel"

    if any(m == zakat_mode or m == donation_mode or "zakat" in m or "donation" in m for m in modes):
        return "Welfare"

    group = original.get("custom_kpws_patient_billing_group")
    if group in ("Panel", "Welfare"):
        return group

    return "Cash"


def _kpws_get_requested_return_items(invoice_name, payload):
    full_return = cint(payload.get("full_return"))

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

    return requested_map, returnable_by_row


def _kpws_create_approval_request_if_needed(original, requested_map, returnable_by_row, group):
    if group not in ("Welfare", "Panel"):
        return None

    try:
        _kpws_ensure_return_request_doctype()
    except Exception:
        pass

    amount = 0
    items = []

    for source_item_name, qty in requested_map.items():
        row = returnable_by_row.get(source_item_name)
        if not row:
            continue

        line_amount = flt(qty) * flt(row.get("rate") or 0)
        amount += line_amount

        items.append({
            "source_item_name": source_item_name,
            "item_code": row.get("item_code"),
            "item_name": row.get("item_name"),
            "return_qty": flt(qty),
            "rate": flt(row.get("rate") or 0),
            "amount": flt(line_amount, 2),
        })

    req = frappe.new_doc("KPWS Pharmacy Return Request")
    req.original_invoice = original.name
    req.billing_group = group
    req.requested_by = frappe.session.user
    req.status = "Pending Approval"
    req.requested_amount = flt(amount, 2)
    req.items_json = frappe.as_json(items, indent=2)
    req.remarks = "Return requires approval because original invoice payment type is Welfare / Panel / Zakat / Donation."

    req.insert(ignore_permissions=True)
    frappe.db.commit()

    return req


@frappe.whitelist()
def create_return_invoice(payload):
    _require_role()

    payload = _json(payload)
    invoice_name = payload.get("invoice")
    submit_now = cint(payload.get("submit"))

    if not invoice_name or not frappe.db.exists("Sales Invoice", invoice_name):
        frappe.throw(_("Original Sales Invoice not found."))

    original = frappe.get_doc("Sales Invoice", invoice_name)

    if original.docstatus != 1:
        frappe.throw(_("Only submitted Sales Invoice can be returned."))

    if cint(original.get("is_return")):
        frappe.throw(_("Cannot create return against a return invoice."))

    settings = _ensure_settings_doc()
    group = _kpws_return_payment_group(original, settings)

    requested_map, returnable_by_row = _kpws_get_requested_return_items(invoice_name, payload)

    # Rule: Welfare / Panel / Zakat / Donation returns need approval.
    if group in ("Welfare", "Panel"):
        req = _kpws_create_approval_request_if_needed(
            original=original,
            requested_map=requested_map,
            returnable_by_row=returnable_by_row,
            group=group,
        )

        return {
            "ok": True,
            "approval_required": True,
            "request": req.name if req else None,
            "customer_group": group,
            "message": "{0} return requires approval. Return request {1} has been created.".format(
                group,
                req.name if req else ""
            ),
        }

    # Rule: Cash returns are direct and returned through Cash mode.
    cash_mode = _kpws_return_cash_mop(settings)
    cash_account = _kpws_return_mop_account(cash_mode, original.company)

    ret = frappe.new_doc("Sales Invoice")
    ret.is_return = 1
    ret.return_against = original.name
    ret.company = original.company
    ret.customer = original.customer
    ret.posting_date = nowdate()
    ret.update_stock = cint(original.get("update_stock"))

    # Cash return should reverse through Cash mode.
    ret.is_pos = 1

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

    _set_if_has(ret, "custom_kpws_patient_billing_group", "Cash")

    original_items_by_name = {
        row.name: row
        for row in original.get("items") or []
    }

    return_amount_abs = 0

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

        child["qty"] = -abs(flt(return_qty))
        child["rate"] = flt(source_row.rate)

        ret.append("items", child)

        return_amount_abs += abs(flt(return_qty) * flt(source_row.rate))

    if not ret.get("items"):
        frappe.throw(_("No valid return items found."))

    ret.set("payments", [])

    payment = {
        "mode_of_payment": cash_mode,
        "amount": -flt(return_amount_abs, 2),
    }

    if cash_account:
        payment["account"] = cash_account

    ret.append("payments", payment)

    # Bypass only POS paid amount validation for this generated negative return.
    _kpws_disable_pos_validation_for_return(ret)

    ret.insert(ignore_permissions=True)

    if submit_now:
        ret = frappe.get_doc("Sales Invoice", ret.name)
        _kpws_disable_pos_validation_for_return(ret)
        ret.submit()

    return {
        "ok": True,
        "approval_required": False,
        "name": ret.name,
        "docstatus": ret.docstatus,
        "return_against": original.name,
        "print_format": _kpws_get_return_print_format(settings, "Cash"),
        "customer_group": "Cash",
        "returned_amount": abs(flt(ret.grand_total)),
        "message": "Cash return invoice created successfully.",
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
        "message": "Cash return now bypasses only POS paid amount validation; Welfare/Panel returns go to approval."
    }
