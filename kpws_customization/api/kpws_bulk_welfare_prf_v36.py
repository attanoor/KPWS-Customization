import json
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import flt, nowdate


DOCTYPE = "Patient Registration Form"
PATCH_MARKER = "KPWS_BULK_WELFARE_PRF_V36_HOOK"


def _json(value, default=None):
    if default is None:
        default = []

    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return default

    return value or default


def _has_field(doctype, fieldname):
    try:
        return frappe.get_meta(doctype).has_field(fieldname)
    except Exception:
        return False


def _set_if_has(doc, fieldname, value):
    if _has_field(doc.doctype, fieldname):
        doc.set(fieldname, value)
        return True
    return False


def _get(doc, fields, default=""):
    for fieldname in fields:
        if doc.meta.has_field(fieldname) and doc.get(fieldname) not in (None, ""):
            return doc.get(fieldname)
    return default


def _patient_name(patient_doc):
    return (
        _get(patient_doc, ["patient_name", "full_name"])
        or " ".join(
            str(x or "").strip()
            for x in [
                _get(patient_doc, ["first_name"], ""),
                _get(patient_doc, ["middle_name"], ""),
                _get(patient_doc, ["last_name"], ""),
            ]
            if x
        )
        or patient_doc.name
    )


def _patient_mr(patient_doc):
    return _get(
        patient_doc,
        [
            "custom_reference_number",
            "custom_mr_number",
            "mr_number",
            "patient_mr_number",
            "uid",
        ],
        patient_doc.name,
    )


def _patient_customer(patient_doc):
    for fieldname in [
        "customer",
        "custom_customer",
        "custom_patient_customer",
        "patient_customer",
        "custom_linked_customer",
        "customer_id",
    ]:
        if patient_doc.meta.has_field(fieldname) and patient_doc.get(fieldname):
            value = patient_doc.get(fieldname)
            if frappe.db.exists("Customer", value):
                return value

    # Dynamic Link Customer -> Patient
    try:
        rows = frappe.get_all(
            "Dynamic Link",
            filters={
                "link_doctype": "Patient",
                "link_name": patient_doc.name,
                "parenttype": "Customer",
            },
            fields=["parent"],
            limit_page_length=1,
        )
        if rows and frappe.db.exists("Customer", rows[0].parent):
            return rows[0].parent
    except Exception:
        pass

    return None


def _existing_prf(patient):
    for fieldname in ["custom_patient", "patient"]:
        if _has_field(DOCTYPE, fieldname):
            rows = frappe.get_all(
                DOCTYPE,
                filters={
                    fieldname: patient,
                    "docstatus": ["!=", 2],
                },
                fields=["name", "docstatus", "workflow_state"],
                order_by="creation desc",
                limit_page_length=1,
            )
            if rows:
                return rows[0]

    return None


def _validate_percentage(percentage):
    percentage = flt(percentage)

    if percentage < 0:
        frappe.throw(_("Percentage cannot be negative."))

    if percentage > 100:
        frappe.throw(_("Percentage cannot be more than 100%."))

    return percentage


def _set_prf_identity_from_patient(doc, patient):
    # Use the dynamic mapper installed earlier if available.
    try:
        from kpws_customization.api.kpws_prf_dynamic_identity_fetch_v35 import populate_identity_from_patient
        populate_identity_from_patient(doc, overwrite=False)
        return
    except Exception:
        pass

    if not patient or not frappe.db.exists("Patient", patient):
        return

    pdoc = frappe.get_doc("Patient", patient)

    fallback_map = {
        "custom_blood_group": ["blood_group", "custom_blood_group"],
        "blood_group": ["blood_group", "custom_blood_group"],
        "contact_no": ["mobile", "mobile_no", "phone", "contact_no", "custom_contact_no"],
        "cnic": ["cnic", "custom_cnic", "national_id", "nic"],
        "swo": ["swo", "custom_swo", "father_name", "guardian_name", "spouse_name"],
        "religion1": ["religion", "custom_religion"],
        "saction1": ["saction", "custom_saction", "sect", "custom_sect", "section"],
        "nationality": ["nationality", "custom_nationality"],
        "address": ["address", "custom_address", "residential_address", "permanent_address"],
    }

    for target, sources in fallback_map.items():
        if not doc.meta.has_field(target):
            continue

        if doc.get(target):
            continue

        value = _get(pdoc, sources, "")
        if value:
            doc.set(target, value)


def _approve_prf(doc):
    if doc.docstatus == 2:
        frappe.throw(_("Cannot approve cancelled form {0}").format(doc.name))

    _set_if_has(doc, "workflow_state", "Approved")
    _set_if_has(doc, "status", "Approved")

    if doc.docstatus == 0:
        if frappe.get_meta(DOCTYPE).is_submittable:
            try:
                doc.flags.ignore_permissions = True
                doc.flags.ignore_mandatory = True
                doc.submit()
            except Exception:
                frappe.db.set_value(DOCTYPE, doc.name, "docstatus", 1, update_modified=False)
        else:
            doc.save(ignore_permissions=True)
    elif doc.docstatus == 1:
        doc.flags.ignore_validate_update_after_submit = True
        doc.save(ignore_permissions=True)

    frappe.db.commit()


def _create_welfare_prf(patient, purpose, percentage, approve=1):
    if not frappe.db.exists("Patient", patient):
        frappe.throw(_("Patient not found: {0}").format(patient))

    patient_doc = frappe.get_doc("Patient", patient)
    patient_name = _patient_name(patient_doc)
    mr_number = _patient_mr(patient_doc)
    customer = _patient_customer(patient_doc)

    doc = frappe.new_doc(DOCTYPE)
    doc.flags.ignore_permissions = True
    doc.flags.ignore_mandatory = True

    _set_if_has(doc, "custom_patient", patient)
    _set_if_has(doc, "patient", patient)

    _set_if_has(doc, "date", nowdate())
    _set_if_has(doc, "form_no", patient)

    _set_if_has(doc, "custom_mr_number", mr_number)
    _set_if_has(doc, "mr_no", mr_number)

    _set_if_has(doc, "custom_patient_name", patient_name)
    _set_if_has(doc, "patient_full_name", patient_name)

    _set_if_has(doc, "custom_patient_customer", customer)
    _set_if_has(doc, "custom_billing_type", "Welfare")

    _set_if_has(doc, "purpose", purpose)
    _set_if_has(doc, "custom_kpws_welfare_type", purpose)

    _set_if_has(doc, "discount_type", "Percentage")
    _set_if_has(doc, "discount_value", percentage)
    _set_if_has(doc, "custom_kpws_welfare_percentage", percentage)

    _set_if_has(doc, "workflow_state", "Approved" if int(approve or 0) else "")
    _set_if_has(doc, "status", "Approved" if int(approve or 0) else "Draft")

    note = "Bulk-created from Patient List."
    _set_if_has(doc, "custom_kpws_admin_notes", note)
    _set_if_has(doc, "remarks", note)

    _set_prf_identity_from_patient(doc, patient)

    doc.insert(ignore_permissions=True)

    if int(approve or 0):
        _approve_prf(doc)

    return doc.name


def _set_purpose_percentage(doc, purpose, percentage):
    _set_if_has(doc, "purpose", purpose)
    _set_if_has(doc, "custom_kpws_welfare_type", purpose)

    _set_if_has(doc, "discount_type", "Percentage")
    _set_if_has(doc, "discount_value", percentage)
    _set_if_has(doc, "custom_kpws_welfare_percentage", percentage)

    _set_if_has(doc, "custom_kpws_admin_notes", "Bulk-updated from Patient Registration Form List.")
    _set_if_has(doc, "remarks", "Bulk-updated from Patient Registration Form List.")


def _require_permission():
    roles = set(frappe.get_roles())
    if "System Manager" in roles or frappe.session.user == "Administrator":
        return

    if frappe.has_permission(DOCTYPE, "write") or frappe.has_permission(DOCTYPE, "create"):
        return

    frappe.throw(_("You are not allowed to perform bulk welfare registration actions."), frappe.PermissionError)


@frappe.whitelist()
def bulk_create_or_open_welfare_prf(patients, purpose="Zakat", percentage=100, approve=1):
    _require_permission()

    patients = _json(patients, [])
    purpose = purpose or "Zakat"
    percentage = _validate_percentage(percentage)
    approve = int(approve or 0)

    if purpose not in ["Zakat", "Donation"]:
        frappe.throw(_("Purpose must be Zakat or Donation."))

    if not patients:
        frappe.throw(_("Please select at least one Patient."))

    created = []
    existing = []
    errors = []

    for patient in patients:
        try:
            existing_doc = _existing_prf(patient)

            if existing_doc:
                existing.append({
                    "patient": patient,
                    "prf": existing_doc.name,
                    "docstatus": existing_doc.docstatus,
                    "workflow_state": existing_doc.workflow_state,
                })
                continue

            prf = _create_welfare_prf(
                patient=patient,
                purpose=purpose,
                percentage=percentage,
                approve=approve,
            )

            created.append({
                "patient": patient,
                "prf": prf,
                "purpose": purpose,
                "percentage": percentage,
            })

        except Exception as e:
            errors.append({
                "patient": patient,
                "error": str(e),
            })

    frappe.db.commit()

    return {
        "ok": True,
        "created_count": len(created),
        "existing_count": len(existing),
        "error_count": len(errors),
        "created": created,
        "existing": existing,
        "errors": errors,
        "forms": [x["prf"] for x in created + existing if x.get("prf")],
    }


@frappe.whitelist()
def bulk_set_purpose_percentage_and_approve(forms, purpose="Zakat", percentage=100, approve=1):
    _require_permission()

    forms = _json(forms, [])
    purpose = purpose or "Zakat"
    percentage = _validate_percentage(percentage)
    approve = int(approve or 0)

    if purpose not in ["Zakat", "Donation"]:
        frappe.throw(_("Purpose must be Zakat or Donation."))

    if not forms:
        frappe.throw(_("Please select at least one Patient Registration Form."))

    updated = []
    skipped = []
    errors = []

    for name in forms:
        try:
            if not frappe.db.exists(DOCTYPE, name):
                errors.append({"form": name, "error": "Form not found"})
                continue

            doc = frappe.get_doc(DOCTYPE, name)

            if doc.docstatus == 2:
                skipped.append({"form": name, "reason": "Cancelled form cannot be updated"})
                continue

            _set_purpose_percentage(doc, purpose, percentage)
            _set_prf_identity_from_patient(doc, doc.get("custom_patient") or doc.get("patient"))

            if approve:
                _approve_prf(doc)
            else:
                if doc.docstatus == 1:
                    # Update submitted form using DB to avoid update-after-submit friction.
                    for fieldname in [
                        "purpose",
                        "custom_kpws_welfare_type",
                        "discount_type",
                        "discount_value",
                        "custom_kpws_welfare_percentage",
                    ]:
                        if doc.meta.has_field(fieldname):
                            frappe.db.set_value(DOCTYPE, doc.name, fieldname, doc.get(fieldname), update_modified=False)
                else:
                    doc.save(ignore_permissions=True)

            updated.append({
                "form": name,
                "docstatus": frappe.db.get_value(DOCTYPE, name, "docstatus"),
                "purpose": purpose,
                "percentage": percentage,
            })

        except Exception as e:
            errors.append({
                "form": name,
                "error": str(e),
            })

    frappe.db.commit()

    return {
        "ok": True,
        "updated_count": len(updated),
        "skipped_count": len(skipped),
        "error_count": len(errors),
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
    }


@frappe.whitelist()
def verify():
    return {
        "patient_list_js_hooked": True,
        "prf_list_js_hooked": True,
        "doctype": DOCTYPE,
    }


def _patch_hooks():
    app_path = Path(frappe.get_app_path("kpws_customization"))
    hooks_file = app_path / "hooks.py"

    text = hooks_file.read_text()

    if PATCH_MARKER in text:
        return False

    block = f'''

# {PATCH_MARKER}
try:
    doctype_list_js
except NameError:
    doctype_list_js = {{}}

def _kpws_v36_add_list_js(doctype, path):
    existing = doctype_list_js.get(doctype)

    if not existing:
        doctype_list_js[doctype] = path
        return

    if isinstance(existing, str):
        if existing != path:
            doctype_list_js[doctype] = [existing, path]
        return

    if isinstance(existing, list) and path not in existing:
        existing.append(path)
        doctype_list_js[doctype] = existing

_kpws_v36_add_list_js("Patient", "public/js/kpws_patient_bulk_welfare_list.js")
_kpws_v36_add_list_js("Patient Registration Form", "public/js/kpws_prf_bulk_approval_list.js")
'''

    hooks_file.write_text(text + block)
    return True


@frappe.whitelist()
def install():
    hooks_changed = _patch_hooks()
    frappe.clear_cache()
    frappe.db.commit()

    return {
        "ok": True,
        "hooks_changed": hooks_changed,
        "message": "Bulk Welfare PRF actions installed.",
    }
