import frappe

CLIENT_SCRIPT_NAME = "KPWS FINAL POS Warehouse Enforcement"
WAREHOUSE = "Pharmacy - KPWS"


def ensure_warehouse_exists():
    if not frappe.db.exists("Warehouse", WAREHOUSE):
        frappe.throw(f"Warehouse not found: {WAREHOUSE}")


def enforce_on_sales_invoice(doc, method=None):
    ensure_warehouse_exists()

    # Always keep Include Payment/POS enabled so POS Profile applies.
    if doc.meta.get_field("is_pos"):
        doc.is_pos = 1

    # Always set source warehouse on invoice.
    if doc.meta.get_field("set_warehouse"):
        doc.set_warehouse = WAREHOUSE

    # Always set warehouse on every item row.
    for row in doc.get("items") or []:
        if row.meta.get_field("warehouse"):
            row.warehouse = WAREHOUSE


def install_client_script():
    if not frappe.db.exists("DocType", "Client Script"):
        return

    script = r'''
frappe.ui.form.on("Sales Invoice", {
    setup(frm) {
        kpws_pos_wh_apply(frm);
    },
    onload(frm) {
        kpws_pos_wh_apply(frm);
    },
    refresh(frm) {
        kpws_pos_wh_apply(frm);
    },
    patient(frm) {
        setTimeout(() => kpws_pos_wh_apply(frm), 800);
        setTimeout(() => kpws_pos_wh_apply(frm), 1800);
    },
    customer(frm) {
        setTimeout(() => kpws_pos_wh_apply(frm), 800);
    },
    custom_kpws_billing_type(frm) {
        setTimeout(() => kpws_pos_wh_apply(frm), 500);
    },
    pos_profile(frm) {
        setTimeout(() => kpws_pos_wh_apply(frm), 500);
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
    items_add(frm, cdt, cdn) {
        kpws_pos_wh_apply_to_row(frm, cdt, cdn);
    }
});

function kpws_pos_wh_apply(frm) {
    const WH = "Pharmacy - KPWS";

    // Always tick Include Payment/POS, including Panel.
    if (frm.fields_dict.is_pos && frm.doc.is_pos != 1) {
        frm.set_value("is_pos", 1);
    }

    // Always set source warehouse.
    if (frm.fields_dict.set_warehouse && frm.doc.set_warehouse !== WH) {
        frm.set_value("set_warehouse", WH);
    }

    // Always set warehouse on item rows.
    (frm.doc.items || []).forEach(function(row) {
        if (row.warehouse !== WH) {
            frappe.model.set_value(row.doctype, row.name, "warehouse", WH);
        }
    });

    frm.refresh_field("items");
}

function kpws_pos_wh_apply_to_row(frm, cdt, cdn) {
    const WH = "Pharmacy - KPWS";
    let row = locals[cdt][cdn];

    if (row && row.warehouse !== WH) {
        frappe.model.set_value(cdt, cdn, "warehouse", WH);
    }

    if (frm.fields_dict.set_warehouse && frm.doc.set_warehouse !== WH) {
        frm.set_value("set_warehouse", WH);
    }

    if (frm.fields_dict.is_pos && frm.doc.is_pos != 1) {
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
        print("Updated Client Script:", CLIENT_SCRIPT_NAME)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": CLIENT_SCRIPT_NAME,
            "dt": "Sales Invoice",
            "view": "Form",
            "enabled": 1,
            "script": script,
        }).insert(ignore_permissions=True)
        print("Created Client Script:", CLIENT_SCRIPT_NAME)


def install():
    ensure_warehouse_exists()
    install_client_script()
    frappe.db.commit()
    frappe.clear_cache()
    print("DONE: Include Payment/POS and Pharmacy warehouse enforcement installed.")
