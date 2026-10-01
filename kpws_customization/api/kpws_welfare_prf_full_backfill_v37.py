import random
import frappe
from frappe.utils import nowdate, flt


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

    # Primary confirmed source from your audit:
    # Patient.customer_group = Welfare
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

    # Also confirm through linked Customer.customer_group = Welfare.
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


def _parse_percentages(percentages):
    values = []

    for p in str(percentages or "25,50,75,100").split(","):
        p = p.strip()
        if not p:
            continue

        value = flt(p)

        if 0 <= value <= 100:
            values.append(value)

    return values or [25, 50, 75, 100]


def _fill_identity(doc, patient):
    try:
        from kpws_customization.api.kpws_prf_dynamic_identity_fetch_v35 import populate_identity_from_patient
        populate_identity_from_patient(doc, overwrite=False)
    except Exception:
        pass


def _fill_prf_fields(doc, pdoc, purpose, percentage, note):
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

    _set_if_has(doc, "purpose", purpose)
    _set_if_has(doc, "custom_kpws_welfare_type", purpose)

    _set_if_has(doc, "discount_type", "Percentage")
    _set_if_has(doc, "discount_value", percentage)
    _set_if_has(doc, "custom_kpws_welfare_percentage", percentage)

    _set_if_has(doc, "workflow_state", "Approved")
    _set_if_has(doc, "status", "Approved")

    _set_if_has(doc, "custom_kpws_admin_notes", note)
    _set_if_has(doc, "remarks", note)

    _fill_identity(doc, patient)


def _approve_or_submit(doc):
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
                # Controlled backfill fallback.
                frappe.db.set_value(DOCTYPE, doc.name, "docstatus", 1, update_modified=False)
        else:
            doc.save(ignore_permissions=True)

    elif doc.docstatus == 1:
        doc.flags.ignore_validate_update_after_submit = True
        doc.save(ignore_permissions=True)

    frappe.db.commit()


def _create_prf(patient, purpose, percentage):
    pdoc = frappe.get_doc("Patient", patient)

    doc = frappe.new_doc(DOCTYPE)
    doc.flags.ignore_permissions = True
    doc.flags.ignore_mandatory = True

    _fill_prf_fields(
        doc=doc,
        pdoc=pdoc,
        purpose=purpose,
        percentage=percentage,
        note="Auto-created and approved by KPWS Welfare PRF full backfill.",
    )

    doc.insert(ignore_permissions=True)
    _approve_or_submit(doc)

    return doc.name


def _update_existing_draft_prf(prf_name, patient, purpose, percentage):
    pdoc = frappe.get_doc("Patient", patient)
    doc = frappe.get_doc(DOCTYPE, prf_name)

    _fill_prf_fields(
        doc=doc,
        pdoc=pdoc,
        purpose=purpose,
        percentage=percentage,
        note="Auto-updated and approved by KPWS Welfare PRF full backfill.",
    )

    _approve_or_submit(doc)

    return doc.name


@frappe.whitelist()
def audit():
    welfare_patients = _welfare_patients()

    with_active_prf = []
    without_active_prf = []
    draft_prfs = []
    submitted_prfs = []

    for patient in welfare_patients:
        existing = _existing_active_prf(patient)

        if existing:
            with_active_prf.append({
                "patient": patient,
                "prf": existing.name,
                "docstatus": existing.docstatus,
                "workflow_state": existing.workflow_state,
            })

            if existing.docstatus == 0:
                draft_prfs.append(existing.name)
            elif existing.docstatus == 1:
                submitted_prfs.append(existing.name)
        else:
            without_active_prf.append(patient)

    return {
        "welfare_patients": len(welfare_patients),
        "welfare_patients_with_active_prf": len(with_active_prf),
        "welfare_patients_without_active_prf": len(without_active_prf),
        "draft_prfs_for_welfare_patients": len(draft_prfs),
        "submitted_prfs_for_welfare_patients": len(submitted_prfs),
        "sample_without_prf": without_active_prf[:50],
        "sample_draft_prfs": draft_prfs[:50],
        "sample_with_active_prf": with_active_prf[:50],
    }


@frappe.whitelist()
def run(dry_run=1, limit=0, seed="KPWS-WELFARE-FULL-BACKFILL-V37", percentages="25,50,75,100", update_drafts=1):
    dry_run = int(dry_run)
    limit = int(limit or 0)
    update_drafts = int(update_drafts or 1)

    rng = random.Random(str(seed))
    percentage_values = _parse_percentages(percentages)

    welfare_patients = _welfare_patients()

    created = []
    updated_drafts = []
    skipped_submitted = []
    errors = []
    would_create = []
    would_update_drafts = []

    processed_live = 0

    for patient in welfare_patients:
        try:
            existing = _existing_active_prf(patient)

            purpose = rng.choice(["Zakat", "Donation"])
            percentage = rng.choice(percentage_values)

            if existing:
                if existing.docstatus == 0 and update_drafts:
                    if dry_run:
                        would_update_drafts.append({
                            "patient": patient,
                            "prf": existing.name,
                            "purpose": purpose,
                            "percentage": percentage,
                        })
                    else:
                        prf = _update_existing_draft_prf(
                            prf_name=existing.name,
                            patient=patient,
                            purpose=purpose,
                            percentage=percentage,
                        )
                        updated_drafts.append({
                            "patient": patient,
                            "prf": prf,
                            "purpose": purpose,
                            "percentage": percentage,
                        })
                        processed_live += 1
                else:
                    skipped_submitted.append({
                        "patient": patient,
                        "prf": existing.name,
                        "docstatus": existing.docstatus,
                        "workflow_state": existing.workflow_state,
                    })

                continue

            if dry_run:
                would_create.append({
                    "patient": patient,
                    "purpose": purpose,
                    "percentage": percentage,
                })
            else:
                prf = _create_prf(patient, purpose, percentage)
                created.append({
                    "patient": patient,
                    "prf": prf,
                    "purpose": purpose,
                    "percentage": percentage,
                })
                processed_live += 1

            if limit and dry_run:
                if len(would_create) + len(would_update_drafts) >= limit:
                    break

            if limit and not dry_run:
                if processed_live >= limit:
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
        "would_update_draft_count": len(would_update_drafts),
        "created_count": len(created),
        "updated_draft_count": len(updated_drafts),
        "skipped_existing_submitted_or_active_count": len(skipped_submitted),
        "error_count": len(errors),
        "percentage_values": percentage_values,
        "would_create_sample": would_create[:50],
        "would_update_drafts_sample": would_update_drafts[:50],
        "created_sample": created[:50],
        "updated_drafts_sample": updated_drafts[:50],
        "errors": errors[:50],
    }


@frappe.whitelist()
def verify_counts():
    rows = frappe.db.sql(
        """
        SELECT
            docstatus,
            IFNULL(workflow_state, '') AS workflow_state,
            COUNT(*) AS count
        FROM `tabPatient Registration Form`
        GROUP BY docstatus, IFNULL(workflow_state, '')
        ORDER BY docstatus, workflow_state
        """,
        as_dict=True,
    )

    return {
        "prf_breakdown": rows,
        "audit": audit(),
    }
