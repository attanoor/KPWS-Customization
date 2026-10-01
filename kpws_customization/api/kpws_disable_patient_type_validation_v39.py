from pathlib import Path
import frappe


PATCH_MARKER = "KPWS_DISABLE_PATIENT_TYPE_VALIDATION_V39"


NOOP_FUNCTION = '''
# KPWS_DISABLE_PATIENT_TYPE_VALIDATION_V39
def validate_patient_clean(doc, method=None):
    """
    Patient Type validation disabled.

    User can freely change Patient Type / Customer Group to:
    Cash, Welfare, Panel, or any other value.

    Panel Customer is no longer mandatory on Patient save.
    Pharmacy/Sales Invoice controls will handle billing validation separately.
    """
    return
'''


def _disable_validation(path):
    p = Path(path)

    if not p.exists():
        return {
            "path": str(p),
            "exists": False,
            "changed": False,
        }

    text = p.read_text()

    backup = p.with_suffix(p.suffix + ".bak_disable_patient_type_v39")
    if not backup.exists():
        backup.write_text(text)

    # If already patched, still force-disable the exact old throw line.
    text = text.replace(
        'frappe.throw(_("Panel patient requires Panel Name / Panel Customer."))',
        'return  # KPWS v39 disabled panel requirement'
    )

    text = text.replace(
        "frappe.throw(_('Panel patient requires Panel Name / Panel Customer.'))",
        "return  # KPWS v39 disabled panel requirement"
    )

    # Append final override at the very end. In Python, the last function definition wins.
    if PATCH_MARKER not in text:
        text = text.rstrip() + "\n\n" + NOOP_FUNCTION + "\n"

    p.write_text(text)

    return {
        "path": str(p),
        "exists": True,
        "changed": True,
        "backup": str(backup),
    }


@frappe.whitelist()
def install():
    app_path = Path(frappe.get_app_path("kpws_customization"))

    target = app_path / "api" / "kpws_clean_flow.py"
    result = _disable_validation(target)

    frappe.clear_cache()
    frappe.db.commit()

    return {
        "ok": True,
        "result": result,
        "message": "Patient Type validation fully disabled. Panel Customer is no longer required on Patient save.",
    }


@frappe.whitelist()
def verify():
    app_path = Path(frappe.get_app_path("kpws_customization"))
    target = app_path / "api" / "kpws_clean_flow.py"

    text = target.read_text() if target.exists() else ""

    return {
        "file": str(target),
        "patch_marker_found": PATCH_MARKER in text,
        "old_panel_throw_still_found": "Panel patient requires Panel Name / Panel Customer" in text,
    }
