from pathlib import Path
import json
import frappe


PATCH_MARKER = "KPWS_RETURN_REQUEST_MANAGEMENT_V15_PATCH"


SERVER_PATCH = r'''

# KPWS_RETURN_REQUEST_MANAGEMENT_V15_PATCH

def _kpws_can_manage_return_request():
    roles = set(frappe.get_roles())
    return bool(roles.intersection({"System Manager", "Accounts Manager", "Accounts User"}))


def _kpws_require_return_manager():
    if not _kpws_can_manage_return_request():
        frappe.throw(_("Only Accounts Manager, Accounts User or System Manager can manage return approvals."), frappe.PermissionError)


@frappe.whitelist()
def list_return_requests(status="Pending Approval", limit=50):
    _require_role()

    if not frappe.db.exists("DocType", "KPWS Pharmacy Return Request"):
        return []

    filters = {}

    if status and status != "All":
        filters["status"] = status

    rows = frappe.get_all(
        "KPWS Pharmacy Return Request",
        filters=filters,
        fields=[
            "name",
            "original_invoice",
            "billing_group",
            "status",
            "requested_amount",
            "requested_by",
            "return_invoice",
            "remarks",
            "creation",
        ],
        order_by="creation desc",
        limit_page_length=cint(limit) or 50,
    )

    return rows


@frappe.whitelist()
def get_return_request_details(request_name):
    _require_role()

    if not request_name or not frappe.db.exists("KPWS Pharmacy Return Request", request_name):
        frappe.throw(_("Return Request not found."))

    doc = frappe.get_doc("KPWS Pharmacy Return Request", request_name)

    items = []
    try:
        items = json.loads(doc.items_json or "[]")
    except Exception:
        items = []

    invoice_summary = None
    try:
        invoice_summary = _kpws_invoice_summary(doc.original_invoice)
    except Exception:
        invoice_summary = None

    return {
        "name": doc.name,
        "original_invoice": doc.original_invoice,
        "billing_group": doc.billing_group,
        "status": doc.status,
        "requested_amount": flt(doc.requested_amount),
        "requested_by": doc.requested_by,
        "return_invoice": doc.return_invoice,
        "remarks": doc.remarks,
        "creation": str(doc.creation),
        "items": items,
        "invoice": invoice_summary,
    }


def _kpws_create_approved_non_cash_return(request_doc):
    original = frappe.get_doc("Sales Invoice", request_doc.original_invoice)

    if original.docstatus != 1:
        frappe.throw(_("Original Sales Invoice must be submitted."))

    if cint(original.get("is_return")):
        frappe.throw(_("Cannot return against a return invoice."))

    try:
        items = json.loads(request_doc.items_json or "[]")
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

    settings = _ensure_settings_doc()

    ret = frappe.new_doc("Sales Invoice")
    ret.is_return = 1
    ret.return_against = original.name
    ret.company = original.company
    ret.customer = original.customer
    ret.posting_date = nowdate()
    ret.update_stock = cint(original.get("update_stock"))

    # Approved Welfare/Panel return must not be POS.
    ret.is_pos = 0

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

    # Force non-POS again after copy.
    ret.is_pos = 0
    ret.set("payments", [])

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

    ret.is_pos = 0
    ret.set("payments", [])

    # Disable POS validation if any customization tries to force POS.
    try:
        _kpws_disable_pos_validation_for_return(ret)
    except Exception:
        pass

    ret.insert(ignore_permissions=True)

    # Clean again after insert
    frappe.db.set_value("Sales Invoice", ret.name, "is_pos", 0, update_modified=False)
    try:
        frappe.db.sql("DELETE FROM `tabSales Invoice Payment` WHERE parent=%s", ret.name)
    except Exception:
        pass
    frappe.db.commit()

    ret = frappe.get_doc("Sales Invoice", ret.name)
    ret.is_pos = 0
    ret.set("payments", [])

    try:
        _kpws_disable_pos_validation_for_return(ret)
    except Exception:
        pass

    ret.submit()

    return ret


@frappe.whitelist()
def approve_return_request(request_name):
    _kpws_require_return_manager()

    if not request_name or not frappe.db.exists("KPWS Pharmacy Return Request", request_name):
        frappe.throw(_("Return Request not found."))

    req = frappe.get_doc("KPWS Pharmacy Return Request", request_name)

    if req.status == "Return Created" and req.return_invoice:
        frappe.throw(_("Return invoice already created: {0}").format(req.return_invoice))

    if req.status == "Rejected":
        frappe.throw(_("Rejected request cannot be approved."))

    ret = _kpws_create_approved_non_cash_return(req)

    req.status = "Return Created"
    req.return_invoice = ret.name
    req.save(ignore_permissions=True)

    frappe.db.commit()

    settings = _ensure_settings_doc()
    group = req.billing_group or "Welfare"

    return {
        "ok": True,
        "request": req.name,
        "return_invoice": ret.name,
        "docstatus": ret.docstatus,
        "print_format": _kpws_get_return_print_format(settings, group),
        "message": "Return request approved and return invoice created.",
    }


@frappe.whitelist()
def reject_return_request(request_name, remarks=None):
    _kpws_require_return_manager()

    if not request_name or not frappe.db.exists("KPWS Pharmacy Return Request", request_name):
        frappe.throw(_("Return Request not found."))

    req = frappe.get_doc("KPWS Pharmacy Return Request", request_name)

    if req.status == "Return Created":
        frappe.throw(_("Return invoice already created. This request cannot be rejected."))

    req.status = "Rejected"

    if remarks:
        req.remarks = (req.remarks or "") + "\\nRejected: " + remarks

    req.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "ok": True,
        "request": req.name,
        "message": "Return request rejected.",
    }
'''


JS_PATCH = r'''

/* KPWS_RETURN_REQUEST_MANAGEMENT_V15_PATCH */

(function () {
    if (typeof KPWSPharmacyBillingPOS === "undefined") {
        console.warn("KPWSPharmacyBillingPOS not found. Return request management skipped.");
        return;
    }

    const oldRender = KPWSPharmacyBillingPOS.prototype.render;

    KPWSPharmacyBillingPOS.prototype.render = function () {
        this.page.main.html(`
            <div class="kpws-pos-shell">
                <div class="kpws-pos-topbar">
                    <div>
                        <div class="kpws-pos-heading">KPWS Pharmacy POS Billing</div>
                        <div class="kpws-pos-subheading">Simple pharmacy billing, returns, approvals and print from one screen</div>
                    </div>

                    <div class="kpws-pos-tabs">
                        <button class="kpws-pos-tab active" data-tab="billing">Billing POS</button>
                        <button class="kpws-pos-tab" data-tab="return">Invoice Return</button>
                        <button class="kpws-pos-tab" data-tab="requests">Return Requests</button>
                        <button class="kpws-pos-tab" data-tab="settings">Settings</button>
                    </div>
                </div>

                <div id="kpws-billing-tab"></div>
                <div id="kpws-return-tab" style="display:none;"></div>
                <div id="kpws-requests-tab" style="display:none;"></div>
                <div id="kpws-settings-tab" style="display:none;"></div>
            </div>
        `);

        this.bindTabs();
        this.renderBilling();
        this.renderReturn();
        this.renderReturnRequests();
        this.renderSettings();
    };

    KPWSPharmacyBillingPOS.prototype.bindTabs = function () {
        this.page.main.find(".kpws-pos-tab").on("click", (e) => {
            const tab = $(e.currentTarget).data("tab");

            this.page.main.find(".kpws-pos-tab").removeClass("active");
            $(e.currentTarget).addClass("active");

            this.page.main.find("#kpws-billing-tab, #kpws-return-tab, #kpws-requests-tab, #kpws-settings-tab").hide();
            this.page.main.find(`#kpws-${tab}-tab`).show();

            if (tab === "requests") {
                this.loadReturnRequests();
            }
        });
    };

    KPWSPharmacyBillingPOS.prototype.renderReturnRequests = function () {
        const root = this.page.main.find("#kpws-requests-tab");

        root.html(`
            <div class="kpws-pos-main">
                <div class="kpws-pos-left">
                    <div class="kpws-pos-card">
                        <div class="kpws-pos-card-title">Return Approval Requests</div>

                        <div class="kpws-pos-grid-2">
                            <div class="kpws-pos-field">
                                <label>Status</label>
                                <select class="kpws-pos-input" id="kpws-request-status">
                                    <option value="Pending Approval">Pending Approval</option>
                                    <option value="Return Created">Return Created</option>
                                    <option value="Rejected">Rejected</option>
                                    <option value="All">All</option>
                                </select>
                            </div>

                            <div class="kpws-pos-field">
                                <label>&nbsp;</label>
                                <button class="kpws-pos-btn primary" id="kpws-refresh-requests" style="width:100%;">
                                    Refresh Requests
                                </button>
                            </div>
                        </div>

                        <div id="kpws-request-list" class="kpws-pos-search-results" style="margin-top:12px;"></div>
                    </div>
                </div>

                <div class="kpws-pos-right">
                    <div class="kpws-pos-card">
                        <div class="kpws-pos-card-title">Request Details</div>
                        <div id="kpws-request-detail">
                            <div class="kpws-pos-cart-empty">Select a request to review.</div>
                        </div>
                    </div>
                </div>
            </div>
        `);

        root.find("#kpws-refresh-requests").on("click", () => this.loadReturnRequests());
        root.find("#kpws-request-status").on("change", () => this.loadReturnRequests());

        this.loadReturnRequests();
    };

    KPWSPharmacyBillingPOS.prototype.loadReturnRequests = async function () {
        const status = this.page.main.find("#kpws-request-status").val() || "Pending Approval";

        this.page.main.find("#kpws-request-list").html(`
            <div class="kpws-pos-warning">Loading return requests...</div>
        `);

        try {
            const r = await this.call("list_return_requests", {
                status: status,
                limit: 50
            });

            const rows = r.message || [];

            if (!rows.length) {
                this.page.main.find("#kpws-request-list").html(`
                    <div class="kpws-pos-cart-empty">No return requests found.</div>
                `);
                return;
            }

            this.page.main.find("#kpws-request-list").html(`
                ${rows.map(row => `
                    <div class="kpws-pos-product">
                        <div>
                            <div class="kpws-pos-product-name">${this.esc(row.name)}</div>
                            <div class="kpws-pos-product-code">
                                Invoice: ${this.esc(row.original_invoice || "-")}
                            </div>
                            <div class="kpws-pos-product-code">
                                Group: ${this.esc(row.billing_group || "-")} |
                                Status: ${this.esc(row.status || "-")}
                            </div>
                        </div>

                        <div class="kpws-pos-product-meta">Amount<br>${Number(row.requested_amount || 0).toFixed(2)}</div>
                        <div class="kpws-pos-product-meta">By<br>${this.esc(row.requested_by || "-")}</div>

                        <button class="kpws-pos-btn primary" data-request="${this.esc(row.name)}">
                            Review
                        </button>
                    </div>
                `).join("")}
            `);

            this.page.main.find("[data-request]").on("click", (e) => {
                const requestName = $(e.currentTarget).data("request");
                this.loadReturnRequestDetails(requestName);
            });

        } catch (e) {
            this.page.main.find("#kpws-request-list").html(`
                <div class="kpws-pos-warning">Unable to load return requests.</div>
            `);
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

        const canAct = d.status === "Pending Approval";

        this.page.main.find("#kpws-request-detail").html(`
            <div class="kpws-pos-status ${canAct ? "orange" : "green"}">
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

            ${canAct ? `
                <div class="kpws-pos-actions">
                    <button class="kpws-pos-btn success" id="kpws-approve-request">Approve & Create Return</button>
                    <button class="kpws-pos-btn danger" id="kpws-reject-request">Reject Request</button>
                </div>
            ` : ""}
        `);

        this.page.main.find("#kpws-approve-request").on("click", () => this.approveReturnRequest(d.name));
        this.page.main.find("#kpws-reject-request").on("click", () => this.rejectReturnRequest(d.name));
    };

    KPWSPharmacyBillingPOS.prototype.approveReturnRequest = async function (requestName) {
        frappe.dom.freeze("Approving return request...");

        try {
            const r = await this.call("approve_return_request", {
                request_name: requestName
            });

            frappe.dom.unfreeze();

            const data = r.message || {};

            frappe.show_alert({
                message: data.message || "Return approved.",
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

    KPWSPharmacyBillingPOS.prototype.rejectReturnRequest = async function (requestName) {
        const remarks = prompt("Enter rejection reason:");

        if (remarks === null) return;

        frappe.dom.freeze("Rejecting return request...");

        try {
            const r = await this.call("reject_return_request", {
                request_name: requestName,
                remarks: remarks
            });

            frappe.dom.unfreeze();

            frappe.show_alert({
                message: (r.message && r.message.message) || "Return request rejected.",
                indicator: "orange"
            }, 8);

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
        "message": "Return Requests tab and approval workflow added to Pharmacy POS."
    }
