from pathlib import Path
import frappe
from frappe.utils import now


PAGE_NAME = "kpws-pharmacy-billing"
PAGE_TITLE = "KPWS Pharmacy Billing"


def _get_existing_columns():
    rows = frappe.db.sql("SHOW COLUMNS FROM `tabPage`", as_dict=True)
    return {row["Field"]: row for row in rows}


def _get_module():
    if frappe.db.exists("Module Def", "KPWS Customization"):
        return "KPWS Customization"

    module = frappe.db.get_value(
        "Module Def",
        {"app_name": "kpws_customization"},
        "name"
    )

    return module or "Custom"


def _get_script():
    app_path = Path(frappe.get_app_path("kpws_customization"))
    js_file = app_path / "page" / "kpws_pharmacy_billing" / "kpws_pharmacy_billing.js"

    if not js_file.exists():
        frappe.throw(f"JS file missing: {js_file}")

    return js_file.read_text()


@frappe.whitelist()
def run():
    columns = _get_existing_columns()
    script = _get_script()
    module = _get_module()

    # Remove any broken/partial entries first
    frappe.db.sql(
        """
        DELETE FROM `tabPage`
        WHERE name=%s OR page_name=%s OR title=%s
        """,
        (PAGE_NAME, PAGE_NAME, PAGE_TITLE),
    )

    data = {
        "name": PAGE_NAME,
        "creation": now(),
        "modified": now(),
        "modified_by": "Administrator",
        "owner": "Administrator",
        "docstatus": 0,
        "idx": 0,
        "page_name": PAGE_NAME,
        "title": PAGE_TITLE,
        "module": module,
        "standard": "No",
        "script": script,
        "content": "",
        "icon": "octicon octicon-credit-card",
    }

    # Keep only columns that really exist in this Frappe version
    data = {k: v for k, v in data.items() if k in columns}

    insert_columns = list(data.keys())
    placeholders = ["%s"] * len(insert_columns)

    frappe.db.sql(
        f"""
        INSERT INTO `tabPage`
        ({", ".join("`" + c + "`" for c in insert_columns)})
        VALUES ({", ".join(placeholders)})
        """,
        [data[c] for c in insert_columns],
    )

    frappe.db.commit()
    frappe.clear_cache()

    result = frappe.db.sql(
        """
        SELECT name, page_name, title, module, standard
        FROM `tabPage`
        WHERE name=%s OR page_name=%s
        """,
        (PAGE_NAME, PAGE_NAME),
        as_dict=True,
    )

    return {
        "ok": True,
        "inserted_rows": result,
        "columns_used": insert_columns,
        "route": "/app/kpws-pharmacy-billing",
    }


@frappe.whitelist()
def verify():
    return frappe.db.sql(
        """
        SELECT name, page_name, title, module, standard, modified
        FROM `tabPage`
        WHERE name=%s OR page_name=%s OR title=%s
        """,
        (PAGE_NAME, PAGE_NAME, PAGE_TITLE),
        as_dict=True,
    )


@frappe.whitelist()
def inspect_page_table():
    return {
        "page_table_exists": frappe.db.sql("SHOW TABLES LIKE 'tabPage'"),
        "columns": list(_get_existing_columns().keys()),
        "matching_pages": frappe.db.sql(
            """
            SELECT name, page_name, title, module, standard
            FROM `tabPage`
            WHERE name LIKE %s OR page_name LIKE %s OR title LIKE %s
            """,
            ("%pharmacy%", "%pharmacy%", "%Pharmacy%"),
            as_dict=True,
        )
    }
