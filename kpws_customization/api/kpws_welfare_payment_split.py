import json
import frappe

CLIENT_SCRIPT_NAME = "KPWS FINAL Welfare Payment Split"


def _as_dict(value):
    if isinstance(value, str):
        return frappe._dict(json.loads(value))
    return frappe._dict(value or {})


def _mode(names):
    for name in names:
        if frappe.db.exists("Mode of Payment", name):
            return name

    for row in frappe.get_all("Mode of Payment", fields=["name"], limit=200):
        low = row.name.lower()
        for name in names:
            if name.lower() in low:
                return row.name

    return names[0] if names else ""


def _mode_account(mode_of_payment, company):
    if not mode_of_payment or not frappe.db.exists("Mode of Payment", mode_of_payment):
        return ""

    mop = frappe.get_doc("Mode of Payment", mode_of_payment)

    for row in mop.get("accounts") or []:
        if row.company == company and row.default_account:
            return row.default_account

    for row in mop.get("accounts") or []:
        if row.default_account:
            return row.default_account

    return ""


def _total(doc):
    return float(doc.get("rounded_total") or doc.get("grand_total") or doc.get("net_total") or 0)


def _billing_type(doc):
    text = " ".join([
        str(doc.get("custom_kpws_billing_type") or ""),
        str(doc.get("pos_profile") or ""),
    ]).lower()

    if "panel" in text:
        return "Panel"

    if "welfare" in text:
        return "Welfare"

    return "Cash"


def _latest_welfare_registration(patient):
    if not patient or not frappe.db.exists("DocType", "Patient Registration Form"):
        return {}

    meta = frappe.get_meta("Patient Registration Form")

    fields = ["name", "modified", "docstatus"]

    for fieldname in [
        "custom_patient",
        "patient",
        "purpose",
        "discount_value",
        "custom_kpws_welfare_type",
        "custom_kpws_welfare_percentage",
    ]:
        if meta.get_field(fieldname):
            fields.append(fieldname)

    filter_sets = []

    for patient_field in ["custom_patient", "patient"]:
        if meta.get_field(patient_field):
            # Prefer submitted/approved records first.
            filter_sets.append({patient_field: patient, "docstatus": 1})
            # Fallback to draft if your PRF is not submitted.
            filter_sets.append({patient_field: patient, "docstatus": 0})

    for filters in filter_sets:
        rows = frappe.get_all(
            "Patient Registration Form",
            filters=filters,
            fields=list(set(fields)),
            order_by="modified desc",
            limit=1,
        )

        if not rows:
            continue

        row = rows[0]

        purpose = row.get("purpose") or row.get("custom_kpws_welfare_type") or ""
        percentage = row.get("discount_value")

        if percentage in (None, ""):
            percentage = row.get("custom_kpws_welfare_percentage") or 0

        return {
            "name": row.name,
            "purpose": purpose,
            "percentage": float(percentage or 0),
            "docstatus": row.docstatus,
        }

    return {}


def _payment_row(mode, amount, company):
    amount = float(amount or 0)

    if amount <= 0:
        return None

    account = _mode_account(mode, company)

    if not account:
        frappe.throw(
            f"Mode of Payment <b>{mode}</b> has no default account for company <b>{company}</b>. "
            f"Open Mode of Payment {mode} and add the default account in the Accounts table."
        )

    return {
        "mode_of_payment": mode,
        "account": account,
        "amount": amount,
        "base_amount": amount,
    }


def _get_payment_rows(doc):
    doc = _as_dict(doc)

    company = doc.get("company") or frappe.defaults.get_defaults().get("company")
    total = _total(doc)

    if total <= 0:
        return []

    billing_type = _billing_type(doc)

    cash_mode = _mode(["Cash"])
    card_mode = _mode(["Credit Card", "Card"])
    panel_mode = _mode(["Panel"])
    zakat_mode = _mode(["Zakat"])
    donation_mode = _mode(["Donation"])

    rows = []

    if billing_type == "Panel":
        row = _payment_row(panel_mode, total, company)
        if row:
            rows.append(row)
        return rows

    if billing_type == "Welfare":
        welfare = _latest_welfare_registration(doc.get("patient"))

        purpose = (
            doc.get("custom_kpws_welfare_type")
            or welfare.get("purpose")
            or ""
        )

        percentage = doc.get("custom_kpws_welfare_percentage")
        if percentage in (None, ""):
            percentage = welfare.get("percentage") or 0

        percentage = max(0, min(100, float(percentage or 0)))

        if percentage > 0 and not purpose:
            frappe.throw("Welfare Patient Registration Form must have Purpose: Zakat or Donation.")

        sponsor_mode = zakat_mode if "zakat" in str(purpose).lower() else donation_mode

        sponsor_amount = total * percentage / 100
        cash_amount = total - sponsor_amount

        sponsor = _payment_row(sponsor_mode, sponsor_amount, company)
        if sponsor:
            rows.append(sponsor)

        cash = _payment_row(cash_mode, cash_amount, company)
        if cash:
            rows.append(cash)

        return rows

    # Cash / Walk-in: Cash + optional Credit Card.
    existing_card_amount = 0
    for row in doc.get("payments") or []:
        mode = str(row.get("mode_of_payment") or "").lower()
        if "card" in mode or "credit" in mode:
            existing_card_amount += float(row.get("amount") or 0)

    if existing_card_amount > total:
        existing_card_amount = 0

    cash = _payment_row(cash_mode, total - existing_card_amount, company)
    if cash:
        rows.append(cash)

    card = _payment_row(card_mode, existing_card_amount, company)
    if card:
        rows.append(card)

    return rows


@frappe.whitelist()
def get_payment_rows(doc):
    return _get_payment_rows(doc)


def enforce_sales_invoice_payments(doc, method=None):
    if doc.doctype != "Sales Invoice":
        return

    if not int(doc.get("is_pos") or 0):
        return

    rows = _get_payment_rows(doc.as_dict())

    doc.set("payments", [])

    for row in rows:
        doc.append("payments", row)

    doc.paid_amount = sum(float(row.get("amount") or 0) for row in rows)


def install_client_script():
    if not frappe.db.exists("DocType", "Client Script"):
        return

    script = r'''
frappe.ui.form.on("Sales Invoice", {
    refresh(frm) {
        kpws_welfare_payment_apply_later(frm);
    },
    pos_profile(frm) {
        kpws_welfare_payment_apply_later(frm);
    },
    patient(frm) {
        kpws_welfare_payment_apply_later(frm);
    },
    custom_kpws_billing_type(frm) {
        kpws_welfare_payment_apply_later(frm);
    },
    custom_kpws_welfare_type(frm) {
        kpws_welfare_payment_apply_later(frm);
    },
    custom_kpws_welfare_percentage(frm) {
        kpws_welfare_payment_apply_later(frm);
    },
    grand_total(frm) {
        kpws_welfare_payment_apply_later(frm);
    },
    rounded_total(frm) {
        kpws_welfare_payment_apply_later(frm);
    },
    net_total(frm) {
        kpws_welfare_payment_apply_later(frm);
    }
});

function kpws_welfare_payment_apply_later(frm) {
    clearTimeout(frm.__kpws_welfare_payment_timer);
    frm.__kpws_welfare_payment_timer = setTimeout(function() {
        kpws_welfare_payment_apply_now(frm);
    }, 500);
}

function kpws_welfare_payment_apply_now(frm) {
    if (!frm.fields_dict.payments) return;

    let total = flt(frm.doc.rounded_total || frm.doc.grand_total || frm.doc.net_total || 0);
    if (!total || total <= 0) return;

    if (frm.__kpws_welfare_payment_running) return;
    frm.__kpws_welfare_payment_running = true;

    frappe.call({
        method: "kpws_customization.api.kpws_welfare_payment_split.get_payment_rows",
        args: {
            doc: frm.doc
        },
        freeze: false,
        callback: function(r) {
            let rows = r.message || [];

            frm.clear_table("payments");

            rows.forEach(function(d) {
                let row = frm.add_child("payments");
                row.mode_of_payment = d.mode_of_payment;
                row.account = d.account;
                row.amount = d.amount;
                row.base_amount = d.base_amount || d.amount;
            });

            frm.refresh_field("payments");
        },
        always: function() {
            frm.__kpws_welfare_payment_running = false;
        }
    });
}
'''

    # Disable older payment-specific scripts only.
    for row in frappe.get_all("Client Script", filters={"dt": "Sales Invoice"}, fields=["name", "script"]):
        if row.name == CLIENT_SCRIPT_NAME:
            continue

        text = ((row.name or "") + "\n" + (row.script or "")).lower()

        if "payment split" in text or "apply_payments" in text or "welfare payment" in text:
            frappe.db.set_value("Client Script", row.name, "enabled", 0, update_modified=False)
            print("Disabled old payment script:", row.name)

    if frappe.db.exists("Client Script", CLIENT_SCRIPT_NAME):
        doc = frappe.get_doc("Client Script", CLIENT_SCRIPT_NAME)
        doc.enabled = 1
        doc.dt = "Sales Invoice"
        doc.view = "Form"
        doc.script = script
        doc.save(ignore_permissions=True)
        print("Updated Client Script:", CLIENT_SCRIPT_NAME)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": CLIENT_SCRIPT_NAME,
            "dt": "Sales Invoice",
            "view": "Form",
            "enabled": 1,
            "script": script,
        }).insert(ignore_permissions=True)
        print("Created Client Script:", CLIENT_SCRIPT_NAME)


def install():
    install_client_script()
    frappe.db.commit()
    frappe.clear_cache()
    print("DONE: Welfare POS Profile now fetches PRF purpose/percentage and calculates payment rows.")
