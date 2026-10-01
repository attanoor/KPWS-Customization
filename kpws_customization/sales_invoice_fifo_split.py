import frappe

PHARMACY_WAREHOUSE = "Pharmacy - KPWS"


def flt(value):
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def get_fifo_batches(item_code, warehouse):
    return frappe.db.sql(
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
                OR b.expiry_date >= CURDATE()
            )
        GROUP BY
            sle.batch_no,
            b.expiry_date,
            b.manufacturing_date,
            b.creation
        HAVING SUM(sle.actual_qty) > 0
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
        },
        as_dict=True,
    )


def copy_item_row(doc, source_row, qty, batch_no):
    new_row = doc.append("items", {})

    skip = {
        "name", "owner", "creation", "modified", "modified_by",
        "parent", "parentfield", "parenttype", "idx", "docstatus"
    }

    for fieldname, value in source_row.as_dict().items():
        if fieldname in skip:
            continue

        try:
            new_row.set(fieldname, value)
        except Exception:
            pass

    qty = flt(qty)
    rate = flt(source_row.get("rate"))
    conversion_factor = flt(source_row.get("conversion_factor")) or 1

    new_row.qty = qty
    new_row.stock_qty = qty * conversion_factor
    new_row.batch_no = batch_no
    new_row.warehouse = source_row.get("warehouse") or PHARMACY_WAREHOUSE

    for amount_field in ["amount", "base_amount", "net_amount", "base_net_amount"]:
        if new_row.meta.get_field(amount_field):
            new_row.set(amount_field, qty * rate)

    return new_row


def allocate_row(row, used_by_batch):
    item_code = row.get("item_code")
    qty = flt(row.get("qty"))
    warehouse = row.get("warehouse") or PHARMACY_WAREHOUSE

    if not item_code or qty <= 0:
        return [(row, qty, row.get("batch_no"))]

    if warehouse != PHARMACY_WAREHOUSE:
        return [(row, qty, row.get("batch_no"))]

    has_batch_no = frappe.db.get_value("Item", item_code, "has_batch_no")

    if not has_batch_no:
        return [(row, qty, row.get("batch_no"))]

    batches = get_fifo_batches(item_code, warehouse)

    if not batches:
        frappe.throw(
            "No available batch found for item "
            + str(item_code)
            + " in "
            + str(warehouse)
        )

    key = item_code + "||" + warehouse

    if key not in used_by_batch:
        used_by_batch[key] = {}

    remaining = qty
    row_plan = []
    total_available = 0

    for batch in batches:
        batch_no = batch.get("batch_no")
        available_qty = flt(batch.get("available_qty"))
        already_used = flt(used_by_batch[key].get(batch_no))
        usable_qty = available_qty - already_used

        total_available += available_qty

        if usable_qty <= 0:
            continue

        if remaining <= 0:
            break

        pick_qty = min(usable_qty, remaining)

        if pick_qty > 0:
            row_plan.append((row, pick_qty, batch_no))
            used_by_batch[key][batch_no] = already_used + pick_qty
            remaining = remaining - pick_qty

    if remaining > 0:
        frappe.throw(
            "Item "
            + str(item_code)
            + " has only "
            + str(total_available)
            + " qty available in "
            + str(warehouse)
            + ", but invoice requires "
            + str(qty)
        )

    return row_plan


def apply_fifo_batch_split(doc, method=None):
    if doc.get("is_return"):
        return

    if not doc.get("items"):
        return

    original_rows = list(doc.get("items") or [])
    used_by_batch = {}
    final_plan = []
    split_needed = False

    for row in original_rows:
        if not row.get("warehouse"):
            row.warehouse = PHARMACY_WAREHOUSE

        row_plan = allocate_row(row, used_by_batch)

        if len(row_plan) > 1:
            split_needed = True

        if len(row_plan) == 1:
            planned_row, planned_qty, planned_batch = row_plan[0]

            if planned_batch and row.get("batch_no") != planned_batch:
                split_needed = True

            if flt(row.get("qty")) != flt(planned_qty):
                split_needed = True

        final_plan.append(row_plan)

    if not split_needed:
        for row_plan in final_plan:
            if len(row_plan) == 1:
                row, qty, batch_no = row_plan[0]
                if batch_no:
                    row.batch_no = batch_no
        return

    doc.set("items", [])

    for row_plan in final_plan:
        for source_row, qty, batch_no in row_plan:
            copy_item_row(doc, source_row, qty, batch_no)
