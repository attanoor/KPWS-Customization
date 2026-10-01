from pathlib import Path
import frappe


PATCH_MARKER = "KPWS_ADVANCE_VISIBILITY_FIX_V24_PATCH"


JS_PATCH = r'''

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
        "message": "Customer Advance section now shows only for customers marked Is Advance Customer."
    }
