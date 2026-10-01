import json
from pathlib import Path
import frappe


DOCTYPE = "KPWS Pharmacy Return Request"
PATCH_MARKER = "KPWS_RETURN_REQUEST_TABLE_FIX_V14_PATCH"


FIELDS = [
    {
        "fieldname": "request_section",
        "label": "Request",
        "fieldtype": "Section Break",
    },
    {
        "fieldname": "original_invoice",
        "label": "Original Sales Invoice",
        "fieldtype": "Link",
        "options": "Sales Invoice",
        "reqd": 1,
    },
    {
        "fieldname": "billing_group",
        "label": "Billing Group",
        "fieldtype": "Data",
        "read_only": 1,
    },
    {
        "fieldname": "requested_by",
        "label": "Requested By",
        "fieldtype": "Link",
        "options": "User",
        "read_only": 1,
    },
    {
        "fieldname": "status",
        "label": "Status",
        "fieldtype": "Select",
        "options": "Pending Approval\nApproved\nRejected\nReturn Created",
        "default": "Pending Approval",
    },
    {
        "fieldname": "amount_section",
        "label": "Amount",
        "fieldtype": "Section Break",
    },
    {
        "fieldname": "requested_amount",
        "label": "Requested Return Amount",
        "fieldtype": "Currency",
        "read_only": 1,
    },
    {
        "fieldname": "return_invoice",
        "label": "Return Sales Invoice",
        "fieldtype": "Link",
        "options": "Sales Invoice",
        "read_only": 1,
    },
    {
        "fieldname": "detail_section",
        "label": "Details",
        "fieldtype": "Section Break",
    },
    {
        "fieldname": "items_json",
        "label": "Requested Items JSON",
        "fieldtype": "Code",
        "options": "JSON",
        "read_only": 1,
    },
    {
        "fieldname": "remarks",
        "label": "Remarks",
        "fieldtype": "Small Text",
    },
]


def _table_exists(table):
    return bool(frappe.db.sql("SHOW TABLES LIKE %s", table))


def _ensure_role(role):
    if not frappe.db.exists("Role", role):
        frappe.get_doc({
            "doctype": "Role",
            "role_name": role,
            "desk_access": 1,
        }).insert(ignore_permissions=True)


def _ensure_custom_doctype():
    # Keep this as custom=1 to avoid missing controller import errors.
    if frappe.db.exists("DocType", DOCTYPE):
        dt = frappe.get_doc("DocType", DOCTYPE)
    else:
        dt = frappe.new_doc("DocType")
        dt.name = DOCTYPE

    dt.module = "Custom"
    dt.custom = 1
    dt.issingle = 0
    dt.istable = 0
    dt.editable_grid = 1
    dt.autoname = "format:KPRR-{YYYY}-{#####}"
    dt.track_changes = 1

    existing = {df.fieldname for df in dt.fields}

    for field in FIELDS:
        if field["fieldname"] not in existing:
            dt.append("fields", field)

    if not dt.permissions:
        for role in ["System Manager", "Accounts Manager", "Accounts User", "KPWS Pharmacy User"]:
            if frappe.db.exists("Role", role):
                dt.append("permissions", {
                    "role": role,
                    "read": 1,
                    "write": 1 if role != "KPWS Pharmacy User" else 0,
                    "create": 1,
                    "delete": 1 if role == "System Manager" else 0,
                })

    dt.flags.ignore_mandatory = True

    if frappe.db.exists("DocType", DOCTYPE):
        dt.save(ignore_permissions=True)
    else:
        dt.insert(ignore_permissions=True)

    frappe.db.commit()
    frappe.clear_cache(doctype=DOCTYPE)


def _create_table_raw():
    table = f"tab{DOCTYPE}"

    if _table_exists(table):
        return False

    frappe.db.sql(f"""
        CREATE TABLE IF NOT EXISTS `{table}` (
            `name` varchar(140) NOT NULL PRIMARY KEY,
            `creation` datetime(6),
            `modified` datetime(6),
            `modified_by` varchar(140),
            `owner` varchar(140),
            `docstatus` int(1) NOT NULL DEFAULT 0,
            `idx` int(8) NOT NULL DEFAULT 0,

            `original_invoice` varchar(140),
            `billing_group` varchar(140),
            `requested_by` varchar(140),
            `status` varchar(140),
            `requested_amount` decimal(21,9) NOT NULL DEFAULT 0,
            `return_invoice` varchar(140),
            `items_json` longtext,
            `remarks` text,

            INDEX `modified` (`modified`),
            INDEX `original_invoice` (`original_invoice`),
            INDEX `status` (`status`)
        ) ENGINE=InnoDB ROW_FORMAT=DYNAMIC CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    frappe.db.commit()
    return True


def ensure_return_request_doctype_and_table():
    _ensure_role("KPWS Pharmacy User")
    _ensure_custom_doctype()

    # Try Frappe schema builder first.
    try:
        from frappe.model.db_schema import updatedb
        updatedb(DOCTYPE)
        frappe.db.commit()
    except Exception:
        pass

    # Raw fallback if table still missing.
    created_raw = _create_table_raw()

    frappe.clear_cache(doctype=DOCTYPE)
    frappe.clear_cache()

    return {
        "doctype_exists": bool(frappe.db.exists("DocType", DOCTYPE)),
        "table_exists": _table_exists(f"tab{DOCTYPE}"),
        "raw_table_created": created_raw,
    }


SERVER_PATCH = r'''

# KPWS_RETURN_REQUEST_TABLE_FIX_V14_PATCH

def _kpws_ensure_return_request_doctype():
    try:
        from kpws_customization.api.kpws_return_request_table_fix_v14 import ensure_return_request_doctype_and_table
        ensure_return_request_doctype_and_table()
    except Exception:
        pass


def _kpws_create_approval_request_if_needed(original, requested_map, returnable_by_row, group):
    if group not in ("Welfare", "Panel"):
        return None

    _kpws_ensure_return_request_doctype()

    amount = 0
    items = []

    for source_item_name, qty in requested_map.items():
        row = returnable_by_row.get(source_item_name)
        if not row:
            continue

        line_amount = flt(qty) * flt(row.get("rate") or 0)
        amount += line_amount

        items.append({
            "source_item_name": source_item_name,
            "item_code": row.get("item_code"),
            "item_name": row.get("item_name"),
            "return_qty": flt(qty),
            "rate": flt(row.get("rate") or 0),
            "amount": flt(line_amount, 2),
        })

    req = frappe.get_doc({
        "doctype": "KPWS Pharmacy Return Request",
        "original_invoice": original.name,
        "billing_group": group,
        "requested_by": frappe.session.user,
        "status": "Pending Approval",
        "requested_amount": flt(amount, 2),
        "items_json": frappe.as_json(items, indent=2),
        "remarks": "Return requires approval because original invoice payment type is Welfare / Panel / Zakat / Donation."
    })

    req.insert(ignore_permissions=True)
    frappe.db.commit()

    return req
'''


def _patch_billing_desk():
    app_path = Path(frappe.get_app_path("kpws_customization"))
    api_file = app_path / "api" / "kpws_pharmacy_billing_desk.py"

    text = api_file.read_text()

    if PATCH_MARKER not in text:
        api_file.write_text(text + "\n\n" + SERVER_PATCH)
        return True

    return False


@frappe.whitelist()
def install():
    status = ensure_return_request_doctype_and_table()
    patched = _patch_billing_desk()

    frappe.clear_cache()
    frappe.db.commit()

    return {
        "ok": True,
        "status": status,
        "billing_desk_patched": patched,
        "message": "KPWS Pharmacy Return Request DocType/table fixed."
    }


@frappe.whitelist()
def verify():
    table = f"tab{DOCTYPE}"

    out = {
        "doctype_exists": bool(frappe.db.exists("DocType", DOCTYPE)),
        "table_exists": _table_exists(table),
        "doctype": None,
        "rows": [],
    }

    if out["doctype_exists"]:
        out["doctype"] = frappe.db.get_value(
            "DocType",
            DOCTYPE,
            ["name", "module", "custom", "autoname"],
            as_dict=True,
        )

    if out["table_exists"]:
        out["rows"] = frappe.db.sql(
            f"""
            SELECT name, original_invoice, billing_group, status, requested_amount, requested_by, creation
            FROM `{table}`
            ORDER BY creation DESC
            LIMIT 5
            """,
            as_dict=True,
        )

    return out
