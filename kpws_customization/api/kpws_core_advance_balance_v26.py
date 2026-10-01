from pathlib import Path
import frappe


PATCH_MARKER = "KPWS_CORE_ADVANCE_BALANCE_V26_PATCH"


SERVER_PATCH = r'''

# KPWS_CORE_ADVANCE_BALANCE_V26_PATCH

def _kpws_table_exists(table):
    try:
        return bool(frappe.db.sql("SHOW TABLES LIKE %s", table))
    except Exception:
        return False


def _kpws_payment_entry_total_amount(pe_name):
    row = frappe.db.get_value(
        "Payment Entry",
        pe_name,
        ["paid_amount", "base_paid_amount", "received_amount", "base_received_amount", "unallocated_amount"],
        as_dict=True,
    ) or {}

    for fieldname in ["paid_amount", "received_amount", "base_paid_amount", "base_received_amount"]:
        value = flt(row.get(fieldname))
        if value > 0:
            return value

    return 0


def _kpws_payment_entry_core_unallocated(pe_name):
    value = frappe.db.get_value("Payment Entry", pe_name, "unallocated_amount")
    return flt(value or 0)


def _kpws_payment_entry_allocated_from_refs(pe_name):
    """
    ERPNext core allocation when Payment Entry itself is allocated to invoices/references.
    """
    if not _kpws_table_exists("tabPayment Entry Reference"):
        return 0

    rows = frappe.db.sql(
        """
        SELECT
            per.reference_doctype,
            per.reference_name,
            SUM(IFNULL(per.allocated_amount, 0)) AS allocated
        FROM `tabPayment Entry Reference` per
        INNER JOIN `tabPayment Entry` pe
            ON pe.name = per.parent
        WHERE
            per.parent = %s
            AND pe.docstatus = 1
        GROUP BY per.reference_doctype, per.reference_name
        """,
        pe_name,
        as_dict=True,
    )

    return flt(sum(flt(row.allocated) for row in rows), 2)


def _kpws_payment_entry_allocated_from_sales_invoice_advances(pe_name):
    """
    ERPNext core allocation when Sales Invoice consumes advance from Payment Entry.
    This is the important table for POS advance allocation.
    """
    if not _kpws_table_exists("tabSales Invoice Advance"):
        return 0

    rows = frappe.db.sql(
        """
        SELECT
            sia.parent AS sales_invoice,
            SUM(IFNULL(sia.allocated_amount, 0)) AS allocated
        FROM `tabSales Invoice Advance` sia
        INNER JOIN `tabSales Invoice` si
            ON si.name = sia.parent
        WHERE
            sia.reference_type = 'Payment Entry'
            AND sia.reference_name = %s
            AND si.docstatus = 1
        GROUP BY sia.parent
        """,
        pe_name,
        as_dict=True,
    )

    return flt(sum(flt(row.allocated) for row in rows), 2)


def _kpws_payment_entry_remaining_advance(pe_name):
    total_amount = _kpws_payment_entry_total_amount(pe_name)
    core_unallocated = _kpws_payment_entry_core_unallocated(pe_name)

    allocated_from_refs = _kpws_payment_entry_allocated_from_refs(pe_name)
    allocated_from_si_advances = _kpws_payment_entry_allocated_from_sales_invoice_advances(pe_name)

    total_allocated = flt(allocated_from_refs + allocated_from_si_advances, 2)
    calculated_remaining = flt(total_amount - total_allocated, 2)

    if calculated_remaining < 0:
        calculated_remaining = 0

    # Use the stricter lower value when ERPNext's own unallocated field is lower.
    # This prevents overstating advance balance.
    if core_unallocated > 0:
        remaining = min(core_unallocated, calculated_remaining)
    else:
        remaining = calculated_remaining

    return {
        "payment_entry": pe_name,
        "paid_amount": flt(total_amount, 2),
        "allocated_amount": flt(total_allocated, 2),
        "allocated_from_payment_entry_references": flt(allocated_from_refs, 2),
        "allocated_from_sales_invoice_advances": flt(allocated_from_si_advances, 2),
        "core_unallocated_amount": flt(core_unallocated, 2),
        "remaining_amount": flt(remaining, 2),
    }


def _kpws_customer_unallocated_advances(customer):
    """
    Strict ERPNext-core based customer advance balance.
    Source:
    - Submitted Payment Entry
    - Payment Type = Receive
    - Party Type = Customer
    - Party = selected customer
    Remaining is recalculated from:
    - Payment Entry Reference
    - Sales Invoice Advance
    """
    if not customer:
        return []

    try:
        payment_entries = frappe.db.sql(
            """
            SELECT
                name,
                posting_date,
                mode_of_payment,
                paid_amount,
                base_paid_amount,
                received_amount,
                base_received_amount,
                unallocated_amount,
                reference_no,
                reference_date
            FROM `tabPayment Entry`
            WHERE
                docstatus = 1
                AND payment_type = 'Receive'
                AND party_type = 'Customer'
                AND party = %s
            ORDER BY posting_date ASC, creation ASC
            """,
            customer,
            as_dict=True,
        )
    except Exception:
        payment_entries = []

    output = []

    for pe in payment_entries:
        calc = _kpws_payment_entry_remaining_advance(pe.name)

        if flt(calc.get("remaining_amount")) <= 0:
            continue

        output.append({
            "name": pe.name,
            "posting_date": pe.posting_date,
            "mode_of_payment": pe.mode_of_payment,
            "paid_amount": calc.get("paid_amount"),
            "allocated_amount": calc.get("allocated_amount"),
            "unallocated_amount": calc.get("remaining_amount"),
            "remaining_amount": calc.get("remaining_amount"),
            "core_unallocated_amount": calc.get("core_unallocated_amount"),
            "allocated_from_payment_entry_references": calc.get("allocated_from_payment_entry_references"),
            "allocated_from_sales_invoice_advances": calc.get("allocated_from_sales_invoice_advances"),
            "reference_no": pe.reference_no,
            "reference_date": pe.reference_date,
        })

    return output


def _kpws_customer_advance_balance(customer):
    rows = _kpws_customer_unallocated_advances(customer)
    return flt(sum(flt(row.get("remaining_amount") or row.get("unallocated_amount")) for row in rows), 2)


@frappe.whitelist()
def get_customer_advance_info(customer=None):
    _require_role()

    if not customer:
        return {
            "customer": "",
            "is_advance_customer": 0,
            "advance_type": "",
            "available_advance": 0,
            "remaining_balance": 0,
            "allocated_already": 0,
            "entries": [],
            "enabled": 0,
            "message": "No customer selected.",
        }

    flags = _kpws_get_customer_advance_flags(customer)
    entries = _kpws_customer_unallocated_advances(customer)

    remaining_balance = flt(sum(flt(row.get("remaining_amount") or 0) for row in entries), 2)
    allocated_already = flt(sum(flt(row.get("allocated_amount") or 0) for row in entries), 2)

    # Also include fully-used entries in allocated_already for display accuracy.
    try:
        all_payment_entries = frappe.get_all(
            "Payment Entry",
            filters={
                "docstatus": 1,
                "payment_type": "Receive",
                "party_type": "Customer",
                "party": customer,
            },
            pluck="name",
            limit_page_length=500,
        )

        allocated_already = 0
        for pe_name in all_payment_entries:
            calc = _kpws_payment_entry_remaining_advance(pe_name)
            allocated_already += flt(calc.get("allocated_amount") or 0)

        allocated_already = flt(allocated_already, 2)
    except Exception:
        pass

    settings = _ensure_settings_doc()
    enabled = cint(settings.get("enable_customer_advance_allocation") or 0)

    return {
        "customer": customer,
        "customer_name": frappe.db.get_value("Customer", customer, "customer_name") or customer,
        "is_advance_customer": flags.get("is_advance_customer"),
        "advance_type": flags.get("advance_type"),
        "available_advance": remaining_balance,
        "remaining_balance": remaining_balance,
        "allocated_already": allocated_already,
        "entries": entries[:10],
        "enabled": enabled,
        "message": "Remaining advance available." if remaining_balance > 0 else "No remaining advance balance found.",
    }


def _kpws_allocate_customer_advances_to_invoice(si, customer, amount):
    amount = flt(amount, 2)

    if amount <= 0:
        return 0

    if not customer:
        return 0

    if not si.meta.has_field("advances"):
        frappe.throw(_("Sales Invoice does not have Advances table. Cannot allocate customer advance."))

    flags = _kpws_get_customer_advance_flags(customer)

    if not cint(flags.get("is_advance_customer")):
        return 0

    child_doctype = si.meta.get_field("advances").options
    child_meta = frappe.get_meta(child_doctype)

    allocated = 0

    for pe in _kpws_customer_unallocated_advances(customer):
        if allocated >= amount:
            break

        available = flt(pe.get("remaining_amount") or pe.get("unallocated_amount"))
        if available <= 0:
            continue

        alloc = min(available, amount - allocated)

        row = {}

        if child_meta.has_field("reference_type"):
            row["reference_type"] = "Payment Entry"

        if child_meta.has_field("reference_name"):
            row["reference_name"] = pe.name

        if child_meta.has_field("advance_amount"):
            row["advance_amount"] = available

        if child_meta.has_field("allocated_amount"):
            row["allocated_amount"] = alloc

        if child_meta.has_field("remarks"):
            row["remarks"] = "Allocated from KPWS Pharmacy POS customer advance"

        si.append("advances", row)
        allocated += alloc

    return flt(allocated, 2)


@frappe.whitelist()
def debug_customer_advance_core(customer):
    _require_role()

    if not customer:
        frappe.throw(_("Customer is required."))

    payment_entries = frappe.get_all(
        "Payment Entry",
        filters={
            "docstatus": 1,
            "payment_type": "Receive",
            "party_type": "Customer",
            "party": customer,
        },
        fields=["name", "posting_date", "mode_of_payment", "paid_amount", "unallocated_amount"],
        order_by="posting_date asc, creation asc",
        limit_page_length=500,
    )

    details = []

    for pe in payment_entries:
        calc = _kpws_payment_entry_remaining_advance(pe.name)
        details.append({
            "payment_entry": pe.name,
            "posting_date": pe.posting_date,
            "mode_of_payment": pe.mode_of_payment,
            "paid_amount_field": pe.paid_amount,
            "unallocated_amount_field": pe.unallocated_amount,
            **calc,
        })

    return {
        "customer": customer,
        "customer_name": frappe.db.get_value("Customer", customer, "customer_name") or customer,
        "flags": _kpws_get_customer_advance_flags(customer),
        "advance_info": get_customer_advance_info(customer),
        "payment_entries": details,
    }
'''


JS_PATCH = r'''

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
        "message": "Customer advance balance is now strictly calculated from ERPNext core allocation tables."
    }
