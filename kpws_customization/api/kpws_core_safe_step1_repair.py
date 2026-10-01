import frappe


def _column_exists(table, column):
    rows = frappe.db.sql(f"SHOW COLUMNS FROM `{table}`", as_dict=True)
    return column in {r["Field"] for r in rows}


def _add_column_if_missing(table, column, definition):
    if not _column_exists(table, column):
        frappe.db.sql(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {definition}")
        print("Added missing custom column:", table, column)
    else:
        print("Column exists:", table, column)


def _ensure_custom_field(dt, fieldname, label, fieldtype, insert_after=None, options=None, **kwargs):
    rows = frappe.get_all(
        "Custom Field",
        filters={"dt": dt, "fieldname": fieldname},
        fields=["name"],
        order_by="creation asc",
        limit_page_length=50,
    )

    if rows:
        names = [r.name for r in rows]
    else:
        cf = frappe.new_doc("Custom Field")
        cf.dt = dt
        cf.fieldname = fieldname
        names = [None]

    for name in names:
        cf = frappe.get_doc("Custom Field", name) if name else cf

        cf.label = label
        cf.fieldtype = fieldtype

        if insert_after:
            cf.insert_after = insert_after

        if options is not None:
            cf.options = options

        for k, v in kwargs.items():
            if hasattr(cf, k):
                setattr(cf, k, v)

        if cf.is_new():
            cf.insert(ignore_permissions=True)
        else:
            cf.save(ignore_permissions=True)

    return names[0] if names[0] else cf.name


def _set_field_property(dt, fieldname, prop, value, property_type="Data"):
    # If field is Custom Field, update Custom Field directly.
    rows = frappe.get_all(
        "Custom Field",
        filters={"dt": dt, "fieldname": fieldname},
        fields=["name"],
        limit_page_length=50,
    )

    if rows:
        for r in rows:
            cf = frappe.get_doc("Custom Field", r.name)
            if hasattr(cf, prop):
                setattr(cf, prop, value)
                cf.save(ignore_permissions=True)
        return

    # If standard field, use Property Setter correctly for Frappe v14.
    if not frappe.get_meta(dt).get_field(fieldname):
        return

    ps_name = frappe.db.exists(
        "Property Setter",
        {
            "doc_type": dt,
            "field_name": fieldname,
            "property": prop,
        },
    )

    if ps_name:
        ps = frappe.get_doc("Property Setter", ps_name)
    else:
        ps = frappe.new_doc("Property Setter")
        ps.doctype_or_field = "DocField"
        ps.doc_type = dt
        ps.field_name = fieldname
        ps.property = prop

    ps.doctype_or_field = "DocField"
    ps.doc_type = dt
    ps.field_name = fieldname
    ps.property = prop
    ps.value = str(value)
    ps.property_type = property_type

    if ps.is_new():
        ps.insert(ignore_permissions=True)
    else:
        ps.save(ignore_permissions=True)


def _upsert_client_script(name, dt, script):
    existing = frappe.db.exists("Client Script", name)

    if existing:
        doc = frappe.get_doc("Client Script", existing)
    else:
        doc = frappe.new_doc("Client Script")
        doc.name = name
        doc.dt = dt
        doc.view = "Form"

    doc.enabled = 1
    doc.dt = dt
    doc.view = "Form"
    doc.script = script

    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)

    print("Enabled Client Script:", name)


def _disable_client_script(name):
    if frappe.db.exists("Client Script", name):
        frappe.db.set_value("Client Script", name, "enabled", 0)
        print("Disabled old Client Script:", name)


def apply():
    print("Applying KPWS core-safe Step 1 repair...")

    # --------------------------------------------------
    # Patient fields
    # --------------------------------------------------
    _ensure_custom_field(
        "Patient",
        "custom_patient_billing_type",
        "Patient Billing Type",
        "Select",
        insert_after="customer",
        options="\nCash\nWelfare\nPanel",
        reqd=1,
        hidden=0,
        read_only=0,
    )

    _ensure_custom_field(
        "Patient",
        "custom_panel_customer",
        "Panel Customer",
        "Link",
        insert_after="custom_patient_billing_type",
        options="Customer",
        hidden=1,
        read_only=1,
        depends_on="eval:doc.custom_patient_billing_type=='Panel'",
    )

    _ensure_custom_field(
        "Patient",
        "custom_latest_welfare_registration",
        "Latest Welfare Registration",
        "Link",
        insert_after="custom_panel_customer",
        options="Patient Registration Form",
        hidden=0,
        read_only=1,
        depends_on="eval:doc.custom_patient_billing_type=='Welfare'",
    )

    _ensure_custom_field(
        "Patient",
        "custom_welfare_type",
        "Welfare Type",
        "Select",
        insert_after="custom_latest_welfare_registration",
        options="\nZakat\nDonation",
        hidden=0,
        read_only=1,
        depends_on="eval:doc.custom_patient_billing_type=='Welfare'",
    )

    _ensure_custom_field(
        "Patient",
        "custom_welfare_percentage",
        "Welfare Percentage",
        "Percent",
        insert_after="custom_welfare_type",
        hidden=0,
        read_only=1,
        depends_on="eval:doc.custom_patient_billing_type=='Welfare'",
    )

    # --------------------------------------------------
    # Patient Registration Form / Welfare fields
    # --------------------------------------------------
    _ensure_custom_field(
        "Patient Registration Form",
        "custom_kpws_panel_assignment_tab",
        "Panel Assignment",
        "Tab Break",
        insert_after="contact_no",
        hidden=0,
        read_only=0,
    )

    _ensure_custom_field(
        "Patient Registration Form",
        "custom_kpws_assigned_panel_customer",
        "Assigned Panel Customer",
        "Link",
        insert_after="custom_kpws_panel_assignment_tab",
        options="Customer",
        hidden=0,
        read_only=0,
    )

    _ensure_custom_field(
        "Patient Registration Form",
        "custom_kpws_admin_notes",
        "Additional Information / Administrator Notes",
        "Small Text",
        insert_after="purpose",
        hidden=0,
        read_only=0,
    )

    # --------------------------------------------------
    # Customer panel field
    # --------------------------------------------------
    _ensure_custom_field(
        "Customer",
        "custom_is_panel",
        "Is Panel",
        "Check",
        insert_after="customer_group",
        hidden=0,
        read_only=0,
    )

    frappe.db.commit()

    # --------------------------------------------------
    # Keep ERPNext core intact; sync only custom-field columns.
    # updatedb is the framework way. Direct column fallback is only for missing custom columns.
    # --------------------------------------------------
    for dt in ["Patient", "Patient Registration Form", "Customer"]:
        try:
            frappe.db.updatedb(dt)
            print("updatedb completed:", dt)
        except Exception as e:
            print("updatedb warning:", dt, e)

    _add_column_if_missing("tabPatient", "custom_patient_billing_type", "varchar(140)")
    _add_column_if_missing("tabPatient", "custom_panel_customer", "varchar(140)")
    _add_column_if_missing("tabPatient", "custom_latest_welfare_registration", "varchar(140)")
    _add_column_if_missing("tabPatient", "custom_welfare_type", "varchar(140)")
    _add_column_if_missing("tabPatient", "custom_welfare_percentage", "decimal(21,9) NOT NULL DEFAULT 0")

    _add_column_if_missing("tabPatient Registration Form", "custom_kpws_assigned_panel_customer", "varchar(140)")
    _add_column_if_missing("tabPatient Registration Form", "custom_kpws_admin_notes", "text")
    _add_column_if_missing("tabPatient Registration Form", "custom_patient", "varchar(140)")
    _add_column_if_missing("tabPatient Registration Form", "custom_mr_number", "varchar(140)")
    _add_column_if_missing("tabPatient Registration Form", "custom_patient_customer", "varchar(140)")
    _add_column_if_missing("tabPatient Registration Form", "custom_billing_type", "varchar(140)")

    _add_column_if_missing("tabCustomer", "custom_is_panel", "int(1) NOT NULL DEFAULT 0")

    frappe.db.commit()

    # --------------------------------------------------
    # UI properties
    # --------------------------------------------------
    if frappe.get_meta("Patient").get_field("customer_group"):
        _set_field_property("Patient", "customer_group", "hidden", 1, "Check")
        _set_field_property("Patient", "customer_group", "reqd", 0, "Check")
        _set_field_property("Patient", "customer_group", "read_only", 1, "Check")

    if frappe.get_meta("Patient").get_field("panel_name"):
        _set_field_property("Patient", "panel_name", "hidden", 0, "Check")
        _set_field_property(
            "Patient",
            "panel_name",
            "depends_on",
            "eval:doc.custom_patient_billing_type=='Panel'",
            "Data",
        )
        _set_field_property(
            "Patient",
            "panel_name",
            "mandatory_depends_on",
            "eval:doc.custom_patient_billing_type=='Panel'",
            "Data",
        )

    for fieldname in ["mr_no", "patient_full_name"]:
        if frappe.get_meta("Patient Registration Form").get_field(fieldname):
            _set_field_property("Patient Registration Form", fieldname, "read_only", 1, "Check")

    # --------------------------------------------------
    # Disable older conflicting UI scripts
    # --------------------------------------------------
    for script_name in [
        "KPWS - Patient Quick Add Panel",
        "KPWS - Patient Panel Name Customer Filter",
        "KPWS - Patient Panel Group Restriction",
        "KPWS - Force Hide Panel Fields on PRF",
        "KPWS - Patient Registration Panel Filter",
        "KPWS - Show Assigned Panel on PRF",
        "KPWS - Step1 Patient Strict Panel Lookup",
        "KPWS - Step1 PRF Strict Panel Lookup",
    ]:
        _disable_client_script(script_name)

    # --------------------------------------------------
    # New strict Patient script
    # --------------------------------------------------
    patient_script = r"""
frappe.ui.form.on("Patient", {
    setup: function(frm) {
        kpws_patient_apply_panel_query(frm);
    },

    onload: function(frm) {
        kpws_patient_apply_panel_query(frm);
        kpws_patient_apply_billing_ui(frm);
    },

    refresh: function(frm) {
        kpws_patient_apply_panel_query(frm);
        kpws_patient_apply_billing_ui(frm);

        if (!frm.is_new() && (frm.doc.custom_patient_billing_type || frm.doc.customer_group) === "Welfare") {
            frm.add_custom_button(__("Create Welfare Registration"), function() {
                frappe.call({
                    method: "kpws_customization.api.kpws_step1_patient_welfare.create_or_open_welfare_registration",
                    args: { patient: frm.doc.name },
                    freeze: true,
                    freeze_message: __("Creating Welfare Registration..."),
                    callback: function(r) {
                        if (r.message && r.message.name) {
                            frappe.set_route("Form", "Patient Registration Form", r.message.name);
                        }
                    }
                });
            }, __("KPWS"));
        }
    },

    custom_patient_billing_type: function(frm) {
        var billing_type = frm.doc.custom_patient_billing_type || "Cash";

        if (frm.fields_dict.customer_group) {
            frm.set_value("customer_group", billing_type);
        }

        if (billing_type === "Cash") {
            if (frm.fields_dict.panel_name) frm.set_value("panel_name", "");
            if (frm.fields_dict.custom_panel_customer) frm.set_value("custom_panel_customer", "");
        }

        kpws_patient_apply_panel_query(frm);
        kpws_patient_apply_billing_ui(frm);
    },

    panel_name: function(frm) {
        if (frm.fields_dict.custom_panel_customer) {
            frm.set_value("custom_panel_customer", frm.doc.panel_name || "");
        }
    },

    custom_panel_customer: function(frm) {
        if (frm.fields_dict.panel_name && frm.doc.custom_panel_customer) {
            frm.set_value("panel_name", frm.doc.custom_panel_customer);
        }
    },

    before_save: function(frm) {
        if (frm.fields_dict.customer_group) {
            frm.set_value("customer_group", frm.doc.custom_patient_billing_type || frm.doc.customer_group || "Cash");
        }
    }
});

function kpws_patient_apply_panel_query(frm) {
    ["panel_name", "custom_panel_customer"].forEach(function(fieldname) {
        if (!frm.fields_dict[fieldname]) return;

        frm.set_query(fieldname, function() {
            return {
                query: "kpws_customization.api.kpws_step1_patient_welfare.get_panel_customers"
            };
        });
    });
}

function kpws_patient_apply_billing_ui(frm) {
    var billing_type = frm.doc.custom_patient_billing_type || frm.doc.customer_group || "Cash";

    if (frm.fields_dict.customer_group) {
        frm.set_df_property("customer_group", "hidden", 1);
        frm.set_df_property("customer_group", "reqd", 0);
        frm.set_df_property("customer_group", "read_only", 1);
    }

    if (frm.fields_dict.custom_patient_billing_type) {
        frm.set_df_property("custom_patient_billing_type", "hidden", 0);
        frm.set_df_property("custom_patient_billing_type", "reqd", 1);
        frm.set_df_property("custom_patient_billing_type", "options", "\nCash\nWelfare\nPanel");
    }

    ["panel_name", "custom_panel_customer"].forEach(function(fieldname) {
        if (!frm.fields_dict[fieldname]) return;
        frm.set_df_property(fieldname, "hidden", billing_type !== "Panel");
        frm.set_df_property(fieldname, "reqd", billing_type === "Panel");
    });

    ["custom_latest_welfare_registration", "custom_welfare_type", "custom_welfare_percentage"].forEach(function(fieldname) {
        if (!frm.fields_dict[fieldname]) return;
        frm.set_df_property(fieldname, "hidden", billing_type !== "Welfare");
        frm.set_df_property(fieldname, "read_only", 1);
    });
}
"""

    prf_script = r"""
frappe.ui.form.on("Patient Registration Form", {
    setup: function(frm) {
        kpws_prf_apply_panel_query(frm);
    },

    onload: function(frm) {
        kpws_prf_apply_panel_query(frm);
    },

    refresh: function(frm) {
        kpws_prf_apply_panel_query(frm);
    }
});

function kpws_prf_apply_panel_query(frm) {
    ["custom_kpws_assigned_panel_customer", "custom_assigned_panel", "custom_panel_customer", "custom_panel"].forEach(function(fieldname) {
        if (!frm.fields_dict[fieldname]) return;

        frm.set_query(fieldname, function() {
            return {
                query: "kpws_customization.api.kpws_step1_patient_welfare.get_panel_customers"
            };
        });
    });
}
"""

    _upsert_client_script("KPWS - Core Safe Patient Billing Flow", "Patient", patient_script)
    _upsert_client_script("KPWS - Core Safe PRF Panel Filter", "Patient Registration Form", prf_script)

    frappe.db.commit()

    for dt in ["Patient", "Patient Registration Form", "Customer"]:
        frappe.clear_cache(doctype=dt)

    frappe.clear_cache()

    print("KPWS core-safe Step 1 repair completed.")
    return "OK"
