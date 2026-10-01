import os
import json
import frappe

TARGET_DOCTYPES = ["Patient", "Patient Registration Form", "Customer"]

CLIENT_SCRIPT_NAME_PATTERNS = [
    "KPWS",
    "Patient",
    "PRF",
    "Welfare",
    "Panel",
]


def _rows_to_json(path, rows):
    with open(path, "w") as f:
        json.dump(rows, f, indent=2, default=str)


def _get_custom_fields():
    return frappe.get_all(
        "Custom Field",
        filters={"dt": ["in", TARGET_DOCTYPES]},
        fields=[
            "name", "dt", "fieldname", "label", "fieldtype",
            "options", "idx", "hidden", "read_only", "reqd"
        ],
        order_by="dt asc, idx asc",
        limit_page_length=10000,
    )


def _get_property_setters():
    return frappe.get_all(
        "Property Setter",
        filters={"doc_type": ["in", TARGET_DOCTYPES]},
        fields=[
            "name", "doctype_or_field", "doc_type", "field_name",
            "property", "property_type", "value"
        ],
        order_by="doc_type asc, field_name asc, property asc",
        limit_page_length=10000,
    )


def _get_client_scripts():
    scripts = frappe.get_all(
        "Client Script",
        fields=["name", "dt", "enabled", "view"],
        order_by="dt asc, name asc",
        limit_page_length=10000,
    )

    result = []

    for s in scripts:
        name = s.name or ""
        dt = s.dt or ""

        if dt in TARGET_DOCTYPES:
            result.append(s)
            continue

        # Catch KPWS patient/welfare/panel scripts even if dt is not clean.
        text = f"{name} {dt}"
        if "KPWS" in text and any(p in text for p in CLIENT_SCRIPT_NAME_PATTERNS):
            result.append(s)

    return result


def _disable_client_scripts(rows):
    for r in rows:
        if frappe.db.exists("Client Script", r.name):
            frappe.db.set_value("Client Script", r.name, "enabled", 0)
            print("Disabled Client Script:", r.name)


def _delete_property_setters(rows):
    for r in rows:
        if frappe.db.exists("Property Setter", r.name):
            frappe.delete_doc("Property Setter", r.name, force=1, ignore_permissions=True)
            print("Deleted Property Setter:", r.name)


def _delete_custom_fields(rows):
    for r in rows:
        if frappe.db.exists("Custom Field", r.name):
            frappe.delete_doc("Custom Field", r.name, force=1, ignore_permissions=True)
            print("Deleted Custom Field:", r.dt, r.fieldname, r.name)


def run():
    mode = os.environ.get("KPWS_CLEAN_MODE", "dry")
    out = os.environ.get("KPWS_CLEAN_OUT", "/root")

    custom_fields = _get_custom_fields()
    property_setters = _get_property_setters()
    client_scripts = _get_client_scripts()

    _rows_to_json(os.path.join(out, "custom_fields_target.json"), custom_fields)
    _rows_to_json(os.path.join(out, "property_setters_target.json"), property_setters)
    _rows_to_json(os.path.join(out, "client_scripts_target.json"), client_scripts)

    print("Target doctypes:", ", ".join(TARGET_DOCTYPES))
    print("Custom Fields found:", len(custom_fields))
    print("Property Setters found:", len(property_setters))
    print("Client Scripts to disable:", len(client_scripts))

    print("")
    print("===== Custom Fields =====")
    for r in custom_fields:
        print(f"{r.dt} | {r.fieldname} | {r.label} | {r.name}")

    print("")
    print("===== Property Setters =====")
    for r in property_setters:
        print(f"{r.doc_type} | {r.field_name} | {r.property} | {r.name}")

    print("")
    print("===== Client Scripts =====")
    for r in client_scripts:
        print(f"{r.dt} | {r.name} | enabled={r.enabled}")

    if mode != "apply":
        print("")
        print("DRY RUN ONLY. Nothing deleted.")
        return "DRY_RUN"

    print("")
    print("APPLY MODE: disabling scripts and deleting metadata...")

    _disable_client_scripts(client_scripts)
    _delete_property_setters(property_setters)
    _delete_custom_fields(custom_fields)

    frappe.db.commit()

    for dt in TARGET_DOCTYPES:
        try:
            frappe.db.updatedb(dt)
        except Exception as e:
            print("updatedb warning:", dt, e)

        frappe.clear_cache(doctype=dt)

    frappe.clear_cache()
    frappe.db.commit()

    print("Custom field reset completed.")
    return "APPLIED"
