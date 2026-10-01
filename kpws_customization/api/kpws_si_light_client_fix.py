import frappe

CLIENT_SCRIPT_NAME = "KPWS FINAL Light Sales Invoice Client"


def install():
    if not frappe.db.exists("DocType", "Client Script"):
        return

    # Disable every Sales Invoice client script. We will keep only one lightweight script.
    for row in frappe.get_all("Client Script", filters={"dt": "Sales Invoice"}, fields=["name"]):
        if row.name != CLIENT_SCRIPT_NAME:
            frappe.db.set_value("Client Script", row.name, "enabled", 0, update_modified=False)
            print("Disabled Sales Invoice Client Script:", row.name)

    script = r'''
frappe.ui.form.on("Sales Invoice", {
    setup(frm) {
        kpws_light_setup(frm);
    },

    onload(frm) {
        kpws_light_setup(frm);
        kpws_light_set_static_defaults(frm);
    },

    refresh(frm) {
        kpws_light_setup(frm);
        kpws_light_set_static_defaults(frm);
    },

    patient(frm) {
        kpws_light_load_context(frm, true);
    },

    custom_kpws_mr_number(frm) {
        kpws_light_load_context(frm, true);
    },

    customer(frm) {
        kpws_light_load_context(frm, true);
    },

    custom_is_walkin(frm) {
        kpws_light_toggle_walkin(frm);
        kpws_light_load_context(frm, true);
    },

    walkin_customer_name(frm) {
        if (frm.doc.custom_is_walkin) {
            kpws_light_load_context(frm, false);
        }
    },

    walkin_mr_number(frm) {
        if (frm.doc.custom_is_walkin) {
            kpws_light_load_context(frm, false);
        }
    }
});

function kpws_light_has(frm, fieldname) {
    return frm.fields_dict && frm.fields_dict[fieldname];
}

function kpws_light_setup(frm) {
    [
        "custom_kpws_billing_type",
        "custom_panel",
        "custom_kpws_panel_customer",
        "custom_kpws_welfare_registration",
        "custom_kpws_welfare_type",
        "custom_kpws_welfare_percentage",
        "selling_price_list"
    ].forEach(function(fieldname) {
        if (kpws_light_has(frm, fieldname)) {
            frm.set_df_property(fieldname, "read_only", 1);
        }
    });

    kpws_light_toggle_walkin(frm);
}

function kpws_light_toggle_walkin(frm) {
    let is_walkin = !!frm.doc.custom_is_walkin;

    ["walkin_customer_name", "walkin_mr_number"].forEach(function(fieldname) {
        if (kpws_light_has(frm, fieldname)) {
            frm.toggle_display(fieldname, is_walkin);
            frm.toggle_reqd(fieldname, is_walkin);
        }
    });

    ["patient", "custom_kpws_mr_number"].forEach(function(fieldname) {
        if (kpws_light_has(frm, fieldname)) {
            frm.toggle_display(fieldname, !is_walkin);
        }
    });
}

function kpws_light_set_static_defaults(frm) {
    if (kpws_light_has(frm, "is_pos") && frm.doc.is_pos != 1) {
        frm.set_value("is_pos", 1);
    }

    if (kpws_light_has(frm, "set_warehouse") && frm.doc.set_warehouse !== "Pharmacy - KPWS") {
        frm.set_value("set_warehouse", "Pharmacy - KPWS");
    }
}

function kpws_light_load_context(frm, show_loader) {
    if (frm.__kpws_light_running) {
        return;
    }

    if (!frm.doc.patient && !frm.doc.customer && !frm.doc.custom_kpws_mr_number && !frm.doc.custom_is_walkin) {
        kpws_light_set_static_defaults(frm);
        return;
    }

    frm.__kpws_light_running = true;

    if (show_loader) {
        frappe.dom.freeze(__("Loading KPWS billing profile..."));
    }

    frappe.call({
        method: "kpws_customization.api.kpws_si_unified_flow.get_context",
        args: {
            patient: frm.doc.patient || "",
            mr_number: frm.doc.custom_kpws_mr_number || "",
            customer: frm.doc.customer || "",
            is_walkin: frm.doc.custom_is_walkin ? 1 : 0,
            walkin_name: frm.doc.walkin_customer_name || "",
            walkin_mr: frm.doc.walkin_mr_number || ""
        },
        freeze: false,
        callback: function(r) {
            let d = r.message || {};
            let updates = {};

            if (kpws_light_has(frm, "is_pos")) {
                updates.is_pos = 1;
            }

            if (kpws_light_has(frm, "set_warehouse")) {
                updates.set_warehouse = d.warehouse || "Pharmacy - KPWS";
            }

            if (d.patient && kpws_light_has(frm, "patient") && frm.doc.patient !== d.patient) {
                updates.patient = d.patient;
            }

            if (d.mr_number && kpws_light_has(frm, "custom_kpws_mr_number") && !frm.doc.custom_is_walkin) {
                updates.custom_kpws_mr_number = d.mr_number;
            }

            if (d.customer && frm.doc.customer !== d.customer) {
                updates.customer = d.customer;
            }

            if (kpws_light_has(frm, "patient_name")) {
                updates.patient_name = d.patient_name || "";
            }

            if (kpws_light_has(frm, "custom_kpws_billing_type")) {
                updates.custom_kpws_billing_type = d.patient_type || "";
            }

            if (kpws_light_has(frm, "custom_panel")) {
                updates.custom_panel = d.panel_customer || "";
            }

            if (kpws_light_has(frm, "custom_kpws_panel_customer")) {
                updates.custom_kpws_panel_customer = d.panel_customer || "";
            }

            if (kpws_light_has(frm, "custom_kpws_welfare_registration")) {
                updates.custom_kpws_welfare_registration = d.welfare_registration || "";
            }

            if (kpws_light_has(frm, "custom_kpws_welfare_type")) {
                updates.custom_kpws_welfare_type = d.welfare_type || "";
            }

            if (kpws_light_has(frm, "custom_kpws_welfare_percentage")) {
                updates.custom_kpws_welfare_percentage = d.welfare_percentage || 0;
            }

            if (kpws_light_has(frm, "pos_profile") && d.pos_profile) {
                updates.pos_profile = d.pos_profile;
            }

            if (kpws_light_has(frm, "selling_price_list") && d.selling_price_list) {
                updates.selling_price_list = d.selling_price_list;
            }

            frm.set_value(updates).then(function() {
                kpws_light_toggle_walkin(frm);
                frm.refresh_fields();
            });
        },
        error: function() {
            // Do not block save from client side. Server validation will show real error if any.
        },
        always: function() {
            frm.__kpws_light_running = false;

            if (show_loader) {
                frappe.dom.unfreeze();
            }
        }
    });
}
'''

    if frappe.db.exists("Client Script", CLIENT_SCRIPT_NAME):
        doc = frappe.get_doc("Client Script", CLIENT_SCRIPT_NAME)
        doc.enabled = 1
        doc.dt = "Sales Invoice"
        doc.view = "Form"
        doc.script = script
        doc.save(ignore_permissions=True)
        print("Updated:", CLIENT_SCRIPT_NAME)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": CLIENT_SCRIPT_NAME,
            "dt": "Sales Invoice",
            "view": "Form",
            "enabled": 1,
            "script": script,
        }).insert(ignore_permissions=True)
        print("Created:", CLIENT_SCRIPT_NAME)

    frappe.db.commit()
    frappe.clear_cache()

    print("")
    print("DONE: Installed lightweight Sales Invoice client script.")
    print("No async validate/before_save client script remains.")
