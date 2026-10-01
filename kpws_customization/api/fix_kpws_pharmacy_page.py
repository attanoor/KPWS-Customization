from pathlib import Path
import frappe


PAGE_NAME = "kpws-pharmacy-billing"
PAGE_TITLE = "KPWS Pharmacy Billing"


@frappe.whitelist()
def run():
    app_path = Path(frappe.get_app_path("kpws_customization"))
    js_file = app_path / "page" / "kpws_pharmacy_billing" / "kpws_pharmacy_billing.js"

    if not js_file.exists():
        frappe.throw(f"Page JS file not found: {js_file}")

    script = js_file.read_text()

    module = "KPWS Customization"
    if not frappe.db.exists("Module Def", module):
        module = frappe.db.get_value("Module Def", {"app_name": "kpws_customization"}, "name") or "Custom"

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

    # Important: make it DB/custom page so getpage does not depend on filesystem page JSON.
    if page.meta.has_field("standard"):
        page.standard = "No"

    if page.meta.has_field("script"):
        page.script = script

    if page.meta.has_field("content"):
        page.content = ""

    try:
        page.roles = []
        for role in ("System Manager", "Accounts Manager", "Accounts User", "Sales User", "KPWS Pharmacy User"):
            if frappe.db.exists("Role", role):
                page.append("roles", {"role": role})
    except Exception:
        pass

    page.save(ignore_permissions=True)

    frappe.clear_cache()
    frappe.db.commit()

    return {
        "ok": True,
        "page_name": page.page_name,
        "page_title": page.title,
        "standard": page.get("standard"),
        "module": page.module,
        "route": "/app/kpws-pharmacy-billing",
        "message": "KPWS Pharmacy Billing page registered successfully."
    }
