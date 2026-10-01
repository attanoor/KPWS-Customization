import frappe


@frappe.whitelist()
def find(name):
    if not name:
        frappe.throw("PRF name is required")

    rows = frappe.db.sql(
        """
        SELECT
            name,
            docstatus,
            amended_from,
            discount_value,
            custom_kpws_welfare_percentage,
            modified,
            creation
        FROM `tabPatient Registration Form`
        WHERE amended_from=%s OR name=%s
        ORDER BY creation DESC
        """,
        (name, name),
        as_dict=True,
    )

    return rows
