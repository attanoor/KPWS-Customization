import json
import frappe
from frappe import _
from frappe.utils import cint


CANDIDATE_DOCTYPES = [
    "Patient Registration Form",
    "Patient Registeration Form",
]

PATIENT_GROUP_FIELDS = (
    "customer_group",
    "custom_customer_group",
    "billing_type",
    "custom_billing_type",
    "patient_type",
    "custom_patient_type",
    "member_type",
    "custom_member_type",
)

PATIENT_PANEL_FIELDS = (
    "panel_name",
    "custom_panel_name",
    "panel_customer",
    "custom_panel_customer",
    "panel",
    "custom_panel",
    "custom_kpws_assigned_panel_customer",
)


def _get_prf_doctype():
    for dt in CANDIDATE_DOCTYPES:
        if frappe.db.exists("DocType", dt):
            return dt
    frappe.throw("Patient Registration Form DocType not found.")


def _meta_has_field(doctype, fieldname):
    try:
        return frappe.get_meta(doctype).has_field(fieldname)
    except Exception:
        return False


def _set_if_has(doc, fieldname, value):
    if _meta_has_field(doc.doctype, fieldname):
        doc.set(fieldname, value)


def _first_value(doc, fields):
    for fieldname in fields:
        if _meta_has_field(doc.doctype, fieldname) and doc.get(fieldname):
            return doc.get(fieldname)
    return None


def _normalize_billing_type(value):
    value = (value or "").strip()
    low = value.lower()

    if "welfare" in low:
        return "Welfare"
    if "panel" in low:
        return "Panel"
    if "cash" in low:
        return "Cash"

    return value


def _patient_mr_number(patient_doc):
    for fieldname in (
        "custom_reference_number",
        "custom_mr_number",
        "mr_number",
        "patient_mr_number",
        "custom_patient_mr_number",
    ):
        if _meta_has_field("Patient", fieldname) and patient_doc.get(fieldname):
            return patient_doc.get(fieldname)

    return patient_doc.name


def _patient_name(patient_doc):
    for fieldname in ("patient_name", "full_name", "customer_name"):
        if _meta_has_field("Patient", fieldname) and patient_doc.get(fieldname):
            return patient_doc.get(fieldname)

    parts = []
    for fieldname in ("first_name", "middle_name", "last_name"):
        if _meta_has_field("Patient", fieldname) and patient_doc.get(fieldname):
            parts.append(patient_doc.get(fieldname))

    return " ".join(parts).strip() or patient_doc.name


def _patient_gender(patient_doc):
    for fieldname in ("sex", "gender"):
        if _meta_has_field("Patient", fieldname) and patient_doc.get(fieldname):
            return patient_doc.get(fieldname)
    return None


def _patient_mobile(patient_doc):
    for fieldname in ("mobile", "mobile_no", "phone", "phone_number", "contact_no", "custom_contact_no"):
        if _meta_has_field("Patient", fieldname) and patient_doc.get(fieldname):
            return patient_doc.get(fieldname)
    return None


def _patient_cnic(patient_doc):
    for fieldname in ("cnic", "uid", "custom_cnic", "custom_nic", "national_id"):
        if _meta_has_field("Patient", fieldname) and patient_doc.get(fieldname):
            return patient_doc.get(fieldname)
    return None


def _patient_customer(patient_doc):
    if _meta_has_field("Patient", "customer") and patient_doc.get("customer"):
        return patient_doc.get("customer")
    return None


def _patient_billing_type(patient_doc):
    billing_type = _first_value(patient_doc, PATIENT_GROUP_FIELDS)

    if billing_type:
        return _normalize_billing_type(billing_type)

    customer = _patient_customer(patient_doc)
    if customer and frappe.db.exists("Customer", customer):
        return _normalize_billing_type(
            frappe.db.get_value("Customer", customer, "customer_group")
        )

    return None


def _patient_panel(patient_doc):
    return _first_value(patient_doc, PATIENT_PANEL_FIELDS)


@frappe.whitelist()
def get_patient_details(patient):
    if not patient:
        return {}

    if not frappe.db.exists("Patient", patient):
        frappe.throw(_("Patient not found: {0}").format(patient))

    doc = frappe.get_doc("Patient", patient)

    return {
        "patient": doc.name,
        "mr_number": _patient_mr_number(doc),
        "patient_name": _patient_name(doc),
        "patient_customer": _patient_customer(doc),
        "billing_type": _patient_billing_type(doc),
        "gender": _patient_gender(doc),
        "dob": doc.get("dob") if _meta_has_field("Patient", "dob") else None,
        "blood_group": doc.get("blood_group") if _meta_has_field("Patient", "blood_group") else None,
        "contact_no": _patient_mobile(doc),
        "cnic": _patient_cnic(doc),
        "panel_customer": _patient_panel(doc),
    }


@frappe.whitelist()
def apply_registration_to_patient(prf_name):
    doctype = _get_prf_doctype()

    if not prf_name or not frappe.db.exists(doctype, prf_name):
        frappe.throw(_("Please save the Patient Registration Form first."))

    prf = frappe.get_doc(doctype, prf_name)
    patient = prf.get("custom_patient") or prf.get("patient")

    if not patient:
        frappe.throw(_("Please select Patient first."))

    if not frappe.db.exists("Patient", patient):
        frappe.throw(_("Patient not found: {0}").format(patient))

    patient_doc = frappe.get_doc("Patient", patient)

    # Update basic Patient master fields only where the field exists.
    patient_name = prf.get("custom_patient_name") or prf.get("patient_full_name")
    if patient_name:
        if _meta_has_field("Patient", "patient_name"):
            patient_doc.set("patient_name", patient_name)
        elif _meta_has_field("Patient", "first_name"):
            patient_doc.set("first_name", patient_name)

    if prf.get("custom_gender"):
        if _meta_has_field("Patient", "sex"):
            patient_doc.set("sex", prf.get("custom_gender"))
        elif _meta_has_field("Patient", "gender"):
            patient_doc.set("gender", prf.get("custom_gender"))

    if prf.get("custom_dob") and _meta_has_field("Patient", "dob"):
        patient_doc.set("dob", prf.get("custom_dob"))

    if prf.get("custom_blood_group") and _meta_has_field("Patient", "blood_group"):
        patient_doc.set("blood_group", prf.get("custom_blood_group"))

    if prf.get("contact_no"):
        for fieldname in ("mobile", "mobile_no", "phone", "phone_number", "contact_no", "custom_contact_no"):
            if _meta_has_field("Patient", fieldname):
                patient_doc.set(fieldname, prf.get("contact_no"))
                break

    if prf.get("cnic"):
        for fieldname in ("cnic", "uid", "custom_cnic", "custom_nic", "national_id"):
            if _meta_has_field("Patient", fieldname):
                patient_doc.set(fieldname, prf.get("cnic"))
                break

    panel_customer = (
        prf.get("custom_panel_customer")
        or prf.get("custom_kpws_assigned_panel_customer")
    )

    if panel_customer:
        for fieldname in PATIENT_PANEL_FIELDS:
            if _meta_has_field("Patient", fieldname):
                patient_doc.set(fieldname, panel_customer)
                break

        for fieldname in PATIENT_GROUP_FIELDS:
            if _meta_has_field("Patient", fieldname):
                patient_doc.set(fieldname, "Panel")
                break

    patient_doc.save(ignore_permissions=True)

    return {
        "ok": True,
        "message": "Patient master updated from registration form.",
        "patient": patient_doc.name,
        "details": get_patient_details(patient_doc.name),
    }


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

    const FIELD_MAP = {
        form_no: "form_no",
        patient_name: "custom_patient_name",
        mr_number: "custom_mr_number",
        patient_customer: "custom_patient_customer",
        billing_type: "custom_billing_type",
        gender: "custom_gender",
        dob: "custom_dob",
        blood_group: "custom_blood_group",
        address: "address",
        swo: "swo",
        cnic: "cnic",
        religion: "religion1",
        saction: "saction1",
        nationality: "nationality",
        contact_no: "contact_no",
        purpose: "purpose",
        percentage: "discount_value",
        welfare_type: "custom_kpws_welfare_type",
        welfare_percentage: "custom_kpws_welfare_percentage",
        panel_customer: "custom_panel_customer",
        assigned_panel: "custom_kpws_assigned_panel_customer",
        admin_notes: "custom_kpws_admin_notes",
        remarks: "remarks"
    };

    function esc(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function has_field(frm, fieldname) {
        return !!frm.fields_dict[fieldname];
    }

    function value(frm, fieldname) {
        return frm.doc[fieldname] || "";
    }

    function set_if_has(frm, fieldname, val) {
        if (has_field(frm, fieldname)) {
            frm.set_value(fieldname, val || "");
        }
    }

    function inject_css() {
        if (document.getElementById("kpws-prf-simple-css")) return;

        const css = `
            .kpws-prf-desk {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 16px;
                padding: 18px;
                margin: 8px 0 18px;
                box-shadow: 0 3px 16px rgba(15, 23, 42, 0.06);
            }

            .kpws-prf-header {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                gap: 16px;
                border-bottom: 1px solid #eef2f7;
                padding-bottom: 14px;
                margin-bottom: 16px;
            }

            .kpws-prf-title {
                font-size: 20px;
                font-weight: 800;
                color: #0f172a;
                line-height: 1.2;
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
                background: #ffffff;
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
        style.id = "kpws-prf-simple-css";
        style.innerHTML = css;
        document.head.appendChild(style);
    }

    function make_input(label, key, fieldname, type, readonly) {
        const v = esc(cur_frm.doc[fieldname] || "");

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

    function make_select(label, fieldname, options) {
        const current = cur_frm.doc[fieldname] || "";
        const opts = options.map(opt => `
            <option value="${esc(opt)}" ${current === opt ? "selected" : ""}>${esc(opt)}</option>
        `).join("");

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
            set_if_has(frm, "custom_kpws_welfare_type", frm.doc.purpose);
        }

        if (frm.doc.discount_value !== undefined && frm.doc.discount_value !== null) {
            set_if_has(frm, "custom_kpws_welfare_percentage", frm.doc.discount_value);
        }

        if (frm.doc.custom_panel_customer) {
            set_if_has(frm, "custom_kpws_assigned_panel_customer", frm.doc.custom_panel_customer);
        }
    }

    function collect_inputs(frm) {
        const wrapper = frm.fields_dict[SIMPLE_HTML_FIELD].$wrapper;

        wrapper.find("[data-kpws-field]").each(function () {
            const fieldname = $(this).attr("data-kpws-field");
            const val = $(this).val();

            if (fieldname && has_field(frm, fieldname)) {
                frm.doc[fieldname] = val;
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

        frm.wrapper.find(".form-tabs-list").hide();
    }

    function show_advanced_layout(frm) {
        HIDE_FIELDS.forEach(function (fieldname) {
            if (has_field(frm, fieldname)) {
                frm.set_df_property(fieldname, "hidden", 0);
            }
        });

        frm.wrapper.find(".form-tabs-list").show();

        frappe.show_alert({
            message: "Advanced fields are now visible.",
            indicator: "blue"
        });
    }

    function fetch_patient_details(frm, patient) {
        if (!patient) return;

        frappe.call({
            method: "kpws_customization.api.prf_simple_screen.get_patient_details",
            args: { patient: patient },
            freeze: true,
            freeze_message: __("Fetching patient details..."),
            callback: function (r) {
                const d = r.message || {};

                set_if_has(frm, "custom_mr_number", d.mr_number);
                set_if_has(frm, "custom_patient_name", d.patient_name);
                set_if_has(frm, "custom_patient_customer", d.patient_customer);
                set_if_has(frm, "custom_billing_type", d.billing_type);
                set_if_has(frm, "custom_gender", d.gender);
                set_if_has(frm, "custom_dob", d.dob);
                set_if_has(frm, "custom_blood_group", d.blood_group);

                if (d.contact_no && !frm.doc.contact_no) {
                    set_if_has(frm, "contact_no", d.contact_no);
                }

                if (d.cnic && !frm.doc.cnic) {
                    set_if_has(frm, "cnic", d.cnic);
                }

                if (d.panel_customer && !frm.doc.custom_panel_customer) {
                    set_if_has(frm, "custom_panel_customer", d.panel_customer);
                    set_if_has(frm, "custom_kpws_assigned_panel_customer", d.panel_customer);
                }

                render_simple_screen(frm);
            }
        });
    }

    function setup_link_controls(frm) {
        const wrapper = frm.fields_dict[SIMPLE_HTML_FIELD].$wrapper;

        const patient_area = wrapper.find(".kpws-patient-link-control").empty();
        const panel_area = wrapper.find(".kpws-panel-link-control").empty();

        const patient_control = frappe.ui.form.make_control({
            parent: patient_area.get(0),
            df: {
                fieldtype: "Link",
                label: "Patient",
                fieldname: "kpws_simple_patient",
                options: "Patient",
                reqd: 1,
                onchange: function () {
                    const patient = patient_control.get_value();

                    set_if_has(frm, "custom_patient", patient);
                    fetch_patient_details(frm, patient);
                }
            },
            render_input: true
        });

        patient_control.set_value(frm.doc.custom_patient || "");

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
                    const panel = panel_control.get_value();

                    set_if_has(frm, "custom_panel_customer", panel);
                    set_if_has(frm, "custom_kpws_assigned_panel_customer", panel);
                }
            },
            render_input: true
        });

        panel_control.set_value(frm.doc.custom_panel_customer || frm.doc.custom_kpws_assigned_panel_customer || "");
    }

    function render_simple_screen(frm) {
        inject_css();

        if (!has_field(frm, SIMPLE_HTML_FIELD)) {
            return;
        }

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

                        ${make_input("Form No", "form_no", "form_no", "text", false)}
                        ${make_input("MR Number", "mr", "custom_mr_number", "text", true)}
                        ${make_input("Patient Type", "billing", "custom_billing_type", "text", true)}
                    </div>

                    <div class="kpws-prf-grid" style="margin-top:12px;">
                        ${make_input("Patient Name", "name", "custom_patient_name", "text", false)}
                        ${make_input("Patient Customer", "customer", "custom_patient_customer", "text", true)}
                        ${make_input("Gender", "gender", "custom_gender", "text", false)}
                        ${make_input("Date of Birth", "dob", "custom_dob", "date", false)}
                    </div>

                    <div class="kpws-prf-grid" style="margin-top:12px;">
                        ${make_input("Blood Group", "blood", "custom_blood_group", "text", false)}
                        ${make_input("Contact No", "contact", "contact_no", "text", false)}
                        ${make_input("CNIC", "cnic", "cnic", "text", false)}
                        ${make_input("S/W/O", "swo", "swo", "text", false)}
                    </div>
                </div>

                <div class="kpws-prf-section">
                    <div class="kpws-prf-section-title">2. Address & Identity Information</div>

                    <div class="kpws-prf-grid">
                        ${make_input("Religion", "religion", "religion1", "text", false)}
                        ${make_input("Sect / Saction", "saction", "saction1", "text", false)}
                        ${make_input("Nationality", "nationality", "nationality", "text", false)}
                    </div>

                    <div class="kpws-prf-grid two" style="margin-top:12px;">
                        ${make_input("Address", "address", "address", "textarea", false)}
                        ${make_input("General Remarks", "remarks", "remarks", "textarea", false)}
                    </div>
                </div>

                <div class="kpws-prf-section">
                    <div class="kpws-prf-section-title">3. Welfare / Donation / Discount</div>

                    <div class="kpws-prf-grid">
                        ${make_select("Purpose", "purpose", ["Zakat", "Donation"])}
                        ${make_input("Approved Percentage", "percent", "discount_value", "number", false)}
                        ${make_select("Linked Welfare Type", "welfare_type", ["Zakat", "Donation"])}
                        ${make_input("Linked Welfare Percentage", "welfare_percent", "custom_kpws_welfare_percentage", "number", false)}
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

                        ${make_input("Panel / Approved Percentage", "panel_percent", "discount_value", "number", false)}
                    </div>

                    <div class="kpws-prf-alert">
                        For Panel patients, assign the panel customer here. The patient master can be updated from the button below.
                    </div>
                </div>

                <div class="kpws-prf-section">
                    <div class="kpws-prf-section-title">5. Admin Notes</div>

                    <div class="kpws-prf-grid two">
                        ${make_input("Admin Remarks", "admin", "custom_kpws_admin_notes", "textarea", false)}
                        ${make_input("Internal Remarks", "remarks", "remarks", "textarea", false)}
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

        const wrapper = frm.fields_dict[SIMPLE_HTML_FIELD].$wrapper;

        wrapper.off("change.kpws_prf").on("change.kpws_prf", "[data-kpws-field]", function () {
            const fieldname = $(this).attr("data-kpws-field");
            const val = $(this).val();

            set_if_has(frm, fieldname, val);

            if (fieldname === "purpose") {
                set_if_has(frm, "custom_kpws_welfare_type", val);
            }

            if (fieldname === "custom_kpws_welfare_type") {
                set_if_has(frm, "purpose", val);
            }

            if (fieldname === "discount_value") {
                set_if_has(frm, "custom_kpws_welfare_percentage", val);
            }

            if (fieldname === "custom_kpws_welfare_percentage") {
                set_if_has(frm, "discount_value", val);
            }
        });

        wrapper.off("click.kpws_prf").on("click.kpws_prf", "[data-kpws-action]", function () {
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
                        callback: function (r) {
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

        hide_old_layout(frm);
    }

    frappe.ui.form.on(cur_frm && cur_frm.doctype ? cur_frm.doctype : "Patient Registration Form", {
        refresh(frm) {
            render_simple_screen(frm);
        },

        custom_patient(frm) {
            if (frm.doc.custom_patient) {
                fetch_patient_details(frm, frm.doc.custom_patient);
            }
        },

        purpose(frm) {
            sync_duplicate_fields(frm);
        },

        discount_value(frm) {
            sync_duplicate_fields(frm);
        },

        custom_panel_customer(frm) {
            sync_duplicate_fields(frm);
        }
    });
})();
"""


def _ensure_simple_html_field(doctype):
    if _meta_has_field(doctype, "custom_kpws_patient_snapshot_html"):
        return "custom_kpws_patient_snapshot_html"

    if frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": "custom_kpws_patient_snapshot_html"}):
        return "custom_kpws_patient_snapshot_html"

    frappe.get_doc({
        "doctype": "Custom Field",
        "dt": doctype,
        "label": "Patient Registration Desk",
        "fieldname": "custom_kpws_patient_snapshot_html",
        "fieldtype": "HTML",
        "insert_after": "naming_series",
        "read_only": 1,
        "no_copy": 1,
    }).insert(ignore_permissions=True)

    frappe.clear_cache(doctype=doctype)
    return "custom_kpws_patient_snapshot_html"


def _upsert_client_script(doctype):
    name = "KPWS Simple Patient Registration Desk"

    existing = frappe.db.exists("Client Script", name)

    if existing:
        doc = frappe.get_doc("Client Script", existing)
    else:
        doc = frappe.new_doc("Client Script")
        doc.name = name

    doc.dt = doctype
    doc.script = CLIENT_SCRIPT.replace(
        'frappe.ui.form.on(cur_frm && cur_frm.doctype ? cur_frm.doctype : "Patient Registration Form",',
        f'frappe.ui.form.on("{doctype}",'
    )

    if doc.meta.has_field("view"):
        doc.view = "Form"

    if doc.meta.has_field("enabled"):
        doc.enabled = 1

    doc.save(ignore_permissions=True)


@frappe.whitelist()
def install():
    doctype = _get_prf_doctype()

    _ensure_simple_html_field(doctype)
    _upsert_client_script(doctype)

    frappe.clear_cache(doctype=doctype)
    frappe.db.commit()

    return {
        "ok": True,
        "doctype": doctype,
        "message": "Simple Patient Registration Desk installed."
    }
