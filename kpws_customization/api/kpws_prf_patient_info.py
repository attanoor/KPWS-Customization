import json
import frappe
from frappe import _
from frappe.utils import nowdate, cint, flt


ADMIN_ROLES = {"Administrator", "System Manager", "Healthcare Manager", "Welfare Manager"}


def _has_field(dt, fieldname):
    try:
        return bool(frappe.get_meta(dt).get_field(fieldname))
    except Exception:
        return False


def _get_roles():
    try:
        return set(frappe.get_roles(frappe.session.user))
    except Exception:
        return set()


def _is_admin():
    return frappe.session.user == "Administrator" or bool(_get_roles().intersection(ADMIN_ROLES))


def _require_admin():
    if not _is_admin():
        frappe.throw(_("Only Administrator / Manager can update this information."), frappe.PermissionError)


def _get_doc_if_exists(dt, name):
    if name and frappe.db.exists(dt, name):
        return frappe.get_doc(dt, name)
    return None


def _get_patient_doc(patient=None, prf_name=None):
    if patient and frappe.db.exists("Patient", patient):
        return frappe.get_doc("Patient", patient)

    if prf_name and frappe.db.exists("Patient Registration Form", prf_name):
        prf = frappe.get_doc("Patient Registration Form", prf_name)

        for f in ["patient_name", "custom_patient"]:
            if prf.meta.get_field(f) and prf.get(f) and frappe.db.exists("Patient", prf.get(f)):
                return frappe.get_doc("Patient", prf.get(f))

        mr = prf.get("mr_no") if prf.meta.get_field("mr_no") else None
        if mr:
            for pf in ["custom_reference_number", "mr_no", "mr_number"]:
                if _has_field("Patient", pf):
                    found = frappe.db.get_value("Patient", {pf: mr}, "name")
                    if found:
                        return frappe.get_doc("Patient", found)

    return None


def _first(doc, fields):
    for f in fields:
        if doc and doc.meta.get_field(f) and doc.get(f):
            return doc.get(f)
    return None


def _patient_mr(patient_doc):
    return _first(patient_doc, ["custom_reference_number", "mr_no", "mr_number", "ref_no", "old_kpws_number"]) or patient_doc.name


def _patient_cnic(patient_doc):
    return _first(patient_doc, ["cnic", "custom_cnic", "uid", "national_id", "cnic_number"])


def _patient_address(patient_doc):
    return _first(patient_doc, ["address", "patient_details", "custom_address"])


def _patient_mobile(patient_doc):
    return _first(patient_doc, ["mobile", "mobile_no", "phone", "contact_no"])


def _patient_panel(patient_doc):
    return _first(patient_doc, ["panel_name", "custom_panel_customer"])


def _patient_billing_type(patient_doc):
    return _first(patient_doc, ["custom_patient_billing_type", "customer_group"]) or "Cash"


def _get_prf(prf_name):
    if prf_name and frappe.db.exists("Patient Registration Form", prf_name):
        return frappe.get_doc("Patient Registration Form", prf_name)
    return None


def _prf_value(prf, fieldname):
    if prf and prf.meta.get_field(fieldname):
        return prf.get(fieldname)
    return None


@frappe.whitelist()
def get_patient_snapshot(prf_name=None, patient=None):
    prf = _get_prf(prf_name)
    patient_doc = _get_patient_doc(patient=patient, prf_name=prf_name)

    if not patient_doc:
        return {"found": 0}

    data = {
        "found": 1,
        "patient": patient_doc.name,
        "patient_name": patient_doc.get("patient_name"),
        "mr_no": _patient_mr(patient_doc),
        "customer": patient_doc.get("customer") if patient_doc.meta.get_field("customer") else None,
        "billing_type": _patient_billing_type(patient_doc),
        "panel_customer": _patient_panel(patient_doc),
        "sex": _first(patient_doc, ["sex", "gender"]),
        "dob": _first(patient_doc, ["dob", "date_of_birth"]),
        "blood_group": _first(patient_doc, ["blood_group"]),
        "mobile": _patient_mobile(patient_doc),
        "phone": _first(patient_doc, ["phone", "landline"]),
        "email": _first(patient_doc, ["email", "email_id"]),
        "cnic": _patient_cnic(patient_doc),
        "address": _patient_address(patient_doc),
        "religion1": _first(patient_doc, ["religion1", "religion"]) or _prf_value(prf, "religion1"),
        "saction1": _first(patient_doc, ["saction1", "section", "sect"]) or _prf_value(prf, "saction1"),
        "nationality": _first(patient_doc, ["nationality"]) or _prf_value(prf, "nationality"),
        "swo": _first(patient_doc, ["swo", "father_name", "guardian_name"]) or _prf_value(prf, "swo"),
    }

    return data


def _set_doc_value_if_has(doc, fieldname, value):
    if doc and doc.meta.get_field(fieldname):
        doc.set(fieldname, value)
        return True
    return False


def _set_first_available(doc, possible_fields, value):
    for f in possible_fields:
        if doc.meta.get_field(f):
            doc.set(f, value)
            return f
    return None


def _clean_phone(value):
    if not value:
        return value

    value = str(value).strip()

    if not value:
        return ""

    # Keep ERPNext/Frappe core validation intact.
    # We only give a clear error before save.
    cleaned = value.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
    if cleaned and not cleaned.isdigit():
        frappe.throw(_("{0} is not a valid phone number. Please enter a valid phone number or leave it blank.").format(value))

    return value


@frappe.whitelist()
def update_patient_from_prf(prf_name, values):
    _require_admin()

    if isinstance(values, str):
        values = json.loads(values or "{}")

    prf = _get_prf(prf_name)
    if not prf:
        frappe.throw(_("Patient Registration Form not found."))

    patient_doc = _get_patient_doc(prf_name=prf_name)
    if not patient_doc:
        frappe.throw(_("Linked Patient not found."))

    allowed = {
        "patient_name",
        "mr_no",
        "sex",
        "dob",
        "blood_group",
        "mobile",
        "phone",
        "email",
        "cnic",
        "address",
        "religion1",
        "saction1",
        "nationality",
        "swo",
    }

    data = {k: v for k, v in values.items() if k in allowed}

    if "mobile" in data:
        data["mobile"] = _clean_phone(data.get("mobile"))

    if "phone" in data:
        data["phone"] = _clean_phone(data.get("phone"))

    # Update Patient core/available fields without bypassing validation.
    if "patient_name" in data:
        _set_doc_value_if_has(patient_doc, "patient_name", data["patient_name"])

    if "mr_no" in data:
        _set_first_available(patient_doc, ["custom_reference_number", "mr_no", "mr_number"], data["mr_no"])

    if "sex" in data:
        _set_first_available(patient_doc, ["sex", "gender"], data["sex"])

    if "dob" in data:
        _set_first_available(patient_doc, ["dob", "date_of_birth"], data["dob"])

    if "blood_group" in data:
        _set_doc_value_if_has(patient_doc, "blood_group", data["blood_group"])

    if "mobile" in data:
        _set_first_available(patient_doc, ["mobile", "mobile_no", "phone", "contact_no"], data["mobile"])

    if "phone" in data:
        _set_first_available(patient_doc, ["phone", "landline"], data["phone"])

    if "email" in data:
        _set_first_available(patient_doc, ["email", "email_id"], data["email"])

    if "cnic" in data:
        _set_first_available(patient_doc, ["cnic", "custom_cnic", "uid", "national_id", "cnic_number"], data["cnic"])

    if "address" in data:
        _set_first_available(patient_doc, ["address", "patient_details", "custom_address"], data["address"])

    for f in ["religion1", "saction1", "nationality", "swo"]:
        if f in data:
            _set_doc_value_if_has(patient_doc, f, data[f])

    patient_doc.save(ignore_permissions=True)

    # Update PRF display/contact fields without triggering approval mandatory checks.
    prf_updates = {}

    mapping = {
        "patient_name": "patient_full_name",
        "mr_no": "mr_no",
        "cnic": "cnic",
        "mobile": "contact_no",
        "address": "address",
        "religion1": "religion1",
        "saction1": "saction1",
        "nationality": "nationality",
        "swo": "swo",
    }

    for source, target in mapping.items():
        if source in data and prf.meta.get_field(target):
            prf_updates[target] = data[source]

    if prf_updates:
        frappe.db.set_value("Patient Registration Form", prf.name, prf_updates, update_modified=True)

    frappe.db.commit()

    return get_patient_snapshot(prf_name=prf.name)


@frappe.whitelist()
def refresh_prf_from_patient(prf_name):
    prf = _get_prf(prf_name)
    if not prf:
        frappe.throw(_("Patient Registration Form not found."))

    patient_doc = _get_patient_doc(prf_name=prf_name)
    if not patient_doc:
        frappe.throw(_("Linked Patient not found."))

    updates = {}

    if prf.meta.get_field("patient_name"):
        updates["patient_name"] = patient_doc.name

    if prf.meta.get_field("mr_no"):
        updates["mr_no"] = _patient_mr(patient_doc)

    if prf.meta.get_field("patient_full_name"):
        updates["patient_full_name"] = patient_doc.get("patient_name")

    if prf.meta.get_field("cnic"):
        updates["cnic"] = _patient_cnic(patient_doc)

    if prf.meta.get_field("contact_no"):
        updates["contact_no"] = _patient_mobile(patient_doc)

    if prf.meta.get_field("address"):
        updates["address"] = _patient_address(patient_doc)

    for f in ["religion1", "saction1", "nationality", "swo"]:
        if prf.meta.get_field(f) and patient_doc.meta.get_field(f):
            updates[f] = patient_doc.get(f)

    if prf.meta.get_field("custom_patient"):
        updates["custom_patient"] = patient_doc.name

    if prf.meta.get_field("custom_patient_customer") and patient_doc.meta.get_field("customer"):
        updates["custom_patient_customer"] = patient_doc.get("customer")

    if prf.meta.get_field("custom_mr_number"):
        updates["custom_mr_number"] = _patient_mr(patient_doc)

    if updates:
        frappe.db.set_value("Patient Registration Form", prf.name, updates, update_modified=True)

    frappe.db.commit()

    return get_patient_snapshot(prf_name=prf.name)


def _set_field_property(dt, fieldname, prop, value, property_type="Data"):
    rows = frappe.get_all(
        "Custom Field",
        filters={"dt": dt, "fieldname": fieldname},
        fields=["name"],
        limit_page_length=100,
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


def _ensure_html_field():
    rows = frappe.get_all(
        "Custom Field",
        filters={"dt": "Patient Registration Form", "fieldname": "custom_kpws_patient_snapshot_html"},
        fields=["name"],
        limit_page_length=10,
    )

    if rows:
        cf = frappe.get_doc("Custom Field", rows[0].name)
    else:
        cf = frappe.new_doc("Custom Field")
        cf.dt = "Patient Registration Form"
        cf.fieldname = "custom_kpws_patient_snapshot_html"

    cf.label = "Patient Information"
    cf.fieldtype = "HTML"
    cf.insert_after = "patient_full_name"
    cf.hidden = 0
    cf.read_only = 1

    if cf.is_new():
        cf.insert(ignore_permissions=True)
    else:
        cf.save(ignore_permissions=True)


def apply_metadata():
    print("Applying PRF patient information UI metadata...")

    _ensure_html_field()

    # Old duplicate custom fields hidden.
    for fieldname in [
        "custom_assistance_type",
        "custom_approval_remarks",
        "custom_coverage_percentage",
        "custom_review_status",
        "actual_patient_name",
        "custom_patient",
        "custom_mr_number",
        "custom_patient_customer",
        "custom_billing_type",
        "custom_panel",
        "custom_assigned_panel",
        "custom_panel_customer",
        "custom_patient_section",
        "custom_auto_filled_patient_details",
        "custom_kpws_panel_assignment_tab",
    ]:
        _set_field_property("Patient Registration Form", fieldname, "hidden", 1, "Check")
        _set_field_property("Patient Registration Form", fieldname, "reqd", 0, "Check")
        _set_field_property("Patient Registration Form", fieldname, "read_only", 1, "Check")

    # Auto-filled fields shown/read-only.
    for fieldname in ["patient_name", "mr_no", "patient_full_name"]:
        if _has_field("Patient Registration Form", fieldname):
            _set_field_property("Patient Registration Form", fieldname, "hidden", 0, "Check")
            _set_field_property("Patient Registration Form", fieldname, "read_only", 1, "Check")

    # Approval fields are not required at initial creation.
    for fieldname in ["purpose", "discount_type", "discount_value"]:
        if _has_field("Patient Registration Form", fieldname):
            _set_field_property("Patient Registration Form", fieldname, "reqd", 0, "Check")
            _set_field_property("Patient Registration Form", fieldname, "hidden", 0, "Check")
            _set_field_property("Patient Registration Form", fieldname, "read_only", 0, "Check")

    frappe.db.commit()
    frappe.clear_cache(doctype="Patient Registration Form")
    frappe.clear_cache(doctype="Patient")
    frappe.clear_cache()

    print("PRF patient information UI metadata applied.")
    return "OK"
