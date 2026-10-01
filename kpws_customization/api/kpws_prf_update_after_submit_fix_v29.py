from pathlib import Path
import frappe
from frappe import _
from frappe.utils import flt


DOCTYPE = "Patient Registration Form"
PATCH_MARKER = "KPWS_PRF_UPDATE_AFTER_SUBMIT_FIX_V29_HOOK"

PERCENTAGE_FIELDS = [
    "discount_value",
    "custom_kpws_welfare_percentage",
]

ALLOWED_UPDATE_AFTER_SUBMIT_FIELDS = [
    "discount_value",
    "custom_kpws_welfare_percentage",
    "purpose",
    "custom_kpws_welfare_type",
    "custom_kpws_admin_notes",
    "remarks",
]

IGNORE_FIELDS = {
    "modified",
    "modified_by",
    "idx",
    "_user_tags",
    "_comments",
    "_assign",
    "_liked_by",
}


CLIENT_SCRIPT_NAME = "KPWS PRF Percentage and Submit Guard"


CLIENT_SCRIPT = r'''
frappe.ui.form.on("Patient Registration Form", {
    onload(frm) {
        kpws_prf_v29_setup(frm);
    },

    refresh(frm) {
        kpws_prf_v29_setup(frm);
    },

    validate(frm) {
        kpws_prf_v29_validate_percentage(frm);
    }
});

function kpws_prf_v29_setup(frm) {
    kpws_prf_v29_inject_css();

    if (frm.doc.docstatus === 2) {
        frm.dashboard.clear_headline();
        frm.dashboard.set_headline_alert(
            "This Patient Registration Form is cancelled. Cancelled documents cannot be edited. Please open the amended/active form or create a new form.",
            "red"
        );

        frm.disable_save();
        return;
    }

    const fields = [
        "discount_value",
        "custom_kpws_welfare_percentage",
        "purpose",
        "custom_kpws_welfare_type",
        "custom_kpws_admin_notes",
        "remarks"
    ];

    fields.forEach((fieldname) => {
        if (!frm.fields_dict[fieldname]) return;

        frm.set_df_property(fieldname, "allow_on_submit", 1);

        if (["discount_value", "custom_kpws_welfare_percentage"].includes(fieldname)) {
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

                field.$input.off("input.kpws_prf_v29").on("input.kpws_prf_v29", function () {
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
        }
    });
}

function kpws_prf_v29_validate_percentage(frm) {
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

function kpws_prf_v29_inject_css() {
    if (document.getElementById("kpws-prf-v29-css")) return;

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
    style.id = "kpws-prf-v29-css";
    style.innerHTML = css;
    document.head.appendChild(style);
}
'''


def _field_exists(fieldname):
    try:
        return frappe.get_meta(DOCTYPE).has_field(fieldname)
    except Exception:
        return False


def _upsert_property_setter(fieldname, prop, value, property_type):
    if not _field_exists(fieldname):
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


def _install_property_setters():
    changed = []

    for fieldname in ALLOWED_UPDATE_AFTER_SUBMIT_FIELDS:
        if _upsert_property_setter(fieldname, "allow_on_submit", "1", "Check"):
            changed.append(f"{fieldname}.allow_on_submit")

    for fieldname in PERCENTAGE_FIELDS:
        if _upsert_property_setter(fieldname, "read_only", "0", "Check"):
            changed.append(f"{fieldname}.read_only")

        if _upsert_property_setter(fieldname, "non_negative", "1", "Check"):
            changed.append(f"{fieldname}.non_negative")

        if _upsert_property_setter(fieldname, "precision", "2", "Data"):
            changed.append(f"{fieldname}.precision")

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

        old = before.get(fieldname)
        new = doc.get(fieldname)

        if old != new:
            changed.append(fieldname)

    return changed


def validate_percentage(doc, method=None):
    for fieldname in PERCENTAGE_FIELDS:
        if not hasattr(doc, fieldname):
            continue

        value = doc.get(fieldname)

        if value in (None, ""):
            continue

        value = flt(value)

        if value < 0:
            frappe.throw(_("Percentage cannot be negative."), title=_("Invalid Percentage"))

        if value > 100:
            frappe.throw(_("Percentage cannot be more than 100%."), title=_("Invalid Percentage"))


def allow_limited_update_after_submit(doc, method=None):
    if doc.docstatus == 2:
        frappe.throw(
            _("Cancelled Patient Registration Form cannot be edited. Please use the amended/active form."),
            title=_("Cannot Edit Cancelled Document")
        )

    validate_percentage(doc)

    if doc.docstatus != 1:
        return

    changed = _changed_fields(doc)

    not_allowed = [
        fieldname for fieldname in changed
        if fieldname not in ALLOWED_UPDATE_AFTER_SUBMIT_FIELDS
    ]

    if not_allowed:
        frappe.throw(
            _("Only Purpose, Percentage, Admin Notes and Remarks can be changed after submission. Not allowed: {0}").format(
                ", ".join(not_allowed)
            ),
            title=_("Update After Submit Blocked")
        )

    # Critical: allow only the approved fields to pass Frappe update-after-submit validation.
    doc.flags.ignore_validate_update_after_submit = True


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

_existing_validate = doc_events["Patient Registration Form"].get("validate", [])
if isinstance(_existing_validate, str):
    _existing_validate = [_existing_validate]
if "kpws_customization.api.kpws_prf_update_after_submit_fix_v29.validate_percentage" not in _existing_validate:
    _existing_validate.append("kpws_customization.api.kpws_prf_update_after_submit_fix_v29.validate_percentage")
doc_events["Patient Registration Form"]["validate"] = _existing_validate

_existing_before_save = doc_events["Patient Registration Form"].get("before_save", [])
if isinstance(_existing_before_save, str):
    _existing_before_save = [_existing_before_save]
if "kpws_customization.api.kpws_prf_update_after_submit_fix_v29.allow_limited_update_after_submit" not in _existing_before_save:
    _existing_before_save.append("kpws_customization.api.kpws_prf_update_after_submit_fix_v29.allow_limited_update_after_submit")
doc_events["Patient Registration Form"]["before_save"] = _existing_before_save
'''

    hooks_file.write_text(text + block)
    return True


@frappe.whitelist()
def install():
    property_changes = _install_property_setters()
    client_script = _upsert_client_script()
    hooks_changed = _patch_hooks()

    frappe.clear_cache(doctype=DOCTYPE)
    frappe.clear_cache()
    frappe.db.commit()

    return {
        "ok": True,
        "property_changes": property_changes,
        "client_script": client_script,
        "hooks_changed": hooks_changed,
        "message": "PRF submitted percentage update fixed and cancelled document editing blocked clearly."
    }


@frappe.whitelist()
def verify(name=None):
    meta = frappe.get_meta(DOCTYPE)

    fields = {}

    for fieldname in sorted(set(PERCENTAGE_FIELDS + ALLOWED_UPDATE_AFTER_SUBMIT_FIELDS)):
        if not meta.has_field(fieldname):
            fields[fieldname] = {"exists": False}
            continue

        df = meta.get_field(fieldname)

        fields[fieldname] = {
            "exists": True,
            "label": df.label,
            "fieldtype": df.fieldtype,
            "allow_on_submit": df.allow_on_submit,
            "read_only": df.read_only,
            "non_negative": getattr(df, "non_negative", None),
            "precision": getattr(df, "precision", None),
        }

    docinfo = None

    if name and frappe.db.exists(DOCTYPE, name):
        docinfo = frappe.db.get_value(
            DOCTYPE,
            name,
            ["name", "docstatus", "amended_from", "discount_value", "custom_kpws_welfare_percentage"],
            as_dict=True
        )

    return {
        "doctype": DOCTYPE,
        "fields": fields,
        "client_script_exists": bool(frappe.db.exists("Client Script", CLIENT_SCRIPT_NAME)),
        "doc": docinfo,
    }
