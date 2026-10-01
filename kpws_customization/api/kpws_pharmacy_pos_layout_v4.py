from pathlib import Path
import frappe


PATCH_MARKER = "KPWS_PHARMACY_POS_LAYOUT_V4_PATCH"


JS_PATCH = r'''

/* KPWS_PHARMACY_POS_LAYOUT_V4_PATCH */

(function () {
    function kpwsInjectPOSLayoutCSS() {
        if (document.getElementById("kpws-pharmacy-pos-layout-v4-css")) return;

        const css = `
            .kpws-pharmacy-wrap {
                padding: 12px !important;
                background: #f8fafc !important;
            }

            .kpws-pos-layout {
                display: grid;
                grid-template-columns: minmax(0, 1fr) 430px;
                gap: 14px;
                align-items: start;
            }

            .kpws-pos-left,
            .kpws-pos-right {
                min-width: 0;
            }

            .kpws-pos-right {
                position: sticky;
                top: 72px;
                max-height: calc(100vh - 90px);
                overflow-y: auto;
                padding-right: 2px;
            }

            .kpws-pos-right .kpws-card {
                margin-bottom: 12px;
            }

            .kpws-pos-cart-title {
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 10px;
            }

            .kpws-pos-pill {
                background: #eff6ff;
                color: #1d4ed8 !important;
                border: 1px solid #bfdbfe;
                border-radius: 999px;
                padding: 4px 9px;
                font-size: 12px;
                font-weight: 900;
            }

            .kpws-pos-cart-row {
                border: 1px solid #e5e7eb;
                border-radius: 12px;
                padding: 10px;
                margin-bottom: 8px;
                background: #ffffff;
            }

            .kpws-pos-cart-main {
                display: flex;
                justify-content: space-between;
                gap: 10px;
                align-items: flex-start;
            }

            .kpws-pos-cart-item-name {
                font-size: 13px;
                font-weight: 900;
                color: #000000 !important;
                line-height: 1.25;
            }

            .kpws-pos-cart-item-code {
                font-size: 12px;
                font-weight: 700;
                color: #475569 !important;
                margin-top: 3px;
            }

            .kpws-pos-cart-amount {
                font-size: 14px;
                font-weight: 900;
                color: #000000 !important;
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
                font-size: 11px;
                font-weight: 900;
                color: #334155 !important;
                margin-bottom: 4px;
            }

            .kpws-pos-total-panel {
                background: #0f172a;
                color: #ffffff !important;
                border-radius: 16px;
                padding: 14px;
                margin-bottom: 12px;
            }

            .kpws-pos-total-row {
                display: flex;
                justify-content: space-between;
                gap: 12px;
                padding: 6px 0;
                color: #ffffff !important;
                font-weight: 800;
            }

            .kpws-pos-total-row * {
                color: #ffffff !important;
            }

            .kpws-pos-grand-total {
                border-top: 1px solid rgba(255,255,255,0.2);
                margin-top: 8px;
                padding-top: 12px;
                font-size: 20px;
                font-weight: 900;
            }

            .kpws-pos-actions {
                display: grid;
                grid-template-columns: 1fr;
                gap: 9px;
                margin-top: 12px;
            }

            .kpws-pos-actions .kpws-btn {
                width: 100%;
                min-height: 44px;
                font-size: 14px;
                border-radius: 12px;
            }

            .kpws-pos-payment-table {
                width: 100%;
                border-collapse: collapse;
                border-radius: 12px;
                overflow: hidden;
                border: 1px solid #e5e7eb;
                background: #ffffff;
            }

            .kpws-pos-payment-table th,
            .kpws-pos-payment-table td {
                padding: 9px;
                border-bottom: 1px solid #f1f5f9;
                font-size: 12px;
                color: #111827 !important;
                font-weight: 800;
            }

            .kpws-pos-payment-table th {
                background: #f8fafc;
                color: #334155 !important;
                font-weight: 900;
            }

            .kpws-pos-payment-table tr:last-child td {
                border-bottom: 0;
            }

            .kpws-pos-empty-cart {
                text-align: center;
                padding: 22px 12px;
                border: 1px dashed #cbd5e1;
                border-radius: 14px;
                background: #f8fafc;
                color: #475569 !important;
                font-weight: 800;
            }

            @media (max-width: 1200px) {
                .kpws-pos-layout {
                    grid-template-columns: minmax(0, 1fr) 380px;
                }
            }

            @media (max-width: 980px) {
                .kpws-pos-layout {
                    grid-template-columns: 1fr;
                }

                .kpws-pos-right {
                    position: static;
                    max-height: none;
                    overflow: visible;
                    padding-right: 0;
                }
            }
        `;

        const style = document.createElement("style");
        style.id = "kpws-pharmacy-pos-layout-v4-css";
        style.innerHTML = css;
        document.head.appendChild(style);
    }

    kpwsInjectPOSLayoutCSS();

    if (!window.KPWSPharmacyBilling) return;

    KPWSPharmacyBilling.prototype.renderBilling = function () {
        kpwsInjectPOSLayoutCSS();

        const root = this.page.main.find("#kpws-billing-tab");

        root.html(`
            <div class="kpws-pos-layout">
                <div class="kpws-pos-left">
                    <div class="kpws-card">
                        <div class="kpws-card-title">1. Patient</div>

                        <div class="kpws-grid">
                            <div class="kpws-field">
                                <div id="kpws-patient-control"></div>
                            </div>
                            <div class="kpws-field">
                                <label>MR Number</label>
                                <div class="kpws-readonly" id="kpws-mr">-</div>
                            </div>
                            <div class="kpws-field">
                                <label>Patient Name</label>
                                <div class="kpws-readonly" id="kpws-patient-name">-</div>
                            </div>
                            <div class="kpws-field">
                                <label>Billing Type</label>
                                <div class="kpws-readonly" id="kpws-billing-type">-</div>
                            </div>
                        </div>

                        <div style="margin-top:12px;" id="kpws-patient-status"></div>

                        <div class="kpws-grid" style="margin-top:12px;">
                            <div class="kpws-field">
                                <div id="kpws-billto-control"></div>
                            </div>
                            <div class="kpws-field">
                                <label>Selling Price List</label>
                                <div class="kpws-readonly" id="kpws-price-list">-</div>
                            </div>
                            <div class="kpws-field">
                                <label>Registration Purpose</label>
                                <div class="kpws-readonly" id="kpws-purpose">-</div>
                            </div>
                            <div class="kpws-field">
                                <label>Approved Percentage</label>
                                <div class="kpws-readonly" id="kpws-percentage">0%</div>
                            </div>
                        </div>
                    </div>

                    <div class="kpws-card">
                        <div class="kpws-card-title">2. Pharmacy Items</div>

                        <div class="kpws-field">
                            <label>Search medicine / item</label>
                            <input class="kpws-input" id="kpws-item-search" placeholder="Type item name or code...">
                        </div>

                        <div id="kpws-search-results"></div>
                    </div>
                </div>

                <div class="kpws-pos-right">
                    <div class="kpws-card">
                        <div class="kpws-pos-cart-title">
                            <div class="kpws-card-title" style="margin-bottom:0;">Cart</div>
                            <span class="kpws-pos-pill" id="kpws-cart-count">0 Items</span>
                        </div>

                        <div id="kpws-cart" style="margin-top:12px;"></div>
                    </div>

                    <div class="kpws-card">
                        <div class="kpws-card-title">Payment</div>

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

                        <div class="kpws-field">
                            <label>Card Amount</label>
                            <input class="kpws-input" type="number" id="kpws-card-amount" min="0" step="0.01" value="0">
                        </div>

                        <div id="kpws-payment-plan" style="margin-top:12px;"></div>

                        <div class="kpws-pos-actions">
                            <button class="kpws-btn green" id="kpws-submit-invoice">Submit & Print</button>
                            <button class="kpws-btn primary" id="kpws-save-draft">Save Draft</button>
                            <button class="kpws-btn light" id="kpws-clear">New / Clear</button>
                        </div>
                    </div>
                </div>
            </div>
        `);

        this.makeBillingControls();
        this.bindBillingEvents();
        this.updateCart();
        this.refreshPaymentPlan();
    };

    KPWSPharmacyBilling.prototype.updateCart = function () {
        const root = this.page.main.find("#kpws-cart");
        this.page.main.find("#kpws-cart-count").text(`${this.cart.length} Item${this.cart.length === 1 ? "" : "s"}`);

        if (!this.cart.length) {
            root.html(`<div class="kpws-pos-empty-cart">No items added yet.</div>`);
            this.refreshPaymentPlan();
            return;
        }

        root.html(`
            <div>
                ${this.cart.map((row, i) => `
                    <div class="kpws-pos-cart-row">
                        <div class="kpws-pos-cart-main">
                            <div>
                                <div class="kpws-pos-cart-item-name">${frappe.utils.escape_html(row.item_name || row.item_code)}</div>
                                <div class="kpws-pos-cart-item-code">${frappe.utils.escape_html(row.item_code)}</div>
                            </div>
                            <div class="kpws-pos-cart-amount">${(Number(row.qty || 0) * Number(row.rate || 0)).toFixed(2)}</div>
                        </div>

                        <div class="kpws-pos-cart-controls">
                            <div>
                                <label class="kpws-pos-mini-label">Qty</label>
                                <input class="kpws-input kpws-cart-qty" data-index="${i}" type="number" min="1" value="${row.qty}">
                            </div>

                            <div>
                                <label class="kpws-pos-mini-label">Rate</label>
                                <div class="kpws-readonly">${row.rate}</div>
                            </div>

                            <button class="kpws-btn red" data-remove="${i}">X</button>
                        </div>

                        <div style="font-size:12px;font-weight:800;color:#475569 !important;margin-top:7px;">
                            Stock: ${row.available_qty}
                        </div>
                    </div>
                `).join("")}
            </div>
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
    };

    KPWSPharmacyBilling.prototype.renderPaymentPlan = function () {
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
            html += warnings.map(w => `<div class="kpws-warning">${frappe.utils.escape_html(w)}</div>`).join("");
        }

        if (!rows.length) {
            html += `<div class="kpws-warning">Add items to calculate payment split.</div>`;
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
                                <td>${frappe.utils.escape_html(row.label || row.role || "")}</td>
                                <td>${frappe.utils.escape_html(row.mode_of_payment || "Missing")}</td>
                                <td style="text-align:right;">${Number(row.amount || 0).toFixed(2)}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            `;
        }

        this.page.main.find("#kpws-payment-plan").html(html);
    };
})();
'''


def _append_once(path):
    p = Path(path)
    if not p.exists():
        return False

    text = p.read_text()

    if PATCH_MARKER in text:
        return False

    p.write_text(text + "\n\n" + JS_PATCH)
    return True


@frappe.whitelist()
def install():
    app_path = Path(frappe.get_app_path("kpws_customization"))

    js_files = [
        app_path / "page" / "kpws_pharmacy_billing" / "kpws_pharmacy_billing.js",
        app_path / "kpws_customization" / "page" / "kpws_pharmacy_billing" / "kpws_pharmacy_billing.js",
    ]

    changed = []

    for js in js_files:
        if _append_once(js):
            changed.append(str(js))

    frappe.clear_cache()
    frappe.db.commit()

    return {
        "ok": True,
        "changed_files": changed,
        "message": "POS layout installed. Cart and payment are now on the right side."
    }
