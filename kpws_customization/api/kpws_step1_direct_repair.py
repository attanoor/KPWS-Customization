import frappe


def column_exists(table, column):
    rows = frappe.db.sql(f"SHOW COLUMNS FROM `{table}`", as_dict=True)
    return column in {r["Field"] for r in rows}


def add_column(table, column, definition):
    if not column_exists(table, column):
        frappe.db.sql(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {definition}")
        print("Added column:", table, column)
    else:
        print("Column already exists:", table, column)


def ensure_custom_field(dt, fieldname, label, fieldtype, insert_after=None, options=None, **kwargs):
    existing = frappe.db.exists("Custom Field", {"dt": dt, "fieldname": fieldname})

    if existing:
        doc = frappe.get_doc("Custom Field", existing)
    else:
        doc = frappe.new_doc("Custom Field")
        doc.dt = dt
        doc.fieldname = fieldname

    doc.label = label
    doc.fieldtype = fieldtype

    if insert_after:
        doc.insert_after = insert_after

    if options is not None:
        doc.options = options

    for k, v in kwargs.items():
        if hasattr(doc, k):
            setattr(doc, k, v)

    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)

    return doc.name


def upsert_client_script(name, dt, script):
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

    print("Upserted Client Script:", name)


def apply():
    print("Starting direct repair...")

    # --------------------------------------------------
    # 1. Ensure Custom Fields exist
    # --------------------------------------------------
    ensure_custom_field(
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

    ensure_custom_field(
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

    ensure_custom_field(
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

    ensure_custom_field(
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

    ensure_custom_field(
        "Patient",
        "custom_welfare_percentage",
        "Welfare Percentage",
        "Percent",
        insert_after="custom_welfare_type",
        hidden=0,
        read_only=1,
        depends_on="eval:doc.custom_patient_billing_type=='Welfare'",
    )

    ensure_custom_field(
        "Patient Registration Form",
        "custom_kpws_assigned_panel_customer",
        "Assigned Panel Customer",
        "Link",
        insert_after="contact_no",
        options="Customer",
        hidden=0,
        read_only=0,
    )

    ensure_custom_field(
        "Patient Registration Form",
        "custom_kpws_admin_notes",
        "Additional Information / Administrator Notes",
        "Small Text",
        insert_after="purpose",
        hidden=0,
        read_only=0,
    )

    ensure_custom_field(
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
    # 2. Force database columns
    # --------------------------------------------------
    add_column("tabPatient", "custom_patient_billing_type", "varchar(140)")
    add_column("tabPatient", "custom_panel_customer", "varchar(140)")
    add_column("tabPatient", "custom_latest_welfare_registration", "varchar(140)")
    add_column("tabPatient", "custom_welfare_type", "varchar(140)")
    add_column("tabPatient", "custom_welfare_percentage", "decimal(21,9) NOT NULL DEFAULT 0")

    add_column("tabPatient Registration Form", "custom_kpws_assigned_panel_customer", "varchar(140)")
    add_column("tabPatient Registration Form", "custom_kpws_admin_notes", "text")
    add_column("tabPatient Registration Form", "custom_patient", "varchar(140)")
    add_column("tabPatient Registration Form", "custom_mr_number", "varchar(140)")
    add_column("tabPatient Registration Form", "custom_patient_customer", "varchar(140)")
    add_column("tabPatient Registration Form", "custom_billing_type", "varchar(140)")

    add_column("tabCustomer", "custom_is_panel", "int(1) NOT NULL DEFAULT 0")

    frappe.db.commit()

    # --------------------------------------------------
    # 3. Disable old conflicting Patient/PRF scripts
    # --------------------------------------------------
    for script_name in [
        "KPWS - Patient Quick Add Panel",
        "KPWS - Patient Panel Name Customer Filter",
        "KPWS - Patient Panel Group Restriction",
        "KPWS - Force Hide Panel Fields on PRF",
        "KPWS - Patient Registration Panel Filter",
        "KPWS - Show Assigned Panel on PRF",
    ]:
        if frappe.db.exists("Client Script", script_name):
            frappe.db.set_value("Client Script", script_name, "enabled", 0)
            print("Disabled old Client Script:", script_name)

    # --------------------------------------------------
    # 4. Force strict panel lookup via DB Client Script
    # --------------------------------------------------
    patient_script = r"""
frappe.ui.form.on("Patient", {
    setup: function(frm) {
        kpws_apply_patient_panel_filter(frm);
    },
    onload: function(frm) {
        kpws_apply_patient_panel_filter(frm);
        kpws_apply_patient_billing_ui(frm);
    },
    refresh: function(frm) {
        kpws_apply_patient_panel_filter(frm);
        kpws_apply_patient_billing_ui(frm);

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
        if (frm.fields_dict.customer_group) {
            frm.set_value("customer_group", frm.doc.custom_patient_billing_type || "Cash");
        }

        if (frm.doc.custom_patient_billing_type === "Cash") {
            if (frm.fields_dict.panel_name) frm.set_value("panel_name", "");
            if (frm.fields_dict.custom_panel_customer) frm.set_value("custom_panel_customer", "");
        }

        kpws_apply_patient_panel_filter(frm);
        kpws_apply_patient_billing_ui(frm);
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

function kpws_apply_patient_panel_filter(frm) {
    ["panel_name", "custom_panel_customer"].forEach(function(fieldname) {
        if (!frm.fields_dict[fieldname]) return;

        frm.set_query(fieldname, function() {
            return {
                query: "kpws_customization.api.kpws_step1_patient_welfare.get_panel_customers"
            };
        });
    });
}

function kpws_apply_patient_billing_ui(frm) {
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
        kpws_apply_prf_panel_filter(frm);
    },
    onload: function(frm) {
        kpws_apply_prf_panel_filter(frm);
    },
    refresh: function(frm) {
        kpws_apply_prf_panel_filter(frm);
    }
});

function kpws_apply_prf_panel_filter(frm) {
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

    upsert_client_script("KPWS - HARD Patient Panel Filter", "Patient", patient_script)
    upsert_client_script("KPWS - HARD PRF Panel Filter", "Patient Registration Form", prf_script)

    frappe.db.commit()

    for dt in ["Patient", "Patient Registration Form", "Customer"]:
        frappe.clear_cache(doctype=dt)

    frappe.clear_cache()

    print("Direct repair completed successfully.")
    return "OK"
