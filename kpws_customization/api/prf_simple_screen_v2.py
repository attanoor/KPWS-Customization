import frappe


CANDIDATE_DOCTYPES = [
    "Patient Registration Form",
    "Patient Registeration Form",
]


CLIENT_SCRIPT = r"""
(function () {
    const SIMPLE_HTML_FIELD = "custom_kpws_patient_snapshot_html";

    const HIDE_FIELDS = [
        "custom_kpws_welfare_type",
        "custom_kpws_welfare_percentage",
        "custom_patient",
        "form_no",
        "custom_mr_number",
        "custom_patient_name",
        "custom_patient_customer",
        "custom_billing_type",
        "custom_gender",
        "custom_dob",
        "custom_blood_group",
        "custom_patient_snapshot_html",
        "address",
        "purpose",
        "discount_value",
        "custom_panel_customer",
        "custom_kpws_admin_notes",
        "custom_kpws_assigned_panel_customer",
        "mr_no",
        "date",
        "patient_full_name",
        "swo",
        "cnic",
        "religion1",
        "saction1",
        "nationality",
        "contact_no",
        "discount_type",
        "remarks",
        "amended_from",
        "workflow_state"
    ];

    const state = {
        rendering: false,
        setting_controls_until: 0,
        fetching_patient: null,
        last_fetched_patient: null
    };

    function esc(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function is_setting_controls() {
        return Date.now() < state.setting_controls_until;
    }

    function get_form_wrapper(frm) {
        if (frm.$wrapper && frm.$wrapper.find) {
            return frm.$wrapper;
        }

        if (frm.wrapper) {
            return $(frm.wrapper);
        }

        return $();
    }

    function has_field(frm, fieldname) {
        return !!frm.fields_dict[fieldname];
    }

    function set_doc_value(frm, fieldname, value) {
        if (!has_field(frm, fieldname)) return;

        frm.doc[fieldname] = value || "";
        frm.refresh_field(fieldname);
        frm.dirty();
    }

    function get_doc_value(frm, fieldname) {
        return frm.doc[fieldname] || "";
    }

    function inject_css() {
        if (document.getElementById("kpws-prf-simple-css-v2")) return;

        const css = `
            .kpws-prf-desk {
                background: #fff;
                border: 1px solid #e5e7eb;
                border-radius: 16px;
                padding: 18px;
                margin: 8px 0 18px;
                box-shadow: 0 3px 16px rgba(15, 23, 42, 0.06);
            }

            .kpws-prf-header {
                display: flex;
                justify-content: space-between;
                gap: 16px;
                border-bottom: 1px solid #eef2f7;
                padding-bottom: 14px;
                margin-bottom: 16px;
            }

            .kpws-prf-title {
                font-size: 20px;
                font-weight: 800;
                color: #0f172a;
            }

            .kpws-prf-subtitle {
                margin-top: 5px;
                color: #64748b;
                font-size: 13px;
            }

            .kpws-prf-badge {
                border-radius: 999px;
                background: #f1f5f9;
                color: #334155;
                font-size: 12px;
                font-weight: 700;
                padding: 6px 10px;
                white-space: nowrap;
                height: fit-content;
            }

            .kpws-prf-section {
                border: 1px solid #e5e7eb;
                border-radius: 14px;
                padding: 14px;
                margin-bottom: 14px;
                background: #fcfcfd;
            }

            .kpws-prf-section-title {
                font-size: 14px;
                font-weight: 800;
                color: #0f172a;
                margin-bottom: 10px;
            }

            .kpws-prf-grid {
                display: grid;
                grid-template-columns: repeat(4, minmax(150px, 1fr));
                gap: 12px;
            }

            .kpws-prf-grid.two {
                grid-template-columns: repeat(2, minmax(220px, 1fr));
            }

            .kpws-prf-field label {
                display: block;
                font-size: 12px;
                font-weight: 700;
                color: #475569;
                margin-bottom: 5px;
            }

            .kpws-prf-field input,
            .kpws-prf-field select,
            .kpws-prf-field textarea {
                width: 100%;
                min-height: 38px;
                border: 1px solid #cbd5e1;
                border-radius: 10px;
                padding: 8px 10px;
                font-size: 13px;
                background: #fff;
                color: #0f172a;
            }

            .kpws-prf-field textarea {
                min-height: 76px;
                resize: vertical;
            }

            .kpws-prf-readonly {
                background: #f8fafc !important;
                color: #475569 !important;
            }

            .kpws-prf-actions {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-top: 14px;
            }

            .kpws-prf-btn {
                border: 0;
                border-radius: 10px;
                padding: 10px 14px;
                font-weight: 800;
                font-size: 13px;
                cursor: pointer;
            }

            .kpws-prf-btn.primary {
                background: #2563eb;
                color: #fff;
            }

            .kpws-prf-btn.success {
                background: #16a34a;
                color: #fff;
            }

            .kpws-prf-btn.dark {
                background: #0f172a;
                color: #fff;
            }

            .kpws-prf-btn.light {
                background: #f1f5f9;
                color: #0f172a;
            }

            .kpws-prf-alert {
                border: 1px dashed #cbd5e1;
                background: #f8fafc;
                color: #334155;
                border-radius: 12px;
                padding: 10px 12px;
                font-size: 13px;
                line-height: 1.45;
                margin-top: 10px;
            }

            @media (max-width: 1100px) {
                .kpws-prf-grid {
                    grid-template-columns: repeat(2, minmax(160px, 1fr));
                }
            }

            @media (max-width: 700px) {
                .kpws-prf-grid,
                .kpws-prf-grid.two {
                    grid-template-columns: 1fr;
                }

                .kpws-prf-header {
                    flex-direction: column;
                }
            }
        `;

        const style = document.createElement("style");
        style.id = "kpws-prf-simple-css-v2";
        style.innerHTML = css;
        document.head.appendChild(style);
    }

    function make_input(frm, label, fieldname, type, readonly) {
        const v = esc(get_doc_value(frm, fieldname));

        if (type === "textarea") {
            return `
                <div class="kpws-prf-field">
                    <label>${esc(label)}</label>
                    <textarea data-kpws-field="${esc(fieldname)}" ${readonly ? "readonly" : ""} class="${readonly ? "kpws-prf-readonly" : ""}">${v}</textarea>
                </div>
            `;
        }

        return `
            <div class="kpws-prf-field">
                <label>${esc(label)}</label>
                <input type="${type || "text"}" data-kpws-field="${esc(fieldname)}" value="${v}" ${readonly ? "readonly" : ""} class="${readonly ? "kpws-prf-readonly" : ""}">
            </div>
        `;
    }

    function make_select(frm, label, fieldname, options) {
        const current = get_doc_value(frm, fieldname);

        const opts = options.map(function (opt) {
            return `<option value="${esc(opt)}" ${current === opt ? "selected" : ""}>${esc(opt)}</option>`;
        }).join("");

        return `
            <div class="kpws-prf-field">
                <label>${esc(label)}</label>
                <select data-kpws-field="${esc(fieldname)}">
                    <option value=""></option>
                    ${opts}
                </select>
            </div>
        `;
    }

    function sync_duplicate_fields(frm) {
        if (frm.doc.purpose) {
            set_doc_value(frm, "custom_kpws_welfare_type", frm.doc.purpose);
        }

        if (frm.doc.discount_value !== undefined && frm.doc.discount_value !== null) {
            set_doc_value(frm, "custom_kpws_welfare_percentage", frm.doc.discount_value);
        }

        if (frm.doc.custom_panel_customer) {
            set_doc_value(frm, "custom_kpws_assigned_panel_customer", frm.doc.custom_panel_customer);
        }
    }

    function collect_inputs(frm) {
        if (!has_field(frm, SIMPLE_HTML_FIELD)) return;

        const wrapper = frm.fields_dict[SIMPLE_HTML_FIELD].$wrapper;

        wrapper.find("[data-kpws-field]").each(function () {
            const fieldname = $(this).attr("data-kpws-field");
            const val = $(this).val();

            if (fieldname && has_field(frm, fieldname)) {
                set_doc_value(frm, fieldname, val);
            }
        });

        sync_duplicate_fields(frm);
        frm.refresh_fields();
    }

    function hide_old_layout(frm) {
        HIDE_FIELDS.forEach(function (fieldname) {
            if (fieldname === SIMPLE_HTML_FIELD) return;

            if (has_field(frm, fieldname)) {
                frm.set_df_property(fieldname, "hidden", 1);
            }
        });

        const $wrapper = get_form_wrapper(frm);
        $wrapper.find(".form-tabs-list, .form-tabs, .form-tabs-wrapper").hide();
    }

    function show_advanced_layout(frm) {
        HIDE_FIELDS.forEach(function (fieldname) {
            if (has_field(frm, fieldname)) {
                frm.set_df_property(fieldname, "hidden", 0);
            }
        });

        const $wrapper = get_form_wrapper(frm);
        $wrapper.find(".form-tabs-list, .form-tabs, .form-tabs-wrapper").show();

        frappe.show_alert({
            message: "Advanced fields are now visible.",
            indicator: "blue"
        }, 8);
    }

    function fetch_patient_details(frm, patient) {
        if (!patient) return;

        if (state.fetching_patient === patient) {
            return;
        }

        if (state.last_fetched_patient === patient && frm.doc.custom_patient === patient && frm.doc.custom_patient_name) {
            return;
        }

        state.fetching_patient = patient;

        frappe.call({
            method: "kpws_customization.api.prf_simple_screen.get_patient_details",
            args: { patient: patient },
            freeze: false,
            callback: function (r) {
                const d = r.message || {};

                if (frm.doc.custom_patient !== patient) {
                    state.fetching_patient = null;
                    return;
                }

                set_doc_value(frm, "custom_mr_number", d.mr_number);
                set_doc_value(frm, "custom_patient_name", d.patient_name);
                set_doc_value(frm, "custom_patient_customer", d.patient_customer);
                set_doc_value(frm, "custom_billing_type", d.billing_type);
                set_doc_value(frm, "custom_gender", d.gender);
                set_doc_value(frm, "custom_dob", d.dob);
                set_doc_value(frm, "custom_blood_group", d.blood_group);

                if (d.contact_no && !frm.doc.contact_no) {
                    set_doc_value(frm, "contact_no", d.contact_no);
                }

                if (d.cnic && !frm.doc.cnic) {
                    set_doc_value(frm, "cnic", d.cnic);
                }

                if (d.panel_customer && !frm.doc.custom_panel_customer) {
                    set_doc_value(frm, "custom_panel_customer", d.panel_customer);
                    set_doc_value(frm, "custom_kpws_assigned_panel_customer", d.panel_customer);
                }

                state.last_fetched_patient = patient;
                state.fetching_patient = null;

                render_simple_screen(frm);
            },
            error: function () {
                state.fetching_patient = null;
            }
        });
    }

    function setup_link_controls(frm) {
        if (!has_field(frm, SIMPLE_HTML_FIELD)) return;

        const wrapper = frm.fields_dict[SIMPLE_HTML_FIELD].$wrapper;

        const patient_area = wrapper.find(".kpws-patient-link-control").empty();
        const panel_area = wrapper.find(".kpws-panel-link-control").empty();

        state.setting_controls_until = Date.now() + 1000;

        const patient_control = frappe.ui.form.make_control({
            parent: patient_area.get(0),
            df: {
                fieldtype: "Link",
                label: "Patient",
                fieldname: "kpws_simple_patient",
                options: "Patient",
                reqd: 1,
                onchange: function () {
                    if (is_setting_controls()) return;

                    const patient = patient_control.get_value();

                    if (!patient) {
                        set_doc_value(frm, "custom_patient", "");
                        return;
                    }

                    if (patient === frm.doc.custom_patient && state.last_fetched_patient === patient) {
                        return;
                    }

                    set_doc_value(frm, "custom_patient", patient);
                    fetch_patient_details(frm, patient);
                }
            },
            render_input: true
        });

        const panel_control = frappe.ui.form.make_control({
            parent: panel_area.get(0),
            df: {
                fieldtype: "Link",
                label: "Panel Customer",
                fieldname: "kpws_simple_panel_customer",
                options: "Customer",
                get_query: function () {
                    return {
                        query: "kpws_customization.api.kpws_patient_customer_rules.panel_customer_query"
                    };
                },
                onchange: function () {
                    if (is_setting_controls()) return;

                    const panel = panel_control.get_value();

                    set_doc_value(frm, "custom_panel_customer", panel);
                    set_doc_value(frm, "custom_kpws_assigned_panel_customer", panel);
                }
            },
            render_input: true
        });

        Promise.resolve(patient_control.set_value(frm.doc.custom_patient || "")).then(function () {
            return Promise.resolve(panel_control.set_value(frm.doc.custom_panel_customer || frm.doc.custom_kpws_assigned_panel_customer || ""));
        }).then(function () {
            setTimeout(function () {
                state.setting_controls_until = 0;
            }, 300);
        });
    }

    function render_simple_screen(frm) {
        if (state.rendering) return;
        if (!has_field(frm, SIMPLE_HTML_FIELD)) return;

        state.rendering = true;
        inject_css();

        const status = frm.doc.docstatus === 1 ? "Submitted" : (frm.is_new() ? "New Draft" : "Draft");

        const html = `
            <div class="kpws-prf-desk">
                <div class="kpws-prf-header">
                    <div>
                        <div class="kpws-prf-title">Patient Registration Desk</div>
                        <div class="kpws-prf-subtitle">
                            One-screen registration for patient details, welfare/panel assignment, percentage and remarks.
                        </div>
                    </div>
                    <div class="kpws-prf-badge">${esc(status)}</div>
                </div>

                <div class="kpws-prf-section">
                    <div class="kpws-prf-section-title">1. Patient Selection & Summary</div>

                    <div class="kpws-prf-grid">
                        <div class="kpws-prf-field">
                            <div class="kpws-patient-link-control"></div>
                        </div>
                        ${make_input(frm, "Form No", "form_no", "text", false)}
                        ${make_input(frm, "MR Number", "custom_mr_number", "text", true)}
                        ${make_input(frm, "Patient Type", "custom_billing_type", "text", true)}
                    </div>

                    <div class="kpws-prf-grid" style="margin-top:12px;">
                        ${make_input(frm, "Patient Name", "custom_patient_name", "text", false)}
                        ${make_input(frm, "Patient Customer", "custom_patient_customer", "text", true)}
                        ${make_input(frm, "Gender", "custom_gender", "text", false)}
                        ${make_input(frm, "Date of Birth", "custom_dob", "date", false)}
                    </div>

                    <div class="kpws-prf-grid" style="margin-top:12px;">
                        ${make_input(frm, "Blood Group", "custom_blood_group", "text", false)}
                        ${make_input(frm, "Contact No", "contact_no", "text", false)}
                        ${make_input(frm, "CNIC", "cnic", "text", false)}
                        ${make_input(frm, "S/W/O", "swo", "text", false)}
                    </div>
                </div>

                <div class="kpws-prf-section">
                    <div class="kpws-prf-section-title">2. Address & Identity Information</div>

                    <div class="kpws-prf-grid">
                        ${make_input(frm, "Religion", "religion1", "text", false)}
                        ${make_input(frm, "Sect / Saction", "saction1", "text", false)}
                        ${make_input(frm, "Nationality", "nationality", "text", false)}
                    </div>

                    <div class="kpws-prf-grid two" style="margin-top:12px;">
                        ${make_input(frm, "Address", "address", "textarea", false)}
                        ${make_input(frm, "General Remarks", "remarks", "textarea", false)}
                    </div>
                </div>

                <div class="kpws-prf-section">
                    <div class="kpws-prf-section-title">3. Welfare / Donation / Discount</div>

                    <div class="kpws-prf-grid">
                        ${make_select(frm, "Purpose", "purpose", ["Zakat", "Donation"])}
                        ${make_input(frm, "Approved Percentage", "discount_value", "number", false)}
                        ${make_select(frm, "Linked Welfare Type", "custom_kpws_welfare_type", ["Zakat", "Donation"])}
                        ${make_input(frm, "Linked Welfare Percentage", "custom_kpws_welfare_percentage", "number", false)}
                    </div>

                    <div class="kpws-prf-alert">
                        Use this section for welfare approval. Percentage will be used as the approved billing discount/coverage percentage.
                    </div>
                </div>

                <div class="kpws-prf-section">
                    <div class="kpws-prf-section-title">4. Panel Assignment</div>

                    <div class="kpws-prf-grid">
                        <div class="kpws-prf-field">
                            <div class="kpws-panel-link-control"></div>
                        </div>
                        ${make_input(frm, "Panel / Approved Percentage", "discount_value", "number", false)}
                    </div>

                    <div class="kpws-prf-alert">
                        For Panel patients, assign the panel customer here. The patient master can be updated from the button below.
                    </div>
                </div>

                <div class="kpws-prf-section">
                    <div class="kpws-prf-section-title">5. Admin Notes</div>

                    <div class="kpws-prf-grid two">
                        ${make_input(frm, "Admin Remarks", "custom_kpws_admin_notes", "textarea", false)}
                        ${make_input(frm, "Internal Remarks", "remarks", "textarea", false)}
                    </div>
                </div>

                <div class="kpws-prf-actions">
                    <button type="button" class="kpws-prf-btn primary" data-kpws-action="save">Save Draft</button>
                    <button type="button" class="kpws-prf-btn success" data-kpws-action="update_patient">Update Patient Details</button>
                    <button type="button" class="kpws-prf-btn dark" data-kpws-action="submit">Submit Registration</button>
                    <button type="button" class="kpws-prf-btn light" data-kpws-action="advanced">Show Advanced Fields</button>
                </div>
            </div>
        `;

        frm.fields_dict[SIMPLE_HTML_FIELD].$wrapper.html(html);

        setup_link_controls(frm);
        bind_events(frm);
        hide_old_layout(frm);

        state.rendering = false;
    }

    function bind_events(frm) {
        const wrapper = frm.fields_dict[SIMPLE_HTML_FIELD].$wrapper;

        wrapper.off("change.kpws_prf_v2").on("change.kpws_prf_v2", "[data-kpws-field]", function () {
            const fieldname = $(this).attr("data-kpws-field");
            const val = $(this).val();

            set_doc_value(frm, fieldname, val);

            if (fieldname === "purpose") {
                set_doc_value(frm, "custom_kpws_welfare_type", val);
            }

            if (fieldname === "custom_kpws_welfare_type") {
                set_doc_value(frm, "purpose", val);
            }

            if (fieldname === "discount_value") {
                set_doc_value(frm, "custom_kpws_welfare_percentage", val);
            }

            if (fieldname === "custom_kpws_welfare_percentage") {
                set_doc_value(frm, "discount_value", val);
            }
        });

        wrapper.off("click.kpws_prf_v2").on("click.kpws_prf_v2", "[data-kpws-action]", function () {
            const action = $(this).attr("data-kpws-action");

            collect_inputs(frm);

            if (action === "save") {
                frm.save();
                return;
            }

            if (action === "advanced") {
                show_advanced_layout(frm);
                return;
            }

            if (action === "update_patient") {
                if (frm.is_new()) {
                    frappe.msgprint("Please save the form first, then update patient details.");
                    frm.save();
                    return;
                }

                frm.save().then(function () {
                    frappe.call({
                        method: "kpws_customization.api.prf_simple_screen.apply_registration_to_patient",
                        args: {
                            prf_name: frm.doc.name
                        },
                        freeze: true,
                        freeze_message: __("Updating patient details..."),
                        callback: function () {
                            frappe.show_alert({
                                message: "Patient details updated.",
                                indicator: "green"
                            }, 8);

                            frm.reload_doc();
                        }
                    });
                });

                return;
            }

            if (action === "submit") {
                if (frm.doc.docstatus === 1) {
                    frappe.msgprint("This registration is already submitted.");
                    return;
                }

                frm.save().then(function () {
                    frm.savesubmit();
                });

                return;
            }
        });
    }

    frappe.ui.form.on("Patient Registration Form", {
        refresh(frm) {
            render_simple_screen(frm);

            if (frm.doc.custom_patient && !frm.doc.custom_patient_name) {
                fetch_patient_details(frm, frm.doc.custom_patient);
            }
        }
    });
})();
"""


def _get_prf_doctype():
    for dt in CANDIDATE_DOCTYPES:
        if frappe.db.exists("DocType", dt):
            return dt
    frappe.throw("Patient Registration Form DocType not found.")


@frappe.whitelist()
def install():
    doctype = _get_prf_doctype()

    script = CLIENT_SCRIPT.replace(
        'frappe.ui.form.on("Patient Registration Form",',
        f'frappe.ui.form.on("{doctype}",'
    )

    name = "KPWS Simple Patient Registration Desk"

    existing = frappe.db.exists("Client Script", name)

    if existing:
        doc = frappe.get_doc("Client Script", existing)
    else:
        doc = frappe.new_doc("Client Script")
        doc.name = name

    doc.dt = doctype
    doc.script = script

    if doc.meta.has_field("view"):
        doc.view = "Form"

    if doc.meta.has_field("enabled"):
        doc.enabled = 1

    doc.save(ignore_permissions=True)

    frappe.clear_cache(doctype=doctype)
    frappe.db.commit()

    return {
        "ok": True,
        "doctype": doctype,
        "message": "Fixed PRF simple UI script installed. Loop and wrapper error removed."
    }
