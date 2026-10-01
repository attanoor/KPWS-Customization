from pathlib import Path
import frappe
from frappe import _


DOCTYPE = "Patient Registration Form"
CLIENT_SCRIPT_NAME = "KPWS PRF Panel Update After Submit"
PATCH_MARKER = "KPWS_PRF_PANEL_UPDATE_AFTER_SUBMIT_V42_HOOK"


BASE_ALLOWED_FIELDS = [
    "purpose",
    "custom_kpws_welfare_type",
    "discount_type",
    "discount_value",
    "custom_kpws_welfare_percentage",
    "custom_kpws_admin_notes",
    "remarks",
    "workflow_state",
    "status",
]


def _has_field(doctype, fieldname):
    try:
        return frappe.get_meta(doctype).has_field(fieldname)
    except Exception:
        return False


def _columns(table):
    try:
        return {r["Field"] for r in frappe.db.sql(f"SHOW COLUMNS FROM `{table}`", as_dict=True)}
    except Exception:
        return set()


def _panel_fields():
    meta = frappe.get_meta(DOCTYPE)
    fields = set()

    known = [
        "custom_panel_customer",
        "panel_customer",
        "panel",
        "custom_panel",
        "custom_kpws_assigned_panel_customer",
        "custom_kpws_panel_customer",
        "custom_kpws_assigned_panel",
        "custom_kpws_assigned_panel_customer",
        "custom_kpws_assigned_panel_name",
        "custom_kpws_panel_name",
        "custom_kpws_assigned_panel_customer",
        "custom_kpws_assigned_panel_customer",
    ]

    for fieldname in known:
        if meta.has_field(fieldname):
            fields.add(fieldname)

    for df in meta.fields:
        label = (df.label or "").strip().lower()
        fieldname = (df.fieldname or "").strip().lower()

        if not df.fieldname:
            continue

        if "panel" in label or "panel" in fieldname:
            fields.add(df.fieldname)

    return sorted(fields)


def _all_allowed_fields():
    fields = set(BASE_ALLOWED_FIELDS)
    fields.update(_panel_fields())

    # Also allow identity fields already used in PRF.
    for fieldname in [
        "custom_blood_group",
        "blood_group",
        "contact_no",
        "cnic",
        "swo",
        "religion1",
        "saction1",
        "nationality",
        "address",
    ]:
        if _has_field(DOCTYPE, fieldname):
            fields.add(fieldname)

    return sorted(fields)


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


def _force_field_metadata():
    fields = _all_allowed_fields()
    panel_fields = _panel_fields()

    docfield_cols = _columns("tabDocField")
    customfield_cols = _columns("tabCustom Field")

    changed = []

    for fieldname in fields:
        _upsert_property_setter(fieldname, "allow_on_submit", "1", "Check")
        changed.append(f"{fieldname}.allow_on_submit")

        if "allow_on_submit" in docfield_cols:
            frappe.db.sql(
                """
                UPDATE `tabDocField`
                SET allow_on_submit = 1
                WHERE parent = %s AND fieldname = %s
                """,
                (DOCTYPE, fieldname),
            )

        if "allow_on_submit" in customfield_cols:
            frappe.db.sql(
                """
                UPDATE `tabCustom Field`
                SET allow_on_submit = 1
                WHERE dt = %s AND fieldname = %s
                """,
                (DOCTYPE, fieldname),
            )

    for fieldname in panel_fields:
        _upsert_property_setter(fieldname, "read_only", "0", "Check")
        changed.append(f"{fieldname}.read_only")

        if "read_only" in docfield_cols:
            frappe.db.sql(
                """
                UPDATE `tabDocField`
                SET read_only = 0
                WHERE parent = %s AND fieldname = %s
                """,
                (DOCTYPE, fieldname),
            )

        if "read_only" in customfield_cols:
            frappe.db.sql(
                """
                UPDATE `tabCustom Field`
                SET read_only = 0
                WHERE dt = %s AND fieldname = %s
                """,
                (DOCTYPE, fieldname),
            )

    frappe.db.commit()
    frappe.clear_cache(doctype=DOCTYPE)
    frappe.clear_cache()

    return changed


def _changed_fields(doc):
    before = doc.get_doc_before_save()
    if not before:
        return []

    changed = []

    ignore = {
        "modified",
        "modified_by",
        "idx",
        "_user_tags",
        "_comments",
        "_assign",
        "_liked_by",
    }

    for df in doc.meta.fields:
        fieldname = df.fieldname

        if not fieldname or fieldname in ignore:
            continue

        if df.fieldtype in ("Table", "Table MultiSelect", "Section Break", "Column Break", "Tab Break", "HTML", "Button"):
            continue

        if before.get(fieldname) != doc.get(fieldname):
            changed.append(fieldname)

    return changed


def allow_panel_update_after_submit(doc, method=None):
    if doc.docstatus == 2:
        frappe.throw(_("Cancelled Patient Registration Form cannot be edited."))

    if doc.docstatus != 1:
        return

    allowed = set(_all_allowed_fields())
    changed = _changed_fields(doc)

    not_allowed = [fieldname for fieldname in changed if fieldname not in allowed]

    if not_allowed:
        frappe.throw(
            _("Only Purpose, Percentage, Panel, Remarks and identity fields can be changed after submission. Not allowed: {0}").format(
                ", ".join(not_allowed)
            ),
            title=_("Update After Submit Blocked")
        )

    doc.flags.ignore_validate_update_after_submit = True


CLIENT_SCRIPT = r'''
frappe.ui.form.on("Patient Registration Form", {
    onload(frm) {
        kpws_prf_panel_v42_setup(frm);
    },

    refresh(frm) {
        kpws_prf_panel_v42_setup(frm);
    },

    validate(frm) {
        kpws_prf_panel_v42_fix_docstatus(frm);
    },

    before_save(frm) {
        kpws_prf_panel_v42_fix_docstatus(frm);
    }
});

function kpws_prf_panel_v42_setup(frm) {
    // Remember original submitted state.
    if (frm.doc && frm.doc.docstatus === 1) {
        frm.__kpws_original_docstatus = 1;
    }

    const panel_fields = [
        "custom_panel_customer",
        "panel_customer",
        "panel",
        "custom_panel",
        "custom_kpws_assigned_panel_customer",
        "custom_kpws_panel_customer",
        "custom_kpws_panel_name",
        "custom_kpws_assigned_panel_name"
    ];

    const other_allowed = [
        "purpose",
        "custom_kpws_welfare_type",
        "discount_type",
        "discount_value",
        "custom_kpws_welfare_percentage",
        "custom_kpws_admin_notes",
        "remarks",
        "workflow_state",
        "status"
    ];

    [...panel_fields, ...other_allowed].forEach((fieldname) => {
        if (!frm.fields_dict[fieldname]) return;

        frm.set_df_property(fieldname, "allow_on_submit", 1);

        if (panel_fields.includes(fieldname)) {
            frm.set_df_property(fieldname, "read_only", 0);
        }
    });

    // Dynamic: any field whose label or fieldname contains panel should be editable after submit.
    Object.keys(frm.fields_dict || {}).forEach((fieldname) => {
        const df = frm.fields_dict[fieldname].df || {};
        const label = String(df.label || "").toLowerCase();

        if (fieldname.toLowerCase().includes("panel") || label.includes("panel")) {
            frm.set_df_property(fieldname, "allow_on_submit", 1);
            frm.set_df_property(fieldname, "read_only", 0);
        }
    });
}

function kpws_prf_panel_v42_fix_docstatus(frm) {
    // Fix the second error:
    // Cannot change docstatus from 1 Submitted to 0 Draft.
    // Some older client script is sending submitted PRF as draft.
    if (frm.__kpws_original_docstatus === 1 && frm.doc.docstatus === 0) {
        frm.doc.docstatus = 1;
    }
}
'''


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

_existing_before_save = doc_events["Patient Registration Form"].get("before_save", [])
if isinstance(_existing_before_save, str):
    _existing_before_save = [_existing_before_save]

_method = "kpws_customization.api.kpws_prf_panel_update_after_submit_v42.allow_panel_update_after_submit"
if _method not in _existing_before_save:
    _existing_before_save.append(_method)

doc_events["Patient Registration Form"]["before_save"] = _existing_before_save
'''

    hooks_file.write_text(text + block)
    return True


@frappe.whitelist()
def install():
    changed = _force_field_metadata()
    client_script = _upsert_client_script()
    hooks_changed = _patch_hooks()

    frappe.clear_cache(doctype=DOCTYPE)
    frappe.clear_cache()
    frappe.db.commit()

    return {
        "ok": True,
        "panel_fields": _panel_fields(),
        "allowed_fields": _all_allowed_fields(),
        "metadata_changed": changed,
        "client_script": client_script,
        "hooks_changed": hooks_changed,
        "message": "PRF Panel update after submit enabled.",
    }


@frappe.whitelist()
def verify(name=None):
    frappe.clear_cache(doctype=DOCTYPE)
    meta = frappe.get_meta(DOCTYPE)

    fields = {}

    for fieldname in _all_allowed_fields():
        if not meta.has_field(fieldname):
            continue

        df = meta.get_field(fieldname)
        fields[fieldname] = {
            "label": df.label,
            "fieldtype": df.fieldtype,
            "allow_on_submit": df.allow_on_submit,
            "read_only": df.read_only,
        }

    doc = None
    if name and frappe.db.exists(DOCTYPE, name):
        doc = frappe.db.get_value(
            DOCTYPE,
            name,
            ["name", "docstatus", "workflow_state", "modified"],
            as_dict=True,
        )

    return {
        "doctype": DOCTYPE,
        "panel_fields": _panel_fields(),
        "fields": fields,
        "client_script_exists": bool(frappe.db.exists("Client Script", CLIENT_SCRIPT_NAME)),
        "doc": doc,
    }


@frappe.whitelist()
def set_panel_direct(prf, panel):
    """
    Emergency direct update if browser save is still blocked by old cached JS.
    """
    if not prf or not frappe.db.exists(DOCTYPE, prf):
        frappe.throw(_("Patient Registration Form not found."))

    panel_fields = _panel_fields()
    if not panel_fields:
        frappe.throw(_("No panel field found on Patient Registration Form."))

    updates = {}

    for fieldname in panel_fields:
        updates[fieldname] = panel

    frappe.db.set_value(DOCTYPE, prf, updates, update_modified=True)
    frappe.db.commit()

    return {
        "ok": True,
        "prf": prf,
        "panel": panel,
        "updated_fields": panel_fields,
    }
