import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)
    report_summary = get_report_summary(data)
    return columns, data, None, chart, report_summary


def get_columns():
    return [
        {"label": _("Request ID"), "fieldname": "name", "fieldtype": "Link", "options": "Patient Registration Form", "width": 120},
        {"label": _("Request Date"), "fieldname": "creation", "fieldtype": "Date", "width": 95},
        {"label": _("Last Updated"), "fieldname": "modified", "fieldtype": "Datetime", "width": 140},
        {"label": _("Patient"), "fieldname": "patient", "fieldtype": "Link", "options": "Patient", "width": 110},
        {"label": _("Patient Name"), "fieldname": "patient_name", "fieldtype": "Data", "width": 150},
        {"label": _("MR / KPWS Number"), "fieldname": "mr_number", "fieldtype": "Data", "width": 130},
        {"label": _("Type"), "fieldname": "funding_source", "fieldtype": "Data", "width": 100},
        {"label": _("Approved %"), "fieldname": "percentage", "fieldtype": "Percent", "width": 90},
        {"label": _("Panel Customer"), "fieldname": "panel_customer", "fieldtype": "Link", "options": "Customer", "width": 150},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
        {"label": _("Bills"), "fieldname": "bill_count", "fieldtype": "Int", "width": 70},
        {"label": _("Amount Given"), "fieldname": "amount_given", "fieldtype": "Currency", "width": 130},
    ]


def get_data(filters):
    conditions = ["1=1"]
    values = {}

    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    if from_date:
        conditions.append("DATE(prf.creation) >= %(from_date)s")
        values["from_date"] = from_date
    if to_date:
        conditions.append("DATE(prf.creation) <= %(to_date)s")
        values["to_date"] = to_date

    funding_source = filters.get("funding_source")
    if funding_source:
        conditions.append(
            "COALESCE(NULLIF(prf.custom_kpws_funding_source, ''), "
            "NULLIF(prf.custom_kpws_welfare_type, ''), NULLIF(prf.purpose, '')) = %(funding_source)s"
        )
        values["funding_source"] = funding_source

    status = filters.get("status")
    if status == "Approved":
        conditions.append("(prf.workflow_state = 'Approved' OR prf.docstatus = 1)")
    elif status == "Pending Approval":
        conditions.append("(prf.docstatus = 0 AND IFNULL(prf.workflow_state, '') IN ('Pending Approval', 'Draft', ''))")
    elif status == "Rejected":
        conditions.append("IFNULL(prf.workflow_state, '') = 'Rejected'")

    patient = filters.get("patient")
    if patient:
        conditions.append("prf.custom_patient = %(patient)s")
        values["patient"] = patient

    search_text = (filters.get("search_text") or "").strip()
    if search_text:
        values["search_text"] = "%" + search_text + "%"
        conditions.append(
            """
            (
                prf.name LIKE %(search_text)s
                OR p.patient_name LIKE %(search_text)s
                OR p.first_name LIKE %(search_text)s
                OR p.last_name LIKE %(search_text)s
                OR p.custom_reference_number LIKE %(search_text)s
                OR p.custom_kpws_cnic LIKE %(search_text)s
                OR p.cnic_number LIKE %(search_text)s
            )
            """
        )

    where_clause = " AND ".join(conditions)

    rows = frappe.db.sql(
        f"""
        SELECT
            prf.name AS name,
            prf.creation AS creation,
            prf.modified AS modified,
            prf.custom_patient AS patient,
            p.patient_name AS patient_name,
            p.custom_reference_number AS mr_number,
            COALESCE(
                NULLIF(prf.custom_kpws_funding_source, ''),
                NULLIF(prf.custom_kpws_welfare_type, ''),
                NULLIF(prf.purpose, ''),
                'Zakat'
            ) AS funding_source,
            COALESCE(prf.custom_kpws_welfare_percentage, prf.discount_value, 0) AS percentage,
            IFNULL(prf.custom_panel_customer, '') AS panel_customer,
            CASE
                WHEN prf.workflow_state = 'Approved' OR prf.docstatus = 1 THEN 'Approved'
                WHEN IFNULL(prf.workflow_state, '') = 'Rejected' THEN 'Rejected'
                ELSE 'Pending Approval'
            END AS status,
            IFNULL(inv.bill_count, 0) AS bill_count,
            IFNULL(inv.amount_given, 0) AS amount_given
        FROM `tabPatient Registration Form` prf
        LEFT JOIN `tabPatient` p ON p.name = prf.custom_patient
        LEFT JOIN (
            SELECT
                custom_kpws_welfare_registration AS registration,
                COUNT(*) AS bill_count,
                SUM(custom_kpws_welfare_covered_amount) AS amount_given
            FROM `tabSales Invoice`
            WHERE docstatus = 1
                AND custom_kpws_welfare_registration IS NOT NULL
                AND custom_kpws_welfare_registration != ''
            GROUP BY custom_kpws_welfare_registration
        ) inv ON inv.registration = prf.name
        WHERE {where_clause}
        ORDER BY prf.creation DESC
        """,
        values,
        as_dict=True,
    )

    for row in rows:
        row.percentage = flt(row.percentage)
        row.amount_given = flt(row.amount_given)

    return rows


def get_chart(data):
    totals = {}
    for row in data:
        key = row.get("funding_source") or "Zakat"
        totals[key] = totals.get(key, 0) + flt(row.get("amount_given"))

    labels = list(totals.keys()) or ["Zakat", "Donation", "Panel"]
    values = [totals.get(label, 0) for label in labels]

    return {
        "data": {
            "labels": labels,
            "datasets": [{"name": _("Amount Given"), "values": values}],
        },
        "type": "bar",
        "colors": ["#5e64ff", "#00b0f0", "#ffa00a"],
    }


def get_report_summary(data):
    approved = [r for r in data if r.get("status") == "Approved"]
    pending = [r for r in data if r.get("status") == "Pending Approval"]
    rejected = [r for r in data if r.get("status") == "Rejected"]
    total_given = sum(flt(r.get("amount_given")) for r in data)

    return [
        {"label": _("Total Requests"), "value": len(data), "indicator": "blue", "datatype": "Int"},
        {"label": _("Approved"), "value": len(approved), "indicator": "green", "datatype": "Int"},
        {"label": _("Pending"), "value": len(pending), "indicator": "orange", "datatype": "Int"},
        {"label": _("Rejected"), "value": len(rejected), "indicator": "red", "datatype": "Int"},
        {"label": _("Total Amount Given"), "value": total_given, "indicator": "blue", "datatype": "Currency"},
    ]
