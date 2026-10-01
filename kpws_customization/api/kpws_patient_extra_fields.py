import frappe
from frappe import _


PATIENT_FIELD_CANDIDATES = {
    "religion": ["custom_religion"],
    "sanction": ["custom_sanction"],
    "nationality": ["custom_nationality"],
}

PRF_FIELD_CANDIDATES = {
    "religion": ["custom_religion", "religion1", "religion"],
    "sanction": ["custom_sanction", "sanction", "saction1", "custom_saction", "custom_sect", "section"],
    "nationality": ["custom_nationality", "nationality"],
}


def _db_column_exists(doctype, fieldname):
    if not doctype or not fieldname:
        return False

    try:
        return bool(
            frappe.db.sql(
                """
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = %s
                  AND COLUMN_NAME = %s
                LIMIT 1
                """,
                ("tab" + doctype, fieldname),
            )
        )
    except Exception:
        return False


def _meta_has_field(doctype, fieldname):
    try:
        return bool(frappe.get_meta(doctype).has_field(fieldname))
    except Exception:
        return False


def _field_ready(doctype, fieldname):
    return _meta_has_field(doctype, fieldname) and _db_column_exists(doctype, fieldname)


def _pick_field(doctype, candidates):
    for fieldname in candidates:
        if _field_ready(doctype, fieldname):
            return fieldname
    return None


def _get_value_safe(doctype, name, fieldname):
    if not doctype or not name or not fieldname:
        return ""

    if not frappe.db.exists(doctype, name):
        return ""

    if not _field_ready(doctype, fieldname):
        return ""

    try:
        return frappe.db.get_value(doctype, name, fieldname) or ""
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"KPWS get value failed: {doctype}.{fieldname}")
        return ""


def _set_value_safe(doctype, name, fieldname, value):
    if not doctype or not name or not fieldname:
        return False

    if not frappe.db.exists(doctype, name):
        return False

    if not _field_ready(doctype, fieldname):
        return False

    try:
        doc = frappe.get_doc(doctype, name)
        doc.set(fieldname, value or "")
        doc.save(ignore_permissions=True)
        return True
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"KPWS set value failed: {doctype}.{fieldname}")
        return False


def _find_latest_prf_for_patient(patient):
    if not patient:
        return None

    candidate_fields = ["patient", "custom_patient", "custom_kpws_source_patient", "mr_no"]

    for fieldname in candidate_fields:
        if not _field_ready("Patient Registration Form", fieldname):
            continue

        prf = frappe.db.get_value(
            "Patient Registration Form",
            {fieldname: patient},
            "name",
            order_by="modified desc",
        )

        if prf:
            return prf

    # fallback by MR number / custom reference number
    ref = frappe.db.get_value("Patient", patient, "custom_reference_number") if frappe.db.exists("Patient", patient) else None
    if ref and _field_ready("Patient Registration Form", "mr_no"):
        prf = frappe.db.get_value(
            "Patient Registration Form",
            {"mr_no": ref},
            "name",
            order_by="modified desc",
        )
        if prf:
            return prf

    return None


def _find_patient_for_prf(patient_registration_form):
    if not patient_registration_form:
        return None

    if not frappe.db.exists("Patient Registration Form", patient_registration_form):
        return None

    candidate_fields = ["patient", "custom_patient", "custom_kpws_source_patient"]

    for fieldname in candidate_fields:
        if not _field_ready("Patient Registration Form", fieldname):
            continue

        patient = frappe.db.get_value("Patient Registration Form", patient_registration_form, fieldname)

        if patient and frappe.db.exists("Patient", patient):
            return patient

    return None


def _field_map():
    return {
        "Patient": {
            key: _pick_field("Patient", candidates)
            for key, candidates in PATIENT_FIELD_CANDIDATES.items()
        },
        "Patient Registration Form": {
            key: _pick_field("Patient Registration Form", candidates)
            for key, candidates in PRF_FIELD_CANDIDATES.items()
        },
    }


@frappe.whitelist()
def debug_field_status():
    fmap = _field_map()

    return {
        "field_map": fmap,
        "Patient": {
            key: {
                "selected": fmap["Patient"].get(key),
                "candidates": PATIENT_FIELD_CANDIDATES.get(key),
            }
            for key in PATIENT_FIELD_CANDIDATES
        },
        "Patient Registration Form": {
            key: {
                "selected": fmap["Patient Registration Form"].get(key),
                "candidates": PRF_FIELD_CANDIDATES.get(key),
            }
            for key in PRF_FIELD_CANDIDATES
        },
    }


@frappe.whitelist()
def get_extra_fields(patient=None, patient_registration_form=None):
    if patient_registration_form and not patient:
        patient = _find_patient_for_prf(patient_registration_form)

    if patient and not patient_registration_form:
        patient_registration_form = _find_latest_prf_for_patient(patient)

    fmap = _field_map()

    data = {
        "patient": patient or "",
        "patient_registration_form": patient_registration_form or "",
        "religion": "",
        "sanction": "",
        "nationality": "",
        "field_map": fmap,
    }

    for key in ["religion", "sanction", "nationality"]:
        prf_field = fmap["Patient Registration Form"].get(key)
        patient_field = fmap["Patient"].get(key)

        prf_value = _get_value_safe("Patient Registration Form", patient_registration_form, prf_field)
        patient_value = _get_value_safe("Patient", patient, patient_field)

        data[key] = prf_value or patient_value or ""

    return data


@frappe.whitelist()
def save_extra_fields(patient=None, patient_registration_form=None, religion=None, sanction=None, nationality=None):
    allowed_roles = {
        "System Manager",
        "Administrator",
        "KPWS Reception User",
        "KPWS Welfare Officer",
    }

    if not allowed_roles.intersection(set(frappe.get_roles())):
        frappe.throw(_("Not permitted."))

    if patient_registration_form and not patient:
        patient = _find_patient_for_prf(patient_registration_form)

    if patient and not patient_registration_form:
        patient_registration_form = _find_latest_prf_for_patient(patient)

    if not patient and not patient_registration_form:
        return {
            "ok": False,
            "message": "Patient or Patient Registration Form is required.",
        }

    fmap = _field_map()

    values = {
        "religion": religion,
        "sanction": sanction,
        "nationality": nationality,
    }

    updated = []

    if patient and frappe.db.exists("Patient", patient):
        changed = False
        for key, value in values.items():
            changed = _set_value_safe("Patient", patient, fmap["Patient"].get(key), value) or changed
        if changed:
            updated.append("Patient")

    if patient_registration_form and frappe.db.exists("Patient Registration Form", patient_registration_form):
        changed = False
        for key, value in values.items():
            changed = _set_value_safe(
                "Patient Registration Form",
                patient_registration_form,
                fmap["Patient Registration Form"].get(key),
                value,
            ) or changed
        if changed:
            updated.append("Patient Registration Form")

    frappe.db.commit()

    return {
        "ok": True,
        "patient": patient or "",
        "patient_registration_form": patient_registration_form or "",
        "updated": updated,
        "values": values,
        "field_map": fmap,
    }


def sync_extra_fields_from_patient_to_prf(patient=None, patient_registration_form=None):
    """
    Called from Patient Intake / Welfare Registration creation flow.
    Copies Religion, Sanction/Saction, Nationality from Patient to Patient Registration Form.
    Safe to call repeatedly.
    """

    if not patient or not patient_registration_form:
        return {
            "ok": False,
            "reason": "patient and patient_registration_form required",
        }

    if not frappe.db.exists("Patient", patient):
        return {
            "ok": False,
            "reason": "patient not found",
        }

    if not frappe.db.exists("Patient Registration Form", patient_registration_form):
        return {
            "ok": False,
            "reason": "patient registration form not found",
        }

    fmap = _field_map()

    values = {}

    for key in ["religion", "sanction", "nationality"]:
        patient_field = fmap.get("Patient", {}).get(key)
        prf_field = fmap.get("Patient Registration Form", {}).get(key)

        if patient_field and prf_field:
            value = _get_value_safe("Patient", patient, patient_field)
            values[key] = value
            _set_value_safe("Patient Registration Form", patient_registration_form, prf_field, value)

    frappe.db.commit()

    return {
        "ok": True,
        "patient": patient,
        "patient_registration_form": patient_registration_form,
        "values": values,
        "field_map": fmap,
    }


@frappe.whitelist()
def force_sync_patient_to_prf(patient=None, patient_registration_form=None):
    return sync_extra_fields_from_patient_to_prf(patient, patient_registration_form)


@frappe.whitelist()
def repair_all_prf_extra_fields(limit=500):
    """
    Backfill existing Patient Registration Forms from linked Patient.
    """

    limit = int(limit or 500)

    rows = frappe.db.sql(
        """
        SELECT name, patient, custom_patient, custom_kpws_source_patient
        FROM `tabPatient Registration Form`
        ORDER BY modified DESC
        LIMIT %s
        """,
        (limit,),
        as_dict=True,
    )

    fixed = []
    skipped = []

    for row in rows:
        patient = row.get("patient") or row.get("custom_patient") or row.get("custom_kpws_source_patient")

        if not patient or not frappe.db.exists("Patient", patient):
            skipped.append(row.name)
            continue

        result = sync_extra_fields_from_patient_to_prf(patient, row.name)

        if result.get("ok"):
            fixed.append(row.name)
        else:
            skipped.append(row.name)

    return {
        "ok": True,
        "fixed_count": len(fixed),
        "skipped_count": len(skipped),
        "fixed": fixed[:50],
        "skipped": skipped[:50],
    }

# KPWS_PRF_EXTRA_FIELDS_AUTOSYNC_V1
def prf_before_save_copy_extra_fields(doc, method=None):
    """
    Carry forward Religion, Sanction, Nationality between Patient and Patient Registration Form.

    Rule:
    - If PRF field is blank, copy from Patient.
    - If PRF field has value, update Patient too.
    """

    patient = (
        doc.get("custom_patient")
        or doc.get("patient")
        or doc.get("custom_kpws_source_patient")
    )

    if not patient or not frappe.db.exists("Patient", patient):
        return

    p = frappe.get_doc("Patient", patient)

    field_pairs = [
        ("custom_religion", "religion1"),
        ("custom_sanction", "sanction"),
        ("custom_nationality", "nationality"),
    ]

    for patient_field, prf_field in field_pairs:
        if not p.meta.has_field(patient_field):
            continue

        if not doc.meta.has_field(prf_field):
            continue

        patient_value = p.get(patient_field) or ""
        prf_value = doc.get(prf_field) or ""

        # Intake -> Welfare Approval
        if patient_value and not prf_value:
            doc.set(prf_field, patient_value)
            prf_value = patient_value

        # Welfare Approval update -> Patient
        if prf_value and prf_value != patient_value:
            frappe.db.set_value(
                "Patient",
                patient,
                patient_field,
                prf_value,
                update_modified=False,
            )

    # Also maintain old/custom PRF fields if present
    if doc.meta.has_field("custom_religion") and doc.get("religion1"):
        doc.set("custom_religion", doc.get("religion1"))

    if doc.meta.has_field("custom_nationality") and doc.get("nationality"):
        doc.set("custom_nationality", doc.get("nationality"))



# KPWS_STABLE_PATIENT_PRF_EXTRA_FIELD_SYNC_V1

def _kpws_set_if_field(doc_or_doctype, name_or_field, fieldname=None, value=None):
    """
    Supports:
    - _kpws_set_if_field(doc, fieldname, value)
    - _kpws_set_if_field(doctype, name, fieldname, value)
    """
    try:
        if isinstance(doc_or_doctype, str):
            doctype = doc_or_doctype
            name = name_or_field
            if not name or not frappe.db.exists(doctype, name):
                return False
            if not frappe.get_meta(doctype).has_field(fieldname):
                return False
            frappe.db.set_value(doctype, name, fieldname, value or "", update_modified=False)
            return True

        doc = doc_or_doctype
        field = name_or_field
        val = fieldname

        if doc and doc.meta.has_field(field):
            doc.set(field, val or "")
            return True

    except Exception:
        frappe.log_error(frappe.get_traceback(), "KPWS extra field set failed")

    return False


def _kpws_patient_extra_values(patient_doc):
    return {
        "religion": patient_doc.get("custom_religion") or "",
        "sanction": patient_doc.get("custom_sanction") or "",
        "nationality": patient_doc.get("custom_nationality") or "",
    }


def _kpws_prf_extra_values(prf_doc):
    return {
        "religion": prf_doc.get("religion1") or prf_doc.get("religion") or "",
        "sanction": prf_doc.get("sanction") or prf_doc.get("saction1") or "",
        "nationality": prf_doc.get("nationality") or "",
    }


def _kpws_find_prfs_for_patient(patient):
    if not patient:
        return []

    names = set()

    for fieldname in ["custom_patient", "patient", "custom_kpws_source_patient"]:
        try:
            if frappe.get_meta("Patient Registration Form").has_field(fieldname):
                rows = frappe.get_all(
                    "Patient Registration Form",
                    filters={fieldname: patient, "docstatus": 0},
                    pluck="name",
                    limit=100,
                )
                for r in rows:
                    names.add(r)
        except Exception:
            pass

    return list(names)


def patient_after_save_sync_extra_fields_to_prf(doc, method=None):
    """
    Patient Intake -> Welfare Approval

    Whenever Patient is saved from Patient Intake, sync the three fields
    to all open PRFs for that same patient.
    """
    if doc.doctype != "Patient":
        return

    vals = _kpws_patient_extra_values(doc)

    prfs = _kpws_find_prfs_for_patient(doc.name)

    for prf_name in prfs:
        if not frappe.db.exists("Patient Registration Form", prf_name):
            continue

        prf = frappe.get_doc("Patient Registration Form", prf_name)

        if prf.meta.has_field("religion1"):
            prf.db_set("religion1", vals["religion"], update_modified=False)
        elif prf.meta.has_field("religion"):
            prf.db_set("religion", vals["religion"], update_modified=False)

        if prf.meta.has_field("sanction"):
            prf.db_set("sanction", vals["sanction"], update_modified=False)
        elif prf.meta.has_field("saction1"):
            prf.db_set("saction1", vals["sanction"], update_modified=False)

        if prf.meta.has_field("nationality"):
            prf.db_set("nationality", vals["nationality"], update_modified=False)

        if prf.meta.has_field("custom_religion"):
            prf.db_set("custom_religion", vals["religion"], update_modified=False)

        if prf.meta.has_field("custom_nationality"):
            prf.db_set("custom_nationality", vals["nationality"], update_modified=False)


def prf_before_save_sync_extra_fields_to_patient(doc, method=None):
    """
    Welfare Approval -> Patient Intake

    If Administrator updates these fields on PRF, sync back to Patient.
    If PRF is blank, fill from Patient.
    """
    if doc.doctype != "Patient Registration Form":
        return

    patient = (
        doc.get("custom_patient")
        or doc.get("patient")
        or doc.get("custom_kpws_source_patient")
    )

    if not patient or not frappe.db.exists("Patient", patient):
        return

    patient_doc = frappe.get_doc("Patient", patient)
    pvals = _kpws_patient_extra_values(patient_doc)
    rvals = _kpws_prf_extra_values(doc)

    # If PRF is blank, carry from Patient
    if not rvals["religion"] and pvals["religion"]:
        if doc.meta.has_field("religion1"):
            doc.set("religion1", pvals["religion"])
        elif doc.meta.has_field("religion"):
            doc.set("religion", pvals["religion"])
        rvals["religion"] = pvals["religion"]

    if not rvals["sanction"] and pvals["sanction"]:
        if doc.meta.has_field("sanction"):
            doc.set("sanction", pvals["sanction"])
        elif doc.meta.has_field("saction1"):
            doc.set("saction1", pvals["sanction"])
        rvals["sanction"] = pvals["sanction"]

    if not rvals["nationality"] and pvals["nationality"]:
        if doc.meta.has_field("nationality"):
            doc.set("nationality", pvals["nationality"])
        rvals["nationality"] = pvals["nationality"]

    # If PRF has values, sync back to Patient
    if rvals["religion"]:
        frappe.db.set_value("Patient", patient, "custom_religion", rvals["religion"], update_modified=False)

    if rvals["sanction"]:
        frappe.db.set_value("Patient", patient, "custom_sanction", rvals["sanction"], update_modified=False)

    if rvals["nationality"]:
        frappe.db.set_value("Patient", patient, "custom_nationality", rvals["nationality"], update_modified=False)

    if doc.meta.has_field("custom_religion") and rvals["religion"]:
        doc.set("custom_religion", rvals["religion"])

    if doc.meta.has_field("custom_nationality") and rvals["nationality"]:
        doc.set("custom_nationality", rvals["nationality"])

# KPWS_CORE_PATIENT_EXTRA_FIELDS_INSTALLER_V90
@frappe.whitelist()
def ensure_core_patient_extra_fields():
    """
    Ensure Religion, Saction/Sanction and Nationality exist as Patient core custom fields
    and also exist on Patient Registration Form for welfare approval snapshot/carry-forward.
    """
    import frappe

    def has_field(dt, fieldname):
        try:
            return frappe.get_meta(dt).has_field(fieldname)
        except Exception:
            return False

    def insert_after(dt, candidates):
        try:
            meta = frappe.get_meta(dt)
            for fieldname in candidates:
                if fieldname and meta.has_field(fieldname):
                    return fieldname
        except Exception:
            pass
        return None

    def ensure(dt, fieldname, label, after_candidates, allow_on_submit=0):
        out = {"doctype": dt, "fieldname": fieldname, "label": label, "status": "exists"}

        if has_field(dt, fieldname):
            return out

        cf_name = f"{dt}-{fieldname}"
        if frappe.db.exists("Custom Field", cf_name):
            # Custom Field exists but meta cache may be stale.
            frappe.clear_cache(doctype=dt)
            out["status"] = "custom_field_exists_cache_cleared"
            return out

        cf = frappe.get_doc({
            "doctype": "Custom Field",
            "dt": dt,
            "fieldname": fieldname,
            "label": label,
            "fieldtype": "Data",
            "insert_after": insert_after(dt, after_candidates),
            "allow_on_submit": allow_on_submit,
        })
        cf.insert(ignore_permissions=True)
        frappe.clear_cache(doctype=dt)
        out["status"] = "created"
        return out

    result = []
    result.append(ensure("Patient", "custom_religion", "Religion", ["custom_kpws_mobile_no", "mobile", "sex", "age_"]))
    result.append(ensure("Patient", "custom_sanction", "Saction", ["custom_religion", "custom_kpws_mobile_no", "mobile", "sex"]))
    result.append(ensure("Patient", "custom_nationality", "Nationality", ["custom_sanction", "custom_religion", "custom_kpws_mobile_no", "mobile"]))

    if frappe.db.exists("DocType", "Patient Registration Form"):
        result.append(ensure("Patient Registration Form", "custom_religion", "Religion", ["custom_mr_number", "custom_patient_name", "custom_patient"], allow_on_submit=1))
        result.append(ensure("Patient Registration Form", "custom_sanction", "Saction", ["custom_religion", "custom_mr_number", "custom_patient_name"], allow_on_submit=1))
        result.append(ensure("Patient Registration Form", "custom_nationality", "Nationality", ["custom_sanction", "custom_religion", "custom_mr_number"], allow_on_submit=1))

    frappe.db.commit()
    return {"ok": True, "fields": result, "debug": debug_field_status()}
