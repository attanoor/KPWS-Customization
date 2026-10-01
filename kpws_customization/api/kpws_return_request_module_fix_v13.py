from pathlib import Path
import json
import frappe


DOCTYPE = "KPWS Pharmacy Return Request"
DT_SCRUB = "kpws_pharmacy_return_request"
MODULE = "KPWS Customization"


def _ensure_module():
    if not frappe.db.exists("Module Def", MODULE):
        frappe.get_doc({
            "doctype": "Module Def",
            "module_name": MODULE,
            "app_name": "kpws_customization",
            "custom": 0,
        }).insert(ignore_permissions=True)
        frappe.db.commit()


def _controller_py():
    return '''# Copyright (c) 2026, KPWS
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class KPWSPharmacyReturnRequest(Document):
    pass
'''


def _doctype_json():
    return {
        "actions": [],
        "allow_rename": 0,
        "autoname": "format:KPRR-.YYYY.-.#####",
        "creation": "2026-01-01 00:00:00.000000",
        "doctype": "DocType",
        "editable_grid": 1,
        "engine": "InnoDB",
        "field_order": [
            "request_section",
            "original_invoice",
            "billing_group",
            "requested_by",
            "status",
            "amount_section",
            "requested_amount",
            "return_invoice",
            "detail_section",
            "items_json",
            "remarks"
        ],
        "fields": [
            {"fieldname": "request_section", "fieldtype": "Section Break", "label": "Request"},
            {"fieldname": "original_invoice", "fieldtype": "Link", "label": "Original Sales Invoice", "options": "Sales Invoice", "reqd": 1},
            {"fieldname": "billing_group", "fieldtype": "Data", "label": "Billing Group", "read_only": 1},
            {"fieldname": "requested_by", "fieldtype": "Link", "label": "Requested By", "options": "User", "read_only": 1},
            {"default": "Pending Approval", "fieldname": "status", "fieldtype": "Select", "label": "Status", "options": "Pending Approval\\nApproved\\nRejected\\nReturn Created"},
            {"fieldname": "amount_section", "fieldtype": "Section Break", "label": "Amount"},
            {"fieldname": "requested_amount", "fieldtype": "Currency", "label": "Requested Return Amount", "read_only": 1},
            {"fieldname": "return_invoice", "fieldtype": "Link", "label": "Return Sales Invoice", "options": "Sales Invoice", "read_only": 1},
            {"fieldname": "detail_section", "fieldtype": "Section Break", "label": "Details"},
            {"fieldname": "items_json", "fieldtype": "Code", "label": "Requested Items JSON", "options": "JSON", "read_only": 1},
            {"fieldname": "remarks", "fieldtype": "Small Text", "label": "Remarks"}
        ],
        "links": [],
        "modified": "2026-01-01 00:00:00.000000",
        "module": MODULE,
        "name": DOCTYPE,
        "owner": "Administrator",
        "permissions": [
            {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
            {"role": "Accounts Manager", "read": 1, "write": 1, "create": 1},
            {"role": "Accounts User", "read": 1, "write": 1, "create": 1},
            {"role": "KPWS Pharmacy User", "read": 1, "create": 1}
        ],
        "sort_field": "modified",
        "sort_order": "DESC",
        "states": [],
        "track_changes": 1
    }


def _write_controller_files():
    app_path = Path(frappe.get_app_path("kpws_customization"))

    # Standard module path for this app
    paths = [
        app_path / "doctype" / DT_SCRUB,
        app_path / "kpws_customization" / "doctype" / DT_SCRUB,
    ]

    written = []

    for folder in paths:
        folder.mkdir(parents=True, exist_ok=True)

        # __init__.py in doctype parent and doctype folder
        (folder.parent / "__init__.py").touch(exist_ok=True)
        (folder / "__init__.py").touch(exist_ok=True)

        py_file = folder / f"{DT_SCRUB}.py"
        json_file = folder / f"{DT_SCRUB}.json"

        py_file.write_text(_controller_py())
        json_file.write_text(json.dumps(_doctype_json(), indent=2))

        written.append(str(py_file))
        written.append(str(json_file))

    return written


def _ensure_doctype_db():
    _ensure_module()

    if frappe.db.exists("DocType", DOCTYPE):
        dt = frappe.get_doc("DocType", DOCTYPE)
    else:
        dt = frappe.get_doc(_doctype_json())

    # Critical fix:
    # custom=0 makes Frappe load controller from kpws_customization module,
    # instead of trying frappe.core.doctype.kpws_pharmacy_return_request.
    dt.module = MODULE
    dt.custom = 0
    dt.autoname = "format:KPRR-.YYYY.-.#####"
    dt.track_changes = 1

    existing_fields = {df.fieldname for df in dt.fields}

    for field in _doctype_json()["fields"]:
        if field["fieldname"] not in existing_fields:
            dt.append("fields", field)

    # Ensure permissions exist
    if not dt.permissions:
        for perm in _doctype_json()["permissions"]:
            dt.append("permissions", perm)

    dt.flags.ignore_mandatory = True

    if frappe.db.exists("DocType", DOCTYPE):
        dt.save(ignore_permissions=True)
    else:
        dt.insert(ignore_permissions=True)

    frappe.db.commit()

    # Ensure table exists
    try:
        frappe.db.sql(f"SELECT name FROM `tab{DOCTYPE}` LIMIT 1")
    except Exception:
        try:
            from frappe.model.db_schema import updatedb
            updatedb(DOCTYPE)
        except Exception:
            pass

    frappe.clear_cache(doctype=DOCTYPE)
    frappe.clear_cache()


SERVER_OVERRIDE = r'''

# KPWS_RETURN_REQUEST_MODULE_FIX_V13_PATCH

def _kpws_ensure_return_request_doctype():
    if not frappe.db.exists("DocType", "KPWS Pharmacy Return Request"):
        try:
            from kpws_customization.api.kpws_return_request_module_fix_v13 import _ensure_doctype_db
            _ensure_doctype_db()
        except Exception:
            pass

    if frappe.db.exists("DocType", "KPWS Pharmacy Return Request"):
        try:
            frappe.db.set_value(
                "DocType",
                "KPWS Pharmacy Return Request",
                {
                    "module": "KPWS Customization",
                    "custom": 0,
                },
                update_modified=False,
            )
            frappe.clear_cache(doctype="KPWS Pharmacy Return Request")
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

    req = frappe.new_doc("KPWS Pharmacy Return Request")
    req.original_invoice = original.name
    req.billing_group = group
    req.requested_by = frappe.session.user
    req.status = "Pending Approval"
    req.requested_amount = flt(amount, 2)
    req.items_json = frappe.as_json(items, indent=2)
    req.remarks = "Return requires approval because original invoice payment type is Welfare / Panel / Zakat / Donation."

    req.insert(ignore_permissions=True)
    frappe.db.commit()

    return req
'''


def _patch_billing_desk():
    app_path = Path(frappe.get_app_path("kpws_customization"))
    api_file = app_path / "api" / "kpws_pharmacy_billing_desk.py"

    text = api_file.read_text()

    if "KPWS_RETURN_REQUEST_MODULE_FIX_V13_PATCH" not in text:
        api_file.write_text(text + "\n\n" + SERVER_OVERRIDE)
        return True

    return False


@frappe.whitelist()
def install():
    written = _write_controller_files()
    _ensure_doctype_db()
    patched = _patch_billing_desk()

    frappe.clear_cache()
    frappe.db.commit()

    return {
        "ok": True,
        "doctype": DOCTYPE,
        "module": MODULE,
        "files_written": written,
        "billing_desk_patched": patched,
        "message": "KPWS Pharmacy Return Request module/controller fixed."
    }


@frappe.whitelist()
def verify():
    exists = frappe.db.exists("DocType", DOCTYPE)

    data = None
    if exists:
        data = frappe.db.get_value(
            "DocType",
            DOCTYPE,
            ["name", "module", "custom", "autoname"],
            as_dict=True
        )

    return {
        "exists": bool(exists),
        "doctype": data,
    }
