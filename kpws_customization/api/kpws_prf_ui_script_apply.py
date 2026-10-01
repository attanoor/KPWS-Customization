import frappe


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


def disable_old_scripts():
    for script_name in [
        "KPWS - HARD PRF Panel Filter",
        "KPWS - Core Safe PRF Panel Filter",
        "KPWS - Clean Welfare Registration Form",
        "KPWS - Step1 PRF Strict Panel Lookup",
        "KPWS - Patient Registration Panel Filter",
        "KPWS - Force Hide Panel Fields on PRF",
        "KPWS - Show Assigned Panel on PRF",
    ]:
        if frappe.db.exists("Client Script", script_name):
            frappe.db.set_value("Client Script", script_name, "enabled", 0)
            print("Disabled old PRF script:", script_name)


def apply():
    disable_old_scripts()

    script = r"""
frappe.ui.form.on("Patient Registration Form", {
    setup(frm) {
        kpws_prf_setup_queries(frm);
    },

    onload(frm) {
        kpws_prf_setup_queries(frm);
        kpws_prf_apply_clean_ui(frm);
        kpws_prf_render_patient_info(frm);
    },

    refresh(frm) {
        kpws_prf_setup_queries(frm);
        kpws_prf_apply_clean_ui(frm);
        kpws_prf_render_patient_info(frm);
        kpws_prf_add_buttons(frm);
    }
});

function kpws_prf_is_admin() {
    const roles = frappe.user_roles || [];
    return frappe.session.user === "Administrator"
        || roles.includes("System Manager")
        || roles.includes("Healthcare Manager")
        || roles.includes("Welfare Manager");
}

function kpws_prf_setup_queries(frm) {
    ["custom_kpws_assigned_panel_customer"].forEach(function(fieldname) {
        if (!frm.fields_dict[fieldname]) return;

        frm.set_query(fieldname, function() {
            return {
                query: "kpws_customization.api.kpws_step1_patient_welfare.get_panel_customers"
            };
        });
    });
}

function kpws_prf_inject_css(frm) {
    if ($("#kpws-prf-clean-style").length) return;

    $("head").append(`
        <style id="kpws-prf-clean-style">
            .kpws-prf-clean .frappe-control[data-fieldname="cnic"],
            .kpws-prf-clean .frappe-control[data-fieldname="contact_no"],
            .kpws-prf-clean .frappe-control[data-fieldname="religion1"],
            .kpws-prf-clean .frappe-control[data-fieldname="saction1"],
            .kpws-prf-clean .frappe-control[data-fieldname="nationality"],
            .kpws-prf-clean .frappe-control[data-fieldname="swo"],
            .kpws-prf-clean .frappe-control[data-fieldname="purpose"],
            .kpws-prf-clean .frappe-control[data-fieldname="discount_type"],
            .kpws-prf-clean .frappe-control[data-fieldname="discount_value"],
            .kpws-prf-clean .frappe-control[data-fieldname="custom_kpws_assigned_panel_customer"] {
                display: inline-block;
                width: calc(50% - 14px);
                vertical-align: top;
                margin-right: 14px;
            }

            .kpws-prf-clean .frappe-control[data-fieldname="address"],
            .kpws-prf-clean .frappe-control[data-fieldname="custom_kpws_admin_notes"],
            .kpws-prf-clean .frappe-control[data-fieldname="custom_kpws_patient_snapshot_html"] {
                display: block;
                width: 100%;
            }

            .kpws-patient-card {
                border: 1px solid var(--border-color);
                border-radius: 10px;
                padding: 14px;
                margin: 8px 0 16px 0;
                background: var(--bg-color);
            }

            .kpws-patient-card-title {
                font-weight: 700;
                font-size: 15px;
                margin-bottom: 10px;
            }

            .kpws-patient-grid {
                display: grid;
                grid-template-columns: repeat(3, minmax(180px, 1fr));
                gap: 10px;
            }

            .kpws-patient-kv {
                padding: 8px 10px;
                border: 1px solid var(--border-color);
                border-radius: 8px;
                background: var(--control-bg);
                min-height: 54px;
            }

            .kpws-patient-kv .label {
                font-size: 11px;
                opacity: 0.75;
                margin-bottom: 4px;
            }

            .kpws-patient-kv .value {
                font-size: 13px;
                font-weight: 600;
                word-break: break-word;
            }

            @media (max-width: 900px) {
                .kpws-patient-grid {
                    grid-template-columns: repeat(1, minmax(180px, 1fr));
                }

                .kpws-prf-clean .frappe-control[data-fieldname] {
                    width: 100% !important;
                    margin-right: 0 !important;
                }
            }
        </style>
    `);
}

function kpws_prf_apply_clean_ui(frm) {
    kpws_prf_inject_css(frm);

    if (frm.page && frm.page.wrapper) {
        $(frm.page.wrapper).addClass("kpws-prf-clean");
    }

    const admin = kpws_prf_is_admin();

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

    ["patient_name", "mr_no", "patient_full_name"].forEach(function(fieldname) {
        if (!frm.fields_dict[fieldname]) return;
        frm.set_df_property(fieldname, "hidden", 0);
        frm.set_df_property(fieldname, "read_only", 1);
    });

    ["cnic", "contact_no", "address", "religion1", "saction1", "nationality", "swo"].forEach(function(fieldname) {
        if (!frm.fields_dict[fieldname]) return;
        frm.set_df_property(fieldname, "hidden", 0);
        frm.set_df_property(fieldname, "read_only", admin ? 0 : 1);
    });

    ["purpose", "discount_type", "discount_value", "custom_kpws_assigned_panel_customer", "custom_kpws_admin_notes"].forEach(function(fieldname) {
        if (!frm.fields_dict[fieldname]) return;
        frm.set_df_property(fieldname, "hidden", 0);
        frm.set_df_property(fieldname, "read_only", admin ? 0 : 1);
        frm.set_df_property(fieldname, "reqd", 0);
    });

    if (frm.fields_dict.workflow_state) {
        frm.set_df_property("workflow_state", "read_only", 1);
    }
}

function kpws_escape(v) {
    if (v === undefined || v === null || v === "") return "—";
    return frappe.utils.escape_html(String(v));
}

function kpws_prf_render_patient_info(frm) {
    if (!frm.fields_dict.custom_kpws_patient_snapshot_html) return;
    if (!frm.doc.name) return;

    frappe.call({
        method: "kpws_customization.api.kpws_prf_patient_info.get_patient_snapshot",
        args: { prf_name: frm.doc.name },
        callback(r) {
            const d = r.message || {};

            if (!d.found) {
                frm.fields_dict.custom_kpws_patient_snapshot_html.$wrapper.html(
                    `<div class="kpws-patient-card">
                        <div class="kpws-patient-card-title">Patient Information</div>
                        <div>No linked Patient found.</div>
                    </div>`
                );
                return;
            }

            const items = [
                ["MR No", d.mr_no],
                ["Patient Name", d.patient_name],
                ["Billing Type", d.billing_type],
                ["Panel", d.panel_customer],
                ["Customer", d.customer],
                ["Gender", d.sex],
                ["DOB", d.dob],
                ["Blood Group", d.blood_group],
                ["CNIC", d.cnic],
                ["Mobile", d.mobile],
                ["Phone", d.phone],
                ["Email", d.email],
                ["Religion", d.religion1],
                ["Saction", d.saction1],
                ["Nationality", d.nationality],
                ["S/O W/O", d.swo],
                ["Address", d.address]
            ];

            const html = `
                <div class="kpws-patient-card">
                    <div class="kpws-patient-card-title">Patient Information from Patient Master</div>
                    <div class="kpws-patient-grid">
                        ${items.map(([label, value]) => `
                            <div class="kpws-patient-kv">
                                <div class="label">${kpws_escape(label)}</div>
                                <div class="value">${kpws_escape(value)}</div>
                            </div>
                        `).join("")}
                    </div>
                </div>
            `;

            frm.fields_dict.custom_kpws_patient_snapshot_html.$wrapper.html(html);
        }
    });
}

function kpws_prf_add_buttons(frm) {
    if (frm.is_new()) return;

    if (frm.doc.patient_name) {
        frm.add_custom_button(__("Open Patient"), function() {
            frappe.set_route("Form", "Patient", frm.doc.patient_name);
        }, __("KPWS"));
    }

    frm.add_custom_button(__("Refresh from Patient"), function() {
        frappe.call({
            method: "kpws_customization.api.kpws_prf_patient_info.refresh_prf_from_patient",
            args: { prf_name: frm.doc.name },
            freeze: true,
            freeze_message: __("Refreshing Patient Information..."),
            callback() {
                frappe.show_alert({ message: __("Patient information refreshed."), indicator: "green" });
                frm.reload_doc();
            }
        });
    }, __("KPWS"));

    if (kpws_prf_is_admin()) {
        frm.add_custom_button(__("Update Patient Information"), function() {
            kpws_prf_open_update_patient_dialog(frm);
        }, __("KPWS"));

        frm.add_custom_button(__("Approve Welfare Registration"), function() {
            frappe.call({
                method: "kpws_customization.api.kpws_step1_patient_welfare.approve_welfare_registration",
                args: { prf_name: frm.doc.name },
                freeze: true,
                freeze_message: __("Approving Welfare Registration..."),
                callback() {
                    frappe.show_alert({ message: __("Welfare Registration approved."), indicator: "green" });
                    frm.reload_doc();
                }
            });
        }, __("KPWS"));
    }
}

function kpws_prf_open_update_patient_dialog(frm) {
    frappe.call({
        method: "kpws_customization.api.kpws_prf_patient_info.get_patient_snapshot",
        args: { prf_name: frm.doc.name },
        callback(r) {
            const d = r.message || {};

            if (!d.found) {
                frappe.msgprint(__("Linked Patient not found."));
                return;
            }

            const dialog = new frappe.ui.Dialog({
                title: __("Update Patient Information"),
                fields: [
                    { fieldname: "patient_name", label: __("Patient Name"), fieldtype: "Data", default: d.patient_name },
                    { fieldname: "mr_no", label: __("MR No"), fieldtype: "Data", default: d.mr_no },
                    { fieldname: "sex", label: __("Gender"), fieldtype: "Data", default: d.sex },
                    { fieldname: "dob", label: __("Date of Birth"), fieldtype: "Date", default: d.dob },
                    { fieldname: "blood_group", label: __("Blood Group"), fieldtype: "Data", default: d.blood_group },
                    { fieldname: "mobile", label: __("Mobile"), fieldtype: "Data", default: d.mobile },
                    { fieldname: "phone", label: __("Phone"), fieldtype: "Data", default: d.phone },
                    { fieldname: "email", label: __("Email"), fieldtype: "Data", default: d.email },
                    { fieldname: "cnic", label: __("CNIC"), fieldtype: "Data", default: d.cnic },
                    { fieldname: "religion1", label: __("Religion"), fieldtype: "Data", default: d.religion1 },
                    { fieldname: "saction1", label: __("Saction"), fieldtype: "Data", default: d.saction1 },
                    { fieldname: "nationality", label: __("Nationality"), fieldtype: "Data", default: d.nationality },
                    { fieldname: "swo", label: __("S/O W/O"), fieldtype: "Data", default: d.swo },
                    { fieldname: "address", label: __("Address"), fieldtype: "Small Text", default: d.address }
                ],
                primary_action_label: __("Update Patient"),
                primary_action(values) {
                    frappe.call({
                        method: "kpws_customization.api.kpws_prf_patient_info.update_patient_from_prf",
                        args: {
                            prf_name: frm.doc.name,
                            values: values
                        },
                        freeze: true,
                        freeze_message: __("Updating Patient Information..."),
                        callback() {
                            frappe.show_alert({ message: __("Patient information updated."), indicator: "green" });
                            dialog.hide();
                            frm.reload_doc();
                        }
                    });
                }
            });

            dialog.show();
        }
    });
}
"""

    upsert_client_script("KPWS - Clean Welfare Registration Form", "Patient Registration Form", script)

    frappe.db.commit()
    frappe.clear_cache(doctype="Patient Registration Form")
    frappe.clear_cache()
    print("Clean PRF client script applied.")
    return "OK"
