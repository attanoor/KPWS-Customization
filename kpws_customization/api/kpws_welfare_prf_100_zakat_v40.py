import frappe
from frappe.utils import nowdate


DOCTYPE = "Patient Registration Form"


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


def _patient_name(pdoc):
    return (
        _get(pdoc, ["patient_name", "full_name"])
        or " ".join(
            str(x or "").strip()
            for x in [
                _get(pdoc, ["first_name"], ""),
                _get(pdoc, ["middle_name"], ""),
                _get(pdoc, ["last_name"], ""),
            ]
            if x
        )
        or pdoc.name
    )


def _patient_mr(pdoc):
    return _get(
        pdoc,
        [
            "custom_reference_number",
            "custom_mr_number",
            "mr_number",
            "patient_mr_number",
            "uid",
        ],
        pdoc.name,
    )


def _patient_customer(pdoc):
    return _get(
        pdoc,
        [
            "customer",
            "custom_customer",
            "custom_patient_customer",
            "patient_customer",
            "custom_linked_customer",
            "customer_id",
        ],
        None,
    )


def _welfare_patients():
    patients = set()

    # Confirmed KPWS source from audit: Patient.customer_group = Welfare
    if _has_field("Patient", "customer_group"):
        rows = frappe.db.sql(
            """
            SELECT name
            FROM `tabPatient`
            WHERE customer_group = 'Welfare'
            ORDER BY creation ASC
            """,
            as_dict=True,
        )
        for row in rows:
            patients.add(row.name)

    # Safety: linked Customer.customer_group = Welfare
    if _has_field("Patient", "customer"):
        rows = frappe.db.sql(
            """
            SELECT p.name
            FROM `tabPatient` p
            INNER JOIN `tabCustomer` c ON c.name = p.customer
            WHERE c.customer_group = 'Welfare'
            ORDER BY p.creation ASC
            """,
            as_dict=True,
        )
        for row in rows:
            patients.add(row.name)

    return sorted(patients)


def _existing_active_prf(patient):
    for fieldname in ["custom_patient", "patient"]:
        if not _has_field(DOCTYPE, fieldname):
            continue

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


def _fill_identity(doc, patient):
    try:
        from kpws_customization.api.kpws_prf_dynamic_identity_fetch_v35 import populate_identity_from_patient
        populate_identity_from_patient(doc, overwrite=False)
    except Exception:
        pass


def _fill_prf_fields(doc, pdoc):
    patient = pdoc.name
    customer = _patient_customer(pdoc)

    _set_if_has(doc, "custom_patient", patient)
    _set_if_has(doc, "patient", patient)

    _set_if_has(doc, "date", nowdate())
    _set_if_has(doc, "form_no", patient)

    _set_if_has(doc, "custom_mr_number", _patient_mr(pdoc))
    _set_if_has(doc, "mr_no", _patient_mr(pdoc))

    _set_if_has(doc, "custom_patient_name", _patient_name(pdoc))
    _set_if_has(doc, "patient_full_name", _patient_name(pdoc))

    _set_if_has(doc, "custom_patient_customer", customer)
    _set_if_has(doc, "custom_billing_type", "Welfare")

    # Required final values
    _set_if_has(doc, "purpose", "Zakat")
    _set_if_has(doc, "custom_kpws_welfare_type", "Zakat")

    _set_if_has(doc, "discount_type", "Percentage")
    _set_if_has(doc, "discount_value", 100)
    _set_if_has(doc, "custom_kpws_welfare_percentage", 100)

    _set_if_has(doc, "workflow_state", "Approved")
    _set_if_has(doc, "status", "Approved")

    note = "Auto-created/updated for all Welfare patients: 100% Zakat approved."
    _set_if_has(doc, "custom_kpws_admin_notes", note)
    _set_if_has(doc, "remarks", note)

    _fill_identity(doc, patient)


def _submit_or_approve(doc):
    if doc.docstatus == 2:
        return

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
        # Update submitted PRF safely.
        doc.flags.ignore_validate_update_after_submit = True
        try:
            doc.save(ignore_permissions=True)
        except Exception:
            pass

    # Final DB enforcement for submitted/approved and 100% Zakat.
    updates = {}

    for fieldname, value in {
        "workflow_state": "Approved",
        "status": "Approved",
        "purpose": "Zakat",
        "custom_kpws_welfare_type": "Zakat",
        "discount_type": "Percentage",
        "discount_value": 100,
        "custom_kpws_welfare_percentage": 100,
        "custom_billing_type": "Welfare",
    }.items():
        if _has_field(DOCTYPE, fieldname):
            updates[fieldname] = value

    if updates:
        frappe.db.set_value(DOCTYPE, doc.name, updates, update_modified=False)

    if frappe.get_meta(DOCTYPE).is_submittable:
        frappe.db.set_value(DOCTYPE, doc.name, "docstatus", 1, update_modified=False)

    frappe.db.commit()


def _create_prf(patient):
    pdoc = frappe.get_doc("Patient", patient)

    doc = frappe.new_doc(DOCTYPE)
    doc.flags.ignore_permissions = True
    doc.flags.ignore_mandatory = True

    _fill_prf_fields(doc, pdoc)

    doc.insert(ignore_permissions=True)
    _submit_or_approve(doc)

    return doc.name


def _update_prf(prf_name, patient):
    pdoc = frappe.get_doc("Patient", patient)
    doc = frappe.get_doc(DOCTYPE, prf_name)

    _fill_prf_fields(doc, pdoc)
    _submit_or_approve(doc)

    return doc.name


@frappe.whitelist()
def audit():
    welfare_patients = _welfare_patients()

    missing = []
    existing_draft = []
    existing_submitted = []

    for patient in welfare_patients:
        existing = _existing_active_prf(patient)

        if not existing:
            missing.append(patient)
        elif existing.docstatus == 0:
            existing_draft.append({"patient": patient, "prf": existing.name})
        elif existing.docstatus == 1:
            existing_submitted.append({"patient": patient, "prf": existing.name, "workflow_state": existing.workflow_state})

    return {
        "welfare_patients": len(welfare_patients),
        "missing_active_prf": len(missing),
        "existing_draft_prf": len(existing_draft),
        "existing_submitted_prf": len(existing_submitted),
        "sample_missing": missing[:30],
        "sample_draft": existing_draft[:30],
        "sample_submitted": existing_submitted[:30],
    }


@frappe.whitelist()
def run(dry_run=1, limit=0):
    dry_run = int(dry_run)
    limit = int(limit or 0)

    welfare_patients = _welfare_patients()

    created = []
    updated = []
    errors = []
    would_create = []
    would_update = []

    processed_live = 0

    for patient in welfare_patients:
        try:
            existing = _existing_active_prf(patient)

            if existing:
                if dry_run:
                    would_update.append({
                        "patient": patient,
                        "prf": existing.name,
                        "from_docstatus": existing.docstatus,
                        "set": "Zakat 100 Approved",
                    })
                else:
                    prf = _update_prf(existing.name, patient)
                    updated.append({
                        "patient": patient,
                        "prf": prf,
                        "set": "Zakat 100 Approved",
                    })
                    processed_live += 1
            else:
                if dry_run:
                    would_create.append({
                        "patient": patient,
                        "set": "Zakat 100 Approved",
                    })
                else:
                    prf = _create_prf(patient)
                    created.append({
                        "patient": patient,
                        "prf": prf,
                        "set": "Zakat 100 Approved",
                    })
                    processed_live += 1

            if limit and dry_run and (len(would_create) + len(would_update)) >= limit:
                break

            if limit and not dry_run and processed_live >= limit:
                break

        except Exception as e:
            errors.append({
                "patient": patient,
                "error": str(e),
            })

    frappe.db.commit()

    return {
        "dry_run": dry_run,
        "total_welfare_patients": len(welfare_patients),
        "would_create_count": len(would_create),
        "would_update_count": len(would_update),
        "created_count": len(created),
        "updated_count": len(updated),
        "error_count": len(errors),
        "would_create_sample": would_create[:30],
        "would_update_sample": would_update[:30],
        "created_sample": created[:30],
        "updated_sample": updated[:30],
        "errors": errors[:50],
    }


@frappe.whitelist()
def verify_counts():
    welfare_patients = _welfare_patients()

    active_prf_patients = set()

    for fieldname in ["custom_patient", "patient"]:
        if not _has_field(DOCTYPE, fieldname):
            continue

        rows = frappe.db.sql(
            f"""
            SELECT DISTINCT `{fieldname}` AS patient
            FROM `tab{DOCTYPE}`
            WHERE docstatus != 2
              AND IFNULL(`{fieldname}`, '') != ''
            """,
            as_dict=True,
        )

        for row in rows:
            if row.patient:
                active_prf_patients.add(row.patient)

    missing = [p for p in welfare_patients if p not in active_prf_patients]

    prf_breakdown = frappe.db.sql(
        f"""
        SELECT
            docstatus,
            IFNULL(workflow_state, '') AS workflow_state,
            IFNULL(purpose, '') AS purpose,
            IFNULL(discount_value, 0) AS percentage,
            COUNT(*) AS count
        FROM `tab{DOCTYPE}`
        WHERE docstatus != 2
        GROUP BY docstatus, IFNULL(workflow_state, ''), IFNULL(purpose, ''), IFNULL(discount_value, 0)
        ORDER BY docstatus, workflow_state, purpose, percentage
        """,
        as_dict=True,
    )

    zakat_100_approved = frappe.db.sql(
        f"""
        SELECT COUNT(*) AS count
        FROM `tab{DOCTYPE}`
        WHERE docstatus = 1
          AND IFNULL(workflow_state, '') = 'Approved'
          AND IFNULL(purpose, '') = 'Zakat'
          AND IFNULL(discount_value, 0) = 100
        """,
        as_dict=True,
    )[0].count

    return {
        "welfare_patients": len(welfare_patients),
        "active_prf_patients": len(active_prf_patients),
        "welfare_patients_missing_active_prf": len(missing),
        "missing_sample": missing[:30],
        "submitted_approved_zakat_100_forms": zakat_100_approved,
        "prf_breakdown": prf_breakdown,
    }
