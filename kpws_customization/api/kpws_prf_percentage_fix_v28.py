from pathlib import Path
import frappe
from frappe.utils import flt
from frappe import _


DOCTYPE = "Patient Registration Form"
PATCH_MARKER = "KPWS_PRF_PERCENTAGE_FIX_V28_HOOK"

PERCENTAGE_FIELDS = [
    "discount_value",
    "custom_kpws_welfare_percentage",
]

ALLOW_UPDATE_AFTER_SUBMIT_FIELDS = [
    "discount_value",
    "custom_kpws_welfare_percentage",
    "purpose",
    "custom_kpws_welfare_type",
    "custom_kpws_admin_notes",
]


CLIENT_SCRIPT_NAME = "KPWS PRF Percentage Guard"


CLIENT_SCRIPT = r'''
frappe.ui.form.on("Patient Registration Form", {
    onload(frm) {
        kpws_prf_percentage_setup(frm);
    },

    refresh(frm) {
        kpws_prf_percentage_setup(frm);
    },

    validate(frm) {
        kpws_prf_validate_percentage(frm, true);
    }
});

function kpws_prf_percentage_setup(frm) {
    kpws_prf_inject_percentage_css();

    const fields = ["discount_value", "custom_kpws_welfare_percentage"];

    fields.forEach((fieldname) => {
        const field = frm.fields_dict[fieldname];

        if (!field || !field.$input) return;

        frm.set_df_property(fieldname, "allow_on_submit", 1);
        frm.set_df_property(fieldname, "read_only", 0);

        field.$wrapper.addClass("kpws-prf-no-spinner");

        field.$input.attr({
            min: 0,
            max: 100,
            step: "0.01",
            inputmode: "decimal"
        });

        field.$input.off("input.kpws_percentage_limit").on("input.kpws_percentage_limit", function () {
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
    });
}

function kpws_prf_validate_percentage(frm, throw_error) {
    const fields = ["discount_value", "custom_kpws_welfare_percentage"];

    fields.forEach((fieldname) => {
        if (!frm.fields_dict[fieldname]) return;

        const value = flt(frm.doc[fieldname]);

        if (value > 100) {
            frappe.validated = false;

            if (throw_error) {
                frappe.throw({
                    title: "Invalid Percentage",
                    message: "Percentage cannot be more than 100%."
                });
            }
        }

        if (value < 0) {
            frappe.validated = false;

            if (throw_error) {
                frappe.throw({
                    title: "Invalid Percentage",
                    message: "Percentage cannot be negative."
                });
            }
        }
    });
}

function kpws_prf_inject_percentage_css() {
    if (document.getElementById("kpws-prf-percentage-css")) return;

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
            font-weight: 800 !important;
        }
    `;

    const style = document.createElement("style");
    style.id = "kpws-prf-percentage-css";
    style.innerHTML = css;
    document.head.appendChild(style);
}
'''


def _field_exists(fieldname):
    try:
        return frappe.get_meta(DOCTYPE).has_field(fieldname)
    except Exception:
        return False


def _set_property(fieldname, prop, value, property_type):
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

    # If field is Custom Field, update it directly too.
    custom_field = frappe.db.exists("Custom Field", {
        "dt": DOCTYPE,
        "fieldname": fieldname,
    })

    if custom_field:
        try:
            if prop in frappe.get_meta("Custom Field").fields_map:
                frappe.db.set_value("Custom Field", custom_field, prop, value, update_modified=False)
        except Exception:
            pass

    return True


def _install_property_setters():
    changed = []

    for fieldname in ALLOW_UPDATE_AFTER_SUBMIT_FIELDS:
        if _set_property(fieldname, "allow_on_submit", "1", "Check"):
            changed.append(f"{fieldname}.allow_on_submit")

    for fieldname in PERCENTAGE_FIELDS:
        if _set_property(fieldname, "read_only", "0", "Check"):
            changed.append(f"{fieldname}.read_only")

        if _set_property(fieldname, "non_negative", "1", "Check"):
            changed.append(f"{fieldname}.non_negative")

        if _set_property(fieldname, "precision", "2", "Data"):
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


def _patch_hooks():
    app_path = Path(frappe.get_app_path("kpws_customization"))
    hooks_file = app_path / "hooks.py"

    text = hooks_file.read_text()

    if PATCH_MARKER in text:
        return False

    hook_block = f'''

# {PATCH_MARKER}
try:
    doc_events
except NameError:
    doc_events = {{}}

doc_events.setdefault("Patient Registration Form", {{}})

_existing_validate = doc_events["Patient Registration Form"].get("validate", [])

if isinstance(_existing_validate, str):
    _existing_validate = [_existing_validate]

if "kpws_customization.api.kpws_prf_percentage_fix_v28.validate_percentage" not in _existing_validate:
    _existing_validate.append("kpws_customization.api.kpws_prf_percentage_fix_v28.validate_percentage")

doc_events["Patient Registration Form"]["validate"] = _existing_validate
'''

    hooks_file.write_text(text + hook_block)
    return True


def validate_percentage(doc, method=None):
    for fieldname in PERCENTAGE_FIELDS:
        if not hasattr(doc, fieldname):
            continue

        value = doc.get(fieldname)

        if value in (None, ""):
            continue

        value = flt(value)

        if value < 0:
            frappe.throw(
                _("Percentage cannot be negative."),
                title=_("Invalid Percentage")
            )

        if value > 100:
            frappe.throw(
                _("Percentage cannot be more than 100%."),
                title=_("Invalid Percentage")
            )


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
        "doctype": DOCTYPE,
        "property_changes": property_changes,
        "client_script": client_script,
        "hooks_changed": hooks_changed,
        "message": "Patient Registration Form percentage update fixed."
    }


@frappe.whitelist()
def verify():
    meta = frappe.get_meta(DOCTYPE)

    fields = {}

    for fieldname in PERCENTAGE_FIELDS + ALLOW_UPDATE_AFTER_SUBMIT_FIELDS:
        if not meta.has_field(fieldname):
            fields[fieldname] = {"exists": False}
            continue

        df = meta.get_field(fieldname)

        fields[fieldname] = {
            "exists": True,
            "fieldtype": df.fieldtype,
            "label": df.label,
            "allow_on_submit": df.allow_on_submit,
            "read_only": df.read_only,
            "non_negative": getattr(df, "non_negative", None),
            "precision": getattr(df, "precision", None),
        }

    return {
        "doctype": DOCTYPE,
        "fields": fields,
        "client_script_exists": bool(frappe.db.exists("Client Script", CLIENT_SCRIPT_NAME)),
    }
