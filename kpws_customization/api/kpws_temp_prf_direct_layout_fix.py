import frappe

DT = "Patient Registration Form"
TABLE = "tabPatient Registration Form"

def col_exists(col):
    return bool(frappe.db.sql("""
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = %s
        AND COLUMN_NAME = %s
    """, (TABLE, col)))

def add_col(col, sql_type):
    if not col_exists(col):
        print("Adding DB column:", col)
        frappe.db.sql(f"ALTER TABLE `{TABLE}` ADD COLUMN `{col}` {sql_type}")
    else:
        print("DB column exists:", col)

def get_df(fieldname):
    return frappe.db.get_value(
        "DocField",
        {"parent": DT, "fieldname": fieldname},
        ["name", "idx", "fieldname", "label", "fieldtype", "hidden"],
        as_dict=True
    )

def set_df(fieldname, values):
    df = get_df(fieldname)
    if df:
        frappe.db.set_value("DocField", df.name, values, update_modified=False)
        print("Updated DocField:", fieldname, values)
        return True
    print("Missing DocField:", fieldname)
    return False

def insert_df(fieldname, label, fieldtype, options=None, insert_after=None, hidden=0, reqd=0):
    existing = get_df(fieldname)
    if existing:
        print("DocField already exists:", fieldname)
        return existing.name

    if insert_after and get_df(insert_after):
        anchor_idx = int(get_df(insert_after).idx or 0)
    else:
        anchor_idx = int(frappe.db.sql("""
            SELECT COALESCE(MAX(idx), 0)
            FROM `tabDocField`
            WHERE parent = %s
        """, DT)[0][0] or 0)

    # Shift fields after anchor
    frappe.db.sql("""
        UPDATE `tabDocField`
        SET idx = idx + 1
        WHERE parent = %s
        AND idx > %s
    """, (DT, anchor_idx))

    doc = frappe.get_doc({
        "doctype": "DocField",
        "parent": DT,
        "parenttype": "DocType",
        "parentfield": "fields",
        "fieldname": fieldname,
        "label": label,
        "fieldtype": fieldtype,
        "options": options,
        "idx": anchor_idx + 1,
        "hidden": hidden,
        "reqd": reqd,
    })
    doc.insert(ignore_permissions=True)
    print("Inserted DocField:", fieldname, "after", insert_after)
    return doc.name

def move_after(fieldname, after_fieldname):
    df = get_df(fieldname)
    anchor = get_df(after_fieldname)

    if not df or not anchor:
        print("Cannot move:", fieldname, "after", after_fieldname)
        return

    all_fields = frappe.get_all(
        "DocField",
        filters={"parent": DT},
        fields=["name", "fieldname", "idx"],
        order_by="idx asc"
    )

    ordered = [x for x in all_fields if x.name != df.name]

    pos = 0
    for i, x in enumerate(ordered):
        if x.name == anchor.name:
            pos = i + 1
            break

    ordered.insert(pos, df)

    for i, x in enumerate(ordered, start=1):
        frappe.db.set_value("DocField", x.name, "idx", i, update_modified=False)

    print("Moved", fieldname, "after", after_fieldname)

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

def disable_conflicting_prf_scripts():
    if not frappe.db.exists("DocType", "Client Script"):
        return

    keep = ["KPWS FINAL PRF Direct Layout"]
    for row in frappe.get_all("Client Script", filters={"dt": DT}, fields=["name", "script"]):
        if row.name in keep:
            continue
        text = ((row.name or "") + "\n" + (row.script or "")).lower()
        if any(k in text for k in ["panel", "welfare", "discount", "purpose", "kpws"]):
            frappe.db.set_value("Client Script", row.name, "enabled", 0, update_modified=False)
            print("Disabled old PRF Client Script:", row.name)

def install_client_script():
    if not frappe.db.exists("DocType", "Client Script"):
        return

    script = r'''
frappe.ui.form.on("Patient Registration Form", {
    setup(frm) {
        kpws_prf_clean_layout(frm);
    },
    onload(frm) {
        kpws_prf_clean_layout(frm);
    },
    refresh(frm) {
        kpws_prf_clean_layout(frm);
    },
    custom_panel_customer(frm) {
        if (frm.fields_dict.custom_kpws_assigned_panel_customer) {
            frm.set_value("custom_kpws_assigned_panel_customer", frm.doc.custom_panel_customer || "");
        }
    }
});

function kpws_prf_clean_layout(frm) {
    if (frm.fields_dict.custom_panel_customer) {
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

    if (frm.fields_dict.custom_kpws_assigned_panel_customer) {
        frm.toggle_display("custom_kpws_assigned_panel_customer", false);
        frm.toggle_reqd("custom_kpws_assigned_panel_customer", false);
    }
}
'''

    name = "KPWS FINAL PRF Direct Layout"
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

    print("Installed final PRF Client Script")

def print_layout():
    print("")
    print("Final layout:")
    rows = frappe.get_all(
        "DocField",
        filters={"parent": DT},
        fields=["idx", "fieldname", "label", "fieldtype", "hidden"],
        order_by="idx asc"
    )
    for r in rows:
        if r.fieldtype == "Tab Break" or r.fieldname in [
            "discount_type",
            "discount_value",
            "purpose",
            "custom_panel_customer",
            "custom_kpws_assigned_panel_customer",
            "basic_information_tab",
            "contact_details_tab",
            "discount_and_purpose_tab",
        ]:
            print(r.idx, r.fieldtype, r.fieldname, r.label, "hidden=", r.hidden)

def run():
    if not frappe.db.exists("DocType", DT):
        raise Exception(f"{DT} not found")

    # Fix bad decimal defaults that caused earlier schema sync crash
    frappe.db.sql("""
        UPDATE `tabCustom Field`
        SET `default` = NULL
        WHERE dt = %s
        AND (`default` = 'NULL' OR `default` = '')
        AND fieldtype IN ('Float', 'Currency', 'Percent')
    """, DT)

    # Manually ensure DB columns exist
    add_col("custom_panel_customer", "varchar(140)")
    add_col("custom_kpws_assigned_panel_customer", "varchar(140)")

    # Hide unwanted tabs
    set_df("basic_information_tab", {"hidden": 1})
    set_df("contact_details_tab", {"hidden": 1})

    # Keep Discount and Purpose visible
    set_df("discount_and_purpose_tab", {
        "hidden": 0,
        "label": "Discount and Purpose"
    })

    # Also create property setters so Customize Form cache cannot override us
    make_ps("basic_information_tab", "hidden", "1")
    make_ps("contact_details_tab", "hidden", "1")
    make_ps("discount_and_purpose_tab", "hidden", "0")
    make_ps("discount_and_purpose_tab", "label", "Discount and Purpose", "Data")

    # Add visible Panel field inside Discount and Purpose
    insert_df(
        fieldname="custom_panel_customer",
        label="Panel",
        fieldtype="Link",
        options="Customer",
        insert_after="purpose",
        hidden=0,
        reqd=0
    )
    set_df("custom_panel_customer", {
        "label": "Panel",
        "fieldtype": "Link",
        "options": "Customer",
        "hidden": 0,
        "reqd": 0,
        "read_only": 0,
        "print_hide": 0
    })
    move_after("custom_panel_customer", "purpose")

    # Add hidden backend field for sales logic sync
    insert_df(
        fieldname="custom_kpws_assigned_panel_customer",
        label="Assigned Panel",
        fieldtype="Link",
        options="Customer",
        insert_after="custom_panel_customer",
        hidden=1,
        reqd=0
    )
    set_df("custom_kpws_assigned_panel_customer", {
        "hidden": 1,
        "reqd": 0,
        "print_hide": 1
    })
    move_after("custom_kpws_assigned_panel_customer", "custom_panel_customer")

    disable_conflicting_prf_scripts()
    install_client_script()

    frappe.db.set_value("DocType", DT, "modified", frappe.utils.now(), update_modified=False)

    frappe.clear_cache(doctype=DT)
    frappe.db.commit()

    print_layout()
    print("")
    print("DONE")

