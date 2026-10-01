import frappe

CLIENT_SCRIPT_NAME = "KPWS FINAL Unified Sales Invoice Flow"


def install_stable_client_script():
    if not frappe.db.exists("DocType", "Client Script"):
        return

    # Disable all Sales Invoice client scripts except the one stable script.
    for row in frappe.get_all("Client Script", filters={"dt": "Sales Invoice"}, fields=["name"]):
        if row.name != CLIENT_SCRIPT_NAME:
            frappe.db.set_value("Client Script", row.name, "enabled", 0, update_modified=False)
            print("Disabled:", row.name)

    script = r'''
frappe.ui.form.on("Sales Invoice", {
    setup(frm) {
        kpws_si_setup(frm);
    },
    onload(frm) {
        kpws_si_apply_later(frm);
    },
    refresh(frm) {
        kpws_si_setup(frm);
        kpws_si_apply_later(frm);
    },
    patient(frm) {
        kpws_si_apply_now(frm, true);
    },
    custom_kpws_mr_number(frm) {
        kpws_si_apply_now(frm, true);
    },
    customer(frm) {
        kpws_si_apply_now(frm, true);
    },
    custom_is_walkin(frm) {
        kpws_si_toggle(frm);
        kpws_si_apply_now(frm, true);
    },
    before_save(frm) {
        return kpws_si_apply_now(frm, false);
    },
    validate(frm) {
        return kpws_si_apply_now(frm, false);
    }
});

function kpws_si_has(frm, fieldname) {
    return frm.fields_dict && frm.fields_dict[fieldname];
}

function kpws_si_setup(frm) {
    ["custom_kpws_billing_type", "custom_panel", "custom_kpws_welfare_registration", "custom_kpws_welfare_type", "custom_kpws_welfare_percentage", "selling_price_list"].forEach(function(f) {
        if (kpws_si_has(frm, f)) {
            frm.set_df_property(f, "read_only", 1);
        }
    });

    kpws_si_toggle(frm);
}

function kpws_si_toggle(frm) {
    let walkin = !!frm.doc.custom_is_walkin;

    ["walkin_customer_name", "walkin_mr_number"].forEach(function(f) {
        if (kpws_si_has(frm, f)) {
            frm.toggle_display(f, walkin);
            frm.toggle_reqd(f, walkin);
        }
    });

    ["custom_kpws_mr_number", "patient"].forEach(function(f) {
        if (kpws_si_has(frm, f)) {
            frm.toggle_display(f, !walkin);
        }
    });
}

function kpws_si_apply_later(frm) {
    clearTimeout(frm.__kpws_si_timer);
    frm.__kpws_si_timer = setTimeout(function() {
        kpws_si_apply_now(frm, false);
    }, 700);
}

function kpws_si_apply_now(frm, show_loader) {
    if (frm.__kpws_si_running) {
        return Promise.resolve();
    }

    if (!frm.doc.patient && !frm.doc.customer && !frm.doc.custom_kpws_mr_number && !frm.doc.custom_is_walkin) {
        if (kpws_si_has(frm, "is_pos")) frm.set_value("is_pos", 1);
        if (kpws_si_has(frm, "set_warehouse")) frm.set_value("set_warehouse", "Pharmacy - KPWS");
        return Promise.resolve();
    }

    frm.__kpws_si_running = true;

    if (show_loader) {
        frappe.dom.freeze(__("Loading KPWS billing profile..."));
    }

    return new Promise(function(resolve) {
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

                if (kpws_si_has(frm, "is_pos")) updates.is_pos = 1;
                if (kpws_si_has(frm, "set_warehouse")) updates.set_warehouse = d.warehouse || "Pharmacy - KPWS";

                if (d.patient && kpws_si_has(frm, "patient") && frm.doc.patient !== d.patient) updates.patient = d.patient;
                if (d.mr_number && kpws_si_has(frm, "custom_kpws_mr_number") && !frm.doc.custom_is_walkin) updates.custom_kpws_mr_number = d.mr_number;
                if (d.customer && frm.doc.customer !== d.customer) updates.customer = d.customer;

                if (kpws_si_has(frm, "patient_name")) updates.patient_name = d.patient_name || "";
                if (kpws_si_has(frm, "custom_kpws_billing_type")) updates.custom_kpws_billing_type = d.patient_type || "";
                if (kpws_si_has(frm, "custom_panel")) updates.custom_panel = d.panel_customer || "";
                if (kpws_si_has(frm, "custom_kpws_panel_customer")) updates.custom_kpws_panel_customer = d.panel_customer || "";
                if (kpws_si_has(frm, "custom_kpws_welfare_registration")) updates.custom_kpws_welfare_registration = d.welfare_registration || "";
                if (kpws_si_has(frm, "custom_kpws_welfare_type")) updates.custom_kpws_welfare_type = d.welfare_type || "";
                if (kpws_si_has(frm, "custom_kpws_welfare_percentage")) updates.custom_kpws_welfare_percentage = d.welfare_percentage || 0;
                if (kpws_si_has(frm, "pos_profile") && d.pos_profile) updates.pos_profile = d.pos_profile;
                if (kpws_si_has(frm, "selling_price_list") && d.selling_price_list) updates.selling_price_list = d.selling_price_list;

                frm.set_value(updates).then(function() {
                    kpws_si_toggle(frm);
                    frm.refresh_fields();
                    frm.__kpws_si_running = false;
                    if (show_loader) frappe.dom.unfreeze();
                    resolve();
                });
            },
            error: function() {
                frm.__kpws_si_running = false;
                if (show_loader) frappe.dom.unfreeze();
                resolve();
            }
        });
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
        print("Updated stable Sales Invoice script")
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": CLIENT_SCRIPT_NAME,
            "dt": "Sales Invoice",
            "view": "Form",
            "enabled": 1,
            "script": script,
        }).insert(ignore_permissions=True)
        print("Created stable Sales Invoice script")


def install():
    install_stable_client_script()
    frappe.db.commit()
    frappe.clear_cache()
    print("DONE: Heavy payment JS removed. Server will handle payment rows on save.")
