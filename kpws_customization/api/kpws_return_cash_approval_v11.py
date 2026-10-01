from pathlib import Path
import frappe


PATCH_MARKER = "KPWS_RETURN_CASH_APPROVAL_V11_PATCH"


SERVER_PATCH = r'''

# KPWS_RETURN_CASH_APPROVAL_V11_PATCH

RETURN_REQUEST_DOCTYPE = "KPWS Pharmacy Return Request"


def _kpws_payment_mode_account(mode_of_payment, company):
    if not mode_of_payment or not frappe.db.exists("Mode of Payment", mode_of_payment):
        return None

    try:
        mop = frappe.get_doc("Mode of Payment", mode_of_payment)
        for row in mop.get("accounts") or []:
            if row.company == company and row.default_account:
                return row.default_account
    except Exception:
        pass

    return None


def _kpws_original_payment_roles(original, settings):
    modes = [
        (row.mode_of_payment or "").strip()
        for row in original.get("payments") or []
        if row.mode_of_payment
    ]

    low_modes = [m.lower() for m in modes]

    panel_mode = (settings.get("panel_mode_of_payment") or "Panel").lower()
    zakat_mode = (settings.get("zakat_mode_of_payment") or "Zakat").lower()
    donation_mode = (settings.get("donation_mode_of_payment") or "Donation").lower()

    if any(m == panel_mode or "panel" in m for m in low_modes):
        return "Panel"

    if any(m == zakat_mode or m == donation_mode or "zakat" in m or "donation" in m for m in low_modes):
        return "Welfare"

    group = original.get("custom_kpws_patient_billing_group")
    if group in ("Cash", "Welfare", "Panel"):
        return group

    return "Cash"


def _kpws_cash_mode(settings):
    mode = settings.get("cash_mode_of_payment") or settings.get("default_mode_of_payment")

    if mode and frappe.db.exists("Mode of Payment", mode):
        return mode

    for name in ("Cash", "CASH"):
        if frappe.db.exists("Mode of Payment", name):
            return name

    frappe.throw(_("Cash Mode of Payment is missing. Please set it in Pharmacy Billing Settings."))


def _kpws_ensure_return_request_doctype():
    if frappe.db.exists("DocType", RETURN_REQUEST_DOCTYPE):
        return

    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": RETURN_REQUEST_DOCTYPE,
        "module": "KPWS Customization",
        "custom": 1,
        "autoname": "format:KPRR-.YYYY.-.#####",
        "fields": [
            {
                "fieldname": "request_section",
                "label": "Request",
                "fieldtype": "Section Break",
            },
            {
                "fieldname": "original_invoice",
                "label": "Original Sales Invoice",
                "fieldtype": "Link",
                "options": "Sales Invoice",
                "reqd": 1,
            },
            {
                "fieldname": "billing_group",
                "label": "Billing Group",
                "fieldtype": "Data",
                "read_only": 1,
            },
            {
                "fieldname": "requested_by",
                "label": "Requested By",
                "fieldtype": "Link",
                "options": "User",
                "read_only": 1,
            },
            {
                "fieldname": "status",
                "label": "Status",
                "fieldtype": "Select",
                "options": "Pending Approval\\nApproved\\nRejected\\nReturn Created",
                "default": "Pending Approval",
            },
            {
                "fieldname": "amount_section",
                "label": "Amount",
                "fieldtype": "Section Break",
            },
            {
                "fieldname": "requested_amount",
                "label": "Requested Return Amount",
                "fieldtype": "Currency",
                "read_only": 1,
            },
            {
                "fieldname": "return_invoice",
                "label": "Return Sales Invoice",
                "fieldtype": "Link",
                "options": "Sales Invoice",
                "read_only": 1,
            },
            {
                "fieldname": "detail_section",
                "label": "Details",
                "fieldtype": "Section Break",
            },
            {
                "fieldname": "items_json",
                "label": "Requested Items JSON",
                "fieldtype": "Code",
                "options": "JSON",
                "read_only": 1,
            },
            {
                "fieldname": "remarks",
                "label": "Remarks",
                "fieldtype": "Small Text",
            },
        ],
        "permissions": [
            {
                "role": "System Manager",
                "read": 1,
                "write": 1,
                "create": 1,
                "submit": 0,
            },
            {
                "role": "Accounts Manager",
                "read": 1,
                "write": 1,
                "create": 1,
            },
            {
                "role": "Accounts User",
                "read": 1,
                "write": 1,
                "create": 1,
            },
            {
                "role": "KPWS Pharmacy User",
                "read": 1,
                "create": 1,
            },
        ],
    })

    doc.insert(ignore_permissions=True)
    frappe.db.commit()


def _kpws_create_return_request(original, requested_map, returnable_by_row, group):
    _kpws_ensure_return_request_doctype()

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

    req = frappe.new_doc(RETURN_REQUEST_DOCTYPE)
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


def _kpws_prepare_requested_return(invoice_name, payload):
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
    group = _kpws_original_payment_roles(original, settings)

    requested_map, returnable_by_row = _kpws_prepare_requested_return(invoice_name, payload)

    # Welfare / Panel must go through approval first.
    if group in ("Welfare", "Panel"):
        req = _kpws_create_return_request(
            original=original,
            requested_map=requested_map,
            returnable_by_row=returnable_by_row,
            group=group,
        )

        return {
            "ok": True,
            "approval_required": True,
            "request": req.name,
            "customer_group": group,
            "message": f"{group} return requires approval. Return request {req.name} has been created.",
        }

    # Cash return is allowed directly and must be returned through Cash mode.
    cash_mode = _kpws_cash_mode(settings)

    ret = frappe.new_doc("Sales Invoice")
    ret.is_return = 1
    ret.return_against = original.name
    ret.company = original.company
    ret.customer = original.customer
    ret.posting_date = nowdate()
    ret.update_stock = cint(original.get("update_stock"))

    # Cash return must be POS with Cash payment mode.
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

    # Make sure billing group is marked cash on direct pharmacy refund.
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

    cash_payment = {
        "mode_of_payment": cash_mode,
        "amount": -flt(return_amount_abs, 2),
    }

    cash_account = _kpws_payment_mode_account(cash_mode, original.company)
    if cash_account:
        cash_payment["account"] = cash_account

    ret.set("payments", [])
    ret.append("payments", cash_payment)

    ret.insert(ignore_permissions=True)

    if submit_now:
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


JS_PATCH = r'''

/* KPWS_RETURN_CASH_APPROVAL_V11_PATCH */

(function () {
    if (typeof KPWSPharmacyBillingPOS === "undefined") {
        console.warn("KPWSPharmacyBillingPOS not found. Cash approval return patch skipped.");
        return;
    }

    KPWSPharmacyBillingPOS.prototype.createReturnInvoice = async function () {
        if (!this.selectedReturnInvoice) {
            frappe.msgprint("Please select invoice first.");
            return;
        }

        const items = this.getReturnItemsPayload();

        if (!items.length) {
            frappe.msgprint("Please enter return quantity first.");
            return;
        }

        frappe.dom.freeze("Processing return...");

        try {
            const r = await this.call("create_return_invoice", {
                payload: JSON.stringify({
                    invoice: this.selectedReturnInvoice,
                    items: items,
                    submit: 1
                })
            });

            frappe.dom.unfreeze();

            const data = r.message || {};

            if (data.approval_required) {
                this.page.main.find("#kpws-return-message").html(`
                    <div class="kpws-pos-warning">
                        ${this.esc(data.message || "Approval required.")}
                    </div>
                `);

                frappe.show_alert({
                    message: data.message || "Return request created for approval.",
                    indicator: "orange"
                }, 10);

                return;
            }

            this.page.main.find("#kpws-return-message").html(`
                <div class="kpws-pos-success">
                    Cash return invoice ${this.esc(data.name)} created and submitted against ${this.esc(data.return_against)}.
                </div>
            `);

            frappe.show_alert({
                message: data.message || "Cash return invoice created successfully.",
                indicator: "green"
            }, 8);

            this.openPrint(data);
            this.loadReturnInvoice(this.selectedReturnInvoice);

        } catch (e) {
            frappe.dom.unfreeze();
        }
    };
})();
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
    server_changed = _append_once(api_file, SERVER_PATCH, PATCH_MARKER)

    js_files = [
        app_path / "page" / "kpws_pharmacy_billing" / "kpws_pharmacy_billing.js",
        app_path / "kpws_customization" / "page" / "kpws_pharmacy_billing" / "kpws_pharmacy_billing.js",
    ]

    js_changed = []

    for js in js_files:
        if _append_once(js, JS_PATCH, PATCH_MARKER):
            js_changed.append(str(js))

    frappe.clear_cache()
    frappe.db.commit()

    return {
        "ok": True,
        "server_changed": server_changed,
        "js_changed": js_changed,
        "message": "Cash returns now refund through Cash; Welfare/Panel returns create approval requests."
    }
