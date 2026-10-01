import frappe

DT = "Patient Registration Form"
CLIENT_SCRIPT_NAME = "KPWS FINAL PRF Patient Data Sync"


def _norm(value):
    return str(value or "").strip().lower().replace("_", " ").replace("-", " ")


def _has_field(dt, fieldname):
    return bool(frappe.get_meta(dt).get_field(fieldname))


def _first(doc, fields):
    for f in fields:
        if doc.meta.get_field(f):
            v = doc.get(f)
            if v not in (None, ""):
                return v
    return ""


def _patient_mr_field():
    meta = frappe.get_meta("Patient")

    # First use the actual field whose label says MR Number / MR No.
    label_matches = []
    for df in meta.fields:
        label = _norm(df.label)
        fieldname = df.fieldname or ""
        if df.fieldtype in ["Data", "Link", "Int"] and (
            label in ["mr number", "mr no", "mr"]
            or ("mr" in label and ("number" in label or "no" in label))
        ):
            label_matches.append(fieldname)

    preferred = [
        "custom_mr_number",
        "custom_mr_no",
        "mr_number",
        "mr_no",
        "patient_mr_number",
        "custom_patient_mr_number",
    ]

    for f in preferred:
        if meta.get_field(f):
            return f

    if label_matches:
        return label_matches[0]

    # Do not fallback to Patient ID. If no MR field exists, return blank.
    return ""


def get_patient_mr_number(patient):
    if not patient or not frappe.db.exists("Patient", patient):
        return ""

    fieldname = _patient_mr_field()
    if not fieldname:
        return ""

    return frappe.db.get_value("Patient", patient, fieldname) or ""


def find_patient_by_mr(mr_number):
    if not mr_number:
        return ""

    mr = str(mr_number).strip()

    # If old data has Patient ID in MR field, use it only to resolve Patient,
    # but later replace MR Number with the true Patient MR field value.
    if frappe.db.exists("Patient", mr):
        return mr

    meta = frappe.get_meta("Patient")

    candidates = []
    mr_field = _patient_mr_field()
    if mr_field:
        candidates.append(mr_field)

    for f in [
        "custom_mr_number",
        "custom_mr_no",
        "mr_number",
        "mr_no",
        "patient_mr_number",
        "custom_patient_mr_number",
    ]:
        if f not in candidates and meta.get_field(f):
            candidates.append(f)

    for f in candidates:
        patient = frappe.db.get_value("Patient", {f: mr}, "name")
        if patient:
            return patient

    return ""


def billing_type_from_patient(patient_doc, linked_customer=None):
    group = _first(patient_doc, ["customer_group", "custom_patient_billing_type", "custom_billing_type"])

    if not group and linked_customer and frappe.db.exists("Customer", linked_customer):
        group = frappe.db.get_value("Customer", linked_customer, "customer_group") or ""

    text = str(group or "").lower()

    if "panel" in text:
        return "Panel"
    if "welfare" in text:
        return "Welfare"
    return "Cash"


@frappe.whitelist()
def resolve_patient_from_mr(mr_number):
    patient = find_patient_by_mr(mr_number)
    return {"patient": patient}


@frappe.whitelist()
def fetch_patient_details(patient=None, mr_number=None):
    if not patient and mr_number:
        patient = find_patient_by_mr(mr_number)

    if not patient or not frappe.db.exists("Patient", patient):
        return {}

    p = frappe.get_doc("Patient", patient)
    customer = _first(p, ["customer", "custom_patient_customer"])
    billing_type = billing_type_from_patient(p, customer)

    return {
        "patient": patient,
        "mr_number": get_patient_mr_number(patient),  # true MR field only, not Patient ID
        "patient_name": _first(p, ["patient_name", "first_name"]) or patient,
        "customer": customer,
        "billing_type": billing_type,
        "gender": _first(p, ["sex", "gender"]),
        "dob": _first(p, ["dob", "date_of_birth"]),
        "blood_group": _first(p, ["blood_group", "custom_blood_group"]),
        "cnic": _first(p, ["cnic", "custom_cnic", "national_id", "custom_national_id"]),
        "mobile": _first(p, ["mobile", "mobile_no", "phone", "custom_mobile_no"]),
        "email": _first(p, ["email", "email_id", "custom_email"]),
        "address": _first(p, ["address", "address_line1", "custom_address"]),
        "religion": _first(p, ["religion", "custom_religion"]),
        "sect": _first(p, ["sect", "section", "custom_sect", "custom_section"]),
        "nationality": _first(p, ["nationality", "custom_nationality"]),
        "swo": _first(p, ["swo", "son_of", "father_name", "custom_swo", "custom_father_name"]),
    }


def populate_on_validate(doc, method=None):
    # Resolve patient from MR if Patient is blank.
    if not doc.get("custom_patient") and doc.get("custom_mr_number"):
        patient = find_patient_by_mr(doc.get("custom_mr_number"))
        if patient:
            doc.custom_patient = patient

    patient = doc.get("custom_patient")

    if patient and frappe.db.exists("Patient", patient):
        data = fetch_patient_details(patient=patient)

        # Patient Information tab: always sync from Patient.
        mapping_always = {
            "custom_mr_number": data.get("mr_number") or "",
            "custom_patient_name": data.get("patient_name") or "",
            "custom_patient_customer": data.get("customer") or "",
            "custom_billing_type": data.get("billing_type") or "",
            "custom_gender": data.get("gender") or "",
            "custom_dob": data.get("dob") or None,
            "custom_blood_group": data.get("blood_group") or "",
        }

        for fieldname, value in mapping_always.items():
            if doc.meta.get_field(fieldname):
                doc.set(fieldname, value)

        # Contact fields: fill only if blank so admin-entered values are not overwritten.
        mapping_if_blank = {
            "custom_cnic": data.get("cnic") or "",
            "custom_mobile": data.get("mobile") or "",
            "custom_email": data.get("email") or "",
            "custom_address": data.get("address") or "",
            "custom_religion": data.get("religion") or "",
            "custom_sect": data.get("sect") or "",
            "custom_nationality": data.get("nationality") or "",
            "custom_swo": data.get("swo") or "",
        }

        for fieldname, value in mapping_if_blank.items():
            if doc.meta.get_field(fieldname) and not doc.get(fieldname) and value:
                doc.set(fieldname, value)

    # Sync visible welfare fields to backend fields for Sales Invoice.
    if doc.meta.get_field("custom_kpws_welfare_type"):
        doc.custom_kpws_welfare_type = doc.get("purpose") or ""

    if doc.meta.get_field("custom_kpws_welfare_percentage"):
        doc.custom_kpws_welfare_percentage = float(doc.get("discount_value") or 0)

    if doc.meta.get_field("custom_kpws_assigned_panel_customer"):
        doc.custom_kpws_assigned_panel_customer = doc.get("custom_panel_customer") or ""


def backfill_existing_forms():
    rows = frappe.get_all(
        DT,
        fields=[
            "name",
            "custom_patient",
            "custom_mr_number",
            "custom_patient_name",
            "purpose",
            "discount_value",
            "custom_panel_customer",
        ],
        limit=100000,
        order_by="modified desc",
    )

    fixed_patient = 0
    fixed_mr = 0
    fixed_info = 0
    skipped = 0

    for row in rows:
        patient = row.custom_patient

        if not patient and row.custom_mr_number:
            patient = find_patient_by_mr(row.custom_mr_number)
            if patient:
                frappe.db.set_value(DT, row.name, "custom_patient", patient, update_modified=False)
                fixed_patient += 1

        if not patient:
            skipped += 1
            continue

        if not frappe.db.exists("Patient", patient):
            skipped += 1
            continue

        data = fetch_patient_details(patient=patient)

        updates = {}

        true_mr = data.get("mr_number") or ""
        if true_mr and row.custom_mr_number != true_mr:
            updates["custom_mr_number"] = true_mr
            fixed_mr += 1

        basic_map = {
            "custom_patient_name": data.get("patient_name") or "",
            "custom_patient_customer": data.get("customer") or "",
            "custom_billing_type": data.get("billing_type") or "",
            "custom_gender": data.get("gender") or "",
            "custom_dob": data.get("dob") or None,
            "custom_blood_group": data.get("blood_group") or "",
        }

        for f, v in basic_map.items():
            if _has_field(DT, f) and v not in (None, ""):
                updates[f] = v

        if _has_field(DT, "custom_kpws_welfare_type"):
            updates["custom_kpws_welfare_type"] = row.purpose or ""

        if _has_field(DT, "custom_kpws_welfare_percentage"):
            updates["custom_kpws_welfare_percentage"] = float(row.discount_value or 0)

        if _has_field(DT, "custom_kpws_assigned_panel_customer"):
            updates["custom_kpws_assigned_panel_customer"] = row.custom_panel_customer or ""

        if updates:
            frappe.db.set_value(DT, row.name, updates, update_modified=False)
            fixed_info += 1

    frappe.db.commit()

    print("Backfill complete")
    print("Patient linked from MR:", fixed_patient)
    print("MR corrected from Patient MR field:", fixed_mr)
    print("Forms updated:", fixed_info)
    print("Skipped no-match:", skipped)


def install_client_script():
    if not frappe.db.exists("DocType", "Client Script"):
        return

    # Disable old PRF scripts to avoid conflicts.
    for row in frappe.get_all("Client Script", filters={"dt": DT}, fields=["name", "script"]):
        if row.name == CLIENT_SCRIPT_NAME:
            continue

        text = ((row.name or "") + "\n" + (row.script or "")).lower()
        if "kpws" in text or "patient" in text or "welfare" in text or "panel" in text:
            frappe.db.set_value("Client Script", row.name, "enabled", 0, update_modified=False)
            print("Disabled old PRF Client Script:", row.name)

    script = r'''
frappe.ui.form.on("Patient Registration Form", {
    setup(frm) {
        kpws_prf_setup(frm);
    },
    onload(frm) {
        kpws_prf_setup(frm);
        kpws_prf_fetch_patient_data(frm);
    },
    refresh(frm) {
        kpws_prf_setup(frm);
        kpws_prf_fetch_patient_data(frm);
    },
    custom_patient(frm) {
        kpws_prf_fetch_patient_data(frm, true);
    },
    custom_mr_number(frm) {
        if (!frm.doc.custom_patient && frm.doc.custom_mr_number) {
            kpws_prf_resolve_patient_from_mr(frm);
        }
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
                    custom_is_panel: 1,
                    disabled: 0
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

    kpws_prf_sync_backend(frm);
}

function kpws_prf_resolve_patient_from_mr(frm) {
    frappe.call({
        method: "kpws_customization.api.kpws_prf_patient_data_fix.resolve_patient_from_mr",
        args: {
            mr_number: frm.doc.custom_mr_number
        },
        callback: function(r) {
            let patient = (r.message || {}).patient;
            if (patient && kpws_prf_has(frm, "custom_patient")) {
                frm.set_value("custom_patient", patient).then(function() {
                    kpws_prf_fetch_patient_data(frm, true);
                });
            }
        }
    });
}

function kpws_prf_fetch_patient_data(frm, show_loader) {
    if (!frm.doc.custom_patient && !frm.doc.custom_mr_number) {
        return;
    }

    let key = String(frm.doc.custom_patient || "") + "|" + String(frm.doc.custom_mr_number || "");
    if (frm.__kpws_prf_last_fetch_key === key && !show_loader) {
        return;
    }

    frm.__kpws_prf_last_fetch_key = key;

    if (show_loader) {
        frappe.dom.freeze(__("Fetching patient information..."));
    }

    frappe.call({
        method: "kpws_customization.api.kpws_prf_patient_data_fix.fetch_patient_details",
        args: {
            patient: frm.doc.custom_patient || "",
            mr_number: frm.doc.custom_mr_number || ""
        },
        freeze: false,
        callback: function(r) {
            let d = r.message || {};
            if (!d.patient) return;

            let overwrite = {
                custom_patient: d.patient,
                custom_mr_number: d.mr_number || "",
                custom_patient_name: d.patient_name || "",
                custom_patient_customer: d.customer || "",
                custom_billing_type: d.billing_type || "",
                custom_gender: d.gender || "",
                custom_dob: d.dob || "",
                custom_blood_group: d.blood_group || ""
            };

            let fill_if_blank = {
                custom_cnic: d.cnic || "",
                custom_mobile: d.mobile || "",
                custom_email: d.email || "",
                custom_address: d.address || "",
                custom_religion: d.religion || "",
                custom_sect: d.sect || "",
                custom_nationality: d.nationality || "",
                custom_swo: d.swo || ""
            };

            let updates = {};

            Object.keys(overwrite).forEach(function(f) {
                if (kpws_prf_has(frm, f) && frm.doc[f] !== overwrite[f]) {
                    updates[f] = overwrite[f];
                }
            });

            Object.keys(fill_if_blank).forEach(function(f) {
                if (kpws_prf_has(frm, f) && !frm.doc[f] && fill_if_blank[f]) {
                    updates[f] = fill_if_blank[f];
                }
            });

            frm.set_value(updates).then(function() {
                kpws_prf_sync_backend(frm);
                frm.refresh_fields();
            });
        },
        always: function() {
            if (show_loader) {
                frappe.dom.unfreeze();
            }
        }
    });
}

function kpws_prf_sync_backend(frm) {
    if (kpws_prf_has(frm, "custom_kpws_welfare_type")) {
        frm.set_value("custom_kpws_welfare_type", frm.doc.purpose || "");
    }

    if (kpws_prf_has(frm, "custom_kpws_welfare_percentage")) {
        frm.set_value("custom_kpws_welfare_percentage", flt(frm.doc.discount_value || 0));
    }

    if (kpws_prf_has(frm, "custom_kpws_assigned_panel_customer")) {
        frm.set_value("custom_kpws_assigned_panel_customer", frm.doc.custom_panel_customer || "");
    }
}
'''

    if frappe.db.exists("Client Script", CLIENT_SCRIPT_NAME):
        doc = frappe.get_doc("Client Script", CLIENT_SCRIPT_NAME)
        doc.enabled = 1
        doc.dt = DT
        doc.view = "Form"
        doc.script = script
        doc.save(ignore_permissions=True)
        print("Updated Client Script:", CLIENT_SCRIPT_NAME)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": CLIENT_SCRIPT_NAME,
            "dt": DT,
            "view": "Form",
            "enabled": 1,
            "script": script,
        }).insert(ignore_permissions=True)
        print("Created Client Script:", CLIENT_SCRIPT_NAME)


def install():
    install_client_script()
    frappe.db.commit()
    frappe.clear_cache(doctype=DT)
    frappe.clear_cache(doctype="Patient")

    print("")
    print("Detected Patient MR field:", _patient_mr_field() or "NOT FOUND")
    print("DONE: PRF Patient data sync installed.")
