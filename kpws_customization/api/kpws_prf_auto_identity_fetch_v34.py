from pathlib import Path
import frappe
from frappe import _
from frappe.utils import flt


DOCTYPE = "Patient Registration Form"
PATCH_MARKER = "KPWS_PRF_AUTO_IDENTITY_FETCH_V34_HOOK"
CLIENT_SCRIPT_NAME = "KPWS PRF Auto Patient Identity Fetch"

IDENTITY_TARGET_FIELDS = [
    "custom_blood_group",
    "blood_group",
    "contact_no",
    "cnic",
    "swo",
    "religion1",
    "saction1",
    "nationality",
    "address",
]

PERCENTAGE_FIELDS = [
    "discount_value",
    "custom_kpws_welfare_percentage",
]

ALLOW_AFTER_SUBMIT_FIELDS = [
    "discount_value",
    "custom_kpws_welfare_percentage",
    "purpose",
    "custom_kpws_welfare_type",
    "custom_kpws_admin_notes",
    "remarks",
] + IDENTITY_TARGET_FIELDS

IGNORE_FIELDS = {
    "modified",
    "modified_by",
    "idx",
    "_user_tags",
    "_comments",
    "_assign",
    "_liked_by",
}


CLIENT_SCRIPT = r'''
frappe.ui.form.on("Patient Registration Form", {
    onload(frm) {
        kpws_prf_auto_identity_setup(frm);
    },

    refresh(frm) {
        kpws_prf_auto_identity_setup(frm);
    },

    custom_patient(frm) {
        kpws_prf_fetch_patient_identity(frm, true);
    },

    patient(frm) {
        kpws_prf_fetch_patient_identity(frm, true);
    },

    validate(frm) {
        kpws_prf_validate_percentage_v34(frm);
    }
});

function kpws_prf_get_patient(frm) {
    return frm.doc.custom_patient || frm.doc.patient || "";
}

function kpws_prf_auto_identity_setup(frm) {
    kpws_prf_inject_css_v34();

    if (frm.doc.docstatus === 2) {
        frm.disable_save();
        frm.dashboard.clear_headline();
        frm.dashboard.set_headline_alert(
            "This Patient Registration Form is cancelled and cannot be edited.",
            "red"
        );
        return;
    }

    const allow_fields = [
        "discount_value",
        "custom_kpws_welfare_percentage",
        "purpose",
        "custom_kpws_welfare_type",
        "custom_kpws_admin_notes",
        "remarks",
        "custom_blood_group",
        "blood_group",
        "contact_no",
        "cnic",
        "swo",
        "religion1",
        "saction1",
        "nationality",
        "address"
    ];

    allow_fields.forEach((fieldname) => {
        if (frm.fields_dict[fieldname]) {
            frm.set_df_property(fieldname, "allow_on_submit", 1);
        }
    });

    ["discount_value", "custom_kpws_welfare_percentage"].forEach((fieldname) => {
        if (!frm.fields_dict[fieldname]) return;

        frm.set_df_property(fieldname, "read_only", 0);

        const field = frm.fields_dict[fieldname];

        if (field && field.$input) {
            field.$wrapper.addClass("kpws-prf-no-spinner");

            field.$input.attr({
                min: 0,
                max: 100,
                step: "0.01",
                inputmode: "decimal"
            });

            field.$input.off("input.kpws_v34").on("input.kpws_v34", function () {
                let value = parseFloat($(this).val());

                if (isNaN(value)) return;

                if (value > 100) {
                    value = 100;
                    $(this).val(value);
                    frm.set_value(fieldname, value);
                    frappe.show_alert({
                        message: "Percentage cannot be more than 100%.",
                        indicator: "orange"
                    }, 5);
                }

                if (value < 0) {
                    value = 0;
                    $(this).val(value);
                    frm.set_value(fieldname, value);
                    frappe.show_alert({
                        message: "Percentage cannot be negative.",
                        indicator: "orange"
                    }, 5);
                }
            });
        }
    });

    // Important:
    // Automatically fetch patient identity when PRF opens with Patient already selected.
    if (kpws_prf_get_patient(frm) && !frm.__kpws_identity_loaded) {
        frm.__kpws_identity_loaded = true;

        setTimeout(() => {
            kpws_prf_fetch_patient_identity(frm, false);
        }, 300);
    }
}

function kpws_prf_fetch_patient_identity(frm, overwrite) {
    const patient = kpws_prf_get_patient(frm);

    if (!patient || frm.doc.docstatus === 2) return;

    frappe.call({
        method: "kpws_customization.api.kpws_prf_auto_identity_fetch_v34.get_patient_identity",
        args: {
            patient: patient
        },
        callback: function (r) {
            const values = (r.message && r.message.values) || {};

            Object.keys(values).forEach((fieldname) => {
                if (!frm.fields_dict[fieldname]) return;

                const current = frm.doc[fieldname];
                const value = values[fieldname];

                if (value === undefined || value === null || value === "") return;

                if (overwrite || current === undefined || current === null || current === "") {
                    frm.set_value(fieldname, value);
                }
            });
        }
    });
}

function kpws_prf_validate_percentage_v34(frm) {
    ["discount_value", "custom_kpws_welfare_percentage"].forEach((fieldname) => {
        if (!frm.fields_dict[fieldname]) return;

        const value = flt(frm.doc[fieldname]);

        if (value > 100) {
            frappe.validated = false;
            frappe.throw({
                title: "Invalid Percentage",
                message: "Percentage cannot be more than 100%."
            });
        }

        if (value < 0) {
            frappe.validated = false;
            frappe.throw({
                title: "Invalid Percentage",
                message: "Percentage cannot be negative."
            });
        }
    });
}

function kpws_prf_inject_css_v34() {
    if (document.getElementById("kpws-prf-auto-identity-v34-css")) return;

    const css = `
        .kpws-prf-no-spinner input[type=number]::-webkit-inner-spin-button,
        .kpws-prf-no-spinner input[type=number]::-webkit-outer-spin-button {
            -webkit-appearance: none !important;
            margin: 0 !important;
        }

        .kpws-prf-no-spinner input[type=number] {
            -moz-appearance: textfield !important;
            appearance: textfield !important;
        }

        .frappe-control[data-fieldname="discount_value"] input,
        .frappe-control[data-fieldname="custom_kpws_welfare_percentage"] input {
            font-weight: 850 !important;
        }
    `;

    const style = document.createElement("style");
    style.id = "kpws-prf-auto-identity-v34-css";
    style.innerHTML = css;
    document.head.appendChild(style);
}
'''


def _has_field(doctype, fieldname):
    try:
        return frappe.get_meta(doctype).has_field(fieldname)
    except Exception:
        return False


def _doc_get(doc, fields, default=""):
    for fieldname in fields:
        if doc.meta.has_field(fieldname) and doc.get(fieldname) not in (None, ""):
            return doc.get(fieldname)
    return default


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


def _patient_identity_values(patient):
    if not patient or not frappe.db.exists("Patient", patient):
        return {}

    pdoc = frappe.get_doc("Patient", patient)

    address = _doc_get(
        pdoc,
        [
            "address",
            "custom_address",
            "residential_address",
            "custom_residential_address",
            "permanent_address",
            "custom_permanent_address",
        ],
        "",
    )

    if not address:
        address = _linked_address_for_patient(patient)

    values = {
        "custom_blood_group": _doc_get(pdoc, ["blood_group", "custom_blood_group"], ""),
        "blood_group": _doc_get(pdoc, ["blood_group", "custom_blood_group"], ""),

        "contact_no": _doc_get(
            pdoc,
            [
                "mobile",
                "mobile_no",
                "phone",
                "contact_no",
                "custom_contact_no",
                "custom_mobile_no",
                "patient_mobile",
            ],
            "",
        ),

        "cnic": _doc_get(
            pdoc,
            [
                "cnic",
                "custom_cnic",
                "national_id",
                "custom_national_id",
                "nic",
                "custom_nic",
            ],
            "",
        ),

        "swo": _doc_get(
            pdoc,
            [
                "swo",
                "custom_swo",
                "s_w_o",
                "custom_s_w_o",
                "father_name",
                "custom_father_name",
                "guardian_name",
                "custom_guardian_name",
                "spouse_name",
                "custom_spouse_name",
            ],
            "",
        ),

        "religion1": _doc_get(
            pdoc,
            [
                "religion",
                "custom_religion",
                "religion1",
            ],
            "",
        ),

        "saction1": _doc_get(
            pdoc,
            [
                "saction",
                "custom_saction",
                "sect",
                "custom_sect",
                "section",
                "custom_section",
                "saction1",
            ],
            "",
        ),

        "nationality": _doc_get(
            pdoc,
            [
                "nationality",
                "custom_nationality",
            ],
            "",
        ),

        "address": address,
    }

    return {
        fieldname: value
        for fieldname, value in values.items()
        if _has_field(DOCTYPE, fieldname)
    }


@frappe.whitelist()
def get_patient_identity(patient):
    if not patient:
        frappe.throw(_("Please select Patient first."))

    return {
        "patient": patient,
        "values": _patient_identity_values(patient),
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

    values = _patient_identity_values(patient)
    changed = []

    for fieldname, value in values.items():
        if fieldname not in IDENTITY_TARGET_FIELDS:
            continue

        if not doc.meta.has_field(fieldname):
            continue

        if value in (None, ""):
            continue

        if overwrite or doc.get(fieldname) in (None, ""):
            doc.set(fieldname, value)
            changed.append(fieldname)

    return changed


def validate_percentage(doc, method=None):
    for fieldname in PERCENTAGE_FIELDS:
        if not doc.meta.has_field(fieldname):
            continue

        value = doc.get(fieldname)

        if value in (None, ""):
            continue

        value = flt(value)

        if value < 0:
            frappe.throw(_("Percentage cannot be negative."), title=_("Invalid Percentage"))

        if value > 100:
            frappe.throw(_("Percentage cannot be more than 100%."), title=_("Invalid Percentage"))


def _changed_fields(doc):
    before = doc.get_doc_before_save()

    if not before:
        return []

    changed = []

    for df in doc.meta.fields:
        fieldname = df.fieldname

        if not fieldname or fieldname in IGNORE_FIELDS:
            continue

        if df.fieldtype in ("Table", "Table MultiSelect"):
            continue

        if before.get(fieldname) != doc.get(fieldname):
            changed.append(fieldname)

    return changed


def before_insert(doc, method=None):
    # Server-side guarantee:
    # whenever PRF is generated from Patient / API / button,
    # identity fields are filled before insert.
    populate_identity_from_patient(doc, overwrite=False)


def before_save(doc, method=None):
    if doc.docstatus == 2:
        frappe.throw(
            _("Cancelled Patient Registration Form cannot be edited."),
            title=_("Cannot Edit Cancelled Document")
        )

    validate_percentage(doc)

    # Keep missing identity fields synced from Patient on every save.
    populate_identity_from_patient(doc, overwrite=False)

    if doc.docstatus != 1:
        return

    allowed = set(ALLOW_AFTER_SUBMIT_FIELDS)
    changed = _changed_fields(doc)

    not_allowed = [
        fieldname for fieldname in changed
        if fieldname not in allowed
    ]

    if not_allowed:
        frappe.throw(
            _("Only Purpose, Percentage, Admin Notes, Remarks and Patient Identity fields can be changed after submission. Not allowed: {0}").format(
                ", ".join(not_allowed)
            ),
            title=_("Update After Submit Blocked")
        )

    doc.flags.ignore_validate_update_after_submit = True


def _upsert_property_setter(fieldname, prop, value, property_type):
    if not _has_field(DOCTYPE, fieldname):
        return False

    existing = frappe.db.exists("Property Setter", {
        "doc_type": DOCTYPE,
        "doctype_or_field": "DocField",
        "field_name": fieldname,
        "property": prop,
    })

    if existing:
        ps = frappe.get_doc("Property Setter", existing)
        ps.value = value
        ps.property_type = property_type
        ps.save(ignore_permissions=True)
    else:
        frappe.get_doc({
            "doctype": "Property Setter",
            "doctype_or_field": "DocField",
            "doc_type": DOCTYPE,
            "field_name": fieldname,
            "property": prop,
            "property_type": property_type,
            "value": value,
        }).insert(ignore_permissions=True)

    return True


def _install_properties():
    changed = []

    for fieldname in ALLOW_AFTER_SUBMIT_FIELDS:
        if _upsert_property_setter(fieldname, "allow_on_submit", "1", "Check"):
            changed.append(f"{fieldname}.allow_on_submit")

    for fieldname in PERCENTAGE_FIELDS:
        if _upsert_property_setter(fieldname, "read_only", "0", "Check"):
            changed.append(f"{fieldname}.read_only")
        if _upsert_property_setter(fieldname, "non_negative", "1", "Check"):
            changed.append(f"{fieldname}.non_negative")
        if _upsert_property_setter(fieldname, "precision", "2", "Data"):
            changed.append(f"{fieldname}.precision")

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

def _kpws_append_prf_hook(event_name, method_path):
    existing = doc_events["Patient Registration Form"].get(event_name, [])
    if isinstance(existing, str):
        existing = [existing]
    if method_path not in existing:
        existing.append(method_path)
    doc_events["Patient Registration Form"][event_name] = existing

_kpws_append_prf_hook("before_insert", "kpws_customization.api.kpws_prf_auto_identity_fetch_v34.before_insert")
_kpws_append_prf_hook("before_save", "kpws_customization.api.kpws_prf_auto_identity_fetch_v34.before_save")
_kpws_append_prf_hook("validate", "kpws_customization.api.kpws_prf_auto_identity_fetch_v34.validate_percentage")
'''

    hooks_file.write_text(text + block)
    return True


@frappe.whitelist()
def install():
    properties = _install_properties()
    client_script = _upsert_client_script()
    hooks_changed = _patch_hooks()

    frappe.clear_cache(doctype=DOCTYPE)
    frappe.clear_cache()
    frappe.db.commit()

    return {
        "ok": True,
        "properties": properties,
        "client_script": client_script,
        "hooks_changed": hooks_changed,
        "message": "PRF identity fields now auto-fetch from Patient on initial creation/opening, no button needed.",
    }


@frappe.whitelist()
def verify(patient=None, prf=None):
    out = {
        "patient_identity": None,
        "prf": None,
    }

    if patient:
        out["patient_identity"] = _patient_identity_values(patient)

    if prf and frappe.db.exists(DOCTYPE, prf):
        fields = ["name", "docstatus"]

        for f in [
            "custom_patient",
            "patient",
            "custom_blood_group",
            "blood_group",
            "contact_no",
            "cnic",
            "swo",
            "religion1",
            "saction1",
            "nationality",
            "address",
            "discount_value",
            "custom_kpws_welfare_percentage",
        ]:
            if _has_field(DOCTYPE, f):
                fields.append(f)

        out["prf"] = frappe.db.get_value(DOCTYPE, prf, fields, as_dict=True)

    return out
