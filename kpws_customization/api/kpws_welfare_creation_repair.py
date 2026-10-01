import frappe


def _set_field_property(dt, fieldname, prop, value, property_type="Data"):
    # If field is Custom Field, change Custom Field directly.
    rows = frappe.get_all(
        "Custom Field",
        filters={"dt": dt, "fieldname": fieldname},
        fields=["name"],
        limit_page_length=100,
    )

    if rows:
        for r in rows:
            cf = frappe.get_doc("Custom Field", r.name)
            if hasattr(cf, prop):
                setattr(cf, prop, value)
                cf.save(ignore_permissions=True)
        return

    # If standard DocField, use Property Setter.
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
    ps.property_type = property_type
    ps.value = str(value)

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

    print("Upserted Client Script:", name)


def apply():
    print("Applying welfare creation repair...")

    # These should NOT be mandatory at Reception creation time.
    # Administrator approval will validate them later.
    for fieldname in ["discount_value", "discount_type", "purpose"]:
        _set_field_property("Patient Registration Form", fieldname, "reqd", 0, "Check")

    # Keep these auto-filled and read-only for Reception.
    for fieldname in ["patient_name", "mr_no", "patient_full_name"]:
        if frappe.get_meta("Patient Registration Form").get_field(fieldname):
            _set_field_property("Patient Registration Form", fieldname, "read_only", 1, "Check")

    # Update Patient button behavior so existing welfare registration gives clear message.
    patient_script = r"""
frappe.ui.form.on("Patient", {
    setup(frm) {
        kpws_patient_welfare_query(frm);
    },

    onload(frm) {
        kpws_patient_welfare_query(frm);
        kpws_patient_welfare_ui(frm);
    },

    refresh(frm) {
        kpws_patient_welfare_query(frm);
        kpws_patient_welfare_ui(frm);

        if (!frm.is_new() && (frm.doc.custom_patient_billing_type || frm.doc.customer_group) === "Welfare") {
            frm.add_custom_button(__("Create Welfare Registration"), function() {
                frappe.call({
                    method: "kpws_customization.api.kpws_step1_patient_welfare.create_or_open_welfare_registration",
                    args: { patient: frm.doc.name },
                    freeze: true,
                    freeze_message: __("Checking Welfare Registration..."),
                    callback(r) {
                        if (!r.message) return;

                        if (r.message.existing) {
                            frappe.msgprint({
                                title: __("Welfare Registration Already Exists"),
                                indicator: "orange",
                                message: __("Welfare Registration <b>{0}</b> already exists for this patient. Please contact Administrator if any changes are required.", [r.message.name])
                            });
                            return;
                        }

                        if (r.message.name) {
                            frappe.show_alert({
                                message: __("Welfare Registration created."),
                                indicator: "green"
                            });
                            frappe.set_route("Form", "Patient Registration Form", r.message.name);
                        }
                    }
                });
            }, __("KPWS"));
        }
    },

    custom_patient_billing_type(frm) {
        const billing_type = frm.doc.custom_patient_billing_type || "Cash";

        if (frm.fields_dict.customer_group) {
            frm.set_value("customer_group", billing_type);
        }

        if (billing_type === "Cash") {
            if (frm.fields_dict.panel_name) frm.set_value("panel_name", "");
            if (frm.fields_dict.custom_panel_customer) frm.set_value("custom_panel_customer", "");
        }

        kpws_patient_welfare_query(frm);
        kpws_patient_welfare_ui(frm);
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

function kpws_patient_welfare_query(frm) {
    ["panel_name", "custom_panel_customer"].forEach(function(fieldname) {
        if (!frm.fields_dict[fieldname]) return;

        frm.set_query(fieldname, function() {
            return {
                query: "kpws_customization.api.kpws_step1_patient_welfare.get_panel_customers"
            };
        });
    });
}

function kpws_patient_welfare_ui(frm) {
    const billing_type = frm.doc.custom_patient_billing_type || frm.doc.customer_group || "Cash";

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

    _upsert_client_script("KPWS - Clean Patient Billing Form", "Patient", patient_script)

    frappe.db.commit()

    for dt in ["Patient", "Patient Registration Form", "Customer"]:
        frappe.clear_cache(doctype=dt)

    frappe.clear_cache()

    print("Welfare creation repair applied.")
    return "OK"
