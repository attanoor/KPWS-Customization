# -*- coding: utf-8 -*-
"""
KPWS Patient + Pharmacy Billing Flow v50

Final policy goals:
- Patient = intake classification and live source of truth for reception.
- Patient Registration Form = welfare approval and percentage.
- KPWS Pharmacy Billing/Sales Invoice = automatic accounting execution.

Supported billing types:
- Cash
- Welfare Zakat
- Welfare Donation
- Welfare Panel
- Panel
- Personal Advance

This module intentionally avoids using Zakat/Donation/Panel/Personal Advance as POS modes of payment.
Only real Cash/Card payment methods should be used as payment modes.
"""

import json
import re

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate


COMPANY = "Kiran Patient Welfare Society"
CASH_PHARMACY_ACCOUNT = "CASH (PHARMACY) - KPWS"
WELFARE_RECEIVABLE = "WELFARE RECEIVABLE - KPWS"
PANEL_RECEIVABLE = "PANEL RECEIVABLE CONTROL - KPWS"
SALES_PHARMACY = "SALES (PHARMACY) - KPWS"
SALES_PANEL = "SALES (PANEL) - KPWS"
COGS_PHARMACY = "COST OF GOODS SOLD - KPWS"


# -----------------------------------------------------------------------------
# Generic helpers
# -----------------------------------------------------------------------------


def _has_dt(dt):
    return bool(frappe.db.exists("DocType", dt))


def _meta_has(dt, fieldname):
    try:
        return frappe.get_meta(dt).has_field(fieldname)
    except Exception:
        return False


def _is_group_account(account):
    if not account or not frappe.db.exists("Account", account):
        return False
    return bool(cint(frappe.db.get_value("Account", account, "is_group")))


def _is_ledger_account(account):
    return bool(account and frappe.db.exists("Account", account) and not _is_group_account(account))


def _settings():
    if frappe.db.exists("DocType", "KPWS Pharmacy Billing Settings"):
        return frappe.get_single("KPWS Pharmacy Billing Settings")
    return frappe._dict()


def _get_setting(fieldname, default=None):
    try:
        value = _settings().get(fieldname)
        return value or default
    except Exception:
        return default


def _normalize_text(value):
    return (value or "").strip()


def _norm_lower(value):
    return _normalize_text(value).lower()


def _normalize_cnic(value):
    return re.sub(r"\D", "", value or "")


def _get_total(doc):
    total = flt(doc.get("rounded_total") or doc.get("grand_total"), 2)
    if total:
        return total
    total = 0
    for item in doc.get("items") or []:
        total += flt(item.get("amount"), 2)
    return flt(total, 2)


def _get_company(doc=None):
    return (doc and doc.get("company")) or COMPANY


def _get_panel_receivable_account():
    account = _get_setting("panel_receivable_account", PANEL_RECEIVABLE)
    if _is_ledger_account(account):
        return account
    return _ensure_account(PANEL_RECEIVABLE, "PANEL RECEIVABLE CONTROL", "Receivable", "Asset", "PANEL RECEIVABLES - KPWS")


def _get_welfare_receivable_account():
    account = _get_setting("welfare_receivable_account", WELFARE_RECEIVABLE)
    if _is_ledger_account(account):
        return account
    return _ensure_account(WELFARE_RECEIVABLE, "WELFARE RECEIVABLE", "Receivable", "Asset", "CURRENT ASSETS - KPWS")


def _get_sales_pharmacy_account():
    return _get_setting("cash_income_account", SALES_PHARMACY)


def _get_sales_panel_account():
    return _get_setting("panel_income_account", SALES_PANEL)


def _ensure_account(name, account_name, account_type, root_type, preferred_parent):
    if frappe.db.exists("Account", name):
        return name

    parent = preferred_parent
    if not frappe.db.exists("Account", parent) or not _is_group_account(parent):
        parent = "CURRENT ASSETS - KPWS" if root_type == "Asset" else None

    if not parent or not frappe.db.exists("Account", parent):
        frappe.throw(_("Could not find a valid parent account for {0}").format(name))

    acc = frappe.new_doc("Account")
    acc.account_name = account_name
    acc.company = COMPANY
    acc.parent_account = parent
    acc.root_type = root_type
    acc.account_type = account_type
    acc.is_group = 0
    acc.insert(ignore_permissions=True)
    return acc.name


# -----------------------------------------------------------------------------
# Installation/customization helpers
# -----------------------------------------------------------------------------


def _create_custom_fields():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    custom_fields = {
        "Patient": [
            {
                "fieldname": "custom_kpws_cnic",
                "label": "CNIC",
                "fieldtype": "Data",
                "insert_after": "custom_reference_number",
                "description": "Mandatory CNIC / B-Form for duplicate prevention. Format may be with or without dashes.",
            },
            {
                "fieldname": "custom_kpws_cnic_normalized",
                "label": "CNIC Normalized",
                "fieldtype": "Data",
                "insert_after": "custom_kpws_cnic",
                "read_only": 1,
                "hidden": 1,
            },
            {
                "fieldname": "custom_kpws_funding_source",
                "label": "Funding Source",
                "fieldtype": "Select",
                "options": "\nSelf Paid\nZakat\nDonation\nPanel\nPersonal Advance",
                "insert_after": "customer_group",
                "depends_on": "eval:(doc.customer_group || '').toLowerCase().includes('welfare') || (doc.customer_group || '').toLowerCase().includes('cash') || (doc.customer_group || '').toLowerCase().includes('panel')",
            },
            {
                "fieldname": "custom_kpws_approved_percentage",
                "label": "Approved Welfare Percentage",
                "fieldtype": "Percent",
                "insert_after": "custom_kpws_funding_source",
                "read_only": 1,
                "depends_on": "eval:(doc.customer_group || '').toLowerCase().includes('welfare')",
            },
            {
                "fieldname": "custom_kpws_latest_registration_form",
                "label": "Latest Welfare Registration",
                "fieldtype": "Link",
                "options": "Patient Registration Form",
                "insert_after": "custom_kpws_approved_percentage",
                "read_only": 1,
            },
        ],
        "Patient Registration Form": [
            {
                "fieldname": "custom_kpws_funding_source",
                "label": "Funding Source",
                "fieldtype": "Select",
                "options": "\nZakat\nDonation\nPanel",
                "insert_after": "custom_billing_type",
            },
        ],
        "Sales Invoice": [
            {
                "fieldname": "custom_kpws_billing_type_final",
                "label": "KPWS Final Billing Type",
                "fieldtype": "Data",
                "insert_after": "custom_kpws_patient_billing_group",
                "read_only": 1,
                "allow_on_submit": 1,
            },
            {
                "fieldname": "custom_kpws_personal_advance_used",
                "label": "Personal Advance Used",
                "fieldtype": "Currency",
                "insert_after": "custom_kpws_patient_card_amount",
                "read_only": 1,
                "allow_on_submit": 1,
            },
            {
                "fieldname": "custom_kpws_advance_adjustment_journal_entry",
                "label": "Advance Adjustment Journal Entry",
                "fieldtype": "Link",
                "options": "Journal Entry",
                "insert_after": "custom_kpws_personal_advance_used",
                "read_only": 1,
                "allow_on_submit": 1,
            },
        ],
    }

    # These may already exist from earlier patches; create/update is idempotent.
    create_custom_fields(custom_fields, update=True)

    # Add Panel option to existing duplicate PRF purpose fields.
    for fieldname in ("purpose", "custom_kpws_welfare_type"):
        cf = frappe.db.exists("Custom Field", {"dt": "Patient Registration Form", "fieldname": fieldname})
        if cf:
            doc = frappe.get_doc("Custom Field", cf)
            options = [x.strip() for x in (doc.options or "").splitlines() if x.strip()]
            for opt in ("Zakat", "Donation", "Panel"):
                if opt not in options:
                    options.append(opt)
            doc.options = "\n".join(options)
            doc.save(ignore_permissions=True)
        elif _meta_has("Patient Registration Form", fieldname):
            # Standard/custom JSON field inside DocType - set through Property Setter
            options = frappe.db.get_value("DocField", {"parent": "Patient Registration Form", "fieldname": fieldname}, "options") or ""
            opts = [x.strip() for x in options.splitlines() if x.strip()]
            for opt in ("Zakat", "Donation", "Panel"):
                if opt not in opts:
                    opts.append(opt)
            frappe.make_property_setter({
                "doctype": "Patient Registration Form",
                "fieldname": fieldname,
                "property": "options",
                "value": "\n".join(opts),
                "property_type": "Text",
            })

    frappe.clear_cache(doctype="Patient")
    frappe.clear_cache(doctype="Patient Registration Form")
    frappe.clear_cache(doctype="Sales Invoice")
    frappe.db.updatedb("Patient")
    frappe.db.updatedb("Patient Registration Form")
    frappe.db.updatedb("Sales Invoice")


def _ensure_mode_of_payment_account(mop_name, account, mop_type="Cash"):
    if not mop_name:
        return None
    if not _is_ledger_account(account):
        return None

    if not frappe.db.exists("Mode of Payment", mop_name):
        mop = frappe.new_doc("Mode of Payment")
        mop.mode_of_payment = mop_name
        mop.type = mop_type
        mop.append("accounts", {"company": COMPANY, "default_account": account})
        mop.insert(ignore_permissions=True)
        return mop.name

    mop = frappe.get_doc("Mode of Payment", mop_name)
    found = False
    for row in mop.get("accounts") or []:
        if row.company == COMPANY:
            row.default_account = account
            found = True
    if not found:
        mop.append("accounts", {"company": COMPANY, "default_account": account})
    mop.save(ignore_permissions=True)
    return mop.name


def _remove_bad_pos_profile_modes():
    bad_modes = ("Zakat", "Donation", "Welfare", "Panel", "Personal Advance")
    if not frappe.db.exists("DocType", "POS Payment Method"):
        return 0
    rows = frappe.db.sql(
        """
        SELECT name FROM `tabPOS Payment Method`
        WHERE mode_of_payment IN %(bad_modes)s
        """,
        {"bad_modes": bad_modes},
        as_dict=True,
    )
    for row in rows:
        frappe.db.delete("POS Payment Method", {"name": row.name})
    return len(rows)


def _install_client_scripts():
    # 1) Patient screen helper: CNIC format, panel/funding display, send PRF button.
    patient_script_name = "KPWS Patient Intake Sync V50"
    patient_script = r'''
frappe.ui.form.on("Patient", {
    refresh: function(frm) {
        kpws_patient_v50_setup(frm);
    },
    custom_kpws_cnic: function(frm) {
        if (frm.doc.custom_kpws_cnic) {
            frappe.call({
                method: "kpws_customization.api.kpws_patient_billing_flow_v50.normalize_cnic_api",
                args: { cnic: frm.doc.custom_kpws_cnic },
                callback: function(r) {
                    if (r.message) frm.set_value("custom_kpws_cnic_normalized", r.message);
                }
            });
        }
    },
    customer_group: function(frm) {
        kpws_patient_v50_setup(frm);
    },
    custom_kpws_funding_source: function(frm) {
        kpws_patient_v50_setup(frm);
    }
});

function kpws_patient_v50_setup(frm) {
    let group = (frm.doc.customer_group || "").toLowerCase();
    let source = frm.doc.custom_kpws_funding_source || "";

    frm.toggle_display("custom_kpws_funding_source", group.includes("welfare") || group.includes("cash") || group.includes("panel"));
    frm.toggle_display("custom_panel_customer", group.includes("panel") || source === "Panel");
    frm.toggle_reqd("custom_panel_customer", group.includes("panel") || source === "Panel");
    frm.toggle_reqd("custom_kpws_cnic", true);

    if (!frm.is_new() && (group.includes("welfare") || source === "Zakat" || source === "Donation" || source === "Panel")) {
        frm.add_custom_button(__("Create / Update Welfare Registration"), function() {
            frappe.call({
                method: "kpws_customization.api.kpws_patient_billing_flow_v50.create_or_update_registration_from_patient",
                args: { patient: frm.doc.name },
                freeze: true,
                freeze_message: __("Creating welfare registration..."),
                callback: function(r) {
                    if (r.message && r.message.name) {
                        frappe.set_route("Form", "Patient Registration Form", r.message.name);
                    }
                }
            });
        }, __("KPWS"));
    }

    if (!frm.is_new()) {
        frm.add_custom_button(__("Open Pharmacy Billing"), function() {
            frappe.set_route("kpws-pharmacy-billing", { patient: frm.doc.name });
        }, __("KPWS"));
    }
}
'''

    # 2) PRF helper: sync purpose fields, panel visibility.
    prf_script_name = "KPWS Patient Registration Funding Sync V50"
    prf_script = r'''
frappe.ui.form.on("Patient Registration Form", {
    refresh: function(frm) { kpws_prf_v50_setup(frm); },
    purpose: function(frm) {
        if (frm.doc.purpose && frm.fields_dict.custom_kpws_welfare_type) frm.set_value("custom_kpws_welfare_type", frm.doc.purpose);
        if (frm.doc.purpose && frm.fields_dict.custom_kpws_funding_source) frm.set_value("custom_kpws_funding_source", frm.doc.purpose);
        kpws_prf_v50_setup(frm);
    },
    custom_kpws_welfare_type: function(frm) {
        if (frm.doc.custom_kpws_welfare_type && frm.fields_dict.purpose) frm.set_value("purpose", frm.doc.custom_kpws_welfare_type);
        if (frm.doc.custom_kpws_welfare_type && frm.fields_dict.custom_kpws_funding_source) frm.set_value("custom_kpws_funding_source", frm.doc.custom_kpws_welfare_type);
        kpws_prf_v50_setup(frm);
    },
    custom_kpws_funding_source: function(frm) {
        if (frm.doc.custom_kpws_funding_source && frm.fields_dict.purpose) frm.set_value("purpose", frm.doc.custom_kpws_funding_source);
        if (frm.doc.custom_kpws_funding_source && frm.fields_dict.custom_kpws_welfare_type) frm.set_value("custom_kpws_welfare_type", frm.doc.custom_kpws_funding_source);
        kpws_prf_v50_setup(frm);
    },
    discount_value: function(frm) {
        if (frm.fields_dict.custom_kpws_welfare_percentage) frm.set_value("custom_kpws_welfare_percentage", frm.doc.discount_value || 0);
    },
    custom_kpws_welfare_percentage: function(frm) {
        if (frm.fields_dict.discount_value) frm.set_value("discount_value", frm.doc.custom_kpws_welfare_percentage || 0);
    }
});

function kpws_prf_v50_setup(frm) {
    let purpose = frm.doc.custom_kpws_funding_source || frm.doc.custom_kpws_welfare_type || frm.doc.purpose || "";
    frm.toggle_display("custom_panel_customer", purpose === "Panel");
    frm.toggle_reqd("custom_panel_customer", purpose === "Panel");
    frm.toggle_reqd("discount_value", purpose === "Zakat" || purpose === "Donation");
    frm.toggle_reqd("custom_kpws_welfare_percentage", purpose === "Zakat" || purpose === "Donation");
}
'''

    # 3) Submitted SI lock guard for KPWS non-cash invoices. Lightweight, does not edit draft docs.
    si_lock_name = "KPWS Submitted Billing Lock V50"
    si_lock_script = r'''
frappe.ui.form.on("Sales Invoice", {
    onload: function(frm) { kpws_si_v50_lock(frm); },
    refresh: function(frm) {
        kpws_si_v50_lock(frm);
        setTimeout(function(){ kpws_si_v50_lock(frm); }, 500);
        setTimeout(function(){ kpws_si_v50_lock(frm); }, 1500);
    }
});

function kpws_si_v50_lock(frm) {
    if (!frm || !frm.doc || frm.doc.docstatus !== 1) return;
    if (!(frm.doc.name || "").startsWith("SINV-KPWS")) return;

    let billing = frm.doc.custom_kpws_billing_type_final || frm.doc.custom_kpws_patient_billing_group || "";
    let non_cash = ["Welfare Zakat", "Welfare Donation", "Welfare Panel", "Panel", "Personal Advance", "Welfare"].includes(billing)
        || frm.doc.debit_to === "WELFARE RECEIVABLE - KPWS"
        || frm.doc.debit_to === "PANEL RECEIVABLE CONTROL - KPWS"
        || flt(frm.doc.custom_kpws_welfare_covered_amount) > 0
        || flt(frm.doc.custom_kpws_personal_advance_used) > 0;

    if (!non_cash) return;

    frm.doc.__unsaved = 0;
    frm.dirty(false);
    if (frm.page) {
        frm.page.clear_primary_action();
        if (frm.page.btn_primary) frm.page.btn_primary.hide();
    }
}
'''

    for name, dt, script in [
        (patient_script_name, "Patient", patient_script),
        (prf_script_name, "Patient Registration Form", prf_script),
        (si_lock_name, "Sales Invoice", si_lock_script),
    ]:
        if frappe.db.exists("Client Script", name):
            cs = frappe.get_doc("Client Script", name)
            cs.script = script
            cs.enabled = 1
            cs.dt = dt
            cs.view = "Form"
            cs.save(ignore_permissions=True)
        else:
            cs = frappe.new_doc("Client Script")
            cs.name = name
            cs.dt = dt
            cs.view = "Form"
            cs.enabled = 1
            cs.script = script
            cs.insert(ignore_permissions=True)


def install():
    _create_custom_fields()

    _ensure_account(WELFARE_RECEIVABLE, "WELFARE RECEIVABLE", "Receivable", "Asset", "CURRENT ASSETS - KPWS")
    _ensure_account(PANEL_RECEIVABLE, "PANEL RECEIVABLE CONTROL", "Receivable", "Asset", "PANEL RECEIVABLES - KPWS")

    # Make sure Cash mode posts to CASH (PHARMACY) for pharmacy patient share.
    cash_mop = _get_setting("cash_mode_of_payment", "Cash") or "Cash"
    _ensure_mode_of_payment_account(cash_mop, CASH_PHARMACY_ACCOUNT, "Cash")

    removed = _remove_bad_pos_profile_modes()
    _install_client_scripts()

    frappe.db.commit()
    return {
        "ok": True,
        "removed_bad_pos_profile_modes": removed,
        "message": "KPWS Patient + Pharmacy Billing Flow v50 installed",
    }


# -----------------------------------------------------------------------------
# Patient and PRF APIs/validation
# -----------------------------------------------------------------------------


@frappe.whitelist()
def normalize_cnic_api(cnic):
    return _normalize_cnic(cnic)


def validate_patient(doc, method=None):
    """Patient screen/intake validation."""
    cnic = doc.get("custom_kpws_cnic") if doc.meta.has_field("custom_kpws_cnic") else None
    normalized = _normalize_cnic(cnic)

    if doc.meta.has_field("custom_kpws_cnic_normalized"):
        doc.custom_kpws_cnic_normalized = normalized

    # CNIC mandatory for KPWS patients. Allow explicit emergency override only if a future field exists.
    if not normalized:
        frappe.throw(_("CNIC is mandatory for KPWS patient registration to avoid duplicate patients."))

    if len(normalized) not in (13,):
        frappe.throw(_("CNIC must be 13 digits. You may enter it with or without dashes."))

    existing = frappe.get_all(
        "Patient",
        filters={"custom_kpws_cnic_normalized": normalized, "name": ["!=", doc.name]},
        fields=["name", "patient_name", "custom_reference_number"],
        limit=1,
    )
    if existing:
        e = existing[0]
        frappe.throw(
            _("Duplicate CNIC found on Patient {0} ({1}, MR {2}). Open the existing patient instead of creating another record.").format(
                e.name, e.patient_name, e.custom_reference_number or "-"
            )
        )

    patient_type = _norm_lower(doc.get("customer_group"))
    source = _normalize_text(doc.get("custom_kpws_funding_source")) if doc.meta.has_field("custom_kpws_funding_source") else ""

    if "panel" in patient_type:
        _validate_panel_customer(doc.get("custom_panel_customer"), "Panel Customer is required when Patient Type is Panel.")

    if "welfare" in patient_type:
        if not source:
            frappe.throw(_("Funding Source is required when Patient Type is Welfare. Select Zakat, Donation, or Panel."))
        if source == "Panel":
            _validate_panel_customer(doc.get("custom_panel_customer"), "Panel Customer is required when Welfare Funding Source is Panel.")


def _validate_panel_customer(customer, message):
    if not customer:
        frappe.throw(_(message))
    if not frappe.db.exists("Customer", customer):
        frappe.throw(_("Selected panel customer does not exist."))
    is_panel = cint(frappe.db.get_value("Customer", customer, "custom_is_panel")) if _meta_has("Customer", "custom_is_panel") else 0
    group = _norm_lower(frappe.db.get_value("Customer", customer, "customer_group"))
    if not is_panel and "panel" not in group:
        frappe.throw(_("Customer {0} is not marked as Panel. Tick 'Is Panel' on Customer or set Customer Group to Panel.").format(customer))


@frappe.whitelist()
def get_patient_intake_context(patient=None, cnic=None, mr_no=None):
    filters = {}
    if patient:
        filters["name"] = patient
    elif cnic:
        filters["custom_kpws_cnic_normalized"] = _normalize_cnic(cnic)
    elif mr_no:
        filters["custom_reference_number"] = mr_no
    else:
        frappe.throw(_("Provide patient, CNIC, or MR number."))

    rows = frappe.get_all(
        "Patient",
        filters=filters,
        fields=[
            "name", "patient_name", "custom_reference_number", "customer_group", "customer",
            "custom_panel_customer", "custom_kpws_funding_source", "custom_kpws_approved_percentage",
            "custom_kpws_latest_registration_form", "custom_kpws_cnic", "custom_kpws_cnic_normalized",
        ],
        limit=5,
    )
    out = []
    for row in rows:
        row = frappe._dict(row)
        reg = _latest_registration(row.name)
        out.append({
            "patient": row,
            "latest_registration": reg,
            "classification": classify_patient(row.name),
            "advance_balance": get_personal_advance_balance(row.customer) if row.customer else 0,
        })
    return out


@frappe.whitelist()
def create_or_update_registration_from_patient(patient):
    """Create/update draft Patient Registration Form from Patient. Does not submit automatically."""
    if not patient or not frappe.db.exists("Patient", patient):
        frappe.throw(_("Valid Patient is required."))

    p = frappe.get_doc("Patient", patient)

    draft_name = frappe.db.get_value(
        "Patient Registration Form",
        {"custom_patient": patient, "docstatus": 0},
        "name",
    )
    prf = frappe.get_doc("Patient Registration Form", draft_name) if draft_name else frappe.new_doc("Patient Registration Form")

    _fill_prf_from_patient(prf, p)
    prf.save(ignore_permissions=True)
    frappe.db.commit()
    return {"name": prf.name}


def _fill_prf_from_patient(prf, p):
    mapping = {
        "custom_patient": p.name,
        "custom_mr_number": p.get("custom_reference_number"),
        "custom_patient_name": p.get("patient_name"),
        "custom_patient_customer": p.get("customer"),
        "custom_billing_type": p.get("customer_group"),
        "custom_panel_customer": p.get("custom_panel_customer"),
        "custom_kpws_funding_source": p.get("custom_kpws_funding_source"),
        "purpose": p.get("custom_kpws_funding_source"),
        "custom_kpws_welfare_type": p.get("custom_kpws_funding_source"),
    }
    for field, value in mapping.items():
        if prf.meta.has_field(field) and value is not None:
            prf.set(field, value)

    if prf.meta.has_field("discount_value") and not flt(prf.get("discount_value")):
        prf.discount_value = 100
    if prf.meta.has_field("custom_kpws_welfare_percentage") and not flt(prf.get("custom_kpws_welfare_percentage")):
        prf.custom_kpws_welfare_percentage = prf.get("discount_value") or 100


def validate_patient_registration_form(doc, method=None):
    """Keep duplicate PRF fields synchronized and validate approval data."""
    purpose = _normalize_text(doc.get("custom_kpws_funding_source") or doc.get("custom_kpws_welfare_type") or doc.get("purpose"))
    if purpose:
        for field in ("custom_kpws_funding_source", "custom_kpws_welfare_type", "purpose"):
            if doc.meta.has_field(field):
                doc.set(field, purpose)

    percentage = flt(doc.get("custom_kpws_welfare_percentage") or doc.get("discount_value"), 2)
    for field in ("custom_kpws_welfare_percentage", "discount_value"):
        if doc.meta.has_field(field):
            doc.set(field, percentage)

    if purpose in ("Zakat", "Donation") and percentage <= 0:
        frappe.throw(_("Percentage is required for Welfare {0} approval.").format(purpose))
    if purpose in ("Zakat", "Donation") and percentage > 100:
        frappe.throw(_("Welfare percentage cannot be greater than 100%."))
    if purpose == "Panel":
        _validate_panel_customer(doc.get("custom_panel_customer"), "Panel Customer is required when Funding Source is Panel.")
        # Panel coverage defaults to 100 unless explicitly configured later.
        if percentage <= 0:
            for field in ("custom_kpws_welfare_percentage", "discount_value"):
                if doc.meta.has_field(field):
                    doc.set(field, 100)


def on_patient_registration_submit(doc, method=None):
    """Approved PRF syncs final funding values back to Patient."""
    patient = doc.get("custom_patient")
    if not patient or not frappe.db.exists("Patient", patient):
        return

    p = frappe.get_doc("Patient", patient)
    purpose = _normalize_text(doc.get("custom_kpws_funding_source") or doc.get("custom_kpws_welfare_type") or doc.get("purpose"))
    percentage = flt(doc.get("custom_kpws_welfare_percentage") or doc.get("discount_value"), 2)

    updates = {}
    if p.meta.has_field("custom_kpws_funding_source"):
        updates["custom_kpws_funding_source"] = purpose
    if p.meta.has_field("custom_kpws_approved_percentage"):
        updates["custom_kpws_approved_percentage"] = percentage
    if p.meta.has_field("custom_kpws_latest_registration_form"):
        updates["custom_kpws_latest_registration_form"] = doc.name
    if purpose == "Panel" and doc.get("custom_panel_customer") and p.meta.has_field("custom_panel_customer"):
        updates["custom_panel_customer"] = doc.get("custom_panel_customer")

    for field, value in updates.items():
        frappe.db.set_value("Patient", patient, field, value, update_modified=False)

    frappe.db.commit()


# -----------------------------------------------------------------------------
# Classification / context
# -----------------------------------------------------------------------------


def _latest_registration(patient):
    if not patient or not frappe.db.exists("DocType", "Patient Registration Form"):
        return None
    rows = frappe.get_all(
        "Patient Registration Form",
        filters={"custom_patient": patient, "docstatus": 1},
        fields=[
            "name", "workflow_state", "purpose", "custom_kpws_welfare_type", "custom_kpws_funding_source",
            "discount_value", "custom_kpws_welfare_percentage", "custom_panel_customer", "modified",
        ],
        order_by="modified desc",
        limit=1,
    )
    return frappe._dict(rows[0]) if rows else None


def classify_patient(patient):
    if not patient or not frappe.db.exists("Patient", patient):
        return {"billing_type": "Cash", "reason": "No patient found"}

    p = frappe.get_doc("Patient", patient)
    patient_type = _normalize_text(p.get("customer_group")) or "Cash"
    type_lower = patient_type.lower()
    patient_customer = p.get("customer")
    patient_panel = p.get("custom_panel_customer")
    patient_source = _normalize_text(p.get("custom_kpws_funding_source")) if p.meta.has_field("custom_kpws_funding_source") else ""

    reg = _latest_registration(patient)
    reg_source = ""
    reg_percentage = 0
    reg_panel = None
    if reg:
        reg_source = _normalize_text(reg.get("custom_kpws_funding_source") or reg.get("custom_kpws_welfare_type") or reg.get("purpose"))
        reg_percentage = flt(reg.get("custom_kpws_welfare_percentage") or reg.get("discount_value"), 2)
        reg_panel = reg.get("custom_panel_customer")

    source = reg_source or patient_source
    source_lower = source.lower()
    panel_customer = reg_panel or patient_panel

    # Customer advance marker has priority only when not welfare/panel.
    is_advance_customer = False
    advance_type = None
    if patient_customer and frappe.db.exists("Customer", patient_customer):
        if _meta_has("Customer", "custom_kpws_is_advance_customer"):
            is_advance_customer = bool(cint(frappe.db.get_value("Customer", patient_customer, "custom_kpws_is_advance_customer")))
        if _meta_has("Customer", "custom_kpws_advance_type"):
            advance_type = frappe.db.get_value("Customer", patient_customer, "custom_kpws_advance_type")

    if "welfare" in type_lower:
        if source_lower == "panel":
            return {
                "billing_type": "Welfare Panel",
                "patient_type": patient_type,
                "funding_source": "Panel",
                "percentage": reg_percentage or 100,
                "patient_customer": patient_customer,
                "bill_to_customer": panel_customer,
                "panel_customer": panel_customer,
                "registration": reg.get("name") if reg else None,
            }
        if source_lower == "donation":
            return {
                "billing_type": "Welfare Donation",
                "patient_type": patient_type,
                "funding_source": "Donation",
                "percentage": reg_percentage or flt(p.get("custom_kpws_approved_percentage"), 2) or 100,
                "patient_customer": patient_customer,
                "bill_to_customer": patient_customer,
                "registration": reg.get("name") if reg else None,
            }
        # Default welfare to Zakat if approved source missing but patient is Welfare.
        return {
            "billing_type": "Welfare Zakat",
            "patient_type": patient_type,
            "funding_source": "Zakat",
            "percentage": reg_percentage or flt(p.get("custom_kpws_approved_percentage"), 2) or 100,
            "patient_customer": patient_customer,
            "bill_to_customer": patient_customer,
            "registration": reg.get("name") if reg else None,
        }

    if "panel" in type_lower or patient_panel:
        return {
            "billing_type": "Panel",
            "patient_type": patient_type,
            "funding_source": "Panel",
            "percentage": 100,
            "patient_customer": patient_customer,
            "bill_to_customer": patient_panel or patient_customer,
            "panel_customer": patient_panel,
            "registration": reg.get("name") if reg else None,
        }

    if patient_source == "Personal Advance" or (is_advance_customer and (advance_type or "").strip() == "Personal Advance"):
        return {
            "billing_type": "Personal Advance",
            "patient_type": patient_type,
            "funding_source": "Personal Advance",
            "percentage": 100,
            "patient_customer": patient_customer,
            "bill_to_customer": patient_customer,
            "advance_balance": get_personal_advance_balance(patient_customer),
            "registration": reg.get("name") if reg else None,
        }

    return {
        "billing_type": "Cash",
        "patient_type": patient_type,
        "funding_source": "Self Paid",
        "percentage": 0,
        "patient_customer": patient_customer,
        "bill_to_customer": patient_customer,
        "registration": reg.get("name") if reg else None,
    }


@frappe.whitelist()
def get_billing_context(patient):
    ctx = classify_patient(patient)
    bill_customer = ctx.get("bill_to_customer") or ctx.get("patient_customer")
    ctx["advance_balance"] = get_personal_advance_balance(bill_customer) if bill_customer else 0
    return ctx


# -----------------------------------------------------------------------------
# Sales Invoice policy and settlement
# -----------------------------------------------------------------------------


def _get_invoice_patient(doc):
    return doc.get("patient") or doc.get("custom_patient") or doc.get("custom_kpws_patient")


def apply_sales_invoice_policy(doc, method=None):
    if doc.doctype != "Sales Invoice" or doc.docstatus == 1:
        return

    patient = _get_invoice_patient(doc)
    if not patient:
        return

    ctx = classify_patient(patient)
    billing_type = ctx.get("billing_type") or "Cash"

    # Store context on invoice for audit/reporting.
    _set_if_has(doc, "custom_kpws_billing_type_final", billing_type)
    _set_if_has(doc, "custom_kpws_patient_billing_group", ctx.get("patient_type"))
    _set_if_has(doc, "custom_kpws_purpose", ctx.get("funding_source"))
    _set_if_has(doc, "custom_kpws_approved_percentage", ctx.get("percentage"))
    _set_if_has(doc, "custom_kpws_welfare_registration", ctx.get("registration"))

    # Cash: keep POS, but only real cash/card modes should exist.
    if billing_type == "Cash":
        _set_item_income_account(doc, _get_sales_pharmacy_account())
        return

    # Non-cash categories must not be POS.
    doc.is_pos = 0
    doc.pos_profile = None
    doc.set("payments", [])
    _zero_pos_fields(doc)

    if billing_type in ("Panel", "Welfare Panel"):
        bill_to = ctx.get("bill_to_customer")
        if not bill_to:
            frappe.throw(_("Panel customer is required for {0} billing.").format(billing_type))
        _validate_panel_customer(bill_to, "Selected Panel Customer is not valid.")
        doc.customer = bill_to
        doc.debit_to = _get_panel_receivable_account()
        _set_item_income_account(doc, _get_sales_panel_account())
        _set_if_has(doc, "custom_kpws_panel_customer", bill_to)
        return

    if billing_type in ("Welfare Zakat", "Welfare Donation"):
        if not ctx.get("registration"):
            frappe.throw(_("Approved Patient Registration Form is required for welfare billing."))
        doc.customer = ctx.get("patient_customer") or doc.customer
        doc.debit_to = _get_welfare_receivable_account()
        _set_item_income_account(doc, _get_sales_pharmacy_account())
        return

    if billing_type == "Personal Advance":
        doc.customer = ctx.get("patient_customer") or doc.customer
        # Use normal customer receivable for personal advance. Do not use POS.
        if not doc.debit_to:
            doc.debit_to = _get_party_account("Customer", doc.customer, _get_company(doc))
        _set_item_income_account(doc, _get_sales_pharmacy_account())
        return


def _set_if_has(doc, fieldname, value):
    if value is not None and doc.meta.has_field(fieldname):
        doc.set(fieldname, value)


def _zero_pos_fields(doc):
    for fieldname in (
        "paid_amount", "base_paid_amount", "change_amount", "base_change_amount",
        "write_off_amount", "base_write_off_amount",
    ):
        if hasattr(doc, fieldname):
            doc.set(fieldname, 0)


def _set_item_income_account(doc, account):
    if not account:
        return
    for item in doc.get("items") or []:
        if hasattr(item, "income_account"):
            item.income_account = account
        if hasattr(item, "expense_account") and _get_setting("pharmacy_cogs_account", COGS_PHARMACY):
            item.expense_account = _get_setting("pharmacy_cogs_account", COGS_PHARMACY)


def on_sales_invoice_submit(doc, method=None):
    if getattr(frappe.flags, "kpws_v50_settlement_running", False):
        return
    patient = _get_invoice_patient(doc)
    if not patient:
        return

    ctx = classify_patient(patient)
    billing_type = ctx.get("billing_type")

    try:
        frappe.flags.kpws_v50_settlement_running = True
        if billing_type in ("Welfare Zakat", "Welfare Donation"):
            _settle_welfare_invoice(doc.name, ctx)
        elif billing_type == "Personal Advance":
            _settle_personal_advance_invoice(doc.name, ctx)
    finally:
        frappe.flags.kpws_v50_settlement_running = False


def _settle_welfare_invoice(si_name, ctx=None):
    si = frappe.get_doc("Sales Invoice", si_name)
    ctx = ctx or classify_patient(_get_invoice_patient(si))
    total = _get_total(si)
    percentage = flt(ctx.get("percentage") or 100, 2)
    if percentage > 100:
        percentage = 100
    covered = flt(total * percentage / 100, 2)
    patient_share = flt(total - covered, 2)

    # Store split.
    _db_set_if_has(si, "custom_kpws_welfare_covered_amount", covered)
    _db_set_if_has(si, "custom_kpws_patient_share_amount", patient_share)
    # Default patient share to cash if not split by UI.
    existing_cash = flt(si.get("custom_kpws_patient_cash_amount"), 2)
    existing_card = flt(si.get("custom_kpws_patient_card_amount"), 2)
    if patient_share > 0 and flt(existing_cash + existing_card, 2) <= 0:
        _db_set_if_has(si, "custom_kpws_patient_cash_amount", patient_share)
        existing_cash = patient_share

    si.reload()

    # Patient share through actual cash/card payment entry.
    if patient_share > 0:
        cash_amt = flt(si.get("custom_kpws_patient_cash_amount"), 2)
        card_amt = flt(si.get("custom_kpws_patient_card_amount"), 2)
        if cash_amt > 0:
            pe = _create_receive_payment(si, _get_setting("cash_mode_of_payment", "Cash"), cash_amt, CASH_PHARMACY_ACCOUNT)
            _db_set_if_has(si, "custom_kpws_cash_payment_entry", pe)
        if card_amt > 0:
            card_mop = _get_setting("card_mode_of_payment", "Credit Card")
            pe = _create_receive_payment(si, card_mop, card_amt, None)
            _db_set_if_has(si, "custom_kpws_card_payment_entry", pe)

    # Covered amount through Zakat/Donation JE.
    if covered > 0:
        je = _create_welfare_journal(si, ctx, covered)
        _db_set_if_has(si, "custom_kpws_auto_journal_entry", je)

    _refresh_invoice_status(si.name)


def _db_set_if_has(doc, fieldname, value):
    if doc.meta.has_field(fieldname):
        frappe.db.set_value(doc.doctype, doc.name, fieldname, value, update_modified=False)


def _create_receive_payment(si, mode_of_payment, amount, forced_paid_to=None):
    amount = flt(amount, 2)
    if amount <= 0:
        return None

    existing = frappe.db.sql(
        """
        SELECT pe.name
        FROM `tabPayment Entry Reference` ref
        JOIN `tabPayment Entry` pe ON pe.name = ref.parent
        WHERE ref.reference_doctype='Sales Invoice'
          AND ref.reference_name=%s
          AND pe.mode_of_payment=%s
          AND pe.docstatus=1
        LIMIT 1
        """,
        (si.name, mode_of_payment),
        as_dict=True,
    )
    if existing:
        return existing[0].name

    paid_to = forced_paid_to or _get_mop_account(mode_of_payment, si.company)
    if not paid_to:
        frappe.throw(_("Mode of Payment {0} has no default account for company {1}.").format(mode_of_payment, si.company))

    receivable = si.debit_to or _get_party_account("Customer", si.customer, si.company)

    pe = frappe.new_doc("Payment Entry")
    pe.payment_type = "Receive"
    pe.company = si.company
    pe.posting_date = si.posting_date or nowdate()
    pe.mode_of_payment = mode_of_payment
    pe.party_type = "Customer"
    pe.party = si.customer
    pe.paid_from = receivable
    pe.paid_to = paid_to
    pe.paid_amount = amount
    pe.received_amount = amount
    pe.reference_no = si.name
    pe.reference_date = si.posting_date or nowdate()
    pe.append("references", {
        "reference_doctype": "Sales Invoice",
        "reference_name": si.name,
        "allocated_amount": amount,
    })
    pe.insert(ignore_permissions=True)
    pe.submit()
    return pe.name


def _get_mop_account(mode_of_payment, company):
    if not mode_of_payment or not frappe.db.exists("Mode of Payment", mode_of_payment):
        return None
    mop = frappe.get_doc("Mode of Payment", mode_of_payment)
    for row in mop.get("accounts") or []:
        if row.company == company and row.default_account:
            return row.default_account
    return None


def _get_party_account(party_type, party, company):
    try:
        from erpnext.accounts.party import get_party_account
        return get_party_account(party_type, party, company)
    except Exception:
        pass
    if party_type == "Customer" and party and frappe.db.exists("Customer", party):
        cust = frappe.get_doc("Customer", party)
        for row in cust.get("accounts") or []:
            if row.company == company and row.account:
                return row.account
    # final fallback
    if _is_ledger_account("DEBTORS - KPWS"):
        return "DEBTORS - KPWS"
    if _is_ledger_account("RECEIVABLES - KPWS"):
        return "RECEIVABLES - KPWS"
    return None


def _create_welfare_journal(si, ctx, amount):
    amount = flt(amount, 2)
    existing = _existing_reference_journal(si.name, si.debit_to)
    if existing:
        return existing

    funding = ctx.get("funding_source") or "Zakat"
    if funding == "Donation":
        expense_account = _get_setting("donation_disbursement_account")
    else:
        expense_account = _get_setting("zakat_disbursement_account")
    if not expense_account:
        frappe.throw(_("Missing {0} disbursement account in KPWS Pharmacy Billing Settings.").format(funding))

    je = frappe.new_doc("Journal Entry")
    je.voucher_type = "Journal Entry"
    je.company = si.company
    je.posting_date = si.posting_date or nowdate()
    je.user_remark = "Auto {0} welfare settlement against Sales Invoice {1}".format(funding, si.name)
    je.append("accounts", {"account": expense_account, "debit_in_account_currency": amount})
    je.append("accounts", {
        "account": si.debit_to,
        "party_type": "Customer",
        "party": si.customer,
        "reference_type": "Sales Invoice",
        "reference_name": si.name,
        "credit_in_account_currency": amount,
    })
    je.insert(ignore_permissions=True)
    je.submit()
    return je.name


def _existing_reference_journal(si_name, account):
    rows = frappe.db.sql(
        """
        SELECT je.name
        FROM `tabJournal Entry Account` acc
        JOIN `tabJournal Entry` je ON je.name = acc.parent
        WHERE acc.reference_type='Sales Invoice'
          AND acc.reference_name=%s
          AND acc.account=%s
          AND acc.credit_in_account_currency > 0
          AND je.docstatus=1
        LIMIT 1
        """,
        (si_name, account),
        as_dict=True,
    )
    return rows[0].name if rows else None


def get_personal_advance_balance(customer, company=COMPANY, account=None, exclude_voucher=None):
    if not customer:
        return 0
    account = account or _get_party_account("Customer", customer, company)
    if not account:
        return 0
    cond = ""
    params = {"company": company, "party": customer, "account": account}
    if exclude_voucher:
        cond = " AND voucher_no != %(exclude_voucher)s"
        params["exclude_voucher"] = exclude_voucher

    # Positive means customer has credit/advance balance.
    rows = frappe.db.sql(
        f"""
        SELECT COALESCE(SUM(credit - debit), 0) AS balance
        FROM `tabGL Entry`
        WHERE company=%(company)s
          AND party_type='Customer'
          AND party=%(party)s
          AND account=%(account)s
          AND is_cancelled=0
          {cond}
        """,
        params,
        as_dict=True,
    )
    return flt(rows[0].balance if rows else 0, 2)


def _settle_personal_advance_invoice(si_name, ctx=None):
    si = frappe.get_doc("Sales Invoice", si_name)
    account = si.debit_to or _get_party_account("Customer", si.customer, si.company)
    available = get_personal_advance_balance(si.customer, si.company, account, exclude_voucher=si.name)
    total = flt(si.outstanding_amount or _get_total(si), 2)
    use_advance = flt(min(available, total), 2)
    remaining = flt(total - use_advance, 2)

    if use_advance > 0:
        je = _create_advance_adjustment_journal(si, account, use_advance)
        _db_set_if_has(si, "custom_kpws_personal_advance_used", use_advance)
        _db_set_if_has(si, "custom_kpws_advance_adjustment_journal_entry", je)

    # If advance is not enough, remaining is collected by Cash Pharmacy unless UI/fields split it.
    if remaining > 0:
        pe = _create_receive_payment(si, _get_setting("cash_mode_of_payment", "Cash"), remaining, CASH_PHARMACY_ACCOUNT)
        _db_set_if_has(si, "custom_kpws_patient_cash_amount", remaining)
        _db_set_if_has(si, "custom_kpws_cash_payment_entry", pe)

    _refresh_invoice_status(si.name)


def _create_advance_adjustment_journal(si, account, amount):
    amount = flt(amount, 2)
    existing = _existing_reference_journal(si.name, account)
    if existing:
        return existing

    # Reclassify existing unallocated customer credit/advance to this invoice reference.
    je = frappe.new_doc("Journal Entry")
    je.voucher_type = "Journal Entry"
    je.company = si.company
    je.posting_date = si.posting_date or nowdate()
    je.user_remark = "Auto personal advance allocation against Sales Invoice {0}".format(si.name)
    je.append("accounts", {
        "account": account,
        "party_type": "Customer",
        "party": si.customer,
        "debit_in_account_currency": amount,
    })
    je.append("accounts", {
        "account": account,
        "party_type": "Customer",
        "party": si.customer,
        "reference_type": "Sales Invoice",
        "reference_name": si.name,
        "credit_in_account_currency": amount,
    })
    je.insert(ignore_permissions=True)
    je.submit()
    return je.name


def _refresh_invoice_status(si_name):
    si = frappe.get_doc("Sales Invoice", si_name)
    try:
        si.set_status(update=True)
    except Exception:
        pass
    frappe.db.commit()


def protect_submitted_invoice(doc, method=None):
    """Prevent client scripts from dirtying submitted KPWS non-cash invoices."""
    if doc.doctype != "Sales Invoice" or doc.docstatus != 1 or not doc.name:
        return
    if not (doc.name or "").startswith("SINV-KPWS"):
        return

    db = frappe.db.get_value(
        "Sales Invoice",
        doc.name,
        [
            "customer", "customer_name", "debit_to", "is_pos", "pos_profile", "selling_price_list",
            "price_list_currency", "plc_conversion_rate", "conversion_rate", "currency", "status", "outstanding_amount",
        ],
        as_dict=True,
    )
    if not db:
        return

    billing = doc.get("custom_kpws_billing_type_final") or frappe.db.get_value("Sales Invoice", doc.name, "custom_kpws_billing_type_final")
    non_cash = billing in ("Welfare Zakat", "Welfare Donation", "Welfare Panel", "Panel", "Personal Advance")
    if not non_cash and db.debit_to not in (_get_welfare_receivable_account(), _get_panel_receivable_account()):
        return

    for field in db:
        if doc.meta.has_field(field):
            doc.set(field, db.get(field))
    if billing in ("Welfare Zakat", "Welfare Donation", "Welfare Panel", "Panel", "Personal Advance"):
        doc.is_pos = 0
        doc.pos_profile = None
        doc.set("payments", [])


# -----------------------------------------------------------------------------
# Audit and repair utilities
# -----------------------------------------------------------------------------


@frappe.whitelist()
def audit_patient(patient):
    ctx = classify_patient(patient)
    return {
        "patient": patient,
        "classification": ctx,
        "advance_balance": get_personal_advance_balance(ctx.get("bill_to_customer") or ctx.get("patient_customer")),
        "latest_registration": _latest_registration(patient),
    }


@frappe.whitelist()
def audit_recent_invoices(limit=20):
    limit = cint(limit or 20)
    fields = [
        "name", "customer", "status", "outstanding_amount", "is_pos", "selling_price_list", "debit_to",
        "patient", "custom_kpws_billing_type_final", "custom_kpws_patient_billing_group",
        "custom_kpws_purpose", "custom_kpws_welfare_covered_amount", "custom_kpws_patient_share_amount",
        "custom_kpws_personal_advance_used", "custom_kpws_cash_payment_entry", "custom_kpws_auto_journal_entry",
    ]
    columns = {r[0] for r in frappe.db.sql("SHOW COLUMNS FROM `tabSales Invoice`")}
    fields = [f for f in fields if f in columns]
    rows = frappe.get_all("Sales Invoice", filters={"name": ["like", "SINV-KPWS-%"]}, fields=fields, order_by="creation desc", limit=limit)
    out = []
    for row in rows:
        row = frappe._dict(row)
        issues = []
        billing = row.get("custom_kpws_billing_type_final") or row.get("custom_kpws_patient_billing_group")
        if billing in ("Welfare Zakat", "Welfare Donation", "Welfare Panel", "Panel", "Personal Advance") and row.get("is_pos"):
            issues.append("Non-cash KPWS invoice should not be POS")
        if billing == "Cash" and not row.get("is_pos"):
            issues.append("Cash invoice should normally be POS")
        if billing in ("Welfare Zakat", "Welfare Donation") and row.get("outstanding_amount"):
            issues.append("Welfare Zakat/Donation should be fully settled by JE and patient share payment")
        if billing in ("Panel", "Welfare Panel") and not row.get("outstanding_amount"):
            issues.append("Panel invoice is normally outstanding until panel pays")
        row["issues"] = issues
        out.append(row)
    return out


@frappe.whitelist()
def repair_invoice(si_name):
    si = frappe.get_doc("Sales Invoice", si_name)
    patient = _get_invoice_patient(si)
    if not patient:
        return {"ok": False, "message": "Invoice has no patient"}
    ctx = classify_patient(patient)
    billing_type = ctx.get("billing_type")
    if billing_type in ("Welfare Zakat", "Welfare Donation"):
        _settle_welfare_invoice(si.name, ctx)
    elif billing_type == "Personal Advance":
        _settle_personal_advance_invoice(si.name, ctx)
    elif billing_type in ("Panel", "Welfare Panel"):
        frappe.db.set_value("Sales Invoice", si.name, "is_pos", 0, update_modified=False)
        frappe.db.set_value("Sales Invoice", si.name, "pos_profile", "", update_modified=False)
        frappe.db.set_value("Sales Invoice", si.name, "debit_to", _get_panel_receivable_account(), update_modified=False)
        _db_set_if_has(si, "custom_kpws_billing_type_final", billing_type)
        frappe.db.sql("DELETE FROM `tabSales Invoice Payment` WHERE parent=%s AND parenttype='Sales Invoice'", si.name)
        _refresh_invoice_status(si.name)
    return frappe.db.get_value("Sales Invoice", si.name, ["status", "outstanding_amount", "is_pos", "debit_to", "custom_kpws_billing_type_final"], as_dict=True)


# KPWS_BILLING_MODE_V91: final four-mode patient classification + Welfare Panel settlement
try:
    from kpws_customization.api import kpws_billing_mode_v91 as _kpws_v91
    classify_patient = _kpws_v91.classify_patient
    get_billing_context = _kpws_v91.desk_get_patient_context
    validate_patient_registration_form = _kpws_v91.validate_patient_registration_form
    apply_sales_invoice_policy = _kpws_v91.apply_sales_invoice_policy
    on_sales_invoice_submit = _kpws_v91.on_submit_sales_invoice
    protect_submitted_invoice = _kpws_v91.protect_submitted_invoice_before_save
    audit_patient = _kpws_v91.audit_patient
    audit_recent_invoices = _kpws_v91.audit_recent
except Exception:
    pass

