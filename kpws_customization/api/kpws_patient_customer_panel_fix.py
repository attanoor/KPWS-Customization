import frappe

PATIENT_DT = "Patient"
CUSTOMER_DT = "Customer"
CLIENT_SCRIPT_NAME = "KPWS FINAL Patient Customer Panel Selector"


def set_property(dt, fieldname, prop, value, ptype="Check"):
    name = frappe.db.exists("Property Setter", {
        "doc_type": dt,
        "doctype_or_field": "DocField",
        "field_name": fieldname,
        "property": prop,
    })

    if name:
        frappe.db.set_value("Property Setter", name, {
            "value": str(value),
            "property_type": ptype,
        }, update_modified=False)
    else:
        frappe.get_doc({
            "doctype": "Property Setter",
            "doc_type": dt,
            "doctype_or_field": "DocField",
            "field_name": fieldname,
            "property": prop,
            "property_type": ptype,
            "value": str(value),
        }).insert(ignore_permissions=True)


def upsert_custom_field(dt, fieldname, values):
    name = frappe.db.exists("Custom Field", {"dt": dt, "fieldname": fieldname})

    if name:
        valid = {df.fieldname for df in frappe.get_meta("Custom Field").fields}
        clean = {k: v for k, v in values.items() if k in valid}
        if clean:
            frappe.db.set_value("Custom Field", name, clean, update_modified=False)
        return name

    doc = frappe.get_doc({
        "doctype": "Custom Field",
        "dt": dt,
        "fieldname": fieldname,
        **values,
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def install_customer_is_panel():
    upsert_custom_field(CUSTOMER_DT, "custom_is_panel", {
        "label": "Is Panel",
        "fieldtype": "Check",
        "insert_after": "customer_group",
        "default": "0",
        "hidden": 0,
        "reqd": 0,
    })


def install_patient_panel_field():
    depends = "eval:((doc.customer_group || '').toLowerCase().includes('panel') || (doc.custom_patient_billing_type || '').toLowerCase().includes('panel'))"

    upsert_custom_field(PATIENT_DT, "custom_panel_customer", {
        "label": "Panel Name",
        "fieldtype": "Link",
        "options": "Customer",
        "insert_after": "customer_group",
        "hidden": 0,
        "reqd": 0,
        "read_only": 0,
        "depends_on": depends,
    })

    for prop, value, ptype in [
        ("label", "Panel Name", "Data"),
        ("fieldtype", "Link", "Data"),
        ("options", "Customer", "Data"),
        ("hidden", "0", "Check"),
        ("reqd", "0", "Check"),
        ("read_only", "0", "Check"),
        ("depends_on", depends, "Data"),
    ]:
        set_property(PATIENT_DT, "custom_panel_customer", prop, value, ptype)

    # Hide Healthcare/KPWS Panel doctype field if it exists. We do not want users using it.
    meta = frappe.get_meta(PATIENT_DT)
    old = meta.get_field("panel_name")
    if old:
        print("Hiding old Patient.panel_name. Current options:", old.options)
        set_property(PATIENT_DT, "panel_name", "hidden", "1", "Check")
        set_property(PATIENT_DT, "panel_name", "reqd", "0", "Check")
        set_property(PATIENT_DT, "panel_name", "read_only", "1", "Check")
        set_property(PATIENT_DT, "panel_name", "label", "Old Panel Name - Hidden", "Data")


def disable_old_patient_panel_scripts():
    if not frappe.db.exists("DocType", "Client Script"):
        return

    for row in frappe.get_all("Client Script", filters={"dt": PATIENT_DT}, fields=["name", "script"]):
        if row.name == CLIENT_SCRIPT_NAME:
            continue

        text = ((row.name or "") + "\n" + (row.script or "")).lower()
        if "panel" in text or "kpws" in text:
            frappe.db.set_value("Client Script", row.name, "enabled", 0, update_modified=False)
            print("Disabled old Patient script:", row.name)


def install_patient_client_script():
    if not frappe.db.exists("DocType", "Client Script"):
        return

    script = r'''
frappe.ui.form.on("Patient", {
    setup(frm) {
        kpws_patient_panel_setup(frm);
    },
    onload(frm) {
        kpws_patient_panel_setup(frm);
    },
    refresh(frm) {
        kpws_patient_panel_setup(frm);
    },
    customer_group(frm) {
        kpws_patient_panel_setup(frm);
    },
    custom_patient_billing_type(frm) {
        kpws_patient_panel_setup(frm);
    },
    custom_panel_customer(frm) {
        kpws_patient_panel_setup(frm);
    }
});

function kpws_patient_has(frm, fieldname) {
    return frm.fields_dict && frm.fields_dict[fieldname];
}

function kpws_patient_type(frm) {
    return String(frm.doc.customer_group || frm.doc.custom_patient_billing_type || "").toLowerCase();
}

function kpws_patient_is_panel(frm) {
    return kpws_patient_type(frm).includes("panel");
}

function kpws_patient_panel_setup(frm) {
    let is_panel = kpws_patient_is_panel(frm);

    if (kpws_patient_has(frm, "custom_panel_customer")) {
        frm.set_query("custom_panel_customer", function() {
            return {
                filters: {
                    custom_is_panel: 1
                }
            };
        });

        frm.toggle_display("custom_panel_customer", is_panel);
        frm.toggle_reqd("custom_panel_customer", is_panel);

        frm.set_df_property("custom_panel_customer", "label", "Panel Name");
        frm.set_df_property("custom_panel_customer", "options", "Customer");
    }

    // Hide wrong old field linked to KPWS Panel doctype.
    if (kpws_patient_has(frm, "panel_name")) {
        frm.toggle_display("panel_name", false);
        frm.toggle_reqd("panel_name", false);
    }

    if (!is_panel && kpws_patient_has(frm, "custom_panel_customer") && frm.doc.custom_panel_customer) {
        frm.set_value("custom_panel_customer", "");
    }
}
'''

    if frappe.db.exists("Client Script", CLIENT_SCRIPT_NAME):
        doc = frappe.get_doc("Client Script", CLIENT_SCRIPT_NAME)
        doc.enabled = 1
        doc.dt = PATIENT_DT
        doc.view = "Form"
        doc.script = script
        doc.save(ignore_permissions=True)
        print("Updated Client Script:", CLIENT_SCRIPT_NAME)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": CLIENT_SCRIPT_NAME,
            "dt": PATIENT_DT,
            "view": "Form",
            "enabled": 1,
            "script": script,
        }).insert(ignore_permissions=True)
        print("Created Client Script:", CLIENT_SCRIPT_NAME)


def migrate_existing_panel_values_if_customer():
    meta = frappe.get_meta(PATIENT_DT)
    if not meta.get_field("panel_name"):
        return

    rows = frappe.get_all(
        PATIENT_DT,
        filters={"customer_group": ["like", "%Panel%"]},
        fields=["name", "panel_name", "custom_panel_customer"],
        limit=10000,
    )

    copied = 0

    for row in rows:
        if row.custom_panel_customer:
            continue

        if row.panel_name and frappe.db.exists("Customer", row.panel_name):
            if frappe.get_meta("Customer").get_field("custom_is_panel") and frappe.db.get_value("Customer", row.panel_name, "custom_is_panel"):
                frappe.db.set_value(PATIENT_DT, row.name, "custom_panel_customer", row.panel_name, update_modified=False)
                copied += 1

    print("Migrated old panel_name values that were valid Customers:", copied)


def install():
    install_customer_is_panel()
    install_patient_panel_field()
    disable_old_patient_panel_scripts()
    install_patient_client_script()
    migrate_existing_panel_values_if_customer()

    frappe.db.commit()
    frappe.clear_cache(doctype=PATIENT_DT)
    frappe.clear_cache(doctype=CUSTOMER_DT)

    print("")
    print("DONE: Patient Panel Name now uses Customer.custom_is_panel only.")
