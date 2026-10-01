import frappe
from frappe import _


def _as_str(value):
    if value is None:
        return ""
    return str(value)


def _get_custom_fields(dt, fieldname):
    return frappe.get_all(
        "Custom Field",
        filters={"dt": dt, "fieldname": fieldname},
        fields=["name"],
        order_by="creation asc",
        limit_page_length=100,
    )


def ensure_custom_field(dt, fieldname, label, fieldtype, insert_after=None, options=None, **kwargs):
    """
    Create/update Custom Field safely.
    If duplicate Custom Fields already exist with same fieldname, update all of them
    so the form behaves consistently.
    """
    existing = _get_custom_fields(dt, fieldname)

    if existing:
        names = [x.name for x in existing]
    else:
        doc = frappe.new_doc("Custom Field")
        doc.dt = dt
        doc.fieldname = fieldname
        doc.label = label
        doc.fieldtype = fieldtype

        if insert_after:
            doc.insert_after = insert_after

        if options is not None:
            doc.options = options

        for k, v in kwargs.items():
            if hasattr(doc, k):
                setattr(doc, k, v)

        doc.insert(ignore_permissions=True)
        names = [doc.name]

    for name in names:
        cf = frappe.get_doc("Custom Field", name)
        cf.label = label
        cf.fieldtype = fieldtype

        if insert_after:
            cf.insert_after = insert_after

        if options is not None:
            cf.options = options

        for k, v in kwargs.items():
            if hasattr(cf, k):
                setattr(cf, k, v)

        cf.save(ignore_permissions=True)

    return names[0]


def ensure_property_setter(dt, fieldname, prop, value, property_type="Data"):
    """
    Frappe v14 requires doctype_or_field.
    Use Property Setter only for standard DocFields.
    """
    ps_name = frappe.db.exists(
        "Property Setter",
        {
            "doc_type": dt,
            "field_name": fieldname,
            "property": prop,
        },
    )

    if ps_name:
        ps = frappe.get_doc("Property Setter", ps_name)
    else:
        ps = frappe.new_doc("Property Setter")
        ps.doctype_or_field = "DocField" if fieldname else "DocType"
        ps.doc_type = dt
        ps.field_name = fieldname
        ps.property = prop

    ps.doctype_or_field = "DocField" if fieldname else "DocType"
    ps.doc_type = dt
    ps.field_name = fieldname
    ps.property = prop
    ps.value = _as_str(value)
    ps.property_type = property_type

    if ps.is_new():
        ps.insert(ignore_permissions=True)
    else:
        ps.save(ignore_permissions=True)

    return ps.name


def set_field_property(dt, fieldname, prop, value, property_type="Data"):
    """
    Prefer changing Custom Field directly.
    Use Property Setter only if the field is a standard DocField.
    """
    custom_fields = _get_custom_fields(dt, fieldname)

    if custom_fields:
        for row in custom_fields:
            cf = frappe.get_doc("Custom Field", row.name)
            if hasattr(cf, prop):
                setattr(cf, prop, value)
                cf.save(ignore_permissions=True)
        return

    if frappe.get_meta(dt).get_field(fieldname):
        ensure_property_setter(dt, fieldname, prop, value, property_type)


def disable_client_script(name):
    if frappe.db.exists("Client Script", name):
        frappe.db.set_value("Client Script", name, "enabled", 0)
        print("Disabled Client Script:", name)


def apply():
    print("Applying KPWS Step 1 metadata fix...")

    # -----------------------------
    # Patient fields
    # -----------------------------
    ensure_custom_field(
        "Patient",
        "custom_patient_billing_type",
        "Patient Billing Type",
        "Select",
        insert_after="customer",
        options="\nCash\nWelfare\nPanel",
        reqd=1,
        hidden=0,
        read_only=0,
    )

    ensure_custom_field(
        "Patient",
        "custom_panel_customer",
        "Panel Customer",
        "Link",
        insert_after="custom_patient_billing_type",
        options="Customer",
        reqd=0,
        hidden=1,
        read_only=1,
        depends_on="eval:doc.custom_patient_billing_type=='Panel'",
    )

    ensure_custom_field(
        "Patient",
        "custom_latest_welfare_registration",
        "Latest Welfare Registration",
        "Link",
        insert_after="custom_panel_customer",
        options="Patient Registration Form",
        hidden=0,
        read_only=1,
        depends_on="eval:doc.custom_patient_billing_type=='Welfare'",
    )

    ensure_custom_field(
        "Patient",
        "custom_welfare_type",
        "Welfare Type",
        "Select",
        insert_after="custom_latest_welfare_registration",
        options="\nZakat\nDonation",
        hidden=0,
        read_only=1,
        depends_on="eval:doc.custom_patient_billing_type=='Welfare'",
    )

    ensure_custom_field(
        "Patient",
        "custom_welfare_percentage",
        "Welfare Percentage",
        "Percent",
        insert_after="custom_welfare_type",
        hidden=0,
        read_only=1,
        depends_on="eval:doc.custom_patient_billing_type=='Welfare'",
    )

    # Old Patient field: Panel Group / customer_group
    # Keep it internally for compatibility, but hide it from users.
    if frappe.get_meta("Patient").get_field("customer_group"):
        set_field_property("Patient", "customer_group", "hidden", 1, "Check")
        set_field_property("Patient", "customer_group", "reqd", 0, "Check")
        set_field_property("Patient", "customer_group", "read_only", 1, "Check")

    # Panel Name should only show when billing type = Panel.
    if frappe.get_meta("Patient").get_field("panel_name"):
        set_field_property("Patient", "panel_name", "hidden", 0, "Check")
        set_field_property(
            "Patient",
            "panel_name",
            "depends_on",
            "eval:doc.custom_patient_billing_type=='Panel'",
            "Data",
        )
        set_field_property(
            "Patient",
            "panel_name",
            "mandatory_depends_on",
            "eval:doc.custom_patient_billing_type=='Panel'",
            "Data",
        )

    # -----------------------------
    # Patient Registration Form / Welfare Registration
    # -----------------------------
    ensure_custom_field(
        "Patient Registration Form",
        "custom_kpws_panel_assignment_tab",
        "Panel Assignment",
        "Tab Break",
        insert_after="contact_no",
        hidden=0,
        read_only=0,
    )

    ensure_custom_field(
        "Patient Registration Form",
        "custom_kpws_assigned_panel_customer",
        "Assigned Panel Customer",
        "Link",
        insert_after="custom_kpws_panel_assignment_tab",
        options="Customer",
        hidden=0,
        read_only=0,
    )

    ensure_custom_field(
        "Patient Registration Form",
        "custom_kpws_admin_notes",
        "Additional Information / Administrator Notes",
        "Small Text",
        insert_after="purpose",
        hidden=0,
        read_only=0,
    )

    # These should auto-fill from Patient, not be manually typed by Reception.
    for fieldname in ["mr_no", "patient_full_name"]:
        if frappe.get_meta("Patient Registration Form").get_field(fieldname):
            set_field_property("Patient Registration Form", fieldname, "read_only", 1, "Check")

    # Disable old conflicting Client Scripts.
    for script_name in [
        "KPWS - Patient Quick Add Panel",
        "KPWS - Patient Panel Name Customer Filter",
        "KPWS - Patient Panel Group Restriction",
        "KPWS - Force Hide Panel Fields on PRF",
        "KPWS - Patient Registration Panel Filter",
        "KPWS - Show Assigned Panel on PRF",
    ]:
        disable_client_script(script_name)

    frappe.db.commit()

    for dt in ["Patient", "Patient Registration Form", "Customer"]:
        frappe.clear_cache(doctype=dt)

    frappe.clear_cache()

    print("KPWS Step 1 metadata fix completed successfully.")

    return "OK"
