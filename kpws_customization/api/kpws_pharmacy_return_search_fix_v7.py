from pathlib import Path
import frappe


PATCH_MARKER = "KPWS_PHARMACY_RETURN_SEARCH_FIX_V7_PATCH"


SERVER_PATCH = r'''

# KPWS_PHARMACY_RETURN_SEARCH_FIX_V7_PATCH

def _kpws_has_column(table, column):
    try:
        return bool(frappe.db.has_column(table, column))
    except Exception:
        return False


def _kpws_sql_conditions_for_patient_search(txt):
    meta = frappe.get_meta("Patient")
    conditions = ["p.name LIKE %(txt)s"]

    for fieldname in [
        "patient_name",
        "full_name",
        "first_name",
        "middle_name",
        "last_name",
        "custom_reference_number",
        "custom_mr_number",
        "mr_number",
        "patient_mr_number",
        "mobile",
        "mobile_no",
        "phone",
        "contact_no",
        "custom_contact_no",
        "cnic",
        "custom_cnic",
    ]:
        if meta.has_field(fieldname):
            conditions.append(f"p.`{fieldname}` LIKE %(txt)s")

    return " OR ".join(conditions)


def _kpws_invoice_patient_join_condition():
    joins = []
    for fieldname in PATIENT_FIELDS_ON_SI:
        if _has_field("Sales Invoice", fieldname):
            joins.append(f"si.`{fieldname}` = p.name")

    if not joins:
        return None

    return " OR ".join(joins)


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

    # 1. Direct Sales Invoice search.
    direct_conditions = [
        "si.name LIKE %(txt)s",
        "si.customer LIKE %(txt)s",
        "si.customer_name LIKE %(txt)s",
    ]

    for fieldname in [
        "custom_kpws_patient_billing_group",
        "custom_kpws_prf",
        "custom_kpws_purpose",
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

    # 2. Search via Patient fields, MR number, KPWS number, patient name.
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

    # 3. Exact invoice fallback.
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
            # Do not hide invoices with zero returnable items.
            # Let the UI show the real reason.
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


@frappe.whitelist()
def debug_return_search(txt=""):
    _require_role()

    txt = (txt or "").strip()

    direct = frappe.db.sql(
        """
        SELECT name, customer, customer_name, docstatus, is_return, posting_date, grand_total
        FROM `tabSales Invoice`
        WHERE name LIKE %(txt)s OR customer LIKE %(txt)s OR customer_name LIKE %(txt)s
        ORDER BY modified DESC
        LIMIT 10
        """,
        {"txt": f"%{txt}%"},
        as_dict=True,
    )

    return {
        "txt": txt,
        "direct_sales_invoice_matches": direct,
        "api_result": search_return_invoices(txt),
        "sales_invoice_patient_fields_found": [
            fieldname for fieldname in PATIENT_FIELDS_ON_SI
            if _has_field("Sales Invoice", fieldname)
        ],
    }
'''


JS_PATCH = r'''

/* KPWS_PHARMACY_RETURN_SEARCH_FIX_V7_PATCH */

(function () {
    if (typeof KPWSPharmacyBillingPOS === "undefined") {
        console.warn("KPWSPharmacyBillingPOS not found. Return search fix skipped.");
        return;
    }

    KPWSPharmacyBillingPOS.prototype.renderReturn = function () {
        const root = this.page.main.find("#kpws-return-tab");

        root.html(`
            <div class="kpws-pos-main">
                <div class="kpws-pos-left">
                    <div class="kpws-pos-card">
                        <div class="kpws-pos-card-title">Search Invoice for Return</div>

                        <div class="kpws-pos-grid-2">
                            <div class="kpws-pos-field">
                                <label>Invoice No / MR No / KPWS No / Patient Name</label>
                                <input class="kpws-pos-input" id="kpws-return-search" placeholder="Type invoice number, MR number, KPWS number or patient name...">
                            </div>

                            <div class="kpws-pos-field">
                                <label>&nbsp;</label>
                                <button class="kpws-pos-btn primary" id="kpws-return-search-btn" style="width:100%;">
                                    Search Invoice
                                </button>
                            </div>
                        </div>

                        <div id="kpws-return-search-results" class="kpws-pos-search-results"></div>
                    </div>

                    <div class="kpws-pos-card">
                        <div class="kpws-pos-card-title">Returnable Items</div>
                        <div id="kpws-return-items">
                            <div class="kpws-pos-cart-empty">Search and select an invoice first.</div>
                        </div>
                    </div>
                </div>

                <div class="kpws-pos-right">
                    <div class="kpws-pos-card">
                        <div class="kpws-pos-card-title">Selected Invoice</div>
                        <div id="kpws-return-summary">
                            <div class="kpws-pos-cart-empty">No invoice selected.</div>
                        </div>
                    </div>

                    <div class="kpws-pos-card">
                        <div class="kpws-pos-card-title">Return Actions</div>

                        <div class="kpws-pos-total-panel">
                            <div class="kpws-pos-total-row">
                                <span>Return Amount</span>
                                <span id="kpws-return-total">0.00</span>
                            </div>
                        </div>

                        <div id="kpws-return-message"></div>

                        <div class="kpws-pos-actions">
                            <button class="kpws-pos-btn dark" id="kpws-full-return">Full Return</button>
                            <button class="kpws-pos-btn success" id="kpws-create-return">Create Return & Print</button>
                            <button class="kpws-pos-btn light" id="kpws-clear-return">Clear Return</button>
                        </div>
                    </div>
                </div>
            </div>
        `);

        this.selectedReturnInvoice = null;
        this.returnInvoiceDetails = null;

        this.bindReturnEvents();
    };

    KPWSPharmacyBillingPOS.prototype.bindReturnEvents = function () {
        let timer = null;

        this.page.main.find("#kpws-return-search").on("input", () => {
            clearTimeout(timer);
            timer = setTimeout(() => this.searchReturnInvoices(), 650);
        });

        this.page.main.find("#kpws-return-search").on("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                this.searchReturnInvoices();
            }
        });

        this.page.main.find("#kpws-return-search-btn").on("click", () => {
            this.searchReturnInvoices();
        });

        this.page.main.find("#kpws-full-return").on("click", () => this.setFullReturnQty());
        this.page.main.find("#kpws-create-return").on("click", () => this.createReturnInvoice());
        this.page.main.find("#kpws-clear-return").on("click", () => this.renderReturn());
    };

    KPWSPharmacyBillingPOS.prototype.searchReturnInvoices = async function () {
        const txt = this.page.main.find("#kpws-return-search").val();

        if (!txt || txt.length < 2) {
            this.page.main.find("#kpws-return-search-results").html(`
                <div class="kpws-pos-warning">Enter at least 2 characters to search.</div>
            `);
            return;
        }

        this.page.main.find("#kpws-return-search-results").html(`
            <div class="kpws-pos-warning">Searching invoices...</div>
        `);

        try {
            const r = await this.call("search_return_invoices", { txt });
            const rows = r.message || [];

            if (!rows.length) {
                this.page.main.find("#kpws-return-search-results").html(`
                    <div class="kpws-pos-warning">
                        No submitted invoice found. Try exact Sales Invoice number or MR number.
                    </div>
                `);
                return;
            }

            this.page.main.find("#kpws-return-search-results").html(`
                ${rows.map(row => {
                    const disabled = Number(row.returnable_item_count || 0) <= 0 ? "disabled" : "";
                    const warning = Number(row.returnable_item_count || 0) <= 0
                        ? `<div class="kpws-pos-warning">No returnable item found or this invoice may already be fully returned.</div>`
                        : "";

                    return `
                        <div class="kpws-pos-product">
                            <div>
                                <div class="kpws-pos-product-name">${this.esc(row.name)}</div>
                                <div class="kpws-pos-product-code">
                                    ${this.esc(row.patient_name || row.customer_name || row.customer || "")}
                                    ${row.mr_number ? " | MR: " + this.esc(row.mr_number) : ""}
                                </div>
                                <div class="kpws-pos-product-code">
                                    Date: ${this.esc(row.posting_date || "")} | Group: ${this.esc(row.billing_group || "-")}
                                </div>
                                ${row.error ? `<div class="kpws-pos-warning">${this.esc(row.error)}</div>` : ""}
                                ${warning}
                            </div>

                            <div class="kpws-pos-product-meta">Total<br>${Number(row.grand_total || 0).toFixed(2)}</div>
                            <div class="kpws-pos-product-meta">Returnable<br>${Number(row.returnable_amount || 0).toFixed(2)}</div>

                            <button class="kpws-pos-btn primary" data-return-invoice="${this.esc(row.name)}" ${disabled}>
                                Select
                            </button>
                        </div>
                    `;
                }).join("")}
            `);

            this.page.main.find("[data-return-invoice]").on("click", (e) => {
                const invoice = $(e.currentTarget).data("return-invoice");
                this.loadReturnInvoice(invoice);
            });

        } catch (e) {
            this.page.main.find("#kpws-return-search-results").html(`
                <div class="kpws-pos-warning">
                    Search failed. Check server error log or test using debug command.
                </div>
            `);
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
        "message": "Return invoice search made more reliable."
    }
