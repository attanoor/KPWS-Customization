import frappe

PATIENT_DT = "Patient"
CUSTOMER_DT = "Customer"
CLIENT_SCRIPT_NAME = "KPWS FORCE Patient Panel Customer Only"


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def panel_customer_query(doctype, txt, searchfield, start, page_len, filters):
    if not frappe.get_meta("Customer").get_field("custom_is_panel"):
        return []

    return frappe.db.sql("""
        SELECT
            name,
            customer_name
        FROM `tabCustomer`
        WHERE
            IFNULL(custom_is_panel, 0) = 1
            AND (
                name LIKE %(txt)s
                OR customer_name LIKE %(txt)s
            )
        ORDER BY customer_name, name
        LIMIT %(start)s, %(page_len)s
    """, {
        "txt": f"%{txt or ''}%",
        "start": int(start or 0),
        "page_len": int(page_len or 20),
    })


def ps(dt, fieldname, prop, value, ptype="Check"):
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


def ensure_custom_field(dt, fieldname, values):
    name = frappe.db.exists("Custom Field", {"dt": dt, "fieldname": fieldname})

    if name:
        valid = {df.fieldname for df in frappe.get_meta("Custom Field").fields}
        clean = {k: v for k, v in values.items() if k in valid}
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
    ensure_custom_field("Customer", "custom_is_panel", {
        "label": "Is Panel",
        "fieldtype": "Check",
        "insert_after": "customer_group",
        "default": "0",
        "hidden": 0,
        "reqd": 0,
    })


def install_patient_panel_field():
    depends = "eval:((doc.customer_group || '').toLowerCase().includes('panel') || (doc.custom_patient_billing_type || '').toLowerCase().includes('panel'))"

    ensure_custom_field("Patient", "custom_panel_customer", {
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
        ps("Patient", "custom_panel_customer", prop, value, ptype)

    # Hide wrong old panel field.
    if frappe.get_meta("Patient").get_field("panel_name"):
        ps("Patient", "panel_name", "hidden", "1", "Check")
        ps("Patient", "panel_name", "reqd", "0", "Check")
        ps("Patient", "panel_name", "read_only", "1", "Check")
        ps("Patient", "panel_name", "label", "Old Panel Name - Hidden", "Data")


def disable_old_patient_scripts():
    if not frappe.db.exists("DocType", "Client Script"):
        return

    for row in frappe.get_all("Client Script", filters={"dt": "Patient"}, fields=["name", "script"]):
        if row.name == CLIENT_SCRIPT_NAME:
            continue

        text = ((row.name or "") + "\n" + (row.script or "")).lower()
        if "panel" in text or "kpws" in text or "patient billing" in text:
            frappe.db.set_value("Client Script", row.name, "enabled", 0, update_modified=False)
            print("Disabled old Patient Client Script:", row.name)


def install_client_script():
    if not frappe.db.exists("DocType", "Client Script"):
        return

    script = r'''
frappe.ui.form.on("Patient", {
    setup(frm) {
        kpws_force_panel_customer_setup(frm);
    },
    onload(frm) {
        kpws_force_panel_customer_setup(frm);
    },
    refresh(frm) {
        kpws_force_panel_customer_setup(frm);
    },
    customer_group(frm) {
        kpws_force_panel_customer_setup(frm);
    },
    custom_patient_billing_type(frm) {
        kpws_force_panel_customer_setup(frm);
    }
});

function kpws_force_has(frm, fieldname) {
    return frm.fields_dict && frm.fields_dict[fieldname];
}

function kpws_force_is_panel_patient(frm) {
    let txt = [
        frm.doc.customer_group || "",
        frm.doc.custom_patient_billing_type || ""
    ].join(" ").toLowerCase();

    return txt.includes("panel");
}

function kpws_force_panel_customer_setup(frm) {
    let is_panel = kpws_force_is_panel_patient(frm);

    if (kpws_force_has(frm, "custom_panel_customer")) {
        frm.set_query("custom_panel_customer", function() {
            return {
                query: "kpws_customization.api.kpws_force_patient_panel_customer.panel_customer_query"
            };
        });

        frm.set_df_property("custom_panel_customer", "label", "Panel Name");
        frm.set_df_property("custom_panel_customer", "options", "Customer");
        frm.toggle_display("custom_panel_customer", is_panel);
        frm.toggle_reqd("custom_panel_customer", is_panel);
    }

    // Hide wrong old field that points to KPWS Panel / Healthcare panel.
    if (kpws_force_has(frm, "panel_name")) {
        frm.toggle_display("panel_name", false);
        frm.toggle_reqd("panel_name", false);
    }

    if (!is_panel && kpws_force_has(frm, "custom_panel_customer") && frm.doc.custom_panel_customer) {
        frm.set_value("custom_panel_customer", "");
    }
}
'''

    if frappe.db.exists("Client Script", CLIENT_SCRIPT_NAME):
        doc = frappe.get_doc("Client Script", CLIENT_SCRIPT_NAME)
        doc.enabled = 1
        doc.dt = "Patient"
        doc.view = "Form"
        doc.script = script
        doc.save(ignore_permissions=True)
        print("Updated:", CLIENT_SCRIPT_NAME)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": CLIENT_SCRIPT_NAME,
            "dt": "Patient",
            "view": "Form",
            "enabled": 1,
            "script": script,
        }).insert(ignore_permissions=True)
        print("Created:", CLIENT_SCRIPT_NAME)


def show_panel_customers():
    print("")
    print("Customers marked Is Panel:")
    rows = frappe.get_all(
        "Customer",
        filters={"custom_is_panel": 1},
        fields=["name", "customer_name"],
        order_by="customer_name asc",
        limit=50,
    )

    for row in rows:
        print("-", row.name, "|", row.customer_name)

    if not rows:
        print("No Customer found with custom_is_panel = 1")


def install():
    install_customer_is_panel()
    install_patient_panel_field()
    disable_old_patient_scripts()
    install_client_script()

    frappe.db.commit()
    frappe.clear_cache(doctype="Patient")
    frappe.clear_cache(doctype="Customer")

    print("")
    print("Patient panel fields after patch:")
    meta = frappe.get_meta("Patient")
    for fn in ["custom_panel_customer", "panel_name"]:
        df = meta.get_field(fn)
        if df:
            print(fn, "| label:", df.label, "| type:", df.fieldtype, "| options:", df.options, "| hidden:", df.hidden)
        else:
            print(fn, "| MISSING")

    show_panel_customers()

    print("")
    print("DONE: Patient Panel Name now queries Customer where Is Panel is checked.")
