from pathlib import Path
import frappe


PATCH_MARKER = "KPWS_WALKIN_PHARMACY_POS_V17_PATCH"


SERVER_PATCH = r'''

# KPWS_WALKIN_PHARMACY_POS_V17_PATCH

def _kpws_set_walkin_fields(si, walkin_name=None, walkin_mr_number=None):
    """
    Store walk-in patient details on Sales Invoice if matching custom fields exist.
    KPWS already uses walkin_customer_name / walkin_mr_number in some flows.
    """
    field_values = {
        "walkin_customer_name": walkin_name,
        "custom_walkin_customer_name": walkin_name,
        "walkin_patient_name": walkin_name,
        "custom_walkin_patient_name": walkin_name,

        "walkin_mr_number": walkin_mr_number,
        "custom_walkin_mr_number": walkin_mr_number,
        "walkin_mr_no": walkin_mr_number,
        "custom_walkin_mr_no": walkin_mr_number,

        "is_walkin": 1,
        "custom_is_walkin": 1,
        "is_walkin_patient": 1,
        "custom_is_walkin_patient": 1,
    }

    for fieldname, value in field_values.items():
        if _has_field("Sales Invoice", fieldname):
            try:
                si.set(fieldname, value)
            except Exception:
                pass


def _kpws_walkin_context():
    settings = _ensure_settings_doc()

    if not settings.default_cash_customer:
        frappe.throw(_("Default Cash Customer is required for Walk-in Patient billing. Please set it in Settings."))

    if not settings.cash_price_list:
        frappe.throw(_("Cash Price List is required for Walk-in Patient billing. Please set it in Settings."))

    return {
        "patient": None,
        "patient_name": "Walk-in Patient",
        "mr_number": "",
        "patient_customer": None,
        "bill_to_customer": settings.default_cash_customer,
        "group": "Walk-in",
        "price_list": settings.cash_price_list,
        "status": {
            "blocked": False,
            "indicator": "green",
            "title": "Walk-in Cash Billing",
            "message": "Walk-in patient billing is allowed. Payment will be collected through Cash/Card.",
        },
        "registration": {},
        "settings": _settings_dict(settings),
    }


def _kpws_compute_walkin_payment_plan(total=0, card_amount=0):
    settings = _ensure_settings_doc()
    total = flt(total, 2)
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


@frappe.whitelist()
def get_walkin_context():
    _require_role()
    return _kpws_walkin_context()


@frappe.whitelist()
def get_walkin_payment_plan(total=0, card_amount=0):
    _require_role()
    return _kpws_compute_walkin_payment_plan(total=flt(total), card_amount=flt(card_amount))


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
    invoice_total = sum(flt(row["qty"]) * flt(row["rate"]) for row in clean_items)

    if is_walkin:
        payment_plan = _kpws_compute_walkin_payment_plan(
            total=invoice_total,
            card_amount=card_amount,
        )
    else:
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
    _set_if_has(si, "custom_kpws_purpose", registration.get("purpose") if not is_walkin else "Cash")
    _set_if_has(si, "custom_kpws_approved_percentage", percentage)

    si.insert(ignore_permissions=True)

    submit_now = cint(payload.get("submit")) or cint(settings.auto_submit_invoice)

    if submit_now:
        si.submit()

    print_group = "Cash" if is_walkin else group

    return {
        "ok": True,
        "name": si.name,
        "docstatus": si.docstatus,
        "route": f"/app/sales-invoice/{si.name}",
        "customer_group": group,
        "print_format": _kpws_group_print_format(settings, print_group),
        "payment_plan": payment_plan,
        "walkin": bool(is_walkin),
        "message": "Walk-in invoice created successfully." if is_walkin else "Sales Invoice created successfully.",
    }


@frappe.whitelist()
def search_return_invoices(txt=""):
    _require_role()

    txt = (txt or "").strip()

    if not txt:
        return []

    values = {
        "txt": f"%{txt}%",
        "exact": txt,
    }

    invoice_names = []
    seen = set()

    def add(name):
        if name and name not in seen:
            seen.add(name)
            invoice_names.append(name)

    direct_conditions = [
        "si.name LIKE %(txt)s",
        "si.customer LIKE %(txt)s",
        "si.customer_name LIKE %(txt)s",
    ]

    for fieldname in [
        "custom_kpws_patient_billing_group",
        "custom_kpws_prf",
        "custom_kpws_purpose",
        "walkin_customer_name",
        "custom_walkin_customer_name",
        "walkin_patient_name",
        "custom_walkin_patient_name",
        "walkin_mr_number",
        "custom_walkin_mr_number",
        "walkin_mr_no",
        "custom_walkin_mr_no",
    ]:
        if _has_field("Sales Invoice", fieldname):
            direct_conditions.append(f"si.`{fieldname}` LIKE %(txt)s")

    is_return_condition = "IFNULL(si.is_return, 0) = 0" if _has_field("Sales Invoice", "is_return") else "1=1"

    rows = frappe.db.sql(
        f"""
        SELECT si.name
        FROM `tabSales Invoice` si
        WHERE
            si.docstatus = 1
            AND {is_return_condition}
            AND ({' OR '.join(direct_conditions)})
        ORDER BY si.posting_date DESC, si.modified DESC
        LIMIT 30
        """,
        values,
        as_dict=True,
    )

    for row in rows:
        add(row.name)

    join_condition = _kpws_invoice_patient_join_condition()

    if join_condition:
        patient_conditions = _kpws_sql_conditions_for_patient_search(txt)

        rows = frappe.db.sql(
            f"""
            SELECT DISTINCT si.name
            FROM `tabSales Invoice` si
            INNER JOIN `tabPatient` p
                ON ({join_condition})
            WHERE
                si.docstatus = 1
                AND {is_return_condition}
                AND ({patient_conditions})
            ORDER BY si.posting_date DESC, si.modified DESC
            LIMIT 30
            """,
            values,
            as_dict=True,
        )

        for row in rows:
            add(row.name)

    if frappe.db.exists("Sales Invoice", txt):
        try:
            si = frappe.get_doc("Sales Invoice", txt)
            if si.docstatus == 1 and not cint(si.get("is_return")):
                add(si.name)
        except Exception:
            pass

    output = []

    for name in invoice_names[:30]:
        try:
            summary = _kpws_invoice_summary(name)
            output.append(summary)
        except Exception as e:
            output.append({
                "name": name,
                "posting_date": "",
                "customer": "",
                "customer_name": "",
                "patient": "",
                "patient_name": "",
                "mr_number": "",
                "billing_group": "",
                "grand_total": 0,
                "returnable_item_count": 0,
                "returnable_amount": 0,
                "error": str(e),
            })

    return output
'''


JS_PATCH = r'''

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
        "message": "Walk-in Patient mode added to Pharmacy POS."
    }
