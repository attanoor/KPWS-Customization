import frappe


@frappe.whitelist()
def get_patient_assigned_panel(patient=None):
    if not patient:
        return {}

    patient = str(patient).strip()
    patient_id = patient

    if not frappe.db.exists("Patient", patient_id):
        patient_id = frappe.db.get_value("Patient", {"patient_name": patient}, "name")

    if not patient_id:
        return {"found": 0, "message": "Patient not found"}

    patient_meta = frappe.get_meta("Patient")

    for f in ["panel_name", "custom_panel_name", "custom_panel", "panel", "customer"]:
        if patient_meta.get_field(f):
            value = frappe.db.get_value("Patient", patient_id, f)

            if value and frappe.db.exists("Customer", value):
                is_panel = frappe.db.get_value("Customer", value, "custom_is_panel") or 0

                if is_panel:
                    customer_name = frappe.db.get_value("Customer", value, "customer_name") or value

                    return {
                        "found": 1,
                        "panel_found": 1,
                        "panel_customer": value,
                        "panel_name": customer_name,
                        "patient_panel_field": f
                    }

    return {
        "found": 1,
        "panel_found": 0,
        "message": "No panel assigned on Patient"
    }
