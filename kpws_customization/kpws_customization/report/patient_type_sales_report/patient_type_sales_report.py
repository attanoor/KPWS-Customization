import frappe
from frappe import _
from frappe.utils import flt

PATIENT_TYPES = [
    "Cash",
    "Welfare Zakat",
    "Welfare Donation",
    "Welfare Panel",
    "Panel",
    "Personal Advance",
]


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)
    report_summary = get_report_summary(data)
    data = data + get_summary_rows(data)
    return columns, data, None, chart, report_summary


def get_columns():
    return [
        {"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
        {"label": _("Invoice No"), "fieldname": "name", "fieldtype": "Link", "options": "Sales Invoice", "width": 150},
        {"label": _("Patient"), "fieldname": "patient", "fieldtype": "Link", "options": "Patient", "width": 110},
        {"label": _("Patient Name"), "fieldname": "patient_name", "fieldtype": "Data", "width": 150},
        {"label": _("MR Number"), "fieldname": "custom_kpws_mr_number", "fieldtype": "Data", "width": 100},
        {"label": _("Bill To"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 140},
        {"label": _("Patient Type"), "fieldname": "patient_type", "fieldtype": "Data", "width": 120},
        {"label": _("Funding Source"), "fieldname": "funding_source", "fieldtype": "Data", "width": 110},
        {"label": _("Approved %"), "fieldname": "approved_percentage", "fieldtype": "Percent", "width": 90},
        {"label": _("Issued Amount"), "fieldname": "issued_amount", "fieldtype": "Currency", "width": 120},
        {"label": _("Returned Amount"), "fieldname": "returned_amount", "fieldtype": "Currency", "width": 130},
        {"label": _("Net Amount"), "fieldname": "net_amount", "fieldtype": "Currency", "width": 120},
        {"label": _("Covered Amount"), "fieldname": "covered_amount", "fieldtype": "Currency", "width": 130},
        {"label": _("Patient Cash"), "fieldname": "patient_cash_amount", "fieldtype": "Currency", "width": 110},
        {"label": _("Patient Card"), "fieldname": "patient_card_amount", "fieldtype": "Currency", "width": 110},
        {"label": _("Outstanding"), "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 110, "precision": 0},
        {"label": _("Issued By"), "fieldname": "issued_by", "fieldtype": "Data", "width": 120},
    ]


def get_data(filters):
    conditions = ["si.docstatus = 1"]
    values = {}

    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    if from_date:
        conditions.append("si.posting_date >= %(from_date)s")
        values["from_date"] = from_date
    if to_date:
        conditions.append("si.posting_date <= %(to_date)s")
        values["to_date"] = to_date

    patient_type = filters.get("patient_type")
    if patient_type:
        conditions.append(
            "COALESCE(NULLIF(si.custom_kpws_billing_type_final, ''), NULLIF(si.custom_kpws_patient_billing_group, '')) = %(patient_type)s"
        )
        values["patient_type"] = patient_type

    where_clause = " AND ".join(conditions)

    rows = frappe.db.sql(
        f"""
        SELECT
            si.posting_date AS posting_date,
            si.name AS name,
            si.patient AS patient,
            COALESCE(
                NULLIF(si.patient_name, ''),
                NULLIF(si.walkin_customer_name, ''),
                NULLIF(si.custom_walkin_patient_name, ''),
                'Walk-in Patient'
            ) AS patient_name,
            COALESCE(
                NULLIF(si.custom_kpws_mr_number, ''),
                NULLIF(si.walkin_mr_number, ''),
                NULLIF(si.custom_walkin_mr_number, '')
            ) AS custom_kpws_mr_number,
            si.customer AS customer,
            COALESCE(
                NULLIF(si.custom_kpws_billing_type_final, ''),
                NULLIF(si.custom_kpws_patient_billing_group, '')
            ) AS patient_type,
            si.custom_kpws_funding_source AS funding_source,
            si.custom_kpws_approved_percentage AS approved_percentage,
            si.grand_total AS grand_total,
            si.is_return AS is_return,
            si.custom_kpws_welfare_covered_amount AS covered_amount,
            si.custom_kpws_patient_cash_amount AS patient_cash_amount,
            si.custom_kpws_patient_card_amount AS patient_card_amount,
            si.outstanding_amount AS outstanding_amount,
            sip.pos_cash AS pos_cash,
            sip.pos_card AS pos_card,
            (SELECT full_name FROM `tabUser` WHERE name = si.owner) AS issued_by
        FROM `tabSales Invoice` si
        LEFT JOIN (
            SELECT parent,
                SUM(CASE WHEN mode_of_payment = 'Cash' THEN amount ELSE 0 END) AS pos_cash,
                SUM(CASE WHEN mode_of_payment != 'Cash' THEN amount ELSE 0 END) AS pos_card
            FROM `tabSales Invoice Payment`
            GROUP BY parent
        ) sip ON sip.parent = si.name
        WHERE {where_clause}
        ORDER BY si.posting_date DESC, si.name DESC
        """,
        values,
        as_dict=True,
    )

    for row in rows:
        grand_total = flt(row.grand_total)
        if row.is_return:
            row.issued_amount = 0
            row.returned_amount = abs(grand_total)
            row.net_amount = -abs(grand_total)
        else:
            row.issued_amount = grand_total
            row.returned_amount = 0
            row.net_amount = grand_total
        row.patient_type = row.patient_type or "Cash"

        pos_cash = flt(row.pop("pos_cash"))
        pos_card = flt(row.pop("pos_card"))
        if pos_cash or pos_card:
            row.patient_cash_amount = pos_cash
            row.patient_card_amount = pos_card
        else:
            row.patient_cash_amount = flt(row.patient_cash_amount)
            row.patient_card_amount = flt(row.patient_card_amount)
        row.outstanding_amount = round(flt(row.outstanding_amount))

        del row["grand_total"]
        del row["is_return"]

    return rows


def get_chart(data):
    totals_by_type = {t: 0 for t in PATIENT_TYPES}
    for row in data:
        totals_by_type[row.get("patient_type") or "Cash"] = (
            totals_by_type.get(row.get("patient_type") or "Cash", 0) + flt(row.get("net_amount"))
        )

    labels = [t for t in PATIENT_TYPES if totals_by_type.get(t)]
    values = [totals_by_type[t] for t in labels]

    if not labels:
        labels = PATIENT_TYPES
        values = [0 for _ in labels]

    return {
        "data": {
            "labels": labels,
            "datasets": [{"name": _("Net Sales"), "values": values}],
        },
        "type": "bar",
        "colors": ["#5e64ff", "#00b0f0", "#7cd6fd", "#ffa00a", "#ff5858", "#28a745"],
    }


def get_report_summary(data):
    total_invoices = len({row.get("name") for row in data})
    total_issued = sum(flt(row.get("issued_amount")) for row in data)
    total_returned = sum(flt(row.get("returned_amount")) for row in data)
    total_net = sum(flt(row.get("net_amount")) for row in data)
    total_card = sum(flt(row.get("patient_card_amount")) for row in data)
    cash_received = total_issued - total_card - total_returned

    return [
        {"label": _("Invoices"), "value": total_invoices, "indicator": "blue", "datatype": "Int"},
        {"label": _("Total Sale"), "value": total_issued, "indicator": "green", "datatype": "Currency"},
        {"label": _("Less Direct Payment by Card"), "value": total_card, "indicator": "orange", "datatype": "Currency"},
        {"label": _("Less Sale Return"), "value": total_returned, "indicator": "red", "datatype": "Currency"},
        {"label": _("Cash Received"), "value": cash_received, "indicator": "blue", "datatype": "Currency"},
        {"label": _("Net Sales"), "value": total_net, "indicator": "blue", "datatype": "Currency"},
    ]


def get_summary_rows(data):
    """Extra bold total-rows appended after the data. These render both in the
    on-screen report grid and in the report's Print view, since both read from
    the same `data` returned by execute() - Frappe's report_summary cards are
    on-screen only and are not included in the print/PDF output."""
    total_issued = sum(flt(row.get("issued_amount")) for row in data)
    total_returned = sum(flt(row.get("returned_amount")) for row in data)
    total_card = sum(flt(row.get("patient_card_amount")) for row in data)
    cash_received = total_issued - total_card - total_returned

    def summary_row(label, amount):
        return {"patient_name": label, "net_amount": amount, "bold": 1}

    return [
        summary_row(_("Total Sale"), total_issued),
        summary_row(_("Less Direct Payment by Card"), total_card),
        summary_row(_("Less Sale Return"), total_returned),
        summary_row(_("Cash Received"), cash_received),
    ]
