from pathlib import Path
import shutil
import frappe
from frappe import _
from frappe.utils import now_datetime


PATIENT_DTYPE = "Patient"
LOG_DTYPE = "KPWS Patient Type Change Log"
CLIENT_SCRIPT_NAME = "KPWS Patient Type Change Flow"
OLD_CLIENTS = [
    "KPWS Patient Type Preserve",
]
PATCH_MARKER = "KPWS_PATIENT_TYPE_CHANGE_FLOW_V48_HOOK"

ALLOWED_TYPES = ["Cash", "Welfare", "Panel"]
LAYOUT_FIELD_TYPES = {
    "Section Break",
    "Column Break",
    "Tab Break",
    "HTML",
    "Button",
    "Table",
    "Table MultiSelect",
    "Fold",
    "Heading",
}


def _table_columns(doctype):
    try:
        return {
            r["Field"]
            for r in frappe.db.sql(f"SHOW COLUMNS FROM `tab{doctype}`", as_dict=True)
        }
    except Exception:
        return set()


def _has_field(doctype, fieldname):
    try:
        return frappe.get_meta(doctype).has_field(fieldname)
    except Exception:
        return False


def _is_real_db_field(doctype, fieldname):
    if not fieldname:
        return False

    if fieldname not in _table_columns(doctype):
        return False

    try:
        df = frappe.get_meta(doctype).get_field(fieldname)
        if df and df.fieldtype in LAYOUT_FIELD_TYPES:
            return False
    except Exception:
        pass

    return True


def _normalize(value):
    value = (value or "").strip()

    for t in ALLOWED_TYPES:
        if value.lower() == t.lower():
            return t

    return value


def _module_name():
    for module in ["KPWS Customization", "Kpws Customization", "Custom"]:
        if frappe.db.exists("Module Def", module):
            return module

    row = frappe.get_all("Module Def", pluck="name", limit_page_length=1)
    return row[0] if row else "Custom"


def _patient_type_fields():
    meta = frappe.get_meta(PATIENT_DTYPE)

    candidates = [
        "customer_group",
        "custom_billing_type",
        "billing_type",
        "patient_type",
        "custom_patient_type",
        "custom_kpws_billing_type",
    ]

    fields = []

    for f in candidates:
        if meta.has_field(f) and _is_real_db_field(PATIENT_DTYPE, f):
            fields.append(f)

    for df in meta.fields:
        if not df.fieldname:
            continue

        if df.fieldname in fields:
            continue

        if df.fieldtype in LAYOUT_FIELD_TYPES:
            continue

        if not _is_real_db_field(PATIENT_DTYPE, df.fieldname):
            continue

        label = (df.label or "").lower()
        fieldname = (df.fieldname or "").lower()

        if "patient type" in label or "billing type" in label:
            fields.append(df.fieldname)

    return fields


def _panel_fields():
    meta = frappe.get_meta(PATIENT_DTYPE)

    known = [
        "custom_panel_customer",
        "panel_customer",
        "panel",
        "custom_panel",
        "custom_kpws_panel_customer",
        "custom_kpws_assigned_panel_customer",
        "custom_assigned_panel_customer",
    ]

    fields = []

    for f in known:
        if meta.has_field(f) and _is_real_db_field(PATIENT_DTYPE, f):
            fields.append(f)

    for df in meta.fields:
        if not df.fieldname:
            continue

        if df.fieldname in fields:
            continue

        if df.fieldtype in LAYOUT_FIELD_TYPES:
            continue

        if not _is_real_db_field(PATIENT_DTYPE, df.fieldname):
            continue

        label = (df.label or "").lower()
        fieldname = (df.fieldname or "").lower()

        if "panel" in label or "panel" in fieldname:
            fields.append(df.fieldname)

    return fields


def _customer_fields():
    meta = frappe.get_meta(PATIENT_DTYPE)

    candidates = [
        "customer",
        "custom_customer",
        "custom_patient_customer",
        "patient_customer",
        "custom_linked_customer",
        "customer_id",
    ]

    return [
        f for f in candidates
        if meta.has_field(f) and _is_real_db_field(PATIENT_DTYPE, f)
    ]


def _get_linked_customer(doc):
    for f in _customer_fields():
        value = doc.get(f)
        if value and frappe.db.exists("Customer", value):
            return value

    return None


def _current_patient_type(doc):
    for f in _patient_type_fields():
        value = _normalize(doc.get(f))
        if value in ALLOWED_TYPES:
            return value

    return ""


def _current_panel(doc):
    for f in _panel_fields():
        value = doc.get(f)
        if value:
            return value

    return ""


def _patient_name(doc):
    for f in ["patient_name", "full_name", "first_name"]:
        if doc.meta.has_field(f) and doc.get(f):
            return doc.get(f)

    return doc.name


def _ensure_log_doctype():
    if frappe.db.exists("DocType", LOG_DTYPE):
        return False

    doc = frappe.new_doc("DocType")
    doc.name = LOG_DTYPE
    doc.module = _module_name()
    doc.custom = 1
    doc.track_changes = 1
    doc.autoname = "format:KPTCL-.#####"

    fields = [
        {"fieldname": "patient_section", "label": "Patient", "fieldtype": "Section Break"},
        {"fieldname": "patient", "label": "Patient", "fieldtype": "Link", "options": "Patient", "reqd": 1, "in_list_view": 1},
        {"fieldname": "patient_name", "label": "Patient Name", "fieldtype": "Data", "read_only": 1, "in_list_view": 1},
        {"fieldname": "linked_customer", "label": "Linked Customer", "fieldtype": "Link", "options": "Customer", "read_only": 1},
        {"fieldname": "change_section", "label": "Change Details", "fieldtype": "Section Break"},
        {"fieldname": "old_patient_type", "label": "Old Patient Type", "fieldtype": "Data", "read_only": 1, "in_list_view": 1},
        {"fieldname": "new_patient_type", "label": "New Patient Type", "fieldtype": "Select", "options": "Cash\nWelfare\nPanel", "reqd": 1, "in_list_view": 1},
        {"fieldname": "old_customer_group", "label": "Old Customer Group", "fieldtype": "Link", "options": "Customer Group", "read_only": 1},
        {"fieldname": "new_customer_group", "label": "New Customer Group", "fieldtype": "Link", "options": "Customer Group", "read_only": 1},
        {"fieldname": "panel_section", "label": "Panel Details", "fieldtype": "Section Break"},
        {"fieldname": "old_panel_customer", "label": "Old Panel Customer", "fieldtype": "Link", "options": "Customer", "read_only": 1},
        {"fieldname": "new_panel_customer", "label": "New Panel Customer", "fieldtype": "Link", "options": "Customer"},
        {"fieldname": "audit_section", "label": "Audit", "fieldtype": "Section Break"},
        {"fieldname": "reason", "label": "Reason / Remarks", "fieldtype": "Small Text"},
        {"fieldname": "source", "label": "Source", "fieldtype": "Data", "read_only": 1, "default": "Patient Form"},
        {"fieldname": "changed_by", "label": "Changed By", "fieldtype": "Link", "options": "User", "read_only": 1, "in_list_view": 1},
        {"fieldname": "changed_on", "label": "Changed On", "fieldtype": "Datetime", "read_only": 1, "in_list_view": 1},
    ]

    for f in fields:
        doc.append("fields", f)

    for role in ["System Manager", "Accounts Manager", "Healthcare Administrator"]:
        if frappe.db.exists("Role", role):
            doc.append("permissions", {
                "role": role,
                "read": 1,
                "write": 1,
                "create": 1,
                "print": 1,
                "email": 1,
                "export": 1,
            })

    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return True


def _disable_old_clients():
    for name in OLD_CLIENTS:
        if frappe.db.exists("Client Script", name):
            frappe.db.set_value("Client Script", name, "enabled", 0)

    frappe.db.commit()


def _neutralize_old_v45_v46_files():
    app_path = Path(frappe.get_app_path("kpws_customization"))

    for rel in [
        "api/kpws_patient_type_preserve_v45.py",
        "api/kpws_patient_type_change_flow_v46.py",
    ]:
        p = app_path / rel
        if not p.exists():
            continue

        text = p.read_text()
        marker = "KPWS_V48_NEUTRALIZED_OLD_PATIENT_TYPE_FLOW"

        if marker in text:
            continue

        text += f'''

# {marker}
def preserve_patient_type(doc, method=None):
    return

def enforce_patient_type_after_save(doc, method=None):
    return

def _sync_direct_save(doc, method=None):
    return
'''
        p.write_text(text)

    for pycache in Path("apps/kpws_customization").rglob("__pycache__"):
        shutil.rmtree(pycache, ignore_errors=True)


def _set_patient_type_raw(patient, new_type, panel_customer=None):
    doc = frappe.get_doc(PATIENT_DTYPE, patient)

    columns = _table_columns(PATIENT_DTYPE)
    updates = {}

    for f in _patient_type_fields():
        if f in columns:
            updates[f] = new_type

    if new_type == "Panel":
        if panel_customer:
            for f in _panel_fields():
                if f in columns:
                    updates[f] = panel_customer
    else:
        for f in _panel_fields():
            if f in columns:
                updates[f] = None

    updates = {
        key: value
        for key, value in updates.items()
        if _is_real_db_field(PATIENT_DTYPE, key)
    }

    if updates:
        frappe.db.set_value(PATIENT_DTYPE, patient, updates, update_modified=True)

    customer = _get_linked_customer(doc)

    if customer and frappe.db.exists("Customer Group", new_type):
        frappe.db.set_value("Customer", customer, "customer_group", new_type, update_modified=True)

    frappe.db.commit()

    return customer


def _insert_log(patient, old_type, new_type, old_panel, new_panel, linked_customer, old_customer_group, new_customer_group, reason, source):
    pdoc = frappe.get_doc(PATIENT_DTYPE, patient)

    log = frappe.new_doc(LOG_DTYPE)
    log.patient = patient
    log.patient_name = _patient_name(pdoc)
    log.linked_customer = linked_customer
    log.old_patient_type = old_type
    log.new_patient_type = new_type
    log.old_panel_customer = old_panel
    log.new_panel_customer = new_panel
    log.old_customer_group = old_customer_group
    log.new_customer_group = new_customer_group
    log.reason = reason or ""
    log.source = source or "Patient Form"
    log.changed_by = frappe.session.user
    log.changed_on = now_datetime()
    
    # KPWS_FIX_DUPLICATE_PATIENT_TYPE_CHANGE_LOG_NAME
    # Some old logic was inserting literal name KPTCL-.##### repeatedly.
    # Force a real autoname before insert.
    try:
        from frappe.model.naming import make_autoname
        if not getattr(log, "name", None) or str(log.name).strip() in ("KPTCL-.#####", "KPTCL-.####", "New KPWS Patient Type Change Log"):
            log.name = make_autoname("KPTCL-.#####", doc=log)
    except Exception:
        pass

    try:
        log.insert(ignore_permissions=True)
    except frappe.DuplicateEntryError:
        from frappe.model.naming import make_autoname
        log.name = make_autoname("KPTCL-.#####", doc=log)
        log.insert(ignore_permissions=True)


    try:
        pdoc.add_comment("Info", f"Patient Type changed from {old_type or '-'} to {new_type}. Log: {log.name}")
    except Exception:
        pass

    frappe.db.commit()
    return log.name


@frappe.whitelist()
def change_patient_type(patient, new_type, panel_customer=None, reason=None, source="Patient Form"):
    if not patient or not frappe.db.exists(PATIENT_DTYPE, patient):
        frappe.throw(_("Patient not found."))

    new_type = _normalize(new_type)

    if new_type not in ALLOWED_TYPES:
        frappe.throw(_("Patient Type must be Cash, Welfare or Panel."))

    pdoc = frappe.get_doc(PATIENT_DTYPE, patient)

    old_type = _current_patient_type(pdoc)
    old_panel = _current_panel(pdoc)
    linked_customer = _get_linked_customer(pdoc)
    old_customer_group = frappe.db.get_value("Customer", linked_customer, "customer_group") if linked_customer else None

    if new_type == "Panel" and panel_customer and not frappe.db.exists("Customer", panel_customer):
        frappe.throw(_("Selected panel customer does not exist."))

    new_panel = panel_customer if new_type == "Panel" else None

    linked_customer = _set_patient_type_raw(
        patient=patient,
        new_type=new_type,
        panel_customer=new_panel,
    )

    new_customer_group = frappe.db.get_value("Customer", linked_customer, "customer_group") if linked_customer else None

    log_name = _insert_log(
        patient=patient,
        old_type=old_type,
        new_type=new_type,
        old_panel=old_panel,
        new_panel=new_panel,
        linked_customer=linked_customer,
        old_customer_group=old_customer_group,
        new_customer_group=new_customer_group,
        reason=reason,
        source=source,
    )

    return {
        "ok": True,
        "patient": patient,
        "old_patient_type": old_type,
        "new_patient_type": new_type,
        "old_panel_customer": old_panel,
        "new_panel_customer": new_panel,
        "linked_customer": linked_customer,
        "old_customer_group": old_customer_group,
        "new_customer_group": new_customer_group,
        "log": log_name,
    }


def _sync_direct_save(doc, method=None):
    before = doc.get_doc_before_save()
    if not before:
        return

    old_type = _current_patient_type(before)
    new_type = _current_patient_type(doc)

    if not new_type or new_type not in ALLOWED_TYPES:
        return

    old_panel = _current_panel(before)
    new_panel = _current_panel(doc)

    if old_type == new_type and old_panel == new_panel:
        return

    if new_type != "Panel":
        for f in _panel_fields():
            if doc.meta.has_field(f):
                doc.set(f, None)
        new_panel = None

    for f in _patient_type_fields():
        if doc.meta.has_field(f):
            doc.set(f, new_type)

    linked_customer = _get_linked_customer(doc)
    old_customer_group = frappe.db.get_value("Customer", linked_customer, "customer_group") if linked_customer else None

    if linked_customer and frappe.db.exists("Customer Group", new_type):
        frappe.db.set_value("Customer", linked_customer, "customer_group", new_type, update_modified=True)

    _insert_log(
        patient=doc.name,
        old_type=old_type,
        new_type=new_type,
        old_panel=old_panel,
        new_panel=new_panel,
        linked_customer=linked_customer,
        old_customer_group=old_customer_group,
        new_customer_group=new_type,
        reason="Direct Patient form save.",
        source="Patient Direct Save",
    )


CLIENT_SCRIPT = r'''
frappe.ui.form.on("Patient", {
    refresh(frm) {
        frm.add_custom_button("Change Patient Type", () => {
            kpws_patient_type_change_dialog_v48(frm);
        });

        frm.add_custom_button("View Type Change Logs", () => {
            frappe.set_route("List", "KPWS Patient Type Change Log", {
                patient: frm.doc.name
            });
        });
    }
});

function kpws_patient_type_current_v48(frm) {
    const fields = [
        "customer_group",
        "custom_billing_type",
        "billing_type",
        "patient_type",
        "custom_patient_type",
        "custom_kpws_billing_type"
    ];

    for (const f of fields) {
        if (frm.fields_dict[f] && frm.doc[f]) {
            return frm.doc[f];
        }
    }

    return "";
}

function kpws_patient_type_change_dialog_v48(frm) {
    const d = new frappe.ui.Dialog({
        title: "Change Patient Type",
        fields: [
            {
                fieldname: "current_type",
                label: "Current Patient Type",
                fieldtype: "Data",
                read_only: 1,
                default: kpws_patient_type_current_v48(frm)
            },
            {
                fieldname: "new_type",
                label: "New Patient Type",
                fieldtype: "Select",
                options: "Cash\nWelfare\nPanel",
                reqd: 1,
                default: kpws_patient_type_current_v48(frm) || "Cash"
            },
            {
                fieldname: "panel_customer",
                label: "Panel Customer",
                fieldtype: "Link",
                options: "Customer",
                depends_on: "eval:doc.new_type=='Panel'"
            },
            {
                fieldname: "reason",
                label: "Reason / Remarks",
                fieldtype: "Small Text",
                reqd: 1
            }
        ],
        primary_action_label: "Update Patient Type",
        primary_action(values) {
            d.hide();

            frappe.call({
                method: "kpws_customization.api.kpws_patient_type_change_flow_v48.change_patient_type",
                args: {
                    patient: frm.doc.name,
                    new_type: values.new_type,
                    panel_customer: values.panel_customer || "",
                    reason: values.reason || "",
                    source: "Patient Form Button"
                },
                freeze: true,
                freeze_message: "Updating patient type...",
                callback(r) {
                    const data = r.message || {};

                    frappe.msgprint({
                        title: "Patient Type Updated",
                        message: `
                            <b>Patient:</b> ${frappe.utils.escape_html(data.patient || "")}<br>
                            <b>Old Type:</b> ${frappe.utils.escape_html(data.old_patient_type || "-")}<br>
                            <b>New Type:</b> ${frappe.utils.escape_html(data.new_patient_type || "-")}<br>
                            <b>Log:</b> <a href="/app/kpws-patient-type-change-log/${encodeURIComponent(data.log || "")}" target="_blank">${frappe.utils.escape_html(data.log || "")}</a>
                        `,
                        indicator: "green"
                    });

                    frm.reload_doc();
                }
            });
        }
    });

    d.show();
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

    doc.dt = PATIENT_DTYPE
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

doc_events.setdefault("Patient", {{}})

_existing_validate = doc_events["Patient"].get("validate", [])
if isinstance(_existing_validate, str):
    _existing_validate = [_existing_validate]

_method = "kpws_customization.api.kpws_patient_type_change_flow_v48._sync_direct_save"
if _method not in _existing_validate:
    _existing_validate.append(_method)

doc_events["Patient"]["validate"] = _existing_validate
'''

    hooks_file.write_text(text + block)
    return True


@frappe.whitelist()
def install():
    log_created = _ensure_log_doctype()
    _disable_old_clients()
    _neutralize_old_v45_v46_files()
    client_script = _upsert_client_script()
    hooks_changed = _patch_hooks()

    frappe.clear_cache(doctype=PATIENT_DTYPE)
    frappe.clear_cache(doctype=LOG_DTYPE)
    frappe.clear_cache()
    frappe.db.commit()

    return {
        "ok": True,
        "log_doctype": LOG_DTYPE,
        "log_created": log_created,
        "client_script": client_script,
        "hooks_changed": hooks_changed,
        "patient_type_fields": _patient_type_fields(),
        "panel_fields": _panel_fields(),
        "message": "v48 controlled patient type change flow installed.",
    }


@frappe.whitelist()
def debug_safe_fields():
    return {
        "patient_db_columns_count": len(_table_columns(PATIENT_DTYPE)),
        "patient_type_fields_used": _patient_type_fields(),
        "panel_fields_used": _panel_fields(),
        "bad_fields_filtered_out": [
            "customer_details_section",
        ],
    }


@frappe.whitelist()
def status(patient):
    if not patient or not frappe.db.exists(PATIENT_DTYPE, patient):
        frappe.throw(_("Patient not found."))

    doc = frappe.get_doc(PATIENT_DTYPE, patient)
    customer = _get_linked_customer(doc)

    logs = []
    if frappe.db.exists("DocType", LOG_DTYPE):
        logs = frappe.get_all(
            LOG_DTYPE,
            filters={"patient": patient},
            fields=["name", "old_patient_type", "new_patient_type", "changed_by", "changed_on", "reason"],
            order_by="creation desc",
            limit_page_length=10,
        )

    return {
        "patient": patient,
        "patient_type": _current_patient_type(doc),
        "panel_customer": _current_panel(doc),
        "linked_customer": customer,
        "linked_customer_group": frappe.db.get_value("Customer", customer, "customer_group") if customer else None,
        "recent_logs": logs,
    }


# KPWS_NOOP_OLD_PATIENT_TYPE_CUSTOMER_SYNC_V76
# Do not create/sync customers during Patient Type changes anymore.
def before_patient_save(doc, method=None):
    return

def validate_patient(doc, method=None):
    return

def on_patient_update(doc, method=None):
    return

def after_patient_insert(doc, method=None):
    return

def _sync_direct_save(*args, **kwargs):
    return

def _insert_log(*args, **kwargs):
    return
