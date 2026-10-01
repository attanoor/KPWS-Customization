from pathlib import Path
import re
import frappe


PATCH_MARKER = "KPWS_PATIENT_TYPE_VALIDATION_FIX_V38"


NEW_FUNCTION = r'''
# KPWS_PATIENT_TYPE_VALIDATION_FIX_V38
def validate_patient_clean(doc, method=None):
    """
    Safe Patient Type validation for KPWS.

    Rules:
    - Cash patient: no panel required.
    - Welfare patient: no panel required.
    - Panel patient: panel customer is required.
    - Changing patient type away from Panel must not be blocked by old panel validation.
    """

    def _get_first(fields):
        for fieldname in fields:
            try:
                if doc.meta.has_field(fieldname) and doc.get(fieldname) not in (None, ""):
                    return doc.get(fieldname)
            except Exception:
                pass
        return None

    def _set_if_has(fieldname, value):
        try:
            if doc.meta.has_field(fieldname):
                doc.set(fieldname, value)
        except Exception:
            pass

    patient_type = _get_first([
        "customer_group",
        "custom_billing_type",
        "billing_type",
        "patient_type",
        "custom_patient_type",
        "custom_kpws_billing_type",
    ])

    patient_type = (patient_type or "").strip()

    # Normalize allowed values only if user selected one of KPWS billing types.
    if patient_type.lower() == "cash":
        patient_type = "Cash"
    elif patient_type.lower() == "welfare":
        patient_type = "Welfare"
    elif patient_type.lower() == "panel":
        patient_type = "Panel"

    # Keep common billing fields synced when they exist.
    for fieldname in [
        "customer_group",
        "custom_billing_type",
        "billing_type",
        "patient_type",
        "custom_patient_type",
        "custom_kpws_billing_type",
    ]:
        try:
            if doc.meta.has_field(fieldname) and patient_type in ("Cash", "Welfare", "Panel"):
                doc.set(fieldname, patient_type)
        except Exception:
            pass

    panel_customer = _get_first([
        "custom_panel_customer",
        "panel_customer",
        "custom_panel",
        "panel",
        "custom_kpws_panel_customer",
        "custom_assigned_panel_customer",
        "custom_kpws_assigned_panel_customer",
    ])

    # Only Panel patients require panel customer.
    if patient_type == "Panel":
        if not panel_customer:
            frappe.throw("Panel patient requires Panel Name / Panel Customer.")

        # If customer is selected as panel, make sure it is actually marked as panel when flag exists.
        if frappe.db.exists("Customer", panel_customer):
            try:
                customer_meta = frappe.get_meta("Customer")
                panel_flags = [
                    "custom_is_panel",
                    "is_panel",
                    "custom_kpws_is_panel",
                ]

                for flag in panel_flags:
                    if customer_meta.has_field(flag):
                        if not frappe.utils.cint(frappe.db.get_value("Customer", panel_customer, flag)):
                            frappe.throw("Selected Panel Customer is not marked as Is Panel.")
                        break
            except Exception as e:
                # Keep the original validation message readable.
                if "Selected Panel Customer" in str(e):
                    raise

        return

    # For Cash/Welfare patients, panel is optional and must not block Patient save.
    return
'''


def _replace_validate_function(path):
    p = Path(path)

    if not p.exists():
        return {
            "path": str(p),
            "exists": False,
            "changed": False,
        }

    text = p.read_text()

    backup = p.with_suffix(p.suffix + ".bak_v38")
    if not backup.exists():
        backup.write_text(text)

    if PATCH_MARKER in text:
        return {
            "path": str(p),
            "exists": True,
            "changed": False,
            "reason": "already patched",
        }

    pattern = r'\ndef\s+validate_patient_clean\s*\([^)]*\):\n(?:(?!\ndef\s+|\nclass\s+).*\n)*'

    if re.search(pattern, text):
        text2 = re.sub(pattern, "\n" + NEW_FUNCTION + "\n", text, count=1)
    else:
        text2 = text + "\n\n" + NEW_FUNCTION + "\n"

    p.write_text(text2)

    return {
        "path": str(p),
        "exists": True,
        "changed": True,
        "backup": str(backup),
    }


@frappe.whitelist()
def install():
    app_path = Path(frappe.get_app_path("kpws_customization"))

    targets = [
        app_path / "api" / "kpws_clean_flow.py",
        app_path / "kpws_customization" / "api" / "kpws_clean_flow.py",
    ]

    results = [_replace_validate_function(path) for path in targets]

    frappe.clear_cache()
    frappe.db.commit()

    return {
        "ok": True,
        "results": results,
        "message": "Patient Type validation fixed. Panel is required only when Patient Type is Panel.",
    }
