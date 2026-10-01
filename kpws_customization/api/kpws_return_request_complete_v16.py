from pathlib import Path
import frappe


PATCH_MARKER = "KPWS_RETURN_REQUEST_COMPLETE_V16_PATCH"


SERVER_PATCH = r'''

# KPWS_RETURN_REQUEST_COMPLETE_V16_PATCH

def _kpws_get_existing_return_request(original_invoice):
    if not frappe.db.exists("DocType", "KPWS Pharmacy Return Request"):
        return None

    priority = ["Approved", "Pending Approval", "Return Created"]

    for status in priority:
        rows = frappe.get_all(
            "KPWS Pharmacy Return Request",
            filters={
                "original_invoice": original_invoice,
                "status": status,
            },
            fields=["name", "status", "return_invoice", "creation"],
            order_by="creation desc",
            limit_page_length=1,
        )

        if rows:
            return frappe.get_doc("KPWS Pharmacy Return Request", rows[0].name)

    return None


def _kpws_zero_pos_fields(doc):
    doc.is_pos = 0

    for fieldname in [
        "pos_profile",
        "paid_amount",
        "base_paid_amount",
        "write_off_amount",
        "base_write_off_amount",
        "change_amount",
        "base_change_amount",
        "loyalty_amount",
        "base_loyalty_amount",
        "loyalty_points",
    ]:
        if _has_field("Sales Invoice", fieldname):
            try:
                if fieldname == "pos_profile":
                    doc.set(fieldname, None)
                else:
                    doc.set(fieldname, 0)
            except Exception:
                pass

    try:
        doc.set("payments", [])
    except Exception:
        pass


def _kpws_bypass_pos_return_validation(doc):
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


def _kpws_db_zero_pos_fields(invoice_name):
    try:
        columns = {
            row["Field"]
            for row in frappe.db.sql("SHOW COLUMNS FROM `tabSales Invoice`", as_dict=True)
        }

        updates = {}

        for fieldname in [
            "is_pos",
            "paid_amount",
            "base_paid_amount",
            "write_off_amount",
            "base_write_off_amount",
            "change_amount",
            "base_change_amount",
            "loyalty_amount",
            "base_loyalty_amount",
            "loyalty_points",
        ]:
            if fieldname in columns:
                updates[fieldname] = 0

        if "pos_profile" in columns:
            updates["pos_profile"] = None

        if updates:
            frappe.db.sql(
                "UPDATE `tabSales Invoice` SET {0} WHERE name=%s".format(
                    ", ".join("`{0}`=%s".format(k) for k in updates)
                ),
                list(updates.values()) + [invoice_name],
            )

        frappe.db.sql("DELETE FROM `tabSales Invoice Payment` WHERE parent=%s", invoice_name)

    except Exception:
        pass


def _kpws_build_return_invoice_from_request(req):
    original = frappe.get_doc("Sales Invoice", req.original_invoice)

    if original.docstatus != 1:
        frappe.throw(_("Original Sales Invoice must be submitted."))

    if cint(original.get("is_return")):
        frappe.throw(_("Cannot create return against a return invoice."))

    try:
        items = json.loads(req.items_json or "[]")
    except Exception:
        items = []

    if not items:
        frappe.throw(_("No requested items found in return request."))

    returnable_items = _kpws_returnable_items(original.name)
    returnable_by_row = {
        row["source_item_name"]: row
        for row in returnable_items
    }

    requested_map = {}

    for row in items:
        source_item_name = row.get("source_item_name")
        return_qty = flt(row.get("return_qty"))

        if not source_item_name or return_qty <= 0:
            continue

        if source_item_name not in returnable_by_row:
            frappe.throw(_("Item is no longer returnable: {0}").format(row.get("item_code")))

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
        frappe.throw(_("No valid return quantity found."))

    ret = frappe.new_doc("Sales Invoice")
    ret.is_return = 1
    ret.return_against = original.name
    ret.company = original.company
    ret.customer = original.customer
    ret.posting_date = nowdate()
    ret.update_stock = cint(original.get("update_stock"))

    _kpws_zero_pos_fields(ret)

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

    _kpws_zero_pos_fields(ret)

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

        child["qty"] = -abs(flt(return_qty))
        child["rate"] = flt(source_row.rate)

        ret.append("items", child)

    if not ret.get("items"):
        frappe.throw(_("No valid return items found."))

    _kpws_zero_pos_fields(ret)
    _kpws_bypass_pos_return_validation(ret)

    ret.insert(ignore_permissions=True)

    _kpws_db_zero_pos_fields(ret.name)
    frappe.db.commit()

    ret = frappe.get_doc("Sales Invoice", ret.name)
    _kpws_zero_pos_fields(ret)
    _kpws_bypass_pos_return_validation(ret)

    ret.submit()

    _kpws_db_zero_pos_fields(ret.name)
    frappe.db.commit()

    return ret


def _kpws_complete_approved_return_request(req):
    if req.status == "Return Created" and req.return_invoice:
        return {
            "already_created": True,
            "return_invoice": req.return_invoice,
        }

    if req.status not in ("Approved", "Pending Approval"):
        frappe.throw(_("Only Pending Approval or Approved requests can be completed."))

    ret = _kpws_build_return_invoice_from_request(req)

    req.status = "Return Created"
    req.return_invoice = ret.name
    req.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "already_created": False,
        "return_invoice": ret.name,
        "docstatus": ret.docstatus,
    }


@frappe.whitelist()
def approve_return_request(request_name):
    _kpws_require_return_manager()

    if not request_name or not frappe.db.exists("KPWS Pharmacy Return Request", request_name):
        frappe.throw(_("Return Request not found."))

    req = frappe.get_doc("KPWS Pharmacy Return Request", request_name)

    if req.status == "Rejected":
        frappe.throw(_("Rejected request cannot be approved."))

    result = _kpws_complete_approved_return_request(req)

    settings = _ensure_settings_doc()
    group = req.billing_group or "Welfare"

    return {
        "ok": True,
        "request": req.name,
        "return_invoice": result.get("return_invoice"),
        "docstatus": result.get("docstatus"),
        "already_created": result.get("already_created"),
        "print_format": _kpws_get_return_print_format(settings, group),
        "message": "Return already created." if result.get("already_created") else "Return request completed and return invoice created.",
    }


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

    # Welfare / Panel / Zakat / Donation logic:
    # 1. Do not create duplicate request.
    # 2. If request is approved, complete the return.
    # 3. If pending, tell user request already exists.
    if group in ("Welfare", "Panel"):
        existing_req = _kpws_get_existing_return_request(original.name)

        if existing_req:
            if existing_req.status == "Return Created":
                return {
                    "ok": True,
                    "approval_required": False,
                    "already_created": True,
                    "request": existing_req.name,
                    "name": existing_req.return_invoice,
                    "return_invoice": existing_req.return_invoice,
                    "customer_group": group,
                    "print_format": _kpws_get_return_print_format(settings, group),
                    "message": "Return was already created from request {0}.".format(existing_req.name),
                }

            if existing_req.status == "Approved":
                result = _kpws_complete_approved_return_request(existing_req)

                return {
                    "ok": True,
                    "approval_required": False,
                    "request": existing_req.name,
                    "name": result.get("return_invoice"),
                    "return_invoice": result.get("return_invoice"),
                    "docstatus": result.get("docstatus"),
                    "customer_group": group,
                    "print_format": _kpws_get_return_print_format(settings, group),
                    "message": "Approved request {0} completed and return invoice created.".format(existing_req.name),
                }

            if existing_req.status == "Pending Approval":
                return {
                    "ok": True,
                    "approval_required": True,
                    "request": existing_req.name,
                    "request_status": existing_req.status,
                    "customer_group": group,
                    "message": "Return request {0} already exists and is pending approval.".format(existing_req.name),
                }

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
            "request_status": "Pending Approval",
            "customer_group": group,
            "message": "{0} return requires approval. Return request {1} has been created.".format(
                group,
                req.name if req else ""
            ),
        }

    # Cash return path remains direct.
    cash_mode = _kpws_return_cash_mop(settings)
    cash_account = _kpws_return_mop_account(cash_mode, original.company)

    ret = frappe.new_doc("Sales Invoice")
    ret.is_return = 1
    ret.return_against = original.name
    ret.company = original.company
    ret.customer = original.customer
    ret.posting_date = nowdate()
    ret.update_stock = cint(original.get("update_stock"))
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

    _kpws_bypass_pos_return_validation(ret)

    ret.insert(ignore_permissions=True)

    if submit_now:
        ret = frappe.get_doc("Sales Invoice", ret.name)
        _kpws_bypass_pos_return_validation(ret)
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

/* KPWS_RETURN_REQUEST_COMPLETE_V16_PATCH */

(function () {
    if (typeof KPWSPharmacyBillingPOS === "undefined") {
        console.warn("KPWSPharmacyBillingPOS not found. Return completion patch skipped.");
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
                    message: data.message || "Return request pending approval.",
                    indicator: "orange"
                }, 10);

                return;
            }

            const invoiceName = data.return_invoice || data.name;

            this.page.main.find("#kpws-return-message").html(`
                <div class="kpws-pos-success">
                    ${this.esc(data.message || "Return completed.")}
                    ${invoiceName ? "<br>Return Invoice: " + this.esc(invoiceName) : ""}
                </div>
            `);

            frappe.show_alert({
                message: data.message || "Return completed.",
                indicator: "green"
            }, 8);

            if (invoiceName) {
                this.openPrint({
                    name: invoiceName,
                    print_format: data.print_format
                });
            }

            this.loadReturnInvoice(this.selectedReturnInvoice);

        } catch (e) {
            frappe.dom.unfreeze();
        }
    };

    KPWSPharmacyBillingPOS.prototype.loadReturnRequestDetails = async function (requestName) {
        const r = await this.call("get_return_request_details", {
            request_name: requestName
        });

        const d = r.message || {};
        const items = d.items || [];

        this.selectedApprovalRequest = d.name;

        let itemsHtml = "";

        if (items.length) {
            itemsHtml = `
                <table class="kpws-pos-payment-table">
                    <thead>
                        <tr>
                            <th>Item</th>
                            <th style="text-align:right;">Qty</th>
                            <th style="text-align:right;">Rate</th>
                            <th style="text-align:right;">Amount</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${items.map(row => `
                            <tr>
                                <td>${this.esc(row.item_name || row.item_code || "")}</td>
                                <td style="text-align:right;">${Number(row.return_qty || 0)}</td>
                                <td style="text-align:right;">${Number(row.rate || 0).toFixed(2)}</td>
                                <td style="text-align:right;">${Number(row.amount || 0).toFixed(2)}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            `;
        }

        const canCreate = d.status === "Pending Approval" || d.status === "Approved";
        const isApproved = d.status === "Approved";
        const isCreated = d.status === "Return Created" && d.return_invoice;

        this.page.main.find("#kpws-request-detail").html(`
            <div class="kpws-pos-status ${canCreate ? "orange" : "green"}">
                <div class="kpws-pos-status-title">${this.esc(d.name)}</div>
                <div class="kpws-pos-status-msg">
                    Original Invoice: ${this.esc(d.original_invoice || "-")}<br>
                    Billing Group: ${this.esc(d.billing_group || "-")}<br>
                    Status: ${this.esc(d.status || "-")}<br>
                    Requested By: ${this.esc(d.requested_by || "-")}<br>
                    Amount: ${Number(d.requested_amount || 0).toFixed(2)}<br>
                    ${d.return_invoice ? "Return Invoice: " + this.esc(d.return_invoice) + "<br>" : ""}
                    Remarks: ${this.esc(d.remarks || "-")}
                </div>
            </div>

            <div style="margin-top:12px;">
                ${itemsHtml}
            </div>

            ${canCreate ? `
                <div class="kpws-pos-actions">
                    <button class="kpws-pos-btn success" id="kpws-approve-request">
                        ${isApproved ? "Create Return Invoice" : "Approve & Create Return"}
                    </button>
                    ${!isApproved ? `<button class="kpws-pos-btn danger" id="kpws-reject-request">Reject Request</button>` : ""}
                </div>
            ` : ""}

            ${isCreated ? `
                <div class="kpws-pos-actions">
                    <button class="kpws-pos-btn primary" id="kpws-print-created-return">
                        Print Return Invoice
                    </button>
                </div>
            ` : ""}
        `);

        this.page.main.find("#kpws-approve-request").on("click", () => this.approveReturnRequest(d.name));
        this.page.main.find("#kpws-reject-request").on("click", () => this.rejectReturnRequest(d.name));

        this.page.main.find("#kpws-print-created-return").on("click", () => {
            this.openPrint({
                name: d.return_invoice
            });
        });
    };

    KPWSPharmacyBillingPOS.prototype.approveReturnRequest = async function (requestName) {
        frappe.dom.freeze("Completing return request...");

        try {
            const r = await this.call("approve_return_request", {
                request_name: requestName
            });

            frappe.dom.unfreeze();

            const data = r.message || {};

            frappe.show_alert({
                message: data.message || "Return request completed.",
                indicator: "green"
            }, 8);

            if (data.return_invoice) {
                this.openPrint({
                    name: data.return_invoice,
                    print_format: data.print_format
                });
            }

            this.loadReturnRequests();
            this.loadReturnRequestDetails(requestName);

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
        "message": "Return request completion fixed. Approved request now creates return invoice directly."
    }
