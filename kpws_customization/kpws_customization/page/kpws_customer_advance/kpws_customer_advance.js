frappe.provide("kpws");
frappe.pages["kpws-customer-advance"].on_page_load = function (wrapper) {
    new kpws.CustomerAdvance(wrapper);
};

kpws.CustomerAdvance = class {
    constructor(wrapper) {
        this.wrapper = wrapper;
        this.page = frappe.ui.make_app_page({
            parent: wrapper,
            title: __("Receive Customer Advance"),
            single_column: true,
        });
        this.customer = null;
        this.make();
        this.load_defaults();
    }

    make() {
        this.$root = $(`
        <div class="kpws-adv">
            <style>
                .kpws-adv{padding:12px}
                .kpws-adv-card{background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:16px;box-shadow:0 1px 8px rgba(0,0,0,.04);margin-bottom:14px}
                .kpws-adv-card h3{margin:0 0 12px;font-size:16px;font-weight:700;color:#111827}
                .kpws-adv-row{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
                .kpws-adv-row-3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
                .kpws-adv-balance{display:flex;gap:18px;flex-wrap:wrap;margin-top:6px}
                .kpws-adv-stat{background:#f9fafb;border-radius:10px;padding:10px 14px;min-width:170px}
                .kpws-adv-stat .label{font-size:12px;color:#6b7280;font-weight:600}
                .kpws-adv-stat .value{font-size:20px;font-weight:800;color:#111827;margin-top:2px}
                .kpws-adv-stat.warn .value{color:#c2410c}
                .kpws-adv-muted{color:#6b7280;font-size:12px;margin-top:8px}
                .kpws-adv-table{width:100%;border-collapse:collapse;margin-top:8px;font-size:13px}
                .kpws-adv-table th,.kpws-adv-table td{text-align:left;padding:6px 8px;border-bottom:1px solid #eee}
                @media(max-width:900px){.kpws-adv-row,.kpws-adv-row-3{grid-template-columns:1fr}}
            </style>

            <div class="kpws-adv-card">
                <h3>Select Patient / Customer</h3>
                <div class="kpws-adv-row">
                    <div data-control="patient"></div>
                    <div data-control="customer"></div>
                </div>
                <div class="kpws-adv-balance" data-area="balance"></div>
                <div class="kpws-adv-muted" data-area="advance-note"></div>
            </div>

            <div class="kpws-adv-card">
                <h3>Receive Advance</h3>
                <div class="kpws-adv-row-3">
                    <div data-control="amount"></div>
                    <div data-control="mode_of_payment"></div>
                    <div data-control="advance_account"></div>
                </div>
                <div class="kpws-adv-row-3" style="margin-top:12px">
                    <div data-control="reference_no"></div>
                    <div data-control="reference_date"></div>
                    <div data-control="posting_date"></div>
                </div>
                <div style="margin-top:12px" data-control="remarks"></div>
                <div style="margin-top:14px">
                    <button class="btn btn-primary" data-action="receive">Receive Advance</button>
                </div>
            </div>

            <div class="kpws-adv-card">
                <h3>Recent Advance Entries</h3>
                <div data-area="entries"></div>
            </div>
        </div>`).appendTo(this.page.main);

        this.make_controls();
        this.bind();
    }

    make_control(fieldname, df) {
        const parent = this.$root.find(`[data-control="${fieldname}"]`).get(0);
        const control = frappe.ui.form.make_control({
            parent,
            df: Object.assign({ fieldname }, df),
            render_input: true,
        });
        control.refresh();
        this[fieldname] = control;
        return control;
    }

    make_controls() {
        this.make_control("patient", {
            label: "Patient",
            fieldtype: "Link",
            options: "Patient",
            onchange: () => this.on_patient_change(),
        });
        this.make_control("customer", {
            label: "Customer",
            fieldtype: "Link",
            options: "Customer",
            onchange: () => this.on_customer_change(),
        });

        this.make_control("amount", { label: "Amount", fieldtype: "Currency", reqd: 1 });
        this.make_control("mode_of_payment", { label: "Mode of Payment", fieldtype: "Link", options: "Mode of Payment", default: "Cash" });
        this.make_control("advance_account", {
            label: "Advance Account",
            fieldtype: "Link",
            options: "Account",
            reqd: 1,
            get_query: () => ({ filters: { company: this.company, is_group: 0 } }),
        });

        this.make_control("reference_no", { label: "Reference No" , fieldtype: "Data"});
        this.make_control("reference_date", { label: "Reference Date", fieldtype: "Date", default: frappe.datetime.get_today() });
        this.make_control("posting_date", { label: "Posting Date", fieldtype: "Date", default: frappe.datetime.get_today() });
        this.make_control("remarks", { label: "Remarks", fieldtype: "Small Text" });
    }

    bind() {
        this.$root.on("click", "[data-action='receive']", () => this.receive_advance());
    }

    load_defaults() {
        frappe.call({
            method: "kpws_customization.api.kpws_pharmacy_billing_desk.get_settings",
            callback: (r) => {
                const s = r.message || {};
                this.company = s.company || "Kiran Patient Welfare Society";
                if (s.personal_advance_account) {
                    this.advance_account.set_value(s.personal_advance_account);
                }
                if (s.cash_mode_of_payment) {
                    this.mode_of_payment.set_value(s.cash_mode_of_payment);
                } else {
                    this.mode_of_payment.set_value("Cash");
                }
            },
        });
    }

    on_patient_change() {
        const patient = this.patient.get_value();
        if (!patient) return;

        frappe.call({
            method: "frappe.client.get_value",
            args: { doctype: "Patient", filters: patient, fieldname: "customer" },
            callback: (r) => {
                const customer = (r.message || {}).customer;
                if (customer) {
                    this.customer.set_value(customer);
                }
                this.refresh_balance();
            },
        });
    }

    on_customer_change() {
        this.refresh_balance();
    }

    refresh_balance() {
        const patient = this.patient.get_value();
        const customer = this.customer.get_value();

        if (!patient && !customer) {
            this.$root.find("[data-area='balance']").empty();
            this.$root.find("[data-area='advance-note']").text("");
            this.$root.find("[data-area='entries']").empty();
            return;
        }

        frappe.call({
            method: "kpws_customization.api.kpws_pharmacy_billing_desk.get_personal_advance_balance",
            args: { patient, customer },
            callback: (r) => {
                this.render_balance(r.message || {});
            },
        });
    }

    render_balance(bal) {
        const fmt = (v) => format_currency(v || 0);
        const $balance = this.$root.find("[data-area='balance']").empty();

        $balance.append(`
            <div class="kpws-adv-stat">
                <div class="label">Total Available Advance</div>
                <div class="value">${fmt(bal.available_advance)}</div>
            </div>
            <div class="kpws-adv-stat">
                <div class="label">Spendable at Billing (Payment Entry)</div>
                <div class="value">${fmt(bal.payment_entry_advance)}</div>
            </div>
            <div class="kpws-adv-stat ${bal.journal_entry_advance ? "warn" : ""}">
                <div class="label">Recorded via Journal Entry</div>
                <div class="value">${fmt(bal.journal_entry_advance)}</div>
            </div>
        `);

        const note = bal.journal_entry_advance
            ? "Amounts recorded via Journal Entry are not yet auto-consumable at Pharmacy Billing. Prefer receiving new advances through this screen so they post as a Payment Entry and can be applied to invoices directly."
            : "";
        this.$root.find("[data-area='advance-note']").text(note);

        const $entries = this.$root.find("[data-area='entries']").empty();
        const peRows = (bal.entries || []).map(e => `
            <tr>
                <td>${e.name}</td>
                <td>Payment Entry</td>
                <td>${e.posting_date}</td>
                <td>${e.mode_of_payment || "-"}</td>
                <td>${fmt(e.unallocated_amount)}</td>
            </tr>`).join("");
        const jeRows = (bal.journal_entries || []).map(e => `
            <tr>
                <td>${e.name}</td>
                <td>Journal Entry</td>
                <td>${e.posting_date}</td>
                <td>-</td>
                <td>${fmt((e.credit || 0) - (e.debit || 0))}</td>
            </tr>`).join("");

        if (!peRows && !jeRows) {
            $entries.html('<span class="kpws-adv-muted">No advance entries yet.</span>');
            return;
        }

        $entries.html(`
            <table class="kpws-adv-table">
                <thead><tr><th>Reference</th><th>Type</th><th>Date</th><th>Mode</th><th>Amount</th></tr></thead>
                <tbody>${peRows}${jeRows}</tbody>
            </table>
        `);
    }

    receive_advance() {
        const patient = this.patient.get_value();
        const customer = this.customer.get_value();
        const amount = this.amount.get_value();
        const advance_account = this.advance_account.get_value();

        if (!patient && !customer) {
            frappe.msgprint("Please select a Patient or Customer.");
            return;
        }
        if (!amount || amount <= 0) {
            frappe.msgprint("Please enter a valid Amount.");
            return;
        }
        if (!advance_account) {
            frappe.msgprint("Please select an Advance Account.");
            return;
        }

        frappe.call({
            method: "kpws_customization.api.kpws_pharmacy_billing_desk.receive_customer_advance",
            args: {
                patient,
                customer,
                amount,
                mode_of_payment: this.mode_of_payment.get_value(),
                advance_account,
                reference_no: this.reference_no.get_value(),
                reference_date: this.reference_date.get_value(),
                posting_date: this.posting_date.get_value(),
                remarks: this.remarks.get_value(),
            },
            freeze: true,
            freeze_message: "Recording advance...",
            callback: (r) => {
                const res = r.message || {};
                frappe.show_alert({ message: `Advance recorded: ${res.payment_entry}`, indicator: "green" });
                this.amount.set_value("");
                this.reference_no.set_value("");
                this.remarks.set_value("");
                this.render_balance(res.balance || {});
            },
        });
    }
};
