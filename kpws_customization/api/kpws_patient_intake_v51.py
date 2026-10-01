
# -*- coding: utf-8 -*-
"""
KPWS Patient Intake + Registration Flow v51

Purpose:
- Single-screen reception/admin workflow for Patient + Patient Registration Form.
- Supports Cash, Welfare Zakat, Welfare Donation, Welfare Panel, Panel, Personal Advance.
- Keeps Patient, Patient Registration Form, and Billing Classification synced.
- Adds CNIC mandatory + normalized duplicate validation.
"""

import re
import json
import frappe
from frappe import _
from frappe.utils import flt, nowdate, cint

COMPANY = "Kiran Patient Welfare Society"

PATIENT_TYPE_CASH = "Cash"
PATIENT_TYPE_WELFARE = "Welfare"
PATIENT_TYPE_PANEL = "Panel"
PATIENT_TYPE_ADVANCE = "Personal Advance"

FUNDING_SELF = "Self Paid"
FUNDING_ZAKAT = "Zakat"
FUNDING_DONATION = "Donation"
FUNDING_PANEL = "Panel"
FUNDING_ADVANCE = "Personal Advance"

WELFARE_RECEIVABLE = "WELFARE RECEIVABLE - KPWS"
PANEL_RECEIVABLE = "PANEL RECEIVABLE CONTROL - KPWS"
CASH_PHARMACY_ACCOUNT = "CASH (PHARMACY) - KPWS"

INTAKE_PAGE_NAME = "kpws-patient-intake"
INTAKE_PAGE_TITLE = "KPWS Patient Intake"


def _safe_has_field(dt, fieldname):
    try:
        return frappe.get_meta(dt).has_field(fieldname)
    except Exception:
        return False


def _norm_text(v):
    return (v or "").strip()


def normalize_cnic(value):
    """Return only digits. 42101-1234567-1 and 4210112345671 become same."""
    return re.sub(r"\D+", "", value or "")


def pretty_cnic(value):
    digits = normalize_cnic(value)
    if len(digits) == 13:
        return f"{digits[:5]}-{digits[5:12]}-{digits[12:]}"
    return value or ""


def _customer_group_exists(name):
    return bool(name and frappe.db.exists("Customer Group", name))


def _ensure_customer_group(name):
    """
    Safe customer group creator.

    ERPNext blocks Customer Group creation if a Customer with the same name exists.
    In KPWS, some names like Panel / Personal Advance may already exist as Customer records,
    so installer must not fail. It should skip and continue.
    """
    import frappe

    if not name:
        return None

    if frappe.db.exists("Customer Group", name):
        return name

    if frappe.db.exists("Customer", name):
        print("Skipping Customer Group creation because Customer already exists with same name:", name)
        return None

    parent = None
    for candidate in ("All Customer Groups", "All Customer Group"):
        if frappe.db.exists("Customer Group", candidate):
            parent = candidate
            break

    try:
        doc = frappe.new_doc("Customer Group")
        doc.customer_group_name = name
        doc.is_group = 0

        if parent:
            doc.parent_customer_group = parent

        doc.insert(ignore_permissions=True)
        return doc.name

    except Exception as e:
        msg = str(e)
        if "same name already exists" in msg or "A customer with the same name already exists" in msg:
            print("Skipping Customer Group due name conflict:", name)
            return None
        raise


def _is_panel_customer(customer):
    if not customer or not frappe.db.exists("Customer", customer):
        return False

    if _safe_has_field("Customer", "custom_is_panel"):
        if cint(frappe.db.get_value("Customer", customer, "custom_is_panel")):
            return True

    # fallback only for non-patient named company-like panel customers
    customer_group = frappe.db.get_value("Customer", customer, "customer_group")
    if customer_group == "Panel":
        # We allow it for backward compatibility, but strongly recommend custom_is_panel=1.
        return True

    return False


def _get_patient_type(patient_doc_or_name):
    if isinstance(patient_doc_or_name, str):
        if not frappe.db.exists("Patient", patient_doc_or_name):
            return ""
        customer_group = frappe.db.get_value("Patient", patient_doc_or_name, "customer_group")
    else:
        customer_group = patient_doc_or_name.get("customer_group")
    return customer_group or ""


def _get_patient_customer(patient_doc_or_name):
    if isinstance(patient_doc_or_name, str):
        if not frappe.db.exists("Patient", patient_doc_or_name):
            return None
        if _safe_has_field("Patient", "customer"):
            return frappe.db.get_value("Patient", patient_doc_or_name, "customer")
        return None
    return patient_doc_or_name.get("customer")


def _get_patient_panel(patient_doc_or_name):
    if isinstance(patient_doc_or_name, str):
        if not frappe.db.exists("Patient", patient_doc_or_name):
            return None
        if _safe_has_field("Patient", "custom_panel_customer"):
            return frappe.db.get_value("Patient", patient_doc_or_name, "custom_panel_customer")
        return None
    return patient_doc_or_name.get("custom_panel_customer")


def _get_patient_funding_source(patient_doc_or_name):
    if isinstance(patient_doc_or_name, str):
        if not frappe.db.exists("Patient", patient_doc_or_name):
            return None
        if _safe_has_field("Patient", "custom_kpws_funding_source"):
            return frappe.db.get_value("Patient", patient_doc_or_name, "custom_kpws_funding_source")
        return None
    return patient_doc_or_name.get("custom_kpws_funding_source")


def _set_if_has(doc, fieldname, value):
    if doc.meta.has_field(fieldname):
        doc.set(fieldname, value)


def _settings():
    if frappe.db.exists("DocType", "KPWS Pharmacy Billing Settings"):
        try:
            return frappe.get_single("KPWS Pharmacy Billing Settings")
        except Exception:
            pass
    return frappe._dict()


def _get_cash_mode():
    s = _settings()
    return s.get("cash_mode_of_payment") or "Cash"


def _get_card_mode():
    s = _settings()
    return s.get("card_mode_of_payment") or "Credit Card"


def _get_panel_receivable():
    s = _settings()
    return s.get("panel_receivable_account") or PANEL_RECEIVABLE


def _get_welfare_receivable():
    s = _settings()
    return s.get("welfare_receivable_account") or WELFARE_RECEIVABLE


def _get_income_accounts():
    s = _settings()
    return {
        "cash_income": s.get("cash_income_account") or "SALES (PHARMACY) - KPWS",
        "panel_income": s.get("panel_income_account") or "SALES (PANEL) - KPWS",
        "cogs": s.get("pharmacy_cogs_account") or "COST OF GOODS SOLD - KPWS",
    }


def install():
    """Run after files are copied. Creates fields, page, and basic settings."""
    ensure_customer_groups()
    ensure_custom_fields()
    ensure_prf_options()
    ensure_page_doc()
    ensure_basic_settings()
    ensure_client_helpers()
    frappe.clear_cache()
    frappe.db.commit()
    return "KPWS Patient Intake Flow v51 installed"


def ensure_customer_groups():
    for name in [PATIENT_TYPE_CASH, PATIENT_TYPE_WELFARE, PATIENT_TYPE_PANEL, PATIENT_TYPE_ADVANCE]:
        _ensure_customer_group(name)


def ensure_custom_fields():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    patient_fields = [
        {
            "fieldname": "custom_kpws_cnic",
            "label": "CNIC",
            "fieldtype": "Data",
            "insert_after": "patient_name",
            "reqd": 1,
            "description": "Mandatory CNIC. System normalizes this for duplicate checking.",
        },
        {
            "fieldname": "custom_kpws_cnic_normalized",
            "label": "CNIC Normalized",
            "fieldtype": "Data",
            "insert_after": "custom_kpws_cnic",
            "read_only": 1,
            "hidden": 1,
            "unique": 1,
        },
        {
            "fieldname": "custom_kpws_funding_source",
            "label": "Funding Source",
            "fieldtype": "Select",
            "options": "\nSelf Paid\nZakat\nDonation\nPanel\nPersonal Advance",
            "insert_after": "customer_group",
            "depends_on": "eval:((doc.customer_group || '').toLowerCase().includes('welfare') || (doc.customer_group || '').toLowerCase().includes('advance'))",
        },
        {
            "fieldname": "custom_kpws_approved_percentage",
            "label": "Approved Welfare Percentage",
            "fieldtype": "Percent",
            "insert_after": "custom_kpws_funding_source",
            "read_only": 1,
        },
        {
            "fieldname": "custom_kpws_latest_registration",
            "label": "Latest Welfare Registration",
            "fieldtype": "Link",
            "options": "Patient Registration Form",
            "insert_after": "custom_kpws_approved_percentage",
            "read_only": 1,
        },
    ]

    prf_fields = [
        {
            "fieldname": "custom_kpws_funding_source",
            "label": "Funding Source",
            "fieldtype": "Select",
            "options": "\nZakat\nDonation\nPanel",
            "insert_after": "custom_billing_type",
        },
        {
            "fieldname": "custom_kpws_approval_remarks",
            "label": "Approval Remarks",
            "fieldtype": "Small Text",
            "insert_after": "custom_kpws_welfare_percentage",
        },
    ]

    si_fields = [
        {
            "fieldname": "custom_kpws_billing_decision",
            "label": "KPWS Billing Decision",
            "fieldtype": "Data",
            "insert_after": "custom_kpws_patient_billing_group",
            "read_only": 1,
            "allow_on_submit": 1,
        },
        {
            "fieldname": "custom_kpws_funding_source",
            "label": "KPWS Funding Source",
            "fieldtype": "Data",
            "insert_after": "custom_kpws_billing_decision",
            "read_only": 1,
            "allow_on_submit": 1,
        },
        {
            "fieldname": "custom_kpws_advance_used_amount",
            "label": "Advance Used Amount",
            "fieldtype": "Currency",
            "insert_after": "custom_kpws_patient_card_amount",
            "read_only": 1,
            "allow_on_submit": 1,
        },
        {
            "fieldname": "custom_kpws_advance_payment_entry",
            "label": "Advance Payment Entry",
            "fieldtype": "Link",
            "options": "Payment Entry",
            "insert_after": "custom_kpws_advance_used_amount",
            "read_only": 1,
            "allow_on_submit": 1,
        },
    ]

    custom_fields = {
        "Patient": patient_fields,
        "Patient Registration Form": prf_fields,
        "Sales Invoice": si_fields,
    }

    create_custom_fields(custom_fields, update=True)

    # Schema sync
    for dt in custom_fields:
        frappe.clear_cache(doctype=dt)
        frappe.db.updatedb(dt)


def _update_field_options(dt, fieldname, options):
    """Updates options for both DocField and Custom Field if present."""
    if frappe.db.exists("Custom Field", {"dt": dt, "fieldname": fieldname}):
        name = frappe.db.get_value("Custom Field", {"dt": dt, "fieldname": fieldname}, "name")
        frappe.db.set_value("Custom Field", name, "options", options, update_modified=False)

    # In custom doctypes, fields may live in DocField
    rows = frappe.get_all("DocField", filters={"parent": dt, "fieldname": fieldname}, fields=["name"])
    for r in rows:
        frappe.db.set_value("DocField", r.name, "options", options, update_modified=False)


def ensure_prf_options():
    opts = "\nZakat\nDonation\nPanel"
    for fieldname in ("purpose", "custom_kpws_welfare_type", "custom_kpws_funding_source"):
        if _safe_has_field("Patient Registration Form", fieldname):
            _update_field_options("Patient Registration Form", fieldname, opts)

    frappe.clear_cache(doctype="Patient Registration Form")


def ensure_page_doc():
    if not frappe.db.exists("Page", INTAKE_PAGE_NAME):
        page = frappe.new_doc("Page")
        page.page_name = INTAKE_PAGE_NAME
        page.title = INTAKE_PAGE_TITLE
        page.module = "Kpws Customization"
        page.standard = "No"
        page.insert(ignore_permissions=True)
    else:
        frappe.db.set_value("Page", INTAKE_PAGE_NAME, "title", INTAKE_PAGE_TITLE, update_modified=False)
        frappe.db.set_value("Page", INTAKE_PAGE_NAME, "module", "Kpws Customization", update_modified=False)


def ensure_basic_settings():
    """Keep existing settings, only fill missing values."""
    if not frappe.db.exists("DocType", "KPWS Pharmacy Billing Settings"):
        return

    s = frappe.get_single("KPWS Pharmacy Billing Settings")
    changed = False

    defaults = {
        "cash_mode_of_payment": "Cash",
        "card_mode_of_payment": "Credit Card",
        "welfare_receivable_account": WELFARE_RECEIVABLE,
        "panel_receivable_account": PANEL_RECEIVABLE,
        "panel_billing_mode": "Receivable",
        "cash_income_account": "SALES (PHARMACY) - KPWS",
        "panel_income_account": "SALES (PANEL) - KPWS",
        "pharmacy_cogs_account": "COST OF GOODS SOLD - KPWS",
    }

    for field, value in defaults.items():
        if hasattr(s, field) or s.get(field) is not None:
            if not s.get(field):
                s.set(field, value)
                changed = True

    if changed:
        s.save(ignore_permissions=True)


def ensure_client_helpers():
    """Small Patient form helper. Main UI is the custom page."""
    script_name = "KPWS Patient Intake Quick Actions V51"
    script = r"""
frappe.ui.form.on("Patient", {
    refresh(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__("Open KPWS Intake"), function() {
                frappe.set_route("kpws-patient-intake", { patient: frm.doc.name });
            }, __("KPWS"));

            frm.add_custom_button(__("Create / Update Welfare Registration"), function() {
                frappe.call({
                    method: "kpws_customization.api.kpws_patient_intake_v51.create_or_update_registration",
                    args: { patient: frm.doc.name },
                    freeze: true,
                    callback: function(r) {
                        if (r.message && r.message.name) {
                            frappe.set_route("Form", "Patient Registration Form", r.message.name);
                        }
                    }
                });
            }, __("KPWS"));
        }
    }
});
"""
    if frappe.db.exists("Client Script", script_name):
        cs = frappe.get_doc("Client Script", script_name)
        cs.script = script
        cs.enabled = 1
        cs.dt = "Patient"
        cs.view = "Form"
        cs.save(ignore_permissions=True)
    else:
        cs = frappe.new_doc("Client Script")
        cs.name = script_name
        cs.dt = "Patient"
        cs.view = "Form"
        cs.enabled = 1
        cs.script = script
        cs.insert(ignore_permissions=True)


def validate_patient(doc, method=None):
    """Backend validation for Patient, including CNIC and dynamic classification rules."""
    # Only enforce for KPWS style patient records; practically all patients here are KPWS.
    if doc.doctype != "Patient":
        return

    if doc.meta.has_field("custom_kpws_cnic"):
        cnic = _norm_text(doc.get("custom_kpws_cnic"))
        normalized = normalize_cnic(cnic)

        if not normalized:
            frappe.throw(_("CNIC is mandatory for KPWS Patient."))

        if len(normalized) != 13:
            frappe.throw(_("CNIC must be 13 digits. Example: 42101-1234567-1"))

        doc.custom_kpws_cnic = pretty_cnic(normalized)
        if doc.meta.has_field("custom_kpws_cnic_normalized"):
            doc.custom_kpws_cnic_normalized = normalized

        # Duplicate check using normalized field
        if doc.meta.has_field("custom_kpws_cnic_normalized"):
            duplicate = frappe.db.get_value(
                "Patient",
                {
                    "custom_kpws_cnic_normalized": normalized,
                    "name": ["!=", doc.name or ""],
                },
                "name",
            )
            if duplicate:
                frappe.throw(_("Another Patient already exists with this CNIC: {0}").format(duplicate))

    patient_type = _get_patient_type(doc)
    funding = _get_patient_funding_source(doc)
    panel = _get_patient_panel(doc)

    if not patient_type:
        frappe.throw(_("Patient Type is mandatory."))

    if patient_type == PATIENT_TYPE_WELFARE:
        if not funding:
            frappe.throw(_("Funding Source is mandatory when Patient Type is Welfare."))

        if funding == FUNDING_PANEL and not panel:
            frappe.throw(_("Panel Customer is mandatory when Welfare Funding Source is Panel."))

        if panel and not _is_panel_customer(panel):
            frappe.throw(_("Selected Panel Customer must be marked as Is Panel on Customer."))

    if patient_type == PATIENT_TYPE_PANEL:
        if not panel:
            frappe.throw(_("Panel Customer is mandatory when Patient Type is Panel."))
        if not _is_panel_customer(panel):
            frappe.throw(_("Selected Panel Customer must be marked as Is Panel on Customer."))

    if patient_type == PATIENT_TYPE_ADVANCE:
        if doc.meta.has_field("custom_kpws_funding_source"):
            doc.custom_kpws_funding_source = FUNDING_ADVANCE


def validate_prf(doc, method=None):
    if doc.doctype != "Patient Registration Form":
        return

    # Sync purpose fields
    purpose = (
        doc.get("custom_kpws_funding_source")
        or doc.get("custom_kpws_welfare_type")
        or doc.get("purpose")
        or ""
    ).strip()

    if purpose:
        _set_if_has(doc, "purpose", purpose)
        _set_if_has(doc, "custom_kpws_welfare_type", purpose)
        _set_if_has(doc, "custom_kpws_funding_source", purpose)

    percentage = flt(doc.get("custom_kpws_welfare_percentage") or doc.get("discount_value") or 0, 2)
    if percentage:
        _set_if_has(doc, "custom_kpws_welfare_percentage", percentage)
        _set_if_has(doc, "discount_value", percentage)

    patient = doc.get("custom_patient")
    if patient and frappe.db.exists("Patient", patient):
        p = frappe.get_doc("Patient", patient)
        _set_if_has(doc, "custom_patient_name", p.get("patient_name"))
        _set_if_has(doc, "custom_mr_number", p.get("custom_reference_number"))
        _set_if_has(doc, "custom_patient_customer", p.get("customer"))
        _set_if_has(doc, "custom_billing_type", p.get("customer_group"))

        if not purpose and p.get("custom_kpws_funding_source"):
            purpose = p.get("custom_kpws_funding_source")
            _set_if_has(doc, "purpose", purpose)
            _set_if_has(doc, "custom_kpws_welfare_type", purpose)
            _set_if_has(doc, "custom_kpws_funding_source", purpose)

        if purpose == FUNDING_PANEL and not doc.get("custom_panel_customer") and p.get("custom_panel_customer"):
            _set_if_has(doc, "custom_panel_customer", p.get("custom_panel_customer"))

    if purpose in (FUNDING_ZAKAT, FUNDING_DONATION):
        if flt(doc.get("custom_kpws_welfare_percentage") or doc.get("discount_value")) <= 0:
            frappe.throw(_("Percentage is required for Zakat/Donation welfare approval."))

    if purpose == FUNDING_PANEL:
        if not doc.get("custom_panel_customer"):
            frappe.throw(_("Panel Customer is required when Funding Source is Panel."))
        if not _is_panel_customer(doc.get("custom_panel_customer")):
            frappe.throw(_("Selected Panel Customer must be marked as Is Panel on Customer."))
        # default panel to 100% if not provided
        if flt(doc.get("custom_kpws_welfare_percentage") or doc.get("discount_value")) <= 0:
            _set_if_has(doc, "custom_kpws_welfare_percentage", 100)
            _set_if_has(doc, "discount_value", 100)


def on_prf_submit(doc, method=None):
    """Approved/submitted PRF is source of truth for welfare funding."""
    patient = doc.get("custom_patient")
    if not patient or not frappe.db.exists("Patient", patient):
        return

    p = frappe.get_doc("Patient", patient)

    purpose = doc.get("custom_kpws_funding_source") or doc.get("custom_kpws_welfare_type") or doc.get("purpose")
    percentage = flt(doc.get("custom_kpws_welfare_percentage") or doc.get("discount_value") or 0, 2)
    panel = doc.get("custom_panel_customer")

    updates = {}

    if p.meta.has_field("custom_kpws_funding_source") and purpose:
        updates["custom_kpws_funding_source"] = purpose

    if p.meta.has_field("custom_kpws_approved_percentage"):
        updates["custom_kpws_approved_percentage"] = percentage

    if p.meta.has_field("custom_kpws_latest_registration"):
        updates["custom_kpws_latest_registration"] = doc.name

    if purpose == FUNDING_PANEL and panel and p.meta.has_field("custom_panel_customer"):
        updates["custom_panel_customer"] = panel

    if p.meta.has_field("customer_group"):
        # Keep patient as welfare for welfare registration.
        updates["customer_group"] = PATIENT_TYPE_WELFARE

    for field, value in updates.items():
        frappe.db.set_value("Patient", patient, field, value, update_modified=False)

    _create_type_change_log(patient, updates, "Patient Registration approved/submitted")


def _create_type_change_log(patient, updates, reason=None):
    if not frappe.db.exists("DocType", "KPWS Patient Type Change Log"):
        return

    try:
        log = frappe.new_doc("KPWS Patient Type Change Log")
        if log.meta.has_field("patient"):
            log.patient = patient
        if log.meta.has_field("remarks"):
            log.remarks = reason or json.dumps(updates, default=str)
        elif log.meta.has_field("reason"):
            log.reason = reason or json.dumps(updates, default=str)
        # best effort for fields if they exist
        for k, v in updates.items():
            if log.meta.has_field(k):
                log.set(k, v)
        log.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "KPWS Patient Type Change Log failed")


def latest_registration(patient):
    if not patient or not frappe.db.exists("Patient", patient):
        return None

    rows = frappe.get_all(
        "Patient Registration Form",
        filters={
            "custom_patient": patient,
            "docstatus": 1,
        },
        fields=["name", "custom_kpws_welfare_type", "purpose", "custom_kpws_funding_source",
                "custom_kpws_welfare_percentage", "discount_value", "custom_panel_customer", "workflow_state"],
        order_by="modified desc",
        limit=1,
    )
    return rows[0] if rows else None


def get_advance_balance_for_customer(customer):
    if not customer:
        return 0

    # ERPNext Payment Entry unallocated balance is the safest source for customer advance.
    total = frappe.db.sql("""
        SELECT COALESCE(SUM(unallocated_amount), 0)
        FROM `tabPayment Entry`
        WHERE docstatus=1
          AND payment_type='Receive'
          AND party_type='Customer'
          AND party=%s
          AND unallocated_amount > 0
    """, (customer,))[0][0] or 0

    return flt(total, 2)


def get_advance_entries(customer, limit=20):
    if not customer:
        return []
    return frappe.db.sql("""
        SELECT name, posting_date, paid_amount, unallocated_amount, mode_of_payment
        FROM `tabPayment Entry`
        WHERE docstatus=1
          AND payment_type='Receive'
          AND party_type='Customer'
          AND party=%s
          AND unallocated_amount > 0
        ORDER BY posting_date asc, creation asc
        LIMIT %s
    """, (customer, int(limit or 20)), as_dict=True)


def get_billing_decision(patient):
    if not patient or not frappe.db.exists("Patient", patient):
        frappe.throw(_("Patient not found"))

    p = frappe.get_doc("Patient", patient)
    patient_type = p.get("customer_group") or PATIENT_TYPE_CASH
    funding = p.get("custom_kpws_funding_source") if p.meta.has_field("custom_kpws_funding_source") else None
    panel = p.get("custom_panel_customer") if p.meta.has_field("custom_panel_customer") else None
    patient_customer = p.get("customer") if p.meta.has_field("customer") else None

    reg = latest_registration(patient)
    reg_purpose = None
    reg_percentage = 0
    reg_panel = None

    if reg:
        reg_purpose = reg.get("custom_kpws_funding_source") or reg.get("custom_kpws_welfare_type") or reg.get("purpose")
        reg_percentage = flt(reg.get("custom_kpws_welfare_percentage") or reg.get("discount_value") or 0, 2)
        reg_panel = reg.get("custom_panel_customer")

    # Approved PRF overrides patient funding for welfare.
    if patient_type == PATIENT_TYPE_WELFARE and reg:
        funding = reg_purpose or funding
        panel = reg_panel or panel

    decision = {
        "patient": patient,
        "patient_name": p.get("patient_name"),
        "mr_number": p.get("custom_reference_number"),
        "cnic": p.get("custom_kpws_cnic"),
        "patient_type": patient_type,
        "funding_source": funding or FUNDING_SELF,
        "approved_percentage": reg_percentage or flt(p.get("custom_kpws_approved_percentage") or 0, 2),
        "panel_customer": panel,
        "patient_customer": patient_customer,
        "latest_registration": reg.get("name") if reg else None,
        "registration_status": "Approved" if reg else "Missing",
        "billing_type": "Cash",
        "invoice_mode": "POS",
        "bill_to_customer": patient_customer,
        "debit_to": None,
        "income_account": _get_income_accounts()["cash_income"],
        "requires_payment_now": True,
        "expected_status_after_submit": "Paid",
        "advance_balance": 0,
        "warnings": [],
    }

    if patient_type == PATIENT_TYPE_WELFARE:
        if not reg:
            decision["billing_type"] = "Welfare Missing Approval"
            decision["invoice_mode"] = "Blocked"
            decision["warnings"].append("Welfare patient has no approved Patient Registration Form.")
            return decision

        if decision["funding_source"] == FUNDING_PANEL:
            decision.update({
                "billing_type": "Welfare Panel",
                "invoice_mode": "Non-POS Panel Receivable",
                "bill_to_customer": panel,
                "debit_to": _get_panel_receivable(),
                "income_account": _get_income_accounts()["panel_income"],
                "requires_payment_now": False,
                "expected_status_after_submit": "Unpaid",
            })
            if not panel:
                decision["warnings"].append("Panel Customer is required for Welfare Panel.")
        elif decision["funding_source"] in (FUNDING_ZAKAT, FUNDING_DONATION):
            decision.update({
                "billing_type": "Welfare " + decision["funding_source"],
                "invoice_mode": "Non-POS Welfare Settlement",
                "bill_to_customer": patient_customer,
                "debit_to": _get_welfare_receivable(),
                "income_account": _get_income_accounts()["cash_income"],
                "requires_payment_now": True,
                "expected_status_after_submit": "Paid when JV + patient share are posted",
            })
            if decision["approved_percentage"] <= 0:
                decision["warnings"].append("Approved percentage is required for Welfare Zakat/Donation.")
        else:
            decision["warnings"].append("Invalid or missing Welfare Funding Source.")

    elif patient_type == PATIENT_TYPE_PANEL:
        decision.update({
            "funding_source": FUNDING_PANEL,
            "billing_type": "Panel",
            "invoice_mode": "Non-POS Panel Receivable",
            "bill_to_customer": panel,
            "debit_to": _get_panel_receivable(),
            "income_account": _get_income_accounts()["panel_income"],
            "requires_payment_now": False,
            "expected_status_after_submit": "Unpaid",
        })
        if not panel:
            decision["warnings"].append("Panel Customer is required for Panel patient.")

    elif patient_type == PATIENT_TYPE_ADVANCE or funding == FUNDING_ADVANCE:
        balance = get_advance_balance_for_customer(patient_customer)
        decision.update({
            "funding_source": FUNDING_ADVANCE,
            "billing_type": "Personal Advance",
            "invoice_mode": "Non-POS Advance Allocation",
            "bill_to_customer": patient_customer,
            "debit_to": None,
            "income_account": _get_income_accounts()["cash_income"],
            "requires_payment_now": True,
            "expected_status_after_submit": "Paid if advance/cash covers invoice",
            "advance_balance": balance,
        })
        if not patient_customer:
            decision["warnings"].append("Patient linked customer is required for Personal Advance.")

    return decision


@frappe.whitelist()
def search_patients(q=None, limit=20):
    q = (q or "").strip()
    filters = []
    or_filters = []

    if q:
        like = f"%{q}%"
        fields = ["name", "patient_name", "custom_reference_number", "customer_group", "custom_kpws_cnic", "customer"]
        for f in fields:
            if f == "name" or _safe_has_field("Patient", f):
                or_filters.append([f, "like", like])

        norm = normalize_cnic(q)
        if norm and _safe_has_field("Patient", "custom_kpws_cnic_normalized"):
            or_filters.append(["custom_kpws_cnic_normalized", "like", f"%{norm}%"])

    fields = ["name", "patient_name"]
    for f in ["custom_reference_number", "custom_kpws_cnic", "customer_group", "custom_panel_customer", "custom_kpws_funding_source", "customer"]:
        if _safe_has_field("Patient", f):
            fields.append(f)

    return frappe.get_all(
        "Patient",
        filters=filters,
        or_filters=or_filters or None,
        fields=fields,
        limit=int(limit or 20),
        order_by="modified desc",
    )


@frappe.whitelist()
def get_patient_context(patient):
    if not patient:
        return {}

    p = frappe.get_doc("Patient", patient)
    data = p.as_dict()
    decision = get_billing_decision(patient)
    reg = latest_registration(patient)

    return {
        "patient": data,
        "decision": decision,
        "registration": reg,
        "advance_entries": get_advance_entries(decision.get("patient_customer")) if decision.get("patient_customer") else [],
    }


@frappe.whitelist()
def get_panel_customers(txt=None, limit=20):
    txt = (txt or "").strip()
    filters = {}
    or_filters = []

    if _safe_has_field("Customer", "custom_is_panel"):
        filters["custom_is_panel"] = 1
    else:
        filters["customer_group"] = "Panel"

    if txt:
        like = f"%{txt}%"
        or_filters = [["name", "like", like], ["customer_name", "like", like]]

    return frappe.get_all(
        "Customer",
        filters=filters,
        or_filters=or_filters or None,
        fields=["name", "customer_name", "customer_group"],
        limit=int(limit or 20),
        order_by="modified desc",
    )


@frappe.whitelist()
def save_patient(payload):
    if isinstance(payload, str):
        payload = json.loads(payload)

    name = payload.get("name")
    if name and frappe.db.exists("Patient", name):
        doc = frappe.get_doc("Patient", name)
    else:
        doc = frappe.new_doc("Patient")

    mapping = {
        "patient_name": "patient_name",
        "cnic": "custom_kpws_cnic",
        "mr_number": "custom_reference_number",
        "patient_type": "customer_group",
        "funding_source": "custom_kpws_funding_source",
        "panel_customer": "custom_panel_customer",
        "mobile": "mobile",
        "sex": "sex",
        "dob": "dob",
    }

    for src, target in mapping.items():
        if target == "patient_name" or doc.meta.has_field(target):
            if src in payload:
                doc.set(target, payload.get(src))

    doc.save(ignore_permissions=True)

    return get_patient_context(doc.name)


@frappe.whitelist()
def create_or_update_registration(patient, payload=None):
    if payload and isinstance(payload, str):
        payload = json.loads(payload)
    payload = payload or {}

    if not patient or not frappe.db.exists("Patient", patient):
        frappe.throw(_("Patient is required."))

    p = frappe.get_doc("Patient", patient)

    # Find latest draft PRF for this patient, otherwise create new
    existing = frappe.get_all(
        "Patient Registration Form",
        filters={"custom_patient": patient, "docstatus": 0},
        fields=["name"],
        order_by="modified desc",
        limit=1,
    )

    if existing:
        prf = frappe.get_doc("Patient Registration Form", existing[0].name)
    else:
        prf = frappe.new_doc("Patient Registration Form")
        _set_if_has(prf, "custom_patient", patient)

    funding = payload.get("funding_source") or p.get("custom_kpws_funding_source") or FUNDING_ZAKAT
    percentage = flt(payload.get("percentage") or p.get("custom_kpws_approved_percentage") or 100, 2)
    panel = payload.get("panel_customer") or p.get("custom_panel_customer")

    _set_if_has(prf, "custom_patient", patient)
    _set_if_has(prf, "custom_patient_name", p.get("patient_name"))
    _set_if_has(prf, "custom_mr_number", p.get("custom_reference_number"))
    _set_if_has(prf, "custom_patient_customer", p.get("customer"))
    _set_if_has(prf, "custom_billing_type", p.get("customer_group"))

    _set_if_has(prf, "purpose", funding)
    _set_if_has(prf, "custom_kpws_welfare_type", funding)
    _set_if_has(prf, "custom_kpws_funding_source", funding)
    _set_if_has(prf, "discount_value", percentage)
    _set_if_has(prf, "custom_kpws_welfare_percentage", percentage)

    if panel:
        _set_if_has(prf, "custom_panel_customer", panel)

    if payload.get("remarks"):
        _set_if_has(prf, "custom_kpws_approval_remarks", payload.get("remarks"))

    prf.save(ignore_permissions=True)

    if p.meta.has_field("custom_kpws_latest_registration"):
        frappe.db.set_value("Patient", patient, "custom_kpws_latest_registration", prf.name, update_modified=False)

    frappe.db.commit()

    return {"name": prf.name, "docstatus": prf.docstatus, "context": get_patient_context(patient)}


@frappe.whitelist()
def submit_registration(registration):
    if not registration or not frappe.db.exists("Patient Registration Form", registration):
        frappe.throw(_("Patient Registration Form not found."))

    doc = frappe.get_doc("Patient Registration Form", registration)
    if doc.docstatus == 0:
        doc.submit()

    return {"name": doc.name, "docstatus": doc.docstatus, "patient": doc.get("custom_patient")}


@frappe.whitelist()
def audit_patient_flow(limit=20):
    rows = frappe.get_all(
        "Patient",
        fields=["name", "patient_name", "customer_group", "custom_panel_customer", "customer", "modified"],
        order_by="modified desc",
        limit=int(limit or 20),
    )

    out = []
    for r in rows:
        item = dict(r)
        if _safe_has_field("Patient", "custom_kpws_cnic"):
            item["cnic"] = frappe.db.get_value("Patient", r.name, "custom_kpws_cnic")
        if _safe_has_field("Patient", "custom_kpws_funding_source"):
            item["funding_source"] = frappe.db.get_value("Patient", r.name, "custom_kpws_funding_source")
        try:
            item["decision"] = get_billing_decision(r.name)
        except Exception as e:
            item["decision_error"] = str(e)
        out.append(item)

    return out
