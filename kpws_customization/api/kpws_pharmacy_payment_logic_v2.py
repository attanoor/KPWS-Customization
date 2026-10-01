from pathlib import Path
import textwrap
import frappe


PATCH_MARKER = "# KPWS_PHARMACY_PAYMENT_LOGIC_V2_PATCH"


SERVER_PATCH = r'''

# KPWS_PHARMACY_PAYMENT_LOGIC_V2_PATCH

def _kpws_get_mop_by_names(names):
    for name in names:
        if name and frappe.db.exists("Mode of Payment", name):
            return name
    return None


def _kpws_total_from_items_for_payment(items, price_list, warehouse):
    total = 0
    clean_rows = []

    for row in items:
        item_code = row.get("item_code")
        qty = flt(row.get("qty"))

        if not item_code or qty <= 0:
            continue

        uom = frappe.db.get_value("Item", item_code, "stock_uom")
        rate = _get_item_price(item_code, price_list, nowdate(), uom)

        if flt(row.get("rate")) > 0:
            rate = flt(row.get("rate"))

        clean_rows.append({
            "item_code": item_code,
            "qty": qty,
            "rate": rate,
            "amount": qty * rate,
        })

        total += qty * rate

    return flt(total), clean_rows


def _kpws_payment_modes(settings):
    return {
        "cash": settings.get("cash_mode_of_payment") or settings.get("default_mode_of_payment") or _kpws_get_mop_by_names(["Cash"]),
        "card": settings.get("card_mode_of_payment") or _kpws_get_mop_by_names(["Card", "Credit Card", "Debit Card", "Bank Card"]),
        "panel": settings.get("panel_mode_of_payment") or _kpws_get_mop_by_names(["Panel"]),
        "zakat": settings.get("zakat_mode_of_payment") or _kpws_get_mop_by_names(["Zakat"]),
        "donation": settings.get("donation_mode_of_payment") or _kpws_get_mop_by_names(["Donation"]),
    }


def _kpws_round_amount(value):
    return flt(value, 2)


def _kpws_compute_payment_plan(patient, total, cash_amount=0, card_amount=0):
    settings = _ensure_settings_doc()
    ctx = get_patient_context(patient)

    group = ctx.get("group") or "Cash"
    registration = ctx.get("registration") or {}
    purpose = (registration.get("purpose") or "").strip()
    percentage = flt(registration.get("percentage"))

    modes = _kpws_payment_modes(settings)
    total = _kpws_round_amount(total)
    card_amount = _kpws_round_amount(card_amount)

    rows = []
    warnings = []

    if total <= 0:
        return {
            "total": 0,
            "rows": [],
            "warnings": ["Invoice total is zero."],
            "patient_share": 0,
            "covered_amount": 0,
            "group": group,
            "purpose": purpose,
            "percentage": percentage,
        }

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
        covered_amount = _kpws_round_amount(total * pct / 100)
        patient_share = _kpws_round_amount(total - covered_amount)

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
            cash_part = _kpws_round_amount(patient_share - card_amount)

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
    cash_part = _kpws_round_amount(total - card_amount)

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
        "require_cash_payment",
        "auto_submit_invoice",
        "update_stock",
        "enforce_patient_status",
        "enforce_pharmacy_stock",
        "block_missing_price",
        "apply_registration_percentage_as_discount",
        "allow_manual_rate",
        "print_format",
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

    # Important:
    # Welfare percentage is now handled as Zakat/Donation payment split, not invoice discount.
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
        "print_format": settings.print_format,
        "payment_plan": payment_plan,
        "message": "Sales Invoice created successfully.",
    }
'''


JS_PATCH = r'''

/* KPWS_PHARMACY_PAYMENT_LOGIC_V2_PATCH */

KPWSPharmacyBilling.prototype.renderBilling = function () {
    const root = this.page.main.find("#kpws-billing-tab");

    root.html(`
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

        <div class="kpws-card">
            <div class="kpws-card-title">3. Cart</div>
            <div id="kpws-cart"></div>
        </div>

        <div class="kpws-card">
            <div class="kpws-card-title">4. Payment Logic</div>

            <div class="kpws-grid">
                <div class="kpws-field">
                    <label>Total Invoice Amount</label>
                    <div class="kpws-readonly" id="kpws-final-total">0.00</div>
                </div>
                <div class="kpws-field">
                    <label>Covered by Zakat / Donation / Panel</label>
                    <div class="kpws-readonly" id="kpws-covered-amount">0.00</div>
                </div>
                <div class="kpws-field">
                    <label>Patient Share</label>
                    <div class="kpws-readonly" id="kpws-patient-share">0.00</div>
                </div>
                <div class="kpws-field">
                    <label>Card Amount</label>
                    <input class="kpws-input" type="number" id="kpws-card-amount" min="0" step="0.01" value="0">
                </div>
            </div>

            <div id="kpws-payment-plan" style="margin-top:14px;"></div>

            <div class="kpws-warning" style="margin-top:12px;">
                Cash patients use Cash/Card. Panel patients use Panel. Welfare patients use Zakat/Donation from the submitted registration form, and any remaining amount is collected as Cash/Card.
            </div>

            <div style="margin-top:14px; display:flex; gap:10px; flex-wrap:wrap;">
                <button class="kpws-btn primary" id="kpws-save-draft">Save Draft</button>
                <button class="kpws-btn green" id="kpws-submit-invoice">Submit Invoice</button>
                <button class="kpws-btn light" id="kpws-clear">New / Clear</button>
            </div>
        </div>
    `);

    this.makeBillingControls();
    this.bindBillingEvents();
    this.updateCart();
    this.refreshPaymentPlan();
};

KPWSPharmacyBilling.prototype.makeBillingControls = function () {
    const patientControl = frappe.ui.form.make_control({
        parent: this.page.main.find("#kpws-patient-control").get(0),
        df: {
            label: "Patient",
            fieldtype: "Link",
            options: "Patient",
            fieldname: "patient",
            reqd: 1,
            onchange: () => {
                const patient = patientControl.get_value();
                this.loadPatient(patient);
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
};

KPWSPharmacyBilling.prototype.bindBillingEvents = function () {
    let timer = null;

    this.page.main.find("#kpws-item-search").on("input", () => {
        clearTimeout(timer);
        timer = setTimeout(() => this.searchItems(), 350);
    });

    this.page.main.find("#kpws-card-amount").on("input", () => {
        clearTimeout(timer);
        timer = setTimeout(() => this.refreshPaymentPlan(), 250);
    });

    this.page.main.find("#kpws-save-draft").on("click", () => this.createInvoice(false));
    this.page.main.find("#kpws-submit-invoice").on("click", () => this.createInvoice(true));

    this.page.main.find("#kpws-clear").on("click", () => {
        this.patientContext = null;
        this.cart = [];
        this.paymentPlan = null;
        this.renderBilling();
    });
};

KPWSPharmacyBilling.prototype.loadPatient = async function (patient) {
    if (!patient) return;

    try {
        const r = await this.call("get_patient_context", { patient });
        this.patientContext = r.message;
        this.cart = [];
        this.paymentPlan = null;

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
};

KPWSPharmacyBilling.prototype.refreshPaymentPlan = async function () {
    const total = this.total ? this.total() : 0;
    const cardAmount = Number(this.page.main.find("#kpws-card-amount").val() || 0);

    this.page.main.find("#kpws-final-total").text(total.toFixed(2));

    if (!this.patientContext || total <= 0) {
        this.page.main.find("#kpws-covered-amount").text("0.00");
        this.page.main.find("#kpws-patient-share").text("0.00");
        this.page.main.find("#kpws-payment-plan").html(`<div class="kpws-warning">Add items to calculate payment split.</div>`);
        return;
    }

    const r = await this.call("get_payment_plan", {
        patient: this.patientContext.patient,
        total: total,
        card_amount: cardAmount
    });

    this.paymentPlan = r.message || {};
    this.renderPaymentPlan();
};

KPWSPharmacyBilling.prototype.renderPaymentPlan = function () {
    const plan = this.paymentPlan || {};
    const rows = plan.rows || [];
    const warnings = plan.warnings || [];

    this.page.main.find("#kpws-covered-amount").text(Number(plan.covered_amount || 0).toFixed(2));
    this.page.main.find("#kpws-patient-share").text(Number(plan.patient_share || 0).toFixed(2));

    let html = "";

    if (warnings.length) {
        html += warnings.map(w => `<div class="kpws-warning">${frappe.utils.escape_html(w)}</div>`).join("");
    }

    if (!rows.length) {
        html += `<div class="kpws-warning">No payment rows calculated.</div>`;
    } else {
        html += `
            <table class="kpws-table">
                <thead>
                    <tr>
                        <th>Payment Type</th>
                        <th>Mode of Payment</th>
                        <th style="width:140px;">Amount</th>
                    </tr>
                </thead>
                <tbody>
                    ${rows.map(row => `
                        <tr>
                            <td><b>${frappe.utils.escape_html(row.label || row.role || "")}</b></td>
                            <td>${frappe.utils.escape_html(row.mode_of_payment || "Missing in Settings")}</td>
                            <td>${Number(row.amount || 0).toFixed(2)}</td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        `;
    }

    this.page.main.find("#kpws-payment-plan").html(html);
};

KPWSPharmacyBilling.prototype.updateCart = function () {
    const root = this.page.main.find("#kpws-cart");

    if (!this.cart.length) {
        root.html(`<div class="kpws-warning">No items added yet.</div>`);
        this.refreshPaymentPlan();
        return;
    }

    root.html(`
        <table class="kpws-table">
            <thead>
                <tr>
                    <th>Item</th>
                    <th style="width:100px;">Stock</th>
                    <th style="width:120px;">Qty</th>
                    <th style="width:120px;">Rate</th>
                    <th style="width:120px;">Amount</th>
                    <th style="width:80px;"></th>
                </tr>
            </thead>
            <tbody>
                ${this.cart.map((row, i) => `
                    <tr>
                        <td>
                            <b>${frappe.utils.escape_html(row.item_name || row.item_code)}</b>
                            <div style="font-size:12px;color:#64748b;">${frappe.utils.escape_html(row.item_code)}</div>
                        </td>
                        <td>${row.available_qty}</td>
                        <td><input class="kpws-input kpws-cart-qty" data-index="${i}" type="number" min="1" value="${row.qty}"></td>
                        <td>${row.rate}</td>
                        <td>${(row.qty * row.rate).toFixed(2)}</td>
                        <td><button class="kpws-btn red" data-remove="${i}">X</button></td>
                    </tr>
                `).join("")}
            </tbody>
        </table>
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

KPWSPharmacyBilling.prototype.updateTotals = function () {
    this.refreshPaymentPlan();
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

        const data = r.message;
        frappe.show_alert({ message: data.message, indicator: "green" }, 8);
        frappe.set_route("Form", "Sales Invoice", data.name);
    } catch (e) {
        frappe.dom.unfreeze();
    }
};

KPWSPharmacyBilling.prototype.renderSettings = function () {
    const root = this.page.main.find("#kpws-settings-tab");

    root.html(`
        <div class="kpws-card">
            <div class="kpws-card-title">Pharmacy Billing Settings</div>

            <div class="kpws-grid-2">
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
                <div id="kpws-setting-print-format"></div>
            </div>

            <div class="kpws-card-title" style="margin-top:18px;">Controls</div>

            <div class="kpws-grid">
                ${this.checkboxHTML("require_cash_payment", "Require Cash Payment")}
                ${this.checkboxHTML("auto_submit_invoice", "Auto Submit Invoice")}
                ${this.checkboxHTML("update_stock", "Update Stock")}
                ${this.checkboxHTML("enforce_patient_status", "Block Invalid Patient Status")}
                ${this.checkboxHTML("enforce_pharmacy_stock", "Block No Stock")}
                ${this.checkboxHTML("block_missing_price", "Block Missing Price")}
                ${this.checkboxHTML("allow_manual_rate", "Allow Manual Rate")}
            </div>

            <div class="kpws-warning" style="margin-top:14px;">
                Welfare percentage is now treated as payment split through Zakat/Donation, not as invoice discount. Remaining patient share goes to Cash/Card.
            </div>

            <div style="margin-top:16px;">
                <button class="kpws-btn green" id="kpws-save-settings">Save Settings</button>
            </div>
        </div>
    `);

    this.makeSettingsControls();
    root.find("#kpws-save-settings").on("click", () => this.saveSettings());
};

KPWSPharmacyBilling.prototype.makeSettingsControls = function () {
    const make = (id, label, fieldtype, options, fieldname) => {
        const control = frappe.ui.form.make_control({
            parent: this.page.main.find(id).get(0),
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
    make("#kpws-setting-print-format", "Receipt Print Format", "Link", "Print Format", "print_format");
};

KPWSPharmacyBilling.prototype.saveSettings = async function () {
    const values = {
        company: this.companyControl.get_value(),
        pharmacy_warehouse: this.pharmacy_warehouseControl.get_value(),
        default_cash_customer: this.default_cash_customerControl.get_value(),

        cash_mode_of_payment: this.cash_mode_of_paymentControl.get_value(),
        card_mode_of_payment: this.card_mode_of_paymentControl.get_value(),
        panel_mode_of_payment: this.panel_mode_of_paymentControl.get_value(),
        zakat_mode_of_payment: this.zakat_mode_of_paymentControl.get_value(),
        donation_mode_of_payment: this.donation_mode_of_paymentControl.get_value(),

        cash_price_list: this.cash_price_listControl.get_value(),
        welfare_price_list: this.welfare_price_listControl.get_value(),
        panel_price_list: this.panel_price_listControl.get_value(),
        print_format: this.print_formatControl.get_value()
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
'''


def _append_once(path, patch, marker):
    p = Path(path)
    text = p.read_text()
    if marker not in text:
        p.write_text(text + "\n\n" + patch)
        return True
    return False


def _copy_js_to_standard_path(app_path):
    src = app_path / "page" / "kpws_pharmacy_billing" / "kpws_pharmacy_billing.js"
    dst_dir = app_path / "kpws_customization" / "page" / "kpws_pharmacy_billing"
    dst_dir.mkdir(parents=True, exist_ok=True)

    dst = dst_dir / "kpws_pharmacy_billing.js"

    if src.exists():
        dst.write_text(src.read_text())

    init1 = app_path / "kpws_customization" / "page" / "__init__.py"
    init2 = dst_dir / "__init__.py"
    init1.parent.mkdir(parents=True, exist_ok=True)
    init1.touch(exist_ok=True)
    init2.touch(exist_ok=True)

    json_file = dst_dir / "kpws_pharmacy_billing.json"
    if not json_file.exists():
        json_file.write_text('''{
  "doctype": "Page",
  "name": "kpws-pharmacy-billing",
  "page_name": "kpws-pharmacy-billing",
  "title": "KPWS Pharmacy Billing",
  "module": "KPWS Customization",
  "standard": "Yes"
}
''')

    return dst


def _ensure_settings_fields():
    from kpws_customization.api.kpws_pharmacy_billing_desk import SETTINGS_DOCTYPE, _ensure_settings_doc

    if not frappe.db.exists("DocType", SETTINGS_DOCTYPE):
        from kpws_customization.api.kpws_pharmacy_billing_desk import install
        install()

    dt = frappe.get_doc("DocType", SETTINGS_DOCTYPE)
    existing = {df.fieldname for df in dt.fields}

    payment_insert_after = "default_mode_of_payment"

    new_fields = [
        {
            "fieldname": "cash_mode_of_payment",
            "label": "Cash Mode of Payment",
            "fieldtype": "Link",
            "options": "Mode of Payment",
            "insert_after": payment_insert_after,
        },
        {
            "fieldname": "card_mode_of_payment",
            "label": "Card Mode of Payment",
            "fieldtype": "Link",
            "options": "Mode of Payment",
            "insert_after": "cash_mode_of_payment",
        },
        {
            "fieldname": "panel_mode_of_payment",
            "label": "Panel Mode of Payment",
            "fieldtype": "Link",
            "options": "Mode of Payment",
            "insert_after": "card_mode_of_payment",
        },
        {
            "fieldname": "zakat_mode_of_payment",
            "label": "Zakat Mode of Payment",
            "fieldtype": "Link",
            "options": "Mode of Payment",
            "insert_after": "panel_mode_of_payment",
        },
        {
            "fieldname": "donation_mode_of_payment",
            "label": "Donation Mode of Payment",
            "fieldtype": "Link",
            "options": "Mode of Payment",
            "insert_after": "zakat_mode_of_payment",
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

    doc = _ensure_settings_doc()

    defaults = {
        "cash_mode_of_payment": ["Cash"],
        "card_mode_of_payment": ["Card", "Credit Card", "Debit Card", "Bank Card"],
        "panel_mode_of_payment": ["Panel"],
        "zakat_mode_of_payment": ["Zakat"],
        "donation_mode_of_payment": ["Donation"],
    }

    for fieldname, names in defaults.items():
        if not doc.get(fieldname):
            for name in names:
                if frappe.db.exists("Mode of Payment", name):
                    doc.set(fieldname, name)
                    break

    # Important: stop old invoice-discount behavior for welfare percentage.
    if doc.meta.has_field("apply_registration_percentage_as_discount"):
        doc.apply_registration_percentage_as_discount = 0

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return added


@frappe.whitelist()
def install():
    app_path = Path(frappe.get_app_path("kpws_customization"))

    api_file = app_path / "api" / "kpws_pharmacy_billing_desk.py"
    server_changed = _append_once(api_file, SERVER_PATCH, PATCH_MARKER)

    # Patch both possible page JS locations
    js_files = []

    normal_js = app_path / "page" / "kpws_pharmacy_billing" / "kpws_pharmacy_billing.js"
    if normal_js.exists():
        js_files.append(normal_js)

    standard_js = _copy_js_to_standard_path(app_path)
    if standard_js.exists():
        js_files.append(standard_js)

    js_changed = []
    for js in js_files:
        if _append_once(js, JS_PATCH, "KPWS_PHARMACY_PAYMENT_LOGIC_V2_PATCH"):
            js_changed.append(str(js))

    added_fields = _ensure_settings_fields()

    frappe.clear_cache()
    frappe.db.commit()

    return {
        "ok": True,
        "server_changed": server_changed,
        "js_changed": js_changed,
        "settings_fields_added": added_fields,
        "message": "Pharmacy payment logic v2 installed."
    }
