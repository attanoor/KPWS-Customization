import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def _exists(dt):
    return frappe.db.exists("DocType", dt)


def apply():
    custom_fields = {}

    if _exists("Customer"):
        custom_fields.setdefault("Customer", []).append({
            "fieldname": "custom_is_panel",
            "fieldtype": "Check",
            "label": "Is Panel Customer",
            "insert_after": "customer_group",
            "description": "Check this only for panel/insurance/company customers.",
        })

    if _exists("Patient"):
        custom_fields.setdefault("Patient", []).extend([
            {"fieldname": "custom_patient_billing_type", "fieldtype": "Select", "label": "Patient Billing Type", "options": "\nCash\nWelfare\nPanel", "insert_after": "customer"},
            {"fieldname": "custom_panel_customer", "fieldtype": "Link", "label": "Panel Customer", "options": "Customer", "insert_after": "custom_patient_billing_type", "depends_on": "eval:doc.custom_patient_billing_type=='Panel'"},
            {"fieldname": "custom_latest_welfare_registration", "fieldtype": "Link", "label": "Latest Welfare Registration", "options": "Patient Registration Form", "insert_after": "custom_panel_customer", "read_only": 1},
            {"fieldname": "custom_welfare_type", "fieldtype": "Select", "label": "Welfare Type", "options": "\nZakat\nDonation", "insert_after": "custom_latest_welfare_registration", "read_only": 1},
            {"fieldname": "custom_welfare_percentage", "fieldtype": "Percent", "label": "Welfare Percentage", "insert_after": "custom_welfare_type", "read_only": 1},
        ])

    if _exists("Patient Registration Form"):
        custom_fields.setdefault("Patient Registration Form", []).extend([
            {"fieldname": "custom_kpws_auto_section", "fieldtype": "Section Break", "label": "Auto Filled Patient Details", "insert_after": "naming_series", "collapsible": 1},
            {"fieldname": "custom_patient", "fieldtype": "Link", "label": "Patient", "options": "Patient", "insert_after": "custom_kpws_auto_section", "read_only": 1},
            {"fieldname": "custom_mr_number", "fieldtype": "Data", "label": "MR Number", "insert_after": "custom_patient", "read_only": 1},
            {"fieldname": "custom_patient_customer", "fieldtype": "Link", "label": "Patient Customer", "options": "Customer", "insert_after": "custom_mr_number", "read_only": 1},
            {"fieldname": "custom_billing_type", "fieldtype": "Data", "label": "Billing Type", "insert_after": "custom_patient_customer", "read_only": 1},
            {"fieldname": "custom_admin_section", "fieldtype": "Section Break", "label": "Administrator Welfare Approval", "insert_after": "custom_billing_type"},
            {"fieldname": "custom_assistance_type", "fieldtype": "Select", "label": "Assistance Type", "options": "\nZakat\nDonation", "insert_after": "custom_admin_section"},
            {"fieldname": "custom_coverage_percentage", "fieldtype": "Percent", "label": "Coverage Percentage", "insert_after": "custom_assistance_type"},
            {"fieldname": "custom_panel_customer", "fieldtype": "Link", "label": "Linked Panel", "options": "Customer", "insert_after": "custom_coverage_percentage"},
            {"fieldname": "custom_review_status", "fieldtype": "Select", "label": "Review Status", "options": "\nSubmitted for Review\nApproved\nRejected", "insert_after": "custom_panel_customer", "default": "Submitted for Review"},
            {"fieldname": "custom_approval_remarks", "fieldtype": "Small Text", "label": "Approval Remarks", "insert_after": "custom_review_status"},
        ])

    if _exists("Sales Invoice"):
        custom_fields.setdefault("Sales Invoice", []).extend([
            {"fieldname": "custom_kpws_simple_billing_section", "fieldtype": "Section Break", "label": "Patient Billing", "insert_after": "customer", "collapsible": 1},
            {"fieldname": "custom_is_walkin", "fieldtype": "Check", "label": "Walk-in Patient", "insert_after": "custom_kpws_simple_billing_section"},
            {"fieldname": "custom_patient", "fieldtype": "Link", "label": "Patient", "options": "Patient", "insert_after": "custom_is_walkin", "depends_on": "eval:!doc.custom_is_walkin"},
            {"fieldname": "custom_walkin_patient_name", "fieldtype": "Data", "label": "Walk-in Patient Name", "insert_after": "custom_patient", "depends_on": "eval:doc.custom_is_walkin"},
            {"fieldname": "custom_walkin_mr_number", "fieldtype": "Data", "label": "Walk-in MR Number", "insert_after": "custom_walkin_patient_name", "depends_on": "eval:doc.custom_is_walkin"},
            {"fieldname": "custom_kpws_billing_type", "fieldtype": "Data", "label": "Billing Type", "insert_after": "custom_walkin_mr_number", "read_only": 1},
            {"fieldname": "custom_kpws_panel_customer", "fieldtype": "Link", "label": "Panel", "options": "Customer", "insert_after": "custom_kpws_billing_type", "read_only": 1, "depends_on": "eval:doc.custom_kpws_billing_type=='Panel'"},
            {"fieldname": "custom_kpws_welfare_registration", "fieldtype": "Link", "label": "Welfare Registration", "options": "Patient Registration Form", "insert_after": "custom_kpws_panel_customer", "read_only": 1, "depends_on": "eval:doc.custom_kpws_billing_type=='Welfare'"},
            {"fieldname": "custom_kpws_welfare_type", "fieldtype": "Data", "label": "Welfare Type", "insert_after": "custom_kpws_welfare_registration", "read_only": 1, "depends_on": "eval:doc.custom_kpws_billing_type=='Welfare'"},
            {"fieldname": "custom_kpws_welfare_percentage", "fieldtype": "Percent", "label": "Welfare Percentage", "insert_after": "custom_kpws_welfare_type", "read_only": 1, "depends_on": "eval:doc.custom_kpws_billing_type=='Welfare'"},
        ])

    if custom_fields:
        create_custom_fields(custom_fields, ignore_validate=True, update=True)

    for dt in ["Customer", "Patient", "Patient Registration Form", "Sales Invoice"]:
        if _exists(dt):
            frappe.clear_cache(doctype=dt)
    frappe.db.commit()
    return "KPWS Patient Flow V2 fields applied"
