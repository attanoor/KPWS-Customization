import csv
import frappe
from pathlib import Path

DT = "Patient Registration Form"
REPORT = "/tmp/kpws_prf_unlinked_after_recovery.csv"
CLIENT_SCRIPT_NAME = "KPWS FINAL PRF Safe Link No Autosave"


def _norm(v):
    return " ".join(str(v or "").strip().lower().split())


def _meta_fields(dt):
    return {df.fieldname for df in frappe.get_meta(dt).fields}


def _first(doc, fields):
    for f in fields:
        if doc.meta.get_field(f):
            v = doc.get(f)
            if v not in (None, ""):
                return v
    return ""


def _clean_date(v):
    if v in (None, "", "0000-00-00"):
        return None
    return v


def _patient_mr_field():
    meta = frappe.get_meta("Patient")

    # Your required MR field.
    if meta.get_field("custom_reference_number"):
        return "custom_reference_number"

    # Safe fallbacks only if custom_reference_number is not present.
    for f in [
        "custom_mr_number",
        "custom_mr_no",
        "mr_number",
        "mr_no",
        "patient_mr_number",
        "custom_patient_mr_number",
    ]:
        if meta.get_field(f):
            return f

    return ""


def _patient_mr(patient):
    fieldname = _patient_mr_field()
    if not fieldname or not patient or not frappe.db.exists("Patient", patient):
        return ""
    return frappe.db.get_value("Patient", patient, fieldname) or ""


def _billing_type(patient_doc, customer=None):
    group = _first(patient_doc, ["customer_group", "custom_patient_billing_type", "custom_billing_type"])

    if not group and customer and frappe.db.exists("Customer", customer):
        group = frappe.db.get_value("Customer", customer, "customer_group") or ""

    txt = _norm(group)

    if "panel" in txt:
        return "Panel"
    if "welfare" in txt:
        return "Welfare"
    return "Cash"


def _patient_detail(patient):
    p = frappe.get_doc("Patient", patient)
    customer = _first(p, ["customer", "custom_patient_customer"])

    return {
        "custom_patient": patient,
        "custom_mr_number": _patient_mr(patient),
        "custom_patient_name": _first(p, ["patient_name", "first_name"]) or patient,
        "custom_patient_customer": customer,
        "custom_billing_type": _billing_type(p, customer),
        "custom_gender": _first(p, ["sex", "gender"]),
        "custom_dob": _clean_date(_first(p, ["dob", "date_of_birth"])),
        "custom_blood_group": _first(p, ["blood_group", "custom_blood_group"]),
        "custom_cnic": _first(p, ["cnic", "custom_cnic", "national_id", "custom_national_id"]),
        "custom_mobile": _first(p, ["mobile", "mobile_no", "phone", "custom_mobile_no"]),
        "custom_email": _first(p, ["email", "email_id", "custom_email"]),
        "custom_address": _first(p, ["address", "address_line1", "custom_address"]),
        "custom_religion": _first(p, ["religion", "custom_religion"]),
        "custom_sect": _first(p, ["sect", "section", "custom_sect", "custom_section"]),
        "custom_nationality": _first(p, ["nationality", "custom_nationality"]),
        "custom_swo": _first(p, ["swo", "son_of", "father_name", "custom_swo", "custom_father_name"]),
    }


def _build_indexes():
    patient_fields = _meta_fields("Patient")
    mr_field = _patient_mr_field()

    fields = ["name"]

    for f in [
        "patient_name",
        "first_name",
        "customer",
        "custom_patient_customer",
        "cnic",
        "custom_cnic",
        "mobile",
        "mobile_no",
        "phone",
        "custom_mobile_no",
        mr_field,
    ]:
        if f and f in patient_fields and f not in fields:
            fields.append(f)

    indexes = {
        "by_id": {},
        "by_mr": {},
        "by_customer": {},
        "by_name": {},
        "by_cnic": {},
        "by_mobile": {},
    }

    def add(index, key, patient):
        key = _norm(key)
        if key:
            index.setdefault(key, set()).add(patient)

    for p in frappe.get_all("Patient", fields=fields, limit=100000):
        indexes["by_id"][_norm(p.name)] = p.name

        if mr_field and mr_field in p:
            add(indexes["by_mr"], p.get(mr_field), p.name)

        for f in ["customer", "custom_patient_customer"]:
            if f in p:
                add(indexes["by_customer"], p.get(f), p.name)

        for f in ["patient_name", "first_name"]:
            if f in p:
                add(indexes["by_name"], p.get(f), p.name)

        for f in ["cnic", "custom_cnic"]:
            if f in p:
                add(indexes["by_cnic"], p.get(f), p.name)

        for f in ["mobile", "mobile_no", "phone", "custom_mobile_no"]:
            if f in p:
                add(indexes["by_mobile"], p.get(f), p.name)

    return indexes


def _one(index, key):
    matches = index.get(_norm(key)) or set()
    if len(matches) == 1:
        return list(matches)[0]
    return ""


def _resolve_patient(row, indexes):
    existing = row.get("custom_patient")

    if existing and frappe.db.exists("Patient", existing):
        return existing, "already_linked"

    mr = row.get("custom_mr_number")
    if mr:
        if _norm(mr) in indexes["by_id"]:
            return indexes["by_id"][_norm(mr)], "patient_id_in_mr"

        p = _one(indexes["by_mr"], mr)
        if p:
            return p, "mr_match"

    p = _one(indexes["by_customer"], row.get("custom_patient_customer"))
    if p:
        return p, "customer_match"

    p = _one(indexes["by_cnic"], row.get("custom_cnic"))
    if p:
        return p, "cnic_match"

    p = _one(indexes["by_mobile"], row.get("custom_mobile"))
    if p:
        return p, "mobile_match"

    p = _one(indexes["by_name"], row.get("custom_patient_name"))
    if p:
        return p, "unique_name_match"

    return "", "unresolved"


def _get_prf_rows():
    fields = _meta_fields(DT)

    wanted = [
        "name",
        "docstatus",
        "custom_patient",
        "custom_mr_number",
        "custom_patient_name",
        "custom_patient_customer",
        "custom_cnic",
        "custom_mobile",
        "purpose",
        "discount_value",
        "custom_panel_customer",
        "custom_religion",
        "custom_sect",
        "custom_nationality",
        "custom_swo",
        "custom_kpws_admin_notes",
    ]

    selected = [f for f in wanted if f in fields or f in ["name", "docstatus"]]

    return frappe.get_all(DT, fields=selected, limit=100000, order_by="modified desc")


def audit():
    indexes = _build_indexes()
    rows = _get_prf_rows()

    counts = {}
    unresolved = []

    for row in rows:
        patient, method = _resolve_patient(row, indexes)
        counts[method] = counts.get(method, 0) + 1

        if not patient:
            unresolved.append(row)

    with open(REPORT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "name",
            "custom_patient",
            "custom_mr_number",
            "custom_patient_name",
            "custom_patient_customer",
            "custom_cnic",
            "custom_mobile",
            "purpose",
            "discount_value",
        ])
        writer.writeheader()

        for r in unresolved:
            writer.writerow({
                "name": r.get("name"),
                "custom_patient": r.get("custom_patient"),
                "custom_mr_number": r.get("custom_mr_number"),
                "custom_patient_name": r.get("custom_patient_name"),
                "custom_patient_customer": r.get("custom_patient_customer"),
                "custom_cnic": r.get("custom_cnic"),
                "custom_mobile": r.get("custom_mobile"),
                "purpose": r.get("purpose"),
                "discount_value": r.get("discount_value"),
            })

    print("Patient MR field used:", _patient_mr_field() or "NOT FOUND")
    print("Total Patient Registration Forms:", len(rows))
    print("")
    print("Match summary:")
    for k in sorted(counts):
        print(k, "=>", counts[k])

    print("")
    print("Unresolved:", len(unresolved))
    print("Unresolved report:", REPORT)


def backfill_apply():
    prf_fields = _meta_fields(DT)
    indexes = _build_indexes()
    rows = _get_prf_rows()

    updated = 0
    linked = 0
    mr_corrected = 0
    unresolved = 0
    errors = 0

    for row in rows:
        patient, method = _resolve_patient(row, indexes)

        if not patient:
            unresolved += 1
            continue

        data = _patient_detail(patient)
        updates = {}

        # Always sync only core Patient-identification fields.
        for f in [
            "custom_patient",
            "custom_mr_number",
            "custom_patient_name",
            "custom_patient_customer",
            "custom_billing_type",
            "custom_gender",
            "custom_dob",
            "custom_blood_group",
        ]:
            if f in prf_fields:
                value = data.get(f)
                if f == "custom_dob":
                    value = _clean_date(value)
                updates[f] = value

        # Preserve admin-entered contact/extra info. Fill only if blank.
        for f in [
            "custom_cnic",
            "custom_mobile",
            "custom_email",
            "custom_address",
            "custom_religion",
            "custom_sect",
            "custom_nationality",
            "custom_swo",
        ]:
            if f in prf_fields and not row.get(f) and data.get(f):
                updates[f] = data.get(f)

        # Preserve visible welfare fields; just sync backend mirror fields.
        if "custom_kpws_welfare_type" in prf_fields:
            updates["custom_kpws_welfare_type"] = row.get("purpose") or ""

        if "custom_kpws_welfare_percentage" in prf_fields:
            updates["custom_kpws_welfare_percentage"] = float(row.get("discount_value") or 0)

        if "custom_kpws_assigned_panel_customer" in prf_fields:
            updates["custom_kpws_assigned_panel_customer"] = row.get("custom_panel_customer") or ""

        if updates.get("custom_dob") in ("", "0000-00-00"):
            updates["custom_dob"] = None

        try:
            frappe.db.set_value(DT, row.name, updates, update_modified=False)
            updated += 1

            if not row.get("custom_patient"):
                linked += 1

            if row.get("custom_mr_number") != updates.get("custom_mr_number"):
                mr_corrected += 1

            if updated % 500 == 0:
                frappe.db.commit()
                print("Committed:", updated)

        except Exception as e:
            errors += 1
            print("ERROR:", row.name, "method:", method, "patient:", patient, "=>", e)

    frappe.db.commit()

    print("")
    print("Backfill complete.")
    print("Updated:", updated)
    print("Newly linked:", linked)
    print("MR corrected from Patient.custom_reference_number:", mr_corrected)
    print("Unresolved:", unresolved)
    print("Errors:", errors)


@frappe.whitelist()
def fetch_patient_details(patient=None, mr_number=None):
    indexes = _build_indexes()

    if not patient and mr_number:
        fake = frappe._dict({"custom_patient": "", "custom_mr_number": mr_number})
        patient, _method = _resolve_patient(fake, indexes)

    if not patient or not frappe.db.exists("Patient", patient):
        return {}

    return _patient_detail(patient)


def populate_on_validate(doc, method=None):
    indexes = _build_indexes()

    if not doc.get("custom_patient"):
        patient, method = _resolve_patient(doc, indexes)
        if patient:
            doc.custom_patient = patient

    if doc.get("custom_patient") and frappe.db.exists("Patient", doc.custom_patient):
        data = _patient_detail(doc.custom_patient)

        for f in [
            "custom_mr_number",
            "custom_patient_name",
            "custom_patient_customer",
            "custom_billing_type",
            "custom_gender",
            "custom_dob",
            "custom_blood_group",
        ]:
            if doc.meta.get_field(f):
                doc.set(f, data.get(f))

        for f in [
            "custom_cnic",
            "custom_mobile",
            "custom_email",
            "custom_address",
            "custom_religion",
            "custom_sect",
            "custom_nationality",
            "custom_swo",
        ]:
            if doc.meta.get_field(f) and not doc.get(f) and data.get(f):
                doc.set(f, data.get(f))

    if doc.meta.get_field("custom_kpws_welfare_type"):
        doc.custom_kpws_welfare_type = doc.get("purpose") or ""

    if doc.meta.get_field("custom_kpws_welfare_percentage"):
        doc.custom_kpws_welfare_percentage = float(doc.get("discount_value") or 0)

    if doc.meta.get_field("custom_kpws_assigned_panel_customer"):
        doc.custom_kpws_assigned_panel_customer = doc.get("custom_panel_customer") or ""


def install_client_script():
    if not frappe.db.exists("DocType", "Client Script"):
        return

    # Disable all old PRF scripts to stop forms becoming Unsaved on open.
    for row in frappe.get_all("Client Script", filters={"dt": DT}, fields=["name", "script"]):
        if row.name == CLIENT_SCRIPT_NAME:
            continue

        frappe.db.set_value("Client Script", row.name, "enabled", 0, update_modified=False)
        print("Disabled old PRF Client Script:", row.name)

    script = r'''
frappe.ui.form.on("Patient Registration Form", {
    setup(frm) {
        kpws_prf_safe_setup(frm);
    },
    refresh(frm) {
        kpws_prf_safe_setup(frm);

        if (!frm.is_new()) {
            frm.add_custom_button(__("Sync Patient Info"), function() {
                kpws_prf_safe_fetch(frm, true);
            });
        }
    },
    custom_patient(frm) {
        // Only when user changes Patient, not on every refresh.
        kpws_prf_safe_fetch(frm, true);
    },
    custom_mr_number(frm) {
        if (frm.doc.custom_mr_number && !frm.doc.custom_patient) {
            kpws_prf_safe_fetch(frm, true);
        }
    },
    purpose(frm) {
        kpws_prf_safe_sync_backend(frm);
    },
    discount_value(frm) {
        kpws_prf_safe_sync_backend(frm);
    },
    custom_panel_customer(frm) {
        kpws_prf_safe_sync_backend(frm);
    }
});

function kpws_prf_safe_has(frm, fieldname) {
    return frm.fields_dict && frm.fields_dict[fieldname];
}

function kpws_prf_safe_setup(frm) {
    if (kpws_prf_safe_has(frm, "custom_panel_customer")) {
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
        if (kpws_prf_safe_has(frm, f)) {
            frm.set_df_property(f, "read_only", 1);
        }
    });

    [
        "custom_kpws_welfare_type",
        "custom_kpws_welfare_percentage",
        "custom_kpws_assigned_panel_customer"
    ].forEach(function(f) {
        if (kpws_prf_safe_has(frm, f)) {
            frm.toggle_display(f, false);
        }
    });
}

function kpws_prf_safe_sync_backend(frm) {
    let updates = {};

    if (kpws_prf_safe_has(frm, "custom_kpws_welfare_type")) {
        updates.custom_kpws_welfare_type = frm.doc.purpose || "";
    }

    if (kpws_prf_safe_has(frm, "custom_kpws_welfare_percentage")) {
        updates.custom_kpws_welfare_percentage = flt(frm.doc.discount_value || 0);
    }

    if (kpws_prf_safe_has(frm, "custom_kpws_assigned_panel_customer")) {
        updates.custom_kpws_assigned_panel_customer = frm.doc.custom_panel_customer || "";
    }

    if (Object.keys(updates).length) {
        frm.set_value(updates);
    }
}

function kpws_prf_safe_fetch(frm, show_loader) {
    if (!frm.doc.custom_patient && !frm.doc.custom_mr_number) {
        return;
    }

    if (show_loader) {
        frappe.dom.freeze(__("Fetching patient information..."));
    }

    frappe.call({
        method: "kpws_customization.api.kpws_prf_safe_recovery.fetch_patient_details",
        args: {
            patient: frm.doc.custom_patient || "",
            mr_number: frm.doc.custom_mr_number || ""
        },
        freeze: false,
        callback: function(r) {
            let d = r.message || {};
            if (!d.custom_patient) return;

            let updates = {
                custom_patient: d.custom_patient || "",
                custom_mr_number: d.custom_mr_number || "",
                custom_patient_name: d.custom_patient_name || "",
                custom_patient_customer: d.custom_patient_customer || "",
                custom_billing_type: d.custom_billing_type || "",
                custom_gender: d.custom_gender || "",
                custom_dob: d.custom_dob || "",
                custom_blood_group: d.custom_blood_group || ""
            };

            [
                "custom_cnic",
                "custom_mobile",
                "custom_email",
                "custom_address",
                "custom_religion",
                "custom_sect",
                "custom_nationality",
                "custom_swo"
            ].forEach(function(f) {
                if (kpws_prf_safe_has(frm, f) && !frm.doc[f] && d[f]) {
                    updates[f] = d[f];
                }
            });

            frm.set_value(updates).then(function() {
                kpws_prf_safe_sync_backend(frm);
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
    print("Installed safe PRF client script.")
    print("Patient MR field used:", _patient_mr_field() or "NOT FOUND")
    print("Forms will no longer become Unsaved just by opening.")
