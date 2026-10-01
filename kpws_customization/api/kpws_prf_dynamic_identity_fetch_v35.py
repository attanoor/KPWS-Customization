import re
from pathlib import Path
import frappe
from frappe import _


DOCTYPE = "Patient Registration Form"
PATCH_MARKER = "KPWS_PRF_DYNAMIC_IDENTITY_FETCH_V35_HOOK"
CLIENT_SCRIPT_NAME = "KPWS PRF Dynamic Patient Identity Fetch"


IDENTITY_KEYS = {
    "blood_group": {
        "labels": ["bloodgroup", "bloodgrp"],
        "target_prefer": ["custom_blood_group", "blood_group"],
    },
    "contact_no": {
        "labels": ["contactno", "contactnumber", "mobileno", "mobile", "phone", "phoneno", "cellno"],
        "target_prefer": ["contact_no", "mobile_no", "custom_contact_no"],
    },
    "cnic": {
        "labels": ["cnic", "nic", "nationalid", "nationalidentity"],
        "target_prefer": ["cnic", "custom_cnic"],
    },
    "swo": {
        "labels": ["swo", "sw/o", "sonof", "daughterof", "wifeof", "fathername", "guardianname", "spousename"],
        "target_prefer": ["swo", "custom_swo"],
    },
    "religion": {
        "labels": ["religion"],
        "target_prefer": ["religion1", "religion", "custom_religion"],
    },
    "saction": {
        "labels": ["saction", "sect", "section", "sectsection"],
        "target_prefer": ["saction1", "saction", "sect", "custom_saction", "custom_sect"],
    },
    "nationality": {
        "labels": ["nationality"],
        "target_prefer": ["nationality", "custom_nationality"],
    },
    "address": {
        "labels": ["address", "residentialaddress", "permanentaddress", "currentaddress", "homeaddress"],
        "target_prefer": ["address", "custom_address"],
    },
}


CLIENT_SCRIPT = r'''
frappe.ui.form.on("Patient Registration Form", {
    onload(frm) {
        kpws_prf_dynamic_identity_setup(frm);
    },

    refresh(frm) {
        kpws_prf_dynamic_identity_setup(frm);
    },

    custom_patient(frm) {
        kpws_prf_dynamic_identity_fetch(frm, true);
    },

    patient(frm) {
        kpws_prf_dynamic_identity_fetch(frm, true);
    }
});

function kpws_prf_dynamic_get_patient(frm) {
    return frm.doc.custom_patient || frm.doc.patient || "";
}

function kpws_prf_dynamic_identity_setup(frm) {
    if (frm.doc.docstatus === 2) {
        frm.disable_save();
        return;
    }

    if (kpws_prf_dynamic_get_patient(frm) && !frm.__kpws_dynamic_identity_loaded) {
        frm.__kpws_dynamic_identity_loaded = true;
        setTimeout(() => {
            kpws_prf_dynamic_identity_fetch(frm, false);
        }, 400);
    }
}

function kpws_prf_dynamic_identity_fetch(frm, overwrite) {
    const patient = kpws_prf_dynamic_get_patient(frm);

    if (!patient || frm.doc.docstatus === 2) return;

    frappe.call({
        method: "kpws_customization.api.kpws_prf_dynamic_identity_fetch_v35.get_patient_identity",
        args: {
            patient: patient
        },
        callback: function (r) {
            const values = (r.message && r.message.values) || {};

            Object.keys(values).forEach((fieldname) => {
                if (!frm.fields_dict[fieldname]) return;

                const value = values[fieldname];
                const current = frm.doc[fieldname];

                if (value === undefined || value === null || value === "") return;

                if (overwrite || current === undefined || current === null || current === "") {
                    frm.set_value(fieldname, value);
                }
            });
        }
    });
}
'''


def _norm(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def _has_field(doctype, fieldname):
    try:
        return frappe.get_meta(doctype).has_field(fieldname)
    except Exception:
        return False


def _field_score(df, key):
    fieldname = _norm(df.fieldname)
    label = _norm(df.label)
    options = _norm(df.options)

    labels = set(_norm(x) for x in IDENTITY_KEYS[key]["labels"])
    preferred = set(_norm(x) for x in IDENTITY_KEYS[key]["target_prefer"])

    if fieldname in preferred:
        return 100

    if label in labels:
        return 90

    if fieldname in labels:
        return 80

    if any(x and x in label for x in labels):
        return 70

    if any(x and x in fieldname for x in labels):
        return 60

    if key == "blood_group" and options == "bloodgroup":
        return 95

    return 0


def _best_fields(doctype, key, only_readable=True):
    meta = frappe.get_meta(doctype)
    matches = []

    skip_types = {
        "Section Break",
        "Column Break",
        "Tab Break",
        "HTML",
        "Button",
        "Table",
        "Table MultiSelect",
    }

    for df in meta.fields:
        if not df.fieldname or df.fieldtype in skip_types:
            continue

        score = _field_score(df, key)
        if score > 0:
            matches.append({
                "fieldname": df.fieldname,
                "label": df.label,
                "fieldtype": df.fieldtype,
                "score": score,
            })

    matches = sorted(matches, key=lambda x: x["score"], reverse=True)
    return matches


def _best_source_field(patient_doc, key):
    matches = _best_fields("Patient", key)

    for row in matches:
        value = patient_doc.get(row["fieldname"])
        if value not in (None, ""):
            return row["fieldname"], value, matches

    return None, "", matches


def _target_fields(key):
    matches = _best_fields(DOCTYPE, key)
    preferred = IDENTITY_KEYS[key]["target_prefer"]

    output = []

    for p in preferred:
        if _has_field(DOCTYPE, p):
            output.append(p)

    for row in matches:
        if row["fieldname"] not in output:
            output.append(row["fieldname"])

    return output


def _format_address(address_name):
    if not address_name or not frappe.db.exists("Address", address_name):
        return ""

    address = frappe.get_doc("Address", address_name)

    parts = [
        address.get("address_line1"),
        address.get("address_line2"),
        address.get("city"),
        address.get("state"),
        address.get("country"),
        address.get("pincode"),
    ]

    return ", ".join([str(x).strip() for x in parts if x])


def _linked_address_for_patient(patient):
    try:
        rows = frappe.get_all(
            "Dynamic Link",
            filters={
                "link_doctype": "Patient",
                "link_name": patient,
                "parenttype": "Address",
            },
            fields=["parent"],
            order_by="creation desc",
            limit_page_length=1,
        )

        if rows:
            return _format_address(rows[0].parent)
    except Exception:
        pass

    return ""


def _identity_values(patient):
    if not patient or not frappe.db.exists("Patient", patient):
        return {}, {}

    patient_doc = frappe.get_doc("Patient", patient)

    values = {}
    debug = {}

    for key in IDENTITY_KEYS:
        source_field, value, source_matches = _best_source_field(patient_doc, key)

        if key == "address" and not value:
            value = _linked_address_for_patient(patient)
            if value:
                source_field = "Dynamic Link Address"

        targets = _target_fields(key)

        debug[key] = {
            "source_field": source_field,
            "source_value": value,
            "source_matches": source_matches[:10],
            "target_fields": targets,
        }

        if value in (None, ""):
            continue

        for target in targets:
            values[target] = value

    return values, debug


@frappe.whitelist()
def get_patient_identity(patient):
    values, debug = _identity_values(patient)

    return {
        "patient": patient,
        "values": values,
        "debug": debug,
    }


def _patient_from_prf(doc):
    for fieldname in ["custom_patient", "patient"]:
        if doc.meta.has_field(fieldname) and doc.get(fieldname):
            return doc.get(fieldname)

    return None


def populate_identity_from_patient(doc, overwrite=False):
    patient = _patient_from_prf(doc)

    if not patient:
        return []

    values, debug = _identity_values(patient)
    changed = []

    for fieldname, value in values.items():
        if not doc.meta.has_field(fieldname):
            continue

        if value in (None, ""):
            continue

        if overwrite or doc.get(fieldname) in (None, ""):
            doc.set(fieldname, value)
            changed.append(fieldname)

    return changed


def before_insert(doc, method=None):
    populate_identity_from_patient(doc, overwrite=False)


def before_save(doc, method=None):
    if doc.docstatus == 2:
        frappe.throw(_("Cancelled Patient Registration Form cannot be edited."))

    populate_identity_from_patient(doc, overwrite=False)

    if doc.docstatus == 1:
        doc.flags.ignore_validate_update_after_submit = True


def _install_property_setters():
    changed = []

    all_targets = set()

    for key in IDENTITY_KEYS:
        for fieldname in _target_fields(key):
            all_targets.add(fieldname)

    for fieldname in sorted(all_targets):
        existing = frappe.db.exists("Property Setter", {
            "doc_type": DOCTYPE,
            "doctype_or_field": "DocField",
            "field_name": fieldname,
            "property": "allow_on_submit",
        })

        if existing:
            ps = frappe.get_doc("Property Setter", existing)
            ps.value = "1"
            ps.property_type = "Check"
            ps.save(ignore_permissions=True)
        else:
            frappe.get_doc({
                "doctype": "Property Setter",
                "doctype_or_field": "DocField",
                "doc_type": DOCTYPE,
                "field_name": fieldname,
                "property": "allow_on_submit",
                "property_type": "Check",
                "value": "1",
            }).insert(ignore_permissions=True)

        changed.append(fieldname)

    frappe.db.commit()
    return changed


def _upsert_client_script():
    if not frappe.db.exists("DocType", "Client Script"):
        return None

    existing = frappe.db.exists("Client Script", CLIENT_SCRIPT_NAME)

    if existing:
        doc = frappe.get_doc("Client Script", existing)
    else:
        doc = frappe.new_doc("Client Script")
        doc.name = CLIENT_SCRIPT_NAME

    doc.dt = DOCTYPE
    doc.script = CLIENT_SCRIPT
    doc.enabled = 1

    if doc.meta.has_field("script_type"):
        doc.script_type = "Client"

    doc.save(ignore_permissions=True)
    return doc.name


def _patch_hooks():
    app_path = Path(frappe.get_app_path("kpws_customization"))
    hooks_file = app_path / "hooks.py"

    text = hooks_file.read_text()

    if PATCH_MARKER in text:
        return False

    block = f'''

# {PATCH_MARKER}
try:
    doc_events
except NameError:
    doc_events = {{}}

doc_events.setdefault("Patient Registration Form", {{}})

def _kpws_prf_v35_append(event_name, method_path):
    existing = doc_events["Patient Registration Form"].get(event_name, [])
    if isinstance(existing, str):
        existing = [existing]
    if method_path not in existing:
        existing.append(method_path)
    doc_events["Patient Registration Form"][event_name] = existing

_kpws_prf_v35_append("before_insert", "kpws_customization.api.kpws_prf_dynamic_identity_fetch_v35.before_insert")
_kpws_prf_v35_append("before_save", "kpws_customization.api.kpws_prf_dynamic_identity_fetch_v35.before_save")
'''

    hooks_file.write_text(text + block)
    return True


@frappe.whitelist()
def install():
    client_script = _upsert_client_script()
    properties = _install_property_setters()
    hooks_changed = _patch_hooks()

    frappe.clear_cache(doctype=DOCTYPE)
    frappe.clear_cache()
    frappe.db.commit()

    return {
        "ok": True,
        "client_script": client_script,
        "identity_target_fields_allow_on_submit": properties,
        "hooks_changed": hooks_changed,
        "message": "Dynamic patient identity fetch installed for PRF.",
    }


@frappe.whitelist()
def debug_mapping(patient):
    values, debug = _identity_values(patient)

    return {
        "patient": patient,
        "values_to_set_on_prf": values,
        "mapping_debug": debug,
    }


@frappe.whitelist()
def backfill_existing_prfs(limit=0, overwrite=0):
    limit = int(limit or 0)
    overwrite = bool(int(overwrite or 0))

    fields = ["name", "docstatus"]

    for f in ["custom_patient", "patient"]:
        if _has_field(DOCTYPE, f):
            fields.append(f)

    rows = frappe.get_all(
        DOCTYPE,
        filters={"docstatus": ["!=", 2]},
        fields=fields,
        order_by="creation desc",
        limit_page_length=limit or 0,
    )

    updated = []
    skipped = []

    for row in rows:
        try:
            doc = frappe.get_doc(DOCTYPE, row.name)

            if not _patient_from_prf(doc):
                skipped.append({"prf": row.name, "reason": "No patient linked"})
                continue

            changed = populate_identity_from_patient(doc, overwrite=overwrite)

            if not changed:
                skipped.append({"prf": row.name, "reason": "No missing identity values"})
                continue

            # Use db_set to avoid update-after-submit friction during migration/backfill.
            for fieldname in changed:
                frappe.db.set_value(DOCTYPE, doc.name, fieldname, doc.get(fieldname), update_modified=False)

            updated.append({
                "prf": row.name,
                "changed_fields": changed,
            })

        except Exception as e:
            skipped.append({"prf": row.name, "reason": str(e)})

    frappe.db.commit()

    return {
        "checked": len(rows),
        "updated_count": len(updated),
        "skipped_count": len(skipped),
        "updated": updated[:50],
        "skipped": skipped[:50],
    }
