import frappe


@frappe.whitelist()
def run():
    page_name = "kpws-pharmacy-billing"

    if not frappe.db.exists("Page", page_name):
        frappe.throw("Page not found: kpws-pharmacy-billing")

    page = frappe.get_doc("Page", page_name)
    page.page_name = page_name
    page.title = "KPWS Pharmacy Billing"
    page.module = "KPWS Customization"

    if page.meta.has_field("standard"):
        page.standard = "Yes"

    if page.meta.has_field("script"):
        page.script = ""

    if page.meta.has_field("content"):
        page.content = ""

    page.save(ignore_permissions=True)

    frappe.clear_cache()
    frappe.db.commit()

    return {
        "ok": True,
        "page": page.name,
        "page_name": page.page_name,
        "standard": page.get("standard"),
        "module": page.module,
        "message": "Pharmacy page now loads full POS JS layout."
    }
