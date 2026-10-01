from pathlib import Path
import frappe


TARGET_FILE = "apps/kpws_customization/kpws_customization/api/kpws_patient_type_change_flow_v46.py"
PATCH_MARKER = "KPWS_PATIENT_TYPE_CHANGE_FLOW_V47_SAFE_DB_FIELDS"


PATCH = r'''

# KPWS_PATIENT_TYPE_CHANGE_FLOW_V47_SAFE_DB_FIELDS
# Fix: do not update layout/meta-only fields like customer_details_section.

def _kpws_v47_table_columns(doctype):
    try:
        return {
            r["Field"]
            for r in frappe.db.sql(f"SHOW COLUMNS FROM `tab{doctype}`", as_dict=True)
        }
    except Exception:
        return set()


def _kpws_v47_is_real_db_field(doctype, fieldname):
    if not fieldname:
        return False

    columns = _kpws_v47_table_columns(doctype)

    if fieldname not in columns:
        return False

    try:
        df = frappe.get_meta(doctype).get_field(fieldname)
        if df and df.fieldtype in (
            "Section Break",
            "Column Break",
            "Tab Break",
            "HTML",
            "Button",
            "Table",
            "Table MultiSelect",
            "Fold",
            "Heading",
        ):
            return False
    except Exception:
        pass

    return True


def _patient_type_fields():
    meta = frappe.get_meta(PATIENT_DTYPE)
    columns = _kpws_v47_table_columns(PATIENT_DTYPE)

    candidates = [
        "customer_group",
        "custom_billing_type",
        "billing_type",
        "patient_type",
        "custom_patient_type",
        "custom_kpws_billing_type",
        "custom_kpws_requested_patient_type",
    ]

    fields = []

    for f in candidates:
        if f in columns and meta.has_field(f) and _kpws_v47_is_real_db_field(PATIENT_DTYPE, f):
            fields.append(f)

    for df in meta.fields:
        if not df.fieldname:
            continue

        if df.fieldname in fields:
            continue

        if df.fieldname not in columns:
            continue

        if df.fieldtype in (
            "Section Break",
            "Column Break",
            "Tab Break",
            "HTML",
            "Button",
            "Table",
            "Table MultiSelect",
            "Fold",
            "Heading",
        ):
            continue

        label = (df.label or "").lower()
        fieldname = (df.fieldname or "").lower()

        if "patient type" in label or "billing type" in label:
            fields.append(df.fieldname)

    return fields


def _panel_fields():
    meta = frappe.get_meta(PATIENT_DTYPE)
    columns = _kpws_v47_table_columns(PATIENT_DTYPE)

    known = [
        "custom_panel_customer",
        "panel_customer",
        "panel",
        "custom_panel",
        "custom_kpws_panel_customer",
        "custom_kpws_assigned_panel_customer",
        "custom_assigned_panel_customer",
    ]

    fields = []

    for f in known:
        if f in columns and meta.has_field(f) and _kpws_v47_is_real_db_field(PATIENT_DTYPE, f):
            fields.append(f)

    for df in meta.fields:
        if not df.fieldname:
            continue

        if df.fieldname in fields:
            continue

        if df.fieldname not in columns:
            continue

        if df.fieldtype in (
            "Section Break",
            "Column Break",
            "Tab Break",
            "HTML",
            "Button",
            "Table",
            "Table MultiSelect",
            "Fold",
            "Heading",
        ):
            continue

        label = (df.label or "").lower()
        fieldname = (df.fieldname or "").lower()

        if "panel" in label or "panel" in fieldname:
            fields.append(df.fieldname)

    return fields


def _set_patient_type_raw(patient, new_type, panel_customer=None):
    doc = frappe.get_doc(PATIENT_DTYPE, patient)
    columns = _kpws_v47_table_columns(PATIENT_DTYPE)

    updates = {}

    for f in _patient_type_fields():
        if f in columns:
            updates[f] = new_type

    if new_type == "Panel":
        if panel_customer:
            for f in _panel_fields():
                if f in columns:
                    updates[f] = panel_customer
    else:
        for f in _panel_fields():
            if f in columns:
                updates[f] = None

    # Final safety: remove anything that is not an actual DB column.
    updates = {
        key: value
        for key, value in updates.items()
        if key in columns and _kpws_v47_is_real_db_field(PATIENT_DTYPE, key)
    }

    if updates:
        frappe.db.set_value(PATIENT_DTYPE, patient, updates, update_modified=True)

    customer = _get_linked_customer(doc)

    if customer and frappe.db.exists("Customer Group", new_type):
        frappe.db.set_value("Customer", customer, "customer_group", new_type, update_modified=True)

    frappe.db.commit()

    return customer


@frappe.whitelist()
def debug_safe_fields():
    return {
        "patient_db_columns_count": len(_kpws_v47_table_columns(PATIENT_DTYPE)),
        "patient_type_fields_used": _patient_type_fields(),
        "panel_fields_used": _panel_fields(),
        "bad_fields_filtered": [
            "customer_details_section",
        ],
    }
'''


def install():
    p = Path(TARGET_FILE)

    if not p.exists():
        return {
            "ok": False,
            "error": f"Target file not found: {TARGET_FILE}",
        }

    text = p.read_text()

    backup = p.with_suffix(p.suffix + ".bak_v47")
    if not backup.exists():
        backup.write_text(text)

    if PATCH_MARKER not in text:
        p.write_text(text.rstrip() + "\n\n" + PATCH + "\n")
        changed = True
    else:
        changed = False

    # Remove pycache so Python reloads cleanly
    import shutil
    for pycache in Path("apps/kpws_customization").rglob("__pycache__"):
        shutil.rmtree(pycache, ignore_errors=True)

    frappe.clear_cache()
    frappe.db.commit()

    return {
        "ok": True,
        "changed": changed,
        "target": TARGET_FILE,
        "backup": str(backup),
        "message": "v47 safe DB field patch installed.",
    }


@frappe.whitelist()
def run():
    return install()
