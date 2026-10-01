import frappe
from frappe import _
from frappe.utils import flt


DOCTYPE = "Patient Registration Form"

BASE_ALLOWED_FIELDS = [
    "discount_value",
    "custom_kpws_welfare_percentage",
    "purpose",
    "custom_kpws_welfare_type",
    "custom_kpws_admin_notes",
    "remarks",
]

PERCENTAGE_FIELDNAMES = [
    "discount_value",
    "custom_kpws_welfare_percentage",
]


def _columns(table):
    try:
        return {r["Field"] for r in frappe.db.sql(f"SHOW COLUMNS FROM `{table}`", as_dict=True)}
    except Exception:
        return set()


def _get_actual_fields():
    meta = frappe.get_meta(DOCTYPE)
    fields = set(BASE_ALLOWED_FIELDS)

    for df in meta.fields:
        label = (df.label or "").strip().lower()
        fieldname = df.fieldname

        if not fieldname:
            continue

        if label == "percentage":
            fields.add(fieldname)

        if fieldname in PERCENTAGE_FIELDNAMES:
            fields.add(fieldname)

    return sorted(fields)


def _get_percentage_fields():
    meta = frappe.get_meta(DOCTYPE)
    fields = set(PERCENTAGE_FIELDNAMES)

    for df in meta.fields:
        if (df.label or "").strip().lower() == "percentage":
            fields.add(df.fieldname)

    return sorted([f for f in fields if meta.has_field(f)])


def _upsert_property_setter(fieldname, prop, value, property_type):
    existing = frappe.db.exists("Property Setter", {
        "doc_type": DOCTYPE,
        "doctype_or_field": "DocField",
        "field_name": fieldname,
        "property": prop,
    })

    if existing:
        ps = frappe.get_doc("Property Setter", existing)
        ps.value = value
        ps.property_type = property_type
        ps.save(ignore_permissions=True)
    else:
        frappe.get_doc({
            "doctype": "Property Setter",
            "doctype_or_field": "DocField",
            "doc_type": DOCTYPE,
            "field_name": fieldname,
            "property": prop,
            "property_type": property_type,
            "value": value,
        }).insert(ignore_permissions=True)


def _force_docfield_update(fields, percentage_fields):
    docfield_cols = _columns("tabDocField")
    customfield_cols = _columns("tabCustom Field")

    changed = []

    for fieldname in fields:
        # Direct DocField update
        if "allow_on_submit" in docfield_cols:
            frappe.db.sql(
                """
                UPDATE `tabDocField`
                SET allow_on_submit = 1
                WHERE parent = %s AND fieldname = %s
                """,
                (DOCTYPE, fieldname),
            )
            changed.append(f"DocField {fieldname}.allow_on_submit=1")

        # Direct Custom Field update
        if "allow_on_submit" in customfield_cols:
            frappe.db.sql(
                """
                UPDATE `tabCustom Field`
                SET allow_on_submit = 1
                WHERE dt = %s AND fieldname = %s
                """,
                (DOCTYPE, fieldname),
            )
            changed.append(f"Custom Field {fieldname}.allow_on_submit=1")

        _upsert_property_setter(fieldname, "allow_on_submit", "1", "Check")

    for fieldname in percentage_fields:
        if "read_only" in docfield_cols:
            frappe.db.sql(
                """
                UPDATE `tabDocField`
                SET read_only = 0
                WHERE parent = %s AND fieldname = %s
                """,
                (DOCTYPE, fieldname),
            )

        if "read_only" in customfield_cols:
            frappe.db.sql(
                """
                UPDATE `tabCustom Field`
                SET read_only = 0
                WHERE dt = %s AND fieldname = %s
                """,
                (DOCTYPE, fieldname),
            )

        if "non_negative" in docfield_cols:
            frappe.db.sql(
                """
                UPDATE `tabDocField`
                SET non_negative = 1
                WHERE parent = %s AND fieldname = %s
                """,
                (DOCTYPE, fieldname),
            )

        if "non_negative" in customfield_cols:
            frappe.db.sql(
                """
                UPDATE `tabCustom Field`
                SET non_negative = 1
                WHERE dt = %s AND fieldname = %s
                """,
                (DOCTYPE, fieldname),
            )

        _upsert_property_setter(fieldname, "read_only", "0", "Check")
        _upsert_property_setter(fieldname, "non_negative", "1", "Check")
        _upsert_property_setter(fieldname, "precision", "2", "Data")

    frappe.db.commit()
    return changed


def validate_percentage(doc, method=None):
    for fieldname in _get_percentage_fields():
        value = doc.get(fieldname)

        if value in (None, ""):
            continue

        value = flt(value)

        if value < 0:
            frappe.throw(_("Percentage cannot be negative."), title=_("Invalid Percentage"))

        if value > 100:
            frappe.throw(_("Percentage cannot be more than 100%."), title=_("Invalid Percentage"))


@frappe.whitelist()
def install():
    fields = _get_actual_fields()
    percentage_fields = _get_percentage_fields()

    changed = _force_docfield_update(fields, percentage_fields)

    frappe.clear_cache(doctype=DOCTYPE)
    frappe.clear_cache()
    frappe.db.commit()

    return {
        "ok": True,
        "allowed_update_after_submit_fields": fields,
        "percentage_fields": percentage_fields,
        "changed": changed,
        "message": "PRF Percentage fields forced allow_on_submit at DocField, Custom Field and Property Setter level.",
    }


@frappe.whitelist()
def verify(name=None):
    frappe.clear_cache(doctype=DOCTYPE)
    meta = frappe.get_meta(DOCTYPE)

    result = {}

    for fieldname in _get_actual_fields():
        df = meta.get_field(fieldname)

        if not df:
            continue

        result[fieldname] = {
            "label": df.label,
            "fieldtype": df.fieldtype,
            "allow_on_submit": df.allow_on_submit,
            "read_only": df.read_only,
            "non_negative": getattr(df, "non_negative", None),
            "precision": getattr(df, "precision", None),
        }

    doc = None
    if name and frappe.db.exists(DOCTYPE, name):
        doc = frappe.db.get_value(
            DOCTYPE,
            name,
            ["name", "docstatus", "discount_value", "custom_kpws_welfare_percentage", "modified"],
            as_dict=True,
        )

    return {
        "doctype": DOCTYPE,
        "fields": result,
        "doc": doc,
    }
