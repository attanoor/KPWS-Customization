from pathlib import Path
import frappe


PATCH_MARKER = "KPWS_FULL_ADVANCE_ZERO_PAYABLE_FIX_V25_PATCH"


SERVER_PATCH = r'''

# KPWS_FULL_ADVANCE_ZERO_PAYABLE_FIX_V25_PATCH

def _kpws_zero_payable_plan(group="Cash", purpose="Advance", percentage=0):
    """
    When customer advance fully covers the invoice, remaining payable becomes 0.
    That is valid and must not be treated as an error.
    """
    return {
        "total": 0,
        "rows": [],
        "warnings": [],
        "patient_share": 0,
        "covered_amount": 0,
        "group": group or "Cash",
        "purpose": purpose or "Advance",
        "percentage": flt(percentage or 0),
        "zero_payable": 1,
    }


def _kpws_compute_walkin_payment_plan(total=0, card_amount=0):
    settings = _ensure_settings_doc()
    total = flt(total, 2)

    if total <= 0:
        return _kpws_zero_payable_plan(group="Walk-in", purpose="Advance", percentage=0)

    card_amount = min(flt(card_amount, 2), total)
    cash_part = flt(total - card_amount, 2)

    modes = _kpws_payment_modes(settings)
    rows = []
    warnings = []

    if card_amount > 0:
        if not modes.get("card"):
            warnings.append("Card Mode of Payment is missing in Settings.")
        rows.append({
            "label": "Card",
            "role": "card",
            "mode_of_payment": modes.get("card"),
            "amount": card_amount,
            "editable": 1,
        })

    if cash_part > 0:
        if not modes.get("cash"):
            warnings.append("Cash Mode of Payment is missing in Settings.")
        rows.append({
            "label": "Cash",
            "role": "cash",
            "mode_of_payment": modes.get("cash"),
            "amount": cash_part,
            "editable": 1,
        })

    return {
        "total": total,
        "rows": rows,
        "warnings": warnings,
        "patient_share": total,
        "covered_amount": 0,
        "group": "Walk-in",
        "purpose": "Cash",
        "percentage": 0,
    }


def _kpws_compute_payment_plan(patient, total, cash_amount=0, card_amount=0):
    settings = _ensure_settings_doc()
    ctx = get_patient_context(patient)

    group = ctx.get("group") or "Cash"
    registration = ctx.get("registration") or {}
    purpose = (registration.get("purpose") or "").strip()
    percentage = flt(registration.get("percentage"))

    modes = _kpws_payment_modes(settings)
    total = flt(total, 2)
    card_amount = flt(card_amount, 2)

    # Important:
    # If remaining payable is zero because customer advance has fully covered the invoice,
    # do not return warning "Invoice total is zero".
    if total <= 0:
        return _kpws_zero_payable_plan(
            group=group,
            purpose=purpose or "Advance",
            percentage=percentage,
        )

    rows = []
    warnings = []

    if group == "Panel":
        mode = modes.get("panel")
        if not mode:
            warnings.append("Panel Mode of Payment is missing in Settings.")

        rows.append({
            "label": "Panel",
            "role": "panel",
            "mode_of_payment": mode,
            "amount": total,
            "editable": 0,
        })

        return {
            "total": total,
            "rows": rows,
            "warnings": warnings,
            "patient_share": 0,
            "covered_amount": total,
            "group": group,
            "purpose": "Panel",
            "percentage": 100,
        }

    if group == "Welfare":
        pct = max(0, min(percentage, 100))
        covered_amount = flt(total * pct / 100, 2)
        patient_share = flt(total - covered_amount, 2)

        purpose_lower = purpose.lower()

        if purpose_lower == "zakat":
            welfare_mode = modes.get("zakat")
            welfare_label = "Zakat"
        elif purpose_lower == "donation":
            welfare_mode = modes.get("donation")
            welfare_label = "Donation"
        else:
            welfare_mode = None
            welfare_label = "Welfare"
            warnings.append("Welfare purpose is missing in Patient Registration Form. It should be Zakat or Donation.")

        if covered_amount > 0:
            if not welfare_mode:
                warnings.append(f"{welfare_label} Mode of Payment is missing in Settings.")

            rows.append({
                "label": welfare_label,
                "role": welfare_label.lower(),
                "mode_of_payment": welfare_mode,
                "amount": covered_amount,
                "editable": 0,
            })

        if patient_share > 0:
            card_amount = min(card_amount, patient_share)
            cash_part = flt(patient_share - card_amount, 2)

            if card_amount > 0:
                if not modes.get("card"):
                    warnings.append("Card Mode of Payment is missing in Settings.")

                rows.append({
                    "label": "Card",
                    "role": "card",
                    "mode_of_payment": modes.get("card"),
                    "amount": card_amount,
                    "editable": 1,
                })

            if cash_part > 0:
                if not modes.get("cash"):
                    warnings.append("Cash Mode of Payment is missing in Settings.")

                rows.append({
                    "label": "Cash",
                    "role": "cash",
                    "mode_of_payment": modes.get("cash"),
                    "amount": cash_part,
                    "editable": 1,
                })

        return {
            "total": total,
            "rows": rows,
            "warnings": warnings,
            "patient_share": patient_share,
            "covered_amount": covered_amount,
            "group": group,
            "purpose": purpose,
            "percentage": pct,
        }

    # Cash patient
    card_amount = min(card_amount, total)
    cash_part = flt(total - card_amount, 2)

    if card_amount > 0:
        if not modes.get("card"):
            warnings.append("Card Mode of Payment is missing in Settings.")

        rows.append({
            "label": "Card",
            "role": "card",
            "mode_of_payment": modes.get("card"),
            "amount": card_amount,
            "editable": 1,
        })

    if cash_part > 0:
        if not modes.get("cash"):
            warnings.append("Cash Mode of Payment is missing in Settings.")

        rows.append({
            "label": "Cash",
            "role": "cash",
            "mode_of_payment": modes.get("cash"),
            "amount": cash_part,
            "editable": 1,
        })

    return {
        "total": total,
        "rows": rows,
        "warnings": warnings,
        "patient_share": total,
        "covered_amount": 0,
        "group": "Cash",
        "purpose": "Cash",
        "percentage": 0,
    }


@frappe.whitelist()
def get_payment_plan(patient, total=0, card_amount=0):
    _require_role()

    if not patient:
        frappe.throw(_("Please select Patient first."))

    return _kpws_compute_payment_plan(
        patient=patient,
        total=flt(total),
        card_amount=flt(card_amount),
    )


@frappe.whitelist()
def get_walkin_payment_plan(total=0, card_amount=0):
    _require_role()

    return _kpws_compute_walkin_payment_plan(
        total=flt(total),
        card_amount=flt(card_amount),
    )
'''


JS_PATCH = r'''

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
        "message": "Full advance / zero payable invoice fixed."
    }
