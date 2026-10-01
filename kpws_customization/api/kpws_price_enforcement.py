import frappe

CLIENT_SCRIPT_NAME = "KPWS FINAL Strict Price List Enforcement"


def _exists_price_list(names):
    for name in names:
        if frappe.db.exists("Price List", name):
            return name
    return ""


def get_patient_type(pos_profile=None, patient_type=None):
    text = (str(patient_type or "") + " " + str(pos_profile or "")).lower()

    if "panel" in text:
        return "Panel"
    if "welfare" in text:
        return "Welfare"
    return "Cash"


@frappe.whitelist()
def get_strict_price_list(pos_profile=None, patient_type=None):
    ptype = get_patient_type(pos_profile, patient_type)

    if ptype == "Panel":
        return _exists_price_list([
            "SPP - Selling Price Panel",
            "SPP",
            "Selling Price Panel",
        ])

    # Cash and Welfare both must use SPW
    return _exists_price_list([
        "SPW - Selling Price Welfare",
        "SPW",
        "Selling Price Welfare",
    ])


def enforce_strict_price_list_on_sales_invoice(doc, method=None):
    target = get_strict_price_list(
        pos_profile=doc.get("pos_profile"),
        patient_type=doc.get("custom_kpws_billing_type"),
    )

    if target and doc.get("selling_price_list") != target:
        doc.selling_price_list = target


def update_pos_profiles():
    spw = _exists_price_list([
        "SPW - Selling Price Welfare",
        "SPW",
        "Selling Price Welfare",
    ])

    spp = _exists_price_list([
        "SPP - Selling Price Panel",
        "SPP",
        "Selling Price Panel",
    ])

    if not spw:
        frappe.throw("Price List not found: SPW - Selling Price Welfare")

    if not spp:
        frappe.throw("Price List not found: SPP - Selling Price Panel")

    if not frappe.db.exists("DocType", "POS Profile"):
        return

    meta = frappe.get_meta("POS Profile")

    if not meta.get_field("selling_price_list"):
        print("POS Profile has no selling_price_list field.")
        return

    for row in frappe.get_all("POS Profile", fields=["name"], limit=200):
        name_l = row.name.lower()

        if "panel" in name_l:
            frappe.db.set_value("POS Profile", row.name, "selling_price_list", spp, update_modified=False)
            print("POS Profile:", row.name, "=>", spp)

        elif "cash" in name_l or "welfare" in name_l:
            frappe.db.set_value("POS Profile", row.name, "selling_price_list", spw, update_modified=False)
            print("POS Profile:", row.name, "=>", spw)


def install_client_script():
    if not frappe.db.exists("DocType", "Client Script"):
        return

    for row in frappe.get_all("Client Script", filters={"dt": "Sales Invoice"}, fields=["name", "script"]):
        if row.name == CLIENT_SCRIPT_NAME:
            continue

        text = ((row.name or "") + "\n" + (row.script or "")).lower()

        if "price list" in text or "selling_price_list" in text:
            frappe.db.set_value("Client Script", row.name, "enabled", 0, update_modified=False)
            print("Disabled old price-list script:", row.name)

    script = r'''
frappe.ui.form.on("Sales Invoice", {
    setup(frm) {
        kpws_strict_price_apply_later(frm);
    },
    onload(frm) {
        kpws_strict_price_apply_later(frm);
    },
    refresh(frm) {
        kpws_strict_price_apply_later(frm);
    },
    pos_profile(frm) {
        kpws_strict_price_apply_now(frm, true);
    },
    custom_kpws_billing_type(frm) {
        kpws_strict_price_apply_now(frm, true);
    },
    patient(frm) {
        kpws_strict_price_apply_later(frm);
    },
    customer(frm) {
        kpws_strict_price_apply_later(frm);
    },
    custom_kpws_mr_number(frm) {
        kpws_strict_price_apply_later(frm);
    },
    selling_price_list(frm) {
        kpws_strict_price_apply_later(frm);
    },
    before_save(frm) {
        return kpws_strict_price_apply_now(frm, false);
    },
    validate(frm) {
        return kpws_strict_price_apply_now(frm, false);
    }
});

frappe.ui.form.on("Sales Invoice Item", {
    item_code(frm, cdt, cdn) {
        kpws_strict_price_apply_later(frm);
    },
    items_add(frm, cdt, cdn) {
        kpws_strict_price_apply_later(frm);
    }
});

function kpws_strict_price_patient_type(frm) {
    let txt = [
        frm.doc.custom_kpws_billing_type || "",
        frm.doc.pos_profile || "",
        frm.doc.customer_group || ""
    ].join(" ").toLowerCase();

    if (txt.includes("panel")) return "Panel";
    if (txt.includes("welfare")) return "Welfare";
    return "Cash";
}

function kpws_strict_price_apply_later(frm) {
    setTimeout(function() { kpws_strict_price_apply_now(frm, false); }, 300);
    setTimeout(function() { kpws_strict_price_apply_now(frm, false); }, 1200);
    setTimeout(function() { kpws_strict_price_apply_now(frm, false); }, 2500);
}

function kpws_strict_price_apply_now(frm, show_loader) {
    if (!frm.doc.pos_profile && !frm.doc.custom_kpws_billing_type) {
        return Promise.resolve();
    }

    if (frm.__kpws_strict_price_running) {
        return Promise.resolve();
    }

    frm.__kpws_strict_price_running = true;

    if (show_loader) {
        frappe.dom.freeze(__("Applying KPWS price list..."));
    }

    return new Promise(function(resolve) {
        frappe.call({
            method: "kpws_customization.api.kpws_price_enforcement.get_strict_price_list",
            args: {
                pos_profile: frm.doc.pos_profile || "",
                patient_type: kpws_strict_price_patient_type(frm)
            },
            freeze: false,
            callback: function(r) {
                let target = r.message || "";

                if (!target) {
                    frm.__kpws_strict_price_running = false;
                    if (show_loader) frappe.dom.unfreeze();
                    resolve();
                    return;
                }

                if (frm.doc.selling_price_list !== target) {
                    frm.set_value("selling_price_list", target).then(function() {
                        frm.refresh_field("selling_price_list");

                        if (frm.doc.items && frm.doc.items.length) {
                            frm.doc.items.forEach(function(row) {
                                if (row.item_code) {
                                    frappe.model.set_value(row.doctype, row.name, "price_list_rate", 0);
                                    frappe.model.set_value(row.doctype, row.name, "rate", 0);
                                }
                            });
                            frm.refresh_field("items");
                        }

                        frm.__kpws_strict_price_running = false;
                        if (show_loader) frappe.dom.unfreeze();
                        resolve();
                    });
                } else {
                    frm.__kpws_strict_price_running = false;
                    if (show_loader) frappe.dom.unfreeze();
                    resolve();
                }
            },
            error: function() {
                frm.__kpws_strict_price_running = false;
                if (show_loader) frappe.dom.unfreeze();
                resolve();
            }
        });
    });
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
    update_pos_profiles()
    install_client_script()
    frappe.db.commit()
    frappe.clear_cache()

    print("")
    print("Verification:")
    for pos_profile, patient_type in [
        ("Cash", "Cash"),
        ("Welfare", "Welfare"),
        ("Panel", "Panel"),
    ]:
        print(pos_profile, patient_type, "=>", get_strict_price_list(pos_profile, patient_type))

    print("")
    print("DONE")
