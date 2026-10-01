from pathlib import Path
import frappe


PATCH_MARKER = "KPWS_PHARMACY_UI_PRINT_V3_PATCH"


JS_PATCH = r'''

/* KPWS_PHARMACY_UI_PRINT_V3_PATCH */

(function () {
    function kpwsPharmacyInjectDarkReadableCSS() {
        if (document.getElementById("kpws-pharmacy-readable-v3-css")) return;

        const css = `
            .kpws-pharmacy-wrap,
            .kpws-pharmacy-wrap * {
                color: #111827;
            }

            .kpws-card-title {
                color: #000000 !important;
                font-weight: 900 !important;
            }

            .kpws-field label {
                color: #111827 !important;
                font-weight: 900 !important;
            }

            .kpws-input {
                color: #000000 !important;
                font-weight: 700 !important;
                background: #ffffff !important;
            }

            .kpws-readonly {
                color: #000000 !important;
                font-weight: 800 !important;
                background: #f8fafc !important;
            }

            .kpws-table th {
                color: #0f172a !important;
                font-weight: 900 !important;
                background: #f1f5f9 !important;
            }

            .kpws-table td,
            .kpws-table td *,
            .kpws-result-row,
            .kpws-result-row *,
            #kpws-payment-plan,
            #kpws-payment-plan *,
            #kpws-cart,
            #kpws-cart *,
            #kpws-search-results,
            #kpws-search-results * {
                color: #111827 !important;
                font-weight: 700 !important;
                opacity: 1 !important;
            }

            .kpws-result-row b,
            .kpws-table td b {
                color: #000000 !important;
                font-weight: 900 !important;
            }

            .kpws-result-row div[style*="color"],
            .kpws-table div[style*="color"] {
                color: #334155 !important;
                font-weight: 700 !important;
            }

            .kpws-btn {
                font-weight: 900 !important;
            }

            .kpws-btn.primary,
            .kpws-btn.green,
            .kpws-btn.dark,
            .kpws-btn.red {
                color: #ffffff !important;
            }

            .kpws-warning {
                color: #7c2d12 !important;
                font-weight: 800 !important;
            }

            .kpws-status-title {
                color: #000000 !important;
                font-weight: 900 !important;
            }

            .kpws-status-msg {
                color: #111827 !important;
                font-weight: 700 !important;
            }
        `;

        const style = document.createElement("style");
        style.id = "kpws-pharmacy-readable-v3-css";
        style.innerHTML = css;
        document.head.appendChild(style);
    }

    function kpwsOpenSalesInvoicePrint(data) {
        if (!data || !data.name) return;

        const params = new URLSearchParams();
        params.set("doctype", "Sales Invoice");
        params.set("name", data.name);
        params.set("trigger_print", "1");
        params.set("no_letterhead", "0");

        if (data.print_format) {
            params.set("format", data.print_format);
        }

        const url = `/printview?${params.toString()}`;

        window.open(url, "_blank");

        frappe.show_alert({
            message: "Print preview opened for Sales Invoice " + data.name,
            indicator: "green"
        }, 8);
    }

    kpwsPharmacyInjectDarkReadableCSS();

    if (window.KPWSPharmacyBilling) {
        const oldRender = KPWSPharmacyBilling.prototype.render;

        KPWSPharmacyBilling.prototype.render = function () {
            const result = oldRender.apply(this, arguments);
            kpwsPharmacyInjectDarkReadableCSS();
            return result;
        };

        KPWSPharmacyBilling.prototype.createInvoice = async function (submit) {
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

                frappe.show_alert({
                    message: data.message || "Sales Invoice created successfully.",
                    indicator: "green"
                }, 8);

                if (submit) {
                    kpwsOpenSalesInvoicePrint(data);
                }

                frappe.set_route("Form", "Sales Invoice", data.name);
            } catch (e) {
                frappe.dom.unfreeze();
            }
        };
    }
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
        "message": "Pharmacy UI readability and submit-print patch installed."
    }
