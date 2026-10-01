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

    page.save(ignore_permissions=True)

    frappe.clear_cache()
    frappe.db.commit()

    return {
        "ok": True,
        "page": page.name,
        "page_name": page.page_name,
        "module": page.module,
        "standard": page.get("standard"),
        "message": "Page asset path fixed."
    }
