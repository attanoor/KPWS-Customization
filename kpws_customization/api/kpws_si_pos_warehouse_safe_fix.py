import frappe

CLIENT_SCRIPT_NAME = "KPWS FINAL POS Warehouse Enforcement"
WAREHOUSE = "Pharmacy - KPWS"


def ensure_warehouse_exists():
    if not frappe.db.exists("Warehouse", WAREHOUSE):
        frappe.throw(f"Warehouse not found: {WAREHOUSE}")


def enforce_on_sales_invoice(doc, method=None):
    ensure_warehouse_exists()

    if doc.meta.get_field("is_pos"):
        doc.is_pos = 1

    if doc.meta.get_field("set_warehouse"):
        doc.set_warehouse = WAREHOUSE

    for row in doc.get("items") or []:
        if row.meta.get_field("warehouse"):
            row.warehouse = WAREHOUSE


def install_client_script():
    if not frappe.db.exists("DocType", "Client Script"):
        return

    script = r'''
frappe.ui.form.on("Sales Invoice", {
    setup(frm) {
        kpws_pos_wh_apply_later(frm);
    },
    onload(frm) {
        kpws_pos_wh_apply_later(frm);
    },
    refresh(frm) {
        kpws_pos_wh_apply_later(frm);
    },
    patient(frm) {
        kpws_pos_wh_apply_later(frm);
    },
    customer(frm) {
        kpws_pos_wh_apply_later(frm);
    },
    custom_kpws_billing_type(frm) {
        kpws_pos_wh_apply_later(frm);
    },
    pos_profile(frm) {
        kpws_pos_wh_apply_later(frm);
    },
    validate(frm) {
        kpws_pos_wh_apply(frm);
    },
    before_save(frm) {
        kpws_pos_wh_apply(frm);
    }
});

frappe.ui.form.on("Sales Invoice Item", {
    item_code(frm, cdt, cdn) {
        kpws_pos_wh_apply_to_row(frm, cdt, cdn);
    },
    qty(frm, cdt, cdn) {
        kpws_pos_wh_apply_to_row(frm, cdt, cdn);
    },
    rate(frm, cdt, cdn) {
        kpws_pos_wh_apply_to_row(frm, cdt, cdn);
    },
    warehouse(frm, cdt, cdn) {
        kpws_pos_wh_apply_to_row(frm, cdt, cdn);
    }
});

function kpws_pos_wh_apply_later(frm) {
    setTimeout(function() { kpws_pos_wh_apply(frm); }, 300);
    setTimeout(function() { kpws_pos_wh_apply(frm); }, 1200);
}

function kpws_pos_wh_apply(frm) {
    const WH = "Pharmacy - KPWS";

    if (!frm || !frm.doc) {
        return;
    }

    // Always tick Include Payment/POS, including Panel.
    if (frm.fields_dict && frm.fields_dict.is_pos && frm.doc.is_pos != 1) {
        frm.set_value("is_pos", 1);
    }

    // Always set source warehouse.
    if (frm.fields_dict && frm.fields_dict.set_warehouse && frm.doc.set_warehouse !== WH) {
        frm.set_value("set_warehouse", WH);
    }

    // Do not touch grid while ERPNext is in the middle of adding a blank row.
    if (!frm.doc.items || !Array.isArray(frm.doc.items)) {
        return;
    }

    frm.doc.items.forEach(function(row) {
        if (row && row.doctype && row.name && row.warehouse !== WH) {
            frappe.model.set_value(row.doctype, row.name, "warehouse", WH);
        }
    });

    if (frm.fields_dict && frm.fields_dict.items) {
        frm.refresh_field("items");
    }
}

function kpws_pos_wh_apply_to_row(frm, cdt, cdn) {
    const WH = "Pharmacy - KPWS";

    if (!frm || !cdt || !cdn) {
        return;
    }

    let row = locals && locals[cdt] ? locals[cdt][cdn] : null;

    if (!row) {
        return;
    }

    if (row.warehouse !== WH) {
        frappe.model.set_value(cdt, cdn, "warehouse", WH);
    }

    if (frm.fields_dict && frm.fields_dict.set_warehouse && frm.doc.set_warehouse !== WH) {
        frm.set_value("set_warehouse", WH);
    }

    if (frm.fields_dict && frm.fields_dict.is_pos && frm.doc.is_pos != 1) {
        frm.set_value("is_pos", 1);
    }
}
'''

    if frappe.db.exists("Client Script", CLIENT_SCRIPT_NAME):
        doc = frappe.get_doc("Client Script", CLIENT_SCRIPT_NAME)
        doc.enabled = 1
        doc.dt = "Sales Invoice"
        doc.view = "Form"
        doc.script = script
        doc.save(ignore_permissions=True)
        print("Updated Client Script safely:", CLIENT_SCRIPT_NAME)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": CLIENT_SCRIPT_NAME,
            "dt": "Sales Invoice",
            "view": "Form",
            "enabled": 1,
            "script": script,
        }).insert(ignore_permissions=True)
        print("Created Client Script safely:", CLIENT_SCRIPT_NAME)


def install():
    ensure_warehouse_exists()
    install_client_script()
    frappe.db.commit()
    frappe.clear_cache()
    print("DONE: Safe POS/Warehouse enforcement installed. items_add handler removed.")
