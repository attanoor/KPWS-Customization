import frappe
from frappe import _


@frappe.whitelist()
def get_pharmacy_available_items(doctype, txt, searchfield, start, page_len, filters):
    """
    Link query for Sales Invoice Item.item_code.
    Shows only items having actual stock > 0 in Pharmacy - KPWS.
    """

    warehouse = None

    if isinstance(filters, dict):
        warehouse = filters.get("warehouse")

    warehouse = warehouse or "Pharmacy - KPWS"

    txt = "%%%s%%" % (txt or "")
    start = int(start or 0)
    page_len = int(page_len or 20)

    return frappe.db.sql(
        """
        SELECT DISTINCT
            item.name,
            item.item_name,
            item.stock_uom,
            bin.actual_qty
        FROM `tabBin` bin
        INNER JOIN `tabItem` item
            ON item.name = bin.item_code
        WHERE
            bin.warehouse = %(warehouse)s
            AND bin.actual_qty > 0
            AND IFNULL(item.disabled, 0) = 0
            AND IFNULL(item.has_variants, 0) = 0
            AND (
                item.name LIKE %(txt)s
                OR item.item_name LIKE %(txt)s
                OR item.item_code LIKE %(txt)s
                OR IFNULL(item.description, '') LIKE %(txt)s
            )
        ORDER BY
            item.item_name ASC,
            item.name ASC
        LIMIT %(start)s, %(page_len)s
        """,
        {
            "warehouse": warehouse,
            "txt": txt,
            "start": start,
            "page_len": page_len,
        },
    )
