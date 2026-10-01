import frappe


@frappe.whitelist()
def get_panel_customers(doctype, txt, searchfield, start, page_len, filters):
    txt = "%%%s%%" % (txt or "")
    start = int(start or 0)
    page_len = int(page_len or 20)

    return frappe.db.sql(
        """
        SELECT
            name,
            customer_name,
            customer_group
        FROM `tabCustomer`
        WHERE
            IFNULL(custom_is_panel, 0) = 1
            AND IFNULL(disabled, 0) = 0
            AND (
                name LIKE %(txt)s
                OR customer_name LIKE %(txt)s
            )
        ORDER BY customer_name ASC
        LIMIT %(start)s, %(page_len)s
        """,
        {
            "txt": txt,
            "start": start,
            "page_len": page_len,
        },
    )
