from pathlib import Path
import frappe


PATCH_MARKER = "KPWS_PARKED_INVOICE_V19_PATCH"


SERVER_PATCH = r'''

# KPWS_PARKED_INVOICE_V19_PATCH

PARK_TABLE = "tabKPWS Pharmacy Parked Invoice"


def _kpws_park_table_exists():
    return bool(frappe.db.sql("SHOW TABLES LIKE %s", PARK_TABLE))


def _kpws_ensure_park_table():
    if _kpws_park_table_exists():
        return

    frappe.db.sql(f"""
        CREATE TABLE IF NOT EXISTS `{PARK_TABLE}` (
            `name` varchar(140) NOT NULL PRIMARY KEY,
            `creation` datetime(6),
            `modified` datetime(6),
            `modified_by` varchar(140),
            `owner` varchar(140),
            `status` varchar(40) DEFAULT 'Parked',

            `patient` varchar(140),
            `patient_name` varchar(255),
            `mr_number` varchar(140),
            `billing_group` varchar(140),
            `is_walkin` int(1) DEFAULT 0,
            `walkin_name` varchar(255),
            `walkin_mr_number` varchar(140),

            `bill_to_customer` varchar(140),
            `total_amount` decimal(21,9) DEFAULT 0,
            `items_count` int(8) DEFAULT 0,

            `payload_json` longtext,
            `completed_invoice` varchar(140),
            `completed_on` datetime(6),
            `remarks` text,

            INDEX `status` (`status`),
            INDEX `creation` (`creation`),
            INDEX `patient` (`patient`),
            INDEX `mr_number` (`mr_number`),
            INDEX `is_walkin` (`is_walkin`),
            INDEX `completed_invoice` (`completed_invoice`)
        ) ENGINE=InnoDB ROW_FORMAT=DYNAMIC CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    frappe.db.commit()


def _kpws_park_invoice_name():
    return frappe.model.naming.make_autoname("KPPARK-.YYYY.-.#####")


def _kpws_payload_total(payload):
    total = 0
    count = 0

    for row in _list(payload.get("items")):
        qty = flt(row.get("qty"))
        rate = flt(row.get("rate"))
        if row.get("item_code") and qty > 0:
            total += qty * rate
            count += 1

    return flt(total, 2), count


def _kpws_park_summary_from_payload(payload):
    is_walkin = cint(payload.get("is_walkin"))

    patient = payload.get("patient")
    patient_name = ""
    mr_number = ""
    billing_group = "Cash"

    if is_walkin:
        patient_name = payload.get("walkin_name") or "Walk-in Patient"
        mr_number = payload.get("walkin_mr_number") or ""
        billing_group = "Walk-in"
    elif patient and frappe.db.exists("Patient", patient):
        try:
            pdoc = frappe.get_doc("Patient", patient)
            patient_name = _patient_name(pdoc)
            mr_number = _patient_mr(pdoc)
            ctx = get_patient_context(patient)
            billing_group = ctx.get("group") or "Cash"
        except Exception:
            patient_name = patient
            mr_number = patient

    total_amount, items_count = _kpws_payload_total(payload)

    return {
        "patient": patient,
        "patient_name": patient_name,
        "mr_number": mr_number,
        "billing_group": billing_group,
        "is_walkin": is_walkin,
        "walkin_name": payload.get("walkin_name") or "",
        "walkin_mr_number": payload.get("walkin_mr_number") or "",
        "bill_to_customer": payload.get("bill_to_customer") or "",
        "total_amount": total_amount,
        "items_count": items_count,
    }


@frappe.whitelist()
def park_invoice(payload):
    _require_role()
    _kpws_ensure_park_table()

    payload = _json(payload)

    items = _list(payload.get("items"))
    if not items:
        frappe.throw(_("Please add at least one item before parking invoice."))

    if cint(payload.get("is_walkin")):
        if not (payload.get("walkin_name") or "").strip():
            frappe.throw(_("Please enter Walk-in Patient Name before parking."))
        if not (payload.get("walkin_mr_number") or "").strip():
            frappe.throw(_("Please enter Walk-in MR Number before parking."))
    else:
        if not payload.get("patient"):
            frappe.throw(_("Please select Patient before parking invoice."))

    summary = _kpws_park_summary_from_payload(payload)
    name = _kpws_park_invoice_name()
    now_value = frappe.utils.now_datetime()

    frappe.db.sql(
        f"""
        INSERT INTO `{PARK_TABLE}` (
            name, creation, modified, modified_by, owner, status,
            patient, patient_name, mr_number, billing_group,
            is_walkin, walkin_name, walkin_mr_number,
            bill_to_customer, total_amount, items_count,
            payload_json, remarks
        )
        VALUES (
            %(name)s, %(now)s, %(now)s, %(user)s, %(user)s, 'Parked',
            %(patient)s, %(patient_name)s, %(mr_number)s, %(billing_group)s,
            %(is_walkin)s, %(walkin_name)s, %(walkin_mr_number)s,
            %(bill_to_customer)s, %(total_amount)s, %(items_count)s,
            %(payload_json)s, %(remarks)s
        )
        """,
        {
            "name": name,
            "now": now_value,
            "user": frappe.session.user,
            "patient": summary.get("patient"),
            "patient_name": summary.get("patient_name"),
            "mr_number": summary.get("mr_number"),
            "billing_group": summary.get("billing_group"),
            "is_walkin": summary.get("is_walkin"),
            "walkin_name": summary.get("walkin_name"),
            "walkin_mr_number": summary.get("walkin_mr_number"),
            "bill_to_customer": summary.get("bill_to_customer"),
            "total_amount": summary.get("total_amount"),
            "items_count": summary.get("items_count"),
            "payload_json": frappe.as_json(payload),
            "remarks": payload.get("remarks") or "",
        },
    )

    frappe.db.commit()

    return {
        "ok": True,
        "name": name,
        "status": "Parked",
        "message": "Invoice parked successfully.",
    }


@frappe.whitelist()
def list_parked_invoices(status="Parked", txt="", limit=50):
    _require_role()
    _kpws_ensure_park_table()

    status = status or "Parked"
    txt = (txt or "").strip()
    limit = cint(limit) or 50

    conditions = []
    values = {}

    if status != "All":
        conditions.append("status = %(status)s")
        values["status"] = status

    if txt:
        conditions.append("""
            (
                name LIKE %(txt)s
                OR patient LIKE %(txt)s
                OR patient_name LIKE %(txt)s
                OR mr_number LIKE %(txt)s
                OR walkin_name LIKE %(txt)s
                OR walkin_mr_number LIKE %(txt)s
                OR bill_to_customer LIKE %(txt)s
                OR completed_invoice LIKE %(txt)s
            )
        """)
        values["txt"] = f"%{txt}%"

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    rows = frappe.db.sql(
        f"""
        SELECT
            name, creation, modified, owner, status,
            patient, patient_name, mr_number, billing_group,
            is_walkin, walkin_name, walkin_mr_number,
            bill_to_customer, total_amount, items_count,
            completed_invoice, completed_on, remarks
        FROM `{PARK_TABLE}`
        {where_clause}
        ORDER BY modified DESC
        LIMIT {limit}
        """,
        values,
        as_dict=True,
    )

    return rows


@frappe.whitelist()
def get_parked_invoice(name):
    _require_role()
    _kpws_ensure_park_table()

    rows = frappe.db.sql(
        f"""
        SELECT *
        FROM `{PARK_TABLE}`
        WHERE name=%s
        LIMIT 1
        """,
        name,
        as_dict=True,
    )

    if not rows:
        frappe.throw(_("Parked invoice not found."))

    row = rows[0]

    try:
        payload = json.loads(row.get("payload_json") or "{}")
    except Exception:
        payload = {}

    row["payload"] = payload
    return row


@frappe.whitelist()
def cancel_parked_invoice(name):
    _require_role()
    _kpws_ensure_park_table()

    rows = frappe.db.sql(
        f"SELECT status FROM `{PARK_TABLE}` WHERE name=%s",
        name,
        as_dict=True,
    )

    if not rows:
        frappe.throw(_("Parked invoice not found."))

    if rows[0].status == "Completed":
        frappe.throw(_("Completed parked invoice cannot be cancelled."))

    frappe.db.sql(
        f"""
        UPDATE `{PARK_TABLE}`
        SET status='Cancelled',
            modified=%s,
            modified_by=%s
        WHERE name=%s
        """,
        (frappe.utils.now_datetime(), frappe.session.user, name),
    )

    frappe.db.commit()

    return {
        "ok": True,
        "name": name,
        "message": "Parked invoice cancelled.",
    }


@frappe.whitelist()
def mark_parked_invoice_completed(name, invoice):
    _require_role()
    _kpws_ensure_park_table()

    if not name:
        return {"ok": False, "message": "No parked invoice selected."}

    if not frappe.db.exists("Sales Invoice", invoice):
        frappe.throw(_("Completed Sales Invoice not found."))

    rows = frappe.db.sql(
        f"SELECT status FROM `{PARK_TABLE}` WHERE name=%s",
        name,
        as_dict=True,
    )

    if not rows:
        frappe.throw(_("Parked invoice not found."))

    frappe.db.sql(
        f"""
        UPDATE `{PARK_TABLE}`
        SET status='Completed',
            completed_invoice=%s,
            completed_on=%s,
            modified=%s,
            modified_by=%s
        WHERE name=%s
        """,
        (
            invoice,
            frappe.utils.now_datetime(),
            frappe.utils.now_datetime(),
            frappe.session.user,
            name,
        ),
    )

    frappe.db.commit()

    return {
        "ok": True,
        "name": name,
        "completed_invoice": invoice,
        "message": "Parked invoice marked completed.",
    }


@frappe.whitelist()
def repair_parked_invoice_table():
    _require_role()
    _kpws_ensure_park_table()

    return {
        "ok": True,
        "table_exists": _kpws_park_table_exists(),
        "count": frappe.db.sql(f"SELECT COUNT(*) AS count FROM `{PARK_TABLE}`", as_dict=True)[0].count,
    }
'''


JS_PATCH = r'''

/* KPWS_PARKED_INVOICE_V19_PATCH */

(function () {
    if (typeof KPWSPharmacyBillingPOS === "undefined") {
        console.warn("KPWSPharmacyBillingPOS not found. Parked invoice patch skipped.");
        return;
    }

    KPWSPharmacyBillingPOS.prototype.buildInvoicePayload = function (submit) {
        return {
            is_walkin: this.isWalkin && this.isWalkin() ? 1 : 0,
            walkin_name: this.getWalkinName ? this.getWalkinName() : "",
            walkin_mr_number: this.getWalkinMR ? this.getWalkinMR() : "",
            patient: this.isWalkin && this.isWalkin() ? "" : (this.patientContext ? this.patientContext.patient : ""),
            bill_to_customer: this.billToControl ? this.billToControl.get_value() : "",
            price_list: this.patientContext ? this.patientContext.price_list : "",
            card_amount: Number(this.page.main.find("#kpws-card-amount").val() || 0),
            submit: submit ? 1 : 0,
            items: (this.cart || []).map(row => ({
                item_code: row.item_code,
                item_name: row.item_name,
                qty: row.qty,
                rate: row.rate,
                available_qty: row.available_qty
            }))
        };
    };

    KPWSPharmacyBillingPOS.prototype.render = function () {
        this.page.main.html(`
            <div class="kpws-pos-shell">
                <div class="kpws-pos-topbar">
                    <div>
                        <div class="kpws-pos-heading">KPWS Pharmacy POS Billing</div>
                        <div class="kpws-pos-subheading">Billing, parked invoices, returns, approvals and print from one screen</div>
                    </div>

                    <div class="kpws-pos-tabs">
                        <button class="kpws-pos-tab active" data-tab="billing">Billing POS</button>
                        <button class="kpws-pos-tab" data-tab="parked">Parked Invoices</button>
                        <button class="kpws-pos-tab" data-tab="return">Invoice Return</button>
                        <button class="kpws-pos-tab" data-tab="requests">Return Requests</button>
                        <button class="kpws-pos-tab" data-tab="settings">Settings</button>
                    </div>
                </div>

                <div id="kpws-billing-tab"></div>
                <div id="kpws-parked-tab" style="display:none;"></div>
                <div id="kpws-return-tab" style="display:none;"></div>
                <div id="kpws-requests-tab" style="display:none;"></div>
                <div id="kpws-settings-tab" style="display:none;"></div>
            </div>
        `);

        this.bindTabs();
        this.renderBilling();

        if (this.renderParkedInvoices) this.renderParkedInvoices();
        if (this.renderReturn) this.renderReturn();
        if (this.renderReturnRequests) this.renderReturnRequests();

        this.renderSettings();
    };

    KPWSPharmacyBillingPOS.prototype.bindTabs = function () {
        this.page.main.find(".kpws-pos-tab").on("click", (e) => {
            const tab = $(e.currentTarget).data("tab");

            this.page.main.find(".kpws-pos-tab").removeClass("active");
            $(e.currentTarget).addClass("active");

            this.page.main.find("#kpws-billing-tab, #kpws-parked-tab, #kpws-return-tab, #kpws-requests-tab, #kpws-settings-tab").hide();
            this.page.main.find(`#kpws-${tab}-tab`).show();

            if (tab === "parked") {
                this.loadParkedInvoices();
            }

            if (tab === "requests" && this.loadReturnRequests) {
                this.loadReturnRequests();
            }
        });
    };

    const oldRenderBillingForPark = KPWSPharmacyBillingPOS.prototype.renderBilling;

    KPWSPharmacyBillingPOS.prototype.renderBilling = function () {
        oldRenderBillingForPark.apply(this, arguments);

        const actions = this.page.main.find(".kpws-pos-actions").first();

        if (actions.length && !this.page.main.find("#kpws-park-invoice").length) {
            actions.prepend(`
                <button class="kpws-pos-btn dark" id="kpws-park-invoice">
                    Park Invoice
                </button>
            `);
        }

        if (!this.page.main.find("#kpws-current-parked").length) {
            this.page.main.find("#kpws-last-invoice").before(`
                <div id="kpws-current-parked"></div>
            `);
        }

        this.renderCurrentParkedBadge();

        this.page.main.find("#kpws-park-invoice").off("click").on("click", () => {
            this.parkCurrentInvoice();
        });
    };

    KPWSPharmacyBillingPOS.prototype.renderCurrentParkedBadge = function () {
        const target = this.page.main.find("#kpws-current-parked");

        if (!target.length) return;

        if (!this.currentParkedInvoice) {
            target.html("");
            return;
        }

        target.html(`
            <div class="kpws-pos-warning">
                Resumed Parked Invoice: ${this.esc(this.currentParkedInvoice)}
            </div>
        `);
    };

    KPWSPharmacyBillingPOS.prototype.clearPOSForNewInvoice = function () {
        this.currentParkedInvoice = null;
        this.patientContext = null;
        this.cart = [];
        this.paymentPlan = null;
        this.lastInvoice = null;

        this.renderBilling();
    };

    KPWSPharmacyBillingPOS.prototype.parkCurrentInvoice = async function () {
        if (!this.patientContext) {
            frappe.msgprint("Please select Patient or enable Walk-in Patient before parking.");
            return;
        }

        if (this.isWalkin && this.isWalkin()) {
            if (!this.getWalkinName()) {
                frappe.msgprint("Please enter Walk-in Patient Name before parking.");
                return;
            }

            if (!this.getWalkinMR()) {
                frappe.msgprint("Please enter Walk-in MR Number before parking.");
                return;
            }
        }

        if (!this.cart || !this.cart.length) {
            frappe.msgprint("Please add at least one item before parking.");
            return;
        }

        const payload = this.buildInvoicePayload(false);

        frappe.dom.freeze("Parking invoice...");

        try {
            const r = await this.call("park_invoice", {
                payload: JSON.stringify(payload)
            });

            frappe.dom.unfreeze();

            const data = r.message || {};

            frappe.show_alert({
                message: data.message || "Invoice parked successfully.",
                indicator: "green"
            }, 8);

            this.clearPOSForNewInvoice();

            this.page.main.find(`[data-tab="parked"]`).click();

        } catch (e) {
            frappe.dom.unfreeze();
        }
    };

    KPWSPharmacyBillingPOS.prototype.renderParkedInvoices = function () {
        const root = this.page.main.find("#kpws-parked-tab");

        root.html(`
            <div class="kpws-pos-main">
                <div class="kpws-pos-left">
                    <div class="kpws-pos-card">
                        <div class="kpws-pos-card-title">Parked Invoices</div>

                        <div class="kpws-pos-grid-2">
                            <div class="kpws-pos-field">
                                <label>Search</label>
                                <input class="kpws-pos-input" id="kpws-parked-search" placeholder="Search by patient, MR, walk-in name, parked no...">
                            </div>

                            <div class="kpws-pos-field">
                                <label>Status</label>
                                <select class="kpws-pos-input" id="kpws-parked-status">
                                    <option value="Parked">Parked</option>
                                    <option value="Completed">Completed</option>
                                    <option value="Cancelled">Cancelled</option>
                                    <option value="All">All</option>
                                </select>
                            </div>
                        </div>

                        <div style="margin-top:12px; display:flex; gap:8px; flex-wrap:wrap;">
                            <button class="kpws-pos-btn primary" id="kpws-refresh-parked">Refresh</button>
                        </div>

                        <div id="kpws-parked-list" class="kpws-pos-search-results" style="margin-top:12px;"></div>
                    </div>
                </div>

                <div class="kpws-pos-right">
                    <div class="kpws-pos-card">
                        <div class="kpws-pos-card-title">How Parking Works</div>

                        <div class="kpws-pos-status green">
                            <div class="kpws-pos-status-title">Park & Resume</div>
                            <div class="kpws-pos-status-msg">
                                Park current invoice when patient wants to wait or another patient needs urgent billing.
                                Later click Resume to bring the same cart back and complete Submit & Print.
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `);

        let timer = null;

        root.find("#kpws-refresh-parked").on("click", () => this.loadParkedInvoices());

        root.find("#kpws-parked-status").on("change", () => this.loadParkedInvoices());

        root.find("#kpws-parked-search").on("input", () => {
            clearTimeout(timer);
            timer = setTimeout(() => this.loadParkedInvoices(), 400);
        });

        this.loadParkedInvoices();
    };

    KPWSPharmacyBillingPOS.prototype.loadParkedInvoices = async function () {
        const status = this.page.main.find("#kpws-parked-status").val() || "Parked";
        const txt = this.page.main.find("#kpws-parked-search").val() || "";

        this.page.main.find("#kpws-parked-list").html(`
            <div class="kpws-pos-warning">Loading parked invoices...</div>
        `);

        try {
            const r = await this.call("list_parked_invoices", {
                status: status,
                txt: txt,
                limit: 50
            });

            const rows = r.message || [];

            if (!rows.length) {
                this.page.main.find("#kpws-parked-list").html(`
                    <div class="kpws-pos-cart-empty">No parked invoices found.</div>
                `);
                return;
            }

            this.page.main.find("#kpws-parked-list").html(`
                ${rows.map(row => {
                    const title = row.is_walkin
                        ? (row.walkin_name || "Walk-in Patient")
                        : (row.patient_name || row.patient || "-");

                    const mr = row.is_walkin
                        ? row.walkin_mr_number
                        : row.mr_number;

                    const canResume = row.status === "Parked";

                    return `
                        <div class="kpws-pos-product">
                            <div>
                                <div class="kpws-pos-product-name">${this.esc(row.name)}</div>
                                <div class="kpws-pos-product-code">
                                    ${this.esc(title)}
                                    ${mr ? " | MR: " + this.esc(mr) : ""}
                                </div>
                                <div class="kpws-pos-product-code">
                                    Group: ${this.esc(row.billing_group || "-")} |
                                    Status: ${this.esc(row.status || "-")} |
                                    Items: ${Number(row.items_count || 0)}
                                </div>
                                ${row.completed_invoice ? `
                                    <div class="kpws-pos-product-code">
                                        Completed Invoice: ${this.esc(row.completed_invoice)}
                                    </div>
                                ` : ""}
                            </div>

                            <div class="kpws-pos-product-meta">Total<br>${Number(row.total_amount || 0).toFixed(2)}</div>
                            <div class="kpws-pos-product-meta">By<br>${this.esc(row.owner || "-")}</div>

                            <div style="display:grid; gap:6px;">
                                ${canResume ? `
                                    <button class="kpws-pos-btn primary" data-resume-parked="${this.esc(row.name)}">
                                        Resume
                                    </button>
                                    <button class="kpws-pos-btn danger" data-cancel-parked="${this.esc(row.name)}">
                                        Cancel
                                    </button>
                                ` : ""}
                                ${row.completed_invoice ? `
                                    <button class="kpws-pos-btn light" data-open-completed="${this.esc(row.completed_invoice)}">
                                        Print
                                    </button>
                                ` : ""}
                            </div>
                        </div>
                    `;
                }).join("")}
            `);

            this.page.main.find("[data-resume-parked]").on("click", (e) => {
                const name = $(e.currentTarget).data("resume-parked");
                this.resumeParkedInvoice(name);
            });

            this.page.main.find("[data-cancel-parked]").on("click", (e) => {
                const name = $(e.currentTarget).data("cancel-parked");
                this.cancelParkedInvoice(name);
            });

            this.page.main.find("[data-open-completed]").on("click", (e) => {
                const invoice = $(e.currentTarget).data("open-completed");
                this.openPrint({ name: invoice });
            });

        } catch (e) {
            this.page.main.find("#kpws-parked-list").html(`
                <div class="kpws-pos-warning">Unable to load parked invoices.</div>
            `);
        }
    };

    KPWSPharmacyBillingPOS.prototype.resumeParkedInvoice = async function (name) {
        frappe.dom.freeze("Loading parked invoice...");

        try {
            const r = await this.call("get_parked_invoice", { name });
            const data = r.message || {};
            const payload = data.payload || {};

            frappe.dom.unfreeze();

            this.page.main.find(`[data-tab="billing"]`).click();

            this.currentParkedInvoice = data.name;
            this.cart = [];
            this.paymentPlan = null;

            if (payload.is_walkin) {
                this.page.main.find("#kpws-walkin-check").prop("checked", true);
                await this.applyWalkinMode();

                this.page.main.find("#kpws-walkin-name").val(payload.walkin_name || "");
                this.page.main.find("#kpws-walkin-mr").val(payload.walkin_mr_number || "");
                this.page.main.find("#kpws-patient-name").text(payload.walkin_name || "Walk-in Patient");
                this.page.main.find("#kpws-mr").text(payload.walkin_mr_number || "Walk-in");

            } else {
                this.page.main.find("#kpws-walkin-check").prop("checked", false);
                await this.applyWalkinMode();

                if (payload.patient) {
                    this.patientControl.set_value(payload.patient);
                    await this.loadPatient(payload.patient);
                }
            }

            if (payload.bill_to_customer && this.billToControl) {
                this.billToControl.set_value(payload.bill_to_customer);
            }

            this.cart = (payload.items || []).map(row => ({
                item_code: row.item_code,
                item_name: row.item_name || row.item_code,
                qty: Number(row.qty || 0),
                rate: Number(row.rate || 0),
                available_qty: Number(row.available_qty || 0)
            })).filter(row => row.item_code && row.qty > 0);

            this.page.main.find("#kpws-card-amount").val(Number(payload.card_amount || 0));

            this.updateCart();
            this.refreshPaymentPlan();
            this.renderCurrentParkedBadge();

            frappe.show_alert({
                message: "Parked invoice resumed: " + data.name,
                indicator: "green"
            }, 8);

        } catch (e) {
            frappe.dom.unfreeze();
        }
    };

    KPWSPharmacyBillingPOS.prototype.cancelParkedInvoice = async function (name) {
        if (!confirm("Cancel parked invoice " + name + "?")) return;

        frappe.dom.freeze("Cancelling parked invoice...");

        try {
            await this.call("cancel_parked_invoice", { name });

            frappe.dom.unfreeze();

            frappe.show_alert({
                message: "Parked invoice cancelled.",
                indicator: "orange"
            }, 8);

            this.loadParkedInvoices();

        } catch (e) {
            frappe.dom.unfreeze();
        }
    };

    KPWSPharmacyBillingPOS.prototype.createInvoice = async function (submit) {
        if (!this.patientContext) {
            frappe.msgprint("Please select Patient or enable Walk-in Patient first.");
            return;
        }

        if (this.isWalkin && this.isWalkin()) {
            if (!this.getWalkinName()) {
                frappe.msgprint("Please enter Walk-in Patient Name.");
                return;
            }

            if (!this.getWalkinMR()) {
                frappe.msgprint("Please enter Walk-in MR Number.");
                return;
            }
        }

        if (!this.cart || !this.cart.length) {
            frappe.msgprint("Please add at least one item.");
            return;
        }

        const payload = this.buildInvoicePayload(submit);

        frappe.dom.freeze(submit ? "Submitting Sales Invoice..." : "Creating Sales Invoice...");

        try {
            const r = await this.call("create_invoice", {
                payload: JSON.stringify(payload)
            });

            const data = r.message || {};

            if (this.currentParkedInvoice && data.name) {
                await this.call("mark_parked_invoice_completed", {
                    name: this.currentParkedInvoice,
                    invoice: data.name
                });
            }

            frappe.dom.unfreeze();

            this.lastInvoice = data;

            frappe.show_alert({
                message: data.message || "Sales Invoice created successfully.",
                indicator: "green"
            }, 8);

            this.renderLastInvoice(data);

            if (submit) {
                this.openPrint(data);
            }

            this.currentParkedInvoice = null;
            this.cart = [];
            this.paymentPlan = null;
            this.updateCart();
            this.renderCurrentParkedBadge();

            this.page.main.find("#kpws-search-results").html("");
            this.page.main.find("#kpws-item-search").val("");
            this.page.main.find("#kpws-card-amount").val("0");

            if (this.isWalkin && this.isWalkin()) {
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

    # create table immediately
    from kpws_customization.api.kpws_pharmacy_billing_desk import repair_parked_invoice_table
    repair_result = repair_parked_invoice_table()

    frappe.clear_cache()
    frappe.db.commit()

    return {
        "ok": True,
        "server_changed": server_changed,
        "js_changed": js_changed,
        "repair_result": repair_result,
        "message": "Parked invoice flow added to Pharmacy POS."
    }
