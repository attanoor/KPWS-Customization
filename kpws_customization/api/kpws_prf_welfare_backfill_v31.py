import random
import frappe
from frappe.utils import nowdate, flt


DOCTYPE = "Patient Registration Form"


def _has_field(doctype, fieldname):
    try:
        return frappe.get_meta(doctype).has_field(fieldname)
    except Exception:
        return False


def _get(doc, fields, default=None):
    for field in fields:
        if doc.meta.has_field(field) and doc.get(field) not in (None, ""):
            return doc.get(field)
    return default


def _set_if_has(doc, fieldname, value):
    if _has_field(doc.doctype, fieldname):
        try:
            doc.set(fieldname, value)
            return True
        except Exception:
            return False
    return False


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
    return _get(
        patient_doc,
        [
            "customer",
            "custom_customer",
            "custom_patient_customer",
            "patient_customer",
            "custom_linked_customer",
        ],
        None,
    )


def _is_welfare_patient(patient_doc):
    # Direct patient fields
    for fieldname in [
        "custom_billing_type",
        "billing_type",
        "patient_type",
        "custom_patient_type",
        "customer_group",
        "custom_customer_group",
    ]:
        if patient_doc.meta.has_field(fieldname):
            value = (patient_doc.get(fieldname) or "").strip().lower()
            if value == "welfare":
                return True

    # Linked customer group
    customer = _patient_customer(patient_doc)
    if customer and frappe.db.exists("Customer", customer):
        group = frappe.db.get_value("Customer", customer, "customer_group")
        if (group or "").strip().lower() == "welfare":
            return True

    return False


def _existing_prf(patient):
    patient_fields = [
        "custom_patient",
        "patient",
    ]

    for fieldname in patient_fields:
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


def _parse_percentages(percentages):
    if not percentages:
        return [25, 50, 75, 100]

    if isinstance(percentages, str):
        values = []
        for p in percentages.split(","):
            p = p.strip()
            if not p:
                continue
            value = flt(p)
            if 0 <= value <= 100:
                values.append(value)
        return values or [25, 50, 75, 100]

    return [25, 50, 75, 100]


def _approve_doc(doc, force_submit=True):
    # Prefer real submit if DocType is submittable.
    submitted = False

    if frappe.get_meta(DOCTYPE).is_submittable:
        try:
            doc.submit()
            submitted = True
        except Exception as e:
            if not force_submit:
                raise

            # Migration fallback only.
            frappe.db.set_value(DOCTYPE, doc.name, "docstatus", 1, update_modified=False)
            submitted = True

    # If not submittable, still mark approval fields.
    if _has_field(DOCTYPE, "workflow_state"):
        frappe.db.set_value(DOCTYPE, doc.name, "workflow_state", "Approved", update_modified=False)

    if _has_field(DOCTYPE, "status"):
        frappe.db.set_value(DOCTYPE, doc.name, "status", "Approved", update_modified=False)

    frappe.db.commit()
    return submitted


def _create_prf(patient_doc, purpose, percentage, force_submit=True):
    patient_name = _patient_name(patient_doc)
    mr_number = _patient_mr(patient_doc)
    customer = _patient_customer(patient_doc)

    doc = frappe.new_doc(DOCTYPE)
    doc.flags.ignore_permissions = True
    doc.flags.ignore_mandatory = True

    _set_if_has(doc, "custom_patient", patient_doc.name)
    _set_if_has(doc, "patient", patient_doc.name)

    _set_if_has(doc, "date", nowdate())
    _set_if_has(doc, "form_no", patient_doc.name)

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

    _set_if_has(doc, "custom_kpws_admin_notes", "Auto-created by KPWS welfare PRF backfill.")
    _set_if_has(doc, "remarks", "Auto-created by KPWS welfare PRF backfill.")

    # Copy optional patient details if available.
    _set_if_has(doc, "contact_no", _get(patient_doc, ["mobile", "mobile_no", "phone", "contact_no", "custom_contact_no"], ""))
    _set_if_has(doc, "cnic", _get(patient_doc, ["cnic", "custom_cnic"], ""))
    _set_if_has(doc, "nationality", _get(patient_doc, ["nationality", "custom_nationality"], ""))
    _set_if_has(doc, "religion1", _get(patient_doc, ["religion", "custom_religion"], ""))
    _set_if_has(doc, "saction1", _get(patient_doc, ["saction", "section", "custom_saction", "custom_section"], ""))

    if _has_field(DOCTYPE, "workflow_state"):
        doc.workflow_state = "Approved"

    doc.insert(ignore_permissions=True)
    _approve_doc(doc, force_submit=force_submit)

    return doc.name


@frappe.whitelist()
def run(dry_run=1, limit=0, seed="KPWS-WELFARE-PRF-2026", percentages="25,50,75,100", force_submit=1):
    dry_run = int(dry_run)
    limit = int(limit or 0)
    force_submit = int(force_submit or 1)

    percentage_values = _parse_percentages(percentages)
    rng = random.Random(str(seed))

    patient_names = frappe.get_all(
        "Patient",
        fields=["name"],
        order_by="creation asc",
        limit_page_length=0,
    )

    scanned = 0
    welfare_found = 0
    skipped_existing = 0
    created = 0
    preview = []
    errors = []

    for row in patient_names:
        scanned += 1

        try:
            patient_doc = frappe.get_doc("Patient", row.name)

            if not _is_welfare_patient(patient_doc):
                continue

            welfare_found += 1

            existing = _existing_prf(patient_doc.name)
            if existing:
                skipped_existing += 1
                preview.append({
                    "patient": patient_doc.name,
                    "patient_name": _patient_name(patient_doc),
                    "status": "Skipped - PRF already exists",
                    "existing_prf": existing.name,
                    "docstatus": existing.docstatus,
                })
                continue

            purpose = rng.choice(["Zakat", "Donation"])
            percentage = rng.choice(percentage_values)

            item = {
                "patient": patient_doc.name,
                "patient_name": _patient_name(patient_doc),
                "mr_number": _patient_mr(patient_doc),
                "customer": _patient_customer(patient_doc),
                "purpose": purpose,
                "percentage": percentage,
                "status": "Would Create" if dry_run else "Created",
            }

            if not dry_run:
                prf_name = _create_prf(
                    patient_doc=patient_doc,
                    purpose=purpose,
                    percentage=percentage,
                    force_submit=force_submit,
                )
                item["prf"] = prf_name
                created += 1

            preview.append(item)

            if limit and created >= limit and not dry_run:
                break

            if limit and dry_run and len([x for x in preview if x.get("status") == "Would Create"]) >= limit:
                break

        except Exception as e:
            errors.append({
                "patient": row.name,
                "error": str(e),
            })

    frappe.db.commit()

    return {
        "dry_run": dry_run,
        "scanned_patients": scanned,
        "welfare_patients_found": welfare_found,
        "skipped_existing_prf": skipped_existing,
        "created": created,
        "percentage_values": percentage_values,
        "preview_count": len(preview),
        "preview": preview[:100],
        "errors": errors[:50],
    }


@frappe.whitelist()
def verify(limit=20):
    rows = frappe.get_all(
        DOCTYPE,
        filters={
            "docstatus": ["!=", 2],
        },
        fields=[
            "name",
            "docstatus",
            "workflow_state",
            "custom_patient",
            "custom_patient_name",
            "custom_billing_type",
            "purpose",
            "discount_value",
            "custom_kpws_welfare_type",
            "custom_kpws_welfare_percentage",
            "creation",
        ],
        order_by="creation desc",
        limit_page_length=int(limit or 20),
    )

    return rows
