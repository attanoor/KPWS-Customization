import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import cint


def _field_exists(dt, fieldname):
    return bool(
        frappe.db.exists("DocField", {"parent": dt, "fieldname": fieldname})
        or frappe.db.exists("Custom Field", {"dt": dt, "fieldname": fieldname})
    )


def _set_custom_field(dt, fieldname, values):
    name = frappe.db.exists("Custom Field", {"dt": dt, "fieldname": fieldname})
    if not name:
        return False
    meta = frappe.get_meta("Custom Field")
    valid = {df.fieldname for df in meta.fields}
    clean = {k: v for k, v in values.items() if k in valid}
    if clean:
        frappe.db.set_value("Custom Field", name, clean, update_modified=False)
    return True


def _set_docfield(dt, fieldname, values):
    name = frappe.db.exists("DocField", {"parent": dt, "fieldname": fieldname})
    if not name:
        return False
    meta = frappe.get_meta("DocField")
    valid = {df.fieldname for df in meta.fields}
    clean = {k: v for k, v in values.items() if k in valid}
    if clean:
        frappe.db.set_value("DocField", name, clean, update_modified=False)
    return True


def _make_property_setter(doc_type, field_name, property_name, value, property_type):
    filters = {
        "doc_type": doc_type,
        "doctype_or_field": "DocField",
        "field_name": field_name,
        "property": property_name,
    }
    existing = frappe.db.exists("Property Setter", filters)
    if existing:
        ps = frappe.get_doc("Property Setter", existing)
        ps.value = value
        ps.property_type = property_type
        ps.save(ignore_permissions=True)
        return ps.name
    ps = frappe.get_doc({
        "doctype": "Property Setter",
        "doc_type": doc_type,
        "doctype_or_field": "DocField",
        "field_name": field_name,
        "property": property_name,
        "property_type": property_type,
        "value": value,
    })
    ps.insert(ignore_permissions=True)
    return ps.name


def ensure_fields():
    """Ensure the minimum clean fields exist and are visible."""
    custom_fields = {}

    if not _field_exists("Customer", "custom_is_panel"):
        custom_fields.setdefault("Customer", []).append({
            "fieldname": "custom_is_panel",
            "label": "Is Panel",
            "fieldtype": "Check",
            "insert_after": "customer_group",
            "default": "0",
            "print_hide": 1,
        })

    if not _field_exists("Patient", "custom_panel_customer"):
        custom_fields.setdefault("Patient", []).append({
            "fieldname": "custom_panel_customer",
            "label": "Panel",
            "fieldtype": "Link",
            "options": "Customer",
            "insert_after": "customer_group",
            "print_hide": 1,
        })

    # These two are required by Healthcare Patient controller/JS. Keep from previous hotfix.
    if not _field_exists("Patient", "customer"):
        custom_fields.setdefault("Patient", []).append({
            "fieldname": "customer",
            "label": "Linked Patient Customer",
            "fieldtype": "Link",
            "options": "Customer",
            "insert_after": "customer_group",
            "hidden": 1,
            "read_only": 1,
            "no_copy": 1,
            "print_hide": 1,
        })
    if not _field_exists("Patient", "age_html"):
        custom_fields.setdefault("Patient", []).append({
            "fieldname": "age_html",
            "label": "Age",
            "fieldtype": "HTML",
            "insert_after": "dob",
            "print_hide": 1,
        })

    if custom_fields:
        create_custom_fields(custom_fields, update=True)

    depends = "eval:((doc.customer_group || '').toLowerCase().includes('panel') || (doc.custom_patient_billing_type || '').toLowerCase().includes('panel'))"

    # Force Patient.custom_panel_customer visible and clean even if previous cleanup hid it.
    panel_values = {
        "label": "Panel",
        "fieldtype": "Link",
        "options": "Customer",
        "insert_after": "customer_group",
        "hidden": 0,
        "read_only": 0,
        "reqd": 0,
        "depends_on": depends,
        "print_hide": 1,
    }
    _set_custom_field("Patient", "custom_panel_customer", panel_values)

    # If any old standard/custom panel fields exist, hide them except our clean field.
    old_panel_fields = ["panel_name", "panel_customer", "custom_panel", "panel", "custom_assigned_panel"]
    for f in old_panel_fields:
        _set_custom_field("Patient", f, {"hidden": 1, "reqd": 0})
        _set_docfield("Patient", f, {"hidden": 1, "reqd": 0})
        try:
            _make_property_setter("Patient", f, "hidden", "1", "Check")
            _make_property_setter("Patient", f, "reqd", "0", "Check")
        except Exception:
            pass

    # Keep Customer.custom_is_panel visible for master setup.
    _set_custom_field("Customer", "custom_is_panel", {"hidden": 0, "read_only": 0, "label": "Is Panel", "default": "0"})

    # Make customer_group understandable for users.
    _set_docfield("Patient", "customer_group", {"label": "Patient Type", "reqd": 1, "hidden": 0})
    try:
        _make_property_setter("Patient", "customer_group", "label", "Patient Type", "Data")
        _make_property_setter("Patient", "customer_group", "hidden", "0", "Check")
        _make_property_setter("Patient", "customer_group", "reqd", "1", "Check")
    except Exception:
        pass

    frappe.clear_cache(doctype="Patient")
    frappe.clear_cache(doctype="Customer")


def install_client_script():
    if not frappe.db.exists("DocType", "Client Script"):
        print("Client Script DocType not found; skipped client script")
        return

    script_name = "KPWS Clean Patient Panel Visibility"
    script = r'''
(function () {
  function has(frm, f) {
    return frm.fields_dict && frm.fields_dict[f];
  }

  function patientType(frm) {
    return String((frm.doc.customer_group || frm.doc.custom_patient_billing_type || "")).toLowerCase();
  }

  function isPanel(frm) {
    return patientType(frm).includes("panel");
  }

  function applyPanelUI(frm) {
    if (has(frm, "custom_panel_customer")) {
      frm.set_query("custom_panel_customer", function () {
        return {
          query: "kpws_customization.kpws_patient_panel_visibility_fix.get_panel_customers"
        };
      });
      frm.toggle_display("custom_panel_customer", isPanel(frm));
      frm.toggle_reqd("custom_panel_customer", isPanel(frm));
      frm.set_df_property("custom_panel_customer", "label", "Panel");
      frm.set_df_property("custom_panel_customer", "description", isPanel(frm) ? "Select existing panel customer only. Create panel masters from Customer with Is Panel checked." : "");
    }

    // Hide older duplicate panel fields from the form UI.
    ["panel_name", "panel_customer", "custom_panel", "panel", "custom_assigned_panel"].forEach(function (f) {
      if (has(frm, f)) {
        frm.toggle_display(f, false);
        frm.toggle_reqd(f, false);
      }
    });
  }

  frappe.ui.form.on("Patient", {
    setup: function (frm) { applyPanelUI(frm); },
    onload: function (frm) { applyPanelUI(frm); },
    refresh: function (frm) { applyPanelUI(frm); },
    customer_group: function (frm) {
      applyPanelUI(frm);
      if (!isPanel(frm) && has(frm, "custom_panel_customer")) {
        frm.set_value("custom_panel_customer", "");
      }
    },
    custom_patient_billing_type: function (frm) { applyPanelUI(frm); },
    custom_panel_customer: function (frm) { applyPanelUI(frm); }
  });
})();
'''

    if frappe.db.exists("Client Script", script_name):
        doc = frappe.get_doc("Client Script", script_name)
        doc.dt = "Patient"
        doc.view = "Form"
        doc.enabled = 1
        doc.script = script
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.get_doc({
            "doctype": "Client Script",
            "name": script_name,
            "dt": "Patient",
            "view": "Form",
            "enabled": 1,
            "script": script,
        })
        doc.insert(ignore_permissions=True)
    print(f"Installed/updated Client Script: {script_name}")


def disable_conflicting_patient_scripts():
    if not frappe.db.exists("DocType", "Client Script"):
        return []
    keep = {"KPWS Clean Patient Panel Visibility"}
    disabled = []
    keywords = ["quick add panel", "create panel", "hard patient", "panel group restriction", "step1 patient", "patient strict panel", "clean patient billing form"]
    for row in frappe.get_all("Client Script", filters={"dt": "Patient"}, fields=["name", "script", "enabled"]):
        if row.name in keep:
            continue
        hay = f"{row.name}\n{row.script or ''}".lower()
        if any(k in hay for k in keywords):
            frappe.db.set_value("Client Script", row.name, "enabled", 0, update_modified=False)
            disabled.append(row.name)
    return disabled


@frappe.whitelist()
def get_panel_customers(doctype, txt, searchfield, start, page_len, filters=None):
    """Only show Customer masters where Is Panel is checked."""
    if not _field_exists("Customer", "custom_is_panel"):
        return []
    txt = f"%{txt or ''}%"
    return frappe.db.sql(
        """
        SELECT name, customer_name
        FROM `tabCustomer`
        WHERE docstatus < 2
          AND IFNULL(custom_is_panel, 0) = 1
          AND (name LIKE %(txt)s OR customer_name LIKE %(txt)s)
        ORDER BY customer_name, name
        LIMIT %(start)s, %(page_len)s
        """,
        {"txt": txt, "start": cint(start), "page_len": cint(page_len)},
    )


def run():
    ensure_fields()
    install_client_script()
    disabled = disable_conflicting_patient_scripts()
    frappe.clear_cache(doctype="Patient")
    frappe.clear_cache(doctype="Customer")
    frappe.clear_cache()
    frappe.db.commit()
    meta = frappe.get_meta("Patient")
    fields = {df.fieldname: {"label": df.label, "hidden": df.hidden, "fieldtype": df.fieldtype, "depends_on": df.depends_on} for df in meta.fields}
    print("RESULT:", {
        "status": "success",
        "panel_field": fields.get("custom_panel_customer"),
        "customer_group_field": fields.get("customer_group"),
        "disabled_conflicting_scripts": disabled,
    })
