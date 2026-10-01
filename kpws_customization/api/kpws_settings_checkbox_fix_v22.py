from pathlib import Path
import frappe


PATCH_MARKER = "KPWS_SETTINGS_CHECKBOX_FIX_V22_PATCH"


JS_PATCH = r'''

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
        "message": "Settings checkboxes fixed and converted to stable toggle switches."
    }
