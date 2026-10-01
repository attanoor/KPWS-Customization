import frappe

DT = "Patient Registration Form"

FIELDS_TO_MAKE_OPTIONAL = [
    "purpose",
    "discount_value",
    "discount_type",
    "custom_panel_customer",
    "custom_kpws_welfare_type",
    "custom_kpws_welfare_percentage",
    "custom_kpws_assigned_panel_customer",
    "custom_kpws_admin_notes",
    "cnic",
    "custom_cnic",
]

def set_docfield_optional(fieldname):
    rows = frappe.get_all(
        "DocField",
        filters={"parent": DT, "fieldname": fieldname},
        fields=["name", "fieldname", "label", "reqd", "hidden"]
    )

    for row in rows:
        frappe.db.set_value("DocField", row.name, {
            "reqd": 0
        }, update_modified=False)
        print("DocField optional:", fieldname, "|", row.label)

def set_custom_field_optional(fieldname):
    rows = frappe.get_all(
        "Custom Field",
        filters={"dt": DT, "fieldname": fieldname},
        fields=["name", "fieldname", "label", "reqd"]
    )

    for row in rows:
        frappe.db.set_value("Custom Field", row.name, {
            "reqd": 0
        }, update_modified=False)
        print("Custom Field optional:", fieldname, "|", row.label)

def set_property_setter_optional(fieldname):
    rows = frappe.get_all(
        "Property Setter",
        filters={
            "doc_type": DT,
            "doctype_or_field": "DocField",
            "field_name": fieldname,
            "property": "reqd",
        },
        fields=["name", "value"]
    )

    if rows:
        for row in rows:
            frappe.db.set_value("Property Setter", row.name, {
                "value": "0",
                "property_type": "Check",
            }, update_modified=False)
            print("Property Setter optional:", fieldname)
    else:
        frappe.get_doc({
            "doctype": "Property Setter",
            "doc_type": DT,
            "doctype_or_field": "DocField",
            "field_name": fieldname,
            "property": "reqd",
            "property_type": "Check",
            "value": "0",
        }).insert(ignore_permissions=True)
        print("Property Setter created optional:", fieldname)

def install_client_script():
    if not frappe.db.exists("DocType", "Client Script"):
        return

    script = r'''
frappe.ui.form.on("Patient Registration Form", {
    setup(frm) {
        kpws_prf_make_draft_fields_optional(frm);
    },
    onload(frm) {
        kpws_prf_make_draft_fields_optional(frm);
    },
    refresh(frm) {
        kpws_prf_make_draft_fields_optional(frm);
    },
    purpose(frm) {
        kpws_prf_sync_backend(frm);
    },
    discount_value(frm) {
        kpws_prf_sync_backend(frm);
    },
    custom_panel_customer(frm) {
        kpws_prf_sync_backend(frm);
    }
});

function kpws_prf_has(frm, fieldname) {
    return frm.fields_dict && frm.fields_dict[fieldname];
}

function kpws_prf_make_draft_fields_optional(frm) {
    ["purpose", "discount_value", "discount_type", "custom_panel_customer"].forEach(function(fieldname) {
        if (kpws_prf_has(frm, fieldname)) {
            frm.toggle_reqd(fieldname, false);
        }
    });

    if (kpws_prf_has(frm, "custom_panel_customer")) {
        frm.set_query("custom_panel_customer", function() {
            return {
                filters: {
                    custom_is_panel: 1
                }
            };
        });
    }

    ["custom_kpws_welfare_type", "custom_kpws_welfare_percentage", "custom_kpws_assigned_panel_customer"].forEach(function(fieldname) {
        if (kpws_prf_has(frm, fieldname)) {
            frm.toggle_display(fieldname, false);
            frm.toggle_reqd(fieldname, false);
        }
    });

    kpws_prf_sync_backend(frm);
}

function kpws_prf_sync_backend(frm) {
    if (kpws_prf_has(frm, "custom_kpws_welfare_type") && frm.doc.purpose) {
        frm.set_value("custom_kpws_welfare_type", frm.doc.purpose);
    }

    if (kpws_prf_has(frm, "custom_kpws_welfare_percentage")) {
        frm.set_value("custom_kpws_welfare_percentage", frm.doc.discount_value || 0);
    }

    if (kpws_prf_has(frm, "custom_kpws_assigned_panel_customer")) {
        frm.set_value("custom_kpws_assigned_panel_customer", frm.doc.custom_panel_customer || "");
    }
}
'''

    name = "KPWS FINAL PRF Optional Draft Fields"

    if frappe.db.exists("Client Script", name):
        doc = frappe.get_doc("Client Script", name)
        doc.enabled = 1
        doc.dt = DT
        doc.view = "Form"
        doc.script = script
        doc.save(ignore_permissions=True)
        print("Updated Client Script:", name)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": name,
            "dt": DT,
            "view": "Form",
            "enabled": 1,
            "script": script,
        }).insert(ignore_permissions=True)
        print("Created Client Script:", name)

def run():
    if not frappe.db.exists("DocType", DT):
        raise Exception(f"{DT} not found")

    print("Making draft creation fields optional...")

    for fieldname in FIELDS_TO_MAKE_OPTIONAL:
        set_docfield_optional(fieldname)
        set_custom_field_optional(fieldname)
        set_property_setter_optional(fieldname)

    install_client_script()

    frappe.db.set_value("DocType", DT, "modified", frappe.utils.now(), update_modified=False)
    frappe.clear_cache(doctype=DT)
    frappe.db.commit()

    print("")
    print("Verification:")
    meta = frappe.get_meta(DT)
    for fieldname in FIELDS_TO_MAKE_OPTIONAL:
        df = meta.get_field(fieldname)
        print(fieldname, "=>", "FOUND" if df else "MISSING", "| reqd:", getattr(df, "reqd", None))

    print("")
    print("DONE: Purpose and Percentage are optional for draft creation.")

