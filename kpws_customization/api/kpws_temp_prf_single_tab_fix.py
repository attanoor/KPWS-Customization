import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

DT = "Patient Registration Form"

def field_exists(fieldname):
    return bool(frappe.get_meta(DT).get_field(fieldname))

def make_ps(fieldname, prop, value, ptype="Check"):
    name = frappe.db.exists("Property Setter", {
        "doc_type": DT,
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
            "doc_type": DT,
            "doctype_or_field": "DocField",
            "field_name": fieldname,
            "property": prop,
            "property_type": ptype,
            "value": str(value),
        }).insert(ignore_permissions=True)

def set_custom_field(fieldname, values):
    name = frappe.db.exists("Custom Field", {"dt": DT, "fieldname": fieldname})
    if not name:
        return

    valid = {df.fieldname for df in frappe.get_meta("Custom Field").fields}
    clean = {k: v for k, v in values.items() if k in valid}
    if clean:
        frappe.db.set_value("Custom Field", name, clean, update_modified=False)

def install_script():
    if not frappe.db.exists("DocType", "Client Script"):
        return

    script = r'''
frappe.ui.form.on("Patient Registration Form", {
    setup(frm) {
        kpws_prf_single_tab_setup(frm);
    },
    onload(frm) {
        kpws_prf_single_tab_setup(frm);
    },
    refresh(frm) {
        kpws_prf_single_tab_setup(frm);
    },
    custom_panel_customer(frm) {
        kpws_prf_sync_panel(frm);
    }
});

function kpws_prf_has_field(frm, fieldname) {
    return frm.fields_dict && frm.fields_dict[fieldname];
}

function kpws_prf_sync_panel(frm) {
    let value = frm.doc.custom_panel_customer;
    if (!value) return;

    if (kpws_prf_has_field(frm, "custom_kpws_assigned_panel_customer")) {
        frm.set_value("custom_kpws_assigned_panel_customer", value);
    }
}

function kpws_prf_single_tab_setup(frm) {
    if (kpws_prf_has_field(frm, "custom_panel_customer")) {
        frm.set_query("custom_panel_customer", function() {
            return {
                filters: {
                    custom_is_panel: 1
                }
            };
        });

        frm.toggle_display("custom_panel_customer", true);
        frm.toggle_reqd("custom_panel_customer", false);
    }

    if (kpws_prf_has_field(frm, "custom_kpws_assigned_panel_customer")) {
        frm.toggle_display("custom_kpws_assigned_panel_customer", false);
        frm.toggle_reqd("custom_kpws_assigned_panel_customer", false);
    }
}
'''

    name = "KPWS FINAL PRF Single Discount Purpose Tab"

    if frappe.db.exists("Client Script", name):
        doc = frappe.get_doc("Client Script", name)
        doc.enabled = 1
        doc.dt = DT
        doc.view = "Form"
        doc.script = script
        doc.save(ignore_permissions=True)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": name,
            "dt": DT,
            "view": "Form",
            "enabled": 1,
            "script": script,
        }).insert(ignore_permissions=True)

def run():
    if not frappe.db.exists("DocType", DT):
        raise Exception(f"{DT} not found")

    print("Creating missing Panel fields on Patient Registration Form...")

    custom_fields = {
        DT: []
    }

    if not field_exists("custom_panel_customer"):
        custom_fields[DT].append({
            "fieldname": "custom_panel_customer",
            "label": "Panel",
            "fieldtype": "Link",
            "options": "Customer",
            "insert_after": "purpose",
            "reqd": 0,
            "hidden": 0,
        })

    if not field_exists("custom_kpws_assigned_panel_customer"):
        custom_fields[DT].append({
            "fieldname": "custom_kpws_assigned_panel_customer",
            "label": "Assigned Panel",
            "fieldtype": "Link",
            "options": "Customer",
            "insert_after": "custom_panel_customer",
            "reqd": 0,
            "hidden": 1,
        })

    if custom_fields[DT]:
        create_custom_fields(custom_fields, update=True)

    # Make Discount and Purpose visible
    for fieldname in ["discount_and_purpose_tab"]:
        if field_exists(fieldname):
            make_ps(fieldname, "hidden", "0")
            make_ps(fieldname, "label", "Discount and Purpose", "Data")

    # Hide other tabs from UI
    for fieldname in ["basic_information_tab", "contact_details_tab"]:
        if field_exists(fieldname):
            print("Hiding tab:", fieldname)
            make_ps(fieldname, "hidden", "1")

    # Move Panel after Purpose and keep visible
    if field_exists("custom_panel_customer"):
        set_custom_field("custom_panel_customer", {
            "label": "Panel",
            "fieldtype": "Link",
            "options": "Customer",
            "insert_after": "purpose",
            "hidden": 0,
            "reqd": 0,
            "read_only": 0,
            "print_hide": 0,
        })

        make_ps("custom_panel_customer", "hidden", "0")
        make_ps("custom_panel_customer", "reqd", "0")
        make_ps("custom_panel_customer", "read_only", "0")
        make_ps("custom_panel_customer", "label", "Panel", "Data")

    # Hide backend assigned panel duplicate
    if field_exists("custom_kpws_assigned_panel_customer"):
        set_custom_field("custom_kpws_assigned_panel_customer", {
            "hidden": 1,
            "reqd": 0,
            "print_hide": 1,
            "insert_after": "custom_panel_customer",
        })

        make_ps("custom_kpws_assigned_panel_customer", "hidden", "1")
        make_ps("custom_kpws_assigned_panel_customer", "reqd", "0")

    install_script()

    frappe.clear_cache(doctype=DT)
    frappe.db.commit()

    print("")
    print("Verification:")
    meta = frappe.get_meta(DT)
    for fn in [
        "basic_information_tab",
        "contact_details_tab",
        "discount_and_purpose_tab",
        "discount_type",
        "discount_value",
        "purpose",
        "custom_panel_customer",
        "custom_kpws_assigned_panel_customer",
    ]:
        df = meta.get_field(fn)
        print(fn, "=>", "FOUND" if df else "MISSING", "| hidden:", getattr(df, "hidden", None), "| label:", getattr(df, "label", None), "| insert_after:", getattr(df, "insert_after", None))

    print("")
    print("DONE: PRF now has only Discount and Purpose visible, with Panel inside it.")

