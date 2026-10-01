import frappe


def _table_column_exists(table, column):
    rows = frappe.db.sql(f"SHOW COLUMNS FROM `{table}`", as_dict=True)
    return column in {r["Field"] for r in rows}


def _add_column_if_missing(table, column, definition):
    if not _table_column_exists(table, column):
        frappe.db.sql(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {definition}")
        print("Added missing custom column:", table, column)


def _custom_fields(dt, fieldname):
    return frappe.get_all(
        "Custom Field",
        filters={"dt": dt, "fieldname": fieldname},
        fields=["name"],
        order_by="creation asc",
        limit_page_length=100,
    )


def _ensure_custom_field(dt, fieldname, label, fieldtype, insert_after=None, options=None, **props):
    rows = _custom_fields(dt, fieldname)

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

        for k, v in props.items():
            if hasattr(cf, k):
                setattr(cf, k, v)

        if cf.is_new():
            cf.insert(ignore_permissions=True)
        else:
            cf.save(ignore_permissions=True)

    return names[0] if names[0] else cf.name


def _set_field_property(dt, fieldname, prop, value, property_type="Data"):
    rows = _custom_fields(dt, fieldname)

    if rows:
        for row in rows:
            cf = frappe.get_doc("Custom Field", row.name)
            if hasattr(cf, prop):
                setattr(cf, prop, value)
                cf.save(ignore_permissions=True)
        return

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


def _hide_field(dt, fieldname):
    if frappe.get_meta(dt).get_field(fieldname) or _custom_fields(dt, fieldname):
        _set_field_property(dt, fieldname, "hidden", 1, "Check")
        _set_field_property(dt, fieldname, "reqd", 0, "Check")
        _set_field_property(dt, fieldname, "read_only", 1, "Check")
        print("Hidden:", dt, fieldname)


def _show_field(dt, fieldname, read_only=None, reqd=None, label=None):
    if not (frappe.get_meta(dt).get_field(fieldname) or _custom_fields(dt, fieldname)):
        return

    _set_field_property(dt, fieldname, "hidden", 0, "Check")

    if read_only is not None:
        _set_field_property(dt, fieldname, "read_only", 1 if read_only else 0, "Check")

    if reqd is not None:
        _set_field_property(dt, fieldname, "reqd", 1 if reqd else 0, "Check")

    if label:
        _set_field_property(dt, fieldname, "label", label, "Data")

    print("Visible:", dt, fieldname)


def _disable_client_script(name):
    if frappe.db.exists("Client Script", name):
        frappe.db.set_value("Client Script", name, "enabled", 0)
        print("Disabled Client Script:", name)


def _upsert_client_script(name, dt, script):
    existing = frappe.db.exists("Client Script", name)

    if existing:
        doc = frappe.get_doc("Client Script", existing)
    else:
        doc = frappe.new_doc("Client Script")
        doc.name = name
        doc.dt = dt
        doc.view = "Form"

    doc.dt = dt
    doc.view = "Form"
    doc.enabled = 1
    doc.script = script

    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)

    print("Enabled Client Script:", name)


def _clean_panel_flags_from_kpws_panel():
    """
    Stop polluted panel list:
    - uncheck custom_is_panel from all customers
    - re-check only customers linked in KPWS Panel
    This does not delete customers.
    """
    if not frappe.get_meta("Customer").get_field("custom_is_panel"):
        return

    frappe.db.sql("""
        UPDATE `tabCustomer`
        SET custom_is_panel = 0
        WHERE IFNULL(custom_is_panel, 0) = 1
    """)

    count = 0

    if frappe.db.exists("DocType", "KPWS Panel"):
        panels = frappe.get_all(
            "KPWS Panel",
            fields=["name", "customer", "panel_name"],
            limit_page_length=10000,
        )

        for p in panels:
            if p.customer and frappe.db.exists("Customer", p.customer):
                frappe.db.set_value("Customer", p.customer, "custom_is_panel", 1, update_modified=False)
                count += 1

    print("Reset Is Panel flags. KPWS Panel linked customers checked:", count)


def apply():
    print("Starting KPWS form cleanup...")

    # --------------------------------------------------
    # Ensure only required custom fields exist.
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

    _ensure_custom_field(
        "Patient Registration Form",
        "custom_kpws_assigned_panel_customer",
        "Assigned Panel Customer",
        "Link",
        insert_after="contact_no",
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

    frappe.db.commit()

    # Framework schema sync first.
    for dt in ["Customer", "Patient", "Patient Registration Form"]:
        try:
            frappe.db.updatedb(dt)
            print("updatedb OK:", dt)
        except Exception as e:
            print("updatedb warning:", dt, e)

    # Fallback only for custom columns that are already intended.
    _add_column_if_missing("tabCustomer", "custom_is_panel", "int(1) NOT NULL DEFAULT 0")

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

    frappe.db.commit()

    # --------------------------------------------------
    # Patient form cleanup.
    # --------------------------------------------------
    _show_field("Patient", "custom_patient_billing_type", read_only=False, reqd=True, label="Patient Billing Type")

    # Old field remains internally for compatibility but hidden from users.
    _hide_field("Patient", "customer_group")

    if frappe.get_meta("Patient").get_field("panel_name"):
        _show_field("Patient", "panel_name", read_only=False, reqd=False, label="Panel Name")
        _set_field_property("Patient", "panel_name", "depends_on", "eval:doc.custom_patient_billing_type=='Panel'", "Data")
        _set_field_property("Patient", "panel_name", "mandatory_depends_on", "eval:doc.custom_patient_billing_type=='Panel'", "Data")

    _hide_field("Patient", "custom_panel_customer")
    _show_field("Patient", "custom_latest_welfare_registration", read_only=True, reqd=False)
    _show_field("Patient", "custom_welfare_type", read_only=True, reqd=False)
    _show_field("Patient", "custom_welfare_percentage", read_only=True, reqd=False)

    # --------------------------------------------------
    # Patient Registration Form cleanup.
    # Keep existing real fields. Hide duplicate new fields.
    # --------------------------------------------------
    for fieldname in [
        # duplicate/new fields shown in wrong places
        "custom_assistance_type",
        "custom_approval_remarks",
        "custom_coverage_percentage",
        "custom_review_status",
        "actual_patient_name",
        "custom_patient",
        "custom_mr_number",
        "custom_patient_customer",
        "custom_billing_type",
        "custom_panel",
        "custom_assigned_panel",
        "custom_panel_customer",
        "custom_patient_section",
        "custom_auto_filled_patient_details",
        "custom_kpws_panel_assignment_tab",
    ]:
        _hide_field("Patient Registration Form", fieldname)

    # Keep proper existing form fields visible/read-only where needed.
    _show_field("Patient Registration Form", "patient_name", read_only=True, reqd=True, label="Patient")
    _show_field("Patient Registration Form", "mr_no", read_only=True, reqd=True, label="MR No")
    _show_field("Patient Registration Form", "patient_full_name", read_only=True, reqd=True, label="Patient Full Name")

    # Contact/admin review fields.
    for fieldname in [
        "cnic",
        "contact_no",
        "address",
        "religion1",
        "saction1",
        "nationality",
    ]:
        if frappe.get_meta("Patient Registration Form").get_field(fieldname):
            _show_field("Patient Registration Form", fieldname, read_only=False, reqd=False)

    _show_field("Patient Registration Form", "custom_kpws_assigned_panel_customer", read_only=False, reqd=False, label="Assigned Panel Customer")

    # Use existing real discount fields. Do not show duplicate Assistance/Coverage fields.
    _show_field("Patient Registration Form", "purpose", read_only=False, reqd=True, label="Purpose / Fund Type")
    _show_field("Patient Registration Form", "discount_type", read_only=False, reqd=True, label="Discount Type")
    _show_field("Patient Registration Form", "discount_value", read_only=False, reqd=True, label="Coverage / Discount Value")
    _show_field("Patient Registration Form", "custom_kpws_admin_notes", read_only=False, reqd=False, label="Additional Information / Administrator Notes")

    if frappe.get_meta("Patient Registration Form").get_field("workflow_state"):
        _show_field("Patient Registration Form", "workflow_state", read_only=True, reqd=False, label="Review Status")

    # --------------------------------------------------
    # Disable conflicting old scripts.
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
        "KPWS - HARD Patient Panel Filter",
        "KPWS - HARD PRF Panel Filter",
        "KPWS - Core Safe Patient Billing Flow",
        "KPWS - Core Safe PRF Panel Filter",
    ]:
        _disable_client_script(script_name)

    # --------------------------------------------------
    # Clean polluted panel customer flags.
    # This is why patient names were appearing in Panel dropdown.
    # --------------------------------------------------
    _clean_panel_flags_from_kpws_panel()

    # --------------------------------------------------
    # Clean single Patient script.
    # --------------------------------------------------
    patient_script = r"""
frappe.ui.form.on("Patient", {
    setup(frm) {
        kpws_patient_clean_set_queries(frm);
    },

    onload(frm) {
        kpws_patient_clean_set_queries(frm);
        kpws_patient_clean_ui(frm);
    },

    refresh(frm) {
        kpws_patient_clean_set_queries(frm);
        kpws_patient_clean_ui(frm);

        if (!frm.is_new() && (frm.doc.custom_patient_billing_type || frm.doc.customer_group) === "Welfare") {
            frm.add_custom_button(__("Create Welfare Registration"), function() {
                frappe.call({
                    method: "kpws_customization.api.kpws_step1_patient_welfare.create_or_open_welfare_registration",
                    args: { patient: frm.doc.name },
                    freeze: true,
                    freeze_message: __("Creating Welfare Registration..."),
                    callback(r) {
                        if (r.message && r.message.name) {
                            frappe.set_route("Form", "Patient Registration Form", r.message.name);
                        }
                    }
                });
            }, __("KPWS"));
        }
    },

    custom_patient_billing_type(frm) {
        let billing_type = frm.doc.custom_patient_billing_type || "Cash";

        if (frm.fields_dict.customer_group) {
            frm.set_value("customer_group", billing_type);
        }

        if (billing_type === "Cash") {
            if (frm.fields_dict.panel_name) frm.set_value("panel_name", "");
            if (frm.fields_dict.custom_panel_customer) frm.set_value("custom_panel_customer", "");
        }

        kpws_patient_clean_set_queries(frm);
        kpws_patient_clean_ui(frm);
    },

    panel_name(frm) {
        if (frm.fields_dict.custom_panel_customer) {
            frm.set_value("custom_panel_customer", frm.doc.panel_name || "");
        }
    },

    before_save(frm) {
        if (frm.fields_dict.customer_group) {
            frm.set_value("customer_group", frm.doc.custom_patient_billing_type || frm.doc.customer_group || "Cash");
        }
    }
});

function kpws_patient_clean_set_queries(frm) {
    ["panel_name", "custom_panel_customer"].forEach(function(fieldname) {
        if (!frm.fields_dict[fieldname]) return;

        frm.set_query(fieldname, function() {
            return {
                query: "kpws_customization.api.kpws_step1_patient_welfare.get_panel_customers"
            };
        });
    });
}

function kpws_patient_clean_ui(frm) {
    let billing_type = frm.doc.custom_patient_billing_type || frm.doc.customer_group || "Cash";

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

    if (frm.fields_dict.panel_name) {
        frm.set_df_property("panel_name", "hidden", billing_type !== "Panel");
        frm.set_df_property("panel_name", "reqd", billing_type === "Panel");
    }

    if (frm.fields_dict.custom_panel_customer) {
        frm.set_df_property("custom_panel_customer", "hidden", 1);
        frm.set_df_property("custom_panel_customer", "read_only", 1);
    }

    ["custom_latest_welfare_registration", "custom_welfare_type", "custom_welfare_percentage"].forEach(function(fieldname) {
        if (!frm.fields_dict[fieldname]) return;
        frm.set_df_property(fieldname, "hidden", billing_type !== "Welfare");
        frm.set_df_property(fieldname, "read_only", 1);
    });
}
"""

    # --------------------------------------------------
    # Clean single PRF script.
    # --------------------------------------------------
    prf_script = r"""
frappe.ui.form.on("Patient Registration Form", {
    setup(frm) {
        kpws_prf_clean_set_queries(frm);
    },

    onload(frm) {
        kpws_prf_clean_set_queries(frm);
        kpws_prf_clean_ui(frm);
    },

    refresh(frm) {
        kpws_prf_clean_set_queries(frm);
        kpws_prf_clean_ui(frm);

        if (frm.doc.patient_name) {
            frm.add_custom_button(__("Open Patient"), function() {
                frappe.set_route("Form", "Patient", frm.doc.patient_name);
            }, __("KPWS"));
        }

        if (frappe.user.has_role("Administrator") || frappe.user.has_role("System Manager") || frappe.user.has_role("Healthcare Manager") || frappe.user.has_role("Welfare Manager")) {
            frm.add_custom_button(__("Approve Welfare Registration"), function() {
                frappe.call({
                    method: "kpws_customization.api.kpws_step1_patient_welfare.approve_welfare_registration",
                    args: { prf_name: frm.doc.name },
                    freeze: true,
                    freeze_message: __("Approving Welfare Registration..."),
                    callback() {
                        frm.reload_doc();
                    }
                });
            }, __("KPWS"));
        }
    }
});

function kpws_prf_clean_set_queries(frm) {
    ["custom_kpws_assigned_panel_customer"].forEach(function(fieldname) {
        if (!frm.fields_dict[fieldname]) return;

        frm.set_query(fieldname, function() {
            return {
                query: "kpws_customization.api.kpws_step1_patient_welfare.get_panel_customers"
            };
        });
    });
}

function kpws_prf_clean_ui(frm) {
    // Hide duplicate fields from earlier patches/old scripts.
    [
        "custom_assistance_type",
        "custom_approval_remarks",
        "custom_coverage_percentage",
        "custom_review_status",
        "actual_patient_name",
        "custom_patient",
        "custom_mr_number",
        "custom_patient_customer",
        "custom_billing_type",
        "custom_panel",
        "custom_assigned_panel",
        "custom_panel_customer",
        "custom_patient_section",
        "custom_auto_filled_patient_details",
        "custom_kpws_panel_assignment_tab"
    ].forEach(function(fieldname) {
        if (!frm.fields_dict[fieldname]) return;
        frm.set_df_property(fieldname, "hidden", 1);
        frm.set_df_property(fieldname, "reqd", 0);
        frm.set_df_property(fieldname, "read_only", 1);
    });

    // Auto-filled patient fields.
    ["patient_name", "mr_no", "patient_full_name"].forEach(function(fieldname) {
        if (!frm.fields_dict[fieldname]) return;
        frm.set_df_property(fieldname, "hidden", 0);
        frm.set_df_property(fieldname, "read_only", 1);
    });

    // Admin-review fields.
    ["purpose", "discount_type", "discount_value", "custom_kpws_admin_notes", "custom_kpws_assigned_panel_customer"].forEach(function(fieldname) {
        if (!frm.fields_dict[fieldname]) return;
        frm.set_df_property(fieldname, "hidden", 0);
    });
}
"""

    _upsert_client_script("KPWS - Clean Patient Billing Form", "Patient", patient_script)
    _upsert_client_script("KPWS - Clean Welfare Registration Form", "Patient Registration Form", prf_script)

    frappe.db.commit()

    for dt in ["Patient", "Patient Registration Form", "Customer"]:
        frappe.clear_cache(doctype=dt)

    frappe.clear_cache()

    print("KPWS form cleanup completed.")
    return "OK"
