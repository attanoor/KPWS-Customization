import frappe

DT = "Patient Registration Form"

def ps_set(dt, fieldname, prop, value, ptype):
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

def cf_set(dt, fieldname, values):
    name = frappe.db.exists("Custom Field", {"dt": dt, "fieldname": fieldname})
    if not name:
        return False

    valid = {df.fieldname for df in frappe.get_meta("Custom Field").fields}
    clean = {k: v for k, v in values.items() if k in valid}

    if clean:
        frappe.db.set_value("Custom Field", name, clean, update_modified=False)

    return True

def set_field(dt, fieldname, values):
    is_custom = cf_set(dt, fieldname, values)

    for prop, value in values.items():
        if prop in ["hidden", "read_only", "reqd", "print_hide"]:
            ps_set(dt, fieldname, prop, int(value), "Check")
        elif prop in ["label", "depends_on"]:
            ps_set(dt, fieldname, prop, value or "", "Data")

    return is_custom

def install_prf_script():
    if not frappe.db.exists("DocType", "Client Script"):
        return

    script = r'''
frappe.ui.form.on("Patient Registration Form", {
    setup(frm) {
        kpws_prf_setup(frm);
    },
    onload(frm) {
        kpws_prf_setup(frm);
    },
    refresh(frm) {
        kpws_prf_setup(frm);
    },
    custom_panel_customer(frm) {
        kpws_sync_prf_panel(frm, "custom_panel_customer");
    },
    custom_kpws_assigned_panel_customer(frm) {
        kpws_sync_prf_panel(frm, "custom_kpws_assigned_panel_customer");
    }
});

function kpws_has_field(frm, fieldname) {
    return frm.fields_dict && frm.fields_dict[fieldname];
}

function kpws_sync_prf_panel(frm, source_field) {
    let value = frm.doc[source_field];
    if (!value) return;

    ["custom_panel_customer", "custom_kpws_assigned_panel_customer"].forEach(function(fieldname) {
        if (fieldname !== source_field && kpws_has_field(frm, fieldname) && frm.doc[fieldname] !== value) {
            frm.set_value(fieldname, value);
        }
    });
}

function kpws_prf_setup(frm) {
    ["custom_panel_customer", "custom_kpws_assigned_panel_customer"].forEach(function(fieldname) {
        if (kpws_has_field(frm, fieldname)) {
            frm.set_query(fieldname, function() {
                return {
                    filters: {
                        custom_is_panel: 1
                    }
                };
            });
        }
    });

    if (kpws_has_field(frm, "custom_panel_customer")) {
        frm.toggle_display("custom_panel_customer", true);
        frm.toggle_reqd("custom_panel_customer", false);
    }

    if (kpws_has_field(frm, "custom_kpws_assigned_panel_customer")) {
        frm.toggle_display("custom_kpws_assigned_panel_customer", false);
        frm.toggle_reqd("custom_kpws_assigned_panel_customer", false);
    }
}
'''

    name = "KPWS FINAL PRF Discount Purpose Layout"

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
    meta = frappe.get_meta(DT)

    print("Current layout fields containing tab/section/panel:")
    for df in meta.fields:
        if (
            df.fieldtype in ["Tab Break", "Section Break"]
            or "panel" in (df.fieldname or "").lower()
            or "panel" in (df.label or "").lower()
            or "discount" in (df.label or "").lower()
            or "purpose" in (df.label or "").lower()
        ):
            print(df.idx, df.fieldname, df.label, df.fieldtype, "hidden=", df.hidden)

    # Hide duplicate Details tab/section
    for df in meta.fields:
        label = (df.label or "").strip().lower()
        if df.fieldtype in ["Tab Break", "Section Break"] and label == "details":
            print("Hiding duplicate Details break:", df.fieldname)
            set_field(DT, df.fieldname, {
                "hidden": 1,
                "print_hide": 1,
            })

    # Find best anchor inside Discount and Purpose area
    anchor = None
    for candidate in [
        "custom_kpws_welfare_percentage",
        "custom_coverage_percentage",
        "coverage_percentage",
        "discount_percentage",
        "custom_kpws_welfare_type",
        "custom_assistance_type",
        "assistance_type",
        "purpose",
    ]:
        if meta.get_field(candidate):
            anchor = candidate
            break

    if not anchor:
        anchor = "patient_name"

    print("Panel field will be inserted after:", anchor)

    # Main visible panel field
    if meta.get_field("custom_panel_customer"):
        print("Showing custom_panel_customer as Panel in Discount and Purpose")
        cf_set(DT, "custom_panel_customer", {
            "label": "Panel",
            "insert_after": anchor,
            "hidden": 0,
            "read_only": 0,
            "reqd": 0,
            "print_hide": 0,
        })
        set_field(DT, "custom_panel_customer", {
            "label": "Panel",
            "hidden": 0,
            "read_only": 0,
            "reqd": 0,
            "print_hide": 0,
        })

    # Hide duplicate backend panel field but keep data column
    if meta.get_field("custom_kpws_assigned_panel_customer"):
        print("Hiding duplicate custom_kpws_assigned_panel_customer")
        set_field(DT, "custom_kpws_assigned_panel_customer", {
            "hidden": 1,
            "read_only": 0,
            "reqd": 0,
            "print_hide": 1,
        })

    install_prf_script()

    frappe.clear_cache(doctype=DT)
    frappe.db.commit()

    print("")
    print("DONE: Patient Registration Form layout cleaned.")
    print("Visible tab should now be Discount and Purpose, with Panel inside it.")

