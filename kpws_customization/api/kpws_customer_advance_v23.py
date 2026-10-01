from pathlib import Path
import frappe


PATCH_MARKER = "KPWS_CUSTOMER_ADVANCE_V23_PATCH"


SERVER_PATCH = r'''

# KPWS_CUSTOMER_ADVANCE_V23_PATCH

def _kpws_customer_has_field(fieldname):
    try:
        return frappe.get_meta("Customer").has_field(fieldname)
    except Exception:
        return False


def _kpws_get_customer_advance_flags(customer):
    if not customer or not frappe.db.exists("Customer", customer):
        return {
            "is_advance_customer": 0,
            "advance_type": "",
        }

    is_advance = 0
    advance_type = ""

    if _kpws_customer_has_field("custom_kpws_is_advance_customer"):
        is_advance = cint(frappe.db.get_value("Customer", customer, "custom_kpws_is_advance_customer"))

    if _kpws_customer_has_field("custom_kpws_advance_type"):
        advance_type = frappe.db.get_value("Customer", customer, "custom_kpws_advance_type") or ""

    return {
        "is_advance_customer": is_advance,
        "advance_type": advance_type,
    }


def _kpws_customer_unallocated_advances(customer):
    if not customer:
        return []

    try:
        rows = frappe.db.sql(
            """
            SELECT
                name,
                posting_date,
                mode_of_payment,
                paid_amount,
                unallocated_amount,
                reference_no,
                reference_date
            FROM `tabPayment Entry`
            WHERE
                docstatus = 1
                AND payment_type = 'Receive'
                AND party_type = 'Customer'
                AND party = %s
                AND IFNULL(unallocated_amount, 0) > 0
            ORDER BY posting_date ASC, creation ASC
            """,
            customer,
            as_dict=True,
        )
    except Exception:
        rows = []

    return rows


def _kpws_customer_advance_balance(customer):
    rows = _kpws_customer_unallocated_advances(customer)
    return flt(sum(flt(row.get("unallocated_amount")) for row in rows), 2)


@frappe.whitelist()
def get_customer_advance_info(customer=None):
    _require_role()

    if not customer:
        return {
            "customer": "",
            "is_advance_customer": 0,
            "advance_type": "",
            "available_advance": 0,
            "entries": [],
            "enabled": 0,
            "message": "No customer selected.",
        }

    flags = _kpws_get_customer_advance_flags(customer)
    entries = _kpws_customer_unallocated_advances(customer)
    balance = flt(sum(flt(row.get("unallocated_amount")) for row in entries), 2)

    settings = _ensure_settings_doc()
    enabled = cint(settings.get("enable_customer_advance_allocation") or 0)

    return {
        "customer": customer,
        "customer_name": frappe.db.get_value("Customer", customer, "customer_name") or customer,
        "is_advance_customer": flags.get("is_advance_customer"),
        "advance_type": flags.get("advance_type"),
        "available_advance": balance,
        "entries": entries[:10],
        "enabled": enabled,
        "message": "Advance available." if balance > 0 else "No unallocated advance found.",
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

        available = flt(pe.get("unallocated_amount"))
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


def _kpws_group_print_format(settings, group):
    group = group or "Cash"

    if group == "Walk-in":
        return settings.get("cash_print_format") or settings.get("print_format")

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

        "cash_return_print_format",
        "welfare_return_print_format",
        "panel_return_print_format",
        "walkin_return_print_format",

        "enable_customer_advance_allocation",

        "require_cash_payment",
        "auto_submit_invoice",
        "update_stock",
        "enforce_patient_status",
        "enforce_pharmacy_stock",
        "block_missing_price",
        "apply_registration_percentage_as_discount",
        "allow_manual_rate",
    ]

    out = {field: doc.get(field) for field in fields}
    out["settings_admin"] = 1 if frappe.session.user == "Administrator" else 0
    return out


@frappe.whitelist()
def create_invoice(payload):
    _require_role()

    payload = _json(payload)
    settings = _ensure_settings_doc()

    is_walkin = cint(payload.get("is_walkin"))
    walkin_name = (payload.get("walkin_name") or "").strip()
    walkin_mr_number = (payload.get("walkin_mr_number") or "").strip()

    patient = payload.get("patient")
    items = _list(payload.get("items"))

    if not items:
        frappe.throw(_("Please add at least one item."))

    if is_walkin:
        if not walkin_name:
            frappe.throw(_("Please enter Walk-in Patient Name."))

        if not walkin_mr_number:
            frappe.throw(_("Please enter Walk-in MR Number."))

        ctx = _kpws_walkin_context()
        group = "Walk-in"
        bill_to_customer = settings.default_cash_customer
        price_list = settings.cash_price_list
        registration = {}
        status = {"blocked": False}

    else:
        if not patient:
            frappe.throw(_("Please select Patient."))

        ctx = get_patient_context(patient)
        status = ctx.get("status") or {}

        if cint(settings.enforce_patient_status) and status.get("blocked"):
            frappe.throw(status.get("message") or _("Patient billing status is not valid."))

        group = ctx.get("group") or "Cash"
        bill_to_customer = payload.get("bill_to_customer") or ctx.get("bill_to_customer")
        price_list = payload.get("price_list") or ctx.get("price_list")
        registration = ctx.get("registration") or {}

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

    if is_walkin:
        _kpws_set_walkin_fields(si, walkin_name=walkin_name, walkin_mr_number=walkin_mr_number)
    else:
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

    percentage = flt(registration.get("percentage"))
    card_amount = flt(payload.get("card_amount"))
    invoice_total = flt(sum(flt(row["qty"]) * flt(row["rate"]) for row in clean_items), 2)

    use_customer_advance = cint(payload.get("use_customer_advance")) and cint(settings.get("enable_customer_advance_allocation") or 0)
    requested_advance_amount = flt(payload.get("advance_amount"))

    customer_advance_allocated = 0
    customer_advance_available = 0

    if use_customer_advance:
        advance_info = get_customer_advance_info(bill_to_customer)
        customer_advance_available = flt(advance_info.get("available_advance"))
        is_advance_customer = cint(advance_info.get("is_advance_customer"))

        if is_advance_customer and customer_advance_available > 0:
            if requested_advance_amount <= 0:
                requested_advance_amount = invoice_total

            customer_advance_allocated = min(invoice_total, requested_advance_amount, customer_advance_available)

    payment_plan_total = flt(invoice_total - customer_advance_allocated, 2)
    if payment_plan_total < 0:
        payment_plan_total = 0

    if is_walkin:
        payment_plan = _kpws_compute_walkin_payment_plan(
            total=payment_plan_total,
            card_amount=card_amount,
        )
    else:
        payment_plan = _kpws_compute_payment_plan(
            patient=patient,
            total=payment_plan_total,
            card_amount=card_amount,
        )

    payment_rows = payment_plan.get("rows") or []
    warnings = payment_plan.get("warnings") or []

    if warnings:
        frappe.throw("<br>".join(warnings), title=_("KPWS Payment Settings Missing"))

    if customer_advance_allocated > 0:
        actually_allocated = _kpws_allocate_customer_advances_to_invoice(
            si=si,
            customer=bill_to_customer,
            amount=customer_advance_allocated,
        )

        if actually_allocated <= 0:
            frappe.throw(_("Unable to allocate customer advance. Please check Payment Entry unallocated balance."))

        customer_advance_allocated = actually_allocated

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
    else:
        # If fully paid through customer advance, keep invoice non-POS.
        si.is_pos = 0

    _set_if_has(si, "custom_kpws_patient_billing_group", group)
    _set_if_has(si, "custom_kpws_prf", registration.get("name"))
    _set_if_has(si, "custom_kpws_purpose", registration.get("purpose") if not is_walkin else "Cash")
    _set_if_has(si, "custom_kpws_approved_percentage", percentage)

    si.insert(ignore_permissions=True)

    submit_now = cint(payload.get("submit")) or cint(settings.auto_submit_invoice)

    if submit_now:
        si.submit()

    print_group = "Cash" if is_walkin else group

    payment_plan["invoice_total"] = invoice_total
    payment_plan["customer_advance_allocated"] = customer_advance_allocated
    payment_plan["customer_advance_available_before"] = customer_advance_available

    return {
        "ok": True,
        "name": si.name,
        "docstatus": si.docstatus,
        "route": f"/app/sales-invoice/{si.name}",
        "customer_group": group,
        "print_format": _kpws_group_print_format(settings, print_group),
        "payment_plan": payment_plan,
        "walkin": bool(is_walkin),
        "customer_advance_allocated": customer_advance_allocated,
        "message": "Walk-in invoice created successfully." if is_walkin else "Sales Invoice created successfully.",
    }
'''


JS_PATCH = r'''

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


def _ensure_customer_fields():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    create_custom_fields({
        "Customer": [
            {
                "fieldname": "custom_kpws_advance_section",
                "label": "KPWS Advance Billing",
                "fieldtype": "Section Break",
                "insert_after": "is_internal_customer",
            },
            {
                "fieldname": "custom_kpws_is_advance_customer",
                "label": "Is Advance Customer",
                "fieldtype": "Check",
                "insert_after": "custom_kpws_advance_section",
                "description": "Enable this customer for advance balance allocation on KPWS Pharmacy POS.",
            },
            {
                "fieldname": "custom_kpws_advance_type",
                "label": "Advance Type",
                "fieldtype": "Select",
                "options": "\\nPersonal Advance\\nPanel Advance",
                "insert_after": "custom_kpws_is_advance_customer",
            },
            {
                "fieldname": "custom_kpws_advance_notes",
                "label": "Advance Notes",
                "fieldtype": "Small Text",
                "insert_after": "custom_kpws_advance_type",
            },
        ]
    }, ignore_validate=True)

    frappe.db.commit()
    frappe.clear_cache(doctype="Customer")


def _ensure_settings_field():
    from kpws_customization.api.kpws_pharmacy_billing_desk import SETTINGS_DOCTYPE

    dt = frappe.get_doc("DocType", SETTINGS_DOCTYPE)
    existing = {df.fieldname for df in dt.fields}

    if "enable_customer_advance_allocation" not in existing:
        dt.append("fields", {
            "fieldname": "enable_customer_advance_allocation",
            "label": "Enable Customer Advance Allocation",
            "fieldtype": "Check",
            "default": "1",
            "insert_after": "allow_manual_rate",
        })
        dt.save(ignore_permissions=True)

    frappe.db.set_single_value(SETTINGS_DOCTYPE, "enable_customer_advance_allocation", 1)

    frappe.db.commit()
    frappe.clear_cache(doctype=SETTINGS_DOCTYPE)


@frappe.whitelist()
def install():
    app_path = Path(frappe.get_app_path("kpws_customization"))

    _ensure_customer_fields()
    _ensure_settings_field()

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
        "message": "Customer advance billing installed for Pharmacy POS."
    }


@frappe.whitelist()
def test_customer_advance(customer):
    from kpws_customization.api.kpws_pharmacy_billing_desk import get_customer_advance_info
    return get_customer_advance_info(customer)
