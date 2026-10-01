from pathlib import Path
import frappe


PATCH_MARKER = "KPWS_PHARMACY_RETURN_V6_PATCH"


SERVER_PATCH = r'''

# KPWS_PHARMACY_RETURN_V6_PATCH

def _kpws_si_patient_value(si):
    for fieldname in PATIENT_FIELDS_ON_SI:
        if _has_field("Sales Invoice", fieldname) and si.get(fieldname):
            return si.get(fieldname)
    return None


def _kpws_patient_search(txt):
    txt = (txt or "").strip()
    if not txt:
        return []

    meta = frappe.get_meta("Patient")
    fields = ["name"]

    optional_fields = [
        "patient_name",
        "full_name",
        "first_name",
        "middle_name",
        "last_name",
        "custom_reference_number",
        "custom_mr_number",
        "mr_number",
        "patient_mr_number",
        "mobile",
        "mobile_no",
        "phone",
        "contact_no",
        "custom_contact_no",
        "cnic",
        "custom_cnic",
    ]

    searchable = [f for f in optional_fields if meta.has_field(f)]

    conditions = ["name LIKE %(txt)s"]
    for fieldname in searchable:
        conditions.append(f"`{fieldname}` LIKE %(txt)s")

    rows = frappe.db.sql(
        f"""
        SELECT name
        FROM `tabPatient`
        WHERE {" OR ".join(conditions)}
        LIMIT 50
        """,
        {"txt": f"%{txt}%"},
        as_dict=True,
    )

    return [r.name for r in rows]


def _kpws_customer_search(txt):
    txt = (txt or "").strip()
    if not txt:
        return []

    rows = frappe.get_all(
        "Customer",
        filters=[
            ["Customer", "name", "like", f"%{txt}%"]
        ],
        fields=["name"],
        limit_page_length=30,
    )

    names = {r.name for r in rows}

    try:
        rows2 = frappe.get_all(
            "Customer",
            filters=[
                ["Customer", "customer_name", "like", f"%{txt}%"]
            ],
            fields=["name"],
            limit_page_length=30,
        )
        names.update(r.name for r in rows2)
    except Exception:
        pass

    return list(names)


def _kpws_returned_qty_map(original_invoice):
    returned_by_source_row = {}
    returned_by_item_code = {}

    returns = frappe.get_all(
        "Sales Invoice",
        filters={
            "return_against": original_invoice,
            "docstatus": 1,
            "is_return": 1,
        },
        pluck="name",
        limit_page_length=500,
    )

    item_meta = frappe.get_meta("Sales Invoice Item")

    for return_name in returns:
        try:
            ret = frappe.get_doc("Sales Invoice", return_name)
        except Exception:
            continue

        for row in ret.get("items") or []:
            qty = abs(flt(row.qty))
            source_row = None

            if item_meta.has_field("sales_invoice_item"):
                source_row = row.get("sales_invoice_item")

            if source_row:
                returned_by_source_row[source_row] = returned_by_source_row.get(source_row, 0) + qty
            else:
                returned_by_item_code[row.item_code] = returned_by_item_code.get(row.item_code, 0) + qty

    return returned_by_source_row, returned_by_item_code


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

        items.append({
            "source_item_name": row.name,
            "idx": row.idx,
            "item_code": row.item_code,
            "item_name": row.item_name,
            "uom": row.uom,
            "warehouse": row.warehouse,
            "batch_no": row.get("batch_no"),
            "serial_no": row.get("serial_no"),
            "rate": flt(row.rate),
            "original_qty": original_qty,
            "returned_qty": flt(returned_qty),
            "available_qty": available_qty,
            "amount_available": flt(available_qty * flt(row.rate), 2),
        })

    return items


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
    returnable_items = [i for i in items if flt(i.get("available_qty")) > 0]

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
        "returnable_amount": flt(sum(flt(i.amount_available) for i in returnable_items), 2),
    }


@frappe.whitelist()
def search_return_invoices(txt=""):
    _require_role()

    txt = (txt or "").strip()

    if not txt:
        return []

    names = []
    seen = set()

    def add_invoice(name):
        if name and name not in seen:
            seen.add(name)
            names.append(name)

    # 1. Invoice number / KPWS invoice number search
    rows = frappe.get_all(
        "Sales Invoice",
        filters=[
            ["Sales Invoice", "name", "like", f"%{txt}%"],
            ["Sales Invoice", "docstatus", "=", 1],
            ["Sales Invoice", "is_return", "=", 0],
        ],
        fields=["name"],
        order_by="posting_date desc, modified desc",
        limit_page_length=20,
    )

    for r in rows:
        add_invoice(r.name)

    # 2. Customer search
    customer_names = _kpws_customer_search(txt)
    if customer_names:
        rows = frappe.get_all(
            "Sales Invoice",
            filters={
                "docstatus": 1,
                "is_return": 0,
                "customer": ["in", customer_names],
            },
            fields=["name"],
            order_by="posting_date desc, modified desc",
            limit_page_length=20,
        )
        for r in rows:
            add_invoice(r.name)

    # 3. MR number / KPWS patient number / patient name search
    patients = _kpws_patient_search(txt)
    if patients:
        for patient_field in PATIENT_FIELDS_ON_SI:
            if not _has_field("Sales Invoice", patient_field):
                continue

            rows = frappe.get_all(
                "Sales Invoice",
                filters={
                    "docstatus": 1,
                    "is_return": 0,
                    patient_field: ["in", patients],
                },
                fields=["name"],
                order_by="posting_date desc, modified desc",
                limit_page_length=20,
            )

            for r in rows:
                add_invoice(r.name)

    output = []

    for name in names[:20]:
        try:
            summary = _kpws_invoice_summary(name)
            if summary.get("returnable_item_count", 0) > 0:
                output.append(summary)
        except Exception:
            continue

    return output


@frappe.whitelist()
def get_return_invoice_details(invoice_name):
    _require_role()

    if not invoice_name or not frappe.db.exists("Sales Invoice", invoice_name):
        frappe.throw(_("Sales Invoice not found."))

    si = frappe.get_doc("Sales Invoice", invoice_name)

    if si.docstatus != 1:
        frappe.throw(_("Only submitted Sales Invoice can be returned."))

    if cint(si.get("is_return")):
        frappe.throw(_("This is already a return invoice."))

    summary = _kpws_invoice_summary(invoice_name)
    summary["items"] = _kpws_returnable_items(invoice_name)

    return summary


def _kpws_copy_if_has(source, target, fieldname):
    if _has_field(source.doctype, fieldname) and _has_field(target.doctype, fieldname):
        target.set(fieldname, source.get(fieldname))


def _kpws_copy_item_fields(source_row, child):
    item_meta = frappe.get_meta("Sales Invoice Item")

    fields = [
        "item_name",
        "description",
        "uom",
        "stock_uom",
        "conversion_factor",
        "warehouse",
        "batch_no",
        "serial_no",
        "income_account",
        "expense_account",
        "cost_center",
        "item_tax_template",
        "price_list_rate",
        "discount_percentage",
        "discount_amount",
    ]

    for fieldname in fields:
        if item_meta.has_field(fieldname) and source_row.get(fieldname) not in (None, ""):
            child[fieldname] = source_row.get(fieldname)

    if item_meta.has_field("sales_invoice_item"):
        child["sales_invoice_item"] = source_row.name

    return child


def _kpws_get_return_print_format(settings, group):
    try:
        return _kpws_group_print_format(settings, group)
    except Exception:
        if group == "Panel":
            return settings.get("panel_print_format") or settings.get("print_format")
        if group == "Welfare":
            return settings.get("welfare_print_format") or settings.get("print_format")
        return settings.get("cash_print_format") or settings.get("print_format")


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
    returnable_by_row = {row["source_item_name"]: row for row in returnable_items}

    requested = _list(payload.get("items"))

    if full_return:
        requested = [
            {
                "source_item_name": row["source_item_name"],
                "return_qty": row["available_qty"],
            }
            for row in returnable_items
            if flt(row["available_qty"]) > 0
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

        available_qty = flt(returnable_by_row[source_item_name].get("available_qty"))

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
    ret.update_stock = cint(original.get("update_stock"))

    # Keep the same billing context
    for fieldname in [
        "currency",
        "conversion_rate",
        "selling_price_list",
        "price_list_currency",
        "plc_conversion_rate",
        "debit_to",
        "cost_center",
        "set_warehouse",
        "is_pos",
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

    original_items_by_name = {row.name: row for row in original.get("items") or []}

    return_amount_abs = 0

    for source_item_name, return_qty in requested_map.items():
        source_row = original_items_by_name.get(source_item_name)

        if not source_row:
            continue

        child = {
            "item_code": source_row.item_code,
            "qty": -abs(flt(return_qty)),
            "rate": flt(source_row.rate),
        }

        child = _kpws_copy_item_fields(source_row, child)

        ret.append("items", child)

        return_amount_abs += abs(flt(return_qty) * flt(source_row.rate))

    if not ret.get("items"):
        frappe.throw(_("No valid return items found."))

    # POS payment reversal if original had POS payments.
    if cint(original.get("is_pos")) and original.get("payments"):
        ret.is_pos = 1

        original_total = abs(flt(original.rounded_total or original.grand_total))
        ratio = 1

        if original_total > 0:
            ratio = min(return_amount_abs / original_total, 1)

        for pay in original.get("payments"):
            amount = abs(flt(pay.amount)) * ratio

            if amount <= 0:
                continue

            ret.append("payments", {
                "mode_of_payment": pay.mode_of_payment,
                "amount": -flt(amount, 2),
                "account": pay.get("account"),
            })

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


JS_PATCH = r'''

/* KPWS_PHARMACY_RETURN_V6_PATCH */

(function () {
    if (typeof KPWSPharmacyBillingPOS === "undefined") {
        console.warn("KPWSPharmacyBillingPOS not found. Return tab patch skipped.");
        return;
    }

    KPWSPharmacyBillingPOS.prototype.render = function () {
        this.page.main.html(`
            <div class="kpws-pos-shell">
                <div class="kpws-pos-topbar">
                    <div>
                        <div class="kpws-pos-heading">KPWS Pharmacy POS Billing</div>
                        <div class="kpws-pos-subheading">Simple pharmacy billing, returns and print from one screen</div>
                    </div>

                    <div class="kpws-pos-tabs">
                        <button class="kpws-pos-tab active" data-tab="billing">Billing POS</button>
                        <button class="kpws-pos-tab" data-tab="return">Invoice Return</button>
                        <button class="kpws-pos-tab" data-tab="settings">Settings</button>
                    </div>
                </div>

                <div id="kpws-billing-tab"></div>
                <div id="kpws-return-tab" style="display:none;"></div>
                <div id="kpws-settings-tab" style="display:none;"></div>
            </div>
        `);

        this.bindTabs();
        this.renderBilling();
        this.renderReturn();
        this.renderSettings();
    };

    KPWSPharmacyBillingPOS.prototype.bindTabs = function () {
        this.page.main.find(".kpws-pos-tab").on("click", (e) => {
            const tab = $(e.currentTarget).data("tab");

            this.page.main.find(".kpws-pos-tab").removeClass("active");
            $(e.currentTarget).addClass("active");

            this.page.main.find("#kpws-billing-tab, #kpws-return-tab, #kpws-settings-tab").hide();
            this.page.main.find(`#kpws-${tab}-tab`).show();
        });
    };

    KPWSPharmacyBillingPOS.prototype.renderReturn = function () {
        const root = this.page.main.find("#kpws-return-tab");

        root.html(`
            <div class="kpws-pos-main">
                <div class="kpws-pos-left">
                    <div class="kpws-pos-card">
                        <div class="kpws-pos-card-title">Search Invoice for Return</div>

                        <div class="kpws-pos-field">
                            <label>Search by Invoice No / MR No / KPWS No / Patient Name</label>
                            <input class="kpws-pos-input" id="kpws-return-search" placeholder="Example: SINV-KPWS, MR number, KPWS number, patient name...">
                        </div>

                        <div id="kpws-return-search-results" class="kpws-pos-search-results"></div>
                    </div>

                    <div class="kpws-pos-card">
                        <div class="kpws-pos-card-title">Returnable Items</div>
                        <div id="kpws-return-items">
                            <div class="kpws-pos-cart-empty">Search and select an invoice first.</div>
                        </div>
                    </div>
                </div>

                <div class="kpws-pos-right">
                    <div class="kpws-pos-card">
                        <div class="kpws-pos-card-title">Selected Invoice</div>
                        <div id="kpws-return-summary">
                            <div class="kpws-pos-cart-empty">No invoice selected.</div>
                        </div>
                    </div>

                    <div class="kpws-pos-card">
                        <div class="kpws-pos-card-title">Return Actions</div>

                        <div class="kpws-pos-total-panel">
                            <div class="kpws-pos-total-row">
                                <span>Return Amount</span>
                                <span id="kpws-return-total">0.00</span>
                            </div>
                        </div>

                        <div id="kpws-return-message"></div>

                        <div class="kpws-pos-actions">
                            <button class="kpws-pos-btn dark" id="kpws-full-return">Full Return</button>
                            <button class="kpws-pos-btn success" id="kpws-create-return">Create Return & Print</button>
                            <button class="kpws-pos-btn light" id="kpws-clear-return">Clear Return</button>
                        </div>
                    </div>
                </div>
            </div>
        `);

        this.selectedReturnInvoice = null;
        this.returnInvoiceDetails = null;

        this.bindReturnEvents();
    };

    KPWSPharmacyBillingPOS.prototype.bindReturnEvents = function () {
        let timer = null;

        this.page.main.find("#kpws-return-search").on("input", () => {
            clearTimeout(timer);
            timer = setTimeout(() => this.searchReturnInvoices(), 350);
        });

        this.page.main.find("#kpws-full-return").on("click", () => this.setFullReturnQty());
        this.page.main.find("#kpws-create-return").on("click", () => this.createReturnInvoice());
        this.page.main.find("#kpws-clear-return").on("click", () => this.renderReturn());
    };

    KPWSPharmacyBillingPOS.prototype.searchReturnInvoices = async function () {
        const txt = this.page.main.find("#kpws-return-search").val();

        if (!txt || txt.length < 2) {
            this.page.main.find("#kpws-return-search-results").html("");
            return;
        }

        const r = await this.call("search_return_invoices", { txt });
        const rows = r.message || [];

        if (!rows.length) {
            this.page.main.find("#kpws-return-search-results").html(`
                <div class="kpws-pos-warning">No submitted returnable invoice found.</div>
            `);
            return;
        }

        this.page.main.find("#kpws-return-search-results").html(`
            ${rows.map(row => `
                <div class="kpws-pos-product">
                    <div>
                        <div class="kpws-pos-product-name">${this.esc(row.name)}</div>
                        <div class="kpws-pos-product-code">
                            ${this.esc(row.patient_name || row.customer_name || row.customer || "")}
                            ${row.mr_number ? " | MR: " + this.esc(row.mr_number) : ""}
                        </div>
                        <div class="kpws-pos-product-code">
                            Date: ${this.esc(row.posting_date)} | Group: ${this.esc(row.billing_group || "-")}
                        </div>
                    </div>

                    <div class="kpws-pos-product-meta">Total<br>${Number(row.grand_total || 0).toFixed(2)}</div>
                    <div class="kpws-pos-product-meta">Returnable<br>${Number(row.returnable_amount || 0).toFixed(2)}</div>

                    <button class="kpws-pos-btn primary" data-return-invoice="${this.esc(row.name)}">
                        Select
                    </button>
                </div>
            `).join("")}
        `);

        this.page.main.find("[data-return-invoice]").on("click", (e) => {
            const invoice = $(e.currentTarget).data("return-invoice");
            this.loadReturnInvoice(invoice);
        });
    };

    KPWSPharmacyBillingPOS.prototype.loadReturnInvoice = async function (invoice) {
        if (!invoice) return;

        const r = await this.call("get_return_invoice_details", {
            invoice_name: invoice
        });

        this.returnInvoiceDetails = r.message || {};
        this.selectedReturnInvoice = invoice;

        this.renderReturnSummary();
        this.renderReturnItems();
        this.updateReturnTotal();
    };

    KPWSPharmacyBillingPOS.prototype.renderReturnSummary = function () {
        const d = this.returnInvoiceDetails || {};

        this.page.main.find("#kpws-return-summary").html(`
            <div class="kpws-pos-status green">
                <div class="kpws-pos-status-title">${this.esc(d.name || "")}</div>
                <div class="kpws-pos-status-msg">
                    Patient: ${this.esc(d.patient_name || d.patient || "-")}<br>
                    MR No: ${this.esc(d.mr_number || "-")}<br>
                    Customer: ${this.esc(d.customer_name || d.customer || "-")}<br>
                    Date: ${this.esc(d.posting_date || "-")}<br>
                    Total: ${Number(d.grand_total || 0).toFixed(2)}
                </div>
            </div>
        `);
    };

    KPWSPharmacyBillingPOS.prototype.renderReturnItems = function () {
        const d = this.returnInvoiceDetails || {};
        const items = d.items || [];

        const returnable = items.filter(row => Number(row.available_qty || 0) > 0);

        if (!returnable.length) {
            this.page.main.find("#kpws-return-items").html(`
                <div class="kpws-pos-warning">No items are available for return on this invoice.</div>
            `);
            return;
        }

        this.page.main.find("#kpws-return-items").html(`
            ${returnable.map((row, i) => `
                <div class="kpws-pos-cart-item">
                    <div class="kpws-pos-cart-top">
                        <div>
                            <div class="kpws-pos-cart-name">${this.esc(row.item_name || row.item_code)}</div>
                            <div class="kpws-pos-cart-code">${this.esc(row.item_code)}</div>
                        </div>

                        <div class="kpws-pos-cart-amount">${Number(row.amount_available || 0).toFixed(2)}</div>
                    </div>

                    <div class="kpws-pos-cart-controls">
                        <div>
                            <label class="kpws-pos-mini-label">Available</label>
                            <div class="kpws-pos-readonly">${Number(row.available_qty || 0)}</div>
                        </div>

                        <div>
                            <label class="kpws-pos-mini-label">Return Qty</label>
                            <input class="kpws-pos-input kpws-return-qty"
                                data-source-item="${this.esc(row.source_item_name)}"
                                data-rate="${Number(row.rate || 0)}"
                                data-available="${Number(row.available_qty || 0)}"
                                type="number"
                                min="0"
                                max="${Number(row.available_qty || 0)}"
                                step="1"
                                value="0">
                        </div>

                        <button class="kpws-pos-btn light kpws-return-row-full"
                            data-source-item="${this.esc(row.source_item_name)}"
                            data-available="${Number(row.available_qty || 0)}">
                            Full
                        </button>
                    </div>

                    <div style="margin-top:7px;color:#334155;font-size:12px;font-weight:900;">
                        Original: ${Number(row.original_qty || 0)} |
                        Already Returned: ${Number(row.returned_qty || 0)} |
                        Rate: ${Number(row.rate || 0)}
                    </div>
                </div>
            `).join("")}
        `);

        this.page.main.find(".kpws-return-qty").on("input", () => this.updateReturnTotal());

        this.page.main.find(".kpws-return-row-full").on("click", (e) => {
            const source = $(e.currentTarget).data("source-item");
            const available = Number($(e.currentTarget).data("available") || 0);

            this.page.main.find(`.kpws-return-qty[data-source-item="${source}"]`).val(available);
            this.updateReturnTotal();
        });
    };

    KPWSPharmacyBillingPOS.prototype.setFullReturnQty = function () {
        this.page.main.find(".kpws-return-qty").each(function () {
            const available = Number($(this).data("available") || 0);
            $(this).val(available);
        });

        this.updateReturnTotal();
    };

    KPWSPharmacyBillingPOS.prototype.getReturnItemsPayload = function () {
        const items = [];

        this.page.main.find(".kpws-return-qty").each(function () {
            const source = $(this).data("source-item");
            const qty = Number($(this).val() || 0);
            const available = Number($(this).data("available") || 0);

            if (qty > 0) {
                items.push({
                    source_item_name: source,
                    return_qty: Math.min(qty, available)
                });
            }
        });

        return items;
    };

    KPWSPharmacyBillingPOS.prototype.updateReturnTotal = function () {
        let total = 0;

        this.page.main.find(".kpws-return-qty").each(function () {
            const qty = Number($(this).val() || 0);
            const rate = Number($(this).data("rate") || 0);
            total += qty * rate;
        });

        this.page.main.find("#kpws-return-total").text(total.toFixed(2));
    };

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

        frappe.dom.freeze("Creating return invoice...");

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

            this.page.main.find("#kpws-return-message").html(`
                <div class="kpws-pos-success">
                    Return invoice ${this.esc(data.name)} created and submitted against ${this.esc(data.return_against)}.
                </div>
            `);

            frappe.show_alert({
                message: data.message || "Return invoice created successfully.",
                indicator: "green"
            }, 8);

            this.openPrint(data);

            // Reload selected invoice so remaining returnable qty updates
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
        "message": "Invoice Return tab added to KPWS Pharmacy POS."
    }
