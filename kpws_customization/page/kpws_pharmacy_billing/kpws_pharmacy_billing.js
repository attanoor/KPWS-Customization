
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
            if (this.clearPOSForNewInvoice) {
                this.clearPOSForNewInvoice();
            } else {
                this.patientContext = null;
                this.cart = [];
                this.paymentPlan = null;
                this.lastInvoice = null;
                this.renderBilling();
            }
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




/* KPWS_PHARMACY_RETURN_SEARCH_FIX_V7_PATCH */

(function () {
    if (typeof KPWSPharmacyBillingPOS === "undefined") {
        console.warn("KPWSPharmacyBillingPOS not found. Return search fix skipped.");
        return;
    }

    KPWSPharmacyBillingPOS.prototype.renderReturn = function () {
        const root = this.page.main.find("#kpws-return-tab");

        root.html(`
            <div class="kpws-pos-main">
                <div class="kpws-pos-left">
                    <div class="kpws-pos-card">
                        <div class="kpws-pos-card-title">Search Invoice for Return</div>

                        <div class="kpws-pos-grid-2">
                            <div class="kpws-pos-field">
                                <label>Invoice No / MR No / KPWS No / Patient Name</label>
                                <input class="kpws-pos-input" id="kpws-return-search" placeholder="Type invoice number, MR number, KPWS number or patient name...">
                            </div>

                            <div class="kpws-pos-field">
                                <label>&nbsp;</label>
                                <button class="kpws-pos-btn primary" id="kpws-return-search-btn" style="width:100%;">
                                    Search Invoice
                                </button>
                            </div>
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
            timer = setTimeout(() => this.searchReturnInvoices(), 650);
        });

        this.page.main.find("#kpws-return-search").on("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                this.searchReturnInvoices();
            }
        });

        this.page.main.find("#kpws-return-search-btn").on("click", () => {
            this.searchReturnInvoices();
        });

        this.page.main.find("#kpws-full-return").on("click", () => this.setFullReturnQty());
        this.page.main.find("#kpws-create-return").on("click", () => this.createReturnInvoice());
        this.page.main.find("#kpws-clear-return").on("click", () => this.renderReturn());
    };

    KPWSPharmacyBillingPOS.prototype.searchReturnInvoices = async function () {
        const txt = this.page.main.find("#kpws-return-search").val();

        if (!txt || txt.length < 2) {
            this.page.main.find("#kpws-return-search-results").html(`
                <div class="kpws-pos-warning">Enter at least 2 characters to search.</div>
            `);
            return;
        }

        this.page.main.find("#kpws-return-search-results").html(`
            <div class="kpws-pos-warning">Searching invoices...</div>
        `);

        try {
            const r = await this.call("search_return_invoices", { txt });
            const rows = r.message || [];

            if (!rows.length) {
                this.page.main.find("#kpws-return-search-results").html(`
                    <div class="kpws-pos-warning">
                        No submitted invoice found. Try exact Sales Invoice number or MR number.
                    </div>
                `);
                return;
            }

            this.page.main.find("#kpws-return-search-results").html(`
                ${rows.map(row => {
                    const disabled = Number(row.returnable_item_count || 0) <= 0 ? "disabled" : "";
                    const warning = Number(row.returnable_item_count || 0) <= 0
                        ? `<div class="kpws-pos-warning">No returnable item found or this invoice may already be fully returned.</div>`
                        : "";

                    return `
                        <div class="kpws-pos-product">
                            <div>
                                <div class="kpws-pos-product-name">${this.esc(row.name)}</div>
                                <div class="kpws-pos-product-code">
                                    ${this.esc(row.patient_name || row.customer_name || row.customer || "")}
                                    ${row.mr_number ? " | MR: " + this.esc(row.mr_number) : ""}
                                </div>
                                <div class="kpws-pos-product-code">
                                    Date: ${this.esc(row.posting_date || "")} | Group: ${this.esc(row.billing_group || "-")}
                                </div>
                                ${row.error ? `<div class="kpws-pos-warning">${this.esc(row.error)}</div>` : ""}
                                ${warning}
                            </div>

                            <div class="kpws-pos-product-meta">Total<br>${Number(row.grand_total || 0).toFixed(2)}</div>
                            <div class="kpws-pos-product-meta">Returnable<br>${Number(row.returnable_amount || 0).toFixed(2)}</div>

                            <button class="kpws-pos-btn primary" data-return-invoice="${this.esc(row.name)}" ${disabled}>
                                Select
                            </button>
                        </div>
                    `;
                }).join("")}
            `);

            this.page.main.find("[data-return-invoice]").on("click", (e) => {
                const invoice = $(e.currentTarget).data("return-invoice");
                this.loadReturnInvoice(invoice);
            });

        } catch (e) {
            this.page.main.find("#kpws-return-search-results").html(`
                <div class="kpws-pos-warning">
                    Search failed. Check server error log or test using debug command.
                </div>
            `);
        }
    };
})();




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

        const isPending = d.status === "Pending Approval";
        const isApproved = d.status === "Approved";
        const isCreated = d.status === "Return Created" && d.return_invoice;

        this.page.main.find("#kpws-request-detail").html(`
            <div class="kpws-pos-status ${isCreated ? "green" : "orange"}">
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

            ${isPending ? `
                <div class="kpws-pos-actions">
                    <button class="kpws-pos-btn success" id="kpws-approve-request">Approve</button>
                    <button class="kpws-pos-btn danger" id="kpws-reject-request">Reject Request</button>
                </div>
            ` : ""}

            ${isApproved ? `
                <div class="kpws-pos-actions">
                    <button class="kpws-pos-btn success" id="kpws-process-request">Process Return</button>
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
        this.page.main.find("#kpws-process-request").on("click", () => this.processReturnRequest(d.name));

        this.page.main.find("#kpws-print-created-return").on("click", () => {
            this.openPrint({
                name: d.return_invoice
            });
        });
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
                message: data.message || "Return request approved.",
                indicator: "green"
            }, 8);

            this.loadReturnRequests();
            this.loadReturnRequestDetails(requestName);

        } catch (e) {
            frappe.dom.unfreeze();
        }
    };

    KPWSPharmacyBillingPOS.prototype.processReturnRequest = async function (requestName) {
        frappe.dom.freeze("Processing return...");

        try {
            const r = await this.call("process_return_request", {
                request_name: requestName
            });

            frappe.dom.unfreeze();

            const data = r.message || {};

            frappe.show_alert({
                message: data.message || "Return processed.",
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




/* KPWS_WALKIN_PHARMACY_POS_V17_PATCH */

(function () {
    if (typeof KPWSPharmacyBillingPOS === "undefined") {
        console.warn("KPWSPharmacyBillingPOS not found. Walk-in patch skipped.");
        return;
    }

    KPWSPharmacyBillingPOS.prototype.isWalkin = function () {
        return this.page.main.find("#kpws-walkin-check").is(":checked");
    };

    KPWSPharmacyBillingPOS.prototype.getWalkinName = function () {
        return (this.page.main.find("#kpws-walkin-name").val() || "").trim();
    };

    KPWSPharmacyBillingPOS.prototype.getWalkinMR = function () {
        return (this.page.main.find("#kpws-walkin-mr").val() || "").trim();
    };

    KPWSPharmacyBillingPOS.prototype.applyWalkinMode = async function () {
        if (!this.isWalkin()) {
            this.page.main.find("#kpws-walkin-fields").hide();
            this.page.main.find("#kpws-normal-patient-area").show();

            this.patientContext = null;
            this.cart = [];
            this.paymentPlan = null;

            this.page.main.find("#kpws-mr").text("-");
            this.page.main.find("#kpws-patient-name").text("-");
            this.page.main.find("#kpws-billing-type").text("-");
            this.page.main.find("#kpws-price-list").text("-");
            this.page.main.find("#kpws-purpose").text("-");
            this.page.main.find("#kpws-percentage").text("0%");
            this.page.main.find("#kpws-patient-status").html("");

            this.updateCart();
            return;
        }

        this.page.main.find("#kpws-walkin-fields").show();
        this.page.main.find("#kpws-normal-patient-area").hide();

        try {
            const r = await this.call("get_walkin_context");
            this.patientContext = r.message || {};
            this.patientContext.is_walkin = true;
            this.cart = [];
            this.paymentPlan = null;

            this.page.main.find("#kpws-mr").text("Walk-in");
            this.page.main.find("#kpws-patient-name").text("Walk-in Patient");
            this.page.main.find("#kpws-billing-type").text("Walk-in / Cash");
            this.page.main.find("#kpws-price-list").text(this.patientContext.price_list || "-");
            this.page.main.find("#kpws-purpose").text("Cash");
            this.page.main.find("#kpws-percentage").text("0%");

            if (this.patientContext.bill_to_customer) {
                this.billToControl.set_value(this.patientContext.bill_to_customer);
            }

            this.renderPatientStatus();
            this.updateCart();
            this.refreshPaymentPlan();

        } catch (e) {
            frappe.msgprint("Unable to load Walk-in context. Please check Default Cash Customer and Cash Price List in Settings.");
            this.page.main.find("#kpws-walkin-check").prop("checked", false);
            this.applyWalkinMode();
        }
    };

    const oldRenderBilling = KPWSPharmacyBillingPOS.prototype.renderBilling;

    KPWSPharmacyBillingPOS.prototype.renderBilling = function () {
        const root = this.page.main.find("#kpws-billing-tab");

        root.html(`
            <div class="kpws-pos-main">
                <div class="kpws-pos-left">
                    <div class="kpws-pos-card">
                        <div class="kpws-pos-card-title">Patient</div>

                        <div style="margin-bottom:12px;">
                            <label style="display:flex;align-items:center;gap:8px;font-weight:950;color:#111827;">
                                <input type="checkbox" id="kpws-walkin-check">
                                Walk-in Patient
                            </label>
                        </div>

                        <div id="kpws-walkin-fields" style="display:none;margin-bottom:12px;">
                            <div class="kpws-pos-grid-2">
                                <div class="kpws-pos-field">
                                    <label>Walk-in Patient Name</label>
                                    <input class="kpws-pos-input" id="kpws-walkin-name" placeholder="Enter patient name">
                                </div>
                                <div class="kpws-pos-field">
                                    <label>Walk-in MR Number</label>
                                    <input class="kpws-pos-input" id="kpws-walkin-mr" placeholder="Enter MR / KPWS number">
                                </div>
                            </div>
                        </div>

                        <div id="kpws-normal-patient-area">
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
                        </div>

                        <div id="kpws-walkin-summary" class="kpws-pos-grid" style="display:none;">
                            <div class="kpws-pos-field">
                                <label>MR Number</label>
                                <div class="kpws-pos-readonly" id="kpws-mr">Walk-in</div>
                            </div>

                            <div class="kpws-pos-field">
                                <label>Patient Name</label>
                                <div class="kpws-pos-readonly" id="kpws-patient-name">Walk-in Patient</div>
                            </div>

                            <div class="kpws-pos-field">
                                <label>Billing Type</label>
                                <div class="kpws-pos-readonly" id="kpws-billing-type">Walk-in / Cash</div>
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

        this.page.main.find("#kpws-walkin-check").on("change", () => {
            if (this.isWalkin()) {
                this.page.main.find("#kpws-walkin-summary").show();
            } else {
                this.page.main.find("#kpws-walkin-summary").hide();
            }
            this.applyWalkinMode();
        });

        this.page.main.find("#kpws-walkin-name").on("input", () => {
            if (this.isWalkin()) {
                this.page.main.find("#kpws-patient-name").text(this.getWalkinName() || "Walk-in Patient");
            }
        });

        this.page.main.find("#kpws-walkin-mr").on("input", () => {
            if (this.isWalkin()) {
                this.page.main.find("#kpws-mr").text(this.getWalkinMR() || "Walk-in");
            }
        });

        this.updateCart();
        this.refreshPaymentPlan();
    };

    KPWSPharmacyBillingPOS.prototype.searchItems = async function () {
        const txt = this.page.main.find("#kpws-item-search").val();

        if (!this.patientContext) {
            frappe.show_alert({ message: "Select Patient or enable Walk-in Patient first.", indicator: "orange" }, 5);
            return;
        }

        if (this.isWalkin()) {
            if (!this.getWalkinName() || !this.getWalkinMR()) {
                frappe.show_alert({ message: "Enter Walk-in Patient Name and MR Number first.", indicator: "orange" }, 5);
                return;
            }
        }

        if (!txt || txt.length < 2) {
            this.page.main.find("#kpws-search-results").html("");
            return;
        }

        const r = await this.call("search_items", {
            txt,
            patient: this.isWalkin() ? "" : this.patientContext.patient,
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
    };

    KPWSPharmacyBillingPOS.prototype.refreshPaymentPlan = async function () {
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
            const method = this.isWalkin() ? "get_walkin_payment_plan" : "get_payment_plan";
            const args = this.isWalkin()
                ? { total: total, card_amount: cardAmount }
                : { patient: this.patientContext.patient, total: total, card_amount: cardAmount };

            const r = await this.call(method, args);

            this.paymentPlan = r.message || {};
            this.renderPaymentPlan();
        } catch (e) {
            this.page.main.find("#kpws-payment-plan").html(`<div class="kpws-pos-warning">Unable to calculate payment plan.</div>`);
        }
    };

    KPWSPharmacyBillingPOS.prototype.createInvoice = async function (submit) {
        if (!this.patientContext) {
            frappe.msgprint("Please select Patient or enable Walk-in Patient first.");
            return;
        }

        if (this.isWalkin()) {
            if (!this.getWalkinName()) {
                frappe.msgprint("Please enter Walk-in Patient Name.");
                return;
            }

            if (!this.getWalkinMR()) {
                frappe.msgprint("Please enter Walk-in MR Number.");
                return;
            }
        }

        if (!this.cart.length) {
            frappe.msgprint("Please add at least one item.");
            return;
        }

        const payload = {
            is_walkin: this.isWalkin() ? 1 : 0,
            walkin_name: this.getWalkinName(),
            walkin_mr_number: this.getWalkinMR(),
            patient: this.isWalkin() ? "" : this.patientContext.patient,
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

            this.cart = [];
            this.paymentPlan = null;
            this.updateCart();
            this.page.main.find("#kpws-search-results").html("");
            this.page.main.find("#kpws-item-search").val("");
            this.page.main.find("#kpws-card-amount").val("0");

            if (this.isWalkin()) {
                this.page.main.find("#kpws-walkin-name").val("");
                this.page.main.find("#kpws-walkin-mr").val("");
                this.page.main.find("#kpws-mr").text("Walk-in");
                this.page.main.find("#kpws-patient-name").text("Walk-in Patient");
            }

        } catch (e) {
            frappe.dom.unfreeze();
        }
    };
})();




/* KPWS_PARKED_INVOICE_V19_PATCH */

(function () {
    if (typeof KPWSPharmacyBillingPOS === "undefined") {
        console.warn("KPWSPharmacyBillingPOS not found. Parked invoice patch skipped.");
        return;
    }

    KPWSPharmacyBillingPOS.prototype.buildInvoicePayload = function (submit) {
        return {
            is_walkin: this.isWalkin && this.isWalkin() ? 1 : 0,
            walkin_name: this.getWalkinName ? this.getWalkinName() : "",
            walkin_mr_number: this.getWalkinMR ? this.getWalkinMR() : "",
            patient: this.isWalkin && this.isWalkin() ? "" : (this.patientContext ? this.patientContext.patient : ""),
            bill_to_customer: this.billToControl ? this.billToControl.get_value() : "",
            price_list: this.patientContext ? this.patientContext.price_list : "",
            card_amount: Number(this.page.main.find("#kpws-card-amount").val() || 0),
            submit: submit ? 1 : 0,
            items: (this.cart || []).map(row => ({
                item_code: row.item_code,
                item_name: row.item_name,
                qty: row.qty,
                rate: row.rate,
                available_qty: row.available_qty
            }))
        };
    };

    KPWSPharmacyBillingPOS.prototype.render = function () {
        this.page.main.html(`
            <div class="kpws-pos-shell">
                <div class="kpws-pos-topbar">
                    <div>
                        <div class="kpws-pos-heading">KPWS Pharmacy POS Billing</div>
                        <div class="kpws-pos-subheading">Billing, parked invoices, returns, approvals and print from one screen</div>
                    </div>

                    <div class="kpws-pos-tabs">
                        <button class="kpws-pos-tab active" data-tab="billing">Billing POS</button>
                        <button class="kpws-pos-tab" data-tab="parked">Parked Invoices</button>
                        <button class="kpws-pos-tab" data-tab="return">Invoice Return</button>
                        <button class="kpws-pos-tab" data-tab="requests">Return Requests</button>
                        <button class="kpws-pos-tab" data-tab="settings">Settings</button>
                    </div>
                </div>

                <div id="kpws-billing-tab"></div>
                <div id="kpws-parked-tab" style="display:none;"></div>
                <div id="kpws-return-tab" style="display:none;"></div>
                <div id="kpws-requests-tab" style="display:none;"></div>
                <div id="kpws-settings-tab" style="display:none;"></div>
            </div>
        `);

        this.bindTabs();
        this.renderBilling();

        if (this.renderParkedInvoices) this.renderParkedInvoices();
        if (this.renderReturn) this.renderReturn();
        if (this.renderReturnRequests) this.renderReturnRequests();

        this.renderSettings();
    };

    KPWSPharmacyBillingPOS.prototype.bindTabs = function () {
        this.page.main.find(".kpws-pos-tab").on("click", (e) => {
            const tab = $(e.currentTarget).data("tab");

            this.page.main.find(".kpws-pos-tab").removeClass("active");
            $(e.currentTarget).addClass("active");

            this.page.main.find("#kpws-billing-tab, #kpws-parked-tab, #kpws-return-tab, #kpws-requests-tab, #kpws-settings-tab").hide();
            this.page.main.find(`#kpws-${tab}-tab`).show();

            if (tab === "parked") {
                this.loadParkedInvoices();
            }

            if (tab === "requests" && this.loadReturnRequests) {
                this.loadReturnRequests();
            }
        });
    };

    const oldRenderBillingForPark = KPWSPharmacyBillingPOS.prototype.renderBilling;

    KPWSPharmacyBillingPOS.prototype.renderBilling = function () {
        oldRenderBillingForPark.apply(this, arguments);

        const actions = this.page.main.find(".kpws-pos-actions").first();

        if (actions.length && !this.page.main.find("#kpws-park-invoice").length) {
            actions.prepend(`
                <button class="kpws-pos-btn dark" id="kpws-park-invoice">
                    Park Invoice
                </button>
            `);
        }

        if (!this.page.main.find("#kpws-current-parked").length) {
            this.page.main.find("#kpws-last-invoice").before(`
                <div id="kpws-current-parked"></div>
            `);
        }

        this.renderCurrentParkedBadge();

        this.page.main.find("#kpws-park-invoice").off("click").on("click", () => {
            this.parkCurrentInvoice();
        });
    };

    KPWSPharmacyBillingPOS.prototype.renderCurrentParkedBadge = function () {
        const target = this.page.main.find("#kpws-current-parked");

        if (!target.length) return;

        if (!this.currentParkedInvoice) {
            target.html("");
            return;
        }

        target.html(`
            <div class="kpws-pos-warning">
                Resumed Parked Invoice: ${this.esc(this.currentParkedInvoice)}
            </div>
        `);
    };

    KPWSPharmacyBillingPOS.prototype.clearPOSForNewInvoice = function () {
        this.currentParkedInvoice = null;
        this.patientContext = null;
        this.cart = [];
        this.paymentPlan = null;
        this.lastInvoice = null;

        this.renderBilling();
    };

    KPWSPharmacyBillingPOS.prototype.parkCurrentInvoice = async function () {
        if (!this.patientContext) {
            frappe.msgprint("Please select Patient or enable Walk-in Patient before parking.");
            return;
        }

        if (this.isWalkin && this.isWalkin()) {
            if (!this.getWalkinName()) {
                frappe.msgprint("Please enter Walk-in Patient Name before parking.");
                return;
            }

            if (!this.getWalkinMR()) {
                frappe.msgprint("Please enter Walk-in MR Number before parking.");
                return;
            }
        }

        if (!this.cart || !this.cart.length) {
            frappe.msgprint("Please add at least one item before parking.");
            return;
        }

        const payload = this.buildInvoicePayload(false);

        frappe.dom.freeze("Parking invoice...");

        try {
            const r = await this.call("park_invoice", {
                payload: JSON.stringify(payload)
            });

            frappe.dom.unfreeze();

            const data = r.message || {};

            frappe.show_alert({
                message: data.message || "Invoice parked successfully.",
                indicator: "green"
            }, 8);

            this.clearPOSForNewInvoice();

            this.page.main.find(`[data-tab="parked"]`).click();

        } catch (e) {
            frappe.dom.unfreeze();
        }
    };

    KPWSPharmacyBillingPOS.prototype.renderParkedInvoices = function () {
        const root = this.page.main.find("#kpws-parked-tab");

        root.html(`
            <div class="kpws-pos-main">
                <div class="kpws-pos-left">
                    <div class="kpws-pos-card">
                        <div class="kpws-pos-card-title">Parked Invoices</div>

                        <div class="kpws-pos-grid-2">
                            <div class="kpws-pos-field">
                                <label>Search</label>
                                <input class="kpws-pos-input" id="kpws-parked-search" placeholder="Search by patient, MR, walk-in name, parked no...">
                            </div>

                            <div class="kpws-pos-field">
                                <label>Status</label>
                                <select class="kpws-pos-input" id="kpws-parked-status">
                                    <option value="Parked">Parked</option>
                                    <option value="Completed">Completed</option>
                                    <option value="Cancelled">Cancelled</option>
                                    <option value="All">All</option>
                                </select>
                            </div>
                        </div>

                        <div style="margin-top:12px; display:flex; gap:8px; flex-wrap:wrap;">
                            <button class="kpws-pos-btn primary" id="kpws-refresh-parked">Refresh</button>
                        </div>

                        <div id="kpws-parked-list" class="kpws-pos-search-results" style="margin-top:12px;"></div>
                    </div>
                </div>

                <div class="kpws-pos-right">
                    <div class="kpws-pos-card">
                        <div class="kpws-pos-card-title">How Parking Works</div>

                        <div class="kpws-pos-status green">
                            <div class="kpws-pos-status-title">Park & Resume</div>
                            <div class="kpws-pos-status-msg">
                                Park current invoice when patient wants to wait or another patient needs urgent billing.
                                Later click Resume to bring the same cart back and complete Submit & Print.
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `);

        let timer = null;

        root.find("#kpws-refresh-parked").on("click", () => this.loadParkedInvoices());

        root.find("#kpws-parked-status").on("change", () => this.loadParkedInvoices());

        root.find("#kpws-parked-search").on("input", () => {
            clearTimeout(timer);
            timer = setTimeout(() => this.loadParkedInvoices(), 400);
        });

        this.loadParkedInvoices();
    };

    KPWSPharmacyBillingPOS.prototype.loadParkedInvoices = async function () {
        const status = this.page.main.find("#kpws-parked-status").val() || "Parked";
        const txt = this.page.main.find("#kpws-parked-search").val() || "";

        this.page.main.find("#kpws-parked-list").html(`
            <div class="kpws-pos-warning">Loading parked invoices...</div>
        `);

        try {
            const r = await this.call("list_parked_invoices", {
                status: status,
                txt: txt,
                limit: 50
            });

            const rows = r.message || [];

            if (!rows.length) {
                this.page.main.find("#kpws-parked-list").html(`
                    <div class="kpws-pos-cart-empty">No parked invoices found.</div>
                `);
                return;
            }

            this.page.main.find("#kpws-parked-list").html(`
                ${rows.map(row => {
                    const title = row.is_walkin
                        ? (row.walkin_name || "Walk-in Patient")
                        : (row.patient_name || row.patient || "-");

                    const mr = row.is_walkin
                        ? row.walkin_mr_number
                        : row.mr_number;

                    const canResume = row.status === "Parked";

                    return `
                        <div class="kpws-pos-product">
                            <div>
                                <div class="kpws-pos-product-name">${this.esc(row.name)}</div>
                                <div class="kpws-pos-product-code">
                                    ${this.esc(title)}
                                    ${mr ? " | MR: " + this.esc(mr) : ""}
                                </div>
                                <div class="kpws-pos-product-code">
                                    Group: ${this.esc(row.billing_group || "-")} |
                                    Status: ${this.esc(row.status || "-")} |
                                    Items: ${Number(row.items_count || 0)}
                                </div>
                                ${row.completed_invoice ? `
                                    <div class="kpws-pos-product-code">
                                        Completed Invoice: ${this.esc(row.completed_invoice)}
                                    </div>
                                ` : ""}
                            </div>

                            <div class="kpws-pos-product-meta">Total<br>${Number(row.total_amount || 0).toFixed(2)}</div>
                            <div class="kpws-pos-product-meta">By<br>${this.esc(row.owner || "-")}</div>

                            <div style="display:grid; gap:6px;">
                                ${canResume ? `
                                    <button class="kpws-pos-btn primary" data-resume-parked="${this.esc(row.name)}">
                                        Resume
                                    </button>
                                    <button class="kpws-pos-btn danger" data-cancel-parked="${this.esc(row.name)}">
                                        Cancel
                                    </button>
                                ` : ""}
                                ${row.completed_invoice ? `
                                    <button class="kpws-pos-btn light" data-open-completed="${this.esc(row.completed_invoice)}">
                                        Print
                                    </button>
                                ` : ""}
                            </div>
                        </div>
                    `;
                }).join("")}
            `);

            this.page.main.find("[data-resume-parked]").on("click", (e) => {
                const name = $(e.currentTarget).data("resume-parked");
                this.resumeParkedInvoice(name);
            });

            this.page.main.find("[data-cancel-parked]").on("click", (e) => {
                const name = $(e.currentTarget).data("cancel-parked");
                this.cancelParkedInvoice(name);
            });

            this.page.main.find("[data-open-completed]").on("click", (e) => {
                const invoice = $(e.currentTarget).data("open-completed");
                this.openPrint({ name: invoice });
            });

        } catch (e) {
            this.page.main.find("#kpws-parked-list").html(`
                <div class="kpws-pos-warning">Unable to load parked invoices.</div>
            `);
        }
    };

    KPWSPharmacyBillingPOS.prototype.resumeParkedInvoice = async function (name) {
        frappe.dom.freeze("Loading parked invoice...");

        try {
            const r = await this.call("get_parked_invoice", { name });
            const data = r.message || {};
            const payload = data.payload || {};

            frappe.dom.unfreeze();

            this.page.main.find(`[data-tab="billing"]`).click();

            this.currentParkedInvoice = data.name;
            this.cart = [];
            this.paymentPlan = null;

            if (payload.is_walkin) {
                this.page.main.find("#kpws-walkin-check").prop("checked", true);
                await this.applyWalkinMode();

                this.page.main.find("#kpws-walkin-name").val(payload.walkin_name || "");
                this.page.main.find("#kpws-walkin-mr").val(payload.walkin_mr_number || "");
                this.page.main.find("#kpws-patient-name").text(payload.walkin_name || "Walk-in Patient");
                this.page.main.find("#kpws-mr").text(payload.walkin_mr_number || "Walk-in");

            } else {
                this.page.main.find("#kpws-walkin-check").prop("checked", false);
                await this.applyWalkinMode();

                if (payload.patient) {
                    this.patientControl.set_value(payload.patient);
                    await this.loadPatient(payload.patient);
                }
            }

            if (payload.bill_to_customer && this.billToControl) {
                this.billToControl.set_value(payload.bill_to_customer);
            }

            this.cart = (payload.items || []).map(row => ({
                item_code: row.item_code,
                item_name: row.item_name || row.item_code,
                qty: Number(row.qty || 0),
                rate: Number(row.rate || 0),
                available_qty: Number(row.available_qty || 0)
            })).filter(row => row.item_code && row.qty > 0);

            this.page.main.find("#kpws-card-amount").val(Number(payload.card_amount || 0));

            this.updateCart();
            this.refreshPaymentPlan();
            this.renderCurrentParkedBadge();

            frappe.show_alert({
                message: "Parked invoice resumed: " + data.name,
                indicator: "green"
            }, 8);

        } catch (e) {
            frappe.dom.unfreeze();
        }
    };

    KPWSPharmacyBillingPOS.prototype.cancelParkedInvoice = async function (name) {
        if (!confirm("Cancel parked invoice " + name + "?")) return;

        frappe.dom.freeze("Cancelling parked invoice...");

        try {
            await this.call("cancel_parked_invoice", { name });

            frappe.dom.unfreeze();

            frappe.show_alert({
                message: "Parked invoice cancelled.",
                indicator: "orange"
            }, 8);

            this.loadParkedInvoices();

        } catch (e) {
            frappe.dom.unfreeze();
        }
    };

    KPWSPharmacyBillingPOS.prototype.createInvoice = async function (submit) {
        if (!this.patientContext) {
            frappe.msgprint("Please select Patient or enable Walk-in Patient first.");
            return;
        }

        if (this.isWalkin && this.isWalkin()) {
            if (!this.getWalkinName()) {
                frappe.msgprint("Please enter Walk-in Patient Name.");
                return;
            }

            if (!this.getWalkinMR()) {
                frappe.msgprint("Please enter Walk-in MR Number.");
                return;
            }
        }

        if (!this.cart || !this.cart.length) {
            frappe.msgprint("Please add at least one item.");
            return;
        }

        const payload = this.buildInvoicePayload(submit);

        frappe.dom.freeze(submit ? "Submitting Sales Invoice..." : "Creating Sales Invoice...");

        try {
            const r = await this.call("create_invoice", {
                payload: JSON.stringify(payload)
            });

            const data = r.message || {};

            if (this.currentParkedInvoice && data.name) {
                await this.call("mark_parked_invoice_completed", {
                    name: this.currentParkedInvoice,
                    invoice: data.name
                });
            }

            frappe.dom.unfreeze();

            this.lastInvoice = data;

            frappe.show_alert({
                message: data.message || "Sales Invoice created successfully.",
                indicator: "green"
            }, 8);

            this.renderLastInvoice(data);

            if (submit) {
                this.openPrint(data);
            }

            this.currentParkedInvoice = null;
            this.cart = [];
            this.paymentPlan = null;
            this.updateCart();
            this.renderCurrentParkedBadge();

            this.page.main.find("#kpws-search-results").html("");
            this.page.main.find("#kpws-item-search").val("");
            this.page.main.find("#kpws-card-amount").val("0");

            if (this.isWalkin && this.isWalkin()) {
                this.page.main.find("#kpws-walkin-name").val("");
                this.page.main.find("#kpws-walkin-mr").val("");
                this.page.main.find("#kpws-mr").text("Walk-in");
                this.page.main.find("#kpws-patient-name").text("Walk-in Patient");
            }

        } catch (e) {
            frappe.dom.unfreeze();
        }
    };
})();




/* KPWS_ADMIN_SETTINGS_RETURN_PRINT_V20_PATCH */

(function () {
    if (typeof KPWSPharmacyBillingPOS === "undefined") {
        console.warn("KPWSPharmacyBillingPOS not found. Admin settings patch skipped.");
        return;
    }

    KPWSPharmacyBillingPOS.prototype.canShowSettings = function () {
        return frappe.session && frappe.session.user === "Administrator";
    };

    const oldRenderAdminSettingsV20 = KPWSPharmacyBillingPOS.prototype.render;

    KPWSPharmacyBillingPOS.prototype.render = function () {
        oldRenderAdminSettingsV20.apply(this, arguments);

        if (!this.canShowSettings()) {
            this.page.main.find('[data-tab="settings"]').remove();
            this.page.main.find("#kpws-settings-tab").remove();
        }
    };

    KPWSPharmacyBillingPOS.prototype.renderSettings = function () {
        const root = this.page.main.find("#kpws-settings-tab");

        if (!root.length) return;

        if (!this.canShowSettings()) {
            root.html(`
                <div class="kpws-pos-card">
                    <div class="kpws-pos-card-title">Settings Restricted</div>
                    <div class="kpws-pos-warning">
                        Pharmacy POS Settings are available only to the Administrator user.
                    </div>
                </div>
            `);
            return;
        }

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

                <div class="kpws-pos-card-title" style="margin-top:18px;">Billing Print Formats</div>

                <div class="kpws-pos-grid">
                    <div id="kpws-setting-cash-print-format"></div>
                    <div id="kpws-setting-welfare-print-format"></div>
                    <div id="kpws-setting-panel-print-format"></div>
                </div>

                <div class="kpws-pos-card-title" style="margin-top:18px;">Return Print Formats</div>

                <div class="kpws-pos-grid">
                    <div id="kpws-setting-cash-return-print-format"></div>
                    <div id="kpws-setting-welfare-return-print-format"></div>
                    <div id="kpws-setting-panel-return-print-format"></div>
                    <div id="kpws-setting-walkin-return-print-format"></div>
                </div>

                <div class="kpws-pos-warning" style="margin-top:14px;">
                    Return print formats are used when a return invoice is created from Pharmacy POS or Return Requests.
                    If any return format is empty, the system will fall back to the normal billing print format.
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
    };

    KPWSPharmacyBillingPOS.prototype.makeSettingsControls = function () {
        const make = (id, label, fieldtype, options, fieldname) => {
            const target = this.page.main.find(id).get(0);
            if (!target) return;

            const control = frappe.ui.form.make_control({
                parent: target,
                df: {
                    label,
                    fieldtype,
                    options,
                    fieldname,
                    get_query: fieldtype === "Link" && options === "Print Format"
                        ? function () {
                            return {
                                filters: {
                                    doc_type: "Sales Invoice"
                                }
                            };
                        }
                        : undefined
                },
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

        make("#kpws-setting-cash-print-format", "Cash Billing Print Format", "Link", "Print Format", "cash_print_format");
        make("#kpws-setting-welfare-print-format", "Welfare Billing Print Format", "Link", "Print Format", "welfare_print_format");
        make("#kpws-setting-panel-print-format", "Panel Billing Print Format", "Link", "Print Format", "panel_print_format");

        make("#kpws-setting-cash-return-print-format", "Cash Return Print Format", "Link", "Print Format", "cash_return_print_format");
        make("#kpws-setting-welfare-return-print-format", "Welfare Return Print Format", "Link", "Print Format", "welfare_return_print_format");
        make("#kpws-setting-panel-return-print-format", "Panel Return Print Format", "Link", "Print Format", "panel_return_print_format");
        make("#kpws-setting-walkin-return-print-format", "Walk-in Return Print Format", "Link", "Print Format", "walkin_return_print_format");
    };

    KPWSPharmacyBillingPOS.prototype.saveSettings = async function () {
        if (!this.canShowSettings()) {
            frappe.msgprint("Only Administrator user can save Pharmacy POS Settings.");
            return;
        }

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
            panel_print_format: get("panel_print_format"),

            cash_return_print_format: get("cash_return_print_format"),
            welfare_return_print_format: get("welfare_return_print_format"),
            panel_return_print_format: get("panel_return_print_format"),
            walkin_return_print_format: get("walkin_return_print_format")
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
    };
})();




/* KPWS_SETTINGS_UI_V21_PATCH */

(function () {
    if (typeof KPWSPharmacyBillingPOS === "undefined") {
        console.warn("KPWSPharmacyBillingPOS not found. Settings UI patch skipped.");
        return;
    }

    function injectSettingsUICSS() {
        if (document.getElementById("kpws-settings-ui-v21-css")) return;

        const css = `
            .kpws-settings-screen {
                background: #f8fafc;
                border-radius: 18px;
            }

            .kpws-settings-header {
                background: linear-gradient(135deg, #0f172a, #1e293b);
                color: #ffffff;
                border-radius: 18px;
                padding: 18px 20px;
                margin-bottom: 16px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 14px;
                box-shadow: 0 8px 22px rgba(15, 23, 42, 0.16);
            }

            .kpws-settings-title {
                color: #ffffff !important;
                font-size: 20px;
                font-weight: 950;
                margin-bottom: 4px;
            }

            .kpws-settings-subtitle {
                color: #cbd5e1 !important;
                font-size: 13px;
                font-weight: 700;
            }

            .kpws-settings-admin-badge {
                background: #dcfce7;
                color: #166534 !important;
                border: 1px solid #86efac;
                border-radius: 999px;
                padding: 7px 12px;
                font-size: 12px;
                font-weight: 950;
                white-space: nowrap;
            }

            .kpws-settings-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 16px;
                align-items: start;
            }

            .kpws-settings-section {
                background: #ffffff;
                border: 1px solid #dbe4ef;
                border-radius: 18px;
                padding: 16px;
                box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
                margin-bottom: 16px;
            }

            .kpws-settings-section.full {
                grid-column: 1 / -1;
            }

            .kpws-settings-section-title {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
                margin-bottom: 14px;
                padding-bottom: 10px;
                border-bottom: 1px solid #e5e7eb;
            }

            .kpws-settings-section-title h3 {
                margin: 0;
                color: #000000 !important;
                font-size: 15px;
                font-weight: 950;
                letter-spacing: 0.01em;
            }

            .kpws-settings-section-title span {
                color: #475569 !important;
                font-size: 12px;
                font-weight: 800;
            }

            .kpws-settings-fields {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 14px;
            }

            .kpws-settings-fields.one {
                grid-template-columns: 1fr;
            }

            .kpws-settings-field {
                min-width: 0;
            }

            .kpws-settings-screen .frappe-control {
                margin-bottom: 0 !important;
            }

            .kpws-settings-screen .frappe-control .control-label,
            .kpws-settings-screen label.control-label,
            .kpws-settings-screen .control-label,
            .kpws-settings-screen .field-label {
                color: #0f172a !important;
                opacity: 1 !important;
                font-size: 12px !important;
                font-weight: 950 !important;
                margin-bottom: 6px !important;
                text-transform: none !important;
            }

            .kpws-settings-screen .control-input-wrapper,
            .kpws-settings-screen .control-input {
                background: transparent !important;
            }

            .kpws-settings-screen input,
            .kpws-settings-screen .input-with-feedback,
            .kpws-settings-screen .form-control,
            .kpws-settings-screen .awesomplete input,
            .kpws-settings-screen .link-field,
            .kpws-settings-screen select {
                background: #ffffff !important;
                color: #000000 !important;
                border: 1px solid #b7c3d0 !important;
                border-radius: 12px !important;
                min-height: 40px !important;
                font-size: 13px !important;
                font-weight: 850 !important;
                box-shadow: none !important;
            }

            .kpws-settings-screen input:focus,
            .kpws-settings-screen .form-control:focus,
            .kpws-settings-screen .awesomplete input:focus {
                border-color: #2563eb !important;
                box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12) !important;
            }

            .kpws-settings-screen .link-btn,
            .kpws-settings-screen .btn-open-row,
            .kpws-settings-screen .btn-clear {
                color: #334155 !important;
                opacity: 1 !important;
            }

            .kpws-settings-controls-grid {
                display: grid;
                grid-template-columns: repeat(3, minmax(190px, 1fr));
                gap: 10px;
            }

            .kpws-settings-check {
                display: flex;
                align-items: center;
                gap: 10px;
                background: #f8fafc;
                border: 1px solid #dbe4ef;
                border-radius: 14px;
                padding: 11px 12px;
                color: #111827 !important;
                font-weight: 900;
                font-size: 13px;
                min-height: 46px;
            }

            .kpws-settings-check input {
                width: 16px;
                height: 16px;
                min-height: auto !important;
                accent-color: #2563eb;
            }

            .kpws-settings-actions {
                position: sticky;
                bottom: 0;
                z-index: 5;
                background: rgba(248, 250, 252, 0.94);
                backdrop-filter: blur(8px);
                border-top: 1px solid #dbe4ef;
                padding: 14px 0 0;
                margin-top: 12px;
                display: flex;
                justify-content: flex-end;
                gap: 10px;
            }

            .kpws-settings-save-btn {
                min-width: 180px;
                min-height: 44px;
                border-radius: 14px;
                background: #16a34a;
                color: #ffffff !important;
                border: 0;
                font-size: 14px;
                font-weight: 950;
                cursor: pointer;
            }

            .kpws-settings-note {
                background: #eff6ff;
                border: 1px solid #bfdbfe;
                color: #1e3a8a !important;
                border-radius: 14px;
                padding: 11px 12px;
                font-size: 13px;
                font-weight: 800;
                line-height: 1.45;
                margin-top: 12px;
            }

            @media (max-width: 1100px) {
                .kpws-settings-grid {
                    grid-template-columns: 1fr;
                }

                .kpws-settings-fields {
                    grid-template-columns: 1fr;
                }

                .kpws-settings-controls-grid {
                    grid-template-columns: repeat(2, minmax(180px, 1fr));
                }
            }

            @media (max-width: 650px) {
                .kpws-settings-header {
                    flex-direction: column;
                    align-items: flex-start;
                }

                .kpws-settings-controls-grid {
                    grid-template-columns: 1fr;
                }
            }
        `;

        const style = document.createElement("style");
        style.id = "kpws-settings-ui-v21-css";
        style.innerHTML = css;
        document.head.appendChild(style);
    }

    injectSettingsUICSS();

    KPWSPharmacyBillingPOS.prototype.renderSettings = function () {
        injectSettingsUICSS();

        const root = this.page.main.find("#kpws-settings-tab");

        if (!root.length) return;

        if (this.canShowSettings && !this.canShowSettings()) {
            root.html(`
                <div class="kpws-settings-screen">
                    <div class="kpws-settings-section">
                        <div class="kpws-settings-section-title">
                            <h3>Settings Restricted</h3>
                        </div>
                        <div class="kpws-pos-warning">
                            Pharmacy POS Settings are available only to the Administrator user.
                        </div>
                    </div>
                </div>
            `);
            return;
        }

        root.html(`
            <div class="kpws-settings-screen">
                <div class="kpws-settings-header">
                    <div>
                        <div class="kpws-settings-title">Pharmacy Billing Settings</div>
                        <div class="kpws-settings-subtitle">
                            Configure pharmacy warehouse, payment modes, price lists, print formats and billing controls.
                        </div>
                    </div>
                    <div class="kpws-settings-admin-badge">Administrator Only</div>
                </div>

                <div class="kpws-settings-grid">
                    <div class="kpws-settings-section">
                        <div class="kpws-settings-section-title">
                            <h3>Operational Defaults</h3>
                            <span>Company, warehouse and customer</span>
                        </div>
                        <div class="kpws-settings-fields">
                            <div class="kpws-settings-field" id="kpws-setting-company"></div>
                            <div class="kpws-settings-field" id="kpws-setting-warehouse"></div>
                            <div class="kpws-settings-field" id="kpws-setting-cash-customer"></div>
                        </div>
                    </div>

                    <div class="kpws-settings-section">
                        <div class="kpws-settings-section-title">
                            <h3>Payment Modes</h3>
                            <span>Cash, card, panel and welfare</span>
                        </div>
                        <div class="kpws-settings-fields">
                            <div class="kpws-settings-field" id="kpws-setting-cash-mop"></div>
                            <div class="kpws-settings-field" id="kpws-setting-card-mop"></div>
                            <div class="kpws-settings-field" id="kpws-setting-panel-mop"></div>
                            <div class="kpws-settings-field" id="kpws-setting-zakat-mop"></div>
                            <div class="kpws-settings-field" id="kpws-setting-donation-mop"></div>
                        </div>
                    </div>

                    <div class="kpws-settings-section">
                        <div class="kpws-settings-section-title">
                            <h3>Price Lists</h3>
                            <span>Used while adding pharmacy items</span>
                        </div>
                        <div class="kpws-settings-fields">
                            <div class="kpws-settings-field" id="kpws-setting-cash-pl"></div>
                            <div class="kpws-settings-field" id="kpws-setting-welfare-pl"></div>
                            <div class="kpws-settings-field" id="kpws-setting-panel-pl"></div>
                        </div>
                    </div>

                    <div class="kpws-settings-section">
                        <div class="kpws-settings-section-title">
                            <h3>Billing Print Formats</h3>
                            <span>Normal invoices</span>
                        </div>
                        <div class="kpws-settings-fields">
                            <div class="kpws-settings-field" id="kpws-setting-cash-print-format"></div>
                            <div class="kpws-settings-field" id="kpws-setting-welfare-print-format"></div>
                            <div class="kpws-settings-field" id="kpws-setting-panel-print-format"></div>
                        </div>
                    </div>

                    <div class="kpws-settings-section full">
                        <div class="kpws-settings-section-title">
                            <h3>Return Print Formats</h3>
                            <span>Return / credit note print formats</span>
                        </div>
                        <div class="kpws-settings-fields">
                            <div class="kpws-settings-field" id="kpws-setting-cash-return-print-format"></div>
                            <div class="kpws-settings-field" id="kpws-setting-welfare-return-print-format"></div>
                            <div class="kpws-settings-field" id="kpws-setting-panel-return-print-format"></div>
                            <div class="kpws-settings-field" id="kpws-setting-walkin-return-print-format"></div>
                        </div>
                        <div class="kpws-settings-note">
                            If a return print format is empty, the system will automatically fall back to the normal billing print format for that billing type.
                        </div>
                    </div>

                    <div class="kpws-settings-section full">
                        <div class="kpws-settings-section-title">
                            <h3>Controls</h3>
                            <span>Validation and billing behavior</span>
                        </div>

                        <div class="kpws-settings-controls-grid">
                            ${this.checkboxHTML("require_cash_payment", "Require Cash Payment")}
                            ${this.checkboxHTML("auto_submit_invoice", "Auto Submit Invoice")}
                            ${this.checkboxHTML("update_stock", "Update Stock")}
                            ${this.checkboxHTML("enforce_patient_status", "Block Invalid Patient Status")}
                            ${this.checkboxHTML("enforce_pharmacy_stock", "Block No Stock")}
                            ${this.checkboxHTML("block_missing_price", "Block Missing Price")}
                            ${this.checkboxHTML("allow_manual_rate", "Allow Manual Rate")}
                        </div>
                    </div>
                </div>

                <div class="kpws-settings-actions">
                    <button class="kpws-settings-save-btn" id="kpws-save-settings">Save Settings</button>
                </div>
            </div>
        `);

        this.makeSettingsControls();

        root.find("[data-setting-check]").each(function () {
            const field = $(this).data("setting-check");
            const checked = Number((window.kpws_pharmacy_billing && window.kpws_pharmacy_billing.settings && window.kpws_pharmacy_billing.settings[field]) || 0);
            $(this).prop("checked", !!checked);
        });

        root.find("#kpws-save-settings").on("click", () => this.saveSettings());

        setTimeout(() => injectSettingsUICSS(), 300);
    };

    KPWSPharmacyBillingPOS.prototype.checkboxHTML = function (field, label) {
        const checked = Number(this.settings && this.settings[field] || 0) ? "checked" : "";
        return `
            <label class="kpws-settings-check">
                <input type="checkbox" data-setting-check="${field}" ${checked}>
                <span>${label}</span>
            </label>
        `;
    };

    KPWSPharmacyBillingPOS.prototype.makeSettingsControls = function () {
        const make = (id, label, fieldtype, options, fieldname) => {
            const target = this.page.main.find(id).get(0);
            if (!target) return;

            const control = frappe.ui.form.make_control({
                parent: target,
                df: {
                    label,
                    fieldtype,
                    options,
                    fieldname,
                    get_query: fieldtype === "Link" && options === "Print Format"
                        ? function () {
                            return {
                                filters: {
                                    doc_type: "Sales Invoice"
                                }
                            };
                        }
                        : undefined
                },
                render_input: true
            });

            control.set_value(this.settings && this.settings[fieldname] || "");
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

        make("#kpws-setting-cash-print-format", "Cash Billing Print Format", "Link", "Print Format", "cash_print_format");
        make("#kpws-setting-welfare-print-format", "Welfare Billing Print Format", "Link", "Print Format", "welfare_print_format");
        make("#kpws-setting-panel-print-format", "Panel Billing Print Format", "Link", "Print Format", "panel_print_format");

        make("#kpws-setting-cash-return-print-format", "Cash Return Print Format", "Link", "Print Format", "cash_return_print_format");
        make("#kpws-setting-welfare-return-print-format", "Welfare Return Print Format", "Link", "Print Format", "welfare_return_print_format");
        make("#kpws-setting-panel-return-print-format", "Panel Return Print Format", "Link", "Print Format", "panel_return_print_format");
        make("#kpws-setting-walkin-return-print-format", "Walk-in Return Print Format", "Link", "Print Format", "walkin_return_print_format");
    };
})();




/* KPWS_SETTINGS_CHECKBOX_FIX_V22_PATCH */

(function () {
    if (typeof KPWSPharmacyBillingPOS === "undefined") {
        console.warn("KPWSPharmacyBillingPOS not found. Settings checkbox fix skipped.");
        return;
    }

    function injectCheckboxFixCSS() {
        if (document.getElementById("kpws-settings-checkbox-fix-v22-css")) return;

        const css = `
            .kpws-settings-check {
                cursor: pointer !important;
                user-select: none !important;
                position: relative !important;
            }

            .kpws-settings-check input.kpws-settings-checkbox {
                position: absolute !important;
                opacity: 0 !important;
                width: 1px !important;
                height: 1px !important;
                min-height: 1px !important;
                pointer-events: none !important;
            }

            .kpws-settings-toggle {
                width: 42px;
                height: 24px;
                border-radius: 999px;
                background: #cbd5e1;
                border: 1px solid #94a3b8;
                display: inline-flex;
                align-items: center;
                padding: 2px;
                transition: all 0.18s ease;
                flex: 0 0 auto;
            }

            .kpws-settings-toggle-knob {
                width: 18px;
                height: 18px;
                border-radius: 999px;
                background: #ffffff;
                box-shadow: 0 1px 4px rgba(15, 23, 42, 0.25);
                transform: translateX(0);
                transition: all 0.18s ease;
            }

            .kpws-settings-check.is-checked {
                background: #eff6ff !important;
                border-color: #93c5fd !important;
            }

            .kpws-settings-check.is-checked .kpws-settings-toggle {
                background: #2563eb;
                border-color: #2563eb;
            }

            .kpws-settings-check.is-checked .kpws-settings-toggle-knob {
                transform: translateX(18px);
            }

            .kpws-settings-check-label {
                color: #111827 !important;
                font-weight: 950 !important;
            }
        `;

        const style = document.createElement("style");
        style.id = "kpws-settings-checkbox-fix-v22-css";
        style.innerHTML = css;
        document.head.appendChild(style);
    }

    injectCheckboxFixCSS();

    KPWSPharmacyBillingPOS.prototype.checkboxHTML = function (field, label) {
        const checked = Number((this.settings && this.settings[field]) || 0) ? "checked" : "";
        const checkedClass = checked ? "is-checked" : "";

        return `
            <label class="kpws-settings-check ${checkedClass}" data-setting-toggle="${field}">
                <input
                    type="checkbox"
                    class="kpws-settings-checkbox"
                    data-setting-check="${field}"
                    ${checked}
                >
                <span class="kpws-settings-toggle">
                    <span class="kpws-settings-toggle-knob"></span>
                </span>
                <span class="kpws-settings-check-label">${label}</span>
            </label>
        `;
    };

    KPWSPharmacyBillingPOS.prototype.bindSettingsCheckboxes = function () {
        const root = this.page.main.find("#kpws-settings-tab");

        root.find(".kpws-settings-check").off("click.kpwscheck").on("click.kpwscheck", function (e) {
            e.preventDefault();
            e.stopPropagation();

            const checkbox = $(this).find("input[data-setting-check]");
            const newValue = !checkbox.prop("checked");

            checkbox.prop("checked", newValue);
            $(this).toggleClass("is-checked", newValue);
        });

        root.find("input[data-setting-check]").each(function () {
            const checked = $(this).prop("checked");
            $(this).closest(".kpws-settings-check").toggleClass("is-checked", checked);
        });
    };

    const oldRenderSettingsCheckboxFixV22 = KPWSPharmacyBillingPOS.prototype.renderSettings;

    KPWSPharmacyBillingPOS.prototype.renderSettings = function () {
        oldRenderSettingsCheckboxFixV22.apply(this, arguments);

        injectCheckboxFixCSS();

        setTimeout(() => {
            this.bindSettingsCheckboxes();
        }, 200);
    };

    KPWSPharmacyBillingPOS.prototype.saveSettings = async function () {
        if (this.canShowSettings && !this.canShowSettings()) {
            frappe.msgprint("Only Administrator user can save Pharmacy POS Settings.");
            return;
        }

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
            panel_print_format: get("panel_print_format"),

            cash_return_print_format: get("cash_return_print_format"),
            welfare_return_print_format: get("welfare_return_print_format"),
            panel_return_print_format: get("panel_return_print_format"),
            walkin_return_print_format: get("walkin_return_print_format")
        };

        this.page.main.find("#kpws-settings-tab input[data-setting-check]").each(function () {
            const fieldname = $(this).data("setting-check");
            values[fieldname] = $(this).prop("checked") ? 1 : 0;
        });

        frappe.dom.freeze("Saving Pharmacy POS Settings...");

        try {
            const r = await this.call("save_settings", {
                values: JSON.stringify(values)
            });

            frappe.dom.unfreeze();

            this.settings = r.message || {};

            frappe.show_alert({
                message: "Settings saved successfully.",
                indicator: "green"
            }, 8);

            this.renderSettings();

        } catch (e) {
            frappe.dom.unfreeze();
        }
    };
})();




/* KPWS_CUSTOMER_ADVANCE_V23_PATCH */

(function () {
    if (typeof KPWSPharmacyBillingPOS === "undefined") {
        console.warn("KPWSPharmacyBillingPOS not found. Customer advance patch skipped.");
        return;
    }

    function injectAdvanceCSS() {
        if (document.getElementById("kpws-customer-advance-v23-css")) return;

        const css = `
            .kpws-advance-box {
                background: #f8fafc;
                border: 1px solid #dbe4ef;
                border-radius: 16px;
                padding: 12px;
                margin-top: 12px;
            }

            .kpws-advance-head {
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 10px;
                margin-bottom: 10px;
            }

            .kpws-advance-title {
                color: #000000 !important;
                font-weight: 950;
                font-size: 14px;
            }

            .kpws-advance-badge {
                border-radius: 999px;
                padding: 4px 9px;
                font-size: 12px;
                font-weight: 950;
                background: #e2e8f0;
                color: #334155 !important;
            }

            .kpws-advance-badge.ok {
                background: #dcfce7;
                color: #166534 !important;
                border: 1px solid #86efac;
            }

            .kpws-advance-badge.warn {
                background: #fff7ed;
                color: #9a3412 !important;
                border: 1px solid #fed7aa;
            }

            .kpws-advance-grid {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 8px;
                align-items: end;
            }

            .kpws-advance-stat label {
                display: block;
                color: #334155 !important;
                font-size: 11px;
                font-weight: 950;
                margin-bottom: 4px;
            }

            .kpws-advance-stat div,
            .kpws-advance-stat input {
                min-height: 36px;
                border: 1px solid #cbd5e1;
                border-radius: 11px;
                padding: 8px;
                background: #ffffff;
                color: #000000 !important;
                font-weight: 900;
                width: 100%;
            }

            .kpws-advance-toggle {
                display: flex;
                align-items: center;
                gap: 8px;
                font-weight: 950;
                color: #111827 !important;
                margin-top: 10px;
                cursor: pointer;
            }

            .kpws-advance-note {
                margin-top: 8px;
                color: #475569 !important;
                font-size: 12px;
                font-weight: 800;
            }

            @media (max-width: 650px) {
                .kpws-advance-grid {
                    grid-template-columns: 1fr;
                }
            }
        `;

        const style = document.createElement("style");
        style.id = "kpws-customer-advance-v23-css";
        style.innerHTML = css;
        document.head.appendChild(style);
    }

    injectAdvanceCSS();

    KPWSPharmacyBillingPOS.prototype.injectAdvanceUI = function () {
        injectAdvanceCSS();

        if (this.page.main.find("#kpws-customer-advance-box").length) return;

        const cardInput = this.page.main.find("#kpws-card-amount");
        const field = cardInput.closest(".kpws-pos-field");

        if (!field.length) return;

        field.after(`
            <div class="kpws-advance-box" id="kpws-customer-advance-box">
                <div class="kpws-advance-head">
                    <div class="kpws-advance-title">Customer Advance</div>
                    <div class="kpws-advance-badge" id="kpws-advance-status">Checking...</div>
                </div>

                <div class="kpws-advance-grid">
                    <div class="kpws-advance-stat">
                        <label>Advance Customer</label>
                        <div id="kpws-advance-type">-</div>
                    </div>
                    <div class="kpws-advance-stat">
                        <label>Available Balance</label>
                        <div id="kpws-advance-available">0.00</div>
                    </div>
                    <div class="kpws-advance-stat">
                        <label>Allocate Amount</label>
                        <input type="number" min="0" step="0.01" id="kpws-advance-amount" value="0">
                    </div>
                </div>

                <label class="kpws-advance-toggle">
                    <input type="checkbox" id="kpws-use-advance">
                    Use available customer advance on this invoice
                </label>

                <div class="kpws-advance-note" id="kpws-advance-note">
                    Mark Customer as Is Advance Customer and receive advance through Payment Entry.
                </div>
            </div>
        `);

        this.page.main.find("#kpws-use-advance, #kpws-advance-amount").on("input change", () => {
            this.refreshPaymentPlan();
        });
    };

    KPWSPharmacyBillingPOS.prototype.currentBillToCustomer = function () {
        if (this.billToControl && this.billToControl.get_value()) {
            return this.billToControl.get_value();
        }

        if (this.patientContext && this.patientContext.bill_to_customer) {
            return this.patientContext.bill_to_customer;
        }

        return "";
    };

    KPWSPharmacyBillingPOS.prototype.refreshCustomerAdvanceInfo = async function () {
        this.injectAdvanceUI();

        const customer = this.currentBillToCustomer();

        if (!customer) {
            this.customerAdvanceInfo = null;
            this.page.main.find("#kpws-advance-status").removeClass("ok warn").text("No Customer");
            this.page.main.find("#kpws-advance-type").text("-");
            this.page.main.find("#kpws-advance-available").text("0.00");
            this.page.main.find("#kpws-advance-amount").val("0");
            this.page.main.find("#kpws-use-advance").prop("checked", false);
            return;
        }

        try {
            const r = await this.call("get_customer_advance_info", { customer });
            const info = r.message || {};
            this.customerAdvanceInfo = info;

            const available = Number(info.available_advance || 0);
            const enabled = Number(info.enabled || 0);
            const isAdvanceCustomer = Number(info.is_advance_customer || 0);

            this.page.main.find("#kpws-advance-type").text(
                isAdvanceCustomer ? (info.advance_type || "Advance Customer") : "Not Marked"
            );

            this.page.main.find("#kpws-advance-available").text(available.toFixed(2));

            if (!enabled) {
                this.page.main.find("#kpws-advance-status").removeClass("ok").addClass("warn").text("Disabled");
                this.page.main.find("#kpws-use-advance").prop("checked", false);
                this.page.main.find("#kpws-advance-amount").val("0");
                return;
            }

            if (isAdvanceCustomer && available > 0) {
                this.page.main.find("#kpws-advance-status").removeClass("warn").addClass("ok").text("Available");

                const total = this.total ? this.total() : 0;
                const allocation = Math.min(total, available);

                this.page.main.find("#kpws-use-advance").prop("checked", true);
                this.page.main.find("#kpws-advance-amount").val(allocation.toFixed(2));
            } else if (!isAdvanceCustomer && available > 0) {
                this.page.main.find("#kpws-advance-status").removeClass("ok").addClass("warn").text("Not Enabled");
                this.page.main.find("#kpws-use-advance").prop("checked", false);
                this.page.main.find("#kpws-advance-amount").val("0");
            } else {
                this.page.main.find("#kpws-advance-status").removeClass("ok").addClass("warn").text("No Balance");
                this.page.main.find("#kpws-use-advance").prop("checked", false);
                this.page.main.find("#kpws-advance-amount").val("0");
            }

        } catch (e) {
            this.customerAdvanceInfo = null;
            this.page.main.find("#kpws-advance-status").removeClass("ok").addClass("warn").text("Error");
        }
    };

    KPWSPharmacyBillingPOS.prototype.getAdvanceAllocationAmount = function () {
        if (!this.page.main.find("#kpws-use-advance").is(":checked")) return 0;

        const available = Number((this.customerAdvanceInfo && this.customerAdvanceInfo.available_advance) || 0);
        const total = this.total ? this.total() : 0;
        const requested = Number(this.page.main.find("#kpws-advance-amount").val() || 0);

        return Math.max(0, Math.min(available, total, requested));
    };

    const oldRenderBillingAdvanceV23 = KPWSPharmacyBillingPOS.prototype.renderBilling;

    KPWSPharmacyBillingPOS.prototype.renderBilling = function () {
        oldRenderBillingAdvanceV23.apply(this, arguments);
        this.injectAdvanceUI();
        this.refreshCustomerAdvanceInfo();
    };

    const oldLoadPatientAdvanceV23 = KPWSPharmacyBillingPOS.prototype.loadPatient;

    KPWSPharmacyBillingPOS.prototype.loadPatient = async function (patient) {
        await oldLoadPatientAdvanceV23.apply(this, arguments);
        await this.refreshCustomerAdvanceInfo();
    };

    const oldApplyWalkinAdvanceV23 = KPWSPharmacyBillingPOS.prototype.applyWalkinMode;

    if (oldApplyWalkinAdvanceV23) {
        KPWSPharmacyBillingPOS.prototype.applyWalkinMode = async function () {
            await oldApplyWalkinAdvanceV23.apply(this, arguments);
            await this.refreshCustomerAdvanceInfo();
        };
    }

    const oldUpdateCartAdvanceV23 = KPWSPharmacyBillingPOS.prototype.updateCart;

    KPWSPharmacyBillingPOS.prototype.updateCart = function () {
        oldUpdateCartAdvanceV23.apply(this, arguments);

        if (this.customerAdvanceInfo) {
            const available = Number(this.customerAdvanceInfo.available_advance || 0);
            const total = this.total ? this.total() : 0;

            if (this.page.main.find("#kpws-use-advance").is(":checked")) {
                const allocation = Math.min(available, total);
                this.page.main.find("#kpws-advance-amount").val(allocation.toFixed(2));
            }
        }
    };

    KPWSPharmacyBillingPOS.prototype.refreshPaymentPlan = async function () {
        const invoiceTotal = this.total ? this.total() : 0;
        const advanceAmount = this.getAdvanceAllocationAmount ? this.getAdvanceAllocationAmount() : 0;
        const remainingTotal = Math.max(0, invoiceTotal - advanceAmount);
        const cardAmount = Number(this.page.main.find("#kpws-card-amount").val() || 0);

        this.page.main.find("#kpws-final-total").text(invoiceTotal.toFixed(2));

        if (!this.patientContext || invoiceTotal <= 0) {
            this.page.main.find("#kpws-covered-amount").text("0.00");
            this.page.main.find("#kpws-patient-share").text("0.00");
            this.page.main.find("#kpws-payable-now").text("0.00");
            this.page.main.find("#kpws-payment-plan").html(`<div class="kpws-pos-warning">Add items to calculate payment split.</div>`);
            return;
        }

        try {
            const method = this.isWalkin && this.isWalkin() ? "get_walkin_payment_plan" : "get_payment_plan";
            const args = this.isWalkin && this.isWalkin()
                ? { total: remainingTotal, card_amount: cardAmount }
                : { patient: this.patientContext.patient, total: remainingTotal, card_amount: cardAmount };

            const r = await this.call(method, args);

            this.paymentPlan = r.message || {};
            this.paymentPlan.invoice_total = invoiceTotal;
            this.paymentPlan.customer_advance_allocated = advanceAmount;
            this.paymentPlan.remaining_after_advance = remainingTotal;

            this.renderPaymentPlan();

        } catch (e) {
            this.page.main.find("#kpws-payment-plan").html(`<div class="kpws-pos-warning">Unable to calculate payment plan.</div>`);
        }
    };

    KPWSPharmacyBillingPOS.prototype.renderPaymentPlan = function () {
        const plan = this.paymentPlan || {};
        const rows = plan.rows || [];
        const warnings = plan.warnings || [];

        const invoiceTotal = Number(plan.invoice_total || plan.total || 0);
        const advance = Number(plan.customer_advance_allocated || 0);
        const covered = Number(plan.covered_amount || 0);
        const share = Number(plan.patient_share || 0);

        this.page.main.find("#kpws-final-total").text(invoiceTotal.toFixed(2));
        this.page.main.find("#kpws-covered-amount").text(covered.toFixed(2));
        this.page.main.find("#kpws-patient-share").text(share.toFixed(2));
        this.page.main.find("#kpws-payable-now").text(share.toFixed(2));

        let html = "";

        if (warnings.length) {
            html += warnings.map(w => `<div class="kpws-pos-warning">${this.esc(w)}</div>`).join("");
        }

        const allRows = [];

        if (advance > 0) {
            allRows.push({
                label: "Customer Advance",
                mode_of_payment: "ERPNext Advance Allocation",
                amount: advance
            });
        }

        rows.forEach(row => allRows.push(row));

        if (!allRows.length) {
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
                        ${allRows.map(row => `
                            <tr>
                                <td>${this.esc(row.label || row.role || "")}</td>
                                <td>${this.esc(row.mode_of_payment || "Advance")}</td>
                                <td style="text-align:right;">${Number(row.amount || 0).toFixed(2)}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            `;
        }

        this.page.main.find("#kpws-payment-plan").html(html);
    };

    const oldBuildPayloadAdvanceV23 = KPWSPharmacyBillingPOS.prototype.buildInvoicePayload;

    KPWSPharmacyBillingPOS.prototype.buildInvoicePayload = function (submit) {
        const payload = oldBuildPayloadAdvanceV23
            ? oldBuildPayloadAdvanceV23.apply(this, arguments)
            : {
                submit: submit ? 1 : 0,
                items: []
            };

        const useAdvance = this.page.main.find("#kpws-use-advance").is(":checked") ? 1 : 0;
        const advanceAmount = this.getAdvanceAllocationAmount ? this.getAdvanceAllocationAmount() : 0;

        payload.use_customer_advance = useAdvance;
        payload.advance_amount = advanceAmount;

        return payload;
    };

    const oldMakeSettingsControlsAdvanceV23 = KPWSPharmacyBillingPOS.prototype.makeSettingsControls;

    KPWSPharmacyBillingPOS.prototype.makeSettingsControls = function () {
        oldMakeSettingsControlsAdvanceV23.apply(this, arguments);
    };

    const oldSaveSettingsAdvanceV23 = KPWSPharmacyBillingPOS.prototype.saveSettings;

    KPWSPharmacyBillingPOS.prototype.saveSettings = async function () {
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
            panel_print_format: get("panel_print_format"),

            cash_return_print_format: get("cash_return_print_format"),
            welfare_return_print_format: get("welfare_return_print_format"),
            panel_return_print_format: get("panel_return_print_format"),
            walkin_return_print_format: get("walkin_return_print_format")
        };

        this.page.main.find("#kpws-settings-tab input[data-setting-check]").each(function () {
            const fieldname = $(this).data("setting-check");
            values[fieldname] = $(this).prop("checked") ? 1 : 0;
        });

        if (typeof values.enable_customer_advance_allocation === "undefined") {
            values.enable_customer_advance_allocation = Number(this.settings && this.settings.enable_customer_advance_allocation || 0);
        }

        frappe.dom.freeze("Saving Pharmacy POS Settings...");

        try {
            const r = await this.call("save_settings", {
                values: JSON.stringify(values)
            });

            frappe.dom.unfreeze();

            this.settings = r.message || {};

            frappe.show_alert({
                message: "Settings saved successfully.",
                indicator: "green"
            }, 8);

            this.renderSettings();

        } catch (e) {
            frappe.dom.unfreeze();
        }
    };
})();




/* KPWS_ADVANCE_VISIBILITY_FIX_V24_PATCH */

(function () {
    if (typeof KPWSPharmacyBillingPOS === "undefined") {
        console.warn("KPWSPharmacyBillingPOS not found. Advance visibility patch skipped.");
        return;
    }

    function injectAdvanceVisibilityCSS() {
        if (document.getElementById("kpws-advance-visibility-v24-css")) return;

        const css = `
            #kpws-customer-advance-box.kpws-advance-hidden {
                display: none !important;
            }

            #kpws-customer-advance-box {
                display: block;
            }
        `;

        const style = document.createElement("style");
        style.id = "kpws-advance-visibility-v24-css";
        style.innerHTML = css;
        document.head.appendChild(style);
    }

    injectAdvanceVisibilityCSS();

    KPWSPharmacyBillingPOS.prototype.hideCustomerAdvanceBox = function () {
        const box = this.page.main.find("#kpws-customer-advance-box");

        if (!box.length) return;

        box.addClass("kpws-advance-hidden");

        this.customerAdvanceInfo = null;

        this.page.main.find("#kpws-use-advance").prop("checked", false);
        this.page.main.find("#kpws-advance-amount").val("0");
        this.page.main.find("#kpws-advance-status").removeClass("ok warn").text("");
        this.page.main.find("#kpws-advance-type").text("-");
        this.page.main.find("#kpws-advance-available").text("0.00");
    };

    KPWSPharmacyBillingPOS.prototype.showCustomerAdvanceBox = function () {
        const box = this.page.main.find("#kpws-customer-advance-box");

        if (!box.length) return;

        box.removeClass("kpws-advance-hidden");
    };

    const oldInjectAdvanceUIV24 = KPWSPharmacyBillingPOS.prototype.injectAdvanceUI;

    KPWSPharmacyBillingPOS.prototype.injectAdvanceUI = function () {
        if (oldInjectAdvanceUIV24) {
            oldInjectAdvanceUIV24.apply(this, arguments);
        }

        injectAdvanceVisibilityCSS();

        // Default state: hidden. It will show only if customer is marked advance customer.
        this.page.main.find("#kpws-customer-advance-box").addClass("kpws-advance-hidden");
    };

    KPWSPharmacyBillingPOS.prototype.refreshCustomerAdvanceInfo = async function () {
        this.injectAdvanceUI();

        const customer = this.currentBillToCustomer ? this.currentBillToCustomer() : "";

        if (!customer) {
            this.hideCustomerAdvanceBox();
            this.refreshPaymentPlan();
            return;
        }

        try {
            const r = await this.call("get_customer_advance_info", { customer });
            const info = r.message || {};

            const enabled = Number(info.enabled || 0);
            const isAdvanceCustomer = Number(info.is_advance_customer || 0);
            const available = Number(info.available_advance || 0);

            // Main rule:
            // Do not show Customer Advance section unless Customer is marked Is Advance Customer.
            if (!enabled || !isAdvanceCustomer) {
                this.hideCustomerAdvanceBox();
                this.refreshPaymentPlan();
                return;
            }

            this.customerAdvanceInfo = info;
            this.showCustomerAdvanceBox();

            this.page.main.find("#kpws-advance-type").text(info.advance_type || "Advance Customer");
            this.page.main.find("#kpws-advance-available").text(available.toFixed(2));

            if (available > 0) {
                this.page.main.find("#kpws-advance-status").removeClass("warn").addClass("ok").text("Available");

                const total = this.total ? this.total() : 0;
                const allocation = Math.min(total, available);

                this.page.main.find("#kpws-use-advance").prop("checked", allocation > 0);
                this.page.main.find("#kpws-advance-amount").val(allocation.toFixed(2));
                this.page.main.find("#kpws-advance-note").text("Advance balance will be allocated against this invoice first.");
            } else {
                this.page.main.find("#kpws-advance-status").removeClass("ok").addClass("warn").text("No Balance");
                this.page.main.find("#kpws-use-advance").prop("checked", false);
                this.page.main.find("#kpws-advance-amount").val("0");
                this.page.main.find("#kpws-advance-note").text("Customer is marked as advance customer, but no unallocated advance balance is available.");
            }

            this.refreshPaymentPlan();

        } catch (e) {
            this.hideCustomerAdvanceBox();
            this.refreshPaymentPlan();
        }
    };

    KPWSPharmacyBillingPOS.prototype.getAdvanceAllocationAmount = function () {
        const box = this.page.main.find("#kpws-customer-advance-box");

        if (!box.length || box.hasClass("kpws-advance-hidden")) return 0;

        if (!this.customerAdvanceInfo) return 0;

        const isAdvanceCustomer = Number(this.customerAdvanceInfo.is_advance_customer || 0);
        const enabled = Number(this.customerAdvanceInfo.enabled || 0);

        if (!enabled || !isAdvanceCustomer) return 0;

        if (!this.page.main.find("#kpws-use-advance").is(":checked")) return 0;

        const available = Number(this.customerAdvanceInfo.available_advance || 0);
        const total = this.total ? this.total() : 0;
        const requested = Number(this.page.main.find("#kpws-advance-amount").val() || 0);

        return Math.max(0, Math.min(available, total, requested));
    };

    const oldRenderBillingAdvanceVisibilityV24 = KPWSPharmacyBillingPOS.prototype.renderBilling;

    KPWSPharmacyBillingPOS.prototype.renderBilling = function () {
        oldRenderBillingAdvanceVisibilityV24.apply(this, arguments);

        this.injectAdvanceUI();
        this.hideCustomerAdvanceBox();

        // Refresh if Bill To Customer is manually changed.
        const billToArea = this.page.main.find("#kpws-billto-control");

        billToArea.find("input").off("change.kpwsadvance blur.kpwsadvance").on("change.kpwsadvance blur.kpwsadvance", () => {
            setTimeout(() => {
                this.refreshCustomerAdvanceInfo();
            }, 250);
        });

        setTimeout(() => {
            this.refreshCustomerAdvanceInfo();
        }, 500);
    };

    const oldUpdateCartAdvanceVisibilityV24 = KPWSPharmacyBillingPOS.prototype.updateCart;

    KPWSPharmacyBillingPOS.prototype.updateCart = function () {
        oldUpdateCartAdvanceVisibilityV24.apply(this, arguments);

        const box = this.page.main.find("#kpws-customer-advance-box");

        if (!box.length || box.hasClass("kpws-advance-hidden")) {
            return;
        }

        if (this.customerAdvanceInfo) {
            const available = Number(this.customerAdvanceInfo.available_advance || 0);
            const total = this.total ? this.total() : 0;

            if (available > 0 && this.page.main.find("#kpws-use-advance").is(":checked")) {
                const allocation = Math.min(available, total);
                this.page.main.find("#kpws-advance-amount").val(allocation.toFixed(2));
            }
        }
    };
})();




/* KPWS_FULL_ADVANCE_ZERO_PAYABLE_FIX_V25_PATCH */

(function () {
    if (typeof KPWSPharmacyBillingPOS === "undefined") {
        console.warn("KPWSPharmacyBillingPOS not found. Full advance UI patch skipped.");
        return;
    }

    const oldRenderPaymentPlanV25 = KPWSPharmacyBillingPOS.prototype.renderPaymentPlan;

    KPWSPharmacyBillingPOS.prototype.renderPaymentPlan = function () {
        const plan = this.paymentPlan || {};
        const rows = plan.rows || [];
        const warnings = plan.warnings || [];

        const invoiceTotal = Number(plan.invoice_total || plan.total || 0);
        const advance = Number(plan.customer_advance_allocated || 0);
        const covered = Number(plan.covered_amount || 0);
        const share = Number(plan.patient_share || 0);

        this.page.main.find("#kpws-final-total").text(invoiceTotal.toFixed(2));
        this.page.main.find("#kpws-covered-amount").text(covered.toFixed(2));
        this.page.main.find("#kpws-patient-share").text(share.toFixed(2));
        this.page.main.find("#kpws-payable-now").text(share.toFixed(2));

        let html = "";

        if (warnings.length) {
            html += warnings.map(w => `<div class="kpws-pos-warning">${this.esc(w)}</div>`).join("");
        }

        const allRows = [];

        if (advance > 0) {
            allRows.push({
                label: "Customer Advance",
                mode_of_payment: "ERPNext Advance Allocation",
                amount: advance
            });
        }

        rows.forEach(row => allRows.push(row));

        if (!allRows.length) {
            html += `<div class="kpws-pos-warning">Add items to calculate payment split.</div>`;
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
                        ${allRows.map(row => `
                            <tr>
                                <td>${this.esc(row.label || row.role || "")}</td>
                                <td>${this.esc(row.mode_of_payment || "Advance")}</td>
                                <td style="text-align:right;">${Number(row.amount || 0).toFixed(2)}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            `;
        }

        if (invoiceTotal > 0 && advance >= invoiceTotal) {
            html += `
                <div class="kpws-pos-success" style="margin-top:10px;">
                    Full invoice amount is covered by customer advance. No cash/card payment is required.
                </div>
            `;
        }

        this.page.main.find("#kpws-payment-plan").html(html);
    };
})();




/* KPWS_CORE_ADVANCE_BALANCE_V26_PATCH */

(function () {
    if (typeof KPWSPharmacyBillingPOS === "undefined") {
        console.warn("KPWSPharmacyBillingPOS not found. Core advance balance UI patch skipped.");
        return;
    }

    function injectCoreAdvanceCSS() {
        if (document.getElementById("kpws-core-advance-v26-css")) return;

        const css = `
            #kpws-customer-advance-box .kpws-advance-grid {
                grid-template-columns: repeat(3, minmax(0, 1fr));
            }

            #kpws-advance-available,
            #kpws-advance-allocated-already,
            #kpws-advance-amount {
                color: #000000 !important;
                font-weight: 950 !important;
            }

            .kpws-advance-core-note {
                background: #eff6ff;
                border: 1px solid #bfdbfe;
                color: #1e3a8a !important;
                border-radius: 12px;
                padding: 8px 10px;
                margin-top: 8px;
                font-size: 12px;
                font-weight: 850;
            }
        `;

        const style = document.createElement("style");
        style.id = "kpws-core-advance-v26-css";
        style.innerHTML = css;
        document.head.appendChild(style);
    }

    injectCoreAdvanceCSS();

    const oldInjectAdvanceUIV26 = KPWSPharmacyBillingPOS.prototype.injectAdvanceUI;

    KPWSPharmacyBillingPOS.prototype.injectAdvanceUI = function () {
        if (oldInjectAdvanceUIV26) {
            oldInjectAdvanceUIV26.apply(this, arguments);
        }

        injectCoreAdvanceCSS();

        const box = this.page.main.find("#kpws-customer-advance-box");
        if (!box.length) return;

        box.find(".kpws-advance-stat label").each(function () {
            const txt = ($(this).text() || "").trim();

            if (txt === "Available Balance") {
                $(this).text("Remaining Balance");
            }

            if (txt === "Allocate Amount") {
                $(this).text("Allocate This Invoice");
            }
        });

        if (!box.find("#kpws-advance-allocated-already").length) {
            const remainingStat = box.find("#kpws-advance-available").closest(".kpws-advance-stat");

            remainingStat.after(`
                <div class="kpws-advance-stat">
                    <label>Already Allocated</label>
                    <div id="kpws-advance-allocated-already">0.00</div>
                </div>
            `);
        }

        if (!box.find(".kpws-advance-core-note").length) {
            box.append(`
                <div class="kpws-advance-core-note">
                    Balance is calculated from ERPNext Payment Entry, Payment Entry Reference, and Sales Invoice Advance allocations.
                </div>
            `);
        }
    };

    KPWSPharmacyBillingPOS.prototype.refreshCustomerAdvanceInfo = async function () {
        this.injectAdvanceUI();

        const customer = this.currentBillToCustomer ? this.currentBillToCustomer() : "";

        if (!customer) {
            this.hideCustomerAdvanceBox();
            this.refreshPaymentPlan();
            return;
        }

        try {
            const r = await this.call("get_customer_advance_info", { customer });
            const info = r.message || {};

            const enabled = Number(info.enabled || 0);
            const isAdvanceCustomer = Number(info.is_advance_customer || 0);
            const remaining = Number(info.remaining_balance || info.available_advance || 0);
            const allocatedAlready = Number(info.allocated_already || 0);

            if (!enabled || !isAdvanceCustomer) {
                this.hideCustomerAdvanceBox();
                this.refreshPaymentPlan();
                return;
            }

            this.customerAdvanceInfo = info;
            this.showCustomerAdvanceBox();

            this.page.main.find("#kpws-advance-type").text(info.advance_type || "Advance Customer");
            this.page.main.find("#kpws-advance-available").text(remaining.toFixed(2));
            this.page.main.find("#kpws-advance-allocated-already").text(allocatedAlready.toFixed(2));

            if (remaining > 0) {
                this.page.main.find("#kpws-advance-status").removeClass("warn").addClass("ok").text("Remaining");

                const total = this.total ? this.total() : 0;
                const allocation = Math.min(total, remaining);

                this.page.main.find("#kpws-use-advance").prop("checked", allocation > 0);
                this.page.main.find("#kpws-advance-amount").val(allocation.toFixed(2));
                this.page.main.find("#kpws-advance-note").text("Only remaining ERPNext advance balance can be allocated.");
            } else {
                this.page.main.find("#kpws-advance-status").removeClass("ok").addClass("warn").text("Fully Used");
                this.page.main.find("#kpws-use-advance").prop("checked", false);
                this.page.main.find("#kpws-advance-amount").val("0");
                this.page.main.find("#kpws-advance-note").text("This customer is marked advance customer, but all advance has already been allocated.");
            }

            this.refreshPaymentPlan();

        } catch (e) {
            this.hideCustomerAdvanceBox();
            this.refreshPaymentPlan();
        }
    };

    KPWSPharmacyBillingPOS.prototype.getAdvanceAllocationAmount = function () {
        const box = this.page.main.find("#kpws-customer-advance-box");

        if (!box.length || box.hasClass("kpws-advance-hidden")) return 0;
        if (!this.customerAdvanceInfo) return 0;

        const isAdvanceCustomer = Number(this.customerAdvanceInfo.is_advance_customer || 0);
        const enabled = Number(this.customerAdvanceInfo.enabled || 0);

        if (!enabled || !isAdvanceCustomer) return 0;

        if (!this.page.main.find("#kpws-use-advance").is(":checked")) return 0;

        const remaining = Number(this.customerAdvanceInfo.remaining_balance || this.customerAdvanceInfo.available_advance || 0);
        const total = this.total ? this.total() : 0;
        const requested = Number(this.page.main.find("#kpws-advance-amount").val() || 0);

        return Math.max(0, Math.min(remaining, total, requested));
    };
})();


/* KPWS_WELFARE_PANEL_ACCOUNTING_V27_UI_PATCH */
(function () {
    if (typeof KPWSPharmacyBillingPOS === "undefined") {
        console.warn("KPWSPharmacyBillingPOS not found. Welfare accounting settings patch skipped.");
        return;
    }

    const EXTRA_FIELDS = [
        "enable_welfare_auto_journal",
        "enable_welfare_patient_share_payment_entry",
        "welfare_receivable_account",
        "zakat_disbursement_account",
        "donation_disbursement_account",
        "panel_billing_mode",
        "panel_receivable_account",
        "cash_income_account",
        "panel_income_account",
        "pharmacy_cogs_account"
    ];

    const oldRenderSettings = KPWSPharmacyBillingPOS.prototype.renderSettings;

    KPWSPharmacyBillingPOS.prototype.renderSettings = function () {
        if (oldRenderSettings) oldRenderSettings.apply(this, arguments);
        if (this.canShowSettings && !this.canShowSettings()) return;
        setTimeout(() => this.renderAccountingAutomationSettings(), 50);
    };

    KPWSPharmacyBillingPOS.prototype.renderAccountingAutomationSettings = function () {
        const root = this.page.main.find("#kpws-settings-tab");
        if (!root.length || root.find("#kpws-accounting-settings-v27").length) return;

        const html = `
            <div class="kpws-settings-section full" id="kpws-accounting-settings-v27">
                <div class="kpws-settings-section-title">
                    <h3>Accounting Automation</h3>
                    <span>Receivable, Zakat/Donation disbursement, Panel receivable and income mapping</span>
                </div>
                <div class="kpws-settings-controls-grid" style="margin-bottom:14px;">
                    ${this.checkboxHTML("enable_welfare_auto_journal", "Auto Post Zakat/Donation Journal Entry")}
                    ${this.checkboxHTML("enable_welfare_patient_share_payment_entry", "Auto Post Patient Share Payment Entry")}
                </div>
                <div class="kpws-settings-fields">
                    <div class="kpws-settings-field" id="kpws-setting-welfare-receivable-account"></div>
                    <div class="kpws-settings-field" id="kpws-setting-zakat-disbursement-account"></div>
                    <div class="kpws-settings-field" id="kpws-setting-donation-disbursement-account"></div>
                    <div class="kpws-settings-field" id="kpws-setting-panel-billing-mode"></div>
                    <div class="kpws-settings-field" id="kpws-setting-panel-receivable-account"></div>
                    <div class="kpws-settings-field" id="kpws-setting-cash-income-account"></div>
                    <div class="kpws-settings-field" id="kpws-setting-panel-income-account"></div>
                    <div class="kpws-settings-field" id="kpws-setting-pharmacy-cogs-account"></div>
                </div>
                <div class="kpws-settings-note">
                    Zakat and Donation are no longer used as Mode of Payment. Welfare invoices stay receivable first, then the system posts an automatic Journal Entry: Dr Zakat/Donation Disbursement, Cr Welfare Receivable.
                </div>
            </div>
        `;

        const controlsSection = root.find(".kpws-settings-section.full").last();
        if (controlsSection.length) {
            controlsSection.before(html);
        } else {
            root.find(".kpws-settings-actions").before(html);
        }

        this.makeAccountingSettingsControls();
        if (this.refreshSettingsCheckboxes) this.refreshSettingsCheckboxes();
    };

    KPWSPharmacyBillingPOS.prototype.makeAccountingSettingsControls = function () {
        const make = (id, label, fieldtype, options, fieldname) => {
            const target = this.page.main.find(id).get(0);
            if (!target || this[`${fieldname}Control`]) return;

            const control = frappe.ui.form.make_control({
                parent: target,
                df: {
                    label,
                    fieldtype,
                    options,
                    fieldname,
                    get_query: fieldtype === "Link" && options === "Account"
                        ? () => {
                            const company = this.companyControl ? this.companyControl.get_value() : this.settings.company;
                            return company ? { filters: { company: company, is_group: 0 } } : { filters: { is_group: 0 } };
                        }
                        : undefined
                },
                render_input: true
            });

            control.set_value((this.settings && this.settings[fieldname]) || "");
            this[`${fieldname}Control`] = control;
        };

        make("#kpws-setting-welfare-receivable-account", "Welfare Receivable Account", "Link", "Account", "welfare_receivable_account");
        make("#kpws-setting-zakat-disbursement-account", "Zakat Disbursement Account", "Link", "Account", "zakat_disbursement_account");
        make("#kpws-setting-donation-disbursement-account", "Donation Disbursement Account", "Link", "Account", "donation_disbursement_account");
        make("#kpws-setting-panel-billing-mode", "Panel Billing Mode", "Select", "Receivable\nPOS Payment", "panel_billing_mode");
        make("#kpws-setting-panel-receivable-account", "Panel Receivable Account", "Link", "Account", "panel_receivable_account");
        make("#kpws-setting-cash-income-account", "Cash/Welfare Income Account", "Link", "Account", "cash_income_account");
        make("#kpws-setting-panel-income-account", "Panel Income Account", "Link", "Account", "panel_income_account");
        make("#kpws-setting-pharmacy-cogs-account", "Pharmacy COGS / Expense Account", "Link", "Account", "pharmacy_cogs_account");
    };

    KPWSPharmacyBillingPOS.prototype.refreshSettingsCheckboxes = function () {
        const self = this;
        this.page.main.find("[data-setting-check]").each(function () {
            const field = $(this).data("setting-check");
            const checked = Number((self.settings && self.settings[field]) || 0);
            $(this).prop("checked", !!checked);
            $(this).closest(".kpws-settings-check").toggleClass("is-checked", !!checked);
        });
    };

    KPWSPharmacyBillingPOS.prototype.saveSettings = async function () {
        if (this.canShowSettings && !this.canShowSettings()) {
            frappe.msgprint("Only Administrator user can save Pharmacy POS Settings.");
            return;
        }

        const get = (field) => {
            const control = this[`${field}Control`];
            return control ? control.get_value() : ((this.settings && this.settings[field]) || "");
        };

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
            panel_print_format: get("panel_print_format"),
            cash_return_print_format: get("cash_return_print_format"),
            welfare_return_print_format: get("welfare_return_print_format"),
            panel_return_print_format: get("panel_return_print_format"),
            walkin_return_print_format: get("walkin_return_print_format"),

            welfare_receivable_account: get("welfare_receivable_account"),
            zakat_disbursement_account: get("zakat_disbursement_account"),
            donation_disbursement_account: get("donation_disbursement_account"),
            panel_billing_mode: get("panel_billing_mode"),
            panel_receivable_account: get("panel_receivable_account"),
            cash_income_account: get("cash_income_account"),
            panel_income_account: get("panel_income_account"),
            pharmacy_cogs_account: get("pharmacy_cogs_account")
        };

        this.page.main.find("[data-setting-check]").each(function () {
            values[$(this).data("setting-check")] = $(this).is(":checked") ? 1 : 0;
        });

        const r = await this.call("save_settings", { values });
        this.settings = r.message || {};
        frappe.show_alert({ message: "Settings saved.", indicator: "green" }, 8);
        this.renderSettings();
    };
})();

// KPWS_BILLING_MODE_V91: backend-decided Bill To customer and four-mode display
(function () {
    if (typeof KPWSPharmacyBillingPOS === "undefined") {
        console.warn("KPWS_BILLING_MODE_V91 skipped: KPWSPharmacyBillingPOS not found");
        return;
    }

    function lockBillTo(pos) {
        if (!pos || !pos.billToControl) return;
        try {
            if (pos.patientContext && pos.patientContext.bill_to_customer) {
                pos.billToControl.set_value(pos.patientContext.bill_to_customer);
            }
            if (pos.billToControl.$input) {
                pos.billToControl.$input.prop("disabled", true).attr("title", "Auto-decided by KPWS billing policy");
            }
            if (pos.billToControl.$wrapper && !pos.billToControl.$wrapper.find(".kpws-v91-billto-note").length) {
                pos.billToControl.$wrapper.append('<div class="kpws-v91-billto-note" style="font-size:11px;color:#64748b;margin-top:4px;">Auto-decided by Patient Type / Welfare Approval / Panel assignment.</div>');
            }
        } catch (e) {}
    }

    const oldLoadPatientV91 = KPWSPharmacyBillingPOS.prototype.loadPatient;
    KPWSPharmacyBillingPOS.prototype.loadPatient = async function (patient) {
        const out = await oldLoadPatientV91.apply(this, arguments);
        try {
            const ctx = this.patientContext || {};
            const reg = ctx.registration || {};
            this.page.main.find("#kpws-billing-type").text(ctx.billing_type_final || ctx.group || "-");
            this.page.main.find("#kpws-purpose").text(ctx.funding_source || reg.purpose || "-");
            this.page.main.find("#kpws-percentage").text(((reg.percentage || ctx.percentage || 0)) + "%");
            if (ctx.bill_to_customer && this.billToControl) {
                this.billToControl.set_value(ctx.bill_to_customer);
            }
            lockBillTo(this);
        } catch (e) {}
        return out;
    };

    const oldRenderBillingV91 = KPWSPharmacyBillingPOS.prototype.renderBilling;
    KPWSPharmacyBillingPOS.prototype.renderBilling = function () {
        const out = oldRenderBillingV91.apply(this, arguments);
        lockBillTo(this);
        return out;
    };

    const oldBuildPayloadV91 = KPWSPharmacyBillingPOS.prototype.buildInvoicePayload;
    KPWSPharmacyBillingPOS.prototype.buildInvoicePayload = function (submit) {
        const payload = oldBuildPayloadV91 ? oldBuildPayloadV91.apply(this, arguments) : { submit: submit ? 1 : 0, items: [] };
        if (this.patientContext && !payload.is_walkin) {
            payload.bill_to_customer = this.patientContext.bill_to_customer || payload.bill_to_customer || "";
            payload.price_list = this.patientContext.price_list || payload.price_list || "";
        }
        return payload;
    };
})();

// KPWS_PANEL_PATIENT_GUARD_V95
// Prevent stale patientContext / stale Bill To Customer from creating Panel invoices for the previous patient.
(function () {
    if (typeof KPWSPharmacyBillingPOS === "undefined") {
        console.warn("KPWS_PANEL_PATIENT_GUARD_V95 skipped: KPWSPharmacyBillingPOS not found");
        return;
    }

    function selectedPatient(pos) {
        try {
            return (pos.patientControl && pos.patientControl.get_value && pos.patientControl.get_value()) || "";
        } catch (e) {
            return "";
        }
    }

    function isWalkin(pos) {
        try { return !!(pos.isWalkin && pos.isWalkin()); } catch (e) { return false; }
    }

    function clearPatientDisplay(pos, text) {
        try {
            pos.patientContext = null;
            pos.paymentPlan = null;
            pos.lastInvoice = null;
            pos.page.main.find("#kpws-mr").text(text || "-");
            pos.page.main.find("#kpws-patient-name").text(text || "-");
            pos.page.main.find("#kpws-billing-type").text("-");
            pos.page.main.find("#kpws-price-list").text("-");
            pos.page.main.find("#kpws-purpose").text("-");
            pos.page.main.find("#kpws-percentage").text("0%");
            pos.page.main.find("#kpws-patient-status").html("");
            if (pos.billToControl && pos.billToControl.set_value) pos.billToControl.set_value("");
            if (pos.updateCart) pos.updateCart();
        } catch (e) {}
    }

    function forceBillTo(pos) {
        try {
            const ctx = pos.patientContext || {};
            if (ctx.bill_to_customer && pos.billToControl && pos.billToControl.set_value) {
                pos.billToControl.set_value(ctx.bill_to_customer);
            }
            if (pos.billToControl && pos.billToControl.$input) {
                pos.billToControl.$input.prop("disabled", true).attr("title", "Auto-decided by KPWS billing policy");
            }
            if (pos.billToControl && pos.billToControl.$wrapper && !pos.billToControl.$wrapper.find(".kpws-v95-billto-note").length) {
                pos.billToControl.$wrapper.append('<div class="kpws-v95-billto-note" style="font-size:11px;color:#64748b;margin-top:4px;">Auto-decided by selected Patient / Welfare Approval / Panel assignment.</div>');
            }
        } catch (e) {}
    }

    function validateCurrentPatient(pos, showMessage) {
        if (isWalkin(pos)) return true;
        const selected = selectedPatient(pos);
        const ctx = pos.patientContext || {};

        if (!selected) {
            if (showMessage) frappe.msgprint("Please select Patient first.");
            return false;
        }

        if (!ctx.patient || ctx.patient !== selected) {
            if (showMessage) {
                frappe.msgprint("Patient details are still loading or stale. Please wait one second, then click Submit again.");
            }
            return false;
        }

        if (ctx.bill_to_customer && pos.billToControl && pos.billToControl.get_value && pos.billToControl.get_value() !== ctx.bill_to_customer) {
            forceBillTo(pos);
        }

        return true;
    }

    KPWSPharmacyBillingPOS.prototype.loadPatient = async function (patient) {
        patient = patient || selectedPatient(this);
        if (!patient) {
            clearPatientDisplay(this);
            return;
        }

        this._kpws_v95_patient_load_seq = (this._kpws_v95_patient_load_seq || 0) + 1;
        const seq = this._kpws_v95_patient_load_seq;
        this._kpws_v95_loading_patient = patient;

        clearPatientDisplay(this, "Loading...");

        try {
            const r = await this.call("get_patient_context", { patient: patient });

            // If user changed patient while request was in progress, ignore this stale response.
            if (seq !== this._kpws_v95_patient_load_seq || selectedPatient(this) !== patient) {
                return;
            }

            const ctx = r.message || {};
            if (!ctx.patient || ctx.patient !== patient) {
                frappe.msgprint("Loaded patient context does not match selected patient. Please refresh and try again.");
                clearPatientDisplay(this);
                return;
            }

            this.patientContext = ctx;
            this.cart = [];
            this.paymentPlan = null;
            this.lastInvoice = null;

            this.page.main.find("#kpws-mr").text(ctx.mr_number || "-");
            this.page.main.find("#kpws-patient-name").text(ctx.patient_name || "-");
            this.page.main.find("#kpws-billing-type").text(ctx.billing_type_final || ctx.group || "-");
            this.page.main.find("#kpws-price-list").text(ctx.price_list || "-");

            const reg = ctx.registration || {};
            this.page.main.find("#kpws-purpose").text(ctx.funding_source || reg.purpose || "-");
            this.page.main.find("#kpws-percentage").text(((reg.percentage || ctx.percentage || 0)) + "%");

            forceBillTo(this);
            if (this.renderPatientStatus) this.renderPatientStatus();
            if (this.updateCart) this.updateCart();
            if (this.refreshPaymentPlan) this.refreshPaymentPlan();
            if (this.refreshCustomerAdvanceInfo) this.refreshCustomerAdvanceInfo();
        } catch (e) {
            if (seq === this._kpws_v95_patient_load_seq) {
                clearPatientDisplay(this);
                frappe.msgprint("Unable to fetch patient context.");
            }
        } finally {
            if (seq === this._kpws_v95_patient_load_seq) {
                this._kpws_v95_loading_patient = null;
            }
        }
    };

    KPWSPharmacyBillingPOS.prototype.buildInvoicePayload = function (submit) {
        const walkin = isWalkin(this);
        const ctx = this.patientContext || {};
        const selected = walkin ? "" : selectedPatient(this);
        const useAdvance = this.page.main.find("#kpws-use-advance").is(":checked") ? 1 : 0;
        const advanceAmount = this.getAdvanceAllocationAmount ? this.getAdvanceAllocationAmount() : 0;

        return {
            is_walkin: walkin ? 1 : 0,
            walkin_name: this.getWalkinName ? this.getWalkinName() : "",
            walkin_mr_number: this.getWalkinMR ? this.getWalkinMR() : "",
            patient: selected,
            selected_patient: selected,
            bill_to_customer: walkin ? (ctx.bill_to_customer || "") : (ctx.bill_to_customer || ""),
            price_list: ctx.price_list || "",
            card_amount: Number(this.page.main.find("#kpws-card-amount").val() || 0),
            submit: submit ? 1 : 0,
            use_customer_advance: useAdvance,
            advance_amount: advanceAmount,
            items: (this.cart || []).map(row => ({
                item_code: row.item_code,
                item_name: row.item_name,
                qty: row.qty,
                rate: row.rate,
                available_qty: row.available_qty
            }))
        };
    };

    KPWSPharmacyBillingPOS.prototype.createInvoice = async function (submit) {
        if (!this.patientContext && !isWalkin(this)) {
            const selected = selectedPatient(this);
            if (selected) {
                await this.loadPatient(selected);
            }
        }

        if (!isWalkin(this) && !validateCurrentPatient(this, true)) {
            return;
        }

        if (isWalkin(this)) {
            if (!this.getWalkinName || !this.getWalkinName()) {
                frappe.msgprint("Please enter Walk-in Patient Name.");
                return;
            }
            if (!this.getWalkinMR || !this.getWalkinMR()) {
                frappe.msgprint("Please enter Walk-in MR Number.");
                return;
            }
        }

        if (!this.cart || !this.cart.length) {
            frappe.msgprint("Please add at least one item.");
            return;
        }

        forceBillTo(this);
        const payload = this.buildInvoicePayload(submit);

        // Last local safety check before sending to server.
        if (!payload.is_walkin && payload.patient !== selectedPatient(this)) {
            frappe.msgprint("Selected patient changed before submit. Please submit again.");
            return;
        }

        frappe.dom.freeze(submit ? "Submitting Sales Invoice..." : "Creating Sales Invoice...");

        try {
            const r = await this.call("create_invoice", { payload: JSON.stringify(payload) });
            const data = r.message || {};

            if (this.currentParkedInvoice && data.name) {
                await this.call("mark_parked_invoice_completed", {
                    name: this.currentParkedInvoice,
                    invoice: data.name
                });
            }

            frappe.dom.unfreeze();
            this.lastInvoice = data;

            frappe.show_alert({
                message: data.message || "Sales Invoice created successfully.",
                indicator: "green"
            }, 8);

            if (this.renderLastInvoice) this.renderLastInvoice(data);
            if (submit && this.openPrint) this.openPrint(data);
        } catch (e) {
            frappe.dom.unfreeze();
        }
    };

    const oldRenderBillingV95 = KPWSPharmacyBillingPOS.prototype.renderBilling;
    KPWSPharmacyBillingPOS.prototype.renderBilling = function () {
        const out = oldRenderBillingV95 ? oldRenderBillingV95.apply(this, arguments) : undefined;
        forceBillTo(this);
        return out;
    };
})();

// KPWS_PANEL_PATIENT_GUARD_V96
// Final browser-side patient lock for Pharmacy Billing. Server still enforces independently.
(function () {
    if (typeof KPWSPharmacyBillingPOS === "undefined") {
        console.warn("KPWS_PANEL_PATIENT_GUARD_V96 skipped: KPWSPharmacyBillingPOS not found");
        return;
    }

    function selectedPatient(pos) {
        try { return (pos.patientControl && pos.patientControl.get_value && pos.patientControl.get_value()) || ""; }
        catch (e) { return ""; }
    }

    function isWalkin(pos) {
        try { return !!(pos.isWalkin && pos.isWalkin()); } catch (e) { return false; }
    }

    function clearPatientArea(pos, label) {
        try {
            pos.patientContext = null;
            pos.paymentPlan = null;
            pos.lastInvoice = null;
            pos.page.main.find("#kpws-mr").text(label || "-");
            pos.page.main.find("#kpws-patient-name").text(label || "-");
            pos.page.main.find("#kpws-billing-type").text("-");
            pos.page.main.find("#kpws-price-list").text("-");
            pos.page.main.find("#kpws-purpose").text("-");
            pos.page.main.find("#kpws-percentage").text("0%");
            pos.page.main.find("#kpws-patient-status").html("");
            if (pos.billToControl && pos.billToControl.set_value) pos.billToControl.set_value("");
        } catch(e) {}
    }

    function lockBillTo(pos) {
        try {
            const ctx = pos.patientContext || {};
            if (ctx.bill_to_customer && pos.billToControl && pos.billToControl.set_value) {
                pos.billToControl.set_value(ctx.bill_to_customer);
            }
            if (pos.billToControl && pos.billToControl.$input) {
                pos.billToControl.$input.prop("disabled", true).attr("title", "Auto-decided by KPWS backend billing policy");
            }
        } catch(e) {}
    }

    KPWSPharmacyBillingPOS.prototype.loadPatient = async function(patient) {
        patient = patient || selectedPatient(this);
        if (!patient) {
            clearPatientArea(this);
            return;
        }

        this._kpws_v96_load_seq = (this._kpws_v96_load_seq || 0) + 1;
        const seq = this._kpws_v96_load_seq;
        this._kpws_v96_selected_patient = patient;
        clearPatientArea(this, "Loading...");

        try {
            const r = await this.call("get_patient_context", { patient: patient });
            if (seq !== this._kpws_v96_load_seq || selectedPatient(this) !== patient) {
                console.warn("KPWS V96 ignored stale patient context", {requested: patient, selected: selectedPatient(this)});
                return;
            }
            const ctx = r.message || {};
            if (!ctx.patient || ctx.patient !== patient) {
                frappe.msgprint("Patient context mismatch. Please reselect Patient and try again.");
                clearPatientArea(this);
                return;
            }
            this.patientContext = ctx;
            this.cart = [];
            this.paymentPlan = null;
            this.lastInvoice = null;

            const reg = ctx.registration || {};
            this.page.main.find("#kpws-mr").text(ctx.mr_number || "-");
            this.page.main.find("#kpws-patient-name").text(ctx.patient_name || "-");
            this.page.main.find("#kpws-billing-type").text(ctx.billing_type_final || ctx.group || "-");
            this.page.main.find("#kpws-price-list").text(ctx.price_list || "-");
            this.page.main.find("#kpws-purpose").text(ctx.funding_source || reg.purpose || "-");
            this.page.main.find("#kpws-percentage").text(((ctx.percentage || reg.percentage || 0)) + "%");

            lockBillTo(this);
            if (this.renderPatientStatus) this.renderPatientStatus();
            if (this.updateCart) this.updateCart();
            if (this.refreshPaymentPlan) this.refreshPaymentPlan();
            if (this.refreshCustomerAdvanceInfo) this.refreshCustomerAdvanceInfo();
        } catch (e) {
            if (seq === this._kpws_v96_load_seq) {
                clearPatientArea(this);
                frappe.msgprint("Unable to fetch selected patient context. Please reselect Patient.");
            }
        }
    };

    KPWSPharmacyBillingPOS.prototype.buildInvoicePayload = function(submit) {
        const walkin = isWalkin(this);
        const ctx = this.patientContext || {};
        const selected = walkin ? "" : selectedPatient(this);
        return {
            is_walkin: walkin ? 1 : 0,
            walkin_name: this.getWalkinName ? this.getWalkinName() : "",
            walkin_mr_number: this.getWalkinMR ? this.getWalkinMR() : "",
            patient: selected,
            selected_patient: selected,
            ui_patient: selected,
            bill_to_customer: ctx.bill_to_customer || "",
            price_list: ctx.price_list || "",
            card_amount: Number(this.page.main.find("#kpws-card-amount").val() || 0),
            submit: submit ? 1 : 0,
            use_customer_advance: this.page.main.find("#kpws-use-advance").is(":checked") ? 1 : 0,
            advance_amount: this.getAdvanceAllocationAmount ? this.getAdvanceAllocationAmount() : 0,
            items: (this.cart || []).map(row => ({
                item_code: row.item_code,
                item_name: row.item_name,
                qty: row.qty,
                rate: row.rate,
                available_qty: row.available_qty
            }))
        };
    };

    KPWSPharmacyBillingPOS.prototype.createInvoice = async function(submit) {
        const walkin = isWalkin(this);
        const selected = selectedPatient(this);

        if (!walkin) {
            if (!selected) {
                frappe.msgprint("Please select Patient first.");
                return;
            }
            if (!this.patientContext || this.patientContext.patient !== selected) {
                await this.loadPatient(selected);
            }
            if (!this.patientContext || this.patientContext.patient !== selected) {
                frappe.msgprint("Selected Patient is still loading. Please wait and submit again.");
                return;
            }
        }

        if (walkin) {
            if (!this.getWalkinName || !this.getWalkinName()) { frappe.msgprint("Please enter Walk-in Patient Name."); return; }
            if (!this.getWalkinMR || !this.getWalkinMR()) { frappe.msgprint("Please enter Walk-in MR Number."); return; }
        }

        if (!this.cart || !this.cart.length) {
            frappe.msgprint("Please add at least one item.");
            return;
        }

        lockBillTo(this);
        const payload = this.buildInvoicePayload(submit);
        console.log("KPWS V96 invoice payload", payload);

        frappe.dom.freeze(submit ? "Submitting Sales Invoice..." : "Creating Sales Invoice...");
        try {
            const r = await this.call("create_invoice", { payload: JSON.stringify(payload) });
            const data = r.message || {};
            if (this.currentParkedInvoice && data.name && this.call) {
                await this.call("mark_parked_invoice_completed", { name: this.currentParkedInvoice, invoice: data.name });
            }
            frappe.dom.unfreeze();
            this.lastInvoice = data;
            frappe.show_alert({ message: data.message || "Sales Invoice created successfully.", indicator: "green" }, 8);
            if (this.renderLastInvoice) this.renderLastInvoice(data);
            if (submit && this.openPrint) this.openPrint(data);
            this.currentParkedInvoice = null;
            this.cart = [];
            this.paymentPlan = null;
            if (this.updateCart) this.updateCart();
            this.page.main.find("#kpws-search-results").html("");
            this.page.main.find("#kpws-item-search").val("");
            this.page.main.find("#kpws-card-amount").val("0");
        } catch (e) {
            frappe.dom.unfreeze();
        }
    };

    const oldRenderBillingV96 = KPWSPharmacyBillingPOS.prototype.renderBilling;
    KPWSPharmacyBillingPOS.prototype.renderBilling = function() {
        const out = oldRenderBillingV96 ? oldRenderBillingV96.apply(this, arguments) : undefined;
        lockBillTo(this);
        return out;
    };
})();

/* KPWS_ITEM_QUICK_QTY_V97_START */
(function () {
    if (typeof KPWSPharmacyBillingPOS === "undefined") {
        console.warn("KPWSPharmacyBillingPOS not found. Quick Qty V97 skipped.");
        return;
    }

    function injectQuickQtyCSS() {
        if (document.getElementById("kpws-quick-qty-v97-css")) return;
        const style = document.createElement("style");
        style.id = "kpws-quick-qty-v97-css";
        style.textContent = `
            .kpws-pos-product.kpws-v97-product {
                grid-template-columns: minmax(0, 1fr) 80px 80px 100px 135px !important;
                gap: 10px !important;
                align-items: end !important;
            }
            .kpws-v97-qty-wrap label {
                display: block;
                color: #334155;
                font-size: 11px;
                font-weight: 950;
                margin-bottom: 4px;
                text-transform: uppercase;
                letter-spacing: .02em;
            }
            .kpws-v97-result-qty {
                width: 100%;
                min-height: 40px;
                border: 1px solid #cbd5e1;
                border-radius: 12px;
                padding: 8px 10px;
                font-size: 14px;
                font-weight: 950;
                color: #000;
                background: #fff;
            }
            .kpws-v97-result-qty:focus {
                outline: 2px solid #bfdbfe;
                border-color: #2563eb;
            }
            .kpws-v97-add-btn {
                width: 100%;
                white-space: nowrap;
            }
            .kpws-v97-help {
                margin-top: 8px;
                color: #475569;
                font-size: 12px;
                font-weight: 800;
            }
            @media (max-width: 1100px) {
                .kpws-pos-product.kpws-v97-product {
                    grid-template-columns: 1fr 1fr !important;
                    align-items: stretch !important;
                }
                .kpws-v97-add-btn { width: auto; }
            }
        `;
        document.head.appendChild(style);
    }

    function safeNumber(value, fallback) {
        const n = Number(value);
        return Number.isFinite(n) ? n : fallback;
    }

    function cssEscapeValue(value) {
        if (window.CSS && CSS.escape) return CSS.escape(String(value || ""));
        return String(value || "").replace(/([ #;&,.+*~':"!^$[\]()=>|/@])/g, "\\$1");
    }

    KPWSPharmacyBillingPOS.prototype.kpwsGetSearchQtyV97 = function (itemCode) {
        const selector = `.kpws-v97-result-qty[data-item-code="${cssEscapeValue(itemCode)}"]`;
        const raw = this.page.main.find(selector).val();
        const qty = safeNumber(raw, 1);
        return qty > 0 ? qty : 1;
    };

    KPWSPharmacyBillingPOS.prototype.kpwsClearItemSearchV97 = function () {
        this.page.main.find("#kpws-item-search").val("");
        this.page.main.find("#kpws-search-results").html("");
        setTimeout(() => {
            const input = this.page.main.find("#kpws-item-search").get(0);
            if (input) input.focus();
        }, 50);
    };

    KPWSPharmacyBillingPOS.prototype.addItem = function (item, qty) {
        if (!item || item.missing_price) return;

        const itemCode = item.item_code;
        const addQty = Math.max(1, safeNumber(qty, 1));
        const availableQty = safeNumber(item.available_qty, 0);

        if (availableQty > 0 && addQty > availableQty) {
            frappe.msgprint(`Quantity cannot be greater than available stock (${availableQty}).`);
            return;
        }

        const existing = (this.cart || []).find(x => x.item_code === itemCode);

        if (existing) {
            const newQty = safeNumber(existing.qty, 0) + addQty;
            if (availableQty > 0 && newQty > availableQty) {
                frappe.msgprint(`Total cart quantity cannot be greater than available stock (${availableQty}).`);
                return;
            }
            existing.qty = newQty;
        } else {
            if (!this.cart) this.cart = [];
            this.cart.push({
                item_code: item.item_code,
                item_name: item.item_name,
                qty: addQty,
                rate: Number(item.rate || 0),
                available_qty: Number(item.available_qty || 0)
            });
        }

        this.updateCart();
        this.kpwsClearItemSearchV97();

        frappe.show_alert({
            message: `${item.item_name || item.item_code} added. Qty: ${addQty}`,
            indicator: "green"
        }, 3);
    };

    KPWSPharmacyBillingPOS.prototype.searchItems = async function () {
        injectQuickQtyCSS();

        const txt = this.page.main.find("#kpws-item-search").val();

        if (!this.patientContext) {
            frappe.show_alert({ message: "Select Patient or enable Walk-in Patient first.", indicator: "orange" }, 5);
            return;
        }

        if (this.isWalkin && this.isWalkin()) {
            if (!this.getWalkinName() || !this.getWalkinMR()) {
                frappe.show_alert({ message: "Enter Walk-in Patient Name and MR Number first.", indicator: "orange" }, 5);
                return;
            }
        }

        if (!txt || txt.length < 2) {
            this.page.main.find("#kpws-search-results").html("");
            return;
        }

        const r = await this.call("search_items", {
            txt,
            patient: (this.isWalkin && this.isWalkin()) ? "" : (this.patientContext ? this.patientContext.patient : ""),
            price_list: this.patientContext ? this.patientContext.price_list : ""
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
                <div class="kpws-pos-product kpws-v97-product">
                    <div>
                        <div class="kpws-pos-product-name">${this.esc(row.item_name || row.item_code)}</div>
                        <div class="kpws-pos-product-code">${this.esc(row.item_code)}</div>
                        ${row.missing_price ? `<div class="kpws-pos-warning">Missing price. Ask Warehouse / Accounts to update pricing.</div>` : ""}
                    </div>

                    <div class="kpws-pos-product-meta">Stock<br>${this.esc(row.available_qty)}</div>
                    <div class="kpws-pos-product-meta">Rate<br>${this.esc(row.rate || 0)}</div>

                    <div class="kpws-v97-qty-wrap">
                        <label>Qty</label>
                        <input
                            class="kpws-v97-result-qty"
                            data-item-code="${this.esc(row.item_code)}"
                            type="number"
                            min="1"
                            step="1"
                            value="1"
                            ${Number(row.available_qty || 0) > 0 ? `max="${this.esc(row.available_qty)}"` : ""}
                            ${row.missing_price ? "disabled" : ""}
                        >
                    </div>

                    <button class="kpws-pos-btn primary kpws-v97-add-btn" data-add-item-v97="${this.esc(row.item_code)}" ${row.missing_price ? "disabled" : ""}>
                        Add to Cart
                    </button>
                </div>
            `).join("")}
            <div class="kpws-v97-help">Tip: type quantity here and press Enter, or click Add to Cart. After adding, search will clear automatically.</div>
        `);

        this.page.main.find("[data-add-item-v97]").on("click", (e) => {
            const itemCode = $(e.currentTarget).data("add-item-v97");
            const item = rows.find(x => x.item_code === itemCode);
            const qty = this.kpwsGetSearchQtyV97(itemCode);
            this.addItem(item, qty);
        });

        this.page.main.find(".kpws-v97-result-qty").on("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                const itemCode = $(e.currentTarget).data("item-code");
                this.page.main.find(`[data-add-item-v97="${cssEscapeValue(itemCode)}"]`).trigger("click");
            }
        });
    };

    const oldBindBillingEventsV97 = KPWSPharmacyBillingPOS.prototype.bindBillingEvents;
    KPWSPharmacyBillingPOS.prototype.bindBillingEvents = function () {
        oldBindBillingEventsV97.apply(this, arguments);
        injectQuickQtyCSS();

        this.page.main.find("#kpws-item-search").off("keydown.kpwsQuickQtyV97").on("keydown.kpwsQuickQtyV97", (e) => {
            if (e.key === "Escape") {
                this.kpwsClearItemSearchV97();
            }
        });
    };

    console.log("KPWS Quick Quantity Add V97 loaded.");
})();
/* KPWS_ITEM_QUICK_QTY_V97_END */

/* KPWS_BILLING_UI_V98_V102_START */
(function () {
    if (typeof KPWSPharmacyBillingPOS === "undefined") {
        console.warn("KPWSPharmacyBillingPOS not found. Billing UI V98-V102 skipped.");
        return;
    }

    const PATCH_VERSION = "V98-V102";

    function n(value, fallback = 0) {
        const out = Number(value);
        return Number.isFinite(out) ? out : fallback;
    }

    function money(value) {
        return n(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function esc(value) {
        if (frappe && frappe.utils && frappe.utils.escape_html) {
            return frappe.utils.escape_html(String(value || ""));
        }
        return String(value || "").replace(/[&<>'"]/g, function (c) {
            return {"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;","\"":"&quot;"}[c];
        });
    }

    function cssEscapeValue(value) {
        if (window.CSS && CSS.escape) return CSS.escape(String(value || ""));
        return String(value || "").replace(/([ #;&,.+*~':"!^$[\]()=>|\/@])/g, "\\$1");
    }

    function injectUIStyle() {
        if (document.getElementById("kpws-billing-ui-v98-v102-css")) return;
        const style = document.createElement("style");
        style.id = "kpws-billing-ui-v98-v102-css";
        style.textContent = `
            body[data-route="kpws-pharmacy-billing"] .kpws-v98-patient-banner {
                display: grid;
                grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr) minmax(220px, .75fr);
                gap: 12px;
                padding: 14px 16px;
                margin: 0 0 14px 0;
                background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
                border: 1px solid rgba(148,163,184,.25);
                border-radius: 18px;
                color: #fff;
                box-shadow: 0 12px 26px rgba(15,23,42,.12);
            }
            body[data-route="kpws-pharmacy-billing"] .kpws-v98-banner-title {
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: .06em;
                color: #cbd5e1;
                font-weight: 900;
                margin-bottom: 6px;
            }
            body[data-route="kpws-pharmacy-billing"] .kpws-v98-banner-main {
                font-size: 19px;
                font-weight: 950;
                line-height: 1.2;
            }
            body[data-route="kpws-pharmacy-billing"] .kpws-v98-banner-sub {
                margin-top: 4px;
                font-size: 12px;
                color: #e2e8f0;
                font-weight: 750;
            }
            body[data-route="kpws-pharmacy-billing"] .kpws-v98-mode-badge {
                display: inline-flex;
                align-items: center;
                gap: 6px;
                padding: 6px 10px;
                border-radius: 999px;
                font-weight: 950;
                font-size: 12px;
                background: rgba(255,255,255,.14);
                border: 1px solid rgba(255,255,255,.18);
                color: #fff;
                margin-bottom: 8px;
            }
            body[data-route="kpws-pharmacy-billing"] .kpws-v98-mode-cash { background: rgba(22,163,74,.30); }
            body[data-route="kpws-pharmacy-billing"] .kpws-v98-mode-welfare { background: rgba(37,99,235,.32); }
            body[data-route="kpws-pharmacy-billing"] .kpws-v98-mode-panel { background: rgba(126,34,206,.35); }
            body[data-route="kpws-pharmacy-billing"] .kpws-v98-mode-welfare-panel { background: rgba(234,88,12,.36); }
            body[data-route="kpws-pharmacy-billing"] .kpws-v98-billto-display {
                background: #f8fafc;
                border: 1px solid #dbe3ef;
                border-radius: 14px;
                padding: 10px 12px;
                min-height: 42px;
                color: #0f172a;
                font-weight: 950;
            }
            body[data-route="kpws-pharmacy-billing"] .kpws-v98-auto-note {
                font-size: 11px;
                color: #64748b;
                font-weight: 800;
                margin-top: 5px;
            }
            body[data-route="kpws-pharmacy-billing"] .kpws-v99-summary {
                display: grid;
                gap: 8px;
                margin-top: 10px;
            }
            body[data-route="kpws-pharmacy-billing"] .kpws-v99-summary-line {
                display: flex;
                justify-content: space-between;
                gap: 12px;
                padding: 10px 12px;
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 14px;
                color: #111827;
                font-weight: 900;
            }
            body[data-route="kpws-pharmacy-billing"] .kpws-v99-summary-line strong { font-size: 16px; }
            body[data-route="kpws-pharmacy-billing"] .kpws-v99-summary-line.primary {
                background: #eff6ff;
                border-color: #bfdbfe;
            }
            body[data-route="kpws-pharmacy-billing"] .kpws-v99-summary-line.success {
                background: #f0fdf4;
                border-color: #bbf7d0;
            }
            body[data-route="kpws-pharmacy-billing"] .kpws-v99-summary-line.warning {
                background: #fff7ed;
                border-color: #fed7aa;
            }
            body[data-route="kpws-pharmacy-billing"] .kpws-v100-confirm-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 10px;
                margin-top: 8px;
            }
            body[data-route="kpws-pharmacy-billing"] .kpws-v100-confirm-cell {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
                padding: 10px 12px;
            }
            body[data-route="kpws-pharmacy-billing"] .kpws-v100-confirm-cell span {
                display: block;
                color: #64748b;
                font-weight: 850;
                font-size: 11px;
                text-transform: uppercase;
            }
            body[data-route="kpws-pharmacy-billing"] .kpws-v100-confirm-cell b {
                color: #0f172a;
                font-size: 14px;
            }
            body[data-route="kpws-pharmacy-billing"] .kpws-v101-keyboard-hint {
                margin-top: 8px;
                color: #475569;
                font-size: 12px;
                font-weight: 800;
            }
            body[data-route="kpws-pharmacy-billing"] .kpws-v101-active-result {
                outline: 3px solid #bfdbfe;
                border-radius: 14px;
            }
            body[data-route="kpws-pharmacy-billing"] .kpws-v102-recent-row {
                display: grid;
                grid-template-columns: minmax(0,1fr) auto;
                gap: 10px;
                padding: 10px 0;
                border-bottom: 1px solid #e5e7eb;
                align-items: center;
            }
            body[data-route="kpws-pharmacy-billing"] .kpws-v102-recent-row:last-child { border-bottom: 0; }
            body[data-route="kpws-pharmacy-billing"] .kpws-v102-invoice-name {
                color: #0f172a;
                font-weight: 950;
            }
            body[data-route="kpws-pharmacy-billing"] .kpws-v102-invoice-meta {
                color: #64748b;
                font-size: 12px;
                font-weight: 800;
                margin-top: 2px;
            }
            body[data-route="kpws-pharmacy-billing"] .kpws-v102-print-btn {
                padding: 7px 10px !important;
                min-height: 34px !important;
            }
            body[data-route="kpws-pharmacy-billing"] .kpws-v98-ready-note {
                font-size: 12px;
                font-weight: 850;
                margin-top: 8px;
                color: #475569;
            }
            body[data-route="kpws-pharmacy-billing"] .kpws-v98-ready-note.blocked { color: #b91c1c; }
            @media (max-width: 1100px) {
                body[data-route="kpws-pharmacy-billing"] .kpws-v98-patient-banner,
                body[data-route="kpws-pharmacy-billing"] .kpws-v100-confirm-grid {
                    grid-template-columns: 1fr;
                }
            }
        `;
        document.head.appendChild(style);
    }

    KPWSPharmacyBillingPOS.prototype.kpwsGetSelectedPatientV98 = function () {
        if (this.isWalkin && this.isWalkin()) return "";
        if (this.patientControl && this.patientControl.get_value) return this.patientControl.get_value() || "";
        const raw = this.page && this.page.main ? this.page.main.find('#kpws-patient-control input').val() : "";
        return raw || (this.patientContext && this.patientContext.patient) || "";
    };

    KPWSPharmacyBillingPOS.prototype.kpwsBillingModeV98 = function () {
        const ctx = this.patientContext || {};
        const reg = ctx.registration || {};
        const plan = this.paymentPlan || {};
        let group = String(plan.group || ctx.group || ctx.billing_group || "").trim();
        const purpose = String(plan.purpose || reg.purpose || ctx.purpose || "").trim();
        const panel = String(reg.panel_customer || reg.panel || reg.panel_name || ctx.panel_customer || ctx.bill_to_customer || "").trim();

        if (this.isWalkin && this.isWalkin()) return { key: "cash", label: "Cash", purpose: "Cash", panel: "" };

        const text = `${group} ${purpose}`.toLowerCase();
        const hasPanel = !!panel && !/^cash$/i.test(group);
        const isWelfare = text.includes("welfare") || text.includes("zakat") || text.includes("donation");

        if (isWelfare && hasPanel) return { key: "welfare-panel", label: "Welfare Panel", purpose: purpose || "Zakat / Donation", panel };
        if (String(group).toLowerCase().includes("panel")) return { key: "panel", label: "Panel", purpose: "Panel", panel };
        if (isWelfare) return { key: "welfare", label: "Welfare", purpose: purpose || "Zakat / Donation", panel: "" };
        return { key: "cash", label: "Cash", purpose: "Cash", panel: "" };
    };

    KPWSPharmacyBillingPOS.prototype.kpwsGetBillToV98 = function () {
        const ctx = this.patientContext || {};
        const reg = ctx.registration || {};
        const mode = this.kpwsBillingModeV98 ? this.kpwsBillingModeV98() : {};
        const controlValue = this.billToControl && this.billToControl.get_value ? this.billToControl.get_value() : "";
        if (mode.key === "welfare-panel") return reg.panel_customer || reg.panel || reg.panel_name || ctx.bill_to_customer || controlValue || "-";
        return ctx.bill_to_customer || controlValue || reg.panel_customer || "-";
    };

    KPWSPharmacyBillingPOS.prototype.kpwsEnsureEnhancedLayoutV98 = function () {
        injectUIStyle();
        const main = this.page && this.page.main;
        if (!main || !main.length) return;

        if (!main.find("#kpws-v98-patient-banner").length) {
            const billingRoot = main.find("#kpws-billing-tab");
            const posMain = main.find(".kpws-pos-main").first();
            const banner = `
                <div class="kpws-v98-patient-banner" id="kpws-v98-patient-banner">
                    <div>
                        <div class="kpws-v98-banner-title">Patient / Medicine Receiver</div>
                        <div class="kpws-v98-banner-main" id="kpws-v98-banner-patient">Select patient to start billing</div>
                        <div class="kpws-v98-banner-sub" id="kpws-v98-banner-mr">MR No: -</div>
                    </div>
                    <div>
                        <div class="kpws-v98-banner-title">Bill To / Covering Party</div>
                        <div class="kpws-v98-banner-main" id="kpws-v98-banner-billto">-</div>
                        <div class="kpws-v98-banner-sub" id="kpws-v98-banner-price">Price List: -</div>
                    </div>
                    <div>
                        <div class="kpws-v98-mode-badge" id="kpws-v98-banner-mode">Billing Mode</div>
                        <div class="kpws-v98-banner-sub" id="kpws-v98-banner-coverage">Coverage: -</div>
                        <div class="kpws-v98-banner-sub" id="kpws-v98-banner-purpose">Purpose: -</div>
                    </div>
                </div>`;
            if (posMain.length) posMain.before(banner);
            else if (billingRoot.length) billingRoot.prepend(banner);
        }

        const billToHolder = main.find("#kpws-billto-control");
        if (billToHolder.length) {
            const field = billToHolder.closest(".kpws-pos-field");
            if (!main.find("#kpws-billto-display-v98").length) {
                field.append(`
                    <label>Bill To Customer</label>
                    <div class="kpws-v98-billto-display" id="kpws-billto-display-v98">-</div>
                    <div class="kpws-v98-auto-note">Auto-selected by system from Patient / Welfare Approval. Users cannot manually change it here.</div>
                `);
            }
            billToHolder.hide();
            if (this.billToControl) {
                try { this.billToControl.df.read_only = 1; this.billToControl.refresh(); } catch (e) {}
                try { this.billToControl.$wrapper && this.billToControl.$wrapper.hide(); } catch (e) {}
            }
        }

        if (!main.find("#kpws-v101-keyboard-hint").length) {
            const searchField = main.find("#kpws-item-search").closest(".kpws-pos-field");
            searchField.append(`
                <div class="kpws-v101-keyboard-hint" id="kpws-v101-keyboard-hint">
                    Keyboard: type/scanner code → Enter. Use Qty box in result → Enter to add. Esc clears search.
                </div>
            `);
        }

        if (!main.find("#kpws-v98-submit-note").length) {
            main.find("#kpws-submit-invoice").after(`<div class="kpws-v98-ready-note" id="kpws-v98-submit-note"></div>`);
        }

        if (!main.find("#kpws-v102-recent-card").length) {
            const right = main.find(".kpws-pos-right").first();
            if (right.length) {
                right.append(`
                    <div class="kpws-pos-card" id="kpws-v102-recent-card">
                        <div class="kpws-pos-card-title">
                            <span>Recent Invoices</span>
                            <button class="kpws-pos-btn light kpws-v102-print-btn" id="kpws-v102-refresh-recent" type="button">Refresh</button>
                        </div>
                        <div id="kpws-v102-recent-list" class="kpws-pos-search-results">
                            <div class="kpws-pos-cart-empty">No recent invoices loaded yet.</div>
                        </div>
                    </div>
                `);
                main.find("#kpws-v102-refresh-recent").off("click.kpwsV102").on("click.kpwsV102", () => this.kpwsLoadRecentInvoicesV102());
            }
        }

        this.kpwsRefreshBannerV98();
        this.kpwsRefreshSubmitStateV98();
    };

    KPWSPharmacyBillingPOS.prototype.kpwsRefreshBannerV98 = function () {
        const main = this.page && this.page.main;
        if (!main || !main.length || !main.find("#kpws-v98-patient-banner").length) return;
        const ctx = this.patientContext || {};
        const reg = ctx.registration || {};
        const plan = this.paymentPlan || {};
        const mode = this.kpwsBillingModeV98();
        const total = this.total ? this.total() : n(plan.invoice_total || plan.total);
        const percentage = n(plan.percentage || reg.percentage || ctx.percentage || 0);
        const billTo = this.kpwsGetBillToV98();
        const patientName = (this.isWalkin && this.isWalkin()) ? (this.getWalkinName && this.getWalkinName() || "Walk-in Patient") : (ctx.patient_name || ctx.patient || this.kpwsGetSelectedPatientV98() || "Select patient to start billing");
        const mr = (this.isWalkin && this.isWalkin()) ? (this.getWalkinMR && this.getWalkinMR() || "Walk-in") : (ctx.mr_number || ctx.patient || "-");
        const priceList = ctx.price_list || "-";
        const covered = mode.key === "panel" ? total : n(plan.covered_amount || (mode.key === "welfare-panel" ? total * percentage / 100 : 0));
        const share = mode.key === "panel" ? 0 : n(plan.patient_share || Math.max(0, total - covered));

        main.find("#kpws-v98-banner-patient").text(patientName || "-");
        main.find("#kpws-v98-banner-mr").text(`MR No: ${mr || "-"}`);
        main.find("#kpws-v98-banner-billto").text(billTo || "-");
        main.find("#kpws-v98-banner-price").text(`Price List: ${priceList || "-"}`);
        main.find("#kpws-v98-banner-mode")
            .attr("class", `kpws-v98-mode-badge kpws-v98-mode-${mode.key}`)
            .text(mode.label || "Billing Mode");
        main.find("#kpws-v98-banner-coverage").text(`Coverage: ${percentage ? percentage + "%" : (mode.key === "panel" ? "100%" : "-")} | Covered: ${money(covered)} | Patient Share: ${money(share)}`);
        main.find("#kpws-v98-banner-purpose").text(`Purpose: ${mode.purpose || "-"}`);
        main.find("#kpws-billto-display-v98").text(billTo || "-");
    };

    KPWSPharmacyBillingPOS.prototype.kpwsRefreshSubmitStateV98 = function () {
        const main = this.page && this.page.main;
        if (!main || !main.length) return;
        const submitBtn = main.find("#kpws-submit-invoice");
        const note = main.find("#kpws-v98-submit-note");
        if (!submitBtn.length) return;

        let blocked = false;
        let message = "Ready to submit once patient, items and payments are valid.";
        if (!this.patientContext) {
            blocked = true;
            message = "Select patient first.";
        } else if (!this.cart || !this.cart.length) {
            blocked = true;
            message = "Add at least one medicine to cart.";
        } else if ((this.paymentPlan && this.paymentPlan.warnings && this.paymentPlan.warnings.length)) {
            blocked = true;
            message = "Fix payment settings/warnings before submitting.";
        }
        submitBtn.prop("disabled", blocked);
        note.toggleClass("blocked", blocked).text(message);
    };

    KPWSPharmacyBillingPOS.prototype.kpwsBuildPaymentSummaryV99 = function () {
        const plan = this.paymentPlan || {};
        const ctx = this.patientContext || {};
        const reg = ctx.registration || {};
        const mode = this.kpwsBillingModeV98();
        const total = n(plan.invoice_total || plan.total || (this.total ? this.total() : 0));
        const percentage = n(plan.percentage || reg.percentage || 0);
        let covered = n(plan.covered_amount || 0);
        let patientShare = n(plan.patient_share || 0);

        if (mode.key === "panel") {
            covered = total;
            patientShare = 0;
        } else if (mode.key === "welfare-panel") {
            if (!covered && percentage) covered = Math.min(total, total * percentage / 100);
            if (!patientShare && total > 0) patientShare = Math.max(0, total - covered);
        } else if (mode.key === "cash") {
            covered = 0;
            patientShare = total;
        }

        const patientCash = n(plan.patient_cash || Math.max(0, patientShare - n(plan.patient_card || 0)));
        const patientCard = n(plan.patient_card || 0);
        const advance = n(plan.customer_advance_allocated || 0);
        const billTo = this.kpwsGetBillToV98();
        const purpose = mode.purpose || plan.purpose || reg.purpose || "-";

        let lines = [];
        lines.push(`<div class="kpws-v99-summary-line primary"><span>Grand Total</span><strong>${money(total)}</strong></div>`);

        if (mode.key === "cash") {
            lines.push(`<div class="kpws-v99-summary-line success"><span>Patient Payable by Cash/Card</span><strong>${money(patientShare)}</strong></div>`);
            if (patientCard > 0) lines.push(`<div class="kpws-v99-summary-line"><span>Card</span><strong>${money(patientCard)}</strong></div>`);
            if (patientCash > 0) lines.push(`<div class="kpws-v99-summary-line"><span>Cash</span><strong>${money(patientCash)}</strong></div>`);
        } else if (mode.key === "welfare") {
            lines.push(`<div class="kpws-v99-summary-line success"><span>${esc(purpose)} Covered by KPWS Fund${percentage ? ` (${percentage}%)` : ""}</span><strong>${money(covered)}</strong></div>`);
            lines.push(`<div class="kpws-v99-summary-line warning"><span>Patient Payable Now</span><strong>${money(patientShare)}</strong></div>`);
        } else if (mode.key === "panel") {
            lines.push(`<div class="kpws-v99-summary-line success"><span>Covered by Panel: ${esc(billTo)}</span><strong>${money(total)}</strong></div>`);
            lines.push(`<div class="kpws-v99-summary-line"><span>Patient Payable Now</span><strong>${money(0)}</strong></div>`);
        } else if (mode.key === "welfare-panel") {
            lines.push(`<div class="kpws-v99-summary-line success"><span>${esc(purpose)} Covered by Panel: ${esc(billTo)}${percentage ? ` (${percentage}%)` : ""}</span><strong>${money(covered)}</strong></div>`);
            lines.push(`<div class="kpws-v99-summary-line warning"><span>Patient Payable Now</span><strong>${money(patientShare)}</strong></div>`);
        }

        if (advance > 0) {
            lines.push(`<div class="kpws-v99-summary-line"><span>Advance Allocation</span><strong>${money(advance)}</strong></div>`);
        }

        return `<div class="kpws-v99-summary">${lines.join("")}</div>`;
    };

    KPWSPharmacyBillingPOS.prototype.kpwsConfirmSubmitV100 = function () {
        const ctx = this.patientContext || {};
        const plan = this.paymentPlan || {};
        const mode = this.kpwsBillingModeV98();
        const total = n(plan.invoice_total || plan.total || (this.total ? this.total() : 0));
        const reg = ctx.registration || {};
        const percentage = n(plan.percentage || reg.percentage || 0);
        const covered = mode.key === "panel" ? total : n(plan.covered_amount || (mode.key === "welfare-panel" && percentage ? total * percentage / 100 : 0));
        const patientShare = mode.key === "panel" ? 0 : n(plan.patient_share || Math.max(0, total - covered));
        const patientName = (this.isWalkin && this.isWalkin()) ? (this.getWalkinName && this.getWalkinName() || "Walk-in Patient") : (ctx.patient_name || ctx.patient || this.kpwsGetSelectedPatientV98() || "-");
        const mr = (this.isWalkin && this.isWalkin()) ? (this.getWalkinMR && this.getWalkinMR() || "-") : (ctx.mr_number || ctx.patient || "-");
        const billTo = this.kpwsGetBillToV98();
        const purpose = mode.purpose || plan.purpose || reg.purpose || "-";
        const html = `
            <div style="font-weight:900;color:#0f172a;margin-bottom:10px;">Please confirm invoice before submission.</div>
            <div class="kpws-v100-confirm-grid">
                <div class="kpws-v100-confirm-cell"><span>Patient</span><b>${esc(patientName)}</b></div>
                <div class="kpws-v100-confirm-cell"><span>MR No</span><b>${esc(mr)}</b></div>
                <div class="kpws-v100-confirm-cell"><span>Billing Type</span><b>${esc(mode.label)}</b></div>
                <div class="kpws-v100-confirm-cell"><span>Bill To</span><b>${esc(billTo)}</b></div>
                <div class="kpws-v100-confirm-cell"><span>Purpose</span><b>${esc(purpose)}</b></div>
                <div class="kpws-v100-confirm-cell"><span>Coverage %</span><b>${percentage || (mode.key === "panel" ? 100 : 0)}%</b></div>
                <div class="kpws-v100-confirm-cell"><span>Grand Total</span><b>${money(total)}</b></div>
                <div class="kpws-v100-confirm-cell"><span>Covered Amount</span><b>${money(covered)}</b></div>
                <div class="kpws-v100-confirm-cell"><span>Patient Payable</span><b>${money(patientShare)}</b></div>
                <div class="kpws-v100-confirm-cell"><span>Items</span><b>${(this.cart || []).length}</b></div>
            </div>
        `;

        return new Promise((resolve) => {
            if (!frappe.ui || !frappe.ui.Dialog) {
                resolve(window.confirm(`Submit invoice for ${patientName} / Bill To ${billTo} / Total ${money(total)}?`));
                return;
            }
            let done = false;
            const d = new frappe.ui.Dialog({
                title: "Confirm Invoice",
                fields: [{ fieldtype: "HTML", fieldname: "summary", options: html }],
                primary_action_label: "Submit Invoice",
                primary_action: function () {
                    done = true;
                    d.hide();
                    resolve(true);
                }
            });
            if (d.set_secondary_action) {
                d.set_secondary_action(function () {
                    done = true;
                    d.hide();
                    resolve(false);
                });
                d.set_secondary_action_label && d.set_secondary_action_label("Cancel");
            }
            d.$wrapper.on("hidden.bs.modal", function () {
                if (!done) resolve(false);
            });
            d.show();
        });
    };

    KPWSPharmacyBillingPOS.prototype.kpwsResetAfterSubmitV98 = function () {
        try {
            this.patientContext = null;
            this.paymentPlan = null;
            this.cart = [];
            this.currentParkedInvoice = null;
            if (this.patientControl && this.patientControl.set_value) this.patientControl.set_value("");
            if (this.billToControl && this.billToControl.set_value) this.billToControl.set_value("");
            const main = this.page.main;
            main.find("#kpws-mr,#kpws-patient-name,#kpws-billing-type,#kpws-price-list,#kpws-purpose").text("-");
            main.find("#kpws-percentage").text("0%");
            main.find("#kpws-card-amount").val("0");
            main.find("#kpws-search-results").html("");
            main.find("#kpws-item-search").val("");
            main.find("#kpws-patient-status").html("");
            if (this.updateCart) this.updateCart();
            if (this.renderCurrentParkedBadge) this.renderCurrentParkedBadge();
            this.kpwsRefreshBannerV98();
            this.kpwsRefreshSubmitStateV98();
            setTimeout(() => {
                const input = this.page.main.find("#kpws-patient-control input").get(0);
                if (input) input.focus();
            }, 200);
        } catch (e) {
            console.warn("KPWS reset after submit failed", e);
        }
    };

    KPWSPharmacyBillingPOS.prototype.kpwsLoadRecentInvoicesV102 = async function () {
        const root = this.page && this.page.main ? this.page.main.find("#kpws-v102-recent-list") : $();
        if (!root.length) return;
        root.html(`<div class="kpws-pos-warning">Loading recent invoices...</div>`);
        try {
            const r = await this.call("list_recent_invoices_ui_v102", { limit: 8 });
            const rows = r.message || [];
            if (!rows.length) {
                root.html(`<div class="kpws-pos-cart-empty">No recent invoices found.</div>`);
                return;
            }
            root.html(rows.map(row => `
                <div class="kpws-v102-recent-row">
                    <div>
                        <div class="kpws-v102-invoice-name">${esc(row.name)}</div>
                        <div class="kpws-v102-invoice-meta">${esc(row.patient_name || row.patient || row.customer || "-")} · ${esc(row.billing_group || "")} · ${money(row.grand_total)}</div>
                    </div>
                    <button class="kpws-pos-btn light kpws-v102-print-btn" data-kpws-v102-print="${esc(row.name)}" data-kpws-v102-format="${esc(row.print_format || "")}">Print</button>
                </div>
            `).join(""));
            root.find("[data-kpws-v102-print]").on("click", (e) => {
                const btn = $(e.currentTarget);
                this.openPrint({ name: btn.data("kpws-v102-print"), print_format: btn.data("kpws-v102-format") || "" });
            });
        } catch (e) {
            root.html(`<div class="kpws-pos-warning">Unable to load recent invoices. Please refresh.</div>`);
        }
    };

    KPWSPharmacyBillingPOS.prototype.kpwsBindKeyboardSearchV101 = function () {
        const main = this.page && this.page.main;
        if (!main || !main.length) return;
        const input = main.find("#kpws-item-search");
        input.off("keydown.kpwsV101").on("keydown.kpwsV101", async (e) => {
            if (e.key === "Escape") {
                if (this.kpwsClearItemSearchV97) this.kpwsClearItemSearchV97();
                else {
                    input.val("");
                    main.find("#kpws-search-results").html("");
                }
                return;
            }
            if (e.key !== "Enter") return;
            e.preventDefault();
            const qtyFields = main.find(".kpws-v97-result-qty");
            if (qtyFields.length === 1) {
                qtyFields.first().focus().select();
                return;
            }
            const txt = String(input.val() || "").trim();
            if (!txt || txt.length < 2) return;
            try {
                const r = await this.call("search_items", {
                    txt,
                    patient: (this.isWalkin && this.isWalkin()) ? "" : (this.patientContext ? this.patientContext.patient : ""),
                    price_list: this.patientContext ? this.patientContext.price_list : ""
                });
                const rows = r.message || [];
                const exact = rows.find(row => String(row.item_code || "").toLowerCase() === txt.toLowerCase() || String(row.barcode || "").toLowerCase() === txt.toLowerCase());
                if (exact && !exact.missing_price) {
                    this.addItem(exact, 1);
                } else if (rows.length) {
                    await this.searchItems();
                    setTimeout(() => {
                        const firstQty = main.find(".kpws-v97-result-qty").first();
                        if (firstQty.length) firstQty.focus().select();
                    }, 80);
                }
            } catch (err) {
                await this.searchItems();
            }
        });
    };

    // Keep buildInvoicePayload safe: always use the actual selected Patient Link value and never trust editable Bill To UI.
    const oldBuildInvoicePayloadV98 = KPWSPharmacyBillingPOS.prototype.buildInvoicePayload;
    if (oldBuildInvoicePayloadV98) {
        KPWSPharmacyBillingPOS.prototype.buildInvoicePayload = function (submit) {
            const payload = oldBuildInvoicePayloadV98.apply(this, arguments) || {};
            payload.selected_patient = this.kpwsGetSelectedPatientV98 ? this.kpwsGetSelectedPatientV98() : payload.patient;
            if (!(this.isWalkin && this.isWalkin())) payload.patient = payload.selected_patient || payload.patient;
            payload.bill_to_customer = this.kpwsGetBillToV98 ? this.kpwsGetBillToV98() : payload.bill_to_customer;
            payload.kpws_ui_patch = PATCH_VERSION;
            return payload;
        };
    }

    const oldRenderBillingV98 = KPWSPharmacyBillingPOS.prototype.renderBilling;
    KPWSPharmacyBillingPOS.prototype.renderBilling = function () {
        oldRenderBillingV98.apply(this, arguments);
        this.kpwsEnsureEnhancedLayoutV98();
        this.kpwsBindKeyboardSearchV101();
        setTimeout(() => this.kpwsLoadRecentInvoicesV102(), 300);
    };

    const oldLoadPatientV98 = KPWSPharmacyBillingPOS.prototype.loadPatient;
    KPWSPharmacyBillingPOS.prototype.loadPatient = async function (patient) {
        const selected = patient || (this.kpwsGetSelectedPatientV98 ? this.kpwsGetSelectedPatientV98() : "");
        const out = await oldLoadPatientV98.apply(this, [selected]);
        this.kpwsEnsureEnhancedLayoutV98();
        this.kpwsRefreshBannerV98();
        this.kpwsRefreshSubmitStateV98();
        return out;
    };

    const oldUpdateCartV98 = KPWSPharmacyBillingPOS.prototype.updateCart;
    KPWSPharmacyBillingPOS.prototype.updateCart = function () {
        const out = oldUpdateCartV98.apply(this, arguments);
        this.kpwsEnsureEnhancedLayoutV98();
        this.kpwsRefreshBannerV98();
        this.kpwsRefreshSubmitStateV98();
        return out;
    };

    const oldRenderPaymentPlanV99 = KPWSPharmacyBillingPOS.prototype.renderPaymentPlan;
    KPWSPharmacyBillingPOS.prototype.renderPaymentPlan = function () {
        oldRenderPaymentPlanV99.apply(this, arguments);
        const plan = this.paymentPlan || {};
        const mode = this.kpwsBillingModeV98();
        const total = n(plan.invoice_total || plan.total || (this.total ? this.total() : 0));
        const percentage = n(plan.percentage || ((this.patientContext || {}).registration || {}).percentage || 0);
        let covered = n(plan.covered_amount || 0);
        let share = n(plan.patient_share || 0);
        if (mode.key === "panel") {
            covered = total;
            share = 0;
        } else if (mode.key === "welfare-panel") {
            if (!covered && percentage) covered = Math.min(total, total * percentage / 100);
            if (!share && total > 0) share = Math.max(0, total - covered);
        } else if (mode.key === "cash") {
            covered = 0;
            share = total;
        }
        this.page.main.find("#kpws-final-total").text(money(total));
        this.page.main.find("#kpws-covered-amount").text(money(covered));
        this.page.main.find("#kpws-patient-share").text(money(share));
        this.page.main.find("#kpws-payable-now").text(money(share));
        this.page.main.find("#kpws-payment-plan").html(this.kpwsBuildPaymentSummaryV99());
        this.kpwsRefreshBannerV98();
        this.kpwsRefreshSubmitStateV98();
    };

    const oldRefreshPaymentPlanV98 = KPWSPharmacyBillingPOS.prototype.refreshPaymentPlan;
    KPWSPharmacyBillingPOS.prototype.refreshPaymentPlan = async function () {
        const out = await oldRefreshPaymentPlanV98.apply(this, arguments);
        this.kpwsEnsureEnhancedLayoutV98();
        this.kpwsRefreshBannerV98();
        this.kpwsRefreshSubmitStateV98();
        return out;
    };

    const oldBindBillingEventsV101 = KPWSPharmacyBillingPOS.prototype.bindBillingEvents;
    KPWSPharmacyBillingPOS.prototype.bindBillingEvents = function () {
        oldBindBillingEventsV101.apply(this, arguments);
        this.kpwsEnsureEnhancedLayoutV98();
        this.kpwsBindKeyboardSearchV101();
        this.page.main.find("#kpws-card-amount").off("input.kpwsV98").on("input.kpwsV98", () => {
            this.kpwsRefreshBannerV98();
            this.kpwsRefreshSubmitStateV98();
        });
    };

    const oldCreateInvoiceV100 = KPWSPharmacyBillingPOS.prototype.createInvoice;
    KPWSPharmacyBillingPOS.prototype.createInvoice = async function (submit) {
        this.kpwsEnsureEnhancedLayoutV98();
        if (submit) {
            if (!this.patientContext) {
                frappe.msgprint("Please select Patient or enable Walk-in Patient first.");
                return;
            }
            if (!this.cart || !this.cart.length) {
                frappe.msgprint("Please add at least one item.");
                return;
            }
            const ok = await this.kpwsConfirmSubmitV100();
            if (!ok) return;
        }
        const before = this.lastInvoice && this.lastInvoice.name;
        const out = await oldCreateInvoiceV100.apply(this, arguments);
        const after = this.lastInvoice && this.lastInvoice.name;
        if (after && after !== before) {
            this.kpwsLoadRecentInvoicesV102();
        }
        if (submit && after && after !== before) {
            setTimeout(() => this.kpwsResetAfterSubmitV98(), 1200);
        } else {
            this.kpwsRefreshBannerV98();
            this.kpwsRefreshSubmitStateV98();
        }
        return out;
    };

    const oldClearPOSV98 = KPWSPharmacyBillingPOS.prototype.clearPOSForNewInvoice;
    if (oldClearPOSV98) {
        KPWSPharmacyBillingPOS.prototype.clearPOSForNewInvoice = function () {
            const out = oldClearPOSV98.apply(this, arguments);
            this.kpwsResetAfterSubmitV98();
            return out;
        };
    }

    console.log("KPWS Billing UI V98-V102 loaded.");
})();
/* KPWS_BILLING_UI_V98_V102_END */
