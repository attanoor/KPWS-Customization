import frappe


PRF = "Patient Registration Form"


def _has_field(doctype, fieldname):
    try:
        return frappe.get_meta(doctype).has_field(fieldname)
    except Exception:
        return False


def _count_sql(sql, values=None):
    row = frappe.db.sql(sql, values or (), as_dict=True)
    return row[0].count if row else 0


def _docstatus_counts(doctype):
    return frappe.db.sql(
        f"""
        SELECT
            docstatus,
            COUNT(*) AS count
        FROM `tab{doctype}`
        GROUP BY docstatus
        ORDER BY docstatus
        """,
        as_dict=True,
    )


def _prf_approval_audit():
    approval_field = None

    if _has_field(PRF, "workflow_state"):
        approval_field = "workflow_state"
    elif _has_field(PRF, "status"):
        approval_field = "status"

    total = _count_sql(f"SELECT COUNT(*) AS count FROM `tab{PRF}`")
    submitted = _count_sql(f"SELECT COUNT(*) AS count FROM `tab{PRF}` WHERE docstatus = 1")
    draft = _count_sql(f"SELECT COUNT(*) AS count FROM `tab{PRF}` WHERE docstatus = 0")
    cancelled = _count_sql(f"SELECT COUNT(*) AS count FROM `tab{PRF}` WHERE docstatus = 2")

    approved = 0
    not_approved = submitted
    not_approved_sample = []

    if approval_field:
        approved = _count_sql(
            f"""
            SELECT COUNT(*) AS count
            FROM `tab{PRF}`
            WHERE docstatus = 1
              AND IFNULL(`{approval_field}`, '') = 'Approved'
            """
        )

        not_approved = _count_sql(
            f"""
            SELECT COUNT(*) AS count
            FROM `tab{PRF}`
            WHERE docstatus = 1
              AND IFNULL(`{approval_field}`, '') != 'Approved'
            """
        )

        fields = ["name", "docstatus", approval_field, "creation", "modified"]

        for f in [
            "custom_patient",
            "patient",
            "custom_patient_name",
            "patient_full_name",
            "purpose",
            "discount_value",
            "custom_kpws_welfare_type",
            "custom_kpws_welfare_percentage",
        ]:
            if _has_field(PRF, f):
                fields.append(f)

        not_approved_sample = frappe.get_all(
            PRF,
            filters={
                "docstatus": 1,
                approval_field: ["!=", "Approved"],
            },
            fields=fields,
            order_by="modified desc",
            limit_page_length=50,
        )

    return {
        "approval_field_used": approval_field,
        "total_forms": total,
        "draft_forms_docstatus_0": draft,
        "submitted_forms_docstatus_1": submitted,
        "cancelled_forms_docstatus_2": cancelled,
        "submitted_and_approved": approved,
        "submitted_but_not_approved": not_approved,
        "docstatus_breakdown": _docstatus_counts(PRF),
        "not_approved_sample_limit_50": not_approved_sample,
    }


def _patient_direct_welfare_counts():
    candidate_fields = [
        "custom_billing_type",
        "billing_type",
        "patient_type",
        "custom_patient_type",
        "customer_group",
        "custom_customer_group",
        "custom_kpws_billing_type",
    ]

    existing_fields = [f for f in candidate_fields if _has_field("Patient", f)]

    breakdown = []
    welfare_patients = set()

    for fieldname in existing_fields:
        rows = frappe.db.sql(
            f"""
            SELECT name
            FROM `tabPatient`
            WHERE LOWER(TRIM(IFNULL(`{fieldname}`, ''))) = 'welfare'
            """,
            as_dict=True,
        )

        names = [r.name for r in rows]
        welfare_patients.update(names)

        breakdown.append({
            "field": fieldname,
            "welfare_count": len(names),
            "sample": names[:20],
        })

    return {
        "fields_checked": existing_fields,
        "unique_direct_welfare_patient_count": len(welfare_patients),
        "breakdown": breakdown,
        "sample_unique_direct_welfare_patients": sorted(list(welfare_patients))[:50],
    }


def _patient_customer_welfare_counts():
    patient_meta = frappe.get_meta("Patient")
    direct_customer_fields = [
        "customer",
        "custom_customer",
        "custom_patient_customer",
        "patient_customer",
        "custom_linked_customer",
        "customer_id",
    ]

    existing_customer_fields = [
        f for f in direct_customer_fields
        if patient_meta.has_field(f)
    ]

    welfare_patients = set()
    breakdown = []

    for fieldname in existing_customer_fields:
        rows = frappe.db.sql(
            f"""
            SELECT p.name AS patient, p.`{fieldname}` AS customer
            FROM `tabPatient` p
            INNER JOIN `tabCustomer` c
                ON c.name = p.`{fieldname}`
            WHERE c.customer_group = 'Welfare'
            """,
            as_dict=True,
        )

        for row in rows:
            welfare_patients.add(row.patient)

        breakdown.append({
            "patient_customer_field": fieldname,
            "welfare_customer_group_count": len(rows),
            "sample": rows[:20],
        })

    # Dynamic Link Customer -> Patient
    try:
        rows = frappe.db.sql(
            """
            SELECT dl.link_name AS patient, dl.parent AS customer
            FROM `tabDynamic Link` dl
            INNER JOIN `tabCustomer` c
                ON c.name = dl.parent
            WHERE dl.link_doctype = 'Patient'
              AND dl.parenttype = 'Customer'
              AND c.customer_group = 'Welfare'
            """,
            as_dict=True,
        )

        for row in rows:
            if frappe.db.exists("Patient", row.patient):
                welfare_patients.add(row.patient)

        breakdown.append({
            "patient_customer_field": "Dynamic Link Customer -> Patient",
            "welfare_customer_group_count": len(rows),
            "sample": rows[:20],
        })
    except Exception as e:
        breakdown.append({
            "patient_customer_field": "Dynamic Link Customer -> Patient",
            "error": str(e),
        })

    return {
        "fields_checked": existing_customer_fields + ["Dynamic Link Customer -> Patient"],
        "unique_linked_customer_welfare_patient_count": len(welfare_patients),
        "breakdown": breakdown,
        "sample_unique_linked_customer_welfare_patients": sorted(list(welfare_patients))[:50],
    }


@frappe.whitelist()
def run():
    total_patients = _count_sql("SELECT COUNT(*) AS count FROM `tabPatient`")

    direct = _patient_direct_welfare_counts()
    linked = _patient_customer_welfare_counts()

    all_welfare = set(direct.get("sample_unique_direct_welfare_patients") or [])
    all_welfare.update(linked.get("sample_unique_linked_customer_welfare_patients") or [])

    return {
        "patient_registration_form_audit": _prf_approval_audit(),
        "patient_audit": {
            "total_patients": total_patients,
            "direct_patient_type_welfare": direct,
            "linked_customer_group_welfare": linked,
            "note": "Direct count checks Patient fields. Linked count checks Customer Group = Welfare through Patient-Customer links.",
        },
    }
