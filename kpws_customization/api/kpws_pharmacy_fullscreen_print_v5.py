from pathlib import Path
import frappe


PATCH_MARKER = "KPWS_PHARMACY_FULLSCREEN_PRINT_V5_PATCH"


SERVER_PATCH = r'''

# KPWS_PHARMACY_FULLSCREEN_PRINT_V5_PATCH

def _kpws_group_print_format(settings, group):
    group = group or "Cash"

    if group == "Panel":
        return settings.get("panel_print_format") or settings.get("print_format")

    if group == "Welfare":
        return settings.get("welfare_print_format") or settings.get("print_format")

    return settings.get("cash_print_format") or settings.get("print_format")


def _settings_dict(doc=None):
    doc = doc or _ensure_settings_doc()

    fields = [
        "company",
        "pharmacy_warehouse",
        "cash_price_list",
        "welfare_price_list",
        "panel_price_list",

        "default_mode_of_payment",
        "cash_mode_of_payment",
        "card_mode_of_payment",
        "panel_mode_of_payment",
        "zakat_mode_of_payment",
        "donation_mode_of_payment",

        "default_cash_customer",

        "print_format",
        "cash_print_format",
        "welfare_print_format",
        "panel_print_format",

        "require_cash_payment",
        "auto_submit_invoice",
        "update_stock",
        "enforce_patient_status",
        "enforce_pharmacy_stock",
        "block_missing_price",
        "apply_registration_percentage_as_discount",
        "allow_manual_rate",
    ]

    return {field: doc.get(field) for field in fields}


@frappe.whitelist()
def create_invoice(payload):
    _require_role()

    payload = _json(payload)
    settings = _ensure_settings_doc()

    patient = payload.get("patient")
    items = _list(payload.get("items"))

    if not patient:
        frappe.throw(_("Please select Patient."))

    if not items:
        frappe.throw(_("Please add at least one item."))

    ctx = get_patient_context(patient)
    status = ctx.get("status") or {}

    if cint(settings.enforce_patient_status) and status.get("blocked"):
        frappe.throw(status.get("message") or _("Patient billing status is not valid."))

    group = ctx.get("group") or "Cash"
    bill_to_customer = payload.get("bill_to_customer") or ctx.get("bill_to_customer")

    if not bill_to_customer:
        frappe.throw(_("Bill To Customer is missing. Please fix Patient/Settings first."))

    if group == "Panel":
        required_panel_customer = ctx.get("bill_to_customer")

        if not required_panel_customer:
            frappe.throw(_("Panel is not assigned on this Patient."))

        if bill_to_customer != required_panel_customer:
            frappe.throw(_("For Panel patient, Bill To Customer must be the assigned Panel Customer: {0}").format(required_panel_customer))

        panel_flag = _panel_flag_field()
        if panel_flag and not cint(frappe.db.get_value("Customer", bill_to_customer, panel_flag)):
            frappe.throw(_("Selected Bill To Customer is not marked as Is Panel."))

    warehouse = settings.pharmacy_warehouse
    if not warehouse:
        frappe.throw(_("Please set Pharmacy Warehouse in Settings tab."))

    price_list = payload.get("price_list") or ctx.get("price_list")
    if not price_list:
        frappe.throw(_("Selling Price List is missing. Please update Settings tab."))

    company = settings.company or _first_company()
    if not company:
        frappe.throw(_("Default Company is missing. Please update Settings tab."))

    si = frappe.new_doc("Sales Invoice")
    si.company = company
    si.customer = bill_to_customer
    si.posting_date = nowdate()
    si.update_stock = cint(settings.update_stock)
    si.selling_price_list = price_list

    _set_if_has(si, "set_warehouse", warehouse)

    for fieldname in PATIENT_FIELDS_ON_SI:
        if _has_field("Sales Invoice", fieldname):
            si.set(fieldname, patient)
            break

    clean_items = []

    for row in items:
        item_code = row.get("item_code")
        qty = flt(row.get("qty"))

        if not item_code:
            continue

        if qty <= 0:
            frappe.throw(_("Qty must be greater than zero for item {0}").format(item_code))

        available = _available_qty(item_code, warehouse)

        if cint(settings.enforce_pharmacy_stock) and available < qty:
            frappe.throw(
                _("Insufficient stock for {0}. Available: {1}, Required: {2}").format(
                    item_code, available, qty
                )
            )

        uom = frappe.db.get_value("Item", item_code, "stock_uom")
        rate = _get_item_price(item_code, price_list, nowdate(), uom)

        if cint(settings.allow_manual_rate) and flt(row.get("rate")) > 0:
            rate = flt(row.get("rate"))

        if cint(settings.block_missing_price) and flt(rate) <= 0:
            frappe.throw(_("Missing price for item {0}. Please ask Warehouse / Accounts to update pricing.").format(item_code))

        clean_items.append({
            "item_code": item_code,
            "qty": qty,
            "rate": rate,
            "warehouse": warehouse,
        })

    if not clean_items:
        frappe.throw(_("Please add at least one valid item."))

    for row in clean_items:
        si.append("items", row)

    registration = ctx.get("registration") or {}
    percentage = flt(registration.get("percentage"))

    card_amount = flt(payload.get("card_amount"))
    invoice_total = sum(flt(row["qty"]) * flt(row["rate"]) for row in clean_items)

    payment_plan = _kpws_compute_payment_plan(
        patient=patient,
        total=invoice_total,
        card_amount=card_amount,
    )

    payment_rows = payment_plan.get("rows") or []
    warnings = payment_plan.get("warnings") or []

    if warnings:
        frappe.throw("<br>".join(warnings), title=_("KPWS Payment Settings Missing"))

    if payment_rows:
        si.is_pos = 1

        for pay in payment_rows:
            mode = pay.get("mode_of_payment")
            amount = flt(pay.get("amount"))

            if amount <= 0:
                continue

            if not mode:
                frappe.throw(_("Mode of Payment missing for {0}. Please update Settings tab.").format(pay.get("label")))

            si.append("payments", {
                "mode_of_payment": mode,
                "amount": amount,
            })

    _set_if_has(si, "custom_kpws_patient_billing_group", group)
    _set_if_has(si, "custom_kpws_prf", registration.get("name"))
    _set_if_has(si, "custom_kpws_purpose", registration.get("purpose"))
    _set_if_has(si, "custom_kpws_approved_percentage", percentage)

    si.insert(ignore_permissions=True)

    submit_now = cint(payload.get("submit")) or cint(settings.auto_submit_invoice)

    if submit_now:
        si.submit()

    return {
        "ok": True,
        "name": si.name,
        "docstatus": si.docstatus,
        "route": f"/app/sales-invoice/{si.name}",
        "customer_group": group,
        "print_format": _kpws_group_print_format(settings, group),
        "payment_plan": payment_plan,
        "message": "Sales Invoice created successfully.",
    }
'''


JS_REPLACE = r'''
frappe.pages["kpws-pharmacy-billing"].on_page_load = function (wrapper) {
    window.kpws_pharmacy_billing = new KPWSPharmacyBillingPOS(wrapper);
};

class KPWSPharmacyBillingPOS {
    constructor(wrapper) {
        this.wrapper = $(wrapper);
        this.page = frappe.ui.make_app_page({
            parent: wrapper,
            title: "KPWS Pharmacy POS Billing",
            single_column: true
        });

        this.settings = {};
        this.patientContext = null;
        this.cart = [];
        this.paymentPlan = null;
        this.lastInvoice = null;
        this.searchTimer = null;
        this.paymentTimer = null;

        this.injectCSS();
        this.render();
        this.loadSettings();
    }

    call(method, args = {}) {
        return frappe.call({
            method: `kpws_customization.api.kpws_pharmacy_billing_desk.${method}`,
            args
        });
    }

    esc(value) {
        return frappe.utils.escape_html(String(value || ""));
    }

    injectCSS() {
        $("#kpws-pharmacy-pos-full-css").remove();

        $("head").append(`
            <style id="kpws-pharmacy-pos-full-css">
                body[data-route="kpws-pharmacy-billing"] .page-head,
                body[data-route="kpws-pharmacy-billing"] .page-title,
                body[data-route="kpws-pharmacy-billing"] .page-actions {
                    display: none !important;
                }

                body[data-route="kpws-pharmacy-billing"] .layout-main-section-wrapper,
                body[data-route="kpws-pharmacy-billing"] .layout-main-section {
                    max-width: none !important;
                    width: 100% !important;
                    padding: 0 !important;
                    margin: 0 !important;
                }

                body[data-route="kpws-pharmacy-billing"] .container,
                body[data-route="kpws-pharmacy-billing"] .page-container,
                body[data-route="kpws-pharmacy-billing"] .page-body {
                    max-width: none !important;
                    width: 100% !important;
                    padding-left: 4px !important;
                    padding-right: 4px !important;
                }

                body[data-route="kpws-pharmacy-billing"] .layout-side-section {
                    display: none !important;
                }

                body[data-route="kpws-pharmacy-billing"] .page_content,
                body[data-route="kpws-pharmacy-billing"] .page-content {
                    padding: 0 !important;
                }

                .kpws-pos-shell {
                    background: #eef2f7;
                    min-height: calc(100vh - 58px);
                    padding: 12px;
                    border-radius: 0;
                    width: 100%;
                }

                .kpws-pos-topbar {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: 12px;
                    background: #0f172a;
                    color: #ffffff;
                    padding: 12px 14px;
                    border-radius: 16px;
                    margin-bottom: 12px;
                }

                .kpws-pos-heading {
                    color: #ffffff;
                    font-size: 18px;
                    font-weight: 950;
                }

                .kpws-pos-subheading {
                    color: #cbd5e1;
                    font-size: 12px;
                    font-weight: 700;
                    margin-top: 2px;
                }

                .kpws-pos-tabs {
                    display: flex;
                    gap: 8px;
                    flex-wrap: wrap;
                }

                .kpws-pos-tab {
                    border: 1px solid rgba(255,255,255,0.22);
                    background: rgba(255,255,255,0.08);
                    color: #ffffff;
                    padding: 8px 14px;
                    border-radius: 999px;
                    font-weight: 900;
                    cursor: pointer;
                }

                .kpws-pos-tab.active {
                    background: #ffffff;
                    color: #0f172a;
                    border-color: #ffffff;
                }

                .kpws-pos-main {
                    display: grid;
                    grid-template-columns: minmax(0, 1fr) 440px;
                    gap: 14px;
                    align-items: start;
                }

                .kpws-pos-left,
                .kpws-pos-right {
                    min-width: 0;
                }

                .kpws-pos-right {
                    position: sticky;
                    top: 8px;
                    max-height: calc(100vh - 74px);
                    overflow-y: auto;
                    padding-right: 4px;
                }

                .kpws-pos-card {
                    background: #ffffff;
                    border: 1px solid #dbe4ef;
                    border-radius: 18px;
                    padding: 16px;
                    margin-bottom: 14px;
                    box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
                }

                .kpws-pos-card-title {
                    font-size: 16px;
                    font-weight: 950;
                    color: #000000;
                    margin-bottom: 12px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    gap: 10px;
                }

                .kpws-pos-grid {
                    display: grid;
                    grid-template-columns: repeat(4, minmax(150px, 1fr));
                    gap: 12px;
                }

                .kpws-pos-grid-2 {
                    display: grid;
                    grid-template-columns: repeat(2, minmax(220px, 1fr));
                    gap: 12px;
                }

                .kpws-pos-field label {
                    display: block;
                    color: #111827;
                    font-size: 12px;
                    font-weight: 950;
                    margin-bottom: 5px;
                }

                .kpws-pos-input {
                    width: 100%;
                    min-height: 40px;
                    border: 1px solid #b7c3d0;
                    border-radius: 12px;
                    padding: 8px 10px;
                    background: #ffffff;
                    color: #000000;
                    font-weight: 800;
                }

                .kpws-pos-readonly {
                    min-height: 40px;
                    border: 1px solid #dbe4ef;
                    border-radius: 12px;
                    padding: 9px 10px;
                    background: #f8fafc;
                    color: #000000;
                    font-weight: 900;
                }

                .kpws-pos-status {
                    border: 1px solid #dbe4ef;
                    border-left: 6px solid #64748b;
                    border-radius: 14px;
                    padding: 12px;
                    background: #ffffff;
                }

                .kpws-pos-status.green {
                    border-left-color: #16a34a;
                }

                .kpws-pos-status.red {
                    border-left-color: #dc2626;
                }

                .kpws-pos-status.orange {
                    border-left-color: #f97316;
                }

                .kpws-pos-status-title {
                    color: #000000;
                    font-weight: 950;
                    margin-bottom: 4px;
                }

                .kpws-pos-status-msg {
                    color: #111827;
                    font-weight: 700;
                    font-size: 13px;
                }

                .kpws-pos-search-results {
                    margin-top: 10px;
                    display: grid;
                    gap: 8px;
                }

                .kpws-pos-product {
                    display: grid;
                    grid-template-columns: minmax(0, 1fr) 90px 90px 100px;
                    gap: 10px;
                    align-items: center;
                    background: #ffffff;
                    border: 1px solid #dbe4ef;
                    border-radius: 14px;
                    padding: 12px;
                }

                .kpws-pos-product-name {
                    color: #000000;
                    font-weight: 950;
                    font-size: 14px;
                    line-height: 1.25;
                }

                .kpws-pos-product-code {
                    color: #334155;
                    font-weight: 800;
                    font-size: 12px;
                    margin-top: 4px;
                }

                .kpws-pos-product-meta {
                    color: #111827;
                    font-weight: 900;
                    text-align: center;
                }

                .kpws-pos-btn {
                    border: 0;
                    border-radius: 12px;
                    padding: 10px 13px;
                    min-height: 40px;
                    font-weight: 950;
                    cursor: pointer;
                }

                .kpws-pos-btn.primary {
                    background: #2563eb;
                    color: #ffffff;
                }

                .kpws-pos-btn.success {
                    background: #16a34a;
                    color: #ffffff;
                }

                .kpws-pos-btn.dark {
                    background: #0f172a;
                    color: #ffffff;
                }

                .kpws-pos-btn.light {
                    background: #e2e8f0;
                    color: #111827;
                }

                .kpws-pos-btn.danger {
                    background: #dc2626;
                    color: #ffffff;
                }

                .kpws-pos-btn:disabled {
                    opacity: 0.5;
                    cursor: not-allowed;
                }

                .kpws-pos-pill {
                    background: #dbeafe;
                    color: #1d4ed8;
                    border: 1px solid #bfdbfe;
                    border-radius: 999px;
                    padding: 4px 10px;
                    font-size: 12px;
                    font-weight: 950;
                }

                .kpws-pos-cart-empty {
                    background: #f8fafc;
                    border: 1px dashed #94a3b8;
                    border-radius: 14px;
                    padding: 24px 12px;
                    text-align: center;
                    color: #334155;
                    font-weight: 900;
                }

                .kpws-pos-cart-item {
                    border: 1px solid #dbe4ef;
                    border-radius: 14px;
                    background: #ffffff;
                    padding: 11px;
                    margin-bottom: 9px;
                }

                .kpws-pos-cart-top {
                    display: flex;
                    justify-content: space-between;
                    gap: 10px;
                    align-items: flex-start;
                }

                .kpws-pos-cart-name {
                    color: #000000;
                    font-size: 13px;
                    line-height: 1.25;
                    font-weight: 950;
                }

                .kpws-pos-cart-code {
                    margin-top: 3px;
                    color: #334155;
                    font-size: 12px;
                    font-weight: 800;
                }

                .kpws-pos-cart-amount {
                    color: #000000;
                    font-size: 15px;
                    font-weight: 950;
                    white-space: nowrap;
                }

                .kpws-pos-cart-controls {
                    display: grid;
                    grid-template-columns: 1fr 1fr 42px;
                    gap: 8px;
                    align-items: end;
                    margin-top: 10px;
                }

                .kpws-pos-mini-label {
                    display: block;
                    color: #111827;
                    font-size: 11px;
                    font-weight: 950;
                    margin-bottom: 4px;
                }

                .kpws-pos-total-panel {
                    background: #0f172a;
                    border-radius: 18px;
                    padding: 14px;
                    margin-bottom: 12px;
                }

                .kpws-pos-total-row {
                    display: flex;
                    justify-content: space-between;
                    gap: 12px;
                    color: #ffffff;
                    font-weight: 900;
                    padding: 6px 0;
                }

                .kpws-pos-total-row span {
                    color: #ffffff !important;
                }

                .kpws-pos-grand-total {
                    border-top: 1px solid rgba(255,255,255,0.22);
                    margin-top: 8px;
                    padding-top: 12px;
                    font-size: 21px;
                    font-weight: 950;
                }

                .kpws-pos-payment-table {
                    width: 100%;
                    border-collapse: collapse;
                    border: 1px solid #dbe4ef;
                    border-radius: 14px;
                    overflow: hidden;
                    background: #ffffff;
                }

                .kpws-pos-payment-table th,
                .kpws-pos-payment-table td {
                    padding: 10px;
                    border-bottom: 1px solid #edf2f7;
                    color: #111827;
                    font-size: 12px;
                    font-weight: 900;
                }

                .kpws-pos-payment-table th {
                    background: #f1f5f9;
                    color: #111827;
                    font-weight: 950;
                }

                .kpws-pos-actions {
                    display: grid;
                    grid-template-columns: 1fr;
                    gap: 9px;
                    margin-top: 12px;
                }

                .kpws-pos-actions .kpws-pos-btn {
                    width: 100%;
                    min-height: 46px;
                    font-size: 14px;
                }

                .kpws-pos-warning {
                    background: #fff7ed;
                    border: 1px solid #fed7aa;
                    color: #7c2d12;
                    font-weight: 900;
                    border-radius: 14px;
                    padding: 10px 12px;
                    margin-top: 10px;
                }

                .kpws-pos-success {
                    background: #dcfce7;
                    border: 1px solid #86efac;
                    color: #166534;
                    font-weight: 900;
                    border-radius: 14px;
                    padding: 10px 12px;
                    margin-top: 10px;
                }

                @media (max-width: 1200px) {
                    .kpws-pos-main {
                        grid-template-columns: minmax(0, 1fr) 390px;
                    }
                }

                @media (max-width: 980px) {
                    .kpws-pos-main {
                        grid-template-columns: 1fr;
                    }

                    .kpws-pos-right {
                        position: static;
                        max-height: none;
                        overflow: visible;
                    }

                    .kpws-pos-grid,
                    .kpws-pos-grid-2 {
                        grid-template-columns: 1fr 1fr;
                    }
                }

                @media (max-width: 650px) {
                    .kpws-pos-topbar {
                        flex-direction: column;
                        align-items: flex-start;
                    }

                    .kpws-pos-grid,
                    .kpws-pos-grid-2,
                    .kpws-pos-product {
                        grid-template-columns: 1fr;
                    }
                }
            </style>
        `);
    }

    render() {
        this.page.main.html(`
            <div class="kpws-pos-shell">
                <div class="kpws-pos-topbar">
                    <div>
                        <div class="kpws-pos-heading">KPWS Pharmacy POS Billing</div>
                        <div class="kpws-pos-subheading">Simple pharmacy billing without leaving this screen</div>
                    </div>

                    <div class="kpws-pos-tabs">
                        <button class="kpws-pos-tab active" data-tab="billing">Billing POS</button>
                        <button class="kpws-pos-tab" data-tab="settings">Settings</button>
                    </div>
                </div>

                <div id="kpws-billing-tab"></div>
                <div id="kpws-settings-tab" style="display:none;"></div>
            </div>
        `);

        this.bindTabs();
        this.renderBilling();
        this.renderSettings();
    }

    bindTabs() {
        this.page.main.find(".kpws-pos-tab").on("click", (e) => {
            const tab = $(e.currentTarget).data("tab");

            this.page.main.find(".kpws-pos-tab").removeClass("active");
            $(e.currentTarget).addClass("active");

            this.page.main.find("#kpws-billing-tab, #kpws-settings-tab").hide();
            this.page.main.find(`#kpws-${tab}-tab`).show();
        });
    }

    async loadSettings() {
        try {
            const r = await this.call("get_settings");
            this.settings = r.message || {};
            this.renderSettings();
        } catch (e) {
            this.settings = {};
        }
    }

    renderBilling() {
        const root = this.page.main.find("#kpws-billing-tab");

        root.html(`
            <div class="kpws-pos-main">
                <div class="kpws-pos-left">
                    <div class="kpws-pos-card">
                        <div class="kpws-pos-card-title">Patient</div>

                        <div class="kpws-pos-grid">
                            <div class="kpws-pos-field">
                                <div id="kpws-patient-control"></div>
                            </div>

                            <div class="kpws-pos-field">
                                <label>MR Number</label>
                                <div class="kpws-pos-readonly" id="kpws-mr">-</div>
                            </div>

                            <div class="kpws-pos-field">
                                <label>Patient Name</label>
                                <div class="kpws-pos-readonly" id="kpws-patient-name">-</div>
                            </div>

                            <div class="kpws-pos-field">
                                <label>Billing Type</label>
                                <div class="kpws-pos-readonly" id="kpws-billing-type">-</div>
                            </div>
                        </div>

                        <div id="kpws-patient-status" style="margin-top:12px;"></div>

                        <div class="kpws-pos-grid" style="margin-top:12px;">
                            <div class="kpws-pos-field">
                                <div id="kpws-billto-control"></div>
                            </div>

                            <div class="kpws-pos-field">
                                <label>Selling Price List</label>
                                <div class="kpws-pos-readonly" id="kpws-price-list">-</div>
                            </div>

                            <div class="kpws-pos-field">
                                <label>Purpose</label>
                                <div class="kpws-pos-readonly" id="kpws-purpose">-</div>
                            </div>

                            <div class="kpws-pos-field">
                                <label>Approved %</label>
                                <div class="kpws-pos-readonly" id="kpws-percentage">0%</div>
                            </div>
                        </div>
                    </div>

                    <div class="kpws-pos-card">
                        <div class="kpws-pos-card-title">Pharmacy Items</div>

                        <div class="kpws-pos-field">
                            <label>Search medicine / item</label>
                            <input class="kpws-pos-input" id="kpws-item-search" placeholder="Type item name or code...">
                        </div>

                        <div id="kpws-search-results" class="kpws-pos-search-results"></div>
                    </div>
                </div>

                <div class="kpws-pos-right">
                    <div class="kpws-pos-card">
                        <div class="kpws-pos-card-title">
                            <span>Cart</span>
                            <span class="kpws-pos-pill" id="kpws-cart-count">0 Items</span>
                        </div>

                        <div id="kpws-cart"></div>
                    </div>

                    <div class="kpws-pos-card">
                        <div class="kpws-pos-card-title">Payment</div>

                        <div class="kpws-pos-total-panel">
                            <div class="kpws-pos-total-row">
                                <span>Total Invoice</span>
                                <span id="kpws-final-total">0.00</span>
                            </div>

                            <div class="kpws-pos-total-row">
                                <span>Zakat / Donation / Panel</span>
                                <span id="kpws-covered-amount">0.00</span>
                            </div>

                            <div class="kpws-pos-total-row">
                                <span>Patient Share</span>
                                <span id="kpws-patient-share">0.00</span>
                            </div>

                            <div class="kpws-pos-total-row kpws-pos-grand-total">
                                <span>Payable Now</span>
                                <span id="kpws-payable-now">0.00</span>
                            </div>
                        </div>

                        <div class="kpws-pos-field">
                            <label>Card Amount</label>
                            <input class="kpws-pos-input" type="number" id="kpws-card-amount" value="0" min="0" step="0.01">
                        </div>

                        <div id="kpws-payment-plan" style="margin-top:12px;"></div>
                        <div id="kpws-last-invoice"></div>

                        <div class="kpws-pos-actions">
                            <button class="kpws-pos-btn success" id="kpws-submit-invoice">Submit & Print</button>
                            <button class="kpws-pos-btn primary" id="kpws-save-draft">Save Draft</button>
                            <button class="kpws-pos-btn light" id="kpws-clear">New / Clear</button>
                        </div>
                    </div>
                </div>
            </div>
        `);

        this.makeBillingControls();
        this.bindBillingEvents();
        this.updateCart();
        this.refreshPaymentPlan();
    }

    makeBillingControls() {
        const patientControl = frappe.ui.form.make_control({
            parent: this.page.main.find("#kpws-patient-control").get(0),
            df: {
                label: "Patient",
                fieldtype: "Link",
                options: "Patient",
                fieldname: "patient",
                reqd: 1,
                onchange: () => {
                    this.loadPatient(patientControl.get_value());
                }
            },
            render_input: true
        });

        this.patientControl = patientControl;

        const billToControl = frappe.ui.form.make_control({
            parent: this.page.main.find("#kpws-billto-control").get(0),
            df: {
                label: "Bill To Customer",
                fieldtype: "Link",
                options: "Customer",
                fieldname: "bill_to_customer"
            },
            render_input: true
        });

        this.billToControl = billToControl;
    }

    bindBillingEvents() {
        this.page.main.find("#kpws-item-search").on("input", () => {
            clearTimeout(this.searchTimer);
            this.searchTimer = setTimeout(() => this.searchItems(), 300);
        });

        this.page.main.find("#kpws-card-amount").on("input", () => {
            clearTimeout(this.paymentTimer);
            this.paymentTimer = setTimeout(() => this.refreshPaymentPlan(), 250);
        });

        this.page.main.find("#kpws-save-draft").on("click", () => this.createInvoice(false));
        this.page.main.find("#kpws-submit-invoice").on("click", () => this.createInvoice(true));

        this.page.main.find("#kpws-clear").on("click", () => {
            this.patientContext = null;
            this.cart = [];
            this.paymentPlan = null;
            this.lastInvoice = null;
            this.renderBilling();
        });
    }

    async loadPatient(patient) {
        if (!patient) return;

        try {
            const r = await this.call("get_patient_context", { patient });
            this.patientContext = r.message || {};
            this.cart = [];
            this.paymentPlan = null;
            this.lastInvoice = null;

            this.page.main.find("#kpws-mr").text(this.patientContext.mr_number || "-");
            this.page.main.find("#kpws-patient-name").text(this.patientContext.patient_name || "-");
            this.page.main.find("#kpws-billing-type").text(this.patientContext.group || "-");
            this.page.main.find("#kpws-price-list").text(this.patientContext.price_list || "-");

            const reg = this.patientContext.registration || {};
            this.page.main.find("#kpws-purpose").text(reg.purpose || "-");
            this.page.main.find("#kpws-percentage").text((reg.percentage || 0) + "%");

            if (this.patientContext.bill_to_customer) {
                this.billToControl.set_value(this.patientContext.bill_to_customer);
            }

            this.renderPatientStatus();
            this.updateCart();
            this.refreshPaymentPlan();
        } catch (e) {
            frappe.msgprint("Unable to fetch patient context.");
        }
    }

    renderPatientStatus() {
        const status = (this.patientContext && this.patientContext.status) || {};
        const indicator = status.indicator || (status.blocked ? "red" : "green");

        this.page.main.find("#kpws-patient-status").html(`
            <div class="kpws-pos-status ${indicator}">
                <div class="kpws-pos-status-title">${this.esc(status.title || "Patient Billing Status")}</div>
                <div class="kpws-pos-status-msg">${this.esc(status.message || "Ready for billing.")}</div>
            </div>
        `);
    }

    async searchItems() {
        const txt = this.page.main.find("#kpws-item-search").val();

        if (!this.patientContext) {
            frappe.show_alert({ message: "Select Patient first.", indicator: "orange" }, 5);
            return;
        }

        if (!txt || txt.length < 2) {
            this.page.main.find("#kpws-search-results").html("");
            return;
        }

        const r = await this.call("search_items", {
            txt,
            patient: this.patientContext.patient,
            price_list: this.patientContext.price_list
        });

        const rows = r.message || [];

        if (!rows.length) {
            this.page.main.find("#kpws-search-results").html(`
                <div class="kpws-pos-warning">No stocked item found in Pharmacy warehouse.</div>
            `);
            return;
        }

        this.page.main.find("#kpws-search-results").html(`
            ${rows.map(row => `
                <div class="kpws-pos-product">
                    <div>
                        <div class="kpws-pos-product-name">${this.esc(row.item_name || row.item_code)}</div>
                        <div class="kpws-pos-product-code">${this.esc(row.item_code)}</div>
                        ${row.missing_price ? `<div class="kpws-pos-warning">Missing price. Ask Warehouse / Accounts to update pricing.</div>` : ""}
                    </div>

                    <div class="kpws-pos-product-meta">Stock<br>${row.available_qty}</div>
                    <div class="kpws-pos-product-meta">Rate<br>${row.rate || 0}</div>

                    <button class="kpws-pos-btn primary" data-add-item="${this.esc(row.item_code)}" ${row.missing_price ? "disabled" : ""}>
                        Add
                    </button>
                </div>
            `).join("")}
        `);

        this.page.main.find("[data-add-item]").on("click", (e) => {
            const itemCode = $(e.currentTarget).data("add-item");
            const item = rows.find(x => x.item_code === itemCode);
            this.addItem(item);
        });
    }

    addItem(item) {
        if (!item || item.missing_price) return;

        const existing = this.cart.find(x => x.item_code === item.item_code);

        if (existing) {
            existing.qty += 1;
        } else {
            this.cart.push({
                item_code: item.item_code,
                item_name: item.item_name,
                qty: 1,
                rate: Number(item.rate || 0),
                available_qty: Number(item.available_qty || 0)
            });
        }

        this.updateCart();
    }

    updateCart() {
        const root = this.page.main.find("#kpws-cart");
        this.page.main.find("#kpws-cart-count").text(`${this.cart.length} Item${this.cart.length === 1 ? "" : "s"}`);

        if (!this.cart.length) {
            root.html(`<div class="kpws-pos-cart-empty">No items added yet.</div>`);
            this.refreshPaymentPlan();
            return;
        }

        root.html(`
            ${this.cart.map((row, i) => `
                <div class="kpws-pos-cart-item">
                    <div class="kpws-pos-cart-top">
                        <div>
                            <div class="kpws-pos-cart-name">${this.esc(row.item_name || row.item_code)}</div>
                            <div class="kpws-pos-cart-code">${this.esc(row.item_code)}</div>
                        </div>

                        <div class="kpws-pos-cart-amount">${(Number(row.qty || 0) * Number(row.rate || 0)).toFixed(2)}</div>
                    </div>

                    <div class="kpws-pos-cart-controls">
                        <div>
                            <label class="kpws-pos-mini-label">Qty</label>
                            <input class="kpws-pos-input kpws-cart-qty" data-index="${i}" type="number" min="1" value="${row.qty}">
                        </div>

                        <div>
                            <label class="kpws-pos-mini-label">Rate</label>
                            <div class="kpws-pos-readonly">${row.rate}</div>
                        </div>

                        <button class="kpws-pos-btn danger" data-remove="${i}">X</button>
                    </div>

                    <div style="margin-top:7px;color:#334155;font-size:12px;font-weight:900;">
                        Stock: ${row.available_qty}
                    </div>
                </div>
            `).join("")}
        `);

        root.find(".kpws-cart-qty").on("input", (e) => {
            const i = Number($(e.currentTarget).data("index"));
            const qty = Number($(e.currentTarget).val() || 0);
            this.cart[i].qty = qty;
            this.updateCart();
        });

        root.find("[data-remove]").on("click", (e) => {
            const i = Number($(e.currentTarget).data("remove"));
            this.cart.splice(i, 1);
            this.updateCart();
        });

        this.refreshPaymentPlan();
    }

    total() {
        return this.cart.reduce((sum, row) => {
            return sum + (Number(row.qty || 0) * Number(row.rate || 0));
        }, 0);
    }

    async refreshPaymentPlan() {
        const total = this.total();
        const cardAmount = Number(this.page.main.find("#kpws-card-amount").val() || 0);

        this.page.main.find("#kpws-final-total").text(total.toFixed(2));

        if (!this.patientContext || total <= 0) {
            this.page.main.find("#kpws-covered-amount").text("0.00");
            this.page.main.find("#kpws-patient-share").text("0.00");
            this.page.main.find("#kpws-payable-now").text("0.00");
            this.page.main.find("#kpws-payment-plan").html(`<div class="kpws-pos-warning">Add items to calculate payment split.</div>`);
            return;
        }

        try {
            const r = await this.call("get_payment_plan", {
                patient: this.patientContext.patient,
                total: total,
                card_amount: cardAmount
            });

            this.paymentPlan = r.message || {};
            this.renderPaymentPlan();
        } catch (e) {
            this.page.main.find("#kpws-payment-plan").html(`<div class="kpws-pos-warning">Unable to calculate payment plan.</div>`);
        }
    }

    renderPaymentPlan() {
        const plan = this.paymentPlan || {};
        const rows = plan.rows || [];
        const warnings = plan.warnings || [];

        const covered = Number(plan.covered_amount || 0);
        const share = Number(plan.patient_share || 0);

        this.page.main.find("#kpws-covered-amount").text(covered.toFixed(2));
        this.page.main.find("#kpws-patient-share").text(share.toFixed(2));
        this.page.main.find("#kpws-payable-now").text(share.toFixed(2));

        let html = "";

        if (warnings.length) {
            html += warnings.map(w => `<div class="kpws-pos-warning">${this.esc(w)}</div>`).join("");
        }

        if (!rows.length) {
            html += `<div class="kpws-pos-warning">No payment rows calculated.</div>`;
        } else {
            html += `
                <table class="kpws-pos-payment-table">
                    <thead>
                        <tr>
                            <th>Type</th>
                            <th>Mode</th>
                            <th style="text-align:right;">Amount</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows.map(row => `
                            <tr>
                                <td>${this.esc(row.label || row.role || "")}</td>
                                <td>${this.esc(row.mode_of_payment || "Missing")}</td>
                                <td style="text-align:right;">${Number(row.amount || 0).toFixed(2)}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            `;
        }

        this.page.main.find("#kpws-payment-plan").html(html);
    }

    openPrint(data) {
        if (!data || !data.name) return;

        const params = new URLSearchParams();
        params.set("doctype", "Sales Invoice");
        params.set("name", data.name);
        params.set("trigger_print", "1");
        params.set("no_letterhead", "0");

        if (data.print_format) {
            params.set("format", data.print_format);
        }

        window.open(`/printview?${params.toString()}`, "_blank");
    }

    renderLastInvoice(data) {
        if (!data || !data.name) {
            this.page.main.find("#kpws-last-invoice").html("");
            return;
        }

        this.page.main.find("#kpws-last-invoice").html(`
            <div class="kpws-pos-success">
                Invoice ${this.esc(data.name)} created${data.docstatus === 1 ? " and submitted" : ""}.
                ${data.print_format ? `<br>Print Format: ${this.esc(data.print_format)}` : ""}
            </div>
        `);
    }

    async createInvoice(submit) {
        if (!this.patientContext) {
            frappe.msgprint("Please select Patient first.");
            return;
        }

        if (!this.cart.length) {
            frappe.msgprint("Please add at least one item.");
            return;
        }

        const payload = {
            patient: this.patientContext.patient,
            bill_to_customer: this.billToControl.get_value(),
            price_list: this.patientContext.price_list,
            card_amount: Number(this.page.main.find("#kpws-card-amount").val() || 0),
            submit: submit ? 1 : 0,
            items: this.cart.map(row => ({
                item_code: row.item_code,
                qty: row.qty,
                rate: row.rate
            }))
        };

        frappe.dom.freeze(submit ? "Submitting Sales Invoice..." : "Creating Sales Invoice...");

        try {
            const r = await this.call("create_invoice", {
                payload: JSON.stringify(payload)
            });

            frappe.dom.unfreeze();

            const data = r.message || {};
            this.lastInvoice = data;

            frappe.show_alert({
                message: data.message || "Sales Invoice created successfully.",
                indicator: "green"
            }, 8);

            this.renderLastInvoice(data);

            if (submit) {
                this.openPrint(data);
            }

            // Stay on POS screen. Do NOT redirect to Sales Invoice.
            this.cart = [];
            this.paymentPlan = null;
            this.updateCart();
            this.page.main.find("#kpws-search-results").html("");
            this.page.main.find("#kpws-item-search").val("");
            this.page.main.find("#kpws-card-amount").val("0");

        } catch (e) {
            frappe.dom.unfreeze();
        }
    }

    renderSettings() {
        const root = this.page.main.find("#kpws-settings-tab");

        root.html(`
            <div class="kpws-pos-card">
                <div class="kpws-pos-card-title">Pharmacy Billing Settings</div>

                <div class="kpws-pos-grid-2">
                    <div id="kpws-setting-company"></div>
                    <div id="kpws-setting-warehouse"></div>
                    <div id="kpws-setting-cash-customer"></div>
                    <div id="kpws-setting-cash-mop"></div>
                    <div id="kpws-setting-card-mop"></div>
                    <div id="kpws-setting-panel-mop"></div>
                    <div id="kpws-setting-zakat-mop"></div>
                    <div id="kpws-setting-donation-mop"></div>
                    <div id="kpws-setting-cash-pl"></div>
                    <div id="kpws-setting-welfare-pl"></div>
                    <div id="kpws-setting-panel-pl"></div>
                </div>

                <div class="kpws-pos-card-title" style="margin-top:18px;">Print Formats by Billing Type</div>

                <div class="kpws-pos-grid">
                    <div id="kpws-setting-cash-print-format"></div>
                    <div id="kpws-setting-welfare-print-format"></div>
                    <div id="kpws-setting-panel-print-format"></div>
                </div>

                <div class="kpws-pos-card-title" style="margin-top:18px;">Controls</div>

                <div class="kpws-pos-grid">
                    ${this.checkboxHTML("require_cash_payment", "Require Cash Payment")}
                    ${this.checkboxHTML("auto_submit_invoice", "Auto Submit Invoice")}
                    ${this.checkboxHTML("update_stock", "Update Stock")}
                    ${this.checkboxHTML("enforce_patient_status", "Block Invalid Patient Status")}
                    ${this.checkboxHTML("enforce_pharmacy_stock", "Block No Stock")}
                    ${this.checkboxHTML("block_missing_price", "Block Missing Price")}
                    ${this.checkboxHTML("allow_manual_rate", "Allow Manual Rate")}
                </div>

                <div style="margin-top:16px;">
                    <button class="kpws-pos-btn success" id="kpws-save-settings">Save Settings</button>
                </div>
            </div>
        `);

        this.makeSettingsControls();
        root.find("#kpws-save-settings").on("click", () => this.saveSettings());
    }

    checkboxHTML(field, label) {
        const checked = Number(this.settings[field] || 0) ? "checked" : "";
        return `
            <label style="display:flex;align-items:center;gap:8px;font-weight:950;color:#111827;">
                <input type="checkbox" data-setting-check="${field}" ${checked}>
                ${label}
            </label>
        `;
    }

    makeSettingsControls() {
        const make = (id, label, fieldtype, options, fieldname) => {
            const target = this.page.main.find(id).get(0);
            if (!target) return;

            const control = frappe.ui.form.make_control({
                parent: target,
                df: { label, fieldtype, options, fieldname },
                render_input: true
            });

            control.set_value(this.settings[fieldname] || "");
            this[`${fieldname}Control`] = control;
        };

        make("#kpws-setting-company", "Company", "Link", "Company", "company");
        make("#kpws-setting-warehouse", "Pharmacy Warehouse", "Link", "Warehouse", "pharmacy_warehouse");
        make("#kpws-setting-cash-customer", "Default Cash Customer", "Link", "Customer", "default_cash_customer");

        make("#kpws-setting-cash-mop", "Cash Mode of Payment", "Link", "Mode of Payment", "cash_mode_of_payment");
        make("#kpws-setting-card-mop", "Card Mode of Payment", "Link", "Mode of Payment", "card_mode_of_payment");
        make("#kpws-setting-panel-mop", "Panel Mode of Payment", "Link", "Mode of Payment", "panel_mode_of_payment");
        make("#kpws-setting-zakat-mop", "Zakat Mode of Payment", "Link", "Mode of Payment", "zakat_mode_of_payment");
        make("#kpws-setting-donation-mop", "Donation Mode of Payment", "Link", "Mode of Payment", "donation_mode_of_payment");

        make("#kpws-setting-cash-pl", "Cash Price List", "Link", "Price List", "cash_price_list");
        make("#kpws-setting-welfare-pl", "Welfare Price List", "Link", "Price List", "welfare_price_list");
        make("#kpws-setting-panel-pl", "Panel Price List", "Link", "Price List", "panel_price_list");

        make("#kpws-setting-cash-print-format", "Cash Print Format", "Link", "Print Format", "cash_print_format");
        make("#kpws-setting-welfare-print-format", "Welfare Print Format", "Link", "Print Format", "welfare_print_format");
        make("#kpws-setting-panel-print-format", "Panel Print Format", "Link", "Print Format", "panel_print_format");
    }

    async saveSettings() {
        const get = (name) => this[`${name}Control`] ? this[`${name}Control`].get_value() : "";

        const values = {
            company: get("company"),
            pharmacy_warehouse: get("pharmacy_warehouse"),
            default_cash_customer: get("default_cash_customer"),

            cash_mode_of_payment: get("cash_mode_of_payment"),
            card_mode_of_payment: get("card_mode_of_payment"),
            panel_mode_of_payment: get("panel_mode_of_payment"),
            zakat_mode_of_payment: get("zakat_mode_of_payment"),
            donation_mode_of_payment: get("donation_mode_of_payment"),

            cash_price_list: get("cash_price_list"),
            welfare_price_list: get("welfare_price_list"),
            panel_price_list: get("panel_price_list"),

            cash_print_format: get("cash_print_format"),
            welfare_print_format: get("welfare_print_format"),
            panel_print_format: get("panel_print_format")
        };

        this.page.main.find("[data-setting-check]").each(function () {
            values[$(this).data("setting-check")] = $(this).is(":checked") ? 1 : 0;
        });

        const r = await this.call("save_settings", {
            values: JSON.stringify(values)
        });

        this.settings = r.message || {};
        frappe.show_alert({ message: "Settings saved.", indicator: "green" }, 8);
        this.renderSettings();
    }
}
'''


def _append_once(path, patch, marker):
    p = Path(path)
    text = p.read_text()
    if marker not in text:
        p.write_text(text + "\n\n" + patch)
        return True
    return False


def _write_js(path):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(JS_REPLACE)


def _ensure_settings_fields():
    from kpws_customization.api.kpws_pharmacy_billing_desk import SETTINGS_DOCTYPE

    if not frappe.db.exists("DocType", SETTINGS_DOCTYPE):
        from kpws_customization.api.kpws_pharmacy_billing_desk import install
        install()

    dt = frappe.get_doc("DocType", SETTINGS_DOCTYPE)
    existing = {df.fieldname for df in dt.fields}

    new_fields = [
        {
            "fieldname": "cash_print_format",
            "label": "Cash Print Format",
            "fieldtype": "Link",
            "options": "Print Format",
            "insert_after": "print_format",
        },
        {
            "fieldname": "welfare_print_format",
            "label": "Welfare Print Format",
            "fieldtype": "Link",
            "options": "Print Format",
            "insert_after": "cash_print_format",
        },
        {
            "fieldname": "panel_print_format",
            "label": "Panel Print Format",
            "fieldtype": "Link",
            "options": "Print Format",
            "insert_after": "welfare_print_format",
        },
    ]

    added = []

    for field in new_fields:
        if field["fieldname"] not in existing:
            dt.append("fields", field)
            added.append(field["fieldname"])

    if added:
        dt.save(ignore_permissions=True)
        frappe.clear_cache(doctype=SETTINGS_DOCTYPE)

    frappe.db.commit()
    return added


@frappe.whitelist()
def install():
    app_path = Path(frappe.get_app_path("kpws_customization"))

    api_file = app_path / "api" / "kpws_pharmacy_billing_desk.py"
    server_changed = _append_once(api_file, SERVER_PATCH, PATCH_MARKER)

    js_paths = [
        app_path / "page" / "kpws_pharmacy_billing" / "kpws_pharmacy_billing.js",
        app_path / "kpws_customization" / "page" / "kpws_pharmacy_billing" / "kpws_pharmacy_billing.js",
    ]

    for js_path in js_paths:
        _write_js(js_path)

    # keep standard page json present
    json_path = app_path / "kpws_customization" / "page" / "kpws_pharmacy_billing" / "kpws_pharmacy_billing.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text('''{
  "doctype": "Page",
  "name": "kpws-pharmacy-billing",
  "page_name": "kpws-pharmacy-billing",
  "title": "KPWS Pharmacy Billing",
  "module": "KPWS Customization",
  "standard": "Yes"
}
''')

    init1 = app_path / "kpws_customization" / "page" / "__init__.py"
    init2 = app_path / "kpws_customization" / "page" / "kpws_pharmacy_billing" / "__init__.py"
    init1.parent.mkdir(parents=True, exist_ok=True)
    init1.touch(exist_ok=True)
    init2.touch(exist_ok=True)

    added_fields = _ensure_settings_fields()

    # force standard page mode
    if frappe.db.exists("Page", "kpws-pharmacy-billing"):
        page = frappe.get_doc("Page", "kpws-pharmacy-billing")
        page.page_name = "kpws-pharmacy-billing"
        page.title = "KPWS Pharmacy Billing"
        page.module = "KPWS Customization"
        if page.meta.has_field("standard"):
            page.standard = "Yes"
        if page.meta.has_field("script"):
            page.script = ""
        if page.meta.has_field("content"):
            page.content = ""
        page.save(ignore_permissions=True)

    frappe.clear_cache()
    frappe.db.commit()

    return {
        "ok": True,
        "server_changed": server_changed,
        "settings_fields_added": added_fields,
        "js_replaced": [str(p) for p in js_paths],
        "message": "Full screen POS, no redirect, and group-wise print formats installed."
    }
