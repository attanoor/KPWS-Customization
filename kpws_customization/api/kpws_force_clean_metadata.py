import frappe

TARGET_DOCTYPES = ["Patient", "Patient Registration Form", "Customer"]


def disable_related_client_scripts():
    scripts = frappe.get_all(
        "Client Script",
        fields=["name", "dt", "enabled"],
        limit_page_length=10000,
    )

    for s in scripts:
        name = s.name or ""
        dt = s.dt or ""

        if dt in TARGET_DOCTYPES or name.startswith("KPWS"):
            frappe.db.set_value("Client Script", s.name, "enabled", 0)
            print("Disabled Client Script:", s.name)


def delete_property_setters():
    rows = frappe.get_all(
        "Property Setter",
        filters={"doc_type": ["in", TARGET_DOCTYPES]},
        fields=["name", "doc_type", "field_name", "property"],
        limit_page_length=10000,
    )

    for r in rows:
        try:
            frappe.delete_doc("Property Setter", r.name, force=1, ignore_permissions=True)
            print("Deleted Property Setter:", r.doc_type, r.field_name, r.property, r.name)
        except Exception as e:
            print("Could not delete Property Setter via ORM, deleting SQL:", r.name, e)
            frappe.db.sql("DELETE FROM `tabProperty Setter` WHERE name=%s", r.name)


def delete_custom_fields():
    rows = frappe.get_all(
        "Custom Field",
        filters={"dt": ["in", TARGET_DOCTYPES]},
        fields=["name", "dt", "fieldname", "label"],
        order_by="dt asc, idx asc",
        limit_page_length=10000,
    )

    print("Custom Fields found:", len(rows))

    for r in rows:
        try:
            frappe.delete_doc("Custom Field", r.name, force=1, ignore_permissions=True)
            print("Deleted Custom Field:", r.dt, r.fieldname, r.name)
        except Exception as e:
            print("Could not delete Custom Field via ORM, deleting SQL:", r.name, e)
            frappe.db.sql("DELETE FROM `tabCustom Field` WHERE name=%s", r.name)


def cleanup_hooks_and_cached_client_scripts():
    # Does not change ERPNext core. Only clears Frappe cache.
    for dt in TARGET_DOCTYPES:
        frappe.clear_cache(doctype=dt)

    frappe.clear_cache()


def run():
    print("Starting force cleanup for:", ", ".join(TARGET_DOCTYPES))

    disable_related_client_scripts()
    delete_property_setters()
    delete_custom_fields()

    frappe.db.commit()

    cleanup_hooks_and_cached_client_scripts()

    remaining_cf = frappe.db.count("Custom Field", {"dt": ["in", TARGET_DOCTYPES]})
    remaining_ps = frappe.db.count("Property Setter", {"doc_type": ["in", TARGET_DOCTYPES]})

    print("Remaining Custom Fields:", remaining_cf)
    print("Remaining Property Setters:", remaining_ps)

    if remaining_cf:
        frappe.throw("Custom Fields still remain. Check list manually.")

    print("FORCE CLEAN COMPLETED.")
    return {
        "remaining_custom_fields": remaining_cf,
        "remaining_property_setters": remaining_ps,
    }
