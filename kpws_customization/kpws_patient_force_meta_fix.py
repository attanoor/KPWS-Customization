import json
import frappe
from frappe.utils import now


def _set_if_col_exists(doctype, name, values):
    meta = frappe.get_meta(doctype)
    valid = {df.fieldname for df in meta.fields}
    clean = {k: v for k, v in values.items() if k in valid}
    if clean:
        frappe.db.set_value(doctype, name, clean, update_modified=False)


def _direct_insert_custom_field(dt, fieldname, label, fieldtype, options=None, insert_after=None, hidden=0, read_only=0, reqd=0, default=None):
    name = f"{dt}-{fieldname}"
    existing = frappe.db.exists("Custom Field", {"dt": dt, "fieldname": fieldname})
    if existing:
        cf = frappe.get_doc("Custom Field", existing)
        updates = {
            "label": label,
            "fieldtype": fieldtype,
            "options": options,
            "insert_after": insert_after,
            "hidden": hidden,
            "read_only": read_only,
            "reqd": reqd,
            "default": default,
        }
        for k, v in updates.items():
            if hasattr(cf, k):
                setattr(cf, k, v)
        try:
            cf.flags.ignore_validate = True
            cf.save(ignore_permissions=True)
        except Exception:
            frappe.db.sql(
                """
                UPDATE `tabCustom Field`
                SET label=%s, fieldtype=%s, options=%s, insert_after=%s,
                    hidden=%s, read_only=%s, reqd=%s, `default`=%s, modified=%s
                WHERE name=%s
                """,
                (label, fieldtype, options, insert_after, hidden, read_only, reqd, default, now(), existing),
            )
        return existing

    try:
        cf = frappe.get_doc({
            "doctype": "Custom Field",
            "dt": dt,
            "fieldname": fieldname,
            "label": label,
            "fieldtype": fieldtype,
            "options": options,
            "insert_after": insert_after,
            "hidden": hidden,
            "read_only": read_only,
            "reqd": reqd,
            "default": default,
        })
        cf.flags.ignore_validate = True
        cf.insert(ignore_permissions=True, ignore_mandatory=True)
        return cf.name
    except Exception as e:
        # Some Frappe versions reject non-custom_ fieldnames in Custom Field validation.
        # Direct SQL is intentional here because Healthcare's Patient controller expects fieldname "customer".
        frappe.db.sql(
            """
            INSERT INTO `tabCustom Field`
            (`name`, `creation`, `modified`, `modified_by`, `owner`, `docstatus`, `idx`,
             `dt`, `fieldname`, `label`, `fieldtype`, `options`, `insert_after`,
             `hidden`, `read_only`, `reqd`, `default`)
            VALUES
            (%s, %s, %s, %s, %s, 0, 0, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                name, now(), now(), "Administrator", "Administrator",
                dt, fieldname, label, fieldtype, options, insert_after,
                hidden, read_only, reqd, default,
            ),
        )
        return name


def _ensure_custom_field(dt, fieldname, label, fieldtype, options=None, insert_after=None, hidden=0, read_only=0, reqd=0, default=None):
    if frappe.db.exists("DocField", {"parent": dt, "fieldname": fieldname}):
        print(f"Standard DocField exists: {dt}.{fieldname}")
        return
    cf_name = _direct_insert_custom_field(dt, fieldname, label, fieldtype, options, insert_after, hidden, read_only, reqd, default)
    print(f"Ensured Custom Field: {cf_name} -> {dt}.{fieldname}")


def _property_setter(doc_type, property_name, value, property_type="Data", field_name=None):
    filters = {
        "doc_type": doc_type,
        "property": property_name,
        "field_name": field_name or "",
        "doctype_or_field": "DocField" if field_name else "DocType",
    }
    existing = frappe.db.exists("Property Setter", filters)
    if existing:
        ps = frappe.get_doc("Property Setter", existing)
        ps.value = value
        ps.property_type = property_type
        ps.save(ignore_permissions=True)
    else:
        ps = frappe.get_doc({
            "doctype": "Property Setter",
            "doc_type": doc_type,
            "doctype_or_field": "DocField" if field_name else "DocType",
            "field_name": field_name or None,
            "property": property_name,
            "property_type": property_type,
            "value": value,
        })
        ps.insert(ignore_permissions=True)
    print(f"Property Setter: {doc_type}.{field_name or '[DocType]'}.{property_name} = {value}")


def run():
    print("--- Checking Patient required meta fields ---")

    # Healthcare Patient controller uses self.customer in validate/on_update/load_dashboard_info.
    # If missing from meta, Patient save crashes with: AttributeError: 'Patient' object has no attribute 'customer'
    _ensure_custom_field(
        "Patient",
        "customer",
        "Linked Customer",
        "Link",
        options="Customer",
        insert_after="customer_group",
        hidden=1,
        read_only=1,
        reqd=0,
    )

    # Healthcare patient.js uses frm.fields_dict['age_html'].wrapper on onload.
    # If missing, form throws: Cannot read properties of undefined (reading 'wrapper')
    _ensure_custom_field(
        "Patient",
        "age_html",
        "Age",
        "HTML",
        insert_after="dob",
        hidden=0,
        read_only=0,
        reqd=0,
    )

    print("--- Setting Patient numbering to KPWS-#### ---")
    # Keep naming_series mode and force only KPWS-.#### option.
    _property_setter("Patient", "autoname", "naming_series:", "Data")
    _property_setter("Patient", "options", "KPWS-.####", "Small Text", field_name="naming_series")
    _property_setter("Patient", "default", "KPWS-.####", "Data", field_name="naming_series")
    _property_setter("Patient", "hidden", "1", "Check", field_name="naming_series")

    # Also update tabDocType/tabDocField directly so the change is immediate even before reload/sync.
    if frappe.db.exists("DocType", "Patient"):
        frappe.db.set_value("DocType", "Patient", "autoname", "naming_series:", update_modified=False)
    ns = frappe.db.exists("DocField", {"parent": "Patient", "fieldname": "naming_series"})
    if ns:
        frappe.db.set_value("DocField", ns, {
            "options": "KPWS-.####",
            "default": "KPWS-.####",
            "hidden": 1,
        }, update_modified=False)

    print("--- Making Patient Type label cleaner ---")
    cg = frappe.db.exists("DocField", {"parent": "Patient", "fieldname": "customer_group"})
    if cg:
        frappe.db.set_value("DocField", cg, "label", "Patient Type", update_modified=False)
        _property_setter("Patient", "label", "Patient Type", "Data", field_name="customer_group")

    print("--- Clearing cache and updating Patient table columns ---")
    frappe.clear_cache(doctype="Patient")
    frappe.clear_cache()
    try:
        frappe.db.updatedb("Patient")
    except Exception as e:
        print("WARNING: frappe.db.updatedb('Patient') failed:", e)

    frappe.db.commit()

    print("--- Verification ---")
    frappe.clear_cache(doctype="Patient")
    meta = frappe.get_meta("Patient")
    fields = {df.fieldname: df.fieldtype for df in meta.fields}
    print("Patient.customer exists:", "customer" in fields, fields.get("customer"))
    print("Patient.age_html exists:", "age_html" in fields, fields.get("age_html"))
    print("Patient autoname:", frappe.get_meta("Patient").autoname)
    ns_docfield = frappe.db.get_value("DocField", {"parent": "Patient", "fieldname": "naming_series"}, ["options", "default", "hidden"], as_dict=True)
    print("Naming series DocField:", ns_docfield)

