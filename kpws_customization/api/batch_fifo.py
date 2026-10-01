import json
import frappe
from frappe.utils import nowdate


def _to_float(value):
    try:
        return float(value or 0)
    except Exception:
        return 0.0


@frappe.whitelist()
def get_fifo_batches(item_code, warehouse="Pharmacy - KPWS", qty=0):
    """
    Return available batches for an item in FIFO / FEFO order.
    For medicines, expiry date is preferred first, then batch creation.
    """

    qty = _to_float(qty)

    if not item_code:
        return []

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
            "today": nowdate(),
        },
        as_dict=True,
    )

    remaining = qty
    result = []

    for row in batches:
        available_qty = _to_float(row.available_qty)

        pick_qty = available_qty
        if qty > 0:
            pick_qty = min(available_qty, remaining)

        if pick_qty > 0:
            result.append({
                "batch_no": row.batch_no,
                "available_qty": available_qty,
                "pick_qty": pick_qty,
                "expiry_date": row.expiry_date,
                "manufacturing_date": row.manufacturing_date,
            })

            if qty > 0:
                remaining -= pick_qty
                if remaining <= 0:
                    break

    return result


@frappe.whitelist()
def get_first_fifo_batch(item_code, warehouse="Pharmacy - KPWS", qty=1):
    batches = get_fifo_batches(item_code=item_code, warehouse=warehouse, qty=qty)

    if not batches:
        return {}

    return batches[0]
