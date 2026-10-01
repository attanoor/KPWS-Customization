import json
import os
import frappe
from frappe.utils import now_datetime


CANDIDATE_DOCTYPES = [
    "Patient Registration Form",
    "Patient Registeration Form",
]


def _safe(obj, key, default=None):
    try:
        if hasattr(obj, "get"):
            return obj.get(key, default)
        return getattr(obj, key, default)
    except Exception:
        return default


def _field_dict(df):
    return {
        "idx": _safe(df, "idx"),
        "label": _safe(df, "label"),
        "fieldname": _safe(df, "fieldname"),
        "fieldtype": _safe(df, "fieldtype"),
        "options": _safe(df, "options"),
        "reqd": _safe(df, "reqd"),
        "hidden": _safe(df, "hidden"),
        "read_only": _safe(df, "read_only"),
        "default": _safe(df, "default"),
        "depends_on": _safe(df, "depends_on"),
        "mandatory_depends_on": _safe(df, "mandatory_depends_on"),
        "read_only_depends_on": _safe(df, "read_only_depends_on"),
        "description": _safe(df, "description"),
    }


def _get_doctype():
    for dt in CANDIDATE_DOCTYPES:
        if frappe.db.exists("DocType", dt):
            return dt
    return None


def _table_has_column(table, column):
    try:
        return bool(frappe.db.has_column(table, column))
    except Exception:
        return False


def _get_client_scripts(doctype):
    if not frappe.db.exists("DocType", "Client Script"):
        return []

    fields = ["name", "dt", "modified"]

    for optional_field in ["enabled", "view"]:
        if _table_has_column("Client Script", optional_field):
            fields.append(optional_field)

    try:
        scripts = frappe.get_all(
            "Client Script",
            filters={"dt": doctype},
            fields=fields,
            order_by="modified desc",
            limit_page_length=100,
        )
    except Exception:
        return []

    output = []
    for row in scripts:
        try:
            doc = frappe.get_doc("Client Script", row.name)
            output.append({
                "name": doc.name,
                "dt": doc.dt,
                "enabled": getattr(doc, "enabled", None),
                "view": getattr(doc, "view", None),
                "modified": str(doc.modified),
                "script_preview": (doc.script or "")[:4000],
            })
        except Exception as e:
            output.append({
                "name": row.name,
                "error": str(e),
            })

    return output


def _get_workflows(doctype):
    if not frappe.db.exists("DocType", "Workflow"):
        return []

    try:
        workflows = frappe.get_all(
            "Workflow",
            filters={"document_type": doctype},
            fields=["name"],
            limit_page_length=50,
        )
    except Exception:
        return []

    output = []
    for row in workflows:
        try:
            output.append(frappe.get_doc("Workflow", row.name).as_dict())
        except Exception as e:
            output.append({
                "name": row.name,
                "error": str(e),
            })

    return output


def _layout_summary(fields):
    lines = []
    current_tab = "Main"
    current_section = "Main Section"

    lines.append("CURRENT PATIENT REGISTRATION FORM LAYOUT")
    lines.append("========================================")

    for f in fields:
        fieldtype = f.get("fieldtype")
        label = f.get("label") or f.get("fieldname") or ""
        fieldname = f.get("fieldname") or ""

        if fieldtype == "Tab Break":
            current_tab = label or "Unnamed Tab"
            current_section = "Main Section"
            lines.append("")
            lines.append(f"===== TAB: {current_tab} =====")
            continue

        if fieldtype == "Section Break":
            current_section = label or "Unnamed Section"
            lines.append("")
            lines.append(f"--- Section: {current_section} ---")
            continue

        if fieldtype == "Column Break":
            lines.append("    | Column Break |")
            continue

        visible = "HIDDEN" if f.get("hidden") else "VISIBLE"
        reqd = "REQD" if f.get("reqd") else ""
        ro = "READONLY" if f.get("read_only") else ""
        options = f"Options: {f.get('options')}" if f.get("options") else ""

        lines.append(
            f"{str(f.get('idx') or '').rjust(3)}. "
            f"[{visible}] {label} ({fieldname}) - {fieldtype} "
            f"{options} {reqd} {ro}".strip()
        )

    return "\n".join(lines)


def run():
    doctype = _get_doctype()

    if not doctype:
        return {
            "ok": False,
            "message": "Patient Registration Form DocType not found."
        }

    meta = frappe.get_meta(doctype)
    fields = [_field_dict(df) for df in meta.fields]

    custom_fields = []
    try:
        custom_fields = frappe.get_all(
            "Custom Field",
            filters={"dt": doctype},
            fields=[
                "name",
                "label",
                "fieldname",
                "fieldtype",
                "insert_after",
                "options",
                "reqd",
                "hidden",
                "read_only",
                "modified",
            ],
            order_by="idx asc",
            limit_page_length=500,
        )
    except Exception:
        custom_fields = []

    property_setters = []
    try:
        property_setters = frappe.get_all(
            "Property Setter",
            filters={"doc_type": doctype},
            fields=[
                "name",
                "field_name",
                "property",
                "value",
                "property_type",
                "modified",
            ],
            order_by="modified desc",
            limit_page_length=500,
        )
    except Exception:
        property_setters = []

    report = {
        "site": frappe.local.site,
        "doctype": doctype,
        "generated_at": str(now_datetime()),
        "field_count": len(fields),
        "custom_field_count": len(custom_fields),
        "fields": fields,
        "custom_fields": custom_fields,
        "property_setters": property_setters,
        "client_scripts": _get_client_scripts(doctype),
        "workflows": _get_workflows(doctype),
        "layout_summary": _layout_summary(fields),
    }

    export_dir = frappe.get_site_path("private", "files", "kpws_prf_ui_audit")
    os.makedirs(export_dir, exist_ok=True)

    ts = now_datetime().strftime("%Y%m%d_%H%M%S")

    json_file = os.path.join(export_dir, f"kpws_prf_ui_audit_{ts}.json")
    txt_file = os.path.join(export_dir, f"kpws_prf_ui_audit_{ts}.txt")

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str, ensure_ascii=False)

    with open(txt_file, "w", encoding="utf-8") as f:
        f.write(report["layout_summary"])

    return {
        "ok": True,
        "doctype": doctype,
        "field_count": len(fields),
        "custom_field_count": len(custom_fields),
        "property_setter_count": len(property_setters),
        "client_script_count": len(report["client_scripts"]),
        "workflow_count": len(report["workflows"]),
        "json_file": json_file,
        "txt_file": txt_file,
        "layout_summary": report["layout_summary"][:15000],
    }
