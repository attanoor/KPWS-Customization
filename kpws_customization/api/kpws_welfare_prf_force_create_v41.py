import frappe
from frappe.utils import nowdate, now_datetime


DOCTYPE = "Patient Registration Form"


def _has_field(doctype, fieldname):
    try:
        return frappe.get_meta(doctype).has_field(fieldname)
    except Exception:
        return False


def _table_columns(doctype):
    return {
        r["Field"]
        for r in frappe.db.sql(f"SHOW COLUMNS FROM `tab{doctype}`", as_dict=True)
    }


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


def _active_prf_map():
    mapping = {}

    for fieldname in ["custom_patient", "patient"]:
        if not _has_field(DOCTYPE, fieldname):
            continue

        rows = frappe.db.sql(
            f"""
            SELECT name, `{fieldname}` AS patient, docstatus, IFNULL(workflow_state, '') AS workflow_state
            FROM `tab{DOCTYPE}`
            WHERE docstatus != 2
              AND IFNULL(`{fieldname}`, '') != ''
            ORDER BY docstatus DESC, creation DESC
            """,
            as_dict=True,
        )

        for row in rows:
            if row.patient and row.patient not in mapping:
                mapping[row.patient] = row

    return mapping


def _safe_name(patient):
    base = f"PRF-WEL-{patient}"
    name = base
    counter = 1

    while frappe.db.exists(DOCTYPE, name):
        counter += 1
        name = f"{base}-{counter}"

    return name


def _identity_values(patient):
    try:
        from kpws_customization.api.kpws_prf_dynamic_identity_fetch_v35 import _identity_values
        values, debug = _identity_values(patient)
        return values or {}
    except Exception:
        return {}


def _base_values(patient):
    pdoc = frappe.get_doc("Patient", patient)
    now = now_datetime()

    values = {
        "name": _safe_name(patient),
        "creation": now,
        "modified": now,
        "modified_by": frappe.session.user,
        "owner": frappe.session.user,
        "docstatus": 1,
        "idx": 0,

        "custom_patient": patient,
        "patient": patient,
        "date": nowdate(),
        "form_no": patient,

        "custom_mr_number": _patient_mr(pdoc),
        "mr_no": _patient_mr(pdoc),

        "custom_patient_name": _patient_name(pdoc),
        "patient_full_name": _patient_name(pdoc),

        "custom_patient_customer": _patient_customer(pdoc),
        "custom_billing_type": "Welfare",

        "purpose": "Zakat",
        "custom_kpws_welfare_type": "Zakat",

        "discount_type": "Percentage",
        "discount_value": 100,
        "custom_kpws_welfare_percentage": 100,

        "workflow_state": "Approved",
        "status": "Approved",

        "custom_kpws_admin_notes": "Force-created/updated for all Welfare patients: 100% Zakat approved.",
        "remarks": "Force-created/updated for all Welfare patients: 100% Zakat approved.",
    }

    identity = _identity_values(patient)
    values.update(identity)

    return values


def _insert_raw_prf(patient):
    columns = _table_columns(DOCTYPE)
    values = _base_values(patient)

    clean = {
        key: value
        for key, value in values.items()
        if key in columns
    }

    col_sql = ", ".join(f"`{c}`" for c in clean.keys())
    placeholders = ", ".join(["%s"] * len(clean))

    frappe.db.sql(
        f"""
        INSERT INTO `tab{DOCTYPE}` ({col_sql})
        VALUES ({placeholders})
        """,
        list(clean.values()),
    )

    return clean["name"]


def _update_raw_prf(prf_name, patient):
    columns = _table_columns(DOCTYPE)
    values = _base_values(patient)

    values.pop("name", None)
    values.pop("creation", None)
    values.pop("owner", None)
    values["modified"] = now_datetime()
    values["modified_by"] = frappe.session.user
    values["docstatus"] = 1

    clean = {
        key: value
        for key, value in values.items()
        if key in columns
    }

    set_sql = ", ".join(f"`{c}`=%s" for c in clean.keys())

    frappe.db.sql(
        f"""
        UPDATE `tab{DOCTYPE}`
        SET {set_sql}
        WHERE name=%s
        """,
        list(clean.values()) + [prf_name],
    )

    return prf_name


@frappe.whitelist()
def audit():
    welfare = _welfare_patients()
    active = _active_prf_map()

    missing = [p for p in welfare if p not in active]
    existing = [p for p in welfare if p in active]

    return {
        "welfare_patients": len(welfare),
        "existing_active_prf_for_welfare": len(existing),
        "missing_active_prf_for_welfare": len(missing),
        "sample_missing": missing[:50],
        "sample_existing": [
            {
                "patient": p,
                "prf": active[p].name,
                "docstatus": active[p].docstatus,
                "workflow_state": active[p].workflow_state,
            }
            for p in existing[:50]
        ],
    }


@frappe.whitelist()
def run(dry_run=1, limit=0):
    dry_run = int(dry_run)
    limit = int(limit or 0)

    welfare = _welfare_patients()
    active = _active_prf_map()

    would_create = []
    would_update = []
    created = []
    updated = []
    errors = []

    processed = 0

    for patient in welfare:
        try:
            existing = active.get(patient)

            if existing:
                if dry_run:
                    would_update.append({
                        "patient": patient,
                        "prf": existing.name,
                        "set": "Approved 100% Zakat",
                    })
                else:
                    prf = _update_raw_prf(existing.name, patient)
                    updated.append({
                        "patient": patient,
                        "prf": prf,
                        "set": "Approved 100% Zakat",
                    })
                    processed += 1
            else:
                if dry_run:
                    would_create.append({
                        "patient": patient,
                        "set": "Approved 100% Zakat",
                    })
                else:
                    prf = _insert_raw_prf(patient)
                    created.append({
                        "patient": patient,
                        "prf": prf,
                        "set": "Approved 100% Zakat",
                    })
                    processed += 1

            if limit and dry_run and (len(would_create) + len(would_update)) >= limit:
                break

            if limit and not dry_run and processed >= limit:
                break

            if not dry_run and processed and processed % 100 == 0:
                frappe.db.commit()

        except Exception as e:
            errors.append({
                "patient": patient,
                "error": str(e),
            })

    frappe.db.commit()

    return {
        "dry_run": dry_run,
        "total_welfare_patients": len(welfare),
        "would_create_count": len(would_create),
        "would_update_count": len(would_update),
        "created_count": len(created),
        "updated_count": len(updated),
        "error_count": len(errors),
        "would_create_sample": would_create[:20],
        "would_update_sample": would_update[:20],
        "created_sample": created[:20],
        "updated_sample": updated[:20],
        "errors": errors[:50],
    }


@frappe.whitelist()
def verify_counts():
    welfare = _welfare_patients()
    active = _active_prf_map()

    missing = [p for p in welfare if p not in active]

    correct = 0
    incorrect = []

    for patient in welfare:
        row = active.get(patient)

        if not row:
            continue

        data = frappe.db.get_value(
            DOCTYPE,
            row.name,
            ["docstatus", "workflow_state", "purpose", "discount_value"],
            as_dict=True,
        )

        if (
            data
            and int(data.docstatus) == 1
            and data.workflow_state == "Approved"
            and data.purpose == "Zakat"
            and float(data.discount_value or 0) == 100
        ):
            correct += 1
        else:
            incorrect.append({
                "patient": patient,
                "prf": row.name,
                "data": data,
            })

    breakdown = frappe.db.sql(
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

    return {
        "welfare_patients": len(welfare),
        "welfare_patients_with_active_prf": len(welfare) - len(missing),
        "welfare_patients_missing_active_prf": len(missing),
        "welfare_patients_correct_approved_zakat_100": correct,
        "incorrect_sample": incorrect[:50],
        "missing_sample": missing[:50],
        "overall_prf_breakdown": breakdown,
    }
