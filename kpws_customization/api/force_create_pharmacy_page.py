from pathlib import Path
import frappe
from frappe.utils import now


PAGE_NAME = "kpws-pharmacy-billing"
PAGE_TITLE = "KPWS Pharmacy Billing"


def _safe_module():
    if frappe.db.exists("Module Def", "KPWS Customization"):
        return "KPWS Customization"

    module = frappe.db.get_value(
        "Module Def",
        {"app_name": "kpws_customization"},
        "name"
    )

    return module or "Custom"


def _standard_value():
    try:
        df = frappe.get_meta("Page").get_field("standard")
        if df and df.fieldtype == "Check":
            return 0
    except Exception:
        pass

    return "No"


def _get_js():
    app_path = Path(frappe.get_app_path("kpws_customization"))
    js_file = app_path / "page" / "kpws_pharmacy_billing" / "kpws_pharmacy_billing.js"

    if not js_file.exists():
        frappe.throw(f"Missing page JS file: {js_file}")

    return js_file.read_text()


def _ensure_role():
    if not frappe.db.exists("Role", "KPWS Pharmacy User"):
        frappe.get_doc({
            "doctype": "Role",
            "role_name": "KPWS Pharmacy User",
            "desk_access": 1,
        }).insert(ignore_permissions=True)


def _upsert_page_with_orm(script):
    module = _safe_module()

    existing = frappe.db.exists("Page", PAGE_NAME)

    if existing:
        page = frappe.get_doc("Page", existing)
    else:
        page = frappe.new_doc("Page")
        page.name = PAGE_NAME
        page.page_name = PAGE_NAME

    page.page_name = PAGE_NAME
    page.title = PAGE_TITLE
    page.module = module

    if page.meta.has_field("standard"):
        page.standard = _standard_value()

    if page.meta.has_field("script"):
        page.script = script

    if page.meta.has_field("content"):
        page.content = ""

    if page.meta.has_field("icon"):
        page.icon = "octicon octicon-credit-card"

    try:
        page.roles = []
        for role in [
            "System Manager",
            "Accounts Manager",
            "Accounts User",
            "Sales User",
            "Sales Manager",
            "KPWS Pharmacy User",
        ]:
            if frappe.db.exists("Role", role):
                page.append("roles", {"role": role})
    except Exception:
        pass

    page.flags.ignore_mandatory = True

    if existing:
        page.save(ignore_permissions=True)
    else:
        page.insert(ignore_permissions=True)

    return page


def _direct_sql_fallback(script):
    module = _safe_module()

    data = {
        "name": PAGE_NAME,
        "creation": now(),
        "modified": now(),
        "modified_by": frappe.session.user,
        "owner": frappe.session.user,
        "docstatus": 0,
        "idx": 0,
    }

    optional = {
        "page_name": PAGE_NAME,
        "title": PAGE_TITLE,
        "module": module,
        "standard": _standard_value(),
        "script": script,
        "content": "",
        "icon": "octicon octicon-credit-card",
    }

    for fieldname, value in optional.items():
        try:
            if frappe.db.has_column("Page", fieldname):
                data[fieldname] = value
        except Exception:
            pass

    if frappe.db.exists("Page", PAGE_NAME):
        set_parts = []
        values = []

        for key, value in data.items():
            if key == "name":
                continue
            set_parts.append(f"`{key}`=%s")
            values.append(value)

        values.append(PAGE_NAME)

        frappe.db.sql(
            f"UPDATE `tabPage` SET {', '.join(set_parts)} WHERE name=%s",
            values,
        )
    else:
        columns = list(data.keys())
        placeholders = ["%s"] * len(columns)

        frappe.db.sql(
            f"""
            INSERT INTO `tabPage` ({', '.join('`' + c + '`' for c in columns)})
            VALUES ({', '.join(placeholders)})
            """,
            [data[c] for c in columns],
        )


@frappe.whitelist()
def run():
    _ensure_role()

    # Also try to install settings/API dependencies if available.
    try:
        from kpws_customization.api.kpws_pharmacy_billing_desk import install as install_desk
        install_desk()
    except Exception:
        pass

    script = _get_js()

    try:
        page = _upsert_page_with_orm(script)
    except Exception:
        _direct_sql_fallback(script)
        page = frappe.get_doc("Page", PAGE_NAME)

    frappe.clear_cache()
    frappe.db.commit()

    return {
        "ok": True,
        "created": bool(frappe.db.exists("Page", PAGE_NAME)),
        "page": frappe.db.get_value(
            "Page",
            PAGE_NAME,
            ["name", "page_name", "title", "module", "standard"],
            as_dict=True,
        ),
        "route": "/app/kpws-pharmacy-billing",
    }


@frappe.whitelist()
def verify():
    return frappe.get_all(
        "Page",
        filters={
            "page_name": PAGE_NAME
        },
        fields=[
            "name",
            "page_name",
            "title",
            "module",
            "standard",
            "modified",
        ],
        limit_page_length=10,
    )
