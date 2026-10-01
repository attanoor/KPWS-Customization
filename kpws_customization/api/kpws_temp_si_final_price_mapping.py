import frappe

MODULE_PATH = frappe.get_app_path("kpws_customization", "api", "kpws_sales_invoice_final.py")
CLIENT_SCRIPT_NAME = "KPWS FINAL SI Price List Mapping"


SERVER_CODE = r'''

# --- KPWS FINAL fixed Sales Invoice price list mapping ---
def _kpws_final_existing_price_list(candidates):
    for price_list in candidates:
        if frappe.db.exists("Price List", price_list):
            return price_list
    return ""

def _kpws_final_patient_type_from_text(pos_profile=None, patient_type=None):
    text = (str(patient_type or "") + " " + str(pos_profile or "")).lower()
    if "panel" in text:
        return "Panel"
    if "welfare" in text:
        return "Welfare"
    return "Cash"

@frappe.whitelist()
def get_price_list_for_pos_profile(pos_profile=None, patient_type=None):
    patient_type = _kpws_final_patient_type_from_text(pos_profile, patient_type)

    if patient_type == "Panel":
        return _kpws_final_existing_price_list([
            "SPP - Selling Price Panel",
            "SPP",
            "Selling Price Panel",
        ])

    # Cash and Welfare both use SPW
    return _kpws_final_existing_price_list([
        "SPW - Selling Price Welfare",
        "SPW",
        "Selling Price Welfare",
    ])

def price_list_for_type(patient_type):
    patient_type = _kpws_final_patient_type_from_text(None, patient_type)

    if patient_type == "Panel":
        return _kpws_final_existing_price_list([
            "SPP - Selling Price Panel",
            "SPP",
            "Selling Price Panel",
        ])

    # Cash and Welfare both use SPW
    return _kpws_final_existing_price_list([
        "SPW - Selling Price Welfare",
        "SPW",
        "Selling Price Welfare",
    ])
'''


CLIENT_SCRIPT = r'''
frappe.ui.form.on("Sales Invoice", {
    setup(frm) {
        kpws_final_price_setup(frm);
    },
    refresh(frm) {
        kpws_final_price_setup(frm);
        kpws_final_apply_price_list_from_pos(frm);
    },
    pos_profile(frm) {
        kpws_final_apply_price_list_from_pos(frm);
    },
    custom_kpws_billing_type(frm) {
        kpws_final_apply_price_list_from_pos(frm);
    },
    patient(frm) {
        setTimeout(() => kpws_final_apply_price_list_from_pos(frm), 1200);
    },
    custom_kpws_mr_number(frm) {
        setTimeout(() => kpws_final_apply_price_list_from_pos(frm), 1200);
    }
});

function kpws_final_price_setup(frm) {
    if (frm.fields_dict.selling_price_list) {
        frm.set_df_property("selling_price_list", "read_only", 1);
    }
}

function kpws_final_apply_price_list_from_pos(frm) {
    if (!frm.doc.pos_profile) {
        return;
    }

    frappe.dom.freeze(__("Applying correct KPWS price list..."));

    frappe.call({
        method: "kpws_customization.api.kpws_sales_invoice_final.get_price_list_for_pos_profile",
        args: {
            pos_profile: frm.doc.pos_profile,
            patient_type: frm.doc.custom_kpws_billing_type || ""
        },
        freeze: false,
        callback: function(r) {
            let price_list = r.message || "";

            if (!price_list) {
                frappe.dom.unfreeze();
                return;
            }

            if (frm.doc.selling_price_list !== price_list) {
                frm.set_value("selling_price_list", price_list).then(function() {
                    frm.refresh_field("selling_price_list");

                    // If items are already selected, force rate refresh after price list correction.
                    if (frm.doc.items && frm.doc.items.length) {
                        frm.doc.items.forEach(function(row) {
                            if (row.item_code) {
                                frappe.model.set_value(row.doctype, row.name, "price_list_rate", 0);
                                frappe.model.set_value(row.doctype, row.name, "rate", 0);
                            }
                        });
                        frm.refresh_field("items");
                    }

                    frappe.dom.unfreeze();
                });
            } else {
                frappe.dom.unfreeze();
            }
        },
        error: function() {
            frappe.dom.unfreeze();
        }
    });
}
'''


def patch_server_module():
    text = open(MODULE_PATH).read()

    marker = "# --- KPWS FINAL fixed Sales Invoice price list mapping ---"

    if marker in text:
        text = text.split(marker)[0].rstrip() + "\n\n" + SERVER_CODE
        print("Replaced previous final price list mapping.")
    else:
        text = text.rstrip() + "\n\n" + SERVER_CODE
        print("Added final price list mapping.")

    open(MODULE_PATH, "w").write(text)


def install_client_script():
    if not frappe.db.exists("DocType", "Client Script"):
        raise Exception("Client Script DocType not found")

    # Disable older POS/Price List scripts only.
    for row in frappe.get_all("Client Script", filters={"dt": "Sales Invoice"}, fields=["name", "script"]):
        if row.name == CLIENT_SCRIPT_NAME:
            continue

        txt = ((row.name or "") + "\n" + (row.script or "")).lower()
        if "price list" in txt and ("kpws" in txt or "pos profile" in txt):
            frappe.db.set_value("Client Script", row.name, "enabled", 0, update_modified=False)
            print("Disabled old price-list script:", row.name)

    if frappe.db.exists("Client Script", CLIENT_SCRIPT_NAME):
        doc = frappe.get_doc("Client Script", CLIENT_SCRIPT_NAME)
        doc.enabled = 1
        doc.dt = "Sales Invoice"
        doc.view = "Form"
        doc.script = CLIENT_SCRIPT
        doc.save(ignore_permissions=True)
        print("Updated Client Script:", CLIENT_SCRIPT_NAME)
    else:
        frappe.get_doc({
            "doctype": "Client Script",
            "name": CLIENT_SCRIPT_NAME,
            "dt": "Sales Invoice",
            "view": "Form",
            "enabled": 1,
            "script": CLIENT_SCRIPT,
        }).insert(ignore_permissions=True)
        print("Created Client Script:", CLIENT_SCRIPT_NAME)


def run():
    patch_server_module()
    install_client_script()

    frappe.db.commit()
    frappe.clear_cache()

    mod = frappe.get_attr("kpws_customization.api.kpws_sales_invoice_final")

    print("")
    print("Verification:")
    for pos_profile, patient_type in [
        ("Cash", "Cash"),
        ("Welfare", "Welfare"),
        ("Panel", "Panel"),
    ]:
        print(pos_profile, patient_type, "=>", mod.get_price_list_for_pos_profile(pos_profile, patient_type))

    print("")
    print("DONE: Cash/Welfare now use SPW, Panel uses SPP.")

