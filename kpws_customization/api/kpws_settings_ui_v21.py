from pathlib import Path
import frappe


PATCH_MARKER = "KPWS_SETTINGS_UI_V21_PATCH"


JS_PATCH = r'''

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

    js_files = [
        app_path / "page" / "kpws_pharmacy_billing" / "kpws_pharmacy_billing.js",
        app_path / "kpws_customization" / "page" / "kpws_pharmacy_billing" / "kpws_pharmacy_billing.js",
    ]

    changed = []

    for js in js_files:
        if _append_once(js, JS_PATCH, PATCH_MARKER):
            changed.append(str(js))

    frappe.clear_cache()
    frappe.db.commit()

    return {
        "ok": True,
        "changed_files": changed,
        "message": "Settings UI redesigned with readable fonts and grouped cards."
    }
