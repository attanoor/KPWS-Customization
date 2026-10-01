import frappe
import json
from datetime import datetime

DT = "Patient Registration Form"

PANEL_CANDIDATES = [
    "custom_panel_customer",
    "custom_kpws_assigned_panel_customer",
    "panel_customer",
    "panel_name",
    "custom_panel",
    "custom_assigned_panel",
    "assigned_panel",
]

ANCHOR_CANDIDATES = [
    "custom_kpws_welfare_percentage",
    "custom_coverage_percentage",
    "coverage_percentage",
    "discount_percentage",
    "discount",
    "custom_kpws_welfare_type",
    "custom_assistance_type",
    "assistance_type",
    "purpose",
    "custom_kpws_admin_notes",
]

def get_docfields():
    return frappe.get_all(
        "DocField",
        filters={"parent": DT},
        fields=[
            "name",
            "fieldname",
            "label",
            "fieldtype",
            "idx",
            "hidden",
            "reqd",
            "read_only",
        ],
        order_by="idx asc",
    )

def print_layout(title):
    print("")
    print("=" * 90)
    print(title)
    print("=" * 90)
    for df in get_docfields():
        label = df.label or ""
        fname = df.fieldname or ""
        important = (
            df.fieldtype in ["Tab Break", "Section Break", "Column Break"]
            or "panel" in fname.lower()
            or "panel" in label.lower()
            or "discount" in label.lower()
            or "purpose" in label.lower()
            or "welfare" in fname.lower()
            or "welfare" in label.lower()
            or "zakat" in label.lower()
            or "donation" in label.lower()
        )
        if important:
            print(
                str(df.idx).rjust(3),
                "|", df.fieldtype.ljust(14),
                "|", fname.ljust(42),
                "|", label.ljust(35),
                "| hidden=", df.hidden,
                "| reqd=", df.reqd,
                "| ro=", df.read_only,
            )

def backup_layout():
    rows = get_docfields()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"/tmp/kpws_prf_docfield_layout_backup_{ts}.json"
    with open(path, "w") as f:
        json.dump(rows, f, indent=2, default=str)
    print("Backup saved:", path)

def set_docfield(name, values):
    clean = {}
    for k, v in values.items():
        clean[k] = v
    frappe.db.set_value("DocField", name, clean, update_modified=False)

def find_discount_break(fields):
    # Prefer actual Tab Break named/labelled Discount and Purpose
    for df in fields:
        label = (df.label or "").strip().lower()
        fname = (df.fieldname or "").strip().lower()
        if df.fieldtype == "Tab Break" and (
            "discount" in label or "purpose" in label or "discount" in fname or "purpose" in fname
        ):
            return df

    # Then Section Break
    for df in fields:
        label = (df.label or "").strip().lower()
        fname = (df.fieldname or "").strip().lower()
        if df.fieldtype == "Section Break" and (
            "discount" in label or "purpose" in label or "discount" in fname or "purpose" in fname
        ):
            return df

    return None

def find_details_breaks(fields):
    found = []
    for df in fields:
        label = (df.label or "").strip().lower()
        fname = (df.fieldname or "").strip().lower()
        if df.fieldtype in ["Tab Break", "Section Break"] and (
            label == "details"
            or fname == "details"
            or fname == "details_tab"
            or fname == "details_section"
        ):
            found.append(df)
    return found

def find_panel_field(fields):
    by_fieldname = {df.fieldname: df for df in fields}

    for fname in PANEL_CANDIDATES:
        if fname in by_fieldname:
            return by_fieldname[fname]

    for df in fields:
        label = (df.label or "").lower()
        fname = (df.fieldname or "").lower()
        if "panel" in label or "panel" in fname:
            if df.fieldtype in ["Link", "Data"]:
                return df

    return None

def find_anchor(fields, discount_break):
    # Search after Discount/Purpose break first
    after_discount = []
    if discount_break:
        started = False
        for df in fields:
            if df.name == discount_break.name:
                started = True
                continue
            if started and df.fieldtype == "Tab Break":
                break
            if started:
                after_discount.append(df)

        by_fieldname = {df.fieldname: df for df in after_discount}
        for fname in ANCHOR_CANDIDATES:
            if fname in by_fieldname:
                return by_fieldname[fname]

        normal_fields = [df for df in after_discount if df.fieldtype not in ["Tab Break", "Section Break", "Column Break"]]
        if normal_fields:
            return normal_fields[-1]

        return discount_break

    # Fallback anywhere
    by_fieldname = {df.fieldname: df for df in fields}
    for fname in ANCHOR_CANDIDATES:
        if fname in by_fieldname:
            return by_fieldname[fname]

    return None

def reindex_move_after(panel_df, anchor_df):
    fields = get_docfields()

    ordered = [df for df in fields if df.name != panel_df.name]

    insert_pos = None
    for i, df in enumerate(ordered):
        if df.name == anchor_df.name:
            insert_pos = i + 1
            break

    if insert_pos is None:
        insert_pos = len(ordered)

    ordered.insert(insert_pos, panel_df)

    for idx, df in enumerate(ordered, start=1):
        frappe.db.set_value("DocField", df.name, "idx", idx, update_modified=False)

def ensure_client_script():
    if not frappe.db.exists("DocType", "Client Script"):
        return

    script = r'''
frappe.ui.form.on("Patient Registration Form", {
    setup(frm) {
        kpws_prf_layout_setup(frm);
    },
    onload(frm) {
        kpws_prf_layout_setup(frm);
    },
    refresh(frm) {
        kpws_prf_layout_setup(frm);
    },
    custom_panel_customer(frm) {
        kpws_prf_sync_panel(frm, "custom_panel_customer");
    },
    custom_kpws_assigned_panel_customer(frm) {
        kpws_prf_sync_panel(frm, "custom_kpws_assigned_panel_customer");
    }
});

function kpws_prf_has_field(frm, fieldname) {
    return frm.fields_dict && frm.fields_dict[fieldname];
}

function kpws_prf_sync_panel(frm, source_field) {
    let value = frm.doc[source_field];
    if (!value) return;

    ["custom_panel_customer", "custom_kpws_assigned_panel_customer"].forEach(function(fieldname) {
        if (fieldname !== source_field && kpws_prf_has_field(frm, fieldname) && frm.doc[fieldname] !== value) {
            frm.set_value(fieldname, value);
        }
    });
}

function kpws_prf_layout_setup(frm) {
    ["custom_panel_customer", "custom_kpws_assigned_panel_customer"].forEach(function(fieldname) {
        if (kpws_prf_has_field(frm, fieldname)) {
            frm.set_query(fieldname, function() {
                return {
                    filters: {
                        custom_is_panel: 1
                    }
                };
            });
        }
    });

    if (kpws_prf_has_field(frm, "custom_panel_customer")) {
        frm.toggle_display("custom_panel_customer", true);
        frm.toggle_reqd("custom_panel_customer", false);
    }

    if (kpws_prf_has_field(frm, "custom_kpws_assigned_panel_customer")) {
        frm.toggle_display("custom_kpws_assigned_panel_customer", false);
        frm.toggle_reqd("custom_kpws_assigned_panel_customer", false);
    }
}
'''

    name = "KPWS FINAL PRF Real Layout"
    if frappe.db.exists("Client Script", name):
        doc = frappe.get_doc("Client Script", name)
        doc.enabled = 1
        doc.dt = DT
        doc.view = "Form"
        doc.script = script
        doc.save(ignore_permissions=True)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": name,
            "dt": DT,
            "view": "Form",
            "enabled": 1,
            "script": script,
        }).insert(ignore_permissions=True)

def run():
    if not frappe.db.exists("DocType", DT):
        raise Exception(f"{DT} not found")

    backup_layout()
    print_layout("BEFORE REAL LAYOUT")

    fields = get_docfields()

    discount_break = find_discount_break(fields)
    details_breaks = find_details_breaks(fields)
    panel_df = find_panel_field(fields)

    print("")
    print("Detected Discount/Purpose break:", discount_break.fieldname if discount_break else None, "|", discount_break.label if discount_break else None)
    print("Detected Details breaks:", [(d.fieldname, d.label, d.fieldtype) for d in details_breaks])
    print("Detected Panel field:", panel_df.fieldname if panel_df else None, "|", panel_df.label if panel_df else None)

    if not discount_break:
        print("No Discount/Purpose Tab/Section found. Creating a visible Section Break before welfare fields.")
        # create a real DocField section if needed
        max_idx = max([int(d.idx or 0) for d in fields] or [0])
        new = frappe.get_doc({
            "doctype": "DocField",
            "parent": DT,
            "parenttype": "DocType",
            "parentfield": "fields",
            "fieldname": "kpws_discount_and_purpose_section",
            "label": "Discount and Purpose",
            "fieldtype": "Section Break",
            "idx": max_idx + 1,
            "hidden": 0,
        })
        new.insert(ignore_permissions=True)
        frappe.db.commit()
        fields = get_docfields()
        discount_break = find_discount_break(fields)

    # Hide Details tab/section
    for d in details_breaks:
        print("Hiding Details break:", d.fieldname, d.label, d.fieldtype)
        set_docfield(d.name, {
            "hidden": 1,
            "print_hide": 1,
        })

    # Make Discount/Purpose visible and cleanly labelled
    if discount_break:
        print("Showing Discount/Purpose break:", discount_break.fieldname)
        set_docfield(discount_break.name, {
            "label": "Discount and Purpose",
            "hidden": 0,
            "print_hide": 0,
        })

    fields = get_docfields()
    panel_df = find_panel_field(fields)
    discount_break = find_discount_break(fields)
    anchor_df = find_anchor(fields, discount_break)

    if not panel_df:
        raise Exception("No panel field found on Patient Registration Form. Need to add one first.")

    if not anchor_df:
        anchor_df = discount_break

    print("Moving Panel field:", panel_df.fieldname, "after:", anchor_df.fieldname)

    # Main panel field visible
    set_docfield(panel_df.name, {
        "label": "Panel",
        "hidden": 0,
        "read_only": 0,
        "reqd": 0,
        "print_hide": 0,
    })

    reindex_move_after(panel_df, anchor_df)

    # Hide duplicate panel fields, keep selected one visible
    fields = get_docfields()
    for df in fields:
        if df.name == panel_df.name:
            continue
        label = (df.label or "").lower()
        fname = (df.fieldname or "").lower()
        if "panel" in label or "panel" in fname:
            if df.fieldtype in ["Link", "Data"]:
                print("Hiding duplicate panel field:", df.fieldname, df.label)
                set_docfield(df.name, {
                    "hidden": 1,
                    "reqd": 0,
                    "print_hide": 1,
                })

    ensure_client_script()

    frappe.clear_cache(doctype=DT)
    frappe.db.commit()

    print_layout("AFTER REAL LAYOUT")
    print("")
    print("DONE: Real DocField layout updated.")

