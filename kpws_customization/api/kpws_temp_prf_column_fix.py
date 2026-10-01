import frappe

DT = "Patient Registration Form"
TABLE = "tabPatient Registration Form"

COLUMNS = {
    "custom_patient": "varchar(140)",
    "custom_mr_number": "varchar(140)",
    "custom_patient_customer": "varchar(140)",
    "custom_billing_type": "varchar(140)",
    "custom_panel_customer": "varchar(140)",
    "custom_kpws_welfare_type": "varchar(140)",
    "custom_kpws_welfare_percentage": "decimal(21,9)",
    "custom_kpws_assigned_panel_customer": "varchar(140)",
    "custom_kpws_admin_notes": "text",
}

def column_exists(fieldname):
    rows = frappe.db.sql(
        """
        SELECT COUNT(*) AS total
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = %s
        AND COLUMN_NAME = %s
        """,
        (TABLE, fieldname),
        as_dict=True,
    )
    return int(rows[0].total or 0) > 0

def run():
    print("DB:", frappe.conf.db_name)
    print("Fixing table:", TABLE)

    for fieldname, sql_type in COLUMNS.items():
        if column_exists(fieldname):
            print("Already exists:", fieldname)
        else:
            print("Adding:", fieldname)
            frappe.db.sql(
                f"ALTER TABLE `{TABLE}` ADD COLUMN `{fieldname}` {sql_type}"
            )

    # Make CNIC non-mandatory so welfare registration can open first.
    frappe.db.sql(
        """
        UPDATE `tabCustom Field`
        SET reqd = 0
        WHERE dt = %s
        AND fieldname IN ('cnic', 'custom_cnic')
        """,
        DT,
    )

    frappe.db.sql(
        """
        UPDATE `tabProperty Setter`
        SET value = '0'
        WHERE doc_type = %s
        AND field_name IN ('cnic', 'custom_cnic')
        AND property = 'reqd'
        """,
        DT,
    )

    frappe.db.commit()
    frappe.clear_cache(doctype=DT)

    print("")
    print("Verification:")
    for fieldname in COLUMNS:
        print(fieldname, "=", column_exists(fieldname))

    print("")
    print("DONE")
