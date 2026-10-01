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
        doc.set(fieldname, value)
        return True
    return False


def _table_columns(doctype):
    try:
        return {r["Field"] for r in frappe.db.sql(f"SHOW COLUMNS FROM `tab{doctype}`", as_dict=True)}
    except Exception:
        return set()


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
            "name",
        ],
        patient_doc.name,
    )


def _possible_patient_customers(patient_doc):
    customers = set()

    # Direct fields on Patient
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
                customers.add(value)

    # Customer with same name as Patient
    if frappe.db.exists("Customer", patient_doc.name):
        customers.add(patient_doc.name)

    # Dynamic Link: Customer linked with Patient
    try:
        dyn_rows = frappe.get_all(
            "Dynamic Link",
            filters={
                "link_doctype": "Patient",
                "link_name": patient_doc.name,
                "parenttype": "Customer",
            },
            fields=["parent"],
            limit_page_length=50,
        )
        for row in dyn_rows:
            if frappe.db.exists("Customer", row.parent):
                customers.add(row.parent)
    except Exception:
        pass

    # Customer fields that link to Patient
    try:
        customer_meta = frappe.get_meta("Customer")
        for df in customer_meta.fields:
            if df.fieldtype == "Link" and df.options == "Patient":
                fieldname = df.fieldname
                rows = frappe.get_all(
                    "Customer",
                    filters={fieldname: patient_doc.name},
                    fields=["name"],
                    limit_page_length=50,
                )
                for row in rows:
                    customers.add(row.name)
    except Exception:
        pass

    return sorted(customers)


def _customer_group(customer):
    if not customer or not frappe.db.exists("Customer", customer):
        return None

    return frappe.db.get_value("Customer", customer, "customer_group")


def _is_welfare_customer(customer):
    group = (_customer_group(customer) or "").strip().lower()
    return group == "welfare"


def _patient_direct_welfare(patient_doc):
    for fieldname in [
        "custom_billing_type",
        "billing_type",
        "patient_type",
        "custom_patient_type",
        "customer_group",
        "custom_customer_group",
        "custom_kpws_billing_type",
    ]:
        if patient_doc.meta.has_field(fieldname):
            value = (patient_doc.get(fieldname) or "").strip().lower()
            if value == "welfare":
                return True, f"Patient.{fieldname}=Welfare"

    return False, ""


def _sales_invoice_welfare_patients():
    patient_fields = []
    si_meta = frappe.get_meta("Sales Invoice")

    for fieldname in ["patient", "custom_patient"]:
        if si_meta.has_field(fieldname):
            patient_fields.append(fieldname)

    group_field = None
    for fieldname in ["custom_kpws_patient_billing_group", "custom_billing_type"]:
        if si_meta.has_field(fieldname):
            group_field = fieldname
            break

    patients = {}

    if not patient_fields or not group_field:
        return patients

    for patient_field in patient_fields:
        rows = frappe.db.sql(
            f"""
            SELECT DISTINCT `{patient_field}` AS patient
            FROM `tabSales Invoice`
            WHERE
                docstatus = 1
                AND IFNULL(`{patient_field}`, '') != ''
                AND `{group_field}` = 'Welfare'
            LIMIT 10000
            """,
            as_dict=True,
        )

        for row in rows:
            if row.patient and frappe.db.exists("Patient", row.patient):
                patients[row.patient] = f"Sales Invoice {group_field}=Welfare via {patient_field}"

    return patients


def _is_welfare_patient(patient_doc, invoice_welfare_map=None):
    invoice_welfare_map = invoice_welfare_map or {}

    direct, reason = _patient_direct_welfare(patient_doc)
    if direct:
        return True, reason, None

    for customer in _possible_patient_customers(patient_doc):
        if _is_welfare_customer(customer):
            return True, f"Linked Customer {customer} group=Welfare", customer

    if patient_doc.name in invoice_welfare_map:
        return True, invoice_welfare_map[patient_doc.name], None

    return False, "", None


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


def _parse_percentages(percentages):
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


def _submit_or_force_approved(doc):
    submitted = False

    if frappe.get_meta(DOCTYPE).is_submittable:
        try:
            doc.flags.ignore_mandatory = True
            doc.flags.ignore_validate = True
            doc.submit()
            submitted = True
        except Exception:
            frappe.db.set_value(DOCTYPE, doc.name, "docstatus", 1, update_modified=False)
            submitted = True
    else:
        submitted = False

    if _has_field(DOCTYPE, "workflow_state"):
        frappe.db.set_value(DOCTYPE, doc.name, "workflow_state", "Approved", update_modified=False)

    if _has_field(DOCTYPE, "status"):
        frappe.db.set_value(DOCTYPE, doc.name, "status", "Approved", update_modified=False)

    frappe.db.commit()
    return submitted


def _create_prf(patient_doc, purpose, percentage, linked_customer=None, reason=""):
    patient_name = _patient_name(patient_doc)
    mr_number = _patient_mr(patient_doc)

    customers = _possible_patient_customers(patient_doc)
    customer = linked_customer or (customers[0] if customers else None)

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

    _set_if_has(doc, "workflow_state", "Approved")
    _set_if_has(doc, "status", "Approved")

    note = f"Auto-created by KPWS welfare PRF backfill. Source: {reason}"
    _set_if_has(doc, "custom_kpws_admin_notes", note)
    _set_if_has(doc, "remarks", note)

    # Optional patient details
    _set_if_has(doc, "contact_no", _get(patient_doc, ["mobile", "mobile_no", "phone", "contact_no", "custom_contact_no"], ""))
    _set_if_has(doc, "cnic", _get(patient_doc, ["cnic", "custom_cnic"], ""))
    _set_if_has(doc, "nationality", _get(patient_doc, ["nationality", "custom_nationality"], ""))
    _set_if_has(doc, "religion1", _get(patient_doc, ["religion", "custom_religion"], ""))
    _set_if_has(doc, "saction1", _get(patient_doc, ["saction", "section", "custom_saction", "custom_section"], ""))

    doc.insert(ignore_permissions=True)
    _submit_or_force_approved(doc)

    return doc.name


@frappe.whitelist()
def audit(limit=50):
    invoice_welfare_map = _sales_invoice_welfare_patients()

    patient_rows = frappe.get_all(
        "Patient",
        fields=["name"],
        order_by="creation asc",
        limit_page_length=0,
    )

    found = []
    checked = 0

    for row in patient_rows:
        checked += 1

        patient_doc = frappe.get_doc("Patient", row.name)
        is_welfare, reason, linked_customer = _is_welfare_patient(patient_doc, invoice_welfare_map)

        if is_welfare:
            found.append({
                "patient": patient_doc.name,
                "patient_name": _patient_name(patient_doc),
                "mr_number": _patient_mr(patient_doc),
                "linked_customers": _possible_patient_customers(patient_doc),
                "linked_customer_used": linked_customer,
                "reason": reason,
                "existing_prf": (_existing_prf(patient_doc.name) or {}).get("name") if _existing_prf(patient_doc.name) else None,
            })

        if limit and len(found) >= int(limit):
            break

    return {
        "checked_patients": checked,
        "welfare_found_preview": len(found),
        "invoice_welfare_patients_found": len(invoice_welfare_map),
        "patient_columns": sorted(list(_table_columns("Patient"))),
        "customer_patient_link_fields": [
            df.fieldname for df in frappe.get_meta("Customer").fields
            if df.fieldtype == "Link" and df.options == "Patient"
        ],
        "preview": found,
    }


@frappe.whitelist()
def run(dry_run=1, limit=0, seed="KPWS-WELFARE-PRF-V32", percentages="25,50,75,100"):
    dry_run = int(dry_run)
    limit = int(limit or 0)

    percentage_values = _parse_percentages(percentages)
    rng = random.Random(str(seed))
    invoice_welfare_map = _sales_invoice_welfare_patients()

    patient_rows = frappe.get_all(
        "Patient",
        fields=["name"],
        order_by="creation asc",
        limit_page_length=0,
    )

    scanned = 0
    welfare_found = 0
    skipped_existing = 0
    created = 0
    would_create = 0
    preview = []
    errors = []

    for row in patient_rows:
        scanned += 1

        try:
            patient_doc = frappe.get_doc("Patient", row.name)
            is_welfare, reason, linked_customer = _is_welfare_patient(patient_doc, invoice_welfare_map)

            if not is_welfare:
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
                    "reason": reason,
                })
                continue

            purpose = rng.choice(["Zakat", "Donation"])
            percentage = rng.choice(percentage_values)

            item = {
                "patient": patient_doc.name,
                "patient_name": _patient_name(patient_doc),
                "mr_number": _patient_mr(patient_doc),
                "linked_customer": linked_customer,
                "purpose": purpose,
                "percentage": percentage,
                "reason": reason,
                "status": "Would Create" if dry_run else "Created",
            }

            if dry_run:
                would_create += 1
            else:
                prf_name = _create_prf(
                    patient_doc=patient_doc,
                    purpose=purpose,
                    percentage=percentage,
                    linked_customer=linked_customer,
                    reason=reason,
                )
                item["prf"] = prf_name
                created += 1

            preview.append(item)

            if limit:
                if dry_run and would_create >= limit:
                    break
                if not dry_run and created >= limit:
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
        "would_create": would_create,
        "created": created,
        "percentage_values": percentage_values,
        "preview_count": len(preview),
        "preview": preview[:100],
        "errors": errors[:50],
    }


@frappe.whitelist()
def verify(limit=30):
    fields = ["name", "docstatus", "creation"]

    for f in [
        "workflow_state",
        "custom_patient",
        "patient",
        "custom_patient_name",
        "custom_billing_type",
        "purpose",
        "discount_value",
        "custom_kpws_welfare_type",
        "custom_kpws_welfare_percentage",
    ]:
        if _has_field(DOCTYPE, f):
            fields.append(f)

    return frappe.get_all(
        DOCTYPE,
        filters={"docstatus": ["!=", 2]},
        fields=fields,
        order_by="creation desc",
        limit_page_length=int(limit or 30),
    )
