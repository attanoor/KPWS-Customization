import frappe
from frappe.utils import escape_html, now

DT = "Patient Registration Form"

FIELD_DEFS = {
    "basic_information_tab": {
        "label": "Patient Information",
        "fieldtype": "Tab Break",
        "hidden": 0,
    },
    "custom_patient": {
        "label": "Patient",
        "fieldtype": "Link",
        "options": "Patient",
        "hidden": 0,
        "read_only": 0,
        "reqd": 1,
    },
    "custom_mr_number": {
        "label": "MR Number",
        "fieldtype": "Data",
        "hidden": 0,
        "read_only": 1,
        "reqd": 0,
    },
    "custom_patient_name": {
        "label": "Patient Name",
        "fieldtype": "Data",
        "hidden": 0,
        "read_only": 1,
        "reqd": 0,
    },
    "custom_patient_customer": {
        "label": "Patient Customer",
        "fieldtype": "Link",
        "options": "Customer",
        "hidden": 0,
        "read_only": 1,
        "reqd": 0,
    },
    "custom_billing_type": {
        "label": "Patient Type",
        "fieldtype": "Select",
        "options": "\nCash\nWelfare\nPanel",
        "hidden": 0,
        "read_only": 1,
        "reqd": 0,
    },
    "custom_gender": {
        "label": "Gender",
        "fieldtype": "Data",
        "hidden": 0,
        "read_only": 1,
        "reqd": 0,
    },
    "custom_dob": {
        "label": "Date of Birth",
        "fieldtype": "Date",
        "hidden": 0,
        "read_only": 1,
        "reqd": 0,
    },
    "custom_blood_group": {
        "label": "Blood Group",
        "fieldtype": "Data",
        "hidden": 0,
        "read_only": 1,
        "reqd": 0,
    },
    "custom_patient_snapshot_html": {
        "label": "Patient Full Details",
        "fieldtype": "HTML",
        "hidden": 0,
        "read_only": 1,
        "reqd": 0,
    },

    "contact_details_tab": {
        "label": "Contact Information",
        "fieldtype": "Tab Break",
        "hidden": 0,
    },
    "custom_cnic": {
        "label": "CNIC",
        "fieldtype": "Data",
        "hidden": 0,
        "read_only": 0,
        "reqd": 0,
    },
    "custom_mobile": {
        "label": "Mobile",
        "fieldtype": "Data",
        "hidden": 0,
        "read_only": 0,
        "reqd": 0,
    },
    "custom_email": {
        "label": "Email",
        "fieldtype": "Data",
        "hidden": 0,
        "read_only": 0,
        "reqd": 0,
    },
    "custom_address": {
        "label": "Address",
        "fieldtype": "Small Text",
        "hidden": 0,
        "read_only": 0,
        "reqd": 0,
    },
    "custom_religion": {
        "label": "Religion",
        "fieldtype": "Data",
        "hidden": 0,
        "read_only": 0,
        "reqd": 0,
    },
    "custom_sect": {
        "label": "Sect",
        "fieldtype": "Data",
        "hidden": 0,
        "read_only": 0,
        "reqd": 0,
    },
    "custom_nationality": {
        "label": "Nationality",
        "fieldtype": "Data",
        "hidden": 0,
        "read_only": 0,
        "reqd": 0,
    },
    "custom_swo": {
        "label": "S/W/O",
        "fieldtype": "Data",
        "hidden": 0,
        "read_only": 0,
        "reqd": 0,
    },

    "discount_and_purpose_tab": {
        "label": "Discount and Purpose",
        "fieldtype": "Tab Break",
        "hidden": 0,
    },
    "purpose": {
        "label": "Purpose",
        "fieldtype": "Select",
        "options": "\nZakat\nDonation",
        "hidden": 0,
        "read_only": 0,
        "reqd": 0,
    },
    "discount_value": {
        "label": "Percentage",
        "fieldtype": "Float",
        "hidden": 0,
        "read_only": 0,
        "reqd": 0,
    },
    "custom_panel_customer": {
        "label": "Panel",
        "fieldtype": "Link",
        "options": "Customer",
        "hidden": 0,
        "read_only": 0,
        "reqd": 0,
    },
    "custom_kpws_admin_notes": {
        "label": "Remarks",
        "fieldtype": "Small Text",
        "hidden": 0,
        "read_only": 0,
        "reqd": 0,
    },

    "custom_kpws_welfare_type": {
        "label": "Welfare Type Backend",
        "fieldtype": "Select",
        "options": "\nZakat\nDonation",
        "hidden": 1,
        "read_only": 0,
        "reqd": 0,
    },
    "custom_kpws_welfare_percentage": {
        "label": "Welfare Percentage Backend",
        "fieldtype": "Percent",
        "hidden": 1,
        "read_only": 0,
        "reqd": 0,
    },
    "custom_kpws_assigned_panel_customer": {
        "label": "Assigned Panel Backend",
        "fieldtype": "Link",
        "options": "Customer",
        "hidden": 1,
        "read_only": 0,
        "reqd": 0,
    },
}

ORDER = [
    "basic_information_tab",
    "custom_patient",
    "custom_mr_number",
    "custom_patient_name",
    "custom_patient_customer",
    "custom_billing_type",
    "custom_gender",
    "custom_dob",
    "custom_blood_group",
    "custom_patient_snapshot_html",

    "contact_details_tab",
    "custom_cnic",
    "custom_mobile",
    "custom_email",
    "custom_address",
    "custom_religion",
    "custom_sect",
    "custom_nationality",
    "custom_swo",

    "discount_and_purpose_tab",
    "purpose",
    "discount_value",
    "custom_panel_customer",
    "custom_kpws_admin_notes",

    "custom_kpws_welfare_type",
    "custom_kpws_welfare_percentage",
    "custom_kpws_assigned_panel_customer",
]

def get_df(fieldname):
    return frappe.db.get_value(
        "DocField",
        {"parent": DT, "fieldname": fieldname},
        ["name", "idx", "fieldname", "label", "fieldtype", "hidden"],
        as_dict=True,
    )

def max_idx():
    return int(frappe.db.sql(
        "select coalesce(max(idx),0) from `tabDocField` where parent=%s",
        DT,
    )[0][0] or 0)

def ensure_df(fieldname, d):
    row = get_df(fieldname)
    values = {
        "label": d.get("label"),
        "fieldtype": d.get("fieldtype"),
        "options": d.get("options"),
        "hidden": int(d.get("hidden", 0)),
        "read_only": int(d.get("read_only", 0)),
        "reqd": int(d.get("reqd", 0)),
        "print_hide": int(d.get("print_hide", 0)),
    }

    if row:
        frappe.db.set_value("DocField", row.name, values, update_modified=False)
        print("Updated DocField:", fieldname)
    else:
        frappe.get_doc({
            "doctype": "DocField",
            "parent": DT,
            "parenttype": "DocType",
            "parentfield": "fields",
            "idx": max_idx() + 1,
            "fieldname": fieldname,
            **values,
        }).insert(ignore_permissions=True)
        print("Inserted DocField:", fieldname)

def ps(fieldname, prop, value, ptype="Check"):
    name = frappe.db.exists("Property Setter", {
        "doc_type": DT,
        "doctype_or_field": "DocField",
        "field_name": fieldname,
        "property": prop,
    })

    if name:
        frappe.db.set_value("Property Setter", name, {
            "value": str(value),
            "property_type": ptype,
        }, update_modified=False)
    else:
        frappe.get_doc({
            "doctype": "Property Setter",
            "doc_type": DT,
            "doctype_or_field": "DocField",
            "field_name": fieldname,
            "property": prop,
            "property_type": ptype,
            "value": str(value),
        }).insert(ignore_permissions=True)

def hide_wrong_tabs_and_duplicates():
    desired_tabs = {
        "Patient Information",
        "Contact Information",
        "Discount and Purpose",
    }

    keep_fieldnames = {
        "basic_information_tab",
        "contact_details_tab",
        "discount_and_purpose_tab",
    }

    rows = frappe.get_all(
        "DocField",
        filters={"parent": DT},
        fields=["name", "fieldname", "label", "fieldtype"],
        order_by="idx asc",
    )

    duplicate_fields = {
        "details",
        "details_tab",
        "details_section",
        "discount_type",
        "patient",
        "patient_name",
        "patient_full_name",
        "mr_no",
        "mr_number",
    }

    for r in rows:
        fname = r.fieldname or ""
        label = (r.label or "").strip()
        label_lower = label.lower()

        should_hide = False

        if r.fieldtype == "Tab Break":
            if fname not in keep_fieldnames and label not in desired_tabs:
                should_hide = True

            if label_lower == "details":
                should_hide = True

        if fname in duplicate_fields:
            should_hide = True

        if should_hide:
            frappe.db.set_value("DocField", r.name, {
                "hidden": 1,
                "reqd": 0,
                "print_hide": 1,
            }, update_modified=False)

            if fname:
                ps(fname, "hidden", "1")
                ps(fname, "reqd", "0")

            print("Hidden:", fname, "|", label, "|", r.fieldtype)

def reindex():
    rows = frappe.get_all(
        "DocField",
        filters={"parent": DT},
        fields=["name", "fieldname"],
        order_by="idx asc",
    )

    by_field = {r.fieldname: r for r in rows}
    ordered = []
    used = set()

    for f in ORDER:
        if f in by_field:
            ordered.append(by_field[f])
            used.add(by_field[f].name)

    for r in rows:
        if r.name not in used:
            ordered.append(r)

    for idx, r in enumerate(ordered, start=1):
        frappe.db.set_value("DocField", r.name, "idx", idx, update_modified=False)

def install_client_script():
    if not frappe.db.exists("DocType", "Client Script"):
        return

    for row in frappe.get_all("Client Script", filters={"dt": DT}, fields=["name", "script"]):
        if row.name == "KPWS FINAL PRF Patient Verification Flow":
            continue

        text = ((row.name or "") + "\n" + (row.script or "")).lower()
        if any(k in text for k in ["kpws", "panel", "welfare", "purpose", "discount"]):
            frappe.db.set_value("Client Script", row.name, "enabled", 0, update_modified=False)
            print("Disabled old PRF script:", row.name)

    script = r'''
frappe.ui.form.on("Patient Registration Form", {
    setup(frm) {
        kpws_prf_setup(frm);
    },
    onload(frm) {
        kpws_prf_setup(frm);
        kpws_prf_fetch_patient(frm);
        kpws_prf_fill_visible_from_backend(frm);
    },
    refresh(frm) {
        kpws_prf_setup(frm);
        kpws_prf_fetch_patient(frm);
        kpws_prf_fill_visible_from_backend(frm);
    },
    custom_patient(frm) {
        kpws_prf_fetch_patient(frm);
    },
    purpose(frm) {
        kpws_prf_sync_backend(frm);
    },
    discount_value(frm) {
        kpws_prf_sync_backend(frm);
    },
    custom_panel_customer(frm) {
        kpws_prf_sync_backend(frm);
    }
});

function kpws_prf_has(frm, fieldname) {
    return frm.fields_dict && frm.fields_dict[fieldname];
}

function kpws_prf_setup(frm) {
    if (kpws_prf_has(frm, "custom_panel_customer")) {
        frm.set_query("custom_panel_customer", function() {
            return {
                filters: {
                    custom_is_panel: 1
                }
            };
        });
    }

    [
        "custom_mr_number",
        "custom_patient_name",
        "custom_patient_customer",
        "custom_billing_type",
        "custom_gender",
        "custom_dob",
        "custom_blood_group"
    ].forEach(function(f) {
        if (kpws_prf_has(frm, f)) {
            frm.set_df_property(f, "read_only", 1);
        }
    });

    [
        "custom_kpws_welfare_type",
        "custom_kpws_welfare_percentage",
        "custom_kpws_assigned_panel_customer"
    ].forEach(function(f) {
        if (kpws_prf_has(frm, f)) {
            frm.toggle_display(f, false);
            frm.toggle_reqd(f, false);
        }
    });

    ["purpose", "discount_value"].forEach(function(f) {
        if (kpws_prf_has(frm, f)) {
            frm.toggle_reqd(f, false);
        }
    });
}

function kpws_prf_fill_visible_from_backend(frm) {
    if (kpws_prf_has(frm, "purpose") && !frm.doc.purpose && frm.doc.custom_kpws_welfare_type) {
        frm.set_value("purpose", frm.doc.custom_kpws_welfare_type);
    }

    if (kpws_prf_has(frm, "discount_value") && !frm.doc.discount_value && frm.doc.custom_kpws_welfare_percentage) {
        frm.set_value("discount_value", frm.doc.custom_kpws_welfare_percentage);
    }

    if (kpws_prf_has(frm, "custom_panel_customer") && !frm.doc.custom_panel_customer && frm.doc.custom_kpws_assigned_panel_customer) {
        frm.set_value("custom_panel_customer", frm.doc.custom_kpws_assigned_panel_customer);
    }

    kpws_prf_sync_backend(frm);
}

function kpws_prf_sync_backend(frm) {
    if (kpws_prf_has(frm, "custom_kpws_welfare_type")) {
        frm.set_value("custom_kpws_welfare_type", frm.doc.purpose || "");
    }

    if (kpws_prf_has(frm, "custom_kpws_welfare_percentage")) {
        frm.set_value("custom_kpws_welfare_percentage", frm.doc.discount_value || 0);
    }

    if (kpws_prf_has(frm, "custom_kpws_assigned_panel_customer")) {
        frm.set_value("custom_kpws_assigned_panel_customer", frm.doc.custom_panel_customer || "");
    }
}

function kpws_prf_fetch_patient(frm) {
    if (!frm.doc.custom_patient) {
        kpws_prf_render_empty_snapshot(frm);
        return;
    }

    frappe.call({
        method: "kpws_customization.api.kpws_temp_prf_final_form_fix.fetch_patient_details",
        args: {
            patient: frm.doc.custom_patient
        },
        freeze: false,
        callback: function(r) {
            let d = r.message || {};

            let map = {
                custom_mr_number: d.mr_number,
                custom_patient_name: d.patient_name,
                custom_patient_customer: d.customer,
                custom_billing_type: d.billing_type,
                custom_gender: d.gender,
                custom_dob: d.dob,
                custom_blood_group: d.blood_group,
                custom_cnic: d.cnic,
                custom_mobile: d.mobile,
                custom_email: d.email,
                custom_address: d.address,
                custom_religion: d.religion,
                custom_sect: d.sect,
                custom_nationality: d.nationality,
                custom_swo: d.swo
            };

            Object.keys(map).forEach(function(f) {
                if (kpws_prf_has(frm, f) && map[f] !== undefined && map[f] !== null && map[f] !== "") {
                    frm.set_value(f, map[f]);
                }
            });

            if (kpws_prf_has(frm, "custom_patient_snapshot_html")) {
                frm.fields_dict.custom_patient_snapshot_html.$wrapper.html(d.html || "");
            }
        }
    });
}

function kpws_prf_render_empty_snapshot(frm) {
    if (kpws_prf_has(frm, "custom_patient_snapshot_html")) {
        frm.fields_dict.custom_patient_snapshot_html.$wrapper.html(
            '<div style="padding:12px;border:1px solid var(--border-color);border-radius:8px;color:var(--text-muted);">Select a patient to view full patient details.</div>'
        );
    }
}
'''

    name = "KPWS FINAL PRF Patient Verification Flow"

    if frappe.db.exists("Client Script", name):
        doc = frappe.get_doc("Client Script", name)
        doc.enabled = 1
        doc.dt = DT
        doc.view = "Form"
        doc.script = script
        doc.save(ignore_permissions=True)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": name,
            "dt": DT,
            "view": "Form",
            "enabled": 1,
            "script": script,
        }).insert(ignore_permissions=True)

    print("Installed final PRF client script")

def first(doc, fields):
    for f in fields:
        if doc.meta.get_field(f):
            v = doc.get(f)
            if v not in (None, ""):
                return v
    return ""

def billing_type_from_text(text):
    t = str(text or "").lower()
    if "panel" in t:
        return "Panel"
    if "welfare" in t:
        return "Welfare"
    return "Cash"

def row(label, value):
    value = value if value not in (None, "") else "-"
    return f"""
        <tr>
            <td style="width:210px;color:var(--text-muted);padding:8px 10px;border-bottom:1px solid var(--border-color);">{escape_html(label)}</td>
            <td style="padding:8px 10px;border-bottom:1px solid var(--border-color);font-weight:500;">{escape_html(str(value))}</td>
        </tr>
    """

@frappe.whitelist()
def fetch_patient_details(patient):
    if not patient or not frappe.db.exists("Patient", patient):
        return {}

    p = frappe.get_doc("Patient", patient)

    customer = first(p, ["customer", "custom_patient_customer"])
    customer_group = ""
    if customer and frappe.db.exists("Customer", customer):
        customer_group = frappe.db.get_value("Customer", customer, "customer_group") or ""

    patient_group = first(p, ["customer_group", "custom_patient_billing_type", "custom_billing_type"])
    billing_type = billing_type_from_text(patient_group or customer_group)

    details = {
        "mr_number": first(p, ["custom_mr_number", "mr_number", "uid", "patient_id"]) or patient,
        "patient_name": first(p, ["patient_name", "first_name"]),
        "customer": customer,
        "billing_type": billing_type,
        "gender": first(p, ["sex", "gender"]),
        "dob": first(p, ["dob", "date_of_birth"]),
        "blood_group": first(p, ["blood_group", "custom_blood_group"]),
        "cnic": first(p, ["cnic", "custom_cnic", "national_id", "custom_national_id"]),
        "mobile": first(p, ["mobile", "mobile_no", "phone", "custom_mobile_no"]),
        "email": first(p, ["email", "email_id", "custom_email"]),
        "address": first(p, ["address", "address_line1", "custom_address"]),
        "religion": first(p, ["religion", "custom_religion"]),
        "sect": first(p, ["sect", "section", "custom_sect", "custom_section"]),
        "nationality": first(p, ["nationality", "custom_nationality"]),
        "swo": first(p, ["swo", "son_of", "father_name", "custom_swo", "custom_father_name"]),
    }

    html = f"""
    <div style="margin-top:12px;border:1px solid var(--border-color);border-radius:10px;overflow:hidden;">
        <div style="padding:12px 14px;background:var(--control-bg);font-weight:700;">Patient Full Details for Verification</div>
        <table style="width:100%;border-collapse:collapse;">
            {row("MR Number", details["mr_number"])}
            {row("Patient Name", details["patient_name"])}
            {row("Linked Customer", details["customer"])}
            {row("Patient Type", details["billing_type"])}
            {row("Gender", details["gender"])}
            {row("Date of Birth", details["dob"])}
            {row("Blood Group", details["blood_group"])}
            {row("CNIC", details["cnic"])}
            {row("Mobile", details["mobile"])}
            {row("Email", details["email"])}
            {row("Address", details["address"])}
            {row("Religion", details["religion"])}
            {row("Sect", details["sect"])}
            {row("Nationality", details["nationality"])}
            {row("S/W/O", details["swo"])}
        </table>
    </div>
    """

    details["html"] = html
    return details

def run():
    if not frappe.db.exists("DocType", DT):
        raise Exception(f"{DT} not found")

    for fieldname, definition in FIELD_DEFS.items():
        ensure_df(fieldname, definition)

    hide_wrong_tabs_and_duplicates()
    reindex()

    for f in ["basic_information_tab", "contact_details_tab", "discount_and_purpose_tab"]:
        ps(f, "hidden", "0")
        ps(f, "label", FIELD_DEFS[f]["label"], "Data")

    for f in [
        "purpose",
        "discount_value",
        "discount_type",
        "custom_kpws_welfare_type",
        "custom_kpws_welfare_percentage",
        "custom_kpws_assigned_panel_customer",
        "cnic",
        "custom_cnic",
    ]:
        if get_df(f):
            ps(f, "reqd", "0")

    for f in [
        "custom_kpws_welfare_type",
        "custom_kpws_welfare_percentage",
        "custom_kpws_assigned_panel_customer",
        "discount_type",
    ]:
        if get_df(f):
            ps(f, "hidden", "1")

    install_client_script()

    frappe.db.set_value("DocType", DT, "modified", now(), update_modified=False)
    frappe.clear_cache(doctype=DT)
    frappe.db.commit()

    print("")
    print("Final PRF tab layout:")
    rows = frappe.get_all(
        "DocField",
        filters={"parent": DT},
        fields=["idx", "fieldname", "label", "fieldtype", "hidden", "read_only"],
        order_by="idx asc",
    )

    for r in rows:
        if r.fieldtype == "Tab Break" or r.fieldname in ORDER:
            print(r.idx, "|", r.fieldtype, "|", r.fieldname, "|", r.label, "| hidden=", r.hidden, "| ro=", r.read_only)

    print("")
    print("DONE: Blank Details tab hidden and Patient Information verification view added.")

