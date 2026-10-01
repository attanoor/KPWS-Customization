import frappe
from frappe.utils import nowdate


def flt(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


@frappe.whitelist()
def get_pharmacy_stock_info(item_code, warehouse="Pharmacy - KPWS"):
    if not item_code:
        return {
            "available_qty": 0,
            "fifo_batch": "",
            "fifo_batch_qty": 0,
            "batch_summary": ""
        }

    available_qty = frappe.db.get_value(
        "Bin",
        {
            "item_code": item_code,
            "warehouse": warehouse
        },
        "actual_qty"
    ) or 0

    batches = frappe.db.sql(
        """
        SELECT
            sle.batch_no,
            SUM(sle.actual_qty) AS available_qty,
            b.expiry_date,
            b.manufacturing_date,
            b.creation
        FROM `tabStock Ledger Entry` sle
        INNER JOIN `tabBatch` b
            ON b.name = sle.batch_no
        WHERE
            sle.item_code = %(item_code)s
            AND sle.warehouse = %(warehouse)s
            AND IFNULL(sle.batch_no, '') != ''
            AND IFNULL(sle.is_cancelled, 0) = 0
            AND IFNULL(b.disabled, 0) = 0
            AND (
                b.expiry_date IS NULL
                OR b.expiry_date = ''
                OR b.expiry_date >= %(today)s
            )
        GROUP BY
            sle.batch_no,
            b.expiry_date,
            b.manufacturing_date,
            b.creation
        HAVING
            SUM(sle.actual_qty) > 0
        ORDER BY
            CASE WHEN b.expiry_date IS NULL OR b.expiry_date = '' THEN 1 ELSE 0 END ASC,
            b.expiry_date ASC,
            b.manufacturing_date ASC,
            b.creation ASC,
            sle.batch_no ASC
        """,
        {
            "item_code": item_code,
            "warehouse": warehouse,
            "today": nowdate()
        },
        as_dict=True
    )

    fifo_batch = ""
    fifo_batch_qty = 0
    batch_lines = []

    for idx, b in enumerate(batches):
        qty = flt(b.available_qty)

        if idx == 0:
            fifo_batch = b.batch_no
            fifo_batch_qty = qty

        expiry = b.expiry_date or "No Expiry"
        batch_lines.append(
            "{0}: {1} qty, Expiry: {2}".format(
                b.batch_no,
                qty,
                expiry
            )
        )

    return {
        "available_qty": flt(available_qty),
        "fifo_batch": fifo_batch,
        "fifo_batch_qty": fifo_batch_qty,
        "batch_summary": "\n".join(batch_lines)
    }
