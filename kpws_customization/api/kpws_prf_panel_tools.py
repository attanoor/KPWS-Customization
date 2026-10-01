import json
import frappe
from frappe import _
from frappe.utils import cint


ADMIN_ROLES = {"Administrator", "System Manager", "Healthcare Manager", "Welfare Manager"}


def _roles():
    try:
        return set(frappe.get_roles(frappe.session.user))
    except Exception:
        return set()


def _is_admin():
    return frappe.session.user == "Administrator" or bool(_roles().intersection(ADMIN_ROLES))


def _require_admin():
    if not _is_admin():
        frappe.throw(_("Only Administrator / Manager can perform this action."), frappe.PermissionError)


def _has_field(dt, fieldname):
    try:
        return bool(frappe.get_meta(dt).get_field(fieldname))
    except Exception:
        return False


def _get_default_customer_group():
    for name in ["Panel", "All Customer Groups", "Commercial"]:
        if frappe.db.exists("Customer Group", name):
            return name

    row = frappe.db.sql(
        """
        SELECT name
        FROM `tabCustomer Group`
        WHERE IFNULL(is_group, 0) = 0
        ORDER BY name
        LIMIT 1
        """,
        as_dict=True,
    )

    return row[0].name if row else None


def _get_default_territory():
    for name in ["Pakistan", "All Territories"]:
        if frappe.db.exists("Territory", name):
            return name

    row = frappe.db.sql(
        """
        SELECT name
        FROM `tabTerritory`
        WHERE IFNULL(is_group, 0) = 0
        ORDER BY name
        LIMIT 1
        """,
        as_dict=True,
    )

    return row[0].name if row else None


def _get_patient_from_prf(prf):
    for f in ["patient_name", "custom_patient"]:
        if prf.meta.get_field(f) and prf.get(f) and frappe.db.exists("Patient", prf.get(f)):
            return frappe.get_doc("Patient", prf.get(f))

    mr = prf.get("mr_no") if prf.meta.get_field("mr_no") else None

    if mr:
        for pf in ["custom_reference_number", "mr_no", "mr_number"]:
            if _has_field("Patient", pf):
                patient = frappe.db.get_value("Patient", {pf: mr}, "name")
                if patient:
                    return frappe.get_doc("Patient", patient)

    return None


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_panel_customers(doctype, txt, searchfield, start, page_len, filters):
    """
    Strict panel customer lookup:
    show only Customer where custom_is_panel = 1.
    """
    txt = txt or ""

    if not _has_field("Customer", "custom_is_panel"):
        return []

    return frappe.db.sql(
        """
        SELECT
            name,
            customer_name,
            customer_group
        FROM `tabCustomer`
        WHERE IFNULL(disabled, 0) = 0
          AND IFNULL(custom_is_panel, 0) = 1
          AND (
                name LIKE %(txt)s
             OR customer_name LIKE %(txt)s
             OR customer_group LIKE %(txt)s
          )
        ORDER BY customer_name ASC
        LIMIT %(start)s, %(page_len)s
        """,
        {
            "txt": "%" + txt + "%",
            "start": cint(start or 0),
            "page_len": cint(page_len or 20),
        },
    )


@frappe.whitelist()
def create_panel_customer(customer_name, mobile_no=None, email_id=None, territory=None, customer_group=None):
    _require_admin()

    customer_name = (customer_name or "").strip()

    if not customer_name:
        frappe.throw(_("Panel / Customer Name is required."))

    if frappe.db.exists("Customer", {"customer_name": customer_name}):
        customer = frappe.db.get_value("Customer", {"customer_name": customer_name}, "name")

        if _has_field("Customer", "custom_is_panel"):
            frappe.db.set_value("Customer", customer, "custom_is_panel", 1)

        frappe.db.commit()

        return {
            "customer": customer,
            "created": 0,
            "message": _("Existing Customer marked as Panel."),
        }

    customer_group = customer_group or _get_default_customer_group()
    territory = territory or _get_default_territory()

    if not customer_group:
        frappe.throw(_("No Customer Group found. Please create a Customer Group first."))

    if not territory:
        frappe.throw(_("No Territory found. Please create a Territory first."))

    doc = frappe.new_doc("Customer")
    doc.customer_name = customer_name
    doc.customer_group = customer_group
    doc.territory = territory

    if doc.meta.get_field("custom_is_panel"):
        doc.custom_is_panel = 1

    if mobile_no and doc.meta.get_field("mobile_no"):
        doc.mobile_no = mobile_no

    if email_id and doc.meta.get_field("email_id"):
        doc.email_id = email_id

    doc.insert(ignore_permissions=True)

    # Keep it strict even if the field was not available at insert time.
    if _has_field("Customer", "custom_is_panel"):
        frappe.db.set_value("Customer", doc.name, "custom_is_panel", 1)

    frappe.db.commit()

    return {
        "customer": doc.name,
        "created": 1,
        "message": _("Panel Customer created."),
    }


@frappe.whitelist()
def assign_panel_to_welfare_registration(prf_name, panel_customer):
    _require_admin()

    if not frappe.db.exists("Patient Registration Form", prf_name):
        frappe.throw(_("Patient Registration Form not found."))

    if not frappe.db.exists("Customer", panel_customer):
        frappe.throw(_("Selected panel customer does not exist."))

    if not _has_field("Customer", "custom_is_panel") or not cint(frappe.db.get_value("Customer", panel_customer, "custom_is_panel")):
        frappe.throw(_("Selected Customer is not marked as Is Panel."))

    prf = frappe.get_doc("Patient Registration Form", prf_name)

    updates = {}

    if prf.meta.get_field("custom_kpws_assigned_panel_customer"):
        updates["custom_kpws_assigned_panel_customer"] = panel_customer

    if prf.meta.get_field("custom_assigned_panel"):
        updates["custom_assigned_panel"] = panel_customer

    if prf.meta.get_field("custom_panel_customer"):
        updates["custom_panel_customer"] = panel_customer

    if prf.meta.get_field("custom_panel"):
        updates["custom_panel"] = panel_customer

    if updates:
        frappe.db.set_value("Patient Registration Form", prf.name, updates, update_modified=True)

    patient = _get_patient_from_prf(prf)

    if patient:
        patient_updates = {}

        if patient.meta.get_field("panel_name"):
            patient_updates["panel_name"] = panel_customer

        if patient.meta.get_field("custom_panel_customer"):
            patient_updates["custom_panel_customer"] = panel_customer

        # Patient remains Welfare unless user changes billing type from Patient form.
        if patient.meta.get_field("custom_patient_billing_type") and patient.get("custom_patient_billing_type") != "Welfare":
            patient_updates["custom_patient_billing_type"] = "Welfare"

        if patient.meta.get_field("customer_group") and patient.get("customer_group") != "Welfare":
            patient_updates["customer_group"] = "Welfare"

        if patient_updates:
            frappe.db.set_value("Patient", patient.name, patient_updates, update_modified=True)

    frappe.db.commit()

    return {
        "prf": prf_name,
        "panel_customer": panel_customer,
        "patient": patient.name if patient else None,
    }


def _ensure_custom_field(dt, fieldname, label, fieldtype, insert_after=None, options=None, **props):
    rows = frappe.get_all(
        "Custom Field",
        filters={"dt": dt, "fieldname": fieldname},
        fields=["name"],
        order_by="creation asc",
        limit_page_length=50,
    )

    if rows:
        cf = frappe.get_doc("Custom Field", rows[0].name)
    else:
        cf = frappe.new_doc("Custom Field")
        cf.dt = dt
        cf.fieldname = fieldname

    cf.label = label
    cf.fieldtype = fieldtype

    if insert_after:
        cf.insert_after = insert_after

    if options is not None:
        cf.options = options

    for k, v in props.items():
        if hasattr(cf, k):
            setattr(cf, k, v)

    if cf.is_new():
        cf.insert(ignore_permissions=True)
    else:
        cf.save(ignore_permissions=True)

    return cf.name


def _set_field_property(dt, fieldname, prop, value, property_type="Data"):
    rows = frappe.get_all(
        "Custom Field",
        filters={"dt": dt, "fieldname": fieldname},
        fields=["name"],
        limit_page_length=50,
    )

    if rows:
        for r in rows:
            cf = frappe.get_doc("Custom Field", r.name)
            if hasattr(cf, prop):
                setattr(cf, prop, value)
                cf.save(ignore_permissions=True)
        return

    if not frappe.get_meta(dt).get_field(fieldname):
        return

    ps_name = frappe.db.exists(
        "Property Setter",
        {"doc_type": dt, "field_name": fieldname, "property": prop},
    )

    if ps_name:
        ps = frappe.get_doc("Property Setter", ps_name)
    else:
        ps = frappe.new_doc("Property Setter")
        ps.doctype_or_field = "DocField"
        ps.doc_type = dt
        ps.field_name = fieldname
        ps.property = prop

    ps.doctype_or_field = "DocField"
    ps.doc_type = dt
    ps.field_name = fieldname
    ps.property = prop
    ps.property_type = property_type
    ps.value = str(value)

    if ps.is_new():
        ps.insert(ignore_permissions=True)
    else:
        ps.save(ignore_permissions=True)


def apply_metadata():
    print("Applying PRF panel assignment metadata...")

    _ensure_custom_field(
        "Customer",
        "custom_is_panel",
        "Is Panel",
        "Check",
        insert_after="customer_group",
        hidden=0,
        read_only=0,
    )

    _ensure_custom_field(
        "Patient Registration Form",
        "custom_kpws_assigned_panel_customer",
        "Assigned Panel Customer",
        "Link",
        insert_after="patient_full_name",
        options="Customer",
        hidden=0,
        read_only=0,
    )

    _ensure_custom_field(
        "Patient Registration Form",
        "custom_kpws_panel_actions_html",
        "Panel Assignment",
        "HTML",
        insert_after="custom_kpws_assigned_panel_customer",
        hidden=0,
        read_only=1,
    )

    # Keep duplicate/old panel fields hidden.
    for fieldname in [
        "custom_assigned_panel",
        "custom_panel_customer",
        "custom_panel",
        "custom_kpws_panel_assignment_tab",
    ]:
        _set_field_property("Patient Registration Form", fieldname, "hidden", 1, "Check")
        _set_field_property("Patient Registration Form", fieldname, "reqd", 0, "Check")
        _set_field_property("Patient Registration Form", fieldname, "read_only", 1, "Check")

    _set_field_property("Patient Registration Form", "custom_kpws_assigned_panel_customer", "hidden", 0, "Check")
    _set_field_property("Patient Registration Form", "custom_kpws_assigned_panel_customer", "read_only", 0, "Check")
    _set_field_property("Patient Registration Form", "custom_kpws_assigned_panel_customer", "label", "Assigned Panel Customer", "Data")

    frappe.db.commit()

    for dt in ["Patient Registration Form", "Customer", "Patient"]:
        try:
            frappe.db.updatedb(dt)
        except Exception as e:
            print("updatedb warning:", dt, e)
        frappe.clear_cache(doctype=dt)

    frappe.clear_cache()

    print("PRF panel assignment metadata applied.")
    return "OK"
