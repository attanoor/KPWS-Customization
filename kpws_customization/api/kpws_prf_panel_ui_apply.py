import frappe


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

    print("Upserted Client Script:", name)


def _disable_old_scripts():
    # Keep the latest clean script name only.
    for script_name in [
        "KPWS - HARD PRF Panel Filter",
        "KPWS - Core Safe PRF Panel Filter",
        "KPWS - Step1 PRF Strict Panel Lookup",
        "KPWS - Patient Registration Panel Filter",
        "KPWS - Force Hide Panel Fields on PRF",
        "KPWS - Show Assigned Panel on PRF",
    ]:
        if frappe.db.exists("Client Script", script_name):
            frappe.db.set_value("Client Script", script_name, "enabled", 0)
            print("Disabled old PRF script:", script_name)


def apply():
    _disable_old_scripts()

    script = r"""
frappe.ui.form.on("Patient Registration Form", {
    setup(frm) {
        kpws_prf_panel_setup_queries(frm);
    },

    onload(frm) {
        kpws_prf_panel_setup_queries(frm);
        kpws_prf_panel_apply_ui(frm);
        kpws_prf_panel_render_box(frm);
    },

    refresh(frm) {
        kpws_prf_panel_setup_queries(frm);
        kpws_prf_panel_apply_ui(frm);
        kpws_prf_panel_render_box(frm);
        kpws_prf_panel_add_buttons(frm);
    },

    custom_kpws_assigned_panel_customer(frm) {
        kpws_prf_panel_render_box(frm);
    }
});

function kpws_prf_panel_is_admin() {
    const roles = frappe.user_roles || [];
    return frappe.session.user === "Administrator"
        || roles.includes("System Manager")
        || roles.includes("Healthcare Manager")
        || roles.includes("Welfare Manager");
}

function kpws_prf_panel_setup_queries(frm) {
    if (frm.fields_dict.custom_kpws_assigned_panel_customer) {
        frm.set_query("custom_kpws_assigned_panel_customer", function() {
            return {
                query: "kpws_customization.api.kpws_prf_panel_tools.search_panel_customers"
            };
        });
    }
}

function kpws_prf_panel_inject_css() {
    if ($("#kpws-prf-panel-style").length) return;

    $("head").append(`
        <style id="kpws-prf-panel-style">
            .kpws-prf-enhanced .frappe-control[data-fieldname="custom_kpws_assigned_panel_customer"] {
                display: inline-block;
                width: calc(50% - 12px);
                vertical-align: top;
                margin-right: 12px;
            }

            .kpws-prf-enhanced .frappe-control[data-fieldname="purpose"],
            .kpws-prf-enhanced .frappe-control[data-fieldname="discount_type"],
            .kpws-prf-enhanced .frappe-control[data-fieldname="discount_value"],
            .kpws-prf-enhanced .frappe-control[data-fieldname="cnic"],
            .kpws-prf-enhanced .frappe-control[data-fieldname="contact_no"],
            .kpws-prf-enhanced .frappe-control[data-fieldname="religion1"],
            .kpws-prf-enhanced .frappe-control[data-fieldname="saction1"],
            .kpws-prf-enhanced .frappe-control[data-fieldname="nationality"],
            .kpws-prf-enhanced .frappe-control[data-fieldname="swo"] {
                display: inline-block;
                width: calc(50% - 12px);
                vertical-align: top;
                margin-right: 12px;
            }

            .kpws-prf-enhanced .frappe-control[data-fieldname="address"],
            .kpws-prf-enhanced .frappe-control[data-fieldname="custom_kpws_admin_notes"],
            .kpws-prf-enhanced .frappe-control[data-fieldname="custom_kpws_panel_actions_html"],
            .kpws-prf-enhanced .frappe-control[data-fieldname="custom_kpws_patient_snapshot_html"] {
                width: 100%;
                display: block;
            }

            .kpws-panel-card {
                border: 1px solid var(--border-color);
                border-radius: 12px;
                padding: 14px;
                margin: 8px 0 16px 0;
                background: var(--bg-color);
            }

            .kpws-panel-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 12px;
                margin-bottom: 10px;
            }

            .kpws-panel-title {
                font-weight: 700;
                font-size: 15px;
            }

            .kpws-panel-subtitle {
                font-size: 12px;
                opacity: .7;
                margin-top: 2px;
            }

            .kpws-panel-status {
                padding: 7px 10px;
                border-radius: 999px;
                border: 1px solid var(--border-color);
                font-size: 12px;
                font-weight: 600;
                background: var(--control-bg);
            }

            .kpws-panel-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(220px, 1fr));
                gap: 10px;
                margin-top: 10px;
            }

            .kpws-panel-kv {
                border: 1px solid var(--border-color);
                border-radius: 10px;
                padding: 10px;
                background: var(--control-bg);
            }

            .kpws-panel-kv .label {
                font-size: 11px;
                opacity: .7;
                margin-bottom: 4px;
            }

            .kpws-panel-kv .value {
                font-size: 13px;
                font-weight: 600;
                word-break: break-word;
            }

            .kpws-panel-actions {
                margin-top: 12px;
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
            }

            @media (max-width: 900px) {
                .kpws-panel-grid {
                    grid-template-columns: 1fr;
                }

                .kpws-prf-enhanced .frappe-control[data-fieldname] {
                    width: 100% !important;
                    margin-right: 0 !important;
                }
            }
        </style>
    `);
}

function kpws_escape(v) {
    if (v === undefined || v === null || v === "") return "—";
    return frappe.utils.escape_html(String(v));
}

function kpws_prf_panel_apply_ui(frm) {
    kpws_prf_panel_inject_css();

    if (frm.page && frm.page.wrapper) {
        $(frm.page.wrapper).addClass("kpws-prf-enhanced");
    }

    const admin = kpws_prf_panel_is_admin();

    if (frm.fields_dict.custom_kpws_assigned_panel_customer) {
        frm.set_df_property("custom_kpws_assigned_panel_customer", "hidden", 0);
        frm.set_df_property("custom_kpws_assigned_panel_customer", "read_only", admin ? 0 : 1);
        frm.set_df_property("custom_kpws_assigned_panel_customer", "label", "Assigned Panel Customer");
    }

    if (frm.fields_dict.custom_kpws_panel_actions_html) {
        frm.set_df_property("custom_kpws_panel_actions_html", "hidden", 0);
    }

    [
        "custom_assigned_panel",
        "custom_panel_customer",
        "custom_panel",
        "custom_kpws_panel_assignment_tab"
    ].forEach(function(fieldname) {
        if (!frm.fields_dict[fieldname]) return;
        frm.set_df_property(fieldname, "hidden", 1);
        frm.set_df_property(fieldname, "read_only", 1);
        frm.set_df_property(fieldname, "reqd", 0);
    });
}

function kpws_prf_panel_render_box(frm) {
    if (!frm.fields_dict.custom_kpws_panel_actions_html) return;

    const panel = frm.doc.custom_kpws_assigned_panel_customer;
    const is_admin = kpws_prf_panel_is_admin();

    const html = `
        <div class="kpws-panel-card">
            <div class="kpws-panel-header">
                <div>
                    <div class="kpws-panel-title">Panel Assignment</div>
                    <div class="kpws-panel-subtitle">
                        Only Customers marked as <b>Is Panel</b> will be available for assignment.
                    </div>
                </div>
                <div class="kpws-panel-status">
                    ${panel ? "Assigned" : "Not Assigned"}
                </div>
            </div>

            <div class="kpws-panel-grid">
                <div class="kpws-panel-kv">
                    <div class="label">Assigned Panel Customer</div>
                    <div class="value">${kpws_escape(panel)}</div>
                </div>
                <div class="kpws-panel-kv">
                    <div class="label">Permission</div>
                    <div class="value">${is_admin ? "Administrator can assign/create panel" : "Read-only"}</div>
                </div>
            </div>

            ${is_admin ? `
                <div class="kpws-panel-actions">
                    <button class="btn btn-xs btn-primary" type="button" id="kpws-assign-existing-panel">
                        Assign Existing Panel
                    </button>
                    <button class="btn btn-xs btn-default" type="button" id="kpws-create-panel-customer">
                        Create New Panel Customer
                    </button>
                </div>
            ` : ""}
        </div>
    `;

    frm.fields_dict.custom_kpws_panel_actions_html.$wrapper.html(html);

    setTimeout(function() {
        $("#kpws-assign-existing-panel").off("click").on("click", function() {
            kpws_prf_open_assign_panel_dialog(frm);
        });

        $("#kpws-create-panel-customer").off("click").on("click", function() {
            kpws_prf_open_create_panel_dialog(frm);
        });
    }, 100);
}

function kpws_prf_panel_add_buttons(frm) {
    if (frm.is_new()) return;
    if (!kpws_prf_panel_is_admin()) return;

    frm.add_custom_button(__("Assign Existing Panel"), function() {
        kpws_prf_open_assign_panel_dialog(frm);
    }, __("Panel"));

    frm.add_custom_button(__("Create New Panel Customer"), function() {
        kpws_prf_open_create_panel_dialog(frm);
    }, __("Panel"));
}

function kpws_prf_open_assign_panel_dialog(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __("Assign Existing Panel"),
        fields: [
            {
                fieldname: "panel_customer",
                label: __("Panel Customer"),
                fieldtype: "Link",
                options: "Customer",
                reqd: 1,
                get_query: function() {
                    return {
                        query: "kpws_customization.api.kpws_prf_panel_tools.search_panel_customers"
                    };
                }
            }
        ],
        primary_action_label: __("Assign Panel"),
        primary_action(values) {
            frappe.call({
                method: "kpws_customization.api.kpws_prf_panel_tools.assign_panel_to_welfare_registration",
                args: {
                    prf_name: frm.doc.name,
                    panel_customer: values.panel_customer
                },
                freeze: true,
                freeze_message: __("Assigning Panel..."),
                callback() {
                    frappe.show_alert({ message: __("Panel assigned."), indicator: "green" });
                    dialog.hide();
                    frm.reload_doc();
                }
            });
        }
    });

    dialog.show();
}

function kpws_prf_open_create_panel_dialog(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __("Create New Panel Customer"),
        fields: [
            {
                fieldname: "customer_name",
                label: __("Panel / Customer Name"),
                fieldtype: "Data",
                reqd: 1
            },
            {
                fieldname: "customer_group",
                label: __("Customer Group"),
                fieldtype: "Link",
                options: "Customer Group",
                default: "Panel"
            },
            {
                fieldname: "territory",
                label: __("Territory"),
                fieldtype: "Link",
                options: "Territory",
                default: "Pakistan"
            },
            {
                fieldname: "mobile_no",
                label: __("Mobile No"),
                fieldtype: "Data"
            },
            {
                fieldname: "email_id",
                label: __("Email"),
                fieldtype: "Data",
                options: "Email"
            }
        ],
        primary_action_label: __("Create & Assign"),
        primary_action(values) {
            frappe.call({
                method: "kpws_customization.api.kpws_prf_panel_tools.create_panel_customer",
                args: values,
                freeze: true,
                freeze_message: __("Creating Panel Customer..."),
                callback(r) {
                    if (!r.message || !r.message.customer) return;

                    frappe.call({
                        method: "kpws_customization.api.kpws_prf_panel_tools.assign_panel_to_welfare_registration",
                        args: {
                            prf_name: frm.doc.name,
                            panel_customer: r.message.customer
                        },
                        freeze: true,
                        freeze_message: __("Assigning Panel..."),
                        callback() {
                            frappe.show_alert({ message: __("Panel Customer created and assigned."), indicator: "green" });
                            dialog.hide();
                            frm.reload_doc();
                        }
                    });
                }
            });
        }
    });

    dialog.show();
}
"""

    _upsert_client_script("KPWS - Clean Welfare Registration Form", "Patient Registration Form", script)

    frappe.db.commit()
    frappe.clear_cache(doctype="Patient Registration Form")
    frappe.clear_cache(doctype="Customer")
    frappe.clear_cache()

    print("Improved PRF panel UI applied.")
    return "OK"
